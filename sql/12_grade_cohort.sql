SELECT issue_year, grade, count(*) AS total_loans,
    count(charged_off) AS resolved_loans,
    100.0 * count(charged_off) / count(*) AS resolved_pct,
    100.0 * avg(charged_off) AS charged_off_pct
FROM eda_loans GROUP BY issue_year, grade ORDER BY issue_year, grade;
