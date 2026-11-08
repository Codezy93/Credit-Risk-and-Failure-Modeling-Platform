WITH values_long AS (
    SELECT issue_year, 'annual_inc' AS feature, annual_inc AS value FROM eda_loans
    UNION ALL SELECT issue_year, 'dti', dti FROM eda_loans
    UNION ALL SELECT issue_year, 'revol_util', revol_util FROM eda_loans
    UNION ALL SELECT issue_year, 'emp_length_years', emp_length_years FROM eda_loans
    UNION ALL SELECT issue_year, 'credit_history_years', credit_history_years FROM eda_loans
    UNION ALL SELECT issue_year, 'pub_rec_bankruptcies', pub_rec_bankruptcies FROM eda_loans
)
SELECT issue_year, feature, count(*) AS total_loans,
    count(*) FILTER (WHERE value IS NULL) AS missing_loans,
    100.0 * count(*) FILTER (WHERE value IS NULL) / count(*) AS missing_pct
FROM values_long GROUP BY issue_year, feature ORDER BY feature, issue_year;
