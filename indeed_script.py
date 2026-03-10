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
from config.search import search_terms, search_location

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
