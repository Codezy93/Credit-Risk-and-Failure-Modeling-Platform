-- Preserve missingness in the prepared splits; do not fit an imputer here.
SELECT split, 'loan_amnt' AS feature, count(*) AS rows,
    count(*) - count(loan_amnt) AS missing,
    100.0 * (count(*) - count(loan_amnt)) / count(*) AS missing_pct
FROM model_population GROUP BY split
UNION ALL
SELECT split, 'annual_inc' AS feature, count(*) AS rows,
    count(*) - count(annual_inc) AS missing,
    100.0 * (count(*) - count(annual_inc)) / count(*) AS missing_pct
FROM model_population GROUP BY split
UNION ALL
SELECT split, 'dti' AS feature, count(*) AS rows,
    count(*) - count(dti) AS missing,
    100.0 * (count(*) - count(dti)) / count(*) AS missing_pct
FROM model_population GROUP BY split
UNION ALL
SELECT split, 'revol_util' AS feature, count(*) AS rows,
    count(*) - count(revol_util) AS missing,
    100.0 * (count(*) - count(revol_util)) / count(*) AS missing_pct
FROM model_population GROUP BY split
UNION ALL
SELECT split, 'revol_bal' AS feature, count(*) AS rows,
    count(*) - count(revol_bal) AS missing,
    100.0 * (count(*) - count(revol_bal)) / count(*) AS missing_pct
FROM model_population GROUP BY split
UNION ALL
SELECT split, 'open_acc' AS feature, count(*) AS rows,
    count(*) - count(open_acc) AS missing,
    100.0 * (count(*) - count(open_acc)) / count(*) AS missing_pct
FROM model_population GROUP BY split
UNION ALL
SELECT split, 'delinq_2yrs' AS feature, count(*) AS rows,
    count(*) - count(delinq_2yrs) AS missing,
    100.0 * (count(*) - count(delinq_2yrs)) / count(*) AS missing_pct
FROM model_population GROUP BY split
UNION ALL
SELECT split, 'pub_rec_bankruptcies' AS feature, count(*) AS rows,
    count(*) - count(pub_rec_bankruptcies) AS missing,
    100.0 * (count(*) - count(pub_rec_bankruptcies)) / count(*) AS missing_pct
FROM model_population GROUP BY split
UNION ALL
SELECT split, 'emp_length_years' AS feature, count(*) AS rows,
    count(*) - count(emp_length_years) AS missing,
    100.0 * (count(*) - count(emp_length_years)) / count(*) AS missing_pct
FROM model_population GROUP BY split
UNION ALL
SELECT split, 'fico_mid' AS feature, count(*) AS rows,
    count(*) - count(fico_mid) AS missing,
    100.0 * (count(*) - count(fico_mid)) / count(*) AS missing_pct
FROM model_population GROUP BY split
UNION ALL
SELECT split, 'credit_history_years' AS feature, count(*) AS rows,
    count(*) - count(credit_history_years) AS missing,
    100.0 * (count(*) - count(credit_history_years)) / count(*) AS missing_pct
FROM model_population GROUP BY split
UNION ALL
SELECT split, 'home_ownership' AS feature, count(*) AS rows,
    count(*) - count(home_ownership) AS missing,
    100.0 * (count(*) - count(home_ownership)) / count(*) AS missing_pct
FROM model_population GROUP BY split
UNION ALL
SELECT split, 'purpose' AS feature, count(*) AS rows,
    count(*) - count(purpose) AS missing,
    100.0 * (count(*) - count(purpose)) / count(*) AS missing_pct
FROM model_population GROUP BY split
UNION ALL
SELECT split, 'application_type' AS feature, count(*) AS rows,
    count(*) - count(application_type) AS missing,
    100.0 * (count(*) - count(application_type)) / count(*) AS missing_pct
FROM model_population GROUP BY split
ORDER BY split, feature;
