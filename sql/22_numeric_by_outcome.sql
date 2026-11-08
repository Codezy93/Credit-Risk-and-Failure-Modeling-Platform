WITH totals AS (
    SELECT charged_off, count(*) AS group_loans FROM eda_loans
    WHERE charged_off IS NOT NULL GROUP BY charged_off
), values_long AS (
    UNPIVOT eda_loans ON loan_amnt, annual_inc, dti, revol_util, revol_bal,
        open_acc, delinq_2yrs, pub_rec_bankruptcies, emp_length_years,
        fico_mid, credit_history_years, int_rate
    INTO NAME feature VALUE value
)
SELECT feature, values_long.charged_off, totals.group_loans,
    count(*) AS nonmissing, totals.group_loans - count(*) AS missing,
    min(value) AS minimum, quantile_cont(value, 0.01) AS p01,
    quantile_cont(value, 0.25) AS p25, median(value) AS median,
    avg(value) AS mean, stddev_samp(value) AS standard_deviation,
    quantile_cont(value, 0.75) AS p75, quantile_cont(value, 0.99) AS p99,
    max(value) AS maximum
FROM values_long JOIN totals USING (charged_off)
GROUP BY feature, values_long.charged_off, totals.group_loans
ORDER BY feature, values_long.charged_off;
