-- ================================================================
-- AI & Data Job Market Analytics - SQL queries
-- Database: job_market.db (SQLite), built by scripts/etl_pipeline.py
-- Tables: postings (one row per ad), posting_skills (long format)
-- ================================================================

-- 1. Posting volume by role family and quarter
SELECT
    post_quarter,
    role_family,
    COUNT(*) AS postings
FROM postings
GROUP BY post_quarter, role_family
ORDER BY post_quarter, postings DESC;


-- 2. Role family growth: first quarter vs latest quarter
WITH bounds AS (
    SELECT MIN(post_quarter) AS q_first, MAX(post_quarter) AS q_last FROM postings
),
counts AS (
    SELECT
        role_family,
        SUM(CASE WHEN post_quarter = (SELECT q_first FROM bounds) THEN 1 ELSE 0 END) AS first_q,
        SUM(CASE WHEN post_quarter = (SELECT q_last  FROM bounds) THEN 1 ELSE 0 END) AS last_q
    FROM postings
    GROUP BY role_family
)
SELECT
    role_family,
    first_q,
    last_q,
    ROUND(100.0 * (last_q - first_q) / first_q, 0) AS growth_pct
FROM counts
ORDER BY growth_pct DESC;


-- 3. Top 15 most requested skills overall
SELECT
    s.skill,
    COUNT(*) AS mentions,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM postings), 1) AS pct_of_postings
FROM posting_skills s
GROUP BY s.skill
ORDER BY mentions DESC
LIMIT 15;


-- 4. Skill trend for the GenAI cluster: naive version
--    (divides by ALL postings, not per-period totals - query 5 fixes this)
SELECT
    CASE WHEN SUBSTR(p.post_month, 6, 2) <= '06'
         THEN SUBSTR(p.post_month, 1, 4) || '-H1'
         ELSE SUBSTR(p.post_month, 1, 4) || '-H2' END AS half_year,
    s.skill,
    COUNT(DISTINCT s.posting_id) AS postings_mentioning,
    ROUND(100.0 * COUNT(DISTINCT s.posting_id) /
        (SELECT COUNT(*) FROM postings), 2) AS naive_pct  -- see query 5
FROM postings p
JOIN posting_skills s ON s.posting_id = p.posting_id
WHERE s.skill IN ('LLMs', 'GenAI', 'RAG', 'Prompt Engineering', 'MLOps')
GROUP BY half_year, s.skill
ORDER BY half_year, postings_mentioning DESC;


-- 5. Same trend done properly: skill share within each half-year
WITH totals AS (
    SELECT
        CASE WHEN SUBSTR(post_month, 6, 2) <= '06'
             THEN SUBSTR(post_month, 1, 4) || '-H1'
             ELSE SUBSTR(post_month, 1, 4) || '-H2' END AS half_year,
        COUNT(*) AS total_postings
    FROM postings
    GROUP BY half_year
)
SELECT
    t.half_year,
    s.skill,
    COUNT(*) AS mentions,
    ROUND(100.0 * COUNT(*) / t.total_postings, 2) AS pct_of_postings
FROM posting_skills s
JOIN postings p ON p.posting_id = s.posting_id
JOIN totals t
  ON t.half_year = CASE WHEN SUBSTR(p.post_month, 6, 2) <= '06'
                        THEN SUBSTR(p.post_month, 1, 4) || '-H1'
                        ELSE SUBSTR(p.post_month, 1, 4) || '-H2' END
WHERE s.skill IN ('LLMs', 'GenAI', 'SQL', 'Excel')
GROUP BY t.half_year, s.skill, t.total_postings
ORDER BY s.skill, t.half_year;


-- 6. Median advertised salary by role family (disclosed postings only)
WITH ranked AS (
    SELECT
        role_family,
        salary_mid_eur,
        ROW_NUMBER() OVER (PARTITION BY role_family ORDER BY salary_mid_eur) AS rn,
        COUNT(*)    OVER (PARTITION BY role_family)                          AS cnt
    FROM postings
    WHERE salary_disclosed = 1
)
SELECT
    role_family,
    MAX(cnt) AS disclosed_postings,
    ROUND(AVG(CASE WHEN rn IN ((cnt+1)/2, (cnt+2)/2) THEN salary_mid_eur END), 0)
        AS median_salary_eur
FROM ranked
GROUP BY role_family
ORDER BY median_salary_eur DESC;


-- 7. The AI premium by city: AI/ML roles vs everything else
WITH tagged AS (
    SELECT
        city,
        CASE WHEN role_family IN ('AI Engineer', 'ML Engineer')
             THEN 'AI/ML' ELSE 'Other data roles' END AS bucket,
        salary_mid_eur
    FROM postings
    WHERE salary_disclosed = 1
),
ranked AS (
    SELECT city, bucket, salary_mid_eur,
        ROW_NUMBER() OVER (PARTITION BY city, bucket ORDER BY salary_mid_eur) AS rn,
        COUNT(*)    OVER (PARTITION BY city, bucket)                          AS cnt
    FROM tagged
)
SELECT
    city,
    ROUND(AVG(CASE WHEN bucket = 'AI/ML' AND rn IN ((cnt+1)/2,(cnt+2)/2)
              THEN salary_mid_eur END), 0) AS ai_ml_median,
    ROUND(AVG(CASE WHEN bucket = 'Other data roles' AND rn IN ((cnt+1)/2,(cnt+2)/2)
              THEN salary_mid_eur END), 0) AS other_median
FROM ranked
GROUP BY city
ORDER BY ai_ml_median DESC;


-- 8. Salary transparency by country: who discloses?
SELECT
    country,
    COUNT(*) AS postings,
    ROUND(100.0 * SUM(salary_disclosed) / COUNT(*), 1) AS disclosure_pct
FROM postings
GROUP BY country
ORDER BY disclosure_pct DESC;


-- 9. Work mode trend by quarter
SELECT
    post_quarter,
    ROUND(100.0 * SUM(CASE WHEN work_mode = 'Remote' THEN 1 ELSE 0 END) / COUNT(*), 1) AS remote_pct,
    ROUND(100.0 * SUM(CASE WHEN work_mode = 'Hybrid' THEN 1 ELSE 0 END) / COUNT(*), 1) AS hybrid_pct,
    ROUND(100.0 * SUM(CASE WHEN work_mode = 'On-site' THEN 1 ELSE 0 END) / COUNT(*), 1) AS onsite_pct
FROM postings
GROUP BY post_quarter
ORDER BY post_quarter;


-- 10. Top skill pairs (co-occurrence within the same posting)
SELECT
    a.skill AS skill_1,
    b.skill AS skill_2,
    COUNT(*) AS postings_together
FROM posting_skills a
JOIN posting_skills b
  ON a.posting_id = b.posting_id
 AND a.skill < b.skill          -- each pair once, no self-pairs
GROUP BY a.skill, b.skill
ORDER BY postings_together DESC
LIMIT 15;


-- 11. Dublin snapshot: what the local market asks for
SELECT
    s.skill,
    COUNT(*) AS mentions,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM postings WHERE city = 'Dublin'), 1)
        AS pct_of_dublin_postings
FROM posting_skills s
JOIN postings p ON p.posting_id = s.posting_id
WHERE p.city = 'Dublin'
GROUP BY s.skill
ORDER BY mentions DESC
LIMIT 10;
