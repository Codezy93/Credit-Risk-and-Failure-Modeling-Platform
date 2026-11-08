-- Keep the source unchanged. Types are handled explicitly in the cleaning query.
CREATE OR REPLACE VIEW raw_loans AS
SELECT * FROM read_csv(
    getvariable('raw_path'),
    header = true,
    all_varchar = true,
    sample_size = 20000
);
