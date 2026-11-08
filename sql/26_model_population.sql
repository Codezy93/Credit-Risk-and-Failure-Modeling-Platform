-- Preserve the retrospective, resolved-loan definition agreed at EDA completion.
CREATE OR REPLACE VIEW model_population AS
SELECT loan_id, issue_date, issue_year, loan_status,
    loan_amnt, annual_inc, dti, revol_util, revol_bal, open_acc,
    delinq_2yrs, pub_rec_bankruptcies, emp_length_years, fico_mid,
    credit_history_years, home_ownership, purpose, application_type,
    charged_off::TINYINT AS charged_off,
    CASE WHEN issue_year <= 2013 THEN 'train'
         WHEN issue_year = 2014 THEN 'validation'
         WHEN issue_year = 2015 THEN 'exploratory_test' END AS split
FROM read_parquet(getvariable('clean_path'))
WHERE term_months = 36 AND issue_year BETWEEN 2011 AND 2015
    AND charged_off IN (0, 1);
