-- Descriptive training-only slices; grouping levels are not additive.
WITH observations AS (
    SELECT issue_year, charged_off, fico_mid, 'delinq_2yrs' AS feature, delinq_2yrs AS value FROM coefficient_population
    UNION ALL
    SELECT issue_year, charged_off, fico_mid, 'pub_rec_bankruptcies' AS feature, pub_rec_bankruptcies AS value FROM coefficient_population
), buckets AS (
    SELECT *, CASE WHEN value IS NULL THEN 'Missing' WHEN value=0 THEN '0'
        WHEN value=1 THEN '1' WHEN value=2 THEN '2' ELSE '3+' END AS value_bucket,
        CASE WHEN fico_mid IS NULL THEN 'FICO_missing'
             ELSE 'FICO_' || cast(floor(fico_mid / 20) * 20 AS INTEGER)::VARCHAR END AS fico_band
    FROM observations
)
SELECT feature,
    CASE WHEN grouping(issue_year)=0 THEN 'year_' || issue_year::VARCHAR
         WHEN grouping(fico_band)=0 THEN fico_band ELSE 'pooled' END AS cohort,
    value_bucket, count(*) AS rows, sum(charged_off)::BIGINT AS charged_off,
    avg(charged_off) AS charged_off_rate
FROM buckets
GROUP BY GROUPING SETS ((feature,value_bucket), (feature,issue_year,value_bucket), (feature,fico_band,value_bucket))
ORDER BY feature,cohort,value_bucket;
