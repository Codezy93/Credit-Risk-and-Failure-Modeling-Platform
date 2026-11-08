WITH values_long AS (
    UNPIVOT eda_loans ON loan_amnt, installment, term_months, emp_length_years,
        annual_inc, dti, revol_util, revol_bal, open_acc, delinq_2yrs,
        pub_rec_bankruptcies, fico_mid, credit_history_years, int_rate
    INTO NAME feature VALUE value
)
SELECT feature, count(*) AS nonmissing,
    (SELECT count(*) FROM eda_loans) - count(*) AS missing,
    100.0 * ((SELECT count(*) FROM eda_loans) - count(*)) /
        (SELECT count(*) FROM eda_loans) AS missing_pct,
    count(DISTINCT value) AS distinct_values,
    min(value) AS minimum, quantile_cont(value, 0.01) AS p01,
    quantile_cont(value, 0.25) AS p25, median(value) AS median,
    avg(value) AS mean, stddev_samp(value) AS standard_deviation,
    quantile_cont(value, 0.75) AS p75, quantile_cont(value, 0.99) AS p99,
    max(value) AS maximum, skewness(value) AS skewness,
    kurtosis(value) AS excess_kurtosis
FROM values_long GROUP BY feature ORDER BY feature;
