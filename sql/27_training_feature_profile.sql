-- Feature removal is decided using training rows only.
WITH training AS MATERIALIZED (
    SELECT * FROM model_population WHERE split = 'train'
)
SELECT 'loan_amnt' AS feature, count(*) AS train_rows,
    count(loan_amnt) AS nonmissing, count(*) - count(loan_amnt) AS missing,
    count(DISTINCT loan_amnt) AS distinct_nonmissing FROM training
UNION ALL
SELECT 'annual_inc' AS feature, count(*) AS train_rows,
    count(annual_inc) AS nonmissing, count(*) - count(annual_inc) AS missing,
    count(DISTINCT annual_inc) AS distinct_nonmissing FROM training
UNION ALL
SELECT 'dti' AS feature, count(*) AS train_rows,
    count(dti) AS nonmissing, count(*) - count(dti) AS missing,
    count(DISTINCT dti) AS distinct_nonmissing FROM training
UNION ALL
SELECT 'revol_util' AS feature, count(*) AS train_rows,
    count(revol_util) AS nonmissing, count(*) - count(revol_util) AS missing,
    count(DISTINCT revol_util) AS distinct_nonmissing FROM training
UNION ALL
SELECT 'revol_bal' AS feature, count(*) AS train_rows,
    count(revol_bal) AS nonmissing, count(*) - count(revol_bal) AS missing,
    count(DISTINCT revol_bal) AS distinct_nonmissing FROM training
UNION ALL
SELECT 'open_acc' AS feature, count(*) AS train_rows,
    count(open_acc) AS nonmissing, count(*) - count(open_acc) AS missing,
    count(DISTINCT open_acc) AS distinct_nonmissing FROM training
UNION ALL
SELECT 'delinq_2yrs' AS feature, count(*) AS train_rows,
    count(delinq_2yrs) AS nonmissing, count(*) - count(delinq_2yrs) AS missing,
    count(DISTINCT delinq_2yrs) AS distinct_nonmissing FROM training
UNION ALL
SELECT 'pub_rec_bankruptcies' AS feature, count(*) AS train_rows,
    count(pub_rec_bankruptcies) AS nonmissing, count(*) - count(pub_rec_bankruptcies) AS missing,
    count(DISTINCT pub_rec_bankruptcies) AS distinct_nonmissing FROM training
UNION ALL
SELECT 'emp_length_years' AS feature, count(*) AS train_rows,
    count(emp_length_years) AS nonmissing, count(*) - count(emp_length_years) AS missing,
    count(DISTINCT emp_length_years) AS distinct_nonmissing FROM training
UNION ALL
SELECT 'fico_mid' AS feature, count(*) AS train_rows,
    count(fico_mid) AS nonmissing, count(*) - count(fico_mid) AS missing,
    count(DISTINCT fico_mid) AS distinct_nonmissing FROM training
UNION ALL
SELECT 'credit_history_years' AS feature, count(*) AS train_rows,
    count(credit_history_years) AS nonmissing, count(*) - count(credit_history_years) AS missing,
    count(DISTINCT credit_history_years) AS distinct_nonmissing FROM training
UNION ALL
SELECT 'home_ownership' AS feature, count(*) AS train_rows,
    count(home_ownership) AS nonmissing, count(*) - count(home_ownership) AS missing,
    count(DISTINCT home_ownership) AS distinct_nonmissing FROM training
UNION ALL
SELECT 'purpose' AS feature, count(*) AS train_rows,
    count(purpose) AS nonmissing, count(*) - count(purpose) AS missing,
    count(DISTINCT purpose) AS distinct_nonmissing FROM training
UNION ALL
SELECT 'application_type' AS feature, count(*) AS train_rows,
    count(application_type) AS nonmissing, count(*) - count(application_type) AS missing,
    count(DISTINCT application_type) AS distinct_nonmissing FROM training
ORDER BY feature;
