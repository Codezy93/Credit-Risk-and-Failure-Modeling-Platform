-- A focused analysis table, not a final model feature matrix.
-- Payment, recovery, settlement and last-FICO fields are deliberately excluded.
CREATE OR REPLACE TABLE loans AS
WITH typed AS (
    SELECT
        try_cast(id AS BIGINT) AS loan_id,
        try_strptime(issue_d, '%b-%Y')::DATE AS issue_date,
        try_strptime(earliest_cr_line, '%b-%Y')::DATE AS earliest_credit_date,
        try_cast(loan_amnt AS DOUBLE) AS loan_amnt,
        try_cast(replace(int_rate, '%', '') AS DOUBLE) AS int_rate,
        try_cast(installment AS DOUBLE) AS installment,
        try_cast(regexp_extract(term, '[0-9]+') AS INTEGER) AS term_months,
        nullif(trim(grade), '') AS grade,
        nullif(trim(sub_grade), '') AS sub_grade,
        nullif(trim(home_ownership), '') AS home_ownership,
        nullif(trim(verification_status), '') AS verification_status,
        nullif(trim(application_type), '') AS application_type,
        nullif(trim(purpose), '') AS purpose,
        nullif(trim(addr_state), '') AS addr_state,
        nullif(trim(loan_status), '') AS loan_status,
        CASE WHEN trim(emp_length) = '< 1 year' THEN 0
             ELSE try_cast(regexp_extract(emp_length, '[0-9]+') AS INTEGER)
        END AS emp_length_years,
        try_cast(annual_inc AS DOUBLE) AS annual_inc,
        try_cast(dti AS DOUBLE) AS dti,
        try_cast(revol_util AS DOUBLE) AS revol_util,
        try_cast(revol_bal AS DOUBLE) AS revol_bal,
        try_cast(open_acc AS DOUBLE) AS open_acc,
        try_cast(delinq_2yrs AS DOUBLE) AS delinq_2yrs,
        try_cast(pub_rec_bankruptcies AS DOUBLE) AS pub_rec_bankruptcies,
        (try_cast(fico_range_low AS DOUBLE) + try_cast(fico_range_high AS DOUBLE)) / 2 AS fico_mid
    FROM raw_loans
)
SELECT * EXCLUDE (annual_inc, dti, revol_util, earliest_credit_date),
    CASE WHEN annual_inc > 0 THEN annual_inc END AS annual_inc,
    CASE WHEN dti >= 0 THEN dti END AS dti,
    -- Values above 100% can occur; do not silently cap them.
    CASE WHEN revol_util >= 0 THEN revol_util END AS revol_util,
    CASE WHEN earliest_credit_date <= issue_date
         THEN date_diff('month', earliest_credit_date, issue_date) / 12.0
    END AS credit_history_years,
    CASE WHEN loan_status = 'Charged Off' THEN 1
         WHEN loan_status = 'Fully Paid' THEN 0
    END AS charged_off,
    year(issue_date) AS issue_year
FROM typed
WHERE loan_id IS NOT NULL AND issue_date IS NOT NULL;

-- Feature and outcome exploration stays in the development period.
CREATE OR REPLACE VIEW eda_loans AS SELECT * FROM loans WHERE issue_year <= 2015;
