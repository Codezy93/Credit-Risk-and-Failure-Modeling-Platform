-- Audit numeric source fields used by the clean table, before NULL replacements.
WITH raw_development AS (
    SELECT loan_amnt, int_rate, installment, annual_inc, dti, revol_util,
        revol_bal, open_acc, delinq_2yrs, pub_rec_bankruptcies,
        fico_range_low, fico_range_high, term, emp_length, issue_d, earliest_cr_line
    FROM read_csv(getvariable('raw_path'), header = true, all_varchar = true)
    WHERE try_cast(id AS BIGINT) IS NOT NULL
      AND try_strptime(issue_d, '%b-%Y')::DATE < DATE '2016-01-01'
), values_long AS (
    UNPIVOT raw_development ON loan_amnt, int_rate, installment, annual_inc,
        dti, revol_util, revol_bal, open_acc, delinq_2yrs,
        pub_rec_bankruptcies, fico_range_low, fico_range_high
    INTO NAME feature VALUE source_value
), parsed AS (
    SELECT feature, nullif(trim(source_value), '') AS source_value,
        try_cast(CASE WHEN feature = 'int_rate' THEN replace(source_value, '%', '')
                      ELSE source_value END AS DOUBLE) AS numeric_value
    FROM values_long
)
SELECT feature,
    (SELECT count(*) FROM raw_development) AS development_rows,
    count(source_value) AS nonblank_source_values,
    (SELECT count(*) FROM raw_development) - count(source_value) AS missing_source_values,
    count(*) FILTER (WHERE source_value IS NOT NULL AND numeric_value IS NULL) AS parse_failures,
    count(*) FILTER (WHERE numeric_value IS NOT NULL AND NOT isfinite(numeric_value)) AS nonfinite_values
FROM parsed GROUP BY feature
UNION ALL
SELECT 'term', count(*), count(nullif(trim(term), '')),
    count(*) - count(nullif(trim(term), '')),
    count(*) FILTER (WHERE nullif(trim(term), '') IS NOT NULL
        AND try_cast(regexp_extract(term, '[0-9]+') AS INTEGER) IS NULL), 0
FROM raw_development
UNION ALL
SELECT 'emp_length', count(*), count(nullif(nullif(trim(emp_length), ''), 'n/a')),
    count(*) - count(nullif(nullif(trim(emp_length), ''), 'n/a')),
    count(*) FILTER (WHERE nullif(nullif(trim(emp_length), ''), 'n/a') IS NOT NULL
        AND try_cast(regexp_extract(emp_length, '[0-9]+') AS INTEGER) IS NULL), 0
FROM raw_development
UNION ALL
SELECT 'issue_d', count(*), count(nullif(trim(issue_d), '')),
    count(*) - count(nullif(trim(issue_d), '')),
    count(*) FILTER (WHERE nullif(trim(issue_d), '') IS NOT NULL
        AND try_strptime(issue_d, '%b-%Y') IS NULL), 0
FROM raw_development
UNION ALL
SELECT 'earliest_cr_line', count(*), count(nullif(trim(earliest_cr_line), '')),
    count(*) - count(nullif(trim(earliest_cr_line), '')),
    count(*) FILTER (WHERE nullif(trim(earliest_cr_line), '') IS NOT NULL
        AND try_strptime(earliest_cr_line, '%b-%Y') IS NULL), 0
FROM raw_development
ORDER BY feature;
