SELECT
    count(*) AS raw_rows,
    count(*) FILTER (WHERE try_cast(id AS BIGINT) IS NULL) AS invalid_id_rows,
    count(try_cast(id AS BIGINT)) - count(DISTINCT try_cast(id AS BIGINT)) AS duplicate_ids,
    count(*) FILTER (WHERE try_strptime(issue_d, '%b-%Y') IS NULL) AS invalid_issue_dates,
    min(try_strptime(issue_d, '%b-%Y'))::DATE AS first_issue_date,
    max(try_strptime(issue_d, '%b-%Y'))::DATE AS last_issue_date
FROM raw_loans;
