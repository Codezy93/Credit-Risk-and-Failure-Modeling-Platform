SELECT split, count(*) AS rows, count(DISTINCT loan_id) AS unique_loan_ids,
    min(issue_date) AS first_issue_month, max(issue_date) AS last_issue_month,
    count(*) FILTER (WHERE charged_off = 0) AS fully_paid,
    count(*) FILTER (WHERE charged_off = 1) AS charged_off,
    100.0 * avg(charged_off) AS charged_off_pct,
    count(*) FILTER (WHERE loan_status IS NULL OR
        (charged_off = 0 AND loan_status != 'Fully Paid') OR
        (charged_off = 1 AND loan_status != 'Charged Off')) AS label_mismatches,
    (SELECT count(*) - count(DISTINCT loan_id) FROM model_population) AS duplicate_ids_in_population
FROM model_population GROUP BY split ORDER BY first_issue_month;
