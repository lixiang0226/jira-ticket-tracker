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

# key word list
privacy_policy_keywords = ["privacy policy", "privacy-policy", "privacy", "data protection"]
terms_keywords = ["terms and conditions", "terms-of-service", "terms", "conditions"]
ccpa_keywords = [
    "california residents",
    "ccpa",
    "personal information",
    "rights regarding your personal information",
    "you have the following rights"
]


# modified
def extract_leadid_and_trustedform(driver):
    try:
        leadid_token = driver.find_element(By.ID, 'leadid_token').get_attribute('value')
    except Exception:
        leadid_token = "Not Found"

    try:
        script = driver.find_element(By.XPATH, "//script[contains(@src, 'trustedform')]")
        trustedform_embed_link = script.get_attribute('src')
    except Exception:
        trustedform_embed_link = "Not Found"

    return leadid_token, trustedform_embed_link

# new stuff
def extract_privacy_policy_details(driver):
    """
    extract data from PP page
    :param driver:
    :return:
    """
    try:
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # find anchor tags that are clickable
        links = soup.find_all('a', href=True)
        privacy_link = None

        # go through the links to identify what matches the PP keywords
        # if found make the url and assign to privacy link element
        for link in links:
            if any(k in link.get_text().lower() for k in privacy_policy_keywords):
                privacy_link = requests.compat.urljoin(driver.current_url, link['href'])
                break
        if not privacy_link:
            # return all "not found" for the 4 outputs
            return "Not Found", "Not Found", "Not Found", "Not Found"

        # send http request to the url
        response = requests.get(privacy_link)
        response.raise_for_status()

        # store the html content of the PP page
        content = response.text
        soup = BeautifulSoup(content, 'html.parser')
        text = soup.get_text()

        # using regex patterns to find mail, date, and ccpa
        # Email
        email_match = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        email = ", ".join(email_match) if email_match else "Not Found"

        # Date
        # accepts both month day and day month formats
        date_match = re.search(
            r"(?:last updated|effective date)[:\s]*([A-Za-z]+\s\d{1,2},\s\d{4}|[A-Za-z]+,?\s\d{4}|\d{4}-\d{2}-\d{2})",
            text,
            re.IGNORECASE
        )
        date = date_match.group(1) if date_match else "Not Found"

        # CCPA
        ccpa_keywords_found = [k for k in ccpa_keywords if k in text.lower()]
        ccpa_info = ", ".join(ccpa_keywords_found[:3]) if ccpa_keywords_found else "Not Found"

        return email, date, ccpa_info, privacy_link
    except Exception as e:
        logging.error(f"Error extracting PP details: {e}")
        return "Error", "Error", "Error", "Error"


# new
def extract_terms_details(driver):
    """
    function to extract info from T&C page"
    :param driver:
    :return:
    """
    try:
        # parse and find all clickable
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        links = soup.find_all('a', href=True)
        terms_link = None

        # loop through to check if any links match T&C keywords
        for link in links:
            if any(k in link.get_text().lower() for k in terms_keywords):
                terms_link = requests.compat.urljoin(driver.current_url, link['href'])
                break
        if not terms_link:
            return "Not Found", "Not Found"

        # send http request and store content
        response = requests.get(terms_link)
        response.raise_for_status()
        text = response.text

        # regex identification to find the date of T&C page
        # also includes both day month and month dat format
        date_match = re.search(
            r"(?:last updated|effective date)[:\s]*([A-Za-z]+\s\d{1,2},\s\d{4}|[A-Za-z]+,?\s\d{4}|\d{4}-\d{2}-\d{2})",
            text,
            re.IGNORECASE
        )
        date = date_match.group(1) if date_match else "Not Found"
        return date, terms_link
    except Exception as e:
        logging.error(f"Error extracting T&C details: {e}")
        return "Error", "Error"


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

# modified for the additional data field
def analyze_urls(url_list):
    results = []
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        messagebox.showerror("Error", f"WebDriver Error: {e}")
        logging.error(f"WebDriver Error: {e}")
        return results

    for url in url_list:
        try:
            logging.info(f"Analyzing URL: {url}")
            driver.get(url)
            time.sleep(2)

            # Partner detection
            partner_list_url = check_landing_page_for_partner_list(driver, url)
            partner_status = "Found" if partner_list_url else "Not Found"

            # TrustedForm + LeadID
            leadid_token, trustedform_embed = extract_leadid_and_trustedform(driver)

            # Embed check
            embed_check_result = check_for_jornaya_or_trustedform(driver)

            # Privacy Policy details
            pp_email, pp_date, pp_ccpa, pp_url = extract_privacy_policy_details(driver)

            # Terms & Conditions details
            tc_date, tc_url = extract_terms_details(driver)

            # Compose result
            result = (
                url,
                partner_status,
                partner_list_url or "N/A",
                leadid_token,
                trustedform_embed,
                embed_check_result,
                pp_email,
                pp_date,
                pp_ccpa,
                pp_url,
                tc_date,
                tc_url
            )
            results.append(result)
        except Exception as e:
            logging.error(f"Error analyzing {url}: {e}")
            results.append((url, "Error") + ("N/A",) * 10)

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

# modified for additional data field and some layout changes after talking
# with the complaince team
def run_analysis(url_list):
    results = analyze_urls(url_list)
    for res in results:
        output_lines = [
            f"URL: {res[0]}",
            f"Partner Status: {res[1]}",
            f"Partner List URL: {res[2]}",
            f"LeadID Token: {res[3]}",
            f"TrustedForm Embed: {res[4]}",
            f"Embed Check: {res[5]}",
            f"Privacy Policy Contact Email: {res[6]}",
            f"Privacy Policy Last Updated Date: {res[7]}",
            f"Privacy Policy CCPA Info: {res[8]}",
            f"Privacy Policy URL: {res[9]}",
            f"Terms & Conditions Last Updated Date: {res[10]}",
            f"Terms & Conditions URL: {res[11]}"
        ]
        output_str = "\n".join(output_lines) + "\n"
        output_text.insert(tk.END, output_str)
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
