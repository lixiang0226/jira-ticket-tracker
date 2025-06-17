# [IMPORTS - keep all, dateutil.parser, datetime, timedelta are no longer strictly needed for is_date_within_year, but dateutil can still be useful for general date parsing if the raw format is inconsistent]
import tkinter as tk
from tkinter import filedialog, messagebox
# from tkinter.ttk import Progressbar
import requests
from bs4 import BeautifulSoup
# import csv
# import os
# import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import threading
import logging
import time
import re
# from dateutil.parser import parse as dateutil_parse # Not strictly needed now if only raw date is kept
# from datetime import datetime, timedelta # Not strictly needed now

# --- DEBUG PRINT FUNCTION ---
def DPRINT(message):
    print(f"[DEBUG] {time.strftime('%H:%M:%S')} - {message}")

# --- Chrome Options & Logging (as before) ---
chrome_options = Options()
chrome_options.add_argument("--headless")
logging.basicConfig(level=logging.INFO, filename="app.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")

# is_date_within_last_year function is no longer needed if we're removing that check.

# --- MODIFIED/NEW EXTRACTION FUNCTIONS ---

def extract_privacy_policy_details(driver):
    DPRINT("Attempting to extract Privacy Policy details using click method...")
    primary_keywords = ["privacy policy", "privacy statement", "privacy notice"]
    secondary_keywords = ["privacy"]

    pp_details = {
        "contact_email": "Not Found",
        "last_updated_raw": "Not Found",
        "ccpa_info": "CCPA Info Not Found", # Default
        "page_url": "Navigation Failed"
    }

    policy_page_url = find_and_navigate_to_policy_page(driver, primary_keywords, secondary_keywords, "Privacy Policy")

    if not policy_page_url:
        DPRINT("  FAILURE: Could not navigate to Privacy Policy page.")
        return pp_details

    pp_details["page_url"] = policy_page_url
    original_landing_url_host = driver.current_url.split('/')[0] + "//" + driver.current_url.split('/')[2] # For navigating back

    try:
        DPRINT(f"  On Privacy Policy page: {driver.current_url}. Extracting details...")
        page_source = driver.page_source
        policy_soup = BeautifulSoup(page_source, 'html.parser')
        page_text_lower = page_source.lower()
        page_text_for_extraction = policy_soup.get_text(separator=" ")

        # Contact Email
        email_pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
        email_matches = list(set(re.findall(email_pattern, page_text_for_extraction)))
        if email_matches:
            pp_details["contact_email"] = ", ".join(email_matches)
            DPRINT(f"    Found emails: {pp_details['contact_email']}")

        # Date Updated (Raw)
        date_patterns = [
            r"(?:last updated|effective date|last revised|date of last revision|this policy was last updated|updated on)[:\s]*([A-Za-z]+\s+\d{1,2},\s+\d{4}|\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]+\s+\d{4})",
            r"([A-Za-z]+\s+\d{1,2},\s+\d{4})", r"(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4})", r"(\d{4}-\d{2}-\d{2})"
        ]
        raw_date_str = "Not Found"
        for i, pattern in enumerate(date_patterns):
            date_match = re.search(pattern, page_text_for_extraction, re.IGNORECASE)
            if date_match:
                raw_date_str = date_match.group(1) if len(date_match.groups()) > 0 else date_match.group(0)
                raw_date_str = raw_date_str.strip()
                DPRINT(f"    Privacy Policy raw date found: '{raw_date_str}' using pattern {i}.")
                break
        pp_details["last_updated_raw"] = raw_date_str

        # CCPA Info
        ccpa_keywords_for_link = ["ccpa", "california consumer privacy act", "your california privacy rights"]
        ccpa_keywords_for_text = ccpa_keywords_for_link + ["do not sell my personal information", "do not sell or share", "shine the light"]

        ccpa_links_found = []
        for link_tag in policy_soup.find_all('a', href=True):
            link_text_lower = link_tag.get_text(strip=True).lower()
            href_lower = link_tag['href'].lower()
            if any(kw in link_text_lower for kw in ccpa_keywords_for_link) or \
                    any(kw in href_lower for kw in ccpa_keywords_for_link):
                resolved_ccpa_link = requests.compat.urljoin(driver.current_url, link_tag['href'])
                ccpa_links_found.append(resolved_ccpa_link)

        if ccpa_links_found:
            pp_details["ccpa_info"] = f"Link(s) Found: {', '.join(list(set(ccpa_links_found))[:2])}" # Show first 2 unique resolved links
            DPRINT(f"    CCPA Link(s) found and resolved: {pp_details['ccpa_info']}")
        else:
            DPRINT("    No direct CCPA links found. Checking for CCPA language keywords...")
            # Why direct link might not be found: Site might embed CCPA details directly, not link to a separate page/anchor.
            # Or, link text/href might not use common CCPA keywords we search for.
            found_text_keywords = [kw for kw in ccpa_keywords_for_text if kw in page_text_lower]
            if found_text_keywords:
                pp_details["ccpa_info"] = f"Language Present (Keywords: {', '.join(list(set(found_text_keywords))[:3])}). No direct link detected. Explanation: Sites may integrate CCPA text directly or use non-standard link phrasing."
                DPRINT(f"    CCPA language keywords found: {found_text_keywords}")
            else:
                pp_details["ccpa_info"] = "CCPA Info Not Found (No specific link or keywords detected)"
                DPRINT("    No CCPA specific links or language keywords detected.")
        # Note: Extracting "full CCPA language" is complex. This approach identifies presence.

    except Exception as e:
        DPRINT(f"  FAILURE: Error extracting details from PP page source: {e}")
    finally:
        # Navigate back logic (same as before)
        current_main_window = driver.window_handles[0]
        if driver.current_window_handle != current_main_window:
            try: driver.close()
            except: pass
            driver.switch_to.window(current_main_window)
        # Check if current_url is the policy page URL, if so, go back
        elif pp_details.get("page_url") and driver.current_url == pp_details["page_url"]:
            driver.back()

        try:
            WebDriverWait(driver, 10).until(lambda d: original_landing_url_host in d.current_url or d.current_url.startswith("data:")) # data: for about:blank like pages
        except TimeoutException:
            DPRINT("Timeout waiting for page after PP processing; current URL might be off.")
        time.sleep(1)
    return pp_details


def extract_terms_details(driver):
    DPRINT("Attempting to extract Terms & Conditions details using click method...")
    primary_keywords = ["terms and conditions", "terms of service", "terms of use", "terms & conditions", "user agreement"]
    secondary_keywords = ["terms", "conditions", "agreement"]

    tc_details = {
        "link_to_pp_full_url": "Not Found",
        "last_updated_raw": "Not Found",
        "page_url": "Navigation Failed"
    }

    policy_page_url = find_and_navigate_to_policy_page(driver, primary_keywords, secondary_keywords, "Terms & Conditions")

    if not policy_page_url:
        DPRINT("  FAILURE: Could not navigate to T&C page.")
        return tc_details

    tc_details["page_url"] = policy_page_url
    original_landing_url_host = driver.current_url.split('/')[0] + "//" + driver.current_url.split('/')[2]


    try:
        DPRINT(f"  On T&C page: {driver.current_url}. Extracting details...")
        page_source = driver.page_source
        policy_soup = BeautifulSoup(page_source, 'html.parser')
        page_text_for_extraction = policy_soup.get_text(separator=" ")

        # T&C Link to Privacy Policy (Full URL)
        pp_link_keywords = ["privacy policy", "privacy notice", "privacy statement"]
        found_pp_link_on_tc_url = "Not Found"
        for link_tag in policy_soup.find_all('a', href=True):
            link_text_lower = link_tag.get_text(strip=True).lower()
            href_lower = link_tag['href'].lower()
            if any(kw in link_text_lower for kw in pp_link_keywords) or \
                    any(kw in href_lower for kw in pp_link_keywords):
                if "privacy" in href_lower: # Basic check
                    resolved_pp_link = requests.compat.urljoin(driver.current_url, link_tag['href'])
                    found_pp_link_on_tc_url = resolved_pp_link
                    DPRINT(f"    Link to Privacy Policy found on T&C page (resolved): {resolved_pp_link}")
                    break
        tc_details["link_to_pp_full_url"] = found_pp_link_on_tc_url

        # Date Updated for T&C (Raw)
        date_patterns = [
            r"(?:last updated|effective date|last revised|date of last revision|this policy was last updated|updated on)[:\s]*([A-Za-z]+\s+\d{1,2},\s+\d{4}|\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]+\s+\d{4})",
            r"([A-Za-z]+\s+\d{1,2},\s+\d{4})", r"(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4})", r"(\d{4}-\d{2}-\d{2})"
        ]
        raw_date_str_tc = "Not Found"
        for i, pattern in enumerate(date_patterns):
            date_match = re.search(pattern, page_text_for_extraction, re.IGNORECASE)
            if date_match:
                raw_date_str_tc = date_match.group(1) if len(date_match.groups()) > 0 else date_match.group(0)
                raw_date_str_tc = raw_date_str_tc.strip()
                DPRINT(f"    T&C raw date found: '{raw_date_str_tc}' using pattern {i}.")
                break
        tc_details["last_updated_raw"] = raw_date_str_tc

    except Exception as e:
        DPRINT(f"  FAILURE: Error extracting details from T&C page source: {e}")
    finally:
        # Navigate back logic (same as before)
        current_main_window = driver.window_handles[0]
        if driver.current_window_handle != current_main_window:
            try: driver.close()
            except: pass
            driver.switch_to.window(current_main_window)
        elif tc_details.get("page_url") and driver.current_url == tc_details["page_url"]:
            driver.back()

        try:
            WebDriverWait(driver, 10).until(lambda d: original_landing_url_host in d.current_url or d.current_url.startswith("data:"))
        except TimeoutException:
            DPRINT("Timeout waiting for page after T&C processing; current URL might be off.")
        time.sleep(1)
    return tc_details

# --- find_and_navigate_to_policy_page (Keep as is from previous version) ---
# ... (This function's logic was confirmed working and doesn't need changes for this request)
def find_and_navigate_to_policy_page(driver, primary_keywords, secondary_keywords, policy_type_name):
    DPRINT(f"Attempting to find and navigate to {policy_type_name} page...")
    original_url = driver.current_url
    original_url_host = original_url.split('/')[0] + "//" + (original_url.split('/')[2] if len(original_url.split('/')) > 2 else original_url)
    DPRINT(f"  Original URL: {original_url}")

    potential_xpaths = []
    for kw_list in [primary_keywords, secondary_keywords]:
        for kw in kw_list:
            kw_lower = kw.lower()
            potential_xpaths.append(f"//a[normalize-space(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'))='{kw_lower}']")
            potential_xpaths.append(f"//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{kw_lower}')]")
            potential_xpaths.append(f"//a[contains(translate(@href, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{kw_lower}')]")

    candidate_elements_with_score = []
    processed_elements = set()

    for xpath_idx, xpath_query in enumerate(potential_xpaths):
        try:
            elements = driver.find_elements(By.XPATH, xpath_query)
            for el in elements:
                if el in processed_elements: continue
                processed_elements.add(el)
                if el.is_displayed() and el.is_enabled():
                    score = len(potential_xpaths) - xpath_idx
                    try:
                        parent = el.find_element(By.XPATH, "./ancestor::*[self::footer or contains(@id,'footer') or contains(@class,'footer') or contains(@id,'legal') or contains(@class,'legal')]")
                        if parent: score += 5
                    except: pass
                    candidate_elements_with_score.append({'element': el, 'score': score})
        except: pass

    if not candidate_elements_with_score:
        DPRINT(f"  No candidate links found for {policy_type_name} using XPath patterns.")
        return None

    sorted_candidates = sorted(candidate_elements_with_score, key=lambda x: x['score'], reverse=True)
    DPRINT(f"  Found {len(sorted_candidates)} potential links for {policy_type_name}, sorted by relevance.")

    successful_navigation_url = None
    original_window = driver.current_window_handle

    for cand_info in sorted_candidates:
        link_element = cand_info['element']
        try:
            link_text = link_element.text.strip()[:50]
            link_href = link_element.get_attribute('href')
            DPRINT(f"  Attempting to click candidate for {policy_type_name} (Score: {cand_info['score']}): Text='{link_text}', Href='{link_href}'")

            driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center', inline: 'center'});", link_element)
            time.sleep(0.5)
            link_element.click()
            time.sleep(3)

            all_windows = driver.window_handles
            if len(all_windows) > 1:
                for window_handle in all_windows:
                    if window_handle != original_window:
                        driver.switch_to.window(window_handle)
                        DPRINT(f"    Switched to new window. URL: {driver.current_url}")
                        break

            navigated_url = driver.current_url
            if navigated_url != original_url and navigated_url != "about:blank" and "javascript:void(0)" not in navigated_url :
                DPRINT(f"  SUCCESS: Navigated to {policy_type_name} page: {navigated_url}")
                successful_navigation_url = navigated_url
                break
            else:
                if len(all_windows) > 1 and driver.current_window_handle != original_window:
                    driver.close()
                    driver.switch_to.window(original_window)
                elif driver.current_url != original_url and (not original_url_host or original_url_host not in driver.current_url):
                    driver.get(original_url)
                    WebDriverWait(driver,10).until(EC.url_to_be(original_url))

        except ElementClickInterceptedException:
            DPRINT(f"    FAILURE: ElementClickInterceptedException for link '{link_text}'. Trying JS click.")
            try:
                driver.execute_script("arguments[0].click();", link_element)
                time.sleep(3)
                all_windows = driver.window_handles
                if len(all_windows) > 1:
                    for window_handle in all_windows:
                        if window_handle != original_window: driver.switch_to.window(window_handle); break
                navigated_url = driver.current_url
                if navigated_url != original_url and navigated_url != "about:blank" and "javascript:void(0)" not in navigated_url :
                    DPRINT(f"  SUCCESS (JS Click): Navigated to {policy_type_name} page: {navigated_url}")
                    successful_navigation_url = navigated_url; break
                else:
                    if len(all_windows) > 1 and driver.current_window_handle != original_window:
                        driver.close(); driver.switch_to.window(original_window)
                    elif driver.current_url != original_url and (not original_url_host or original_url_host not in driver.current_url):
                        driver.get(original_url); WebDriverWait(driver,10).until(EC.url_to_be(original_url))
            except Exception as e_js: DPRINT(f"    FAILURE: JS click also failed for '{link_text}': {e_js}")
        except StaleElementReferenceException: DPRINT(f"    FAILURE: StaleElementReferenceException for link."); pass
        except Exception as e:
            DPRINT(f"    FAILURE: Error clicking link '{link_text}': {type(e).__name__}")
            if len(driver.window_handles) > 1 and driver.current_window_handle != original_window:
                try: driver.close(); driver.switch_to.window(original_window)
                except: pass
            elif driver.current_url != original_url and (not original_url_host or original_url_host not in driver.current_url):
                try: driver.get(original_url); WebDriverWait(driver,10).until(EC.url_to_be(original_url))
                except: DPRINT("Could not return to original URL after click error")

        if not successful_navigation_url:
            if driver.current_window_handle != original_window :
                if driver.current_window_handle in driver.window_handles and len(driver.window_handles) > 1:
                    try: driver.close()
                    except: pass
                driver.switch_to.window(original_window)
            if driver.current_url != original_url: # Check again if URL is original after potential close
                if not original_url_host or original_url_host not in driver.current_url:
                    driver.get(original_url)
                    try: WebDriverWait(driver, 10).until(EC.url_to_be(original_url))
                    except: DPRINT(f"  Failed to return to original URL ({original_url}) for next candidate. Current: {driver.current_url}")

    if successful_navigation_url: return successful_navigation_url
    else:
        DPRINT(f"  {policy_type_name} link not successfully navigated.")
        if driver.current_window_handle != original_window: driver.switch_to.window(original_window)
        if driver.current_url != original_url:
            if not original_url_host or original_url_host not in driver.current_url:
                driver.get(original_url)
                try: WebDriverWait(driver, 10).until(EC.url_to_be(original_url))
                except: pass
        return None

# --- Other existing functions (extract_leadid, check_landing_page_for_partner_list, etc. - KEEP AS IS from previous working version) ---
# ... (These are assumed to be correct from your last confirmed working version)
def extract_leadid_and_trustedform(driver): # (No changes from previous working version)
    DPRINT("Attempting to extract LeadID token and TrustedForm link...")
    leadid_token_val = "Not Found"
    trustedform_embed_link_val = "Not Found"
    try:
        leadid_token_element = driver.find_element(By.ID, 'leadid_token')
        leadid_token_val = leadid_token_element.get_attribute('value')
    except: DPRINT("  leadid_token element not found by ID.")
    try:
        script_elements = driver.find_elements(By.XPATH, "//script[contains(@src, 'activeprospect.com') or contains(@src, 'trustedform.com')]")
        if script_elements: trustedform_embed_link_val = script_elements[0].get_attribute('src')
        else: DPRINT("  TrustedForm/ActiveProspect script element not found.")
    except Exception as e: DPRINT(f"  Error extracting TrustedForm embed link: {e}"); trustedform_embed_link_val = "Error Retrieving"
    DPRINT(f"  Extraction result - LeadID: {leadid_token_val}, TrustedForm: {trustedform_embed_link_val}")
    return leadid_token_val, trustedform_embed_link_val

def check_landing_page_for_partner_list(driver, base_url_of_landing_page): # (No changes from previous)
    DPRINT(f"Checking for partner list link on current page (derived from: {base_url_of_landing_page})")
    partner_page_url = None
    try:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        keywords = ["partners", "partner list", "marketing partners", "affiliates", "third parties"]
        links = soup.find_all('a', href=True)
        for link in links:
            href_val = link.get('href', '') # Ensure href_val is a string
            link_text = link.get_text(strip=True).lower()
            if any(f'\\b{re.escape(keyword)}\\b' in link_text for keyword in keywords) or \
                    any(f'\\b{re.escape(keyword)}\\b' in href_val.lower() for keyword in keywords):
                partner_page_url = href_val; break
        if partner_page_url:
            if not partner_page_url.startswith(('http://', 'https://')):
                partner_page_url = requests.compat.urljoin(driver.current_url, partner_page_url)
            DPRINT(f"  Partner list URL determined: {partner_page_url}")
            return partner_page_url
        else: DPRINT("  No explicit partner list URL identified in links on this page.")
    except Exception as e: DPRINT(f"  FAILURE: Error in check_landing_page_for_partner_list: {e}")
    return None

def check_for_jornaya_or_trustedform(driver): # (No changes from previous)
    DPRINT("Checking for Jornaya or TrustedForm script embeds...")
    result_status = "No Jornaya or TrustedForm Embed"
    try:
        page_source_lower = driver.page_source.lower()
        jornaya_keywords = ["jornaya", "leadid.com", "207.net", "tcpa_guardian_script"]
        trustedform_keywords = ["trustedform", "activeprospect.com"]
        found_jornaya = any(kw in page_source_lower for kw in jornaya_keywords)
        found_trustedform = any(kw in page_source_lower for kw in trustedform_keywords)
        if found_jornaya and found_trustedform: result_status = "Jornaya & TrustedForm Embeds Found"
        elif found_jornaya: result_status = "Jornaya Embed Found"
        elif found_trustedform: result_status = "TrustedForm Embed Found"
    except Exception as e: DPRINT(f"  FAILURE: Error in check_for_jornaya_or_trustedform: {e}"); return "Error in Embed Check"
    DPRINT(f"  Embed check result: {result_status}")
    return result_status

def check_tcpas(driver): # (No changes from previous)
    DPRINT("Checking for TCPA/Consent disclosures with partner references...")
    try:
        page_text_lower = driver.page_source.lower()
        # More targeted check for consent-related text mentioning partners
        # This regex looks for typical consent phrases near partner mentions
        # It's an example; real-world consent language varies greatly
        consent_partner_pattern = r"(by\s+(?:clicking|submitting|checking|continuing|providing|signing\s+up)|i\s+agree|you\s+agree)[\s\S]{0,500}(partners|marketing\s+partners|affiliates|third\s+parties)"

        if re.search(consent_partner_pattern, page_text_lower, re.IGNORECASE):
            DPRINT("    SUCCESS: Partner reference found near consent-related text.")
            return True
    except Exception as e: DPRINT(f"  FAILURE: Error in check_tcpas: {e}")
    DPRINT("  TCPA check complete. No definitive partner reference in consent found on current page.")
    return False

def check_partner_list_content(url_to_check): # (No changes from previous)
    DPRINT(f"Checking content of partner list URL: {url_to_check}")
    if not url_to_check or not url_to_check.startswith(('http://', 'https://')): return False
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'}
        response = requests.get(url_to_check, headers=headers, timeout=20)
        response.raise_for_status()
        content = response.text.lower()
        dabella_keywords = [r"\bdabella\b", r"\bda bella\b", r"\bdabella interiors\b"]
        if any(re.search(pattern, content) for pattern in dabella_keywords):
            DPRINT("    SUCCESS: Found DaBella keyword pattern in partner list content.")
            return True
    except Exception as e: DPRINT(f"  FAILURE: Error/Timeout fetching partner list from {url_to_check}: {e}")
    DPRINT("    FAILURE: DaBella keywords not found in partner list content.")
    return False



# --- analyze_urls (Updated for new data structure and function calls) ---
def analyze_urls(url_list):
    DPRINT(f"Starting analysis for {len(url_list)} URLs.")
    results_data = []
    driver = None
    try:
        DPRINT("Initializing Chrome WebDriver...")
        service_instance = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service_instance, options=chrome_options)
        driver.set_page_load_timeout(45)
        DPRINT("SUCCESS: WebDriver initialized.")
    except Exception as e:
        DPRINT(f"FATAL FAILURE: WebDriver Error during initialization: {e}")
        messagebox.showerror("Error", f"WebDriver Error: {e}")
        logging.critical(f"WebDriver Error during initialization: {e}", exc_info=True)
        return results_data

    num_expected_fields = 11 # Updated number of fields

    for url_idx, url_from_list in enumerate(url_list):
        original_landing_url = url_from_list.strip()
        if not original_landing_url: continue
        if not original_landing_url.startswith(('http://', 'https://')):
            original_landing_url = 'http://' + original_landing_url

        DPRINT(f"--- Analyzing URL {url_idx + 1}/{len(url_list)}: {original_landing_url} ---")

        current_result_values = ["N/A"] * num_expected_fields
        current_result_values[0] = original_landing_url

        try:
            DPRINT(f"  Navigating to landing page: {original_landing_url}")
            driver.get(original_landing_url)
            WebDriverWait(driver, 20).until(lambda d: d.execute_script('return document.readyState') == 'complete')
            time.sleep(2)
            DPRINT(f"  Navigation complete. Current URL: {driver.current_url}")

            # Standard extractions
            current_result_values[4], current_result_values[5] = extract_leadid_and_trustedform(driver)
            current_result_values[3] = check_for_jornaya_or_trustedform(driver)
            partner_list_url = check_landing_page_for_partner_list(driver, original_landing_url)
            current_result_values[2] = partner_list_url if partner_list_url else "N/A"
            has_tcpa_partner_text = check_tcpas(driver)

            dabella_status = "No Explicit Partner List or TCPA Partner Reference Found"
            if partner_list_url: dabella_status = "Partner List Link Found (DaBella check pending)"
            elif has_tcpa_partner_text: dabella_status = "TCPA/Consent with Partner Reference Text Found"
            current_result_values[1] = dabella_status

            # Privacy Policy Details
            DPRINT(f"  Ensuring driver is on landing page {original_landing_url} before PP detail extraction.")
            current_url_main_part = driver.current_url.split('?')[0].split('#')[0].rstrip('/')
            original_landing_url_main_part = original_landing_url.split('?')[0].split('#')[0].rstrip('/')
            if current_url_main_part != original_landing_url_main_part:
                driver.get(original_landing_url)
                WebDriverWait(driver, 20).until(lambda d: d.execute_script('return document.readyState') == 'complete'); time.sleep(1)

            pp_data = extract_privacy_policy_details(driver)
            current_result_values[6] = pp_data.get("contact_email", "N/A")
            current_result_values[7] = pp_data.get("last_updated_raw", "N/A")
            current_result_values[8] = pp_data.get("ccpa_info", "N/A")

            # Terms & Conditions Details
            DPRINT(f"  Ensuring driver is on landing page {original_landing_url} before T&C detail extraction.")
            current_url_main_part = driver.current_url.split('?')[0].split('#')[0].rstrip('/') # Re-check
            if current_url_main_part != original_landing_url_main_part:
                driver.get(original_landing_url)
                WebDriverWait(driver, 20).until(lambda d: d.execute_script('return document.readyState') == 'complete'); time.sleep(1)

            tc_data = extract_terms_details(driver)
            current_result_values[9] = tc_data.get("link_to_pp_full_url", "N/A")
            current_result_values[10] = tc_data.get("last_updated_raw", "N/A")

            if partner_list_url:
                DPRINT(f"  Performing final DaBella check on partner list: {partner_list_url}")
                dabella_found = check_partner_list_content(partner_list_url)
                current_result_values[1] = "DaBella Found on Partner List" if dabella_found else "Partner List Found - DaBella Not Found"

            DPRINT(f"  SUCCESS: Analysis for {original_landing_url} completed.")

        except TimeoutException as te:
            DPRINT(f"  FAILURE: TimeoutException for {original_landing_url}: {te}")
            current_result_values[1] = "Error: Page Load/Interaction Timeout"
        except Exception as page_e:
            DPRINT(f"  FAILURE: General error during analysis of {original_landing_url}: {page_e}")
            current_result_values[1] = f"Error: {type(page_e).__name__} - {str(page_e)[:100]}"

        results_data.append(tuple(current_result_values))
        DPRINT(f"--- End Analysis for URL: {original_landing_url} ---")
        if len(driver.window_handles) > 1:
            try:
                main_window = driver.window_handles[0]
                for handle in driver.window_handles:
                    if handle != main_window: driver.switch_to.window(handle); driver.close()
                driver.switch_to.window(main_window)
            except Exception as e_tab: DPRINT(f"  Error during tab cleanup: {e_tab}")

    if driver: DPRINT("Quitting WebDriver."); driver.quit(); DPRINT("WebDriver quit successfully.")
    DPRINT(f"Finished all URL analyses. Total results: {len(results_data)}")
    return results_data

# --- GUI Section (Updated display_results) ---
def process_input():
    DPRINT("Process_input called.")
    urls_input = text_area.get("1.0", "end-1c").strip()
    if not urls_input: messagebox.showerror("Error", "Please provide URLs."); return
    urls = [u.strip() for u in urls_input.splitlines() if u.strip()]
    if not urls: messagebox.showerror("Error", "Please provide valid URLs."); return

    output_text.delete(1.0, "end")
    output_text.insert(tk.END, f"Processing {len(urls)} URLs... Check console for debug logs.\n\n")
    root.update_idletasks()

    def run_analysis_in_thread():
        analysis_results = analyze_urls(urls)
        root.after(0, lambda: display_results(analysis_results))

    def display_results(results_list):
        output_text.delete(1.0, "end")
        if results_list:
            DPRINT(f"Displaying {len(results_list)} results in GUI.")
            for item in results_list:
                if len(item) == 11: # Expected number of fields (updated)
                    output_text.insert(tk.END, f"URL: {item[0]}\n")
                    output_text.insert(tk.END, f"DaBella/Partner Status: {item[1]}\n")
                    output_text.insert(tk.END, f"Partner List URL: {item[2]}\n")
                    output_text.insert(tk.END, f"Embed Check: {item[3]}\n")
                    output_text.insert(tk.END, f"LeadID Token: {item[4]}\n")
                    output_text.insert(tk.END, f"TrustedForm Embed: {item[5]}\n")
                    output_text.insert(tk.END, f"PP Contact Email: {item[6]}\n")
                    output_text.insert(tk.END, f"PP Last Updated: {item[7]}\n")
                    output_text.insert(tk.END, f"PP CCPA Info: {item[8]}\n")
                    output_text.insert(tk.END, f"T&C Link to Privacy Policy: {item[9]}\n") # Renamed
                    output_text.insert(tk.END, f"T&C Last Updated: {item[10]}\n\n")
                else:
                    DPRINT(f"WARNING: Malformed result tuple (expected 11 fields): {item}")
                    output_text.insert(tk.END, f"Malformed result (expected 11 fields): {item}\n\n")
        else:
            output_text.insert(tk.END, "No results or WebDriver init error. Check console/log.\n")
        DPRINT("GUI display updated.")
        analyze_button.config(state=tk.NORMAL)

    analyze_button.config(state=tk.DISABLED)
    analysis_thread = threading.Thread(target=run_analysis_in_thread, daemon=True)
    analysis_thread.start()

# Tkinter GUI Setup (Same as before)
root = tk.Tk()
root.title("URL Compliance Analyzer v3") # Version bump
frame = tk.Frame(root); frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
tk.Label(frame, text="Enter URLs (one per line):").pack()
text_area_frame = tk.Frame(frame); text_area_frame.pack(fill=tk.X, pady=5)
text_area_scrollbar_y = tk.Scrollbar(text_area_frame, orient=tk.VERTICAL)
text_area = tk.Text(text_area_frame, height=10, width=60, wrap=tk.WORD, yscrollcommand=text_area_scrollbar_y.set)
text_area_scrollbar_y.config(command=text_area.yview); text_area_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
text_area.pack(side=tk.LEFT, fill=tk.X, expand=True)
analyze_button = tk.Button(frame, text="Analyze URLs", command=process_input); analyze_button.pack(pady=10)
tk.Label(frame, text="Results:").pack()
output_text_frame = tk.Frame(frame); output_text_frame.pack(fill=tk.BOTH, expand=True, pady=5)
output_text_scrollbar_y = tk.Scrollbar(output_text_frame, orient=tk.VERTICAL)
output_text = tk.Text(output_text_frame, height=20, width=80, wrap=tk.WORD, yscrollcommand=output_text_scrollbar_y.set)
output_text_scrollbar_y.config(command=output_text.yview); output_text_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

if __name__ == "__main__":
    DPRINT("Starting Tkinter mainloop.")
    root.mainloop()
    DPRINT("Tkinter mainloop finished.")
