WITH bands AS (
    SELECT charged_off, 'fico_mid' AS feature, floor(fico_mid / 20) * 20 AS band FROM eda_loans
    UNION ALL
    SELECT charged_off, 'dti', floor(dti / 5) * 5 FROM eda_loans
    UNION ALL
    SELECT charged_off, 'annual_inc', floor(annual_inc / 20000) * 20000 FROM eda_loans
)
SELECT feature, band, count(*) AS total_loans, count(charged_off) AS resolved_loans,
    sum(charged_off) AS charged_off_loans, 100.0 * avg(charged_off) AS charged_off_pct
FROM bands WHERE band IS NOT NULL GROUP BY feature, band ORDER BY feature, band;
