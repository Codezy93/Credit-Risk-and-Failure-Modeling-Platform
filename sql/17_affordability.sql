-- Requested principal / annual income and this loan's installment / monthly income.
-- These describe the approved loan; they are not additional pre-pricing features.
WITH ratios AS (
    SELECT charged_off, 'principal_to_annual_income' AS metric,
        loan_amnt / annual_inc AS ratio FROM eda_loans
    UNION ALL
    SELECT charged_off, 'installment_to_monthly_income',
        12.0 * installment / annual_inc FROM eda_loans
), bands AS (
    SELECT *, CASE WHEN ratio IS NULL THEN 6
        WHEN ratio < 0.10 THEN 1 WHEN ratio < 0.20 THEN 2
        WHEN ratio < 0.30 THEN 3 WHEN ratio < 0.50 THEN 4 ELSE 5 END AS band_order,
        CASE WHEN ratio IS NULL THEN 'Missing'
        WHEN ratio < 0.10 THEN '<10%' WHEN ratio < 0.20 THEN '10-<20%'
        WHEN ratio < 0.30 THEN '20-<30%' WHEN ratio < 0.50 THEN '30-<50%'
        ELSE '50%+' END AS ratio_band
    FROM ratios
)
SELECT metric, band_order, ratio_band, count(*) AS total_loans,
    count(charged_off) AS resolved_loans, sum(charged_off) AS charged_off_loans,
    100.0 * count(charged_off) / count(*) AS resolved_pct,
    100.0 * avg(charged_off) AS charged_off_pct,
    median(ratio) AS median_ratio, max(ratio) AS maximum_ratio
FROM bands GROUP BY metric, band_order, ratio_band ORDER BY metric, band_order;
