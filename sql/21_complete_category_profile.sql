WITH categories AS (
    UNPIVOT eda_loans ON grade, sub_grade, home_ownership, verification_status,
        application_type, purpose, addr_state
    INTO NAME feature VALUE category
)
SELECT feature, category, count(*) AS total_loans,
    100.0 * count(*) / (SELECT count(*) FROM eda_loans) AS pct_of_development,
    count(charged_off) AS resolved_loans, sum(charged_off) AS charged_off_loans,
    100.0 * avg(charged_off) AS charged_off_pct,
    count(*) < 200 AS rare_in_development
FROM categories GROUP BY feature, category ORDER BY feature, total_loans DESC, category;
