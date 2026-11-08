-- Diagnostic audit of clean development values. It does not remove rows.
SELECT 'nonpositive_loan_amount' AS check_name,
    count(*) FILTER (WHERE loan_amnt <= 0) AS affected_loans FROM eda_loans
UNION ALL SELECT 'missing_loan_amount', count(*) FILTER (WHERE loan_amnt IS NULL) FROM eda_loans
UNION ALL SELECT 'interest_outside_0_to_100', count(*) FILTER (WHERE int_rate <= 0 OR int_rate >= 100) FROM eda_loans
UNION ALL SELECT 'nonpositive_installment', count(*) FILTER (WHERE installment <= 0) FROM eda_loans
UNION ALL SELECT 'unexpected_term', count(*) FILTER (WHERE term_months IS NULL OR term_months NOT IN (36, 60)) FROM eda_loans
UNION ALL SELECT 'nonpositive_clean_income', count(*) FILTER (WHERE annual_inc <= 0) FROM eda_loans
UNION ALL SELECT 'negative_clean_dti', count(*) FILTER (WHERE dti < 0) FROM eda_loans
UNION ALL SELECT 'negative_clean_utilization', count(*) FILTER (WHERE revol_util < 0) FROM eda_loans
UNION ALL SELECT 'negative_revolving_balance', count(*) FILTER (WHERE revol_bal < 0) FROM eda_loans
UNION ALL SELECT 'negative_open_accounts', count(*) FILTER (WHERE open_acc < 0) FROM eda_loans
UNION ALL SELECT 'negative_delinquencies', count(*) FILTER (WHERE delinq_2yrs < 0) FROM eda_loans
UNION ALL SELECT 'negative_bankruptcies', count(*) FILTER (WHERE pub_rec_bankruptcies < 0) FROM eda_loans
UNION ALL SELECT 'employment_outside_0_to_10', count(*) FILTER (WHERE emp_length_years < 0 OR emp_length_years > 10) FROM eda_loans
UNION ALL SELECT 'fico_outside_300_to_850', count(*) FILTER (WHERE fico_mid < 300 OR fico_mid > 850) FROM eda_loans
UNION ALL SELECT 'negative_credit_history', count(*) FILTER (WHERE credit_history_years < 0) FROM eda_loans;
