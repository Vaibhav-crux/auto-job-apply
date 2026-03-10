import os
import sys
import time
import threading
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
from config.search import search_terms, search_switch_skills, search_location, linkedin_easy_apply, date_posted


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


def click_easy_apply_filter(driver, wait):
    """Click the LinkedIn 'Easy Apply' filter pill button if not already selected."""
    # Try locating by ID first, then fall back to aria-label
    locators = [
        (By.ID, "searchFilter_applyWithLinkedin"),
        (By.XPATH, "//button[@aria-label='Easy Apply filter.']"),
        (By.XPATH, "//button[contains(@aria-label,'Easy Apply')]"),
    ]

    easy_apply_btn = None
    for by, value in locators:
        try:
            easy_apply_btn = wait.until(EC.presence_of_element_located((by, value)))
            break
        except Exception:
            continue

    if easy_apply_btn is None:
        print("⚠️ 'Easy Apply' filter button not found on this page — skipping")
        return

    try:
        # Scroll the button into view to avoid click interception
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", easy_apply_btn)
        time.sleep(0.5)

        # Check if already active
        if easy_apply_btn.get_attribute("aria-checked") == "true":
            print("ℹ️ 'Easy Apply' filter already active")
            return

        # Use JS click — most reliable for LinkedIn pill/filter buttons
        driver.execute_script("arguments[0].click();", easy_apply_btn)
        print("✅ Clicked 'Easy Apply' filter")
        time.sleep(2)  # Wait for results to refresh
    except Exception as e:
        print(f"⚠️ Could not click 'Easy Apply' filter: {e}")


def click_date_posted_filter(driver, wait):
    """Open the 'Date posted' dropdown, select the right option, and click 'Show results'."""
    # Map config value → LinkedIn radio input ID (stable semantic IDs, NOT dynamic ember IDs)
    # LinkedIn options: r86400 (24h), r604800 (week), r2592000 (month)
    if date_posted == 1:
        radio_id = "timePostedRange-r86400"
        label = "Past 24 hours"
    elif date_posted <= 7:
        radio_id = "timePostedRange-r604800"
        label = "Past week"
    elif date_posted <= 30:
        radio_id = "timePostedRange-r2592000"
        label = "Past month"
    else:
        print("ℹ️ date_posted not mapped to a LinkedIn filter — skipping Date posted filter")
        return

    try:
        # ── Step 1: Open the 'Date posted' pill dropdown ──────────────────────
        date_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "searchFilter_timePostedRange"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", date_btn)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", date_btn)
        print("✅ Opened 'Date posted' dropdown")

        # ── Step 2: Wait for dropdown panel to appear before reading radio ────
        # Presence of any date-posted radio input confirms the panel is open
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[name='date-posted-filter-value']")
        ))
        time.sleep(0.3)

        # ── Step 3: Click the radio (timePostedRange-* IDs are stable) ────────
        radio = driver.find_element(By.ID, radio_id)
        driver.execute_script("arguments[0].click();", radio)
        print(f"✅ Selected Date posted: {label}")
        time.sleep(0.5)

        # ── Step 4: Click 'Show X results' button ─────────────────────────────
        # aria-label starts with "Apply current filter" — the result count is dynamic
        # so we match on the stable prefix only (never use ember IDs — they change every load)
        show_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(@aria-label, 'Apply current filter')]")
        ))
        driver.execute_script("arguments[0].click();", show_btn)
        print("✅ Clicked 'Show results' — filter applied")
        time.sleep(2)  # Wait for results to refresh

    except Exception as e:
        print(f"⚠️ Could not set 'Date posted' filter: {e}")
        # Try to close any open dropdown gracefully
        try:
            driver.find_element(By.ID, "searchFilter_timePostedRange").click()
        except Exception:
            pass

def wait_for_user_or_timeout(timeout=60):
    """Wait up to `timeout` seconds for the user to press Enter, then continue."""
    print(f"\n⏳ You have {timeout}s to apply any filters manually in the browser.")
    print("   Press Enter at any time to skip the wait and start browsing jobs...")

    entered = threading.Event()

    def _read_input():
        try:
            input()
        except Exception:
            pass
        entered.set()

    t = threading.Thread(target=_read_input, daemon=True)
    t.start()

    # Count down, printing remaining seconds every 10s
    interval = 10
    elapsed = 0
    while elapsed < timeout:
        if entered.wait(timeout=min(interval, timeout - elapsed)):
            print("✅ Enter pressed — starting job browsing now")
            return
        elapsed += interval
        remaining = timeout - elapsed
        if remaining > 0:
            print(f"   ⏳ {remaining}s remaining... (press Enter to skip)")

    print("⏰ Timeout reached — starting job browsing automatically")


def browse_job_cards(driver, wait, count):
    """Click on the first `count` job cards in the search results list."""
    if count <= 0:
        print("ℹ️ search_switch_skills is 0 — skipping job browsing")
        return

    print(f"\n🗂️ Browsing up to {count} job cards from the results list...")

    # LinkedIn can render cards as either:
    #   <li data-occludable-job-id="...">  (outer scaffold wrapper)
    #   <div data-job-id="...">            (inner clickable card container)
    # After manual filter changes the page reloads — wait actively for cards
    # rather than relying on a fixed sleep.
    SELECTORS = [
        ("li[data-occludable-job-id]", "data-occludable-job-id"),
        ("div[data-job-id]",           "data-job-id"),
    ]

    job_cards = []
    id_attr = None

    # Retry up to 3 times with a 3-second gap to handle slow page reloads
    for attempt in range(1, 4):
        for selector, attr in SELECTORS:
            try:
                # Wait up to 10s for at least one card to appear
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                found = driver.find_elements(By.CSS_SELECTOR, selector)
                if found:
                    job_cards = found
                    id_attr = attr
                    print(f"   Using selector: {selector} — found {len(found)} cards")
                    break
            except Exception:
                continue
        if job_cards:
            break
        print(f"   ⏳ Attempt {attempt}/3: no cards yet, waiting 3s...")
        time.sleep(3)

    if not job_cards:
        print("⚠️ No job cards found after waiting — make sure you're on the job search results page")
        return


    target = min(count, len(job_cards))
    print(f"   Will click first {target} of {len(job_cards)} cards")

    for i in range(target):
        card = job_cards[i]
        job_id = card.get_attribute(id_attr) or f"#{i+1}"
        try:
            # Prefer clicking the title link; fall back to the card element itself
            link = card.find_element(By.CSS_SELECTOR, "a.job-card-container__link")
            title = link.get_attribute("aria-label") or f"Job {job_id}"
        except Exception:
            link = card
            title = f"Job {job_id}"

        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", link)
            print(f"   [{i+1}/{target}] ✅ Clicked: {title}")
            time.sleep(1.5)  # Brief pause between clicks
        except Exception as e:
            print(f"   [{i+1}/{target}] ⚠️ Could not click job {job_id}: {e}")

    print(f"✅ Done browsing {target} job cards")



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

            # Filters are applied manually by the user during the wait below

            # Wait for user to apply any extra manual filters, then browse jobs
            wait_for_user_or_timeout(timeout=60)
            browse_job_cards(driver, wait, search_switch_skills)

        # keep browser open for manual inspection
        input("\n\nPress Enter to close the browser...")
    except Exception as e:
        print(f"❌ Error during automation: {e}")
    finally:
        driver.quit()
        print("🔒 Browser closed")


if __name__ == "__main__":
    main()
