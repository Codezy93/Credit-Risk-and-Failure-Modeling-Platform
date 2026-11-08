-- Report replacements explicitly instead of hiding them in cleaning.
SELECT 'nonpositive_income' AS check_name, count(*) FILTER (WHERE try_cast(annual_inc AS DOUBLE) <= 0) AS affected_rows FROM raw_loans
UNION ALL
SELECT 'negative_dti', count(*) FILTER (WHERE try_cast(dti AS DOUBLE) < 0) FROM raw_loans
UNION ALL
SELECT 'negative_revol_util', count(*) FILTER (WHERE try_cast(revol_util AS DOUBLE) < 0) FROM raw_loans
UNION ALL
SELECT 'credit_date_after_issue', count(*) FILTER (WHERE try_strptime(earliest_cr_line, '%b-%Y') > try_strptime(issue_d, '%b-%Y')) FROM raw_loans
UNION ALL
SELECT 'income_parse_failures', count(*) FILTER (WHERE nullif(trim(annual_inc), '') IS NOT NULL AND try_cast(annual_inc AS DOUBLE) IS NULL) FROM raw_loans
UNION ALL
SELECT 'dti_parse_failures', count(*) FILTER (WHERE nullif(trim(dti), '') IS NOT NULL AND try_cast(dti AS DOUBLE) IS NULL) FROM raw_loans;
