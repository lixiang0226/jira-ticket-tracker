from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException
import time
import re

# --- Configuration ---
# Keywords for the actual link we want (e.g., "Terms of Service")
TARGET_LINK_KEYWORDS = [
    "terms of service", "terms & conditions", "terms and conditions",
    "user agreement", "legal notice", "terms of use", "service agreement",
    "acceptable use policy"
]
# Keywords for links that might reveal the target link on hover (e.g., "Legal", "Company")
HOVER_PARENT_KEYWORDS = [
    "legal", "company", "about", "resources", "support", "policies", "information"
]
# Keywords that might be found in the href itself if text is unhelpful (e.g., an icon link)
HREF_TARGET_KEYWORDS = [
    "terms", "legal", "tos", "service-agreement", "user-agreement", "policy"
]

# Helper to check if text contains any of the keywords
def contains_keyword(text, keywords):
    if not text:
        return False
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in keywords)

def find_terms_url(driver, base_url):
    """
    Attempts to find the Terms of Service URL on the given page.
    Prioritizes hover-based search, then direct find.
    """
    print(f"\n🔍 Searching for Terms of Service on: {base_url}")
    driver.get(base_url)
    time.sleep(2) # Allow initial page load

    # --- Phase 1: Hover Find (PRIORITIZED) ---
    print("Phase 1: Attempting hover-based find (more precise)...")
    potential_hover_elements = []
    try:
        # Gather all links again, could also include other tags like <li> or <div> if they act as menu headers
        all_elements_for_hover = driver.find_elements(By.XPATH, "//a | //li | //button | //span | //div[string-length(normalize-space(.)) > 0 and string-length(normalize-space(.)) < 50]")

        for el in all_elements_for_hover:
            try:
                el_text = el.text
                if el_text and contains_keyword(el_text, HOVER_PARENT_KEYWORDS):
                    # Filter out links that are clearly target links themselves
                    if not contains_keyword(el_text, TARGET_LINK_KEYWORDS):
                        if el.is_displayed() and el.is_enabled(): # Ensure it's interactable
                            potential_hover_elements.append(el)
            except Exception:
                continue # Stale element or other issue, skip

        # Deduplicate potential hover elements based on text and rough location
        unique_hover_targets = []
        seen_texts_and_locations = set()
        for el in potential_hover_elements:
            try:
                # Use a combination of text and y-coordinate (divided to group nearby elements) as key
                key = (el.text.lower().strip(), el.location['y'] // 20)
                if key not in seen_texts_and_locations:
                    unique_hover_targets.append(el)
                    seen_texts_and_locations.add(key)
            except Exception: # Stale element, etc.
                continue

        print(f"Found {len(unique_hover_targets)} potential hover targets: {[el.text for el in unique_hover_targets[:5]]}...")

        for i, hover_target in enumerate(unique_hover_targets):
            try:
                target_text = hover_target.text.strip()
                if not target_text: # Skip if no text after strip
                    continue
                print(f"\n  Hovering over ({i+1}/{len(unique_hover_targets)}): '{target_text}'")
                ActionChains(driver).move_to_element(hover_target).perform()
                time.sleep(0.8)  # Wait for potential dropdown/popup to appear

                all_links_after_hover = driver.find_elements(By.TAG_NAME, "a")
                for link_after_hover in all_links_after_hover:
                    link_text = link_after_hover.text
                    link_href = link_after_hover.get_attribute("href")

                    if not link_href:
                        continue

                    if contains_keyword(link_text, TARGET_LINK_KEYWORDS):
                        if link_after_hover.is_displayed():
                            print(f"    🎯 Found link after hover: '{link_text}' -> {link_href}")
                            return link_href # Found via hover, return immediately
                        # else:
                        #     print(f"    (Found '{link_text}' but it's not visible)")

            except ElementNotInteractableException:
                print(f"    ⚠️ Could not interact with (hover over): '{target_text}' (possibly obscured or not interactable)")
            except NoSuchElementException:
                print(f"    ⚠️ Hover target '{target_text}' became stale or disappeared.")
            except Exception as e:
                print(f"    Error during hover attempt on '{target_text if 'target_text' in locals() else 'unknown element'}': {type(e).__name__} - {e}")

            # Optional: Move mouse away to close menu if it persists
            try:
                # Attempt to move to a neutral corner of the page to reset hover states
                body_element = driver.find_element(By.TAG_NAME, "body")
                ActionChains(driver).move_to_element_with_offset(body_element, 5, 5).perform()
                time.sleep(0.2)
            except: # If body element cannot be found or other issues
                try: # Fallback to relative move
                    ActionChains(driver).move_by_offset(50, 50).perform()
                    time.sleep(0.2)
                except:
                    pass # Ignore if moving mouse away fails

    except Exception as e:
        print(f"Error during hover find setup: {e}")

    print("\nPhase 1 (Hover) did not find the URL. Proceeding to fallback...")

    # --- Phase 2: Direct Find (FALLBACK) ---
    print("Phase 2: Attempting direct find (fallback)...")
    try:
        all_links_phase1 = driver.find_elements(By.TAG_NAME, "a")
        for link in all_links_phase1:
            link_text = link.text
            link_href = link.get_attribute("href")

            if not link_href: # Skip if no href
                continue

            # Check link text first
            if contains_keyword(link_text, TARGET_LINK_KEYWORDS):
                if link.is_displayed(): # Check if it's actually visible
                    print(f"🎯 Found direct link by text: '{link_text}' -> {link_href}")
                    return link_href

            # Fallback: Check href content if text is not descriptive (e.g. icon links)
            if (not link_text or len(link_text.strip()) < 5) and contains_keyword(link_href, HREF_TARGET_KEYWORDS):
                if link.is_displayed():
                    print(f"🎯 Found direct link by href content: '{link_href}'")
                    return link_href

    except Exception as e:
        print(f"Error during direct find: {e}")


    print("\n❌ Terms of Service URL not found after all attempts.")
    return None

if __name__ == "__main__":
    # --- WebDriver Setup ---
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    # options.add_argument("--headless") # Consider enabling for faster runs after debugging
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(5)

        test_urls = [
            "https://stripe.com/",            # Good for hover test ("Legal" -> "Stripe Services Agreement")
            "https://www.python.org",         # Footer link ("Legal" -> "Terms and Conditions")
            "https://www.amazon.com",         # Footer link ("Conditions of Use")
            "https://www.reddit.com/",        # Footer or menu ("User Agreement")
            "https://www.microsoft.com/en-us/", # Footer link ("Terms of use")
            "https://www.example.com"         # Unlikely to find
        ]

        target_url = input("Enter the URL of the website (e.g., https://example.com): ")
        if target_url: # Only process if user enters something
            if not target_url.startswith("http"):
                target_url = "https://" + target_url

            if target_url not in test_urls:
                test_urls.insert(0, target_url)

        for url in test_urls:
            if not url.strip():
                continue
            terms_page_url = find_terms_url(driver, url)
            if terms_page_url:
                print(f"✅ Final Terms URL for {url}: {terms_page_url}")
            else:
                print(f"⚠️ No Terms URL found for {url}.")
            print("-" * 50)
            time.sleep(1)

    except Exception as e:
        print(f"An overall error occurred: {e}")
    finally:
        if driver:
            print("Quitting WebDriver.")
            driver.quit()
