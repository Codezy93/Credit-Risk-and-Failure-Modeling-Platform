-- This narrower comparison uses 36-month loans from 2011-2014.
-- Its outcome coverage is reported, rather than assumed to be complete.
WITH bands AS (
    SELECT charged_off,
        CASE WHEN fico_mid IS NULL THEN 6 WHEN fico_mid < 660 THEN 1
             WHEN fico_mid < 680 THEN 2 WHEN fico_mid < 700 THEN 3
             WHEN fico_mid < 740 THEN 4 ELSE 5 END AS fico_order,
        CASE WHEN fico_mid IS NULL THEN 'Missing' WHEN fico_mid < 660 THEN '<660'
             WHEN fico_mid < 680 THEN '660-<680' WHEN fico_mid < 700 THEN '680-<700'
             WHEN fico_mid < 740 THEN '700-<740' ELSE '740+' END AS fico_band,
        CASE WHEN dti IS NULL THEN 5 WHEN dti < 10 THEN 1
             WHEN dti < 20 THEN 2 WHEN dti < 30 THEN 3 ELSE 4 END AS dti_order,
        CASE WHEN dti IS NULL THEN 'Missing' WHEN dti < 10 THEN '<10'
             WHEN dti < 20 THEN '10-<20' WHEN dti < 30 THEN '20-<30'
             ELSE '30+' END AS dti_band
    FROM eda_loans WHERE issue_year BETWEEN 2011 AND 2014 AND term_months = 36
)
SELECT fico_order, fico_band, dti_order, dti_band, count(*) AS total_loans,
    count(charged_off) AS resolved_loans, sum(charged_off) AS charged_off_loans,
    100.0 * count(charged_off) / count(*) AS resolved_pct,
    100.0 * avg(charged_off) AS charged_off_pct
FROM bands GROUP BY fico_order, fico_band, dti_order, dti_band
ORDER BY fico_order, dti_order;
