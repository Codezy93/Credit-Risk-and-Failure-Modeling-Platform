-- audit_population contains only hashed prepared loans, their frozen scores,
-- and state joined by ID from the unchanged clean table. No new predictors.
CREATE OR REPLACE TABLE audit_segments AS
WITH labels AS (
    SELECT loan_id, split, charged_off, probability,
        coalesce(nullif(trim(home_ownership), ''), 'Missing') AS home_group,
        coalesce(nullif(trim(purpose), ''), 'Missing') AS purpose_group,
        CASE WHEN annual_inc IS NULL THEN 'Missing'
             WHEN annual_inc <= getvariable('income_q1') THEN 'Q1_lowest'
             WHEN annual_inc <= getvariable('income_q2') THEN 'Q2'
             WHEN annual_inc <= getvariable('income_q3') THEN 'Q3' ELSE 'Q4_highest' END AS income_group,
        CASE WHEN fico_mid IS NULL THEN 'Missing' WHEN fico_mid < 680 THEN 'Below_680'
             WHEN fico_mid < 720 THEN '680_to_719' WHEN fico_mid < 760 THEN '720_to_759' ELSE '760_plus' END AS fico_group,
        CASE WHEN emp_length_years IS NULL THEN 'Missing' WHEN emp_length_years < 2 THEN 'Below_2_years'
             WHEN emp_length_years < 6 THEN '2_to_5_years' WHEN emp_length_years < 10 THEN '6_to_9_years'
             ELSE '10_plus_years' END AS employment_group,
        CASE WHEN delinq_2yrs IS NULL THEN 'Missing' WHEN delinq_2yrs=0 THEN 'None' ELSE 'One_or_more' END AS delinquency_group,
        CASE WHEN pub_rec_bankruptcies IS NULL THEN 'Missing' WHEN pub_rec_bankruptcies=0 THEN 'None' ELSE 'One_or_more' END AS bankruptcy_group,
        CASE WHEN has_missing_predictor THEN 'Any_missing' ELSE 'Complete' END AS missingness_group,
        coalesce(nullif(trim(addr_state), ''), 'Missing') AS state_group,
        coalesce(nullif(trim(application_type), ''), 'Missing') AS application_group
    FROM audit_population
)
SELECT *, income_group || ' / ' || home_group AS income_home_group,
    fico_group || ' / ' || delinquency_group AS fico_delinquency_group
FROM labels;
