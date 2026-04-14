"""
ai_engine.py — Groq-powered resume analysis.
Returns a structured dict with career, skills, roadmap, and courses.
Handles ALL career domains: tech, finance, BCom, arts, HR, marketing, etc.
"""

import os
import json
import logging
import re
from groq import Groq

logger = logging.getLogger(__name__)

_api_key = os.environ.get("GROQ_API_KEY", "")
if not _api_key:
    logger.warning("GROQ_API_KEY not set — AI analysis will use fallback mode.")

client = Groq(api_key=_api_key) if _api_key else None

SYSTEM_PROMPT = """
You are an expert career counselor and resume analyst with deep knowledge across ALL industries:
technology, finance, accounting, commerce (BCom/MCom), marketing, HR, healthcare, law, arts,
education, engineering, hospitality, and more.

When given resume text, you MUST respond ONLY with valid JSON — no markdown, no preamble, no explanation.
The JSON must follow this exact schema:

{
  "career": "string — single best-fit career title matching the person's actual background",
  "skills": ["list", "of", "detected", "skills"],
  "roadmap": "string — a numbered 4-6 step preparation roadmap as plain text, use \\n between steps",
  "courses": [
    {"title": "Course Name", "platform": "Coursera/Udemy/YouTube/LinkedIn Learning/etc", "url": "https://...or empty string"}
  ]
}

CRITICAL RULES — read carefully:
- career: Must reflect the ACTUAL resume content. If the resume is about accounting/BCom → suggest
  "Chartered Accountant", "Financial Analyst", "Accounts Executive", etc. NOT a tech role.
  If it's marketing → "Digital Marketing Manager", "Brand Strategist", etc.
  If it's HR → "HR Manager", "Talent Acquisition Specialist", etc.
  If it's tech → appropriate tech role. Never force a tech career on a non-tech resume.
- skills: List only skills ACTUALLY found or clearly implied in the resume. Max 15.
  For BCom: include Tally, GST, Excel, Accounting, Financial Reporting, etc. if present.
  For marketing: include SEO, Social Media, Campaign Management, etc. if present.
- roadmap: Write practical, domain-specific steps. For a BCom student the steps should mention
  CA exams, internships, certifications like CPA/CMA — NOT Python or coding bootcamps.
  For a tech person, mention relevant tech skills, projects, certifications.
  Each step should be on its own line, numbered like: 1. Step one\\n2. Step two
- courses: Recommend 4-6 REAL, relevant courses for the detected career.
  For finance/BCom: recommend courses like "Financial Accounting", "Tally Prime", "GST Certification".
  For marketing: recommend "Google Digital Marketing", "HubSpot Content Marketing", etc.
  For tech: recommend relevant programming/framework courses.
  Include the actual platform (Coursera, Udemy, YouTube, LinkedIn Learning, ICAI, etc.)
- If the resume is too short or unclear, make your best guess based on any available information.
- NEVER return the same generic response for every resume. Every response must be tailored.
"""


def analyze_resume(resume_text: str) -> dict:
    """
    Send resume text to Groq and return a structured analysis dict.
    Falls back to keyword analysis if the API call fails or key is missing.
    """
    if not client:
        logger.warning("No Groq client — using fallback analysis.")
        return _fallback_analysis(resume_text)

    truncated = resume_text[:6000]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Better model for nuanced analysis
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": f"Analyze this resume and return ONLY valid JSON:\n\n{truncated}"}
            ],
            temperature=0.4,
            max_tokens=1800,
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
        "career":  data.get("career",  "Professional"),
        "skills":  data.get("skills",  []),
        "roadmap": data.get("roadmap", ""),
        "courses": data.get("courses", []),
    }


def _fallback_analysis(text: str) -> dict:
    """
    Keyword-based fallback when the Groq API is unavailable.
    Covers tech AND non-tech domains.
    """
    text_lower = text.lower()

    # ── Skill detection ──────────────────────
    all_skills = {
        # Tech
        "Python": "python", "Java": "java", "C++": "c++",
        "JavaScript": "javascript", "SQL": "sql",
        "Machine Learning": "machine learning", "Deep Learning": "deep learning",
        "Data Analysis": "data analysis", "Pandas": "pandas", "NumPy": "numpy",
        "TensorFlow": "tensorflow", "React": "react", "HTML": "html",
        "CSS": "css", "Flask": "flask", "Django": "django",
        "Docker": "docker", "AWS": "aws", "Git": "git",
        # Finance / Commerce
        "Accounting": "accounting", "Finance": "finance",
        "Tally": "tally", "GST": "gst", "Taxation": "taxation",
        "Auditing": "auditing", "Excel": "excel",
        "Financial Reporting": "financial reporting",
        "Bookkeeping": "bookkeeping", "Payroll": "payroll",
        # Marketing
        "Marketing": "marketing", "SEO": "seo", "Social Media": "social media",
        "Content Writing": "content writing", "Digital Marketing": "digital marketing",
        "Sales": "sales", "CRM": "crm", "Email Marketing": "email marketing",
        # HR
        "Recruitment": "recruitment", "HR Management": "hr management",
        "Human Resources": "human resource",
        # Data / BI
        "Power BI": "power bi", "Tableau": "tableau",
        # Management
        "Project Management": "project management",
        "Business Analysis": "business analysis",
        "Leadership": "leadership", "Communication": "communication",
    }
    detected = [label for label, keyword in all_skills.items() if keyword in text_lower]

    # ── Career mapping ────────────────────────
    career_map = [
        (["machine learning", "tensorflow", "deep learning"], "Machine Learning Engineer",
         ["1. Master Python and ML libraries (scikit-learn, TensorFlow)\n2. Study statistics and mathematics\n3. Build 3-5 ML projects\n4. Earn Google ML or AWS ML certification\n5. Contribute to Kaggle competitions"],
         [{"title": "Machine Learning Specialization", "platform": "Coursera", "url": "https://coursera.org"},
          {"title": "Deep Learning A-Z", "platform": "Udemy", "url": "https://udemy.com"}]),

        (["data analysis", "pandas", "power bi", "tableau"], "Data Analyst",
         ["1. Strengthen SQL and Excel skills\n2. Learn Power BI or Tableau\n3. Study Python (pandas, matplotlib)\n4. Build a portfolio with real datasets\n5. Earn Google Data Analytics Certificate"],
         [{"title": "Google Data Analytics Certificate", "platform": "Coursera", "url": "https://coursera.org"},
          {"title": "SQL for Data Science", "platform": "Coursera", "url": "https://coursera.org"}]),

        (["accounting", "tally", "gst", "auditing", "finance", "bookkeeping"], "Accounts Executive",
         ["1. Complete Tally Prime certification\n2. Learn GST filing and taxation rules\n3. Practice with real accounting software (Zoho Books / QuickBooks)\n4. Pursue CA Foundation or CMA Inter if targeting senior roles\n5. Build experience with internships at CA firms\n6. Learn MS Excel advanced features (VLOOKUP, Pivot Tables)"],
         [{"title": "Tally Prime Complete Course", "platform": "Udemy", "url": "https://udemy.com"},
          {"title": "GST Certification Course", "platform": "Udemy", "url": "https://udemy.com"},
          {"title": "Financial Accounting Fundamentals", "platform": "Coursera", "url": "https://coursera.org"},
          {"title": "Excel for Accountants", "platform": "LinkedIn Learning", "url": "https://linkedin.com/learning"}]),

        (["marketing", "seo", "digital marketing", "social media", "content writing"], "Digital Marketing Executive",
         ["1. Learn SEO fundamentals and tools (SEMrush, Ahrefs)\n2. Earn Google Digital Marketing certification\n3. Build hands-on experience with Google Ads and Meta Ads\n4. Create a portfolio of campaigns\n5. Learn email marketing tools (Mailchimp, HubSpot)"],
         [{"title": "Google Digital Marketing & E-commerce", "platform": "Coursera", "url": "https://coursera.org"},
          {"title": "HubSpot Content Marketing Certification", "platform": "HubSpot Academy", "url": "https://academy.hubspot.com"},
          {"title": "The Complete Digital Marketing Course", "platform": "Udemy", "url": "https://udemy.com"}]),

        (["sales", "crm"], "Sales Executive",
         ["1. Learn CRM tools (Salesforce, HubSpot CRM)\n2. Study consultative selling techniques\n3. Practice cold outreach and negotiation\n4. Earn Salesforce Admin certification\n5. Build communication and presentation skills"],
         [{"title": "Salesforce CRM Training", "platform": "Trailhead", "url": "https://trailhead.salesforce.com"},
          {"title": "Sales Training: Practical Sales Techniques", "platform": "Udemy", "url": "https://udemy.com"}]),

        (["hr management", "recruitment", "human resource", "payroll"], "HR Executive",
         ["1. Study HR fundamentals and labor law\n2. Learn payroll software (GreytHR, Zoho People)\n3. Earn SHRM-CP or PHRi certification\n4. Practice with recruitment platforms (LinkedIn, Naukri)\n5. Develop employee engagement and conflict resolution skills"],
         [{"title": "Human Resource Management", "platform": "Coursera", "url": "https://coursera.org"},
          {"title": "HR Analytics", "platform": "LinkedIn Learning", "url": "https://linkedin.com/learning"},
          {"title": "Recruitment Fundamentals", "platform": "Udemy", "url": "https://udemy.com"}]),

        (["react", "html", "css", "javascript"], "Frontend Developer",
         ["1. Master HTML5, CSS3, and JavaScript ES6+\n2. Learn React.js and TypeScript\n3. Build 3-5 portfolio projects\n4. Learn Git and version control\n5. Study responsive design and accessibility"],
         [{"title": "The Complete Web Developer Bootcamp", "platform": "Udemy", "url": "https://udemy.com"},
          {"title": "React - The Complete Guide", "platform": "Udemy", "url": "https://udemy.com"}]),

        (["flask", "django", "python"], "Backend Developer",
         ["1. Master Python and a framework (Django or Flask)\n2. Learn databases: PostgreSQL and MongoDB\n3. Study REST API design\n4. Learn Docker and basic DevOps\n5. Build and deploy 3 real-world projects"],
         [{"title": "Python Django Full Stack", "platform": "Udemy", "url": "https://udemy.com"},
          {"title": "REST APIs with Flask", "platform": "Udemy", "url": "https://udemy.com"}]),

        (["docker", "aws", "kubernetes"], "DevOps Engineer",
         ["1. Learn Linux fundamentals\n2. Master Docker and Kubernetes\n3. Earn AWS Cloud Practitioner certification\n4. Learn CI/CD pipelines (GitHub Actions, Jenkins)\n5. Study infrastructure as code (Terraform)"],
         [{"title": "AWS Certified Cloud Practitioner", "platform": "Udemy", "url": "https://udemy.com"},
          {"title": "Docker and Kubernetes Complete Guide", "platform": "Udemy", "url": "https://udemy.com"}]),
    ]

    career = "Software Developer"
    roadmap = "1. Build core technical skills\n2. Work on 2-3 portfolio projects\n3. Earn a relevant certification\n4. Apply to entry-level or internship roles\n5. Network through LinkedIn and professional communities"
    courses = [
        {"title": "Python Bootcamp", "platform": "Udemy", "url": "https://udemy.com"},
        {"title": "Git & GitHub Crash Course", "platform": "YouTube", "url": "https://youtube.com"},
    ]

    for keywords, title, rm, crs in career_map:
        if any(k in text_lower for k in keywords):
            career  = title
            roadmap = rm[0] if isinstance(rm, list) else rm
            courses = crs
            break

    return {
        "career":  career,
        "skills":  detected[:12],
        "roadmap": roadmap,
        "courses": courses,
        "raw":     "(fallback — Groq API unavailable)",
    }
