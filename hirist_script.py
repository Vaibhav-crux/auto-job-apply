import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Load environment variables
load_dotenv()

EMAIL = os.getenv("HIRIST_EMAIL")
PASSWORD = os.getenv("HIRIST_PASSWORD")

# Add project root to path so we can import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config.search import (
    search_terms, date_posted, experience_years, search_location,
    skip_search_terms, skip_company_jobs,
)
from utils.excel_helper import save_to_excel
from config.settings import application_limit, skip_questions
from utils.matching import find_answer, save_question
from utils.confirm_popup import ConfirmPopup
from utils.job_summary_popup import JobSummaryPopup

# Project root for file paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def login_to_hirist(driver, wait):
    """Navigate to Hirist homepage and perform login."""

    driver.get("https://www.hirist.tech/")
    print("✅ Opened Hirist homepage")

    # Wait for page to load
    time.sleep(3)

    # Click the "Jobseeker Login" button
    try:
        jobseeker_btn = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//p[contains(text(), 'Jobseeker Login')]/ancestor::button")
            )
        )
        jobseeker_btn.click()
        print("✅ Clicked Jobseeker Login button")
    except TimeoutException:
        # Fallback: try finding by the image alt text
        jobseeker_btn = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[.//img[@alt='down'] and .//p[contains(text(),'Jobseeker Login')]]")
            )
        )
        jobseeker_btn.click()
        print("✅ Clicked Jobseeker Login button (fallback)")

    time.sleep(2)

    # Enter email
    email_field = wait.until(
        EC.presence_of_element_located((By.NAME, "email"))
    )
    email_field.clear()
    email_field.send_keys(EMAIL)
    print("✅ Entered email")

    # Enter password
    password_field = wait.until(
        EC.presence_of_element_located((By.NAME, "password"))
    )
    password_field.clear()
    password_field.send_keys(PASSWORD)
    print("✅ Entered password")

    # Click Login button
    login_button = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[@type='submit' and contains(text(), 'Login')]")
        )
    )
    login_button.click()
    print("✅ Clicked Login button")

    # Wait for login to complete (page navigation / dashboard load)
    time.sleep(5)
    print("🎉 Login successful!")


def search_jobs(driver, wait):
    """Click search icon, enter first skill, select suggestion, then search."""

    SUGGESTION_XPATH = "//div[contains(@class, 'mui-style')]/li[contains(@class, 'mui-style')]"

    term = search_terms[0]  # Hirist only takes one skill at a time
    print(f"\n🔍 Searching for: {term}")

    # --- 1. Click the search icon in the navbar ---
    search_icon = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "div[data-testid='search_icon']")
        )
    )
    search_icon.click()
    print("✅ Clicked search icon")
    time.sleep(2)

    # --- 2. Type the skill and select a suggestion ---
    skill_input = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "input[name='query'][placeholder='Enter skills/designations/companies']")
        )
    )
    skill_input.click()

    # Set the skill text instantly via JavaScript (avoids per-character delay)
    driver.execute_script("""
        var input = arguments[0];
        var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSetter.call(input, arguments[1]);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    """, skill_input, term)
    print(f"  ⌨️  Typed: {term}")
    time.sleep(3)  # Wait for autocomplete suggestions to appear

    # Try to find a suggestion; if not found, backspace one char at a time until one appears
    suggestion_found = False
    current_text = term

    while current_text:
        try:
            first_option = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, SUGGESTION_XPATH))
            )
            selected_text = first_option.text.strip()
            first_option.click()
            print(f"  ✅ Selected suggestion: {selected_text}")
            suggestion_found = True
            time.sleep(1)
            break
        except TimeoutException:
            # No suggestion found, delete last character and try again
            ActionChains(driver).send_keys(Keys.BACKSPACE).perform()
            current_text = current_text[:-1]
            if current_text:
                print(f"  🔙 Backspaced → '{current_text}'")
                time.sleep(2)  # Wait for new suggestions

    if not suggestion_found:
        print(f"  ⚠️ No suggestions found for '{term}' even after backspacing")

    # --- 3. Click the Search button ---
    search_button = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(@class, 'MuiButton-containedPrimary') and text()='Search']")
        )
    )
    search_button.click()
    print("✅ Clicked Search button")

    # Wait for search results to load
    time.sleep(5)
    print("🎉 Search results loaded!")


def apply_filters(driver, wait):
    """Apply experience and posting date filters on the search results page."""

    print("\n🔧 Applying filters...")

    # --- 1. Experience filter ---
    if experience_years >= 0:
        # Map experience_years to data-value
        # Options: 1=Any, 2=0-1, 3=2-3, 4=4-6, 5=7-10, 6=11-15, 7=16-20, 8=21-25, 9=26+
        if experience_years <= 1:
            exp_value = "2"       # 0 - 1 yrs
        elif experience_years <= 3:
            exp_value = "3"       # 2 - 3 yrs
        elif experience_years <= 6:
            exp_value = "4"       # 4 - 6 yrs
        elif experience_years <= 10:
            exp_value = "5"       # 7 - 10 yrs
        elif experience_years <= 15:
            exp_value = "6"       # 11 - 15 yrs
        elif experience_years <= 20:
            exp_value = "7"       # 16 - 20 yrs
        elif experience_years <= 25:
            exp_value = "8"       # 21 - 25 yrs
        else:
            exp_value = "9"       # 26+ yrs

        try:
            exp_dropdown = wait.until(
                EC.element_to_be_clickable(
                    (By.ID, "lotus-select-experience")
                )
            )
            exp_dropdown.click()
            print("  ✅ Opened Experience dropdown")
            time.sleep(1)

            option = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, f"li[role='option'][data-value='{exp_value}']")
                )
            )
            option_text = option.find_element(By.TAG_NAME, "p").text.strip()
            option.click()
            print(f"  ✅ Selected experience: {option_text} (experience_years={experience_years})")
            time.sleep(1)

        except TimeoutException:
            print(f"  ⚠️ Could not find Experience dropdown or option (value={exp_value})")
    else:
        print("  ⏭️  Experience: skipped (-1)")

    # --- 2. Posting date filter ---
    # Map date_posted to the corresponding data-value
    if date_posted <= 0:
        posting_value = "0"     # All Postings
    elif date_posted <= 3:
        posting_value = "3"     # < 3 Days
    elif date_posted <= 7:
        posting_value = "7"     # Last 1 Week
    elif date_posted <= 15:
        posting_value = "15"    # Last 2 Weeks
    elif date_posted <= 30:
        posting_value = "30"    # Last 1 Month
    else:
        posting_value = "90"    # Last 3 Months

    try:
        posting_dropdown = wait.until(
            EC.element_to_be_clickable(
                (By.ID, "lotus-select-posting")
            )
        )
        posting_dropdown.click()
        print("  ✅ Opened Posting dropdown")
        time.sleep(1)

        option = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, f"li[role='option'][data-value='{posting_value}']")
            )
        )
        option_text = option.find_element(By.TAG_NAME, "p").text.strip()
        option.click()
        print(f"  ✅ Selected posting: {option_text} (date_posted={date_posted})")
        time.sleep(1)

    except TimeoutException:
        print(f"  ⚠️ Could not find Posting dropdown or option (value={posting_value})")

    # --- 3. Location filter ---
    if search_location:
        try:
            loc_dropdown = wait.until(
                EC.element_to_be_clickable(
                    (By.ID, "lotus-select-loc")
                )
            )
            loc_dropdown.click()
            print("  ✅ Opened Location dropdown")
            time.sleep(1)

            # Type the location in the search input inside the dropdown
            loc_search_input = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "input[placeholder='Search Any Location here...']")
                )
            )
            loc_search_input.send_keys(search_location)
            print(f"  ⌨️  Typed location: {search_location}")
            time.sleep(1)

            # Find the first visible matching li option and click it
            try:
                # Get all visible option items in the location menu
                loc_options = driver.find_elements(
                    By.CSS_SELECTOR, "#menu-loc li[role='option'][data-value]"
                )
                selected_loc = False
                for opt in loc_options:
                    try:
                        opt_text = opt.find_element(By.TAG_NAME, "p").text.strip()
                    except Exception:
                        continue
                    if opt.is_displayed() and opt_text:
                        opt.click()
                        print(f"  ✅ Selected location: {opt_text}")
                        selected_loc = True
                        break

                if not selected_loc:
                    print(f"  ⚠️ No matching location found for '{search_location}', using Any Location")
                    # Press Escape to close the dropdown
                    ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            except Exception as e:
                print(f"  ⚠️ Error selecting location: {e}")
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()

            time.sleep(1)

        except TimeoutException:
            print("  ⚠️ Could not find Location dropdown")
    else:
        print("  ⏭️  Location: skipped (empty)")

    # --- 4. Click the Apply button ---
    try:
        apply_button = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[.//p[text()='Apply']]")
            )
        )
        apply_button.click()
        print("  ✅ Clicked Apply button")
        time.sleep(5)
    except TimeoutException:
        print("  ⚠️ Apply button not found")

    print("🎉 Filters applied!")


def handle_screening_questions(driver, wait, popup, job_title):
    """Handle the 'Submit a Form' questions on Hirist after clicking Apply."""
    try:
        # Wait to see if screening questions appear
        time.sleep(3)
        try:
            screening_container = driver.find_element(By.CSS_SELECTOR, "div.screening-questions-container")
        except NoSuchElementException:
            return True # No extra questions, application went through directly

        print(f"    📝 Screening questions detected")
        
        # Loop through all questions
        questions = screening_container.find_elements(By.CSS_SELECTOR, "div.screening-question-container")
        for q_container in questions:
            # Get the question text
            try:
                question_el = q_container.find_element(By.CSS_SELECTOR, "div.question-text")
                question_text = question_el.text.strip()
                # Remove leading numbers like "1." from question
                question_text = ' '.join(question_text.split()[1:]) if bool(question_text) and question_text[0].isdigit() else question_text
            except NoSuchElementException:
                continue

            # Determine type of question and extract options
            has_radio_options = False
            has_text_input = False
            options_list = []
            
            try:
                # Check for radio buttons
                radio_container = q_container.find_element(By.CSS_SELECTOR, "div.answer-options")
                radio_labels = radio_container.find_elements(By.CSS_SELECTOR, "label")
                if radio_labels:
                    has_radio_options = True
                    for lbl in radio_labels:
                        options_list.append(lbl.text.strip())
            except NoSuchElementException:
                try:
                    # Check for text area
                    q_container.find_element(By.CSS_SELECTOR, "textarea.short-answer-text-area")
                    has_text_input = True
                except NoSuchElementException:
                    pass

            if not has_radio_options and not has_text_input:
                continue

            # Get answer from AI / config
            answer, confidence = find_answer(
                question_text,
                options=options_list if has_radio_options else None
            )

            # Auto-skip optional questions if configured
            is_mandatory = "mandatory-question" in q_container.find_element(By.CSS_SELECTOR, "div.question-text > div:last-child").get_attribute("class")
            if popup.disabled and not is_mandatory and skip_questions and confidence == "unknown":
                print(f"      ⏭️  Auto-skipped (optional question)")
                continue

            print(f"      💬 Q: {question_text[:80]}..." if len(question_text) > 80 else f"      💬 Q: {question_text}")
            print(f"         A: {answer if answer else '(unknown)'} [{confidence}]{'' if is_mandatory else ' (skippable)'}")

            # Show Popup
            action, final_answer = popup.show(
                question=question_text,
                answer=answer,
                options=options_list if has_radio_options else None,
                confidence=confidence,
                multi_select=False,
                can_skip=not is_mandatory
            )

            if action == "cancel":
                print("      ❌ User cancelled — skipping this job")
                return False

            if action == "skip":
                print(f"      ⏭️  Skipped question")
                continue

            if final_answer and (confidence == "unknown" or final_answer != answer):
                answer_type = "option" if has_radio_options else "text"
                save_question(question_text, final_answer, answer_type)
                print(f"      💾 Saved Q&A to extra_questions.json")

            if has_radio_options and final_answer:
                try:
                    labels = q_container.find_elements(By.CSS_SELECTOR, "div.answer-options label")
                    for lbl in labels:
                        if lbl.text.strip() == final_answer:
                            driver.execute_script("arguments[0].click();", lbl)
                            print(f"      ✅ Selected option: {final_answer}")
                            break
                    time.sleep(0.5)
                except Exception as e:
                    print(f"      ⚠️ Could not select radio option: {e}")
            elif has_text_input and final_answer:
                try:
                    textarea = q_container.find_element(By.CSS_SELECTOR, "textarea.short-answer-text-area")
                    textarea.clear()
                    textarea.send_keys(final_answer)
                    print(f"      ✅ Entered text: {final_answer[:30] + '...' if len(final_answer)>30 else final_answer}")
                    time.sleep(0.5)
                except Exception as e:
                    print(f"      ⚠️ Could not enter text: {e}")

        # Try to click Next / Submit
        try:
            submit_btn = driver.find_element(By.CSS_SELECTOR, "div.submission-btn button")
            if not submit_btn.get_attribute("disabled"):
                driver.execute_script("arguments[0].click();", submit_btn)
                print(f"      ✅ Clicked form Next/Submit button")
                time.sleep(2)
                return True
            else:
                print(f"      ⚠️ Submit button is disabled. Mandatory questions missing? Skipping...")
                return False
        except NoSuchElementException:
             pass

    except Exception as e:
        print(f"    ⚠️ Error handling screening questions: {e}")
        return False
        
    return True


def browse_jobs(driver, wait, popup):
    """Iterate through job listing cards, open each in a new tab.
    Paginates through pages until application_limit is reached."""

    print(f"\n💼 Browsing job listings... (limit: {application_limit})")

    # Convert skip lists to lowercase for case-insensitive matching
    skip_companies_lower = [c.lower() for c in skip_company_jobs]
    skip_terms_lower = [s.lower() for s in skip_search_terms]

    applied_count = 0
    skipped_count = 0
    total_processed = 0
    applied_jobs_data = []
    main_window = driver.current_window_handle
    page_num = 1

    while applied_count < application_limit:
        print(f"\n  📄 Page {page_num}")

        # Wait for job listings to load
        time.sleep(3)

        # Find all job cards on the page
        job_cards = driver.find_elements(
            By.CSS_SELECTOR, "div.MuiPaper-root[class*='mui-style'] div[data-testid^='job-list-']"
        )

        if not job_cards:
            print("  ⚠️ No job listings found on this page")
            break

        print(f"  📝 Found {len(job_cards)} job(s) on page {page_num}")

        limit_reached = False

        for i, card in enumerate(job_cards):
            if applied_count >= application_limit:
                limit_reached = True
                break

            try:
                # Get the job title
                try:
                    title_el = card.find_element(By.CSS_SELECTOR, "p[data-testid='job_title']")
                    job_title = title_el.text.strip()
                except Exception:
                    job_title = "Unknown"

                # Get the company name (from the parent card's logo alt or nearby elements)
                company_name = "Unknown"
                try:
                    # The company logo is a sibling of the job-list div, in the parent Paper
                    parent_paper = card.find_element(By.XPATH, "./ancestor::div[contains(@class, 'MuiPaper-root')]")
                    logo_el = parent_paper.find_element(By.CSS_SELECTOR, "img.joblist__logo")
                    # The alt text contains the company identifier
                    company_name = logo_el.get_attribute("alt") or "Unknown"
                except Exception:
                    pass

                total_processed += 1

                # Check if company should be skipped
                if company_name.lower() in skip_companies_lower:
                    skipped_count += 1
                    print(f"  ⏭️  [{total_processed}] Skipping: {job_title} @ {company_name} (blacklisted)")
                    continue

                # Check if job title contains skip_search_terms
                title_lower = job_title.lower()
                skip_title = False
                for term in skip_terms_lower:
                    if term in title_lower:
                        skipped_count += 1
                        print(f"  ⏭️  [{total_processed}] Skipping: {job_title} @ {company_name} (title contains '{term}')")
                        skip_title = True
                        break
                if skip_title:
                    continue

                # Scrape job details from the card
                job_details = {
                    "position": job_title,
                    "company": company_name,
                    "location": "",
                    "experience": "",
                    "salary": "",
                    "skills": "",
                    "url": "",
                }

                # Experience from card
                try:
                    exp_el = card.find_element(By.CSS_SELECTOR, "span[data-testid='job_experience']")
                    job_details["experience"] = exp_el.text.strip()
                except Exception:
                    pass

                # Location from card
                try:
                    loc_el = card.find_element(By.CSS_SELECTOR, "p[data-testid='job_location']")
                    job_details["location"] = loc_el.text.strip()
                except Exception:
                    pass

                # Skills/tags from card
                try:
                    tag_els = card.find_elements(By.CSS_SELECTOR, "span[data-testid^='job_tag_']")
                    job_details["skills"] = ", ".join(t.text.strip() for t in tag_els if t.text.strip())
                except Exception:
                    pass

                # Ctrl+Click the job title to open in a new tab
                print(f"\n  🔗 [{total_processed}] Opening: {job_title} @ {company_name}")
                ActionChains(driver).key_down(Keys.CONTROL).click(title_el).key_up(Keys.CONTROL).perform()
                time.sleep(2)

                # Switch to the new tab
                all_windows = driver.window_handles
                new_tab = [w for w in all_windows if w != main_window]
                if not new_tab:
                    print(f"    ⚠️ No new tab opened, skipping")
                    continue

                driver.switch_to.window(new_tab[-1])
                # Bring the new tab to focus in browser
                driver.execute_script("window.focus();")
                time.sleep(3)

                # Capture the job URL
                job_details["url"] = driver.current_url

                # --- Scrape details from the job detail page ---
                # Position
                try:
                    h1_el = driver.find_element(By.CSS_SELECTOR, "h1.MuiTypography-body1")
                    # The h1 contains the title text plus child divs, get just the text node
                    job_details["position"] = driver.execute_script(
                        "return arguments[0].childNodes[0].textContent.trim();", h1_el
                    )
                except Exception:
                    pass

                # Company name (could be an <a> or a <span> inside)
                try:
                    company_el = driver.find_element(By.CSS_SELECTOR, "span[data-testid='company-name']")
                    job_details["company"] = company_el.text.strip()
                except Exception:
                    pass

                # Experience
                try:
                    exp_el = driver.find_element(By.CSS_SELECTOR, "span[data-testid='experience']")
                    job_details["experience"] = exp_el.text.strip()
                except Exception:
                    pass

                # Location (span right after company-name, no data-testid)
                try:
                    loc_el = driver.find_element(
                        By.CSS_SELECTOR, "span.MuiTypography-version_hirist"
                    )
                    job_details["location"] = loc_el.text.strip()
                except Exception:
                    pass

                # Skills from the job-header-main div
                try:
                    skill_links = driver.find_elements(
                        By.CSS_SELECTOR, "div[data-testid='job-header-main'] a"
                    )
                    job_details["skills"] = ", ".join(
                        s.text.strip() for s in skill_links if s.text.strip()
                    )
                except Exception:
                    pass

                print(f"    📋 {job_details['position']} @ {job_details['company']}")
                print(f"       📍 {job_details['location']} | 🧑‍💼 {job_details['experience']} | 🔧 {job_details['skills']}")

                # --- Click Apply button ---
                # Check if already applied
                try:
                    already_applied = driver.find_element(
                        By.XPATH, "//button[contains(@class, 'MuiButton-textPrimary') and text()='Applied']"
                    )
                    if already_applied:
                        skipped_count += 1
                        print(f"    ⏭️  Already applied, skipping")
                        driver.close()
                        driver.switch_to.window(main_window)
                        time.sleep(1)
                        continue
                except NoSuchElementException:
                    pass  # Not applied yet, proceed

                try:
                    apply_btn = wait.until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//button[contains(@class, 'MuiButton-textPrimary') and contains(text(), 'Apply')]")
                        )
                    )
                    apply_btn.click()
                    print(f"    ✅ Clicked Apply")
                    time.sleep(2)

                    # Handle screening questions if they appear
                    success = handle_screening_questions(driver, wait, popup, job_title)
                    if success:
                        applied_count += 1
                        job_details["applied_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        save_to_excel(job_details, platform="hirist")
                        print(f"    🎉 [{applied_count}/{application_limit}] Applied: {job_details['position']} @ {job_details['company']}")
                    else:
                        skipped_count += 1
                        print(f"    ❌ Skipped (user cancelled / form error): {job_title}")

                except (TimeoutException, NoSuchElementException):
                    print(f"    ⚠️ No Apply button found, skipping")
                except Exception as e:
                    print(f"    ⚠️ Error applying: {e}")

                # Close the job tab and switch back
                try:
                    driver.close()
                except Exception:
                    pass
                driver.switch_to.window(main_window)
                time.sleep(1)

            except Exception as e:
                print(f"  ⚠️ [{total_processed}] Error processing job card: {e}")
                try:
                    driver.switch_to.window(main_window)
                except Exception:
                    pass
                continue

        # If limit reached, stop pagination
        if limit_reached:
            print(f"\n  🛑 Application limit reached ({application_limit}).")
            break

        # Try to go to the next page
        try:
            next_btn = driver.find_element(
                By.XPATH, "//button[@aria-label='Go to next page']"
            )
            if next_btn.is_enabled():
                next_btn.click()
                page_num += 1
                print(f"\n  ➡️ Navigating to page {page_num}...")
                time.sleep(3)
            else:
                print("\n  ⚠️ Next button is disabled — no more pages.")
                break
        except NoSuchElementException:
            print("\n  ⚠️ No more pages available.")
            break

    return applied_count, skipped_count, total_processed


def main():
    popup = ConfirmPopup()
    
    # Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 20)

    try:
        # Step 1: Login
        login_to_hirist(driver, wait)

        # Step 2: Search for jobs
        search_jobs(driver, wait)

        # Step 3: Apply filters
        apply_filters(driver, wait)

        # Step 4: Browse and open job listings
        applied_count, skipped_count, total_processed = browse_jobs(driver, wait, popup)

        # Show summary popup
        summary_popup = JobSummaryPopup()
        summary_text = "Application limit reached ({}).\n\n📊 Summary: Opened {}/{} | Skipped {} | Total processed {}".format(
            application_limit, applied_count, application_limit, skipped_count, total_processed
        )
        summary_popup.show(summary_text)
        summary_popup.destroy()

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        driver.quit()
        print("🔒 Browser closed")


if __name__ == "__main__":
    main()
