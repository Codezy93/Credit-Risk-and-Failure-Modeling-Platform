-- Outcome denominators include only ordinary Fully Paid / Charged Off loans.
WITH categories AS (
    UNPIVOT eda_loans ON grade, purpose, home_ownership, verification_status, application_type
    INTO NAME feature VALUE category
)
SELECT feature, category, count(*) AS total_loans,
    count(charged_off) AS resolved_loans, sum(charged_off) AS charged_off_loans,
    100.0 * avg(charged_off) AS charged_off_pct
FROM categories GROUP BY feature, category ORDER BY feature, category;
