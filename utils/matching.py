"""
Question matching engine for Naukri chatbot auto-fill.
Maps chatbot questions to answers from config/personals.py and utils/extra_questions.json.
"""

import os
import sys
import json
import re

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.personals import (
    first_name, middle_name, last_name,
    current_city, current_state, current_country, current_pincode,
    current_salary, expected_salary,
    current_company, current_designation,
    current_experience_years, current_experience_months,
    linkedin_profile, github_profile,
    notice_period, notice_period_serving, last_day_of_notice_period,
    gender, date_of_birth, disability_status, veteran_status,
    skills, cover_letter,
    relocation_location, relocation_preference,
)
from datetime import datetime, timedelta

EXTRA_QUESTIONS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra_questions.json")


def _notice_period_label():
    """Convert notice_period days to the closest Naukri chatbot option."""
    if notice_period <= 15:
        return "15 Days or less"
    elif notice_period <= 30:
        return "1 Month"
    elif notice_period <= 60:
        return "2 Months"
    elif notice_period <= 90:
        return "3 Months"
    else:
        return "More than 3 Months"


def _full_name():
    parts = [first_name, middle_name, last_name]
    return " ".join(p for p in parts if p).strip()


def _relocation_answer(question_text):
    """Determine relocation answer based on config.
    If relocation_location is empty -> answer with relocation_preference for all.
    If relocation_location is populated -> 'Yes' only for listed cities, else based on preference.
    If preference is 'Maybe' and question has options -> 'No'.
    """
    q_lower = question_text.lower()

    if not relocation_location:
        # Empty list = answer for all locations
        if relocation_preference == "Maybe":
            return "No"  # For options, select No
        return relocation_preference

    # Check if any listed location appears in the question
    for loc in relocation_location:
        if loc.lower() in q_lower:
            return "Yes"

    # Location not in our list
    if relocation_preference == "Maybe":
        return "No"
    return relocation_preference


def _skill_experience_answer(question_text):
    """Match skill-specific experience from the skills dict.
    E.g. 'How many years of experience in Python?' → looks up skills['Python'].
    Falls back to skills['Other'] if skill not found.
    Returns None if no skill keyword found in the question at all.
    """
    q_lower = question_text.lower()
    # Check each skill (longest name first to avoid partial matches)
    sorted_skills = sorted(skills.keys(), key=len, reverse=True)
    for skill_name in sorted_skills:
        if skill_name == "Other":
            continue
        if skill_name.lower() in q_lower:
            years = skills[skill_name]
            return str(int(years)) if years == int(years) else str(years)
    # No specific skill matched — use "Other" fallback
    if "Other" in skills:
        other_val = skills["Other"]
        return str(int(other_val)) if other_val == int(other_val) else str(other_val)
    return None


def _last_day_of_np():
    """Return last day of notice period.
    If serving notice, return last_day_of_notice_period from config.
    If not serving, calculate from today + notice_period days.
    """
    if notice_period_serving.lower() == "yes" and last_day_of_notice_period:
        return last_day_of_notice_period
    # Not serving — calculate from today
    future_date = datetime.now() + timedelta(days=notice_period)
    return future_date.strftime("%d/%m/%Y")


# ──────────────────────────────────────────────
# QUESTION_MAP: list of (keywords, answer_value)
#   keywords = list of lowercase substrings that should ALL appear in the question
#   answer_value = str or callable returning str
# Ordered from most specific to least specific.
# ──────────────────────────────────────────────
QUESTION_MAP = [
    # Salary
    (["current", "ctc"],            lambda: str(current_salary)),
    (["current", "salary"],         lambda: str(current_salary)),
    (["expected", "ctc"],           lambda: str(expected_salary)),
    (["expected", "salary"],        lambda: str(expected_salary)),
    (["ctc"],                       lambda: str(current_salary)),   # fallback if just "CTC"

    # Notice period
    (["serving", "notice"],         lambda: notice_period_serving),
    (["serving", "np"],             lambda: notice_period_serving),
    (["currently", "serving"],      lambda: notice_period_serving),
    (["last", "day", "notice"],     _last_day_of_np),
    (["last", "date", "notice"],    _last_day_of_np),
    (["end", "date", "notice"],     _last_day_of_np),
    (["notice", "period"],          _notice_period_label),

    # Skill-specific experience (MUST come before generic experience)
    # This is handled dynamically via _skill_experience_answer, added as None sentinel
    (["experience", "in"],          None),  # sentinel: handled specially
    (["years", "of", "experience", "in"], None),  # sentinel
    (["proficien"],                 None),  # sentinel

    # Generic experience (overall)
    (["total", "experience"],       lambda: str(current_experience_years)),
    (["relevant", "experience"],    lambda: str(current_experience_years)),
    (["years", "experience"],       lambda: str(current_experience_years)),
    (["overall", "experience"],     lambda: str(current_experience_years)),
    (["experience"],                lambda: str(current_experience_years)),

    # Location
    (["current", "location"],       lambda: current_city),
    (["current", "city"],           lambda: current_city),
    (["city"],                      lambda: current_city),
    (["location"],                  lambda: current_city),
    (["state"],                     lambda: current_state),
    (["country"],                   lambda: current_country),
    (["pincode"],                   lambda: current_pincode),
    (["zip"],                       lambda: current_pincode),

    # Company
    (["current", "company"],        lambda: current_company),
    (["current", "organization"],   lambda: current_company),
    (["current", "employer"],       lambda: current_company),
    (["designation"],               lambda: current_designation),
    (["current", "role"],           lambda: current_designation),
    (["job", "title"],              lambda: current_designation),

    # Personal
    (["full", "name"],              _full_name),
    (["first", "name"],             lambda: first_name),
    (["last", "name"],              lambda: last_name),
    (["gender"],                    lambda: gender),
    (["date", "birth"],             lambda: date_of_birth),
    (["dob"],                       lambda: date_of_birth),
    (["birth", "date"],             lambda: date_of_birth),
    (["disability"],                lambda: disability_status),
    (["handicap"],                  lambda: disability_status),
    (["veteran"],                   lambda: veteran_status),

    # Links
    (["linkedin"],                  lambda: linkedin_profile),
    (["github"],                    lambda: github_profile),
    (["portfolio"],                 lambda: github_profile),

    # Relocation
    (["relocate"],                  None),  # handled specially below
    (["residing"],                  None),  # handled specially below
    (["willing", "move"],           None),  # handled specially below

    # Cover letter
    (["cover", "letter"],           lambda: cover_letter.strip()),
]


# ──────────────────────────────────────────────
# Learned answers from extra_questions.json
# ──────────────────────────────────────────────
def load_learned_answers():
    """Load previously answered questions from extra_questions.json."""
    if not os.path.exists(EXTRA_QUESTIONS_PATH):
        return []
    try:
        with open(EXTRA_QUESTIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def save_question(question, answer, answer_type="text"):
    """Save a new Q&A pair to extra_questions.json."""
    learned = load_learned_answers()

    # Don't save duplicates (case-insensitive question match)
    q_lower = question.strip().lower()
    for item in learned:
        if item.get("question", "").strip().lower() == q_lower:
            # Update the answer for existing question
            item["answer"] = answer
            item["type"] = answer_type
            with open(EXTRA_QUESTIONS_PATH, "w", encoding="utf-8") as f:
                json.dump(learned, f, indent=2, ensure_ascii=False)
            return

    learned.append({
        "question": question.strip(),
        "answer": answer,
        "type": answer_type
    })
    with open(EXTRA_QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(learned, f, indent=2, ensure_ascii=False)


def _match_learned(question_lower):
    """Try to find answer from extra_questions.json using fuzzy keyword matching."""
    learned = load_learned_answers()
    for item in learned:
        saved_q = item.get("question", "").strip().lower()
        if not saved_q:
            continue
        # Check if the saved question is semantically similar:
        # - exact match
        # - one contains the other
        # - significant word overlap
        if saved_q == question_lower or saved_q in question_lower or question_lower in saved_q:
            return item.get("answer", "")

        # Word overlap check: if >60% of words match
        saved_words = set(re.findall(r'\w+', saved_q))
        question_words = set(re.findall(r'\w+', question_lower))
        if saved_words and question_words:
            overlap = saved_words & question_words
            if len(overlap) / max(len(saved_words), len(question_words)) > 0.6:
                return item.get("answer", "")

    return None


def _pick_best_option(answer, options):
    """Given an answer string and a list of option strings, pick the best matching option."""
    answer_lower = answer.strip().lower()

    # Exact match first
    for opt in options:
        if opt.strip().lower() == answer_lower:
            return opt

    # Substring match
    for opt in options:
        opt_lower = opt.strip().lower()
        if answer_lower in opt_lower or opt_lower in answer_lower:
            return opt

    # Word overlap
    answer_words = set(re.findall(r'\w+', answer_lower))
    best_opt = None
    best_score = 0
    for opt in options:
        opt_words = set(re.findall(r'\w+', opt.strip().lower()))
        if opt_words and answer_words:
            overlap = len(answer_words & opt_words) / max(len(answer_words), len(opt_words))
            if overlap > best_score:
                best_score = overlap
                best_opt = opt
    if best_score > 0.3:
        return best_opt

    return None


# ──────────────────────────────────────────────
# Main matching function
# ──────────────────────────────────────────────
def find_answer(question_text, options=None):
    """
    Find the best answer for a chatbot question.

    Args:
        question_text: The question string from the chatbot
        options: Optional list of radio button option strings

    Returns:
        (answer, confidence) where confidence is "auto", "learned", or "unknown"
        answer is a string. For options, it's the matching option text.
    """
    q_lower = question_text.strip().lower()

    # 1. Try QUESTION_MAP (config-based answers)
    for keywords, answer_fn in QUESTION_MAP:
        if all(kw in q_lower for kw in keywords):
            # Special handling for relocation questions (answer_fn is None)
            if answer_fn is None:
                # Check if this is a relocation sentinel
                if any(kw in keywords for kw in ["relocate", "residing", "willing"]):
                    raw_answer = _relocation_answer(question_text)
                else:
                    # Skill-specific experience sentinel
                    raw_answer = _skill_experience_answer(question_text)
                    if raw_answer is None:
                        # No skill matched, fall through to next QUESTION_MAP entry
                        continue
            else:
                raw_answer = answer_fn() if callable(answer_fn) else answer_fn

            # If there are options, try to match the answer to an option
            if options:
                matched_opt = _pick_best_option(raw_answer, options)
                if matched_opt:
                    return matched_opt, "auto"
                # If raw answer didn't match any option, return it anyway (user can fix via popup)
                return raw_answer, "auto"

            return str(raw_answer), "auto"

    # 2. Try learned answers from extra_questions.json
    learned_answer = _match_learned(q_lower)
    if learned_answer is not None:
        if options:
            matched = _pick_best_option(learned_answer, options)
            if matched:
                return matched, "learned"
        return str(learned_answer), "learned"

    # 4. Unknown question
    return "", "unknown"
