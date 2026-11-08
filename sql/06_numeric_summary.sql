WITH values_long AS (
    UNPIVOT eda_loans ON loan_amnt, int_rate, annual_inc, dti, revol_util,
        fico_mid, credit_history_years, emp_length_years
    INTO NAME feature VALUE value
)
SELECT feature, count(*) AS nonmissing,
    (SELECT count(*) FROM eda_loans) - count(*) AS missing,
    min(value) AS minimum, quantile_cont(value, 0.01) AS p01,
    quantile_cont(value, 0.25) AS p25, median(value) AS median,
    quantile_cont(value, 0.75) AS p75, quantile_cont(value, 0.99) AS p99,
    max(value) AS maximum
FROM values_long GROUP BY feature ORDER BY feature;
