import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.ttk import Progressbar
import requests
from bs4 import BeautifulSoup
import threading
import logging
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

chrome_driver_path = "/opt/homebrew/bin/chromedriver"
chrome_options = Options()
chrome_options.add_argument("--headless")
service = Service(executable_path=chrome_driver_path)

logging.basicConfig(level=logging.INFO, filename="app.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")

privacy_policy_keywords = ["privacy policy", "privacy-policy", "privacy", "data protection"]
terms_keywords = ["terms and conditions", "terms-of-service", "terms", "conditions"]
ccpa_keywords = [
    "california residents",
    "ccpa",
    "personal information",
    "rights regarding your personal information",
    "you have the following rights"
]

def extract_leadid_and_trustedform(driver):
    try:
        leadid_token = driver.find_element(By.ID, 'leadid_token').get_attribute('value')
        trustedform_script = driver.find_element(By.XPATH, "//script[@src='https://cdn.trustedform.com/trustedform-1.10.8.js']")
        trustedform_embed_link = trustedform_script.get_attribute('src')
        return leadid_token, trustedform_embed_link
    except Exception as e:
        logging.error(f"Error extracting leadid_token or TrustedForm embed link: {e}")
        return None, None

def check_landing_page_for_partner_list(driver, url):
    try:
        driver.get(url)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        keywords = ["partners", "partner-list", "affiliates", "third parties", "marketing partners"]
        partner_page_url = None
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            if any(keyword in href.lower() for keyword in keywords):
                partner_page_url = href
                break
        if not partner_page_url:
            for keyword in keywords:
                if keyword in driver.page_source.lower():
                    partner_page_url = url
                    break
        if partner_page_url and not partner_page_url.startswith(('http://', 'https://')):
            partner_page_url = requests.compat.urljoin(url, partner_page_url)
        return partner_page_url
    except Exception as e:
        logging.error(f"Error analyzing URL {url}: {e}")
        return None

def check_for_jornaya_or_trustedform(driver):
    try:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        jornaya_keywords = ["jornaya", "jornaya.com", "lead-gen", "leadexchange"]
        trustedform_keywords = ["trustedform", "trustedform.com"]
        scripts = soup.find_all('script', src=True)
        iframes = soup.find_all('iframe', src=True)
        for script in scripts + iframes:
            src = script.get('src', '').lower()
            if any(keyword in src for keyword in jornaya_keywords):
                return "Jornaya Embed Found"
            if any(keyword in src for keyword in trustedform_keywords):
                return "TrustedForm Embed Found"
        return "No Jornaya or TrustedForm Embed"
    except Exception as e:
        logging.error(f"Error checking for Jornaya or TrustedForm: {e}")
        return "Error in Embed Check"

def check_tcpas(driver):
    try:
        tcpas = driver.find_elements(By.XPATH, "//a[contains(text(),'TCPA')]")
        for tcpa in tcpas:
            try:
                tcpa.click()
                time.sleep(2)
                popup_content = driver.page_source
                if "partners" in popup_content.lower() or "affiliates" in popup_content.lower():
                    return True
            except:
                continue
    except Exception as e:
        logging.error(f"Error checking TCPA: {e}")
    return False

def check_partner_list_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        content = response.text.lower()
        keywords = ["dabella", "da bella", "dabella interiors"]
        for keyword in keywords:
            if keyword in content:
                return True
        return False
    except requests.RequestException as e:
        logging.error(f"Error fetching partner list: {e}")
        return False

def check_ccpa_content(soup):
    try:
        text = soup.get_text().lower()
        for phrase in ccpa_keywords:
            if phrase in text:
                return True
        return False
    except Exception as e:
        logging.error(f"Error checking CCPA content: {e}")
        return False

def analyze_urls(url_list):
    results = []
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        messagebox.showerror("Error", f"WebDriver Error: {e}")
        logging.error(f"WebDriver Error: {e}")
        return results

    for url in url_list:
        logging.info(f"Analyzing URL: {url}")
        driver.get(url)
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Identify links
        privacy_policy_url = None
        terms_url = None
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text().lower()
            if not privacy_policy_url and any(k in href.lower() or k in text for k in privacy_policy_keywords):
                privacy_policy_url = requests.compat.urljoin(driver.current_url, href)
            if not terms_url and any(k in href.lower() or k in text for k in terms_keywords):
                terms_url = requests.compat.urljoin(driver.current_url, href)

        # Extract Privacy Policy Date
        privacy_policy_info = "Not Found"
        if privacy_policy_url:
            try:
                response = requests.get(privacy_policy_url)
                response.raise_for_status()
                date_match = re.search(
                    r"(?:effective|revised|updated).{0,200}?(?P<date>[A-Za-z]+\s\d{1,2},\s\d{4}|[A-Za-z]+\s\d{4}|\d{4}-\d{2}-\d{2})",
                    response.text,
                    re.IGNORECASE | re.DOTALL
                )
                if date_match:
                    privacy_policy_info = f"Privacy policy: {date_match.group('date')}"
            except Exception as e:
                logging.error(f"Error fetching privacy policy: {e}")

        # Extract Terms Contact Info (email)
        terms_info = "Not Found"
        if terms_url:
            try:
                response = requests.get(terms_url)
                response.raise_for_status()
                emails = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", response.text)
                if emails:
                    terms_info = f"Terms and conditions: {emails[0]}"
                else:
                    terms_info = "Terms and conditions: No contact found"
            except Exception as e:
                logging.error(f"Error fetching terms page: {e}")

        # Partner, Embed, LeadID
        partner_list_url = check_landing_page_for_partner_list(driver, url)
        embed_check_result = check_for_jornaya_or_trustedform(driver)
        leadid_token, trustedform_embed_link = extract_leadid_and_trustedform(driver)

        # Assemble dict result with exact keys
        result = {
            "URL": url,
            "Status": "Partner List Found" if partner_list_url else "No Partner List Found",
            "Partner List URL": partner_list_url or "N/A",
            "Embed Check": embed_check_result or "Not Found",
            "LeadID Token": leadid_token or "Not Found",
            "TrustedForm Embed Link": trustedform_embed_link or "Not Found",
            "Privacy Policy Info": privacy_policy_info,
            "Terms and Conditions Info": terms_info
        }

        results.append(result)

    driver.quit()
    return results


def start_analysis():
    output_text.delete("1.0", tk.END)
    input_text = text_area.get("1.0", "end-1c").strip()
    if not input_text:
        messagebox.showerror("Error", "Please enter URLs, one per line.")
        return
    url_list = input_text.splitlines()
    threading.Thread(target=run_analysis, args=(url_list,)).start()

def run_analysis(url_list):
    results = analyze_urls(url_list)
    for res in results:
        output_str = "\n".join([f"{key}: {value}" for key, value in res.items()])
        output_text.insert(tk.END, output_str + "\n")
        send_to_pipedream(res)

def send_to_pipedream(data):
    WEBHOOK_URL = "https://eopijdtghxj4ezn.m.pipedream.net"
    try:
        requests.post(WEBHOOK_URL, json=data)
    except Exception as e:
        print(f"Error sending to Pipedream: {e}")

root = tk.Tk()
root.title("Webpage Analyzer")
root.geometry("800x600")

label = tk.Label(root, text="Enter URLs (one per line):")
label.pack(pady=5)

text_area = tk.Text(root, height=10)
text_area.pack(fill=tk.BOTH, padx=10, pady=5)

run_button = tk.Button(root, text="Analyze URLs", command=start_analysis)
run_button.pack(pady=10)

output_label = tk.Label(root, text="Results:")
output_label.pack(pady=5)

output_text = tk.Text(root, height=15)
output_text.pack(fill=tk.BOTH, padx=10, pady=5)

root.mainloop()
