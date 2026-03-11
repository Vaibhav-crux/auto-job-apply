"""
Indeed Login Automation
=======================
Uses `nodriver` (Chrome DevTools Protocol, no WebDriver signatures) with a
PERSISTENT Chrome profile so that Cloudflare cf_clearance cookies are saved
between runs.

First run  : Solve every challenge manually. The script waits at each step.
Later runs : Cloudflare recognises the profile and skips the challenge.
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import nodriver as uc

# ── Environment ───────────────────────────────────────────────────────────────
load_dotenv()
INDEED_EMAIL = os.getenv("INDEED_EMAIL")

# Config imports
sys.path.insert(0, str(Path(__file__).parent))
from config.search import search_terms, search_location, date_posted, work_mode
from config.settings import application_limit
from utils.excel_helper import save_to_excel

# Persistent Chrome profile — keeps cookies/cf_clearance between sessions
PROFILE_DIR = Path(__file__).parent / "chrome_profile" / "indeed"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

INDEED_AUTH_URL = (
    "https://secure.indeed.com/auth"
    "?hl=en_IN&co=IN"
    "&continue=https%3A%2F%2Fin.indeed.com%2F"
    "&tmpl=desktop"
    "&from=gnav-util-homepage"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def wait_for(tab, selector: str, timeout: int = 20, description: str = ""):
    """Wait until `selector` exists in the DOM. Returns the element."""
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            el = await tab.find(selector, timeout=2)
            if el:
                return el
        except Exception:
            pass
        await asyncio.sleep(0.5)
    raise TimeoutError(
        f"Timeout ({timeout}s) waiting for: {description or selector}"
    )


async def is_cloudflare_present(tab) -> bool:
    """Return True if a Cloudflare Turnstile iframe is in the page."""
    try:
        html = await tab.get_content()
        return "challenges.cloudflare.com" in html or "cf-turnstile" in html
    except Exception:
        return False


async def wait_past_cloudflare(tab, next_selectors: list, step_label: str,
                               timeout: int = 120):
    """
    If Cloudflare is on screen, pause and wait until one of `next_selectors`
    appears (meaning the challenge was solved).
    """
    if not await is_cloudflare_present(tab):
        return

    print("\n" + "─" * 60)
    print(f"🤖 Cloudflare challenge at: {step_label}")
    print("   Please tick the checkbox in the browser.")
    print("   Script continues automatically once solved.")
    print("─" * 60 + "\n")

    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        for sel in next_selectors:
            try:
                el = await tab.find(sel, timeout=2)
                if el:
                    print("✅ Cloudflare cleared — continuing…")
                    await asyncio.sleep(1)
                    return
            except Exception:
                pass
        # Also stop waiting if Cloudflare is no longer detected
        if not await is_cloudflare_present(tab):
            print("✅ Cloudflare cleared — continuing…")
            await asyncio.sleep(1)
            return
        await asyncio.sleep(1)

    print(f"⚠️  Timed out at Cloudflare step: {step_label}")


# ── Main login flow ───────────────────────────────────────────────────────────

async def login_to_indeed(tab):
    """Full Indeed OTP login flow with Cloudflare handling.
    Skips login entirely if the session is already active.
    """

    # ── Step 1: Check if already logged in ───────────────────────────────────
    # Navigate to homepage; if the job-search box is visible the session is live.
    await tab.get("https://in.indeed.com/")
    print("✅ Opened Indeed homepage")
    await asyncio.sleep(3)

    content = await tab.get_content()
    if "text-input-what" in content:
        print("🎉 Already logged in — skipping sign-in flow.")
        print(f"   Current URL: {tab.url}")
        return  # ← skip everything below

    print("🔒 Not logged in — starting sign-in flow…")

    # ── Step 2: Navigate to auth page ────────────────────────────────────────
    await tab.get(INDEED_AUTH_URL)
    print("✅ Opened Indeed auth page")
    await asyncio.sleep(3)

    # ── Step 3: Handle Cloudflare before email field ──────────────────────────
    await wait_past_cloudflare(
        tab,
        next_selectors=["[name='__email']", "input[type='email']"],
        step_label="auth page load",
    )

    # Step 3 — enter email
    print("⌛ Waiting for email field…")
    try:
        email_field = await wait_for(
            tab, "[name='__email']", timeout=30, description="email field"
        )
    except TimeoutError:
        email_field = await wait_for(
            tab, "input[type='email']", timeout=30, description="email field (fallback)"
        )

    await email_field.click()
    await asyncio.sleep(0.3)
    await email_field.send_keys(INDEED_EMAIL)
    print(f"✅ Entered email: {INDEED_EMAIL}")
    await asyncio.sleep(1)

    # Step 4 — click Continue
    try:
        continue_btn = await wait_for(
            tab,
            "button[data-tn-element='auth-page-email-submit-button']",
            timeout=10,
        )
    except TimeoutError:
        continue_btn = await wait_for(
            tab, "button[type='submit']", timeout=10
        )

    await continue_btn.click()
    print("✅ Clicked Continue")
    await asyncio.sleep(3)

    # Step 5 — Cloudflare after Continue
    await wait_past_cloudflare(
        tab,
        next_selectors=[
            "#auth-page-google-otp-fallback",
            "a[data-tn-element='auth-page-google-password-fallback']",
        ],
        step_label="after Continue",
    )

    # Step 6 — click 'Sign in with a code instead'
    try:
        otp_link = await wait_for(
            tab, "#auth-page-google-otp-fallback", timeout=15
        )
    except TimeoutError:
        otp_link = await wait_for(
            tab,
            "a[data-tn-element='auth-page-google-password-fallback']",
            timeout=15,
        )

    await otp_link.click()
    print("✅ Clicked 'Sign in with a code instead'")
    await asyncio.sleep(3)

    # Step 7 — Cloudflare on OTP page
    await wait_past_cloudflare(
        tab,
        next_selectors=[
            "button[data-tn-element='otp-verify-login-submit-button']",
            "input[autocomplete='one-time-code']",
            "input[inputmode='numeric']",
        ],
        step_label="OTP page",
    )

    # Step 8 — wait for user to enter OTP and click Sign in
    print("\n" + "─" * 60)
    print("⏳ Please check your email/phone for the OTP code.")
    print("   Enter the code in the browser, then click 'Sign in'.")
    print("   Script continues automatically once the page changes.")
    print("─" * 60 + "\n")

    # Poll until OTP submit button disappears OR homepage search appears
    import time
    deadline = time.time() + 300  # 5 minutes
    logged_in = False
    while time.time() < deadline:
        try:
            content = await tab.get_content()
            # Homepage search box appeared → logged in
            if "text-input-what" in content:
                logged_in = True
                break
            # OTP button gone → form submitted, navigating
            if "otp-verify-login-submit-button" not in content:
                await asyncio.sleep(2)
                content = await tab.get_content()
                if "text-input-what" in content or "otp-verify-login-submit-button" not in content:
                    logged_in = True
                    break
        except Exception:
            pass
        await asyncio.sleep(1)

    if logged_in:
        print("✅ Page changed — login detected, continuing…")
    else:
        print("⚠️  5-minute timeout reached. Continuing anyway…")

    await asyncio.sleep(4)

    # Step 9 — confirm homepage
    content = await tab.get_content()
    if "text-input-what" in content:
        print("🎉 Login successful! Indeed homepage search box detected.")
        print(f"   Current URL: {tab.url}")
    else:
        print(f"⚠️  Not on homepage yet. URL: {tab.url}")
        print("   You may already be logged in — continuing.")


async def search_jobs(tab):
    """Fill the Indeed search box with the first term from config/search.py and submit."""

    if not search_terms:
        print("⚠️  No search_terms defined in config/search.py — skipping search.")
        return

    term = search_terms[0]
    print(f"\n🔍 Searching for: '{term}'"
          + (f" in '{search_location}'" if search_location else ""))

    # ── Job title / keyword field ─────────────────────────────────────────────
    what_input = await wait_for(
        tab, "#text-input-what", timeout=20, description="job search input"
    )
    # Clear via JS then type — avoids key-code characters polluting the URL
    await tab.evaluate('document.querySelector("#text-input-what").value = ""')
    await what_input.click()
    await asyncio.sleep(0.2)
    await what_input.send_keys(term)
    print(f"   ⌨️  Typed job term: {term}")
    await asyncio.sleep(0.5)

    # ── Location field (only if search_location is set) ───────────────────────
    if search_location:
        where_input = await wait_for(
            tab, "#text-input-where", timeout=10, description="location input"
        )
        # Clear via JS then type
        await tab.evaluate('document.querySelector("#text-input-where").value = ""')
        await where_input.click()
        await asyncio.sleep(0.2)
        await where_input.send_keys(search_location)
        print(f"   ⌨️  Typed location: {search_location}")
        await asyncio.sleep(0.5)
    else:
        print("   📍 No location specified — leaving blank")

    # ── Click 'Find jobs' ─────────────────────────────────────────────────────
    try:
        find_btn = await wait_for(
            tab,
            "button.yosegi-InlineWhatWhere-primaryButton",
            timeout=10,
            description="Find jobs button",
        )
    except TimeoutError:
        find_btn = await wait_for(
            tab, "button[type='submit']", timeout=10
        )

    await find_btn.click()
    print("✅ Clicked 'Find jobs' — waiting for results…")
    await asyncio.sleep(4)
    print(f"   Result URL: {tab.url}")


async def apply_filters(tab):
    """Apply the Date posted filter based on date_posted in config/search.py.

    date_posted mapping:
        1  → Last 24 hours
        3  → Last 3 days
        7  → Last 7 days
        14 → Last 14 days
        anything else / 0 / -1 → skip (show all dates)
    """
    # Map value → aria-label text
    DATE_MAP = {
        1:  "Last 24 hours",
        3:  "Last 3 days",
        7:  "Last 7 days",
        14: "Last 14 days",
    }

    label = DATE_MAP.get(date_posted)
    if not label:
        print(f"\n📅 date_posted={date_posted} — no Date posted filter applied (showing all)")
        return

    print(f"\n📅 Applying Date posted filter: '{label}'")

    # ── Open the Date posted dropdown ──────────────────────────────────────────
    try:
        date_btn = await wait_for(
            tab, "#fromAge_filter_button", timeout=15,
            description="Date posted filter button"
        )
    except TimeoutError:
        # Fallback: button with aria-label containing 'Date posted'
        date_btn = await wait_for(
            tab,
            "button[aria-label='Date posted filter']",
            timeout=10,
        )

    await date_btn.click()
    print("   ✅ Opened Date posted dropdown")
    await asyncio.sleep(1)

    # ── Click the matching menu item ──────────────────────────────────────────
    try:
        option = await wait_for(
            tab,
            f"a[aria-label='{label}']",
            timeout=10,
            description=f"Date posted option '{label}'",
        )
        await option.click()
        print(f"   ✅ Selected: {label}")
        await asyncio.sleep(3)  # wait for results to refresh
    except TimeoutError:
        print(f"   ⚠️  Could not find option '{label}' in the dropdown")

    # ── Job type filter ───────────────────────────────────────────────────────
    if not work_mode:
        print("\n💼 work_mode is empty — skipping Job type filter")
    else:
        print(f"\n💼 Applying Job type filter: {work_mode}")
        try:
            job_type_btn = await wait_for(
                tab, "#filter-jobtype1", timeout=15,
                description="Job type filter button"
            )
            await job_type_btn.click()
            print("   ✅ Opened Job type modal")
            await asyncio.sleep(1.5)

            # Tick each matching checkbox by matching the visible label text
            all_labels = await tab.select_all("#filter-jobtype1-menu label")
            for label_el in all_labels:
                try:
                    html = await label_el.get_html()
                    matched = next(
                        (m for m in work_mode if m.lower() in html.lower()), None
                    )
                    if matched:
                        await label_el.click()
                        print(f"   ✅ Checked: {matched}")
                        await asyncio.sleep(0.3)
                except Exception as ex:
                    print(f"   ⚠️  Error reading label: {ex}")

            # Click the Update button to apply
            update_btn = await wait_for(
                tab,
                "button[type='submit'][form='filter-jobtype1-menu']",
                timeout=10,
                description="Job type Update button",
            )
            await update_btn.click()
            print("   ✅ Clicked Update — results refreshing…")
            await asyncio.sleep(3)

        except TimeoutError:
            print("   ⚠️  Job type filter button not found — skipping")

async def browse_jobs(tab, browser):
    """Scrape up to application_limit jobs from the results page."""
    print(f"\n📋 Scraping top {application_limit} jobs…\n")

    # Give the page a moment to ensure job cards are loaded
    await asyncio.sleep(2)

    # Job cards are inside `td.resultContent`
    job_cards = await tab.select_all("td.resultContent")

    if not job_cards:
        print("   ⚠️  No job cards found on the page.")
        return

    count = 0
    for card in job_cards:
        if count >= application_limit:
            break

        title = "N/A"
        company = "N/A"
        location = "N/A"
        salary = "N/A"
        job_url = "N/A"
        
        try:
            # Click the main job title link inside the card to load details in the right pane
            title_link = await card.query_selector("h2.jobTitle a")
            if not title_link:
                continue

            await title_link.click()
            await asyncio.sleep(2)  # Wait for the right pane to load
            
            # Capture the current tab URL after clicking on the job
            job_url = tab.url

            # ── Check if it's "Apply on company site" (Skip) ──────────────────
            is_external = False
            try:
                # The "Apply on company site" button appears in the right pane under this container
                external_btn = await tab.query_selector("#viewJobButtonLinkContainer button[contenthtml='Apply on company site']")
                if external_btn:
                    is_external = True
                else:
                    # Fallback check on the span text just in case
                    external_span = await tab.query_selector("#viewJobButtonLinkContainer span")
                    if external_span:
                        span_text = await external_span.get_html()
                        if "Apply on company site" in span_text:
                            is_external = True
            except Exception:
                pass

            if is_external:
                print(f"   ⏭️  Skipping external job (Apply on company site)")
                continue

            # ── Check for "Apply now" ─────────────────────────────────────────
            # It's an Indeed Easy Apply job
            job_type = "N/A"

            # ── Extract Job type from the right pane ──────────────────────────
            try:
                # Matches the specific Job type section by looking at the inner text or aria-label
                # The user provided: <div role="group" aria-label="Job type" ...>
                job_type_group = await tab.query_selector("div[role='group'][aria-label='Job type']")
                if job_type_group:
                    # Inside this group, the actual types are inside `li` elements
                    type_nodes = await job_type_group.query_selector_all("li[data-testid='list-item'] span")
                    types = []
                    for node in type_nodes:
                        html = await node.get_html()
                        # Extract text from span e.g. <span class="...">Full-time</span>
                        if ">" in html and "<" in html.split(">")[1]:
                            text = html.split(">")[1].split("<")[0].strip()
                            if text and text not in types:
                                types.append(text)
                    if types:
                        job_type = ", ".join(types)
            except Exception:
                pass

            # ── Extract basic details from the card itself ────────────────────
            # 1. Job Title
            title_node = await card.query_selector("h2.jobTitle span[title]")
            if title_node:
                html = await title_node.get_html()
                title = html.split(">")[1].split("<")[0].strip()

            # 2. Company Name
            company_node = await card.query_selector('span[data-testid="company-name"]')
            if company_node:
                company = (await company_node.get_html()).split(">")[1].split("<")[0].strip()

            # 3. Location
            location_node = await card.query_selector('div[data-testid="text-location"]')
            if location_node:
                location = (await location_node.get_html()).split(">")[1].split("<")[0].strip()

            # 4. Salary
            salary_node = await card.query_selector('li.salary-snippet-container div.mosaic-provider-jobcards-1f1q1js span')
            if salary_node:
                salary = (await salary_node.get_html()).split(">")[1].split("<")[0].strip()

            print(f"[{count+1}] 🏢 {company}")
            print(f"    │ Role:     {title}")
            print(f"    │ Location: {location}")
            print(f"    │ Type:     {job_type}")
            if salary != "N/A":
                print(f"    │ Salary:   {salary}")
            print("    └" + "─" * 40)
            
            # ── Click "Apply now" ─────────────────────────────────────────────
            try:
                apply_btn = await tab.query_selector("#indeedApplyButton")
                if apply_btn:
                    await apply_btn.click()
                    print("    ▶️  Clicked 'Apply now' — opening application tab…")
                    
                    # Store current tab ID
                    main_tab = tab
                    
                    # Wait for a new tab/window to be created
                    await asyncio.sleep(4)
                    
                    # Get all open tabs, the new one is usually the last
                    all_tabs = browser.tabs
                    if len(all_tabs) > 1:
                        apply_tab = all_tabs[-1]
                        
                        # Bring new tab to the front
                        await apply_tab.bring_to_front()
                        print("    👀 Switched to application tab")
                        
                        # Wait for the "Add a CV for the employer" or Continue button
                        try:
                            # Use the specific data-testid the user provided
                            continue_btn = await wait_for(
                                apply_tab, 
                                "button[data-testid='continue-button']", 
                                timeout=15, 
                                description="Continue button (Add a CV)"
                            )
                            await continue_btn.click()
                            print("    ✅ Clicked 'Continue' to submit CV")
                            await asyncio.sleep(2)  # Wait a moment after clicking
                            
                            # ── Wait for the "Enter a job that shows relevant experience" section ──
                            print("    ⌛ Waiting for job experience section…")
                            try:
                                job_heading = await wait_for(
                                    apply_tab,
                                    "h2.mosaic-provider-module-apply-resume-kousv8",
                                    timeout=15,
                                    description="Job experience heading"
                                )
                                print("    ✅ Found job experience section")
                                await asyncio.sleep(1)
                                
                                # Click the Continue button on this section
                                continue_btn_2 = await wait_for(
                                    apply_tab,
                                    "button[data-testid='continue-button']",
                                    timeout=10,
                                    description="Continue button (Job experience)"
                                )
                                await continue_btn_2.click()
                                print("    ✅ Clicked 'Continue' on job experience section")
                                await asyncio.sleep(3)
                                
                                # ── Wait for the "Please review your application" page ──
                                print("    ⌛ Waiting for application review page…")
                                try:
                                    review_heading = await wait_for(
                                        apply_tab,
                                        "h1.mosaic-provider-module-apply-preview-19k0fjx",
                                        timeout=15,
                                        description="Review application heading"
                                    )
                                    print("    ✅ Found application review page")
                                    await asyncio.sleep(2)
                                    
                                    # ── Handle reCAPTCHA and wait for Submit button to be enabled ──
                                    print("    ⏳ Checking reCAPTCHA status…")
                                    import time
                                    deadline = time.time() + 120  # 2 minutes timeout
                                    submit_enabled = False
                                    
                                    while time.time() < deadline:
                                        try:
                                            submit_btn = await apply_tab.query_selector(
                                                "button[data-testid='submit-application-button']"
                                            )
                                            if submit_btn:
                                                # Check if button is disabled
                                                is_disabled = await apply_tab.evaluate(
                                                    'document.querySelector("button[data-testid=\'submit-application-button\']").disabled'
                                                )
                                                if not is_disabled:
                                                    submit_enabled = True
                                                    print("    ✅ Submit button is now enabled")
                                                    break
                                        except Exception:
                                            pass
                                        
                                        await asyncio.sleep(1)
                                    
                                    if not submit_enabled:
                                        print("    ⚠️  reCAPTCHA not solved or Submit button still disabled after 2 minutes")
                                        print("    ⏳ Please solve the reCAPTCHA manually in the browser window")
                                        print("    ⏳ Waiting for you to solve it…")
                                        
                                        # Wait up to 5 more minutes for user to solve
                                        deadline = time.time() + 300
                                        while time.time() < deadline:
                                            try:
                                                submit_btn = await apply_tab.query_selector(
                                                    "button[data-testid='submit-application-button']"
                                                )
                                                if submit_btn:
                                                    is_disabled = await apply_tab.evaluate(
                                                        'document.querySelector("button[data-testid=\'submit-application-button\']").disabled'
                                                    )
                                                    if not is_disabled:
                                                        print("    ✅ Submit button enabled after user interaction")
                                                        break
                                            except Exception:
                                                pass
                                            await asyncio.sleep(1)
                                    
                                    # Click the Submit button
                                    try:
                                        submit_btn = await apply_tab.query_selector(
                                            "button[data-testid='submit-application-button']"
                                        )
                                        if submit_btn:
                                            await submit_btn.click()
                                            print("    ✅ Clicked 'Submit your application'")
                                            await asyncio.sleep(3)
                                            print("    🎉 Application submitted successfully!")
                                            
                                            # ── Save job to Excel ──────────────────────────
                                            from datetime import datetime
                                            job_data = {
                                                "position": title,
                                                "company": company,
                                                "location": location,
                                                "experience": "N/A",  # Not available from Indeed
                                                "salary": salary,
                                                "skills": job_type,
                                                "url": job_url,
                                                "applied_at": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                                            }
                                            save_to_excel(job_data, platform="indeed")
                                        else:
                                            print("    ⚠️  Submit button not found")
                                    except Exception as e:
                                        print(f"    ⚠️  Failed to click Submit button: {e}")
                                
                                except TimeoutError:
                                    print("    ⚠️  Review page not found or timeout reached.")
                            except TimeoutError:
                                print("    ⚠️  Job experience section not found or timeout reached.")
                            
                        except TimeoutError:
                            print("    ⚠️  Did not find the 'Continue' button in time.")
                        
                        # Close the application tab and return to the main tab
                        await apply_tab.close()
                        await main_tab.bring_to_front()
                        print("    ⤴️  Closed application tab, returning to search results.")
                        await asyncio.sleep(1)
                    else:
                        print("    ⚠️  Application tab did not open.")
                else:
                    print("    ⚠️  'Apply now' button not found on right pane.")
            except Exception as e:
                print(f"    ⚠️  Failed to click Apply now: {e}")

            count += 1

        except Exception as e:
            print(f"   ⚠️  Error processing card: {e}")

    print(f"\n✅ Scraped {count} jobs successfully.")


async def main_async():
    if not INDEED_EMAIL:
        print("❌ INDEED_EMAIL not set in .env. Aborting.")
        return

    print(f"📁 Using Chrome profile: {PROFILE_DIR}")
    print("   (Cookies are saved here — Cloudflare challenge reduces over time)\n")

    browser = await uc.start(
        user_data_dir=str(PROFILE_DIR),
        headless=False,               # must be False for Cloudflare
        browser_args=[
            "--start-maximized",
            "--disable-notifications",
        ],
    )

    tab = await browser.get("https://in.indeed.com/")
    # Give the persistent profile time to fully restore cookies and render the page
    await asyncio.sleep(3)

    try:
        await login_to_indeed(tab)

        # ── Job search ────────────────────────────────────────────────────────
        await search_jobs(tab)

        # ── Filters ────────────────────────────────────────────────────────────
        await apply_filters(tab)

        # ── Scraping ───────────────────────────────────────────────────────────
        await browse_jobs(tab, browser)

        # Keep browser open for the next automation phase
        input("\n\nPress Enter to close the browser...")


    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        browser.stop()
        print("🔒 Browser closed")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
