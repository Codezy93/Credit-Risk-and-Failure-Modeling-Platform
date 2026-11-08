SELECT grade, term_months, count(*) AS total_loans,
    count(charged_off) AS resolved_loans, 100.0 * avg(charged_off) AS charged_off_pct,
    avg(int_rate) AS mean_interest_rate
FROM eda_loans GROUP BY grade, term_months ORDER BY grade, term_months;
