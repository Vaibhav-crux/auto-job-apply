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
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException
)

# Load environment variables
load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("EMAIL_PASSWORD")

# Add project root to path so we can import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config.search import (
    search_terms, search_location, experience_years,
    search_terms_counts, skip_search_terms,
    work_mode, salary, date_posted,
    skip_company_jobs,
)
from utils.matching import find_answer, save_question
from utils.confirm_popup import ConfirmPopup
from utils.excel_helper import save_to_excel
from config.settings import application_limit, skip_questions

# Global popup instance (tracks disabled state across jobs)
popup = ConfirmPopup()

# Project root for file paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def login_to_naukri(driver, wait):
    """Navigate to Naukri homepage and perform login."""

    driver.get("https://www.naukri.com/mnjuser/homepage")
    print("✅ Opened Naukri homepage")

    # Wait for the email/username field
    email_field = wait.until(
        EC.presence_of_element_located((By.ID, "usernameField"))
    )
    email_field.clear()
    email_field.send_keys(EMAIL)
    print("✅ Entered email")

    # Enter password
    password_field = wait.until(
        EC.presence_of_element_located((By.ID, "passwordField"))
    )
    password_field.clear()
    password_field.send_keys(PASSWORD)
    print("✅ Entered password")

    # Click login button
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
    """Fill in the search bar with keywords, experience, and location, then search."""

    print(f"\n🔍 Search terms: {search_terms} | Experience: {experience_years} yrs | Location: {search_location}")

    # --- 1. Click the search bar to expand it ---
    search_bar = wait.until(
        EC.element_to_be_clickable((By.ID, "ni-gnb-searchbar"))
    )
    search_bar.click()
    time.sleep(1)

    # --- 2. For each search term, type it, wait for suggestions, and select first 2 ---
    keyword_input = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, ".nI-gNb-sb__keywords .suggestor-input")
        )
    )

    SUGGESTION_SELECTOR = ".nI-gNb-sb__keywords .suggestor-wrapper ul.layer-wrap li.tuple-wrap"

    # Convert skip terms to lowercase for case-insensitive matching
    skip_lower = [s.lower() for s in skip_search_terms]
    # Track all already-selected titles globally to avoid duplicates
    already_selected = set()

    def open_keyword_dropdown(term):
        """Re-expand search bar, find input, type term, return fresh suggestions."""
        # Click search bar to make sure it's expanded
        search_bar = wait.until(
            EC.element_to_be_clickable((By.ID, "ni-gnb-searchbar"))
        )
        search_bar.click()
        time.sleep(0.5)

        # Re-find the input (fresh reference)
        kw_input = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, ".nI-gNb-sb__keywords .suggestor-input")
            )
        )
        kw_input.click()
        time.sleep(0.3)
        kw_input.send_keys(Keys.END)
        time.sleep(0.2)
        kw_input.send_keys(term)
        time.sleep(1.5)

        # Fetch fresh suggestions
        suggestions = wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, SUGGESTION_SELECTOR)
            )
        )
        return suggestions

    for term in search_terms:
        selected_count = 0

        while selected_count < search_terms_counts:
            try:
                suggestions = open_keyword_dropdown(term)

                picked = False
                for suggestion in suggestions:
                    try:
                        option_title = suggestion.find_element(By.CSS_SELECTOR, ".opt").get_attribute("title")
                    except Exception:
                        continue
                    title_lower = option_title.lower()

                    # Skip if matches any skip term
                    if any(skip in title_lower for skip in skip_lower):
                        print(f"  ⏭️  [{term}] Skipping: {option_title} (matches skip term)")
                        continue

                    # Skip if already selected
                    if title_lower in already_selected:
                        print(f"  ⏭️  [{term}] Skipping: {option_title} (already selected)")
                        continue

                    suggestion.click()
                    already_selected.add(title_lower)
                    selected_count += 1
                    print(f"  ✅ [{term}] Selected suggestion {selected_count}: {option_title}")
                    time.sleep(0.8)
                    picked = True
                    break  # Break to re-open dropdown with fresh DOM for next pick

                if not picked:
                    print(f"  ⚠️ [{term}] No more valid suggestions available")
                    break

            except Exception as e:
                print(f"  ⚠️ Could not find suggestions for '{term}': {e}")
                break

    print("  ✅ All keyword suggestions selected")

    # --- 3. Select experience ---
    if experience_years >= 0:
        exp_input = wait.until(
            EC.element_to_be_clickable((By.ID, "experienceDD"))
        )
        exp_input.click()
        time.sleep(1)

        # Click the matching experience option using its value attribute (e.g. value="a2")
        exp_value = f"a{experience_years}"
        exp_option = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, f"ul.dropdown li[value='{exp_value}']")
            )
        )
        exp_option.click()
        print(f"  ✅ Selected experience: {experience_years} years")
        time.sleep(0.5)

    # --- 4. Enter location ---
    if search_location:
        location_input = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, ".nI-gNb-sb__locations .suggestor-input")
            )
        )
        location_input.click()
        location_input.clear()
        location_input.send_keys(search_location)
        time.sleep(1.5)

        # Pick the first suggestion from the dropdown
        try:
            first_suggestion = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".nI-gNb-sb__locations .suggestor-wrapper ul li")
                )
            )
            first_suggestion.click()
        except Exception:
            # If no dropdown appears, press Escape and continue
            location_input.send_keys(Keys.ESCAPE)
        print(f"  ✅ Entered location: {search_location}")

    # --- 5. Click the Search button ---
    search_button = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button.nI-gNb-sb__icon-wrapper")
        )
    )
    search_button.click()
    print("  ✅ Clicked Search button")

    # Wait for search results to load
    time.sleep(5)
    print("🎉 Search results loaded!")


def apply_filters(driver, wait):
    """Apply work mode, salary, and freshness filters on the search results page."""

    print("\n🔧 Applying filters...")

    # --- 1. Work Mode filter ---
    if work_mode:
        try:
            # Expand the Work mode section if collapsed
            wm_heading = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@data-filter-id='wfhType']/ancestor::div[contains(@class,'filterContainer')]//span[text()='Work mode']/following-sibling::i")
                )
            )
            if wm_heading.get_attribute("data-opened") == "false":
                wm_heading.click()
                time.sleep(0.5)

            for mode in work_mode:
                try:
                    checkbox_id = f"chk-{mode}-wfhType-"
                    checkbox = driver.find_element(By.ID, checkbox_id)
                    if not checkbox.is_selected():
                        # Click the label to toggle the checkbox
                        label = driver.find_element(
                            By.CSS_SELECTOR, f"label[for='{checkbox_id}']"
                        )
                        label.click()
                        print(f"  ✅ Selected work mode: {mode}")
                        time.sleep(1)
                except Exception as e:
                    print(f"  ⚠️ Could not select work mode '{mode}': {e}")
        except Exception as e:
            print(f"  ⚠️ Work mode filter not found: {e}")
    else:
        print("  ⏭️  Work mode: skipped (empty list)")

    # --- 2. Salary filter ---
    if salary >= 0:
        try:
            # Expand the Salary section if collapsed
            sal_heading = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@data-filter-id='salaryRange']/ancestor::div[contains(@class,'filterContainer')]//span[text()='Salary']/following-sibling::i")
                )
            )
            if sal_heading.get_attribute("data-opened") == "false":
                sal_heading.click()
                time.sleep(0.5)

            salary_in_lakhs = salary / 100000  # Convert to lakhs

            # Find all salary checkboxes and parse their ranges
            salary_options = driver.find_elements(
                By.CSS_SELECTOR, "div[data-filter-id='salaryRange'] .styles_chckBoxCont__t_dRs"
            )

            selected_salary = False
            for option in salary_options:
                label_el = option.find_element(By.CSS_SELECTOR, ".styles_filterLabel__jRP04")
                label_text = label_el.get_attribute("title")  # e.g. "6-10 Lakhs"

                # Parse the range like "6-10 Lakhs" or "0-3 Lakhs"
                try:
                    range_part = label_text.lower().replace("lakhs", "").replace("lakh", "").strip()
                    parts = range_part.split("-")
                    low = float(parts[0].strip())
                    high = float(parts[1].strip())

                    if low <= salary_in_lakhs <= high:
                        checkbox = option.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                        checkbox_id = checkbox.get_attribute("id")
                        if not checkbox.is_selected():
                            label_click = option.find_element(
                                By.CSS_SELECTOR, f"label[for='{checkbox_id}']"
                            )
                            label_click.click()
                            print(f"  ✅ Selected salary range: {label_text} (salary: {salary})")
                            time.sleep(1)
                        selected_salary = True
                        break
                except (ValueError, IndexError):
                    continue

            if not selected_salary:
                print(f"  ⚠️ No matching salary range found for {salary}")

        except Exception as e:
            print(f"  ⚠️ Salary filter not found: {e}")
    else:
        print("  ⏭️  Salary: skipped (-1)")

    # --- 3. Freshness filter ---
    if date_posted > 0:
        try:
            # Click the freshness dropdown button
            freshness_btn = wait.until(
                EC.element_to_be_clickable((By.ID, "filter-freshness"))
            )
            freshness_btn.click()
            time.sleep(1)

            # Select the option by data-id
            freshness_option = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, f"a[data-id='filter-freshness-{date_posted}']")
                )
            )
            freshness_option.click()
            print(f"  ✅ Selected freshness: Last {date_posted} day(s)")
            time.sleep(1)

        except Exception as e:
            print(f"  ⚠️ Freshness filter error: {e}")
    else:
        print("  ⏭️  Freshness: skipped")

    print("🎉 All filters applied!")


def handle_chatbot(driver, wait, job_title):
    """Handle the Naukri chatbot Q&A flow after clicking Apply."""

    # Wait a moment for chatbot to appear
    time.sleep(2)

    try:
        chatbot = driver.find_element(By.CSS_SELECTOR, "div.chatbot_MessageContainer")
    except NoSuchElementException:
        print("      ℹ️  No chatbot appeared — job applied directly!")
        return True  # Applied successfully without chatbot

    print("      🤖 Chatbot detected, answering questions...")
    max_questions = 20  # Safety limit
    answered = 0

    while answered < max_questions:
        time.sleep(1.5)

        # Get the latest bot question
        try:
            bot_messages = driver.find_elements(By.CSS_SELECTOR, "li.botItem .botMsg span")
            if not bot_messages:
                break
            question_text = bot_messages[-1].text.strip()
            if not question_text:
                break
        except (StaleElementReferenceException, NoSuchElementException):
            break

        # Check if chatbot has closed (no input visible)
        has_text_input = False
        has_radio_options = False
        has_checkbox_options = False
        has_date_input = False
        options_list = []

        # Check for multi-select checkboxes
        try:
            checkbox_container = driver.find_element(By.CSS_SELECTOR, "div.multiselectcheckboxes")
            checkboxes = checkbox_container.find_elements(By.CSS_SELECTOR, "input.mcc__checkbox")
            if checkboxes:
                has_checkbox_options = True
                for cb in checkboxes:
                    options_list.append(cb.get_attribute("value"))
        except NoSuchElementException:
            pass

        # Check for radio button options (only if no checkboxes)
        if not has_checkbox_options:
            try:
                radio_container = driver.find_element(By.CSS_SELECTOR, "div.singleselect-radiobutton-container")
                radio_buttons = radio_container.find_elements(By.CSS_SELECTOR, "input.ssrc__radio")
                if radio_buttons:
                    has_radio_options = True
                    for rb in radio_buttons:
                        options_list.append(rb.get_attribute("value"))
            except NoSuchElementException:
                pass

        # Check for date input (DD/MM/YYYY)
        if not has_checkbox_options and not has_radio_options:
            try:
                driver.find_element(By.CSS_SELECTOR, "div.dob__container")
                has_date_input = True
            except NoSuchElementException:
                pass

        # Check for text input
        if not has_date_input:
            try:
                text_input = driver.find_element(By.CSS_SELECTOR, "div.textArea[contenteditable='true']")
                # Check if it's visible (not d-none)
                input_container = driver.find_element(By.CSS_SELECTOR, "div.chatbot_SendMessageContainer")
                if "d-none" not in (input_container.get_attribute("class") or ""):
                    has_text_input = True
            except NoSuchElementException:
                pass

        if not has_text_input and not has_radio_options and not has_checkbox_options and not has_date_input:
            # Chatbot might be done or transitioning
            time.sleep(1)
            # Check if chatbot container is still visible
            try:
                driver.find_element(By.CSS_SELECTOR, "div.chatbot_MessageContainer")
                # Still there but no input — might be processing
                continue
            except NoSuchElementException:
                break

        # Find the answer
        has_options = has_radio_options or has_checkbox_options
        answer, confidence = find_answer(
            question_text,
            options=options_list if has_options else None
        )

        # For multi-select, answer could be a list
        if has_checkbox_options and isinstance(answer, str) and answer:
            # Try to match multiple options from answer
            answer_lower = answer.lower()
            pre_selected = [opt for opt in options_list if opt.lower() in answer_lower]
            if not pre_selected:
                pre_selected = [answer] if answer in options_list else []
            answer = pre_selected

        # Check for skip chip (optional question)
        can_skip = False
        try:
            chips = driver.find_elements(By.CSS_SELECTOR, "div.chatbot_Chip")
            for chip in chips:
                chip_text = chip.text.strip().lower()
                if "skip" in chip_text:
                    can_skip = True
                    break
        except Exception:
            pass

        print(f"      💬 Q: {question_text[:80]}..." if len(question_text) > 80 else f"      💬 Q: {question_text}")
        print(f"         A: {answer if answer else '(unknown)'} [{confidence}]{' (skippable)' if can_skip else ''}")

        # Auto-skip: when popup disabled + skip_questions=True + question is skippable + no confident answer
        if popup.disabled and can_skip and skip_questions and confidence == "unknown":
            # Click the skip chip
            try:
                chips = driver.find_elements(By.CSS_SELECTOR, "div.chatbot_Chip")
                for chip in chips:
                    if "skip" in chip.text.strip().lower():
                        driver.execute_script("arguments[0].click();", chip)
                        print(f"      ⏭️  Auto-skipped (optional question)")
                        break
                time.sleep(2)
                continue
            except Exception as e:
                print(f"      ⚠️ Error auto-skipping: {e}")

        # Show Tkinter popup for confirmation
        action, final_answer = popup.show(
            question=question_text,
            answer=answer,
            options=options_list if has_options else None,
            confidence=confidence,
            multi_select=has_checkbox_options,
            can_skip=can_skip
        )

        if action == "cancel":
            print("      ❌ User cancelled — skipping this job")
            return False  # Signal to close tab

        if action == "skip":
            # Click the skip chip in the chatbot
            try:
                chips = driver.find_elements(By.CSS_SELECTOR, "div.chatbot_Chip")
                for chip in chips:
                    if "skip" in chip.text.strip().lower():
                        driver.execute_script("arguments[0].click();", chip)
                        print(f"      ⏭️  Skipped question")
                        break
                time.sleep(2)
                continue
            except Exception as e:
                print(f"      ⚠️ Error skipping question: {e}")


        # If "disable", popup.disabled is already set to True

        # Save questions for future use:
        # - Unknown questions with a user answer
        # - User-modified answers (final_answer differs from original)
        if final_answer and (confidence == "unknown" or final_answer != answer):
            if has_checkbox_options:
                answer_type = "checkbox"
                save_answer = ", ".join(final_answer) if isinstance(final_answer, list) else final_answer
            elif has_radio_options:
                answer_type = "option"
                save_answer = final_answer
            else:
                answer_type = "text"
                save_answer = final_answer
            save_question(question_text, save_answer, answer_type)
            print(f"      💾 Saved Q&A to extra_questions.json")

        # Fill in the answer
        if has_radio_options and final_answer:
            # Select the matching radio button and click Save
            try:
                radio_buttons = driver.find_elements(By.CSS_SELECTOR, "div.singleselect-radiobutton-container input.ssrc__radio")
                selected = False

                for rb in radio_buttons:
                    if rb.get_attribute("value") == final_answer:
                        # Use JavaScript click on the radio input (most reliable)
                        driver.execute_script("arguments[0].click();", rb)
                        time.sleep(0.5)

                        # Verify selection
                        if rb.is_selected():
                            print(f"      ✅ Selected option: {final_answer}")
                            selected = True
                        else:
                            # Fallback: click the label
                            try:
                                label = driver.find_element(By.CSS_SELECTOR, f"label[for='{rb.get_attribute('id')}']")
                                label.click()
                                time.sleep(0.5)
                                if rb.is_selected():
                                    print(f"      ✅ Selected option via label: {final_answer}")
                                    selected = True
                            except Exception:
                                pass
                        break

                if selected:
                    time.sleep(0.5)
                    # Click the Save button: <div class="sendMsg">Save</div>
                    try:
                        save_btn = driver.find_element(By.CSS_SELECTOR, "div.sendMsg")
                        driver.execute_script("arguments[0].click();", save_btn)
                        print(f"      ✅ Clicked Save button")
                    except NoSuchElementException:
                        try:
                            save_btn = driver.find_element(By.XPATH, "//div[contains(@class, 'send')]//div[contains(text(), 'Save') or contains(text(), 'Submit')]")
                            driver.execute_script("arguments[0].click();", save_btn)
                            print(f"      ✅ Clicked Save button (fallback)")
                        except NoSuchElementException:
                            print(f"      ℹ️  No Save button found")
                    time.sleep(2)
                else:
                    print(f"      ⚠️ Could not select radio option: {final_answer}")
            except Exception as e:
                print(f"      ⚠️ Error selecting radio option: {e}")

        elif has_checkbox_options and final_answer:
            # Multi-select checkboxes
            selected_list = final_answer if isinstance(final_answer, list) else [final_answer]
            try:
                checkboxes = driver.find_elements(By.CSS_SELECTOR, "div.multiselectcheckboxes input.mcc__checkbox")
                for cb in checkboxes:
                    cb_value = cb.get_attribute("value")
                    should_check = cb_value in selected_list
                    is_checked = cb.is_selected()

                    if should_check and not is_checked:
                        driver.execute_script("arguments[0].click();", cb)
                        time.sleep(0.3)
                    elif not should_check and is_checked:
                        driver.execute_script("arguments[0].click();", cb)
                        time.sleep(0.3)

                print(f"      ✅ Selected checkboxes: {', '.join(selected_list)}")
                time.sleep(0.5)

                # Click Save button
                try:
                    save_btn = driver.find_element(By.CSS_SELECTOR, "div.sendMsg")
                    driver.execute_script("arguments[0].click();", save_btn)
                    print(f"      ✅ Clicked Save button")
                except NoSuchElementException:
                    pass
                time.sleep(2)
            except Exception as e:
                print(f"      ⚠️ Error selecting checkboxes: {e}")

        elif has_date_input and final_answer:
            # Fill date input DD/MM/YYYY
            try:
                date_str = final_answer.strip()
                parts = date_str.split("/")
                if len(parts) == 3:
                    dd, mm, yyyy = parts[0], parts[1], parts[2]

                    day_input = driver.find_element(By.CSS_SELECTOR, "input.dob__input.day")
                    day_input.clear()
                    day_input.send_keys(dd)
                    time.sleep(0.2)

                    month_input = driver.find_element(By.CSS_SELECTOR, "input.dob__input.month")
                    month_input.clear()
                    month_input.send_keys(mm)
                    time.sleep(0.2)

                    year_input = driver.find_element(By.CSS_SELECTOR, "input.dob__input.year")
                    year_input.clear()
                    year_input.send_keys(yyyy)
                    time.sleep(0.3)

                    print(f"      ✅ Entered date: {date_str}")

                    # Click Save button
                    try:
                        save_btn = driver.find_element(By.CSS_SELECTOR, "div.sendMsg")
                        driver.execute_script("arguments[0].click();", save_btn)
                        print(f"      ✅ Clicked Save button")
                    except NoSuchElementException:
                        pass
                    time.sleep(2)
                else:
                    print(f"      ⚠️ Invalid date format: {date_str} (expected DD/MM/YYYY)")
            except Exception as e:
                print(f"      ⚠️ Error filling date: {e}")

        elif has_text_input and final_answer:
            # Type into the contenteditable div
            try:
                text_input = driver.find_element(By.CSS_SELECTOR, "div.textArea[contenteditable='true']")
                text_input.click()
                text_input.clear()
                # Use ActionChains for contenteditable divs
                actions = ActionChains(driver)
                actions.click(text_input).send_keys(final_answer).perform()
                time.sleep(0.3)

                # Press Enter or click Send to submit the message
                text_input.send_keys(Keys.ENTER)
                print(f"      ✅ Typed answer: {final_answer[:50]}..." if len(final_answer) > 50 else f"      ✅ Typed answer: {final_answer}")
                time.sleep(1)
            except Exception as e:
                print(f"      ⚠️ Error typing answer: {e}")

        answered += 1

        # Wait for next question or chatbot to close
        time.sleep(2)

        # Check if chatbot closed
        try:
            driver.find_element(By.CSS_SELECTOR, "div.chatbot_MessageContainer")
        except NoSuchElementException:
            print("      ✅ Chatbot closed — application submitted!")
            return True

    print("      ✅ Chatbot Q&A completed")
    return True


def browse_jobs(driver, wait):
    """Iterate through job listing pages, apply to valid ones, skip blacklisted.
    Paginates through search result pages until application_limit is reached."""

    print(f"\n💼 Browsing job listings... (limit: {application_limit})")

    # Convert skip lists to lowercase for case-insensitive matching
    skip_companies_lower = [c.lower() for c in skip_company_jobs]
    skip_terms_lower = [s.lower() for s in skip_search_terms]

    applied_count = 0
    skipped_count = 0
    external_count = 0
    total_processed = 0
    applied_jobs_data = []  # Collect data for Excel
    main_window = driver.current_window_handle
    page_num = 1

    while applied_count < application_limit:
        print(f"\n  📄 Page {page_num}")

        # Wait for job listings to load
        time.sleep(3)

        job_cards = driver.find_elements(
            By.CSS_SELECTOR, "div.srp-jobtuple-wrapper"
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
                # Get the job ID
                job_id = card.get_attribute("data-job-id")

                # Get the job title
                title_el = card.find_element(By.CSS_SELECTOR, "a.title")
                job_title = title_el.get_attribute("title") or title_el.text

                # Get the company name
                try:
                    company_el = card.find_element(By.CSS_SELECTOR, "a.comp-name")
                    company_name = company_el.get_attribute("title") or company_el.text
                except Exception:
                    company_name = "Unknown"

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

                # Scrape job details from the search card BEFORE opening
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
                    exp_el = card.find_element(By.CSS_SELECTOR, "span.expwdth")
                    job_details["experience"] = (exp_el.get_attribute("title") or exp_el.text).strip()
                except Exception:
                    pass

                # Salary from card
                try:
                    sal_el = card.find_element(By.CSS_SELECTOR, "span.sal span")
                    sal_text = (sal_el.get_attribute("title") or sal_el.text).strip()
                    if sal_text.lower() != "not disclosed":
                        job_details["salary"] = sal_text
                except Exception:
                    pass

                # Location from card
                try:
                    loc_el = card.find_element(By.CSS_SELECTOR, "span.locWdth")
                    job_details["location"] = (loc_el.get_attribute("title") or loc_el.text).strip()
                except Exception:
                    pass

                # Skills from card
                try:
                    skill_els = card.find_elements(By.CSS_SELECTOR, "li.tag-li")
                    job_details["skills"] = ", ".join(s.text.strip() for s in skill_els if s.text.strip())
                except Exception:
                    pass

                # Click the job title to open in new tab
                print(f"\n  🔗 [{total_processed}] Opening: {job_title} @ {company_name} (ID: {job_id})")
                title_el.click()
                time.sleep(2)

                # Switch to the new tab
                all_windows = driver.window_handles
                new_tab = [w for w in all_windows if w != main_window]
                if not new_tab:
                    print(f"    ⚠️ No new tab opened, skipping")
                    continue

                driver.switch_to.window(new_tab[-1])
                time.sleep(2)

                # Check for "Apply on company site" button — skip external
                try:
                    driver.find_element(By.ID, "company-site-button")
                    external_count += 1
                    print(f"    ⏭️  External apply (company site) — closing tab")
                    driver.close()
                    driver.switch_to.window(main_window)
                    continue
                except NoSuchElementException:
                    pass

                # Capture the job URL BEFORE applying
                job_details["url"] = driver.current_url

                # Try clicking the Apply or "I'm interested" button
                try:
                    try:
                        apply_btn = driver.find_element(By.ID, "apply-button")
                    except NoSuchElementException:
                        # Try "I'm interested" button
                        apply_btn = driver.find_element(By.XPATH, "//button[contains(text(), \"interested\") or contains(text(), \"Interested\")]")

                    wait.until(EC.element_to_be_clickable(apply_btn))
                    apply_btn.click()
                    print(f"    ✅ Clicked Apply for: {job_title}")
                    time.sleep(2)

                    # Handle chatbot if it appears
                    success = handle_chatbot(driver, wait, job_title)
                    if success:
                        applied_count += 1
                        job_details["applied_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        save_to_excel(job_details)
                        print(f"    🎉 [{applied_count}/{application_limit}] Applied: {job_details['position']} @ {job_details['company']}")
                    else:
                        skipped_count += 1
                        print(f"    ❌ Skipped (user cancelled): {job_title}")

                except (TimeoutException, NoSuchElementException):
                    print(f"    ⚠️ No Apply/Interested button found, skipping")
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
            # <a class="styles_btn-secondary__2AsIP"><span>Next</span>...</a>
            next_btn = driver.find_element(
                By.XPATH, "//a[contains(@class, 'styles_btn-secondary__2AsIP')]//span[text()='Next']/.."
            )
            next_btn.click()
            page_num += 1
            print(f"\n  ➡️ Navigating to page {page_num}...")
            time.sleep(3)
        except NoSuchElementException:
            print("\n  ⚠️ No more pages available.")
            break

    print(f"\n📊 Summary: Applied {applied_count}/{application_limit} | Skipped {skipped_count} | External {external_count} | Total processed {total_processed}")


def main():
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
        login_to_naukri(driver, wait)

        # Step 2: Search for jobs
        search_jobs(driver, wait)

        # Step 3: Apply filters
        apply_filters(driver, wait)

        # Step 4: Browse and open job listings
        browse_jobs(driver, wait)

        # Keep browser open for inspection
        input("\n\nPress Enter to close the browser...")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        driver.quit()
        print("🔒 Browser closed")


if __name__ == "__main__":
    main()
