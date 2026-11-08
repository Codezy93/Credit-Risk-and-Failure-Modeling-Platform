-- Diagnostic cutoffs, not cleaning rules. The income p99 comes from development data.
WITH limits AS (
    SELECT quantile_cont(annual_inc, 0.99) AS income_p99 FROM eda_loans
), checks AS (
    SELECT loan_id, charged_off, 'income_above_p99' AS check_name,
        annual_inc AS value, income_p99 AS cutoff, annual_inc > income_p99 AS flagged
    FROM eda_loans CROSS JOIN limits
    UNION ALL
    SELECT loan_id, charged_off, 'income_above_1m', annual_inc, 1000000,
        annual_inc > 1000000 FROM eda_loans
    UNION ALL
    SELECT loan_id, charged_off, 'dti_above_100', dti, 100, dti > 100 FROM eda_loans
    UNION ALL
    SELECT loan_id, charged_off, 'dti_equals_999', dti, 999, dti = 999 FROM eda_loans
    UNION ALL
    SELECT loan_id, charged_off, 'utilization_above_100', revol_util, 100,
        revol_util > 100 FROM eda_loans
)
SELECT check_name, cutoff,
    CASE WHEN value IS NULL THEN 'missing'
         WHEN flagged THEN 'flagged' ELSE 'not_flagged' END AS value_group,
    count(*) AS loans, count(charged_off) AS resolved_loans,
    sum(charged_off) AS charged_off_loans,
    100.0 * avg(charged_off) AS charged_off_pct,
    min(value) AS minimum, median(value) AS median, max(value) AS maximum
FROM checks
GROUP BY check_name, cutoff, value_group
ORDER BY check_name, value_group;
