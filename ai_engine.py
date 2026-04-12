"""
ai_engine.py — Groq-powered resume analysis.
Returns a structured dict with career, skills, roadmap, and courses.
"""

import os
import json
import logging
import re
from groq import Groq

logger = logging.getLogger(__name__)

# API key is read from environment — never hardcode it here
_api_key = os.environ.get("GROQ_API_KEY", "")
if not _api_key:
    logger.warning("GROQ_API_KEY not set — AI analysis will use fallback mode.")

client = Groq(api_key=_api_key) if _api_key else None

SYSTEM_PROMPT = """
You are an expert career counselor and resume analyst.
When given resume text, you MUST respond ONLY with valid JSON — no markdown, no preamble, no explanation.
The JSON must follow this exact schema:

{
  "career": "string — single best-fit career title",
  "skills": ["list", "of", "detected", "skills"],
  "roadmap": "string — a 3-5 step preparation roadmap as plain text, use \\n between steps",
  "courses": [
    {"title": "Course Name", "platform": "Coursera/Udemy/YouTube/etc", "url": "https://...or empty string"}
  ]
}

Rules:
- skills: List only skills actually found in the resume. Max 15.
- roadmap: Practical, specific steps to reach the recommended career. Numbered.
- courses: 4-6 specific, real courses relevant to the career. Include platform.
- If the resume text is too short or unclear, still return the schema with best guesses.
"""


def analyze_resume(resume_text: str) -> dict:
    """
    Send resume text to Groq and return a structured analysis dict.
    Falls back to keyword analysis if the API call fails or key is missing.
    """
    if not client:
        logger.warning("No Groq client — using fallback analysis.")
        return _fallback_analysis(resume_text)

    truncated = resume_text[:6000]  # Stay within context limits

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": f"Analyze this resume:\n\n{truncated}"}
            ],
            temperature=0.3,
            max_tokens=1500,
        )

        raw_output = response.choices[0].message.content.strip()
        logger.info("Groq raw response (first 300 chars): %s", raw_output[:300])

        parsed = _parse_json_response(raw_output)
        parsed["raw"] = raw_output
        return parsed

    except Exception as e:
        logger.error("Groq API error: %s", e, exc_info=True)
        return _fallback_analysis(resume_text)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _parse_json_response(text: str) -> dict:
    """
    Robustly parse JSON from the model response.
    Handles cases where the model wraps it in ```json ... ``` fences.
    """
    cleaned = re.sub(r"```(?:json)?", "", text).strip().strip("`").strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError("No valid JSON found in AI response")

    # Normalise courses — accept both list-of-strings and list-of-dicts
    courses = data.get("courses", [])
    if courses and isinstance(courses[0], str):
        courses = [{"title": c, "platform": "", "url": ""} for c in courses]
    data["courses"] = courses

    return {
        "career":  data.get("career",  "Software Developer"),
        "skills":  data.get("skills",  []),
        "roadmap": data.get("roadmap", ""),
        "courses": data.get("courses", []),
    }


def _fallback_analysis(text: str) -> dict:
    """Simple keyword-based fallback when the API is unavailable."""
    text_lower = text.lower()

    skill_keywords = [
        "python", "java", "c++", "javascript", "sql", "machine learning",
        "deep learning", "data analysis", "pandas", "numpy", "tensorflow",
        "html", "css", "react", "flask", "django", "power bi", "excel",
        "tableau", "accounting", "finance", "tally", "marketing", "sales",
        "hr", "management", "docker", "kubernetes", "aws", "git",
    ]
    detected = [s.title() for s in skill_keywords if s in text_lower]

    career_map = [
        (["machine learning", "tensorflow", "deep learning"], "Machine Learning Engineer"),
        (["data analysis", "pandas", "numpy"],                "Data Analyst"),
        (["react", "html", "css", "javascript"],              "Frontend Developer"),
        (["flask", "django", "python"],                       "Backend Developer"),
        (["docker", "kubernetes", "aws"],                     "DevOps Engineer"),
        (["sql", "excel", "power bi", "tableau"],             "Data Analyst"),
        (["accounting", "tally", "finance"],                  "Financial Analyst"),
        (["marketing", "sales", "seo"],                       "Marketing Executive"),
        (["hr", "human resource", "recruitment"],             "HR Manager"),
    ]

    career = "Software Developer"
    for keywords, title in career_map:
        if any(k in text_lower for k in keywords):
            career = title
            break

    return {
        "career":  career,
        "skills":  detected[:12],
        "roadmap": (
            "1. Strengthen core skills\n"
            "2. Build 2-3 portfolio projects\n"
            "3. Earn a relevant certification\n"
            "4. Apply to entry-level roles"
        ),
        "courses": [
            {"title": "The Complete Python Bootcamp", "platform": "Udemy",    "url": ""},
            {"title": "SQL for Data Science",          "platform": "Coursera", "url": ""},
            {"title": "Git & GitHub Crash Course",     "platform": "YouTube",  "url": ""},
        ],
        "raw": "(fallback — API unavailable)",
    }
