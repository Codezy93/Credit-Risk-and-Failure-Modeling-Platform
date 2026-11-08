SELECT issue_year, term_months, count(*) AS total_loans,
    count(charged_off) AS resolved_loans,
    100.0 * count(charged_off) / count(*) AS resolved_pct,
    100.0 * avg(charged_off) AS charged_off_pct
FROM loans GROUP BY issue_year, term_months ORDER BY issue_year, term_months;
