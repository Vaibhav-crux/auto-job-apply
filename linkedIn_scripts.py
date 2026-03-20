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

# Add project root to path so we can import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config.search import (
    search_terms, search_location, experience_years,
    search_terms_counts, skip_search_terms,
    work_mode, salary, date_posted,
    skip_company_jobs, linkedin_easy_apply
)
from config.settings import application_limit
from utils.matching import find_answer
from utils.excel_helper import save_to_excel

# Load credentials from environment
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")

def login_to_linkedin(driver, wait):
    """Navigate to LinkedIn login page and perform login."""
    if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
        raise ValueError("LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables must be set")

    driver.get("https://www.linkedin.com/login")
    print("✅ Opened LinkedIn login page")

    # Wait for the username field
    username_field = wait.until(
        EC.presence_of_element_located((By.ID, "username"))
    )
    username_field.clear()
    username_field.send_keys(LINKEDIN_EMAIL)
    print("✅ Entered username")

    # Enter password
    password_field = wait.until(
        EC.presence_of_element_located((By.ID, "password"))
    )
    password_field.clear()
    password_field.send_keys(LINKEDIN_PASSWORD)
    print("✅ Entered password")

    # Uncheck "Keep me logged in" checkbox
    try:
        remember_label = driver.find_element(By.XPATH, "//label[@for='rememberMeOptIn-checkbox']")
        remember_label.click()
        print("✅ Unchecked 'Keep me logged in'")
    except NoSuchElementException:
        print("ℹ️  'Keep me logged in' checkbox not found")

    # Click sign in button
    sign_in_button = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[@type='submit' and contains(text(), 'Sign in')]")
        )
    )
    sign_in_button.click()
    print("✅ Clicked Sign in button")

    # Wait for login to complete (may require manual verification)
    try:
        wait.until(lambda driver: driver.current_url == "https://www.linkedin.com/feed/")
        print("🎉 Login successful!")
    except TimeoutException:
        print("⚠️  Login verification may be required. Please check your LinkedIn app and confirm sign-in.")
        input("Press Enter after confirming sign-in on your app...")
        wait.until(lambda driver: driver.current_url == "https://www.linkedin.com/feed/")
        print("🎉 Login successful!")
def search_jobs(driver, wait, search_term):
    """Go to LinkedIn jobs page with search term and location via URL."""
    print(f"\n🔍 Searching for: {search_term} | Location: {search_location}")

    # Construct search URL
    url = f"https://www.linkedin.com/jobs/search/?keywords={search_term.replace(' ', '%20')}"
    if search_location:
        url += f"&location={search_location.replace(' ', '%20')}"
    driver.get(url)

    # Wait for results to load
    time.sleep(5)
    print("🎉 Search results loaded!")
def apply_filters(driver, wait):
    """Apply filters based on config, following the technique from test.txt."""
    print("\n🔧 Applying filters...")

    # Click "All filters" button to open the filter modal
    try:
        all_filters_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="All filters"]'))
        )
        all_filters_button.click()
        time.sleep(2)
        print("  ✅ Opened All filters modal")
    except Exception as e:
        print(f"  ❌ Failed to open All filters: {e}")
        return
    # Experience level filter (if experience_years is set)
    if experience_years >= 0:
        try:
            # Map experience_years to levels
            levels = []
            if experience_years <= 1:
                levels.append("Internship")
            if experience_years <= 2:
                levels.append("Entry level")
            if experience_years <= 5:
                levels.append("Associate")
            if experience_years <= 10:
                levels.append("Mid-Senior level")
            if experience_years > 10:
                levels.append("Director")

            for level in levels:
                print(f"  🔍 Selecting {level}...")
                level_span = wait.until(
                    EC.element_to_be_clickable((By.XPATH, f"//span[normalize-space()='{level}']"))
                )
                level_span.click()
                time.sleep(1)
            if levels:
                print(f"  ✅ Selected experience levels: {levels}")
            else:
                print("  ⏭️  No matching experience levels")
        except Exception as e:
            print(f"  ❌ Experience filter failed: {e}")
    else:
        print("  ⏭️  Experience: skipped (-1)")

    # Date posted filter
    if date_posted > 0:
        try:
            # Map date_posted to option
            if date_posted == 1:
                option = "Past 24 hours"
            elif date_posted == 3:
                option = "Past 3 days"
            elif date_posted == 7:
                option = "Past week"
            elif date_posted <= 15:
                option = "Past 2 weeks"
            else:
                option = "Past month"

            print(f"  🔍 Selecting {option}...")
            # Click the span with the option text
            option_span = wait.until(
                EC.element_to_be_clickable((By.XPATH, f"//span[normalize-space()='{option}']"))
            )
            option_span.click()
            time.sleep(1)
            print(f"  ✅ Selected date posted: {option}")
        except Exception as e:
            print(f"  ❌ Date posted filter failed: {e}")
    else:
        print("  ⏭️  Date posted: skipped")

    # Work mode filter
    if work_mode:
        try:
            # Map work_mode to LinkedIn terms
            linkedin_modes = []
            for mode in work_mode:
                if "remote" in mode.lower():
                    linkedin_modes.append("Remote")
                elif "hybrid" in mode.lower():
                    linkedin_modes.append("Hybrid")
                elif "on-site" in mode.lower() or "office" in mode.lower():
                    linkedin_modes.append("On-site")

            for mode in linkedin_modes:
                print(f"  🔍 Selecting {mode}...")
                mode_span = wait.until(
                    EC.element_to_be_clickable((By.XPATH, f"//span[normalize-space()='{mode}']"))
                )
                mode_span.click()
                time.sleep(1)
            if linkedin_modes:
                print(f"  ✅ Selected work modes: {linkedin_modes}")
        except Exception as e:
            print(f"  ❌ Work mode filter failed: {e}")
    else:
        print("  ⏭️  Work mode: skipped (empty list)")

    # Salary filter - skip for now as it's -1
    if salary >= 0:
        print("  ⏭️  Salary: not implemented yet")
    else:
        print("  ⏭️  Salary: skipped (-1)")

    # Easy Apply filter - toggle checkbox
    if linkedin_easy_apply:
        try:
            # Try multiple approaches to find and click the Easy Apply toggle
            easy_apply_checkbox = None
            selectors = [
                # Method 1: Find checkbox with role="switch" near "Easy Apply" text
                "//input[@role='switch' and @data-artdeco-toggle-button='true' and ancestor::*[.//span[contains(text(), 'Easy Apply')]]]",
                # Method 2: Find via the toggle div that contains "Easy Apply"
                "//div[contains(@class, 'artdeco-toggle') and .//span[contains(text(), 'Easy Apply')]]//input[@role='switch']",
                # Method 3: Find any toggle with Easy Apply nearby
                "//*[contains(text(), 'Easy Apply')]/ancestor::div[@class='artdeco-toggle']//input[@role='switch']",
            ]
            
            for selector in selectors:
                try:
                    easy_apply_checkbox = driver.find_element(By.XPATH, selector)
                    if easy_apply_checkbox:
                        break
                except:
                    continue
            
            if easy_apply_checkbox:
                # Check if already enabled (aria-checked="true")
                is_checked = easy_apply_checkbox.get_attribute('aria-checked') == 'true'
                
                if not is_checked:
                    # Click to enable
                    driver.execute_script("arguments[0].scrollIntoView(true);", easy_apply_checkbox)
                    time.sleep(0.5)
                    easy_apply_checkbox.click()
                    time.sleep(1)
                    print("  ✅ Enabled Easy Apply filter")
                else:
                    print("  ✅ Easy Apply filter already enabled")
            else:
                print("  ⏭️  Easy Apply filter: checkbox not found")
        except Exception as e:
            print(f"  ⏭️  Easy Apply filter: error ({type(e).__name__})")

    # Click "Show results" button
    try:
        show_results_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-test-reusables-filters-modal-show-results-button='true']"))
        )
        show_results_button.click()
        time.sleep(2)
        print("  ✅ Applied filters and showed results")
    except Exception as e:
        print(f"  ❌ Failed to show results: {e}")

    print("🎉 Filters applied!")

def extract_job_details(job, job_index):
    """Extract job details from job element."""
    try:
        # Try to get job link - handle missing <a> tag gracefully
        job_details_button = None
        try:
            job_details_button = job.find_element(By.TAG_NAME, 'a')
        except NoSuchElementException:
            # If no <a> tag, try nested elements
            try:
                job_details_button = job.find_element(By.XPATH, ".//*[contains(@href, '/jobs/')]")
            except:
                print(f"  ⏭️  Job {job_index + 1}: No clickable link found, skipping")
                return None
        
        job_id = job.get_dom_attribute('data-occludable-job-id')
        if not job_id:
            print(f"  ⏭️  Job {job_index + 1}: No job ID found, skipping")
            return None
            
        title = job_details_button.text.split('\n')[0] if job_details_button and job_details_button.text else "Unknown"
        
        # Check for Easy Apply badge
        has_easy_apply = False
        try:
            # Try multiple selectors to find Easy Apply badge
            easy_apply_selectors = [
                ".//span[contains(text(), 'Easy Apply')]",
                ".//span[contains(@class, 'easy-apply')]",
                ".",  # Check the element itself
            ]
            
            for selector in easy_apply_selectors:
                try:
                    elem = job.find_element(By.XPATH, selector)
                    if elem and 'Easy Apply' in elem.text:
                        has_easy_apply = True
                        break
                except:
                    continue
        except:
            pass
        
        # Extract company, location, and work style from subtitle
        try:
            other_details = job.find_element(By.CLASS_NAME, 'artdeco-entity-lockup__subtitle').text
        except:
            other_details = ""
        
        company = "Unknown"
        work_location = "Unknown"
        work_style = ""
        
        if other_details:
            # Parse: "Company · Location (WorkStyle)" or "Company · Location" or other variations
            parts = other_details.split(' · ')
            
            if len(parts) >= 1:
                company = parts[0].strip()
            
            if len(parts) >= 2:
                remaining = ' · '.join(parts[1:]).strip()
                
                # Extract work style if present in parentheses
                if '(' in remaining and ')' in remaining:
                    start = remaining.rfind('(')
                    end = remaining.rfind(')')
                    work_style = remaining[start+1:end]
                    work_location = remaining[:start].strip()
                else:
                    work_location = remaining
        
        return {
            'job_id': job_id,
            'title': title,
            'company': company,
            'location': work_location,
            'style': work_style,
            'has_easy_apply': has_easy_apply,
            'index': job_index + 1
        }
    except Exception as e:
        print(f"  ❌ Failed to extract details for job {job_index + 1}: {e}")
        return None

def should_skip_job(job_details):
    """Check if job should be skipped based on skip_search_terms, skip_company_jobs, or Easy Apply setting."""
    if not job_details:
        return True
    
    title = job_details['title'].lower()
    company = job_details['company'].lower()
    
    # Check skip_search_terms
    for skip_term in skip_search_terms:
        if skip_term.lower() in title:
            print(f"  ⏭️  Skipping: '{skip_term}' found in title")
            return True
    
    # Check skip_company_jobs
    for skip_company in skip_company_jobs:
        if skip_company.lower() in company:
            print(f"  ⏭️  Skipping: '{skip_company}' found in company name")
            return True
    
    # Check Easy Apply filter
    if linkedin_easy_apply and not job_details.get('has_easy_apply', False):
        print(f"  ⏭️  Skipping: Easy Apply not available (setting enabled)")
        return True
    
    return False

def click_apply_button(driver, wait):
    """Click the 'Easy Apply' button on job details panel."""
    try:
        # Close any lingering dialogs first
        close_any_dialogs(driver)
        time.sleep(1)
        
        # Try different selectors for the Easy Apply button
        selectors = [
            "//button[contains(@class, 'jobs-apply-button') and contains(., 'Easy Apply')]",
            "//button[contains(., 'Easy Apply')]",
            "//div[contains(@class, 'jobs-details__main-content')]//button[contains(., 'Easy Apply')]",
            "//button[@aria-label='Easy Apply to this job']",
            "//button[contains(@aria-label, 'Apply')]",
            "//div[@class='jobs-apply-button__container']//button",
        ]
        
        for selector in selectors:
            try:
                apply_button = driver.find_element(By.XPATH, selector)
                
                # Check if it's enabled and visible
                if apply_button.is_displayed() and apply_button.is_enabled():
                    # Scroll into view
                    driver.execute_script("arguments[0].scrollIntoView(true);", apply_button)
                    time.sleep(0.5)
                    
                    # Try regular click first
                    try:
                        apply_button.click()
                    except:
                        # If blocked, use JavaScript click
                        driver.execute_script("arguments[0].click();", apply_button)
                    
                    time.sleep(2)
                    print("  ✅ Clicked Easy Apply button")
                    return True
            except:
                continue
        
        print("  ❌ Easy Apply button not found or not clickable")
        return False
    except Exception as e:
        print(f"  ❌ Failed to click Easy Apply button: {e}")
        return False

def answer_application_questions(driver, wait):
    """Answer application questions with ALWAYS showing popups (except 4 excluded fields)."""
    try:
        from selenium.webdriver.support.select import Select
        from config.personals import (
            first_name, last_name, current_city, current_state,
            current_country, current_experience_years, current_experience_months,
            gender, disability_status, veteran_status, linkedin_profile, phone_number,
            current_salary, expected_salary, notice_period
        )
        from utils.confirm_popup import ConfirmPopup
        
        popup = ConfirmPopup()
        
        # Wait for modal to appear
        modal = wait.until(
            EC.presence_of_element_located((By.XPATH, "//div[@data-test-modal-id='easy-apply-modal']"))
        )
        time.sleep(1)
        
        # Find all form elements
        all_questions = modal.find_elements(By.XPATH, ".//div[@data-test-form-element]")
        
        if not all_questions:
            print("  ℹ️  No form fields found")
            return
        
        print(f"  📝 Found {len(all_questions)} form fields to fill")
        
        popup_disabled = False
        
        for question_idx, question in enumerate(all_questions):
            try:
                # ============ CHECK IF IT'S A SELECT DROPDOWN ============
                try:
                    select_elem = question.find_element(By.XPATH, ".//select")
                    # Find the label
                    label_text = ""
                    try:
                        label_elem = question.find_element(By.XPATH, ".//label")
                        label_text = label_elem.find_element(By.XPATH, ".//span").text
                    except:
                        label_text = "Unknown"
                    
                    select = Select(select_elem)
                    current_value = select.first_selected_option.text
                    all_options = [opt.text for opt in select.options]
                    label_lower = label_text.lower()
                    
                    # Check if this is an excluded field (NO POPUP)
                    is_excluded = ('email' in label_lower or 'phone' in label_lower or 
                                   'contact' in label_lower or 'resume' in label_lower or 
                                   'cv' in label_lower or 'document' in label_lower or
                                   'postal' in label_lower or 'zip' in label_lower or 
                                   'pincode' in label_lower or 'code' in label_lower)
                    
                    # Determine suggested answer
                    answer = current_value
                    if not is_excluded or current_value == "Select an option":
                        if 'gender' in label_lower or 'sex' in label_lower:
                            answer = gender
                        elif 'disability' in label_lower:
                            answer = disability_status
                        elif 'proficiency' in label_lower:
                            answer = "Professional"
                        elif 'experience' in label_lower:
                            if 'month' in label_lower:
                                answer = str(current_experience_months)
                            elif 'year' in label_lower:
                                answer = str(current_experience_years)
                        elif any(word in label_lower for word in ['location', 'city', 'state', 'country']):
                            if 'country' in label_lower:
                                answer = current_country
                            elif 'state' in label_lower or 'province' in label_lower:
                                answer = current_state
                            else:
                                answer = current_city
                    
                    # Show popup for non-excluded fields (ALWAYS)
                    final_answer = answer
                    if not is_excluded and not popup_disabled:
                        action, confirmed_answer = popup.show(
                            question=label_text,
                            answer=answer,
                            options=all_options,
                            confidence="auto",
                            multi_select=False,
                            can_skip=True
                        )
                        
                        if action == "cancel":
                            print(f"    ❌ User cancelled job application")
                            return False
                        elif action == "disable":
                            popup_disabled = True
                            final_answer = confirmed_answer
                        elif action == "skip":
                            print(f"    ⏭️  User skipped question: {label_text}")
                            continue
                        else:  # submit
                            final_answer = confirmed_answer
                    
                    # Try to select the answer
                    try:
                        select.select_by_visible_text(final_answer)
                        driver.execute_script("""
                            var event = new Event('change', { bubbles: true });
                            arguments[0].dispatchEvent(event);
                        """, select_elem)
                        print(f"    ✅ Selected: {final_answer}")
                    except:
                        # Try partial matching
                        found = False
                        for option in select.options:
                            if final_answer.lower() in option.text.lower() or option.text.lower() in final_answer.lower():
                                select.select_by_visible_text(option.text)
                                driver.execute_script("""
                                    var event = new Event('change', { bubbles: true });
                                    arguments[0].dispatchEvent(event);
                                """, select_elem)
                                print(f"    ✅ Selected: {option.text}")
                                found = True
                                break
                        if not found:
                            print(f"    ⚠️  Could not match '{final_answer}', keeping current")
                    
                    continue
                except NoSuchElementException:
                    pass
                
                # ============ CHECK IF IT'S A TEXT INPUT ============
                try:
                    text_elem = question.find_element(By.XPATH, ".//input[@type='text']")
                    label_text = ""
                    try:
                        label_elem = question.find_element(By.XPATH, ".//label[@for]")
                        label_text = label_elem.text
                    except:
                        label_text = "Unknown"
                    
                    current_value = text_elem.get_attribute('value')
                    label_lower = label_text.lower()
                    
                    # Check if this is an excluded field (NO POPUP)
                    is_excluded = ('email' in label_lower or 'phone' in label_lower or 
                                   'mobile' in label_lower or 'contact' in label_lower or
                                   'postal' in label_lower or 'zip' in label_lower or 
                                   'code' in label_lower or 'pincode' in label_lower or
                                   'resume' in label_lower or 'cv' in label_lower or 'document' in label_lower)
                    
                    # Determine suggested answer
                    answer = current_value if current_value and current_value.strip() else ""
                    
                    if not answer:
                        if 'name' in label_lower:
                            if 'first' in label_lower:
                                answer = first_name
                            elif 'last' in label_lower:
                                answer = last_name
                            else:
                                answer = f"{first_name} {last_name}"
                        elif 'city' in label_lower or 'location' in label_lower:
                            answer = current_city
                        elif 'state' in label_lower or 'province' in label_lower:
                            answer = current_state
                        elif 'country' in label_lower:
                            answer = current_country
                        elif 'experience' in label_lower or 'years' in label_lower:
                            if 'month' in label_lower:
                                answer = str(current_experience_months)
                            else:
                                answer = str(current_experience_years)
                        elif 'salary' in label_lower or 'ctc' in label_lower or 'compensation' in label_lower:
                            if 'current' in label_lower or 'present' in label_lower:
                                answer = str(current_salary)
                            else:
                                answer = str(expected_salary)
                        elif 'notice' in label_lower:
                            if 'month' in label_lower:
                                answer = str(notice_period // 30)
                            elif 'week' in label_lower:
                                answer = str(notice_period // 7)
                            else:
                                answer = str(notice_period)
                    
                    # Show popup for non-excluded fields (ALWAYS)
                    final_answer = answer
                    if not is_excluded and not popup_disabled:
                        action, confirmed_answer = popup.show(
                            question=label_text,
                            answer=answer,
                            options=None,
                            confidence="auto",
                            multi_select=False,
                            can_skip=True
                        )
                        
                        if action == "cancel":
                            print(f"    ❌ User cancelled job application")
                            return False
                        elif action == "disable":
                            popup_disabled = True
                            final_answer = confirmed_answer
                        elif action == "skip":
                            print(f"    ⏭️  User skipped question: {label_text}")
                            continue
                        else:  # submit
                            final_answer = confirmed_answer
                    elif is_excluded:
                        # For excluded fields, fill silently
                        if not current_value or not current_value.strip():
                            if 'email' in label_lower:
                                final_answer = os.getenv("LINKEDIN_EMAIL", "")
                            elif 'phone' in label_lower or 'mobile' in label_lower or 'contact' in label_lower:
                                final_answer = phone_number
                    
                    # Fill the text field
                    if final_answer:
                        text_elem.clear()
                        text_elem.send_keys(final_answer)
                        print(f"    ✅ Filled: {final_answer}")
                    else:
                        print(f"    ⏭️  Left empty: {label_text}")
                    
                    continue
                except NoSuchElementException:
                    pass
                
                # ============ CHECK IF IT'S RADIO BUTTONS ============
                try:
                    radio_elem = question.find_element(By.XPATH, ".//fieldset[@data-test-form-builder-radio-button-form-component='true']")
                    label_text = ""
                    try:
                        label_elem = radio_elem.find_element(By.XPATH, ".//span[@data-test-form-builder-radio-button-form-component__title]")
                        label_text = label_elem.text
                    except:
                        label_text = "Unknown"
                    
                    # Get all radio options and their labels
                    radio_inputs = radio_elem.find_elements(By.XPATH, ".//input[@type='radio']")
                    radio_options = []
                    selected_option = None
                    
                    for radio_input in radio_inputs:
                        opt_id = radio_input.get_attribute('id')
                        opt_label_elem = radio_elem.find_element(By.XPATH, f".//label[@for='{opt_id}']")
                        opt_text = opt_label_elem.text if opt_label_elem else "Unknown"
                        radio_options.append(opt_text)
                        if radio_input.is_selected():
                            selected_option = opt_text
                    
                    # Check if this is an excluded field
                    label_lower = label_text.lower()
                    is_excluded = ('email' in label_lower or 'phone' in label_lower or 
                                   'contact' in label_lower or 'resume' in label_lower or 
                                   'cv' in label_lower or 'document' in label_lower or
                                   'postal' in label_lower or 'zip' in label_lower or 
                                   'code' in label_lower or 'pincode' in label_lower)
                    
                    # Default answer is first option or selected
                    answer = selected_option if selected_option else (radio_options[0] if radio_options else "")
                    
                    # Show popup for non-excluded fields (ALWAYS)
                    if not is_excluded and not popup_disabled:
                        action, confirmed_answer = popup.show(
                            question=label_text,
                            answer=answer,
                            options=radio_options,
                            confidence="auto",
                            multi_select=False,
                            can_skip=True
                        )
                        
                        if action == "cancel":
                            print(f"    ❌ User cancelled job application")
                            return False
                        elif action == "disable":
                            popup_disabled = True
                            answer = confirmed_answer
                        elif action == "skip":
                            print(f"    ⏭️  User skipped question: {label_text}")
                            continue
                        else:  # submit
                            answer = confirmed_answer
                    
                    # Click the selected radio option (click the label to avoid element click intercepted)
                    for radio_input in radio_inputs:
                        opt_id = radio_input.get_attribute('id')
                        opt_label_elem = radio_elem.find_element(By.XPATH, f".//label[@for='{opt_id}']")
                        if opt_label_elem.text == answer:
                            try:
                                opt_label_elem.click()  # Click label instead of input to avoid interception
                            except:
                                driver.execute_script("arguments[0].click();", opt_label_elem)
                            print(f"    ✅ Selected: {answer}")
                            break
                    
                    continue
                except NoSuchElementException:
                    pass
                
                # ============ CHECK IF IT'S CHECKBOXES ============
                try:
                    checkbox_elem = question.find_element(By.XPATH, ".//input[@type='checkbox']")
                    label_text = ""
                    try:
                        label_elem = question.find_element(By.XPATH, ".//label[@for]")
                        label_text = label_elem.text
                    except:
                        label_text = "Unknown"
                    
                    label_lower = label_text.lower()
                    
                    # Check if this is an excluded field
                    is_excluded = ('email' in label_lower or 'phone' in label_lower or 
                                   'contact' in label_lower or 'resume' in label_lower or 
                                   'cv' in label_lower or 'document' in label_lower or
                                   'postal' in label_lower or 'zip' in label_lower or 
                                   'code' in label_lower or 'pincode' in label_lower)
                    
                    is_checked = checkbox_elem.is_selected()
                    
                    # Show popup for non-excluded fields (ALWAYS)
                    if not is_excluded and not popup_disabled:
                        action, confirmed_answer = popup.show(
                            question=label_text,
                            answer=is_checked,
                            options=None,
                            confidence="auto",
                            multi_select=False,
                            can_skip=True
                        )
                        
                        if action == "cancel":
                            print(f"    ❌ User cancelled job application")
                            return False
                        elif action == "disable":
                            popup_disabled = True
                            is_checked = confirmed_answer
                        elif action == "skip":
                            print(f"    ⏭️  User skipped question: {label_text}")
                            continue
                        else:  # submit
                            is_checked = confirmed_answer
                    
                    # Check/uncheck based on decision
                    if is_checked and not checkbox_elem.is_selected():
                        checkbox_elem.click()
                        print(f"    ✅ Checked")
                    elif not is_checked and checkbox_elem.is_selected():
                        checkbox_elem.click()
                        print(f"    ✅ Unchecked")
                    
                    continue
                except NoSuchElementException:
                    pass
                    
            except Exception as e:
                print(f"    ⏭️  Skipping field {question_idx + 1}: {e}")
        
        print("  ✅ Form filling completed")
        popup.destroy()
        
    except TimeoutException:
        print("  ℹ️  No application form found")
    except Exception as e:
        print(f"  ❌ Error in question answering: {e}")
        import traceback
        traceback.print_exc()

def close_any_dialogs(driver):
    """Close any open confirmation or modal dialogs."""
    try:
        # Try to close any confirmation dialogs
        try:
            dismiss_buttons = driver.find_elements(By.XPATH, "//button[@aria-label='Dismiss' or contains(text(), 'Dismiss') or contains(text(), 'Cancel')]")
            if dismiss_buttons:
                dismiss_buttons[0].click()
                time.sleep(1)
        except:
            pass
        
        # Try pressing ESC key
        try:
            actions = ActionChains(driver)
            actions.send_keys(Keys.ESCAPE).perform()
            time.sleep(0.5)
        except:
            pass
            
    except:
        pass

def uncheck_follow_company(driver):
    """Uncheck the follow company checkbox if it's checked."""
    try:
        follow_checkbox = driver.find_element(By.XPATH, ".//input[@id='follow-company-checkbox' and @type='checkbox']")
        if follow_checkbox.is_selected():
            try:
                # Try clicking the checkbox directly
                follow_checkbox.click()
            except:
                # Fallback: click the associated label
                try:
                    follow_label = driver.find_element(By.XPATH, ".//label[@for='follow-company-checkbox']")
                    follow_label.click()
                except:
                    # Last resort: use JavaScript
                    driver.execute_script("arguments[0].click();", follow_checkbox)
            print("    ✅ Unchecked follow company")
    except:
        # Checkbox not found, which is fine - not all jobs have it
        pass

def submit_application(driver, wait):
    """Submit application by progressively clicking through Next/Review/Submit buttons, then handle success modal."""
    job_url = driver.current_url  # Initialize first in case of error
    try:
        # Capture the job URL with currentJobId (the URL changes when job is clicked)
        job_url = driver.current_url
        
        time.sleep(1)
        
        max_iterations = 20
        iteration = 0
        submitted = False
        
        while iteration < max_iterations:
            iteration += 1
            print(f"    📋 Processing form (iteration {iteration})...")
            
            # Answer all questions on current page
            answer_application_questions(driver, wait)
            time.sleep(1)
            
            # Look for Submit button FIRST (final action)
            button_to_click = None
            button_name = ""
            
            try:
                submit_button = driver.find_element(By.XPATH, "//button[contains(., 'Submit')]")
                if submit_button.is_displayed() and submit_button.is_enabled():
                    button_to_click = submit_button
                    button_name = "Submit"
                    submitted = True
                    # Uncheck follow company checkbox before submitting
                    uncheck_follow_company(driver)
            except:
                pass
            
            # If no Submit, look for Review button
            if not button_to_click:
                try:
                    review_button = driver.find_element(By.XPATH, "//button[contains(., 'Review')]")
                    if review_button.is_displayed() and review_button.is_enabled():
                        button_to_click = review_button
                        button_name = "Review"
                except:
                    pass
            
            # If no Review, look for Next button
            if not button_to_click:
                try:
                    next_button = driver.find_element(By.XPATH, "//button[contains(., 'Next')]")
                    if next_button.is_displayed() and next_button.is_enabled():
                        button_to_click = next_button
                        button_name = "Next"
                except:
                    pass
            
            if button_to_click:
                print(f"    ⏳ Found '{button_name}' button (iteration {iteration}), clicking...")
                driver.execute_script("arguments[0].scrollIntoView(true);", button_to_click)
                time.sleep(0.5)
                
                try:
                    button_to_click.click()
                except:
                    driver.execute_script("arguments[0].click();", button_to_click)
                
                time.sleep(2)
                
                # If this was Submit, application has been submitted, now handle success modal
                if "submit" in button_name.lower():
                    print(f"    🎉 Clicked Submit - Waiting for success confirmation...")
                    return _handle_success_modal(driver, wait, job_url)
            else:
                # No button found after answering questions
                # Check if we already submitted - if so, we're done
                if submitted:
                    print(f"    ✅ Application successfully submitted!")
                    return _handle_success_modal(driver, wait, job_url)
                
                # Check if modal is still open
                try:
                    modal = driver.find_element(By.XPATH, "//div[@data-test-modal-id='easy-apply-modal' and @aria-hidden='false']")
                    print(f"    ⚠️  No button found but modal still open (attempt {iteration})")
                    time.sleep(1)
                except:
                    # Modal is closed after all our submissions
                    print(f"    ✅ Modal closed - Application successfully completed!")
                    return {"success": True, "submitted": True, "url": job_url}
        
        print(f"  ❌ Failed to submit application after {max_iterations} iterations")
        return {"success": False, "submitted": False, "url": job_url}
        
    except Exception as e:
        print(f"  ❌ Error in application submission: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "submitted": False, "url": job_url}


def _handle_success_modal(driver, wait, job_url):
    """Handle the 'Your application was sent' success modal and click Done button."""
    try:
        # Wait for success message modal to appear (typically shows "Your application was sent to {company}")
        print("    ⏳ Waiting for success confirmation modal...")
        time.sleep(2)
        
        # Try to find and click the "Done" button in the success modal
        try:
            # Look for Done button - might be in success modal
            done_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Done')]"))
            )
            print(f"    ✅ Found 'Done' button, clicking...")
            driver.execute_script("arguments[0].scrollIntoView(true);", done_button)
            time.sleep(0.5)
            try:
                done_button.click()
            except:
                driver.execute_script("arguments[0].click();", done_button)
            print(f"    ✅ Clicked 'Done' button")
            time.sleep(2)
        except TimeoutException:
            print(f"    ⚠️  'Done' button not found, but application was submitted")
        
        # Close any remaining modal or dialog
        try:
            close_any_dialogs(driver)
        except:
            pass
        
        print(f"    ✅ Application successfully submitted!")
        return {"success": True, "submitted": True, "url": job_url}
        
    except Exception as e:
        print(f"    ⚠️  Error handling success modal: {e}")
        # Application was likely submitted even if we can't handle modal
        return {"success": True, "submitted": True, "url": job_url}

def save_job_to_excel(driver, job_details, application_link='Unknown'):
    """Extract job data and save to Excel."""
    try:
        # Extract job info from the job_details dict
        position = job_details.get('title', 'Unknown')
        company = job_details.get('company', 'Unknown')
        
        # Use location from job_details (already extracted from job listing)
        location = job_details.get('location', 'Unknown')
        
        # Try to extract more details from the page
        experience = 'Unknown'
        salary = 'Unknown'  # LinkedIn doesn't show salary, so always use Unknown
        skills = 'Unknown'
        
        try:
            # Try to find job description section for experience
            description_elem = driver.find_element(By.XPATH, "//div[contains(@class, 'jobs-box__html-content') or contains(@class, 'description__container')]")
            description_text = description_elem.text.lower()
            
            # Extract experience (look for patterns like "2+ years", "5-7 years", etc.)
            import re
            exp_match = re.search(r'(\d+)\+?\s*(?:-\s*\d+)?\s*years?', description_text)
            if exp_match:
                experience = exp_match.group(0)
        except:
            pass
        
        try:
            # Try to extract skills from the job description
            skills_section = driver.find_element(By.XPATH, "//h3[contains(text(), 'Skills') or contains(text(), 'skill')]/following-sibling::*")
            skills = skills_section.text[:100]  # Get first 100 chars
        except:
            pass
        
        # Get the job URL (use the application_link which contains currentJobId)
        url = application_link if application_link != 'Unknown' else driver.current_url
        
        # Format timestamp
        applied_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create job dict for Excel
        job_data = {
            'position': position,
            'company': company,
            'location': location,
            'experience': experience,
            'salary': salary,
            'skills': skills,
            'url': url,
            'applied_at': applied_at
        }
        
        # Save to Excel
        save_to_excel(job_data, platform='linkedin')
        print(f"    📁 Saved job to Excel: {position} @ {company} ({location})")
        
    except Exception as e:
        print(f"    ⚠️  Failed to save job to Excel: {e}")

def get_page_info(driver):
    """Get pagination element and current page number.
    
    Returns:
        tuple: (pagination_element, current_page) or (None, None) if not found
    """
    try:
        # Try to find pagination element with different class names
        pagination_element = None
        class_names = ["jobs-search-pagination__pages", "artdeco-pagination", "artdeco-pagination__pages"]
        
        for class_name in class_names:
            try:
                pagination_element = driver.find_element(By.CLASS_NAME, class_name)
                if pagination_element:
                    break
            except NoSuchElementException:
                continue
        
        if not pagination_element:
            print("  ℹ️  No pagination element found")
            return None, None
        
        # Scroll pagination into view
        driver.execute_script("arguments[0].scrollIntoView(true);", pagination_element)
        time.sleep(0.5)
        
        # Get current page number
        try:
            active_button = pagination_element.find_element(By.XPATH, ".//button[contains(@class, 'active')]")
            current_page = int(active_button.text.strip())
            return pagination_element, current_page
        except (NoSuchElementException, ValueError):
            # If can't find active page, return pagination element with None page number
            return pagination_element, None
            
    except Exception as e:
        print(f"  ⚠️  Failed to get page info: {e}")
        return None, None

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
        login_to_linkedin(driver, wait)
        # For now, use the first search term
        if search_terms:
            search_jobs(driver, wait, search_terms[0])
            apply_filters(driver, wait)
            
            # Process jobs until we reach application_limit of successful applications
            print(f"\n📋 Processing jobs to reach {application_limit} successful applications...")
            
            applied_count = 0
            skipped_count = 0
            
            while applied_count < application_limit:
                try:
                    # Get pagination info for current page
                    pagination_element, current_page = get_page_info(driver)
                    if pagination_element is None:
                        print("\n⏹️  Could not find pagination element")
                        break
                    
                    # Wait and get all job listings on current page
                    wait.until(EC.presence_of_all_elements_located((By.XPATH, "//li[@data-occludable-job-id]")))
                    job_listings = driver.find_elements(By.XPATH, "//li[@data-occludable-job-id]")
                    
                    print(f"\n📄 Found {len(job_listings)} jobs on page {current_page}")
                    
                    # Process each job on the current page
                    jobs_processed_on_page = 0
                    for job_index, job in enumerate(job_listings):
                        # Check if we've reached our limit
                        if applied_count >= application_limit:
                            break
                        
                        try:
                            # Extract job details
                            job_details = extract_job_details(job, job_index)
                            if not job_details:
                                continue
                            
                            print(f"\n{job_index + 1}. Job ID: {job_details['job_id']}")
                            print(f"   Title: {job_details['title']}")
                            print(f"   Company: {job_details['company']}")
                            print(f"   Location: {job_details['location']}")
                            if job_details['style']:
                                print(f"   Style: {job_details['style']}")
                            easy_apply_text = "✅ Yes" if job_details['has_easy_apply'] else "❌ No"
                            print(f"   Easy Apply: {easy_apply_text}")
                            
                            # Check if should skip
                            if should_skip_job(job_details):
                                skipped_count += 1
                                continue
                            
                            # Click on job to view details - refetch the element to avoid stale element reference
                            try:
                                # Refetch the job element by its ID to ensure it's fresh
                                job_li = driver.find_element(By.XPATH, f"//li[@data-occludable-job-id='{job_details['job_id']}']")
                                job_link = job_li.find_element(By.TAG_NAME, 'a')
                                driver.execute_script("arguments[0].scrollIntoView(true);", job_link)
                                job_link.click()
                                time.sleep(2)
                            except Exception as e:
                                print(f"   ⚠️  Could not click job link: {e}")
                                continue
                            
                            # Click Apply button
                            if not click_apply_button(driver, wait):
                                close_any_dialogs(driver)
                                continue
                            
                            # Submit application (handles answering questions internally)
                            submit_result = submit_application(driver, wait)
                            
                            # Save to Excel if submission was successful
                            if submit_result.get("success"):
                                app_url = submit_result.get("url", "Unknown")
                                save_job_to_excel(driver, job_details, app_url)
                                applied_count += 1
                                jobs_processed_on_page += 1
                                print(f"    ✅ Application #{applied_count} of {application_limit} completed")
                                
                                # Check if we've reached the limit
                                if applied_count >= application_limit:
                                    print(f"\n🎉 Reached application limit of {application_limit}")
                                    break
                            else:
                                # On submission failure, skip to next job
                                print(f"\n⚠️  Application submission failed, moving to next job")
                            
                        except Exception as e:
                            print(f"  ❌ Error processing job {job_index + 1}: {e}")
                            continue
                    
                    # Check if we've reached the limit before trying to go to next page
                    if applied_count >= application_limit:
                        break
                    
                    # Try to go to next page
                    print(f"\n⏳ Moving to next page...")
                    try:
                        # Re-fetch pagination element for latest state
                        pagination_element, current_page = get_page_info(driver)
                        if pagination_element is None or current_page is None:
                            print(f"  ⏹️  Cannot determine current page. Stopping pagination.")
                            break
                        next_page_button = pagination_element.find_element(By.XPATH, f".//button[@aria-label='Page {current_page + 1}']")
                        next_page_button.click()
                        print(f"  ✅ Moved to page {current_page + 1}")
                        time.sleep(2)  # Wait for new page to load
                    except NoSuchElementException:
                        print(f"  ⏹️  No page {current_page + 1} found. Reached end of results.")
                        break
                    
                except Exception as e:
                    print(f"  ❌ Error in page processing loop: {e}")
                    break
            
            print(f"\n📊 Summary:")
            print(f"   ✅ Applied: {applied_count}")
            print(f"   ⏭️  Skipped: {skipped_count}")
            print(f"   📋 Total processed: {applied_count + skipped_count}")
        else:
            print("No search terms provided")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        print("\nTo close the browser, press Enter.")
        input()
        driver.quit()


if __name__ == "__main__":
    main()