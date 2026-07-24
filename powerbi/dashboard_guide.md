# Power BI dashboard build guide

Load `data/processed/postings_clean.csv` and `data/processed/posting_skills.csv`
(Get Data → Text/CSV). Two tables, one relationship:

- postings[posting_id] → posting_skills[posting_id]  (1:many, single direction)

Add a date table:

```
DimDate = CALENDAR(MIN(postings[posted_date]), MAX(postings[posted_date]))
```

with Year, Quarter = "Q" & QUARTER([Date]), Month = FORMAT([Date], "MMM"),
MonthNum for sorting. Relate DimDate[Date] → postings[posted_date].

## DAX measures

```
Postings = COUNTROWS(postings)

Disclosed Postings = CALCULATE([Postings], postings[salary_disclosed] = TRUE)

Salary Disclosure % = DIVIDE([Disclosed Postings], [Postings])

Median Salary = CALCULATE(
    MEDIAN(postings[salary_mid_eur]),
    postings[salary_disclosed] = TRUE)

AI Median Salary = CALCULATE([Median Salary],
    postings[role_family] IN {"AI Engineer", "ML Engineer"})

Non-AI Median Salary = CALCULATE([Median Salary],
    NOT postings[role_family] IN {"AI Engineer", "ML Engineer"})

AI Salary Premium % = DIVIDE([AI Median Salary] - [Non-AI Median Salary], [Non-AI Median Salary])

Remote Share % = DIVIDE(
    CALCULATE([Postings], postings[work_mode] = "Remote"), [Postings])

Skill Mentions = COUNTROWS(posting_skills)

Postings Mentioning Skill = DISTINCTCOUNT(posting_skills[posting_id])

Skill Penetration % = DIVIDE([Postings Mentioning Skill], CALCULATE([Postings], ALL(posting_skills)))

Postings YoY % =
VAR prev = CALCULATE([Postings], SAMEPERIODLASTYEAR(DimDate[Date]))
RETURN DIVIDE([Postings] - prev, prev)
```

## Report pages

**Page 1 – Market pulse**
- Cards: Postings, Postings YoY %, Median Salary, Remote Share %
- Line: Postings by month, legend = role_family (or top 4 families)
- Bar: postings by city
- Slicers: date, role family, seniority, city

**Page 2 – Skills radar**
- Bar: Skill Penetration % for top 15 skills (skill on axis)
- Line: Skill Penetration % over time, small multiples by skill for
  LLMs / GenAI / SQL / Excel — the rise-and-fade story in one visual
- Table: skill, mentions, penetration %, sorted

**Page 3 – Pay**
- Bar: Median Salary by role family, conditional colour on AI/ML
- Clustered bar: Median Salary by city and seniority
- Card: AI Salary Premium %
- Note visual: "Based on the X% of postings that disclose salary"
  (always show Salary Disclosure % near pay figures - honest dashboards
  build trust)

Save as `powerbi/job_market_dashboard.pbix`, screenshots into
`powerbi/screenshots/`, embed the best one in the README.
