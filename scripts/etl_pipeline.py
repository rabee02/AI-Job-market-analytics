"""
ETL for the scraped job postings: the transform step is mostly text work.

- standardise messy job titles into role families and seniority levels
- parse free-text salary strings ("€45,000 - €55,000 per annum",
  "Up to €70,000", "£48,000 - £58,000", "Negotiable") into numeric
  min/max/mid in EUR
- extract skills from description text into a long-format skills table
- de-duplicate reposted ads
- load a postings table + skills table into SQLite

Run:  python scripts/etl_pipeline.py
"""

import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw" / "job_postings_raw.csv"
PROCESSED = BASE / "data" / "processed"
DB_PATH = BASE / "job_market.db"

GBP_TO_EUR = 1.17

ROLE_PATTERNS = [
    (r"\b(genai|llm|prompt|ai)\b",              "AI Engineer"),
    (r"\b(machine learning|ml|mlops)\b",        "ML Engineer"),
    (r"\bdata scien|applied scientist\b",       "Data Scientist"),
    (r"\b(data engineer|etl developer|analytics engineer)\b", "Data Engineer"),
    (r"\b(bi|business intelligence|power bi developer|reporting)\b", "BI Analyst"),
    (r"\b(manager|head of|team lead)\b",        "Analytics Manager"),
    (r"\bbusiness analyst|operations analyst\b", "Business Analyst"),
    (r"\bdata\b.*\banalyst|analyst\b.*\bdata\b|insights analyst", "Data Analyst"),
]

SKILLS = [
    "SQL", "Python", "Excel", "Power BI", "Tableau", "R", "Azure", "AWS",
    "Snowflake", "Databricks", "Spark", "dbt", "Airflow", "Machine Learning",
    "LLMs", "GenAI", "RAG", "Prompt Engineering", "MLOps", "Statistics",
    "A/B Testing", "Data Modelling", "ETL", "Git",
]
# word-boundary regex per skill; R needs care so "R" doesn't match every word
SKILL_RES = {
    s: re.compile(rf"(?<![\w]){re.escape(s)}(?![\w])", re.IGNORECASE)
    for s in SKILLS
}


def classify_role(title: str) -> str:
    t = title.lower()
    for pattern, family in ROLE_PATTERNS:
        if re.search(pattern, t):
            return family
    return "Data Analyst"


def classify_seniority(title: str) -> str:
    t = title.lower()
    if re.search(r"\b(senior|sr|lead|head|manager|principal)\b", t):
        return "Senior"
    if re.search(r"\b(junior|jr|graduate|entry)\b", t):
        return "Junior"
    return "Mid"


def parse_salary(raw) -> tuple:
    """Return (min_eur, max_eur, mid_eur, disclosed) from a salary string."""
    if not isinstance(raw, str) or not raw.strip():
        return (np.nan, np.nan, np.nan, False)
    text = raw.strip()
    if re.search(r"negotiable|competitive", text, re.IGNORECASE):
        return (np.nan, np.nan, np.nan, False)

    currency = GBP_TO_EUR if "\u00a3" in text else 1.0
    nums = [float(n.replace(",", "")) for n in re.findall(r"[\d,]+(?:\.\d+)?", text)]
    nums = [n for n in nums if n > 1000]          # ignore stray small numbers
    if not nums:
        return (np.nan, np.nan, np.nan, False)

    if re.search(r"up to", text, re.IGNORECASE):
        hi = nums[0] * currency
        return (round(hi * 0.85), round(hi), round(hi * 0.925), True)
    if len(nums) >= 2:
        lo, hi = nums[0] * currency, nums[1] * currency
        return (round(lo), round(hi), round((lo + hi) / 2), True)
    mid = nums[0] * currency
    return (round(mid * 0.95), round(mid * 1.05), round(mid), True)


def clean_location(loc: str) -> str:
    city = str(loc).split(",")[0].strip().title()
    country = {
        "Dublin": "Ireland", "London": "UK", "Amsterdam": "Netherlands",
        "Berlin": "Germany", "Paris": "France", "Madrid": "Spain",
        "Warsaw": "Poland", "Lisbon": "Portugal",
    }.get(city, "Unknown")
    return f"{city}|{country}"


def run():
    df = pd.read_csv(RAW)
    n_raw = len(df)

    # dedupe reposted ads: same title+company+location+description
    df = df.drop_duplicates(subset=["job_title", "company", "location", "description", "posted_date"])
    print(f"[transform] removed {n_raw - len(df)} reposted duplicates")

    df["posted_date"] = pd.to_datetime(df["posted_date"])
    df["post_month"] = df["posted_date"].dt.to_period("M").astype(str)
    df["post_quarter"] = df["posted_date"].dt.to_period("Q").astype(str)

    df["role_family"] = df["job_title"].apply(classify_role)
    df["seniority"] = df["job_title"].apply(classify_seniority)
    df["is_ai_role"] = df["role_family"].isin(["AI Engineer", "ML Engineer", "Data Scientist"])

    loc = df["location"].apply(clean_location).str.split("|", expand=True)
    df["city"], df["country"] = loc[0], loc[1]

    sal = df["salary_raw"].apply(parse_salary)
    df[["salary_min_eur", "salary_max_eur", "salary_mid_eur", "salary_disclosed"]] = \
        pd.DataFrame(sal.tolist(), index=df.index)
    disclosed_pct = df["salary_disclosed"].mean() * 100
    print(f"[transform] salary parsed; {disclosed_pct:.0f}% of postings disclose a figure")

    # skills long table
    skill_rows = []
    for pid, desc in zip(df["posting_id"], df["description"].fillna("")):
        for skill, regex in SKILL_RES.items():
            if regex.search(desc):
                skill_rows.append({"posting_id": pid, "skill": skill})
    skills_df = pd.DataFrame(skill_rows)
    print(f"[transform] extracted {len(skills_df):,} skill mentions "
          f"({len(skills_df) / len(df):.1f} per posting)")

    PROCESSED.mkdir(parents=True, exist_ok=True)
    postings_out = df.drop(columns=["description"])   # keep the db lean
    postings_out.to_csv(PROCESSED / "postings_clean.csv", index=False)
    skills_df.to_csv(PROCESSED / "posting_skills.csv", index=False)

    with sqlite3.connect(DB_PATH) as conn:
        postings_out.to_sql("postings", conn, if_exists="replace", index=False)
        skills_df.to_sql("posting_skills", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS ix_post_month ON postings(post_month)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_post_id ON postings(posting_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_skill ON posting_skills(skill)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_skill_pid ON posting_skills(posting_id)")
    print(f"[load] {len(df):,} postings and skills table written to {DB_PATH.name}")


if __name__ == "__main__":
    run()
