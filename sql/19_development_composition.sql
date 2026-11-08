SELECT issue_year, count(*) AS total_loans,
    100.0 * count(*) FILTER (WHERE term_months = 60) / count(*) AS term_60_pct,
    100.0 * count(*) FILTER (WHERE grade IN ('A', 'B')) / count(*) AS grade_ab_pct,
    median(loan_amnt) AS median_loan_amnt,
    median(annual_inc) AS median_annual_inc,
    median(dti) AS median_dti, median(fico_mid) AS median_fico,
    median(int_rate) AS median_int_rate,
    100.0 * count(charged_off) / count(*) AS resolved_pct,
    100.0 * avg(charged_off) AS charged_off_pct
FROM eda_loans GROUP BY issue_year ORDER BY issue_year;
