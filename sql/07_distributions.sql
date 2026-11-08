-- Full-data histograms. Plotting limits are applied in Python, not to this table.
WITH values_long AS (
    UNPIVOT eda_loans ON loan_amnt, int_rate, annual_inc, dti, revol_util, fico_mid
    INTO NAME feature VALUE value
), binned AS (
    SELECT feature,
        CASE feature WHEN 'loan_amnt' THEN 1000 WHEN 'annual_inc' THEN 10000
             WHEN 'fico_mid' THEN 10 WHEN 'int_rate' THEN 1 ELSE 5 END AS width,
        value
    FROM values_long
)
SELECT feature, floor(value / width) * width AS bin_start, width, count(*) AS loans
FROM binned GROUP BY feature, bin_start, width ORDER BY feature, bin_start;
