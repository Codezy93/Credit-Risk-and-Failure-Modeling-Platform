-- Retrospective resolved-loan benchmark, not a fixed-horizon deployment backtest.
SELECT issue_year, term_months,
    CASE WHEN term_months != 36 OR issue_year < 2011 THEN 'outside_benchmark'
         WHEN issue_year <= 2013 THEN 'train'
         WHEN issue_year = 2014 THEN 'validation'
         WHEN issue_year = 2015 THEN 'exploratory_test'
    END AS proposed_split,
    count(*) AS all_loans, count(charged_off) AS eligible_resolved_loans,
    count(*) - count(charged_off) AS excluded_other_status,
    count(*) FILTER (WHERE charged_off = 0) AS fully_paid,
    count(*) FILTER (WHERE charged_off = 1) AS charged_off,
    100.0 * count(charged_off) / count(*) AS resolved_pct,
    100.0 * avg(charged_off) AS charged_off_pct
FROM eda_loans GROUP BY issue_year, term_months, proposed_split
ORDER BY issue_year, term_months;
