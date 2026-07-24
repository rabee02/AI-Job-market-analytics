"""
Generates a job-postings dataset structured the way a real job-board scrape
comes out: messy titles, free-text salary strings, skills buried inside
description text, inconsistent location formats.

~40,000 postings across 8 European cities, Jan 2024 - Jun 2026, with
realistic trends baked in: AI/ML roles growing fast, GenAI skills exploding
from a low base, steady demand for SQL/Excel, remote share drifting down.
"""

import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(11)

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

N = 40_000
START = pd.Timestamp("2024-01-01")
END = pd.Timestamp("2026-06-30")
TOTAL_DAYS = (END - START).days

# role family -> (base share, growth multiplier over the period, title variants)
ROLES = {
    "Data Analyst": (0.26, 1.1, [
        "Data Analyst", "Senior Data Analyst", "Junior Data Analyst",
        "Data Analyst (SQL/Power BI)", "Business Data Analyst", "Data & Insights Analyst"]),
    "BI Analyst": (0.13, 1.0, [
        "BI Analyst", "Business Intelligence Analyst", "Power BI Developer",
        "Senior BI Analyst", "BI & Reporting Analyst"]),
    "Data Engineer": (0.17, 1.35, [
        "Data Engineer", "Senior Data Engineer", "Azure Data Engineer",
        "ETL Developer", "Analytics Engineer", "Junior Data Engineer"]),
    "Data Scientist": (0.14, 1.15, [
        "Data Scientist", "Senior Data Scientist", "Junior Data Scientist",
        "Data Scientist - NLP", "Applied Scientist"]),
    "ML Engineer": (0.09, 1.9, [
        "Machine Learning Engineer", "ML Engineer", "Senior ML Engineer",
        "MLOps Engineer", "ML Platform Engineer"]),
    "AI Engineer": (0.06, 3.2, [
        "AI Engineer", "GenAI Engineer", "LLM Engineer",
        "AI Solutions Engineer", "Prompt Engineer", "AI Application Developer"]),
    "Analytics Manager": (0.07, 1.1, [
        "Analytics Manager", "Head of Data", "Data Team Lead",
        "BI Manager", "Insights Manager"]),
    "Business Analyst": (0.08, 0.95, [
        "Business Analyst", "Senior Business Analyst", "Business Analyst (Data)",
        "Operations Analyst", "Reporting Analyst"]),
}

CITIES = {
    "Dublin, Ireland":        (0.17, 1.00),
    "London, UK":             (0.24, 1.18),
    "Amsterdam, Netherlands": (0.11, 1.05),
    "Berlin, Germany":        (0.12, 0.92),
    "Paris, France":          (0.10, 0.95),
    "Madrid, Spain":          (0.08, 0.72),
    "Warsaw, Poland":         (0.10, 0.60),
    "Lisbon, Portugal":       (0.08, 0.62),
}

COMPANIES = [
    "TechFlow Solutions", "Datacore Analytics", "Meridian Financial", "CloudNine Systems",
    "Quantify Labs", "Nexus Retail Group", "Alpine Insurance", "BrightPath Health",
    "Vector Consulting", "Ironbridge Bank", "Streamline Logistics", "Corebyte",
    "Helix Pharma", "Northgate Energy", "Pixelworks Media", "Summit Recruitment",
    "Orbital Software", "Fairview Insights", "Cobalt Digital", "Trinity Data Partners",
]

# skill -> (base probability in a data role posting, trend multiplier over period)
SKILLS = {
    "SQL":            (0.68, 1.00),
    "Python":         (0.55, 1.15),
    "Excel":          (0.42, 0.85),
    "Power BI":       (0.38, 1.20),
    "Tableau":        (0.22, 0.85),
    "R":              (0.10, 0.70),
    "Azure":          (0.24, 1.25),
    "AWS":            (0.20, 1.10),
    "Snowflake":      (0.12, 1.45),
    "Databricks":     (0.10, 1.70),
    "Spark":          (0.13, 1.15),
    "dbt":            (0.08, 1.80),
    "Airflow":        (0.09, 1.35),
    "Machine Learning": (0.22, 1.30),
    "LLMs":           (0.03, 6.0),
    "GenAI":          (0.02, 7.5),
    "RAG":            (0.01, 8.0),
    "Prompt Engineering": (0.01, 5.5),
    "MLOps":          (0.05, 2.2),
    "Statistics":     (0.18, 0.95),
    "A/B Testing":    (0.08, 1.10),
    "Data Modelling": (0.15, 1.10),
    "ETL":            (0.20, 1.05),
    "Git":            (0.16, 1.15),
}

# role family salary midpoints (EUR, 2024) and growth
SALARY = {
    "Data Analyst": (48_000, 0.035), "BI Analyst": (52_000, 0.033),
    "Data Engineer": (65_000, 0.045), "Data Scientist": (62_000, 0.040),
    "ML Engineer": (75_000, 0.055), "AI Engineer": (78_000, 0.065),
    "Analytics Manager": (85_000, 0.035), "Business Analyst": (50_000, 0.030),
}
CITY_SALARY_FACTOR = {c: f for c, (_, f) in CITIES.items()}

DESC_TEMPLATES = [
    "We are looking for a {title} to join our growing team. You will work with {skills} to deliver insights across the business. Experience with stakeholder management is a plus.",
    "{company} is hiring a {title}. The role involves building reports and pipelines using {skills}. Hybrid working available.",
    "Exciting opportunity for a {title}. Day to day you'll use {skills}. You will partner with product and finance teams.",
    "As a {title} you will own dashboards and data models. Our stack: {skills}. Strong communication skills required.",
    "Join {company} as a {title}. Required: {skills}. Nice to have: cloud certification.",
]


def pick_role(day_frac):
    names, weights = [], []
    for name, (share, growth, _) in ROLES.items():
        names.append(name)
        weights.append(share * (1 + (growth - 1) * day_frac))
    weights = np.array(weights); weights /= weights.sum()
    return np.random.choice(names, p=weights)


def pick_skills(role, day_frac):
    picked = []
    for skill, (p, trend) in SKILLS.items():
        prob = p * (1 + (trend - 1) * day_frac)
        # role-specific boosts
        if role in ("AI Engineer", "ML Engineer") and skill in (
                "LLMs", "GenAI", "RAG", "Prompt Engineering", "MLOps", "Machine Learning"):
            prob = min(0.9, prob * 6)
        if role == "Data Engineer" and skill in ("Airflow", "dbt", "Spark", "Snowflake", "Databricks", "ETL", "Azure", "AWS"):
            prob = min(0.85, prob * 2.5)
        if role in ("Data Analyst", "BI Analyst", "Business Analyst") and skill in ("Power BI", "Excel", "Tableau", "SQL"):
            prob = min(0.9, prob * 1.5)
        if np.random.rand() < min(prob, 0.95):
            picked.append(skill)
    if not picked:
        picked = ["SQL"]
    return picked


def salary_text(role, city, day_frac, seniority):
    base, growth = SALARY[role]
    years = day_frac * 2.5
    mid = base * (1 + growth) ** years * CITY_SALARY_FACTOR[city]
    mid *= {"Junior": 0.75, "Mid": 1.0, "Senior": 1.3}[seniority]
    mid *= np.random.uniform(0.9, 1.1)
    lo = round(mid * 0.9, -3)
    hi = round(mid * 1.1, -3)

    r = np.random.rand()
    if r < 0.30:
        return ""  # ~30% of postings don't disclose salary
    if r < 0.34:
        return "Negotiable"
    if r < 0.38:
        return "Competitive salary + benefits"
    if r < 0.44:
        return f"Up to \u20ac{hi:,.0f}"
    if r < 0.50:
        return f"\u20ac{mid:,.0f} per annum"
    if city == "London, UK":
        return f"\u00a3{lo * 0.85:,.0f} - \u00a3{hi * 0.85:,.0f}"
    return f"\u20ac{lo:,.0f} - \u20ac{hi:,.0f} per annum"


rows = []
# posting volume grows over the period
day_weights = np.linspace(0.75, 1.35, TOTAL_DAYS)
day_weights /= day_weights.sum()
days = np.random.choice(TOTAL_DAYS, N, p=day_weights)

city_names = list(CITIES.keys())
city_p = np.array([v[0] for v in CITIES.values()]); city_p /= city_p.sum()

for i in range(N):
    d = START + pd.Timedelta(days=int(days[i]))
    day_frac = days[i] / TOTAL_DAYS
    role = pick_role(day_frac)
    title = np.random.choice(ROLES[role][2])
    seniority = ("Senior" if "Senior" in title or "Head" in title or "Manager" in title or "Lead" in title
                 else "Junior" if "Junior" in title
                 else np.random.choice(["Mid", "Senior", "Junior"], p=[0.6, 0.25, 0.15]))
    city = np.random.choice(city_names, p=city_p)
    company = np.random.choice(COMPANIES)
    skills = pick_skills(role, day_frac)

    # remote share declines over the period: ~28% -> ~15%
    remote_p = 0.28 - 0.13 * day_frac
    work_mode = np.random.choice(
        ["Remote", "Hybrid", "On-site"],
        p=[remote_p, 0.55, 1 - 0.55 - remote_p])

    desc = np.random.choice(DESC_TEMPLATES).format(
        title=title, company=company, skills=", ".join(skills))

    rows.append({
        "posting_id": f"JP{100000 + i}",
        "posted_date": d.strftime("%Y-%m-%d"),
        "job_title": title.upper() if np.random.rand() < 0.08 else title,
        "company": company,
        "location": city if np.random.rand() > 0.06 else city.split(",")[0],
        "salary_raw": salary_text(role, city, day_frac, seniority),
        "work_mode": work_mode,
        "description": desc,
    })

df = pd.DataFrame(rows)
# scraper artefacts: ~400 duplicate postings (reposted ads)
df = pd.concat([df, df.sample(400, random_state=5)]).sample(frac=1, random_state=6)
df.to_csv(RAW_DIR / "job_postings_raw.csv", index=False)
print(f"Wrote {len(df):,} postings to {RAW_DIR / 'job_postings_raw.csv'}")
