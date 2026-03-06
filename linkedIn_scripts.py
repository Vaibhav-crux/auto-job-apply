import os
import sys
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys

# Load environment variables from .env
load_dotenv()

EMAIL = os.getenv("LINKEDIN_EMAIL")
PASSWORD = os.getenv("LINKEDIN_PASSWORD")

# Add project root to path so imports from config/utils work if needed later
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import search config
from config.search import search_terms, search_switch_skills, search_location


# ---------------------------------------------------------------------------
# Helper routines
# ---------------------------------------------------------------------------

def login_to_linkedin(driver, wait):
    """Open LinkedIn, navigate to the login form, and submit credentials."""
    # Try to open the login page directly first for speed and robustness.
    # If that fails, fall back to the homepage and click the Sign in link.
    try:
        driver.get("https://www.linkedin.com/login")
        print("✅ Opened LinkedIn login page (direct)")
        email_field = wait.until(
            EC.presence_of_element_located((By.ID, "username"))
        )
    except Exception:
        driver.get("https://www.linkedin.com/")
        print("⚠️ Could not open login page directly; opened homepage")
        try:
            signin = wait.until(
                EC.element_to_be_clickable((By.LINK_TEXT, "Sign in"))
            )
            signin.click()
            print("✅ Clicked 'Sign in' link")
        except Exception:
            driver.get("https://www.linkedin.com/login")
            print("⚠️ Fallback: navigated directly to login page")
        email_field = wait.until(
            EC.presence_of_element_located((By.ID, "username"))
        )
    email_field.clear()
    email_field.send_keys(EMAIL)
    print("✅ Entered email")

    password_field = wait.until(
        EC.presence_of_element_located((By.ID, "password"))
    )
    password_field.clear()
    password_field.send_keys(PASSWORD)
    print("✅ Entered password")

    # ensure 'Keep me logged in' is disabled when present
    try:
        remember_checkbox = wait.until(
            EC.presence_of_element_located((By.ID, "rememberMeOptIn-checkbox"))
        )
        try:
            # Try a normal click first (best for accessibility/handlers)
            if remember_checkbox.is_selected():
                remember_checkbox.click()

            # re-check state/value; some pages keep the attribute/value until JS runs
            value = remember_checkbox.get_attribute("value")
            if remember_checkbox.is_selected() or value == "true":
                # Force the unchecked state and update the value attribute via JS
                driver.execute_script(
                    "arguments[0].checked = false; arguments[0].setAttribute('value','false'); arguments[0].dispatchEvent(new Event('change'));",
                    remember_checkbox,
                )
            print("✅ Disabled 'Keep me logged in'")
        except Exception:
            # Fallback: directly set via JS if click or attribute checks fail
            try:
                driver.execute_script(
                    "arguments[0].checked = false; arguments[0].setAttribute('value','false'); arguments[0].dispatchEvent(new Event('change'));",
                    remember_checkbox,
                )
                print("✅ Disabled 'Keep me logged in' (via JS)")
            except Exception:
                print("⚠️ Could not disable 'Keep me logged in' checkbox")
    except Exception:
        print("ℹ️ 'Keep me logged in' checkbox not found; continuing")

    # click the submit button
    login_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
    )
    login_button.click()
    print("✅ Clicked 'Sign in' button")

    # allow time for login to complete
    time.sleep(5)
    print("🎉 Login successful!")


def navigate_to_jobs(driver, wait):
    """Navigate to the Jobs page."""
    try:
        driver.get("https://www.linkedin.com/jobs/")
        print("✅ Navigated to LinkedIn Jobs page")
        time.sleep(3)  # Wait for page to settle and search boxes to load
        wait.until(EC.presence_of_element_located((By.ID, ":r1:")))
        print("✅ Jobs search box loaded")
    except Exception as e:
        print(f"❌ Error navigating to jobs page: {e}")
        raise


def search_by_skill(driver, wait, skill):
    """Search for jobs by skill/title using the typeahead search box."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            search_box = wait.until(
                EC.presence_of_element_located((By.ID, ":r1:"))
            )
            search_box.clear()
            search_box.send_keys(skill)
            print(f"✅ Typed skill: {skill}")
            time.sleep(1.5)  # Wait for typeahead suggestions to appear
            
            # Re-find the element to avoid stale reference before sending RETURN
            search_box = wait.until(
                EC.presence_of_element_located((By.ID, ":r1:"))
            )
            search_box.send_keys(Keys.RETURN)
            print(f"✅ Pressed Enter to search for: {skill}")
            time.sleep(3)  # Wait for results to load
            return  # Success, exit function
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ Attempt {attempt + 1} failed: {str(e)[:50]}. Retrying...")
                time.sleep(1)
            else:
                print(f"❌ Error searching by skill after {max_retries} attempts: {e}")
                raise


def set_location(driver, wait, location):
    """Set the job search location."""
    if not location or location.strip() == "":
        print("ℹ️ Location not set (search_location is empty)")
        return
    
    try:
        location_box = wait.until(
            EC.presence_of_element_located((By.ID, ":r8:"))
        )
        location_box.clear()
        location_box.send_keys(location)
        print(f"✅ Typed location: {location}")
        time.sleep(1)  # Wait for location suggestions
        
        # Press Enter to apply location filter
        location_box.send_keys(Keys.RETURN)
        print(f"✅ Applied location filter: {location}")
        time.sleep(2)  # Wait for results to update
    except Exception as e:
        print(f"❌ Error setting location: {e}")
        raise


def main():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 20)

    try:
        login_to_linkedin(driver, wait)
        
        # Iterate through search terms
        for idx, skill in enumerate(search_terms):
            print(f"\n{'='*60}")
            print(f"🔍 Searching for skill [{idx + 1}/{len(search_terms)}]: {skill}")
            print(f"{'='*60}")
            
            # Navigate to Jobs page to reset search box (fresh state for each skill)
            navigate_to_jobs(driver, wait)
            
            # Search by skill
            search_by_skill(driver, wait, skill)
            
            # Set location if provided
            if search_location:
                set_location(driver, wait, search_location)
            
            # future functionality: apply for jobs based on search_switch_skills count
            print(f"ℹ️ Will switch to next skill after {search_switch_skills} applications")
            print(f"⏸️ Paused for manual job review. Applications logic to be added next.")
            
            # keep browser open for manual inspection between searches
            input(f"\nPress Enter to continue to next skill (or close to exit)...")

        # keep browser open for manual inspection
        input("\n\nPress Enter to close the browser...")
    except Exception as e:
        print(f"❌ Error during automation: {e}")
    finally:
        driver.quit()
        print("🔒 Browser closed")


if __name__ == "__main__":
    main()
