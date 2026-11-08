WITH values_long AS (
    SELECT charged_off, 'annual_inc' AS feature, annual_inc AS value FROM eda_loans
    UNION ALL SELECT charged_off, 'dti', dti FROM eda_loans
    UNION ALL SELECT charged_off, 'revol_util', revol_util FROM eda_loans
    UNION ALL SELECT charged_off, 'emp_length_years', emp_length_years FROM eda_loans
    UNION ALL SELECT charged_off, 'credit_history_years', credit_history_years FROM eda_loans
    UNION ALL SELECT charged_off, 'pub_rec_bankruptcies', pub_rec_bankruptcies FROM eda_loans
)
SELECT feature, CASE WHEN value IS NULL THEN 'missing' ELSE 'present' END AS value_group,
    count(*) AS total_loans, count(charged_off) AS resolved_loans,
    sum(charged_off) AS charged_off_loans,
    100.0 * count(charged_off) / count(*) AS resolved_pct,
    100.0 * avg(charged_off) AS charged_off_pct
FROM values_long GROUP BY feature, value_group ORDER BY feature, value_group;
