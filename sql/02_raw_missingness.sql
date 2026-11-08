-- Count empty strings as missing as well as SQL NULLs, across every source column.
WITH counts AS (
    SELECT count(*) - count(nullif(trim(COLUMNS(*)), '')) FROM raw_loans
), missing AS (
    UNPIVOT counts ON COLUMNS(*) INTO NAME column_name VALUE missing_count
)
SELECT column_name, missing_count,
    100.0 * missing_count / (SELECT count(*) FROM raw_loans) AS missing_pct
FROM missing
ORDER BY missing_pct DESC, column_name;
