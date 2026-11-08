CREATE OR REPLACE TEMP VIEW model_category_coverage AS
WITH categories AS (
    UNPIVOT model_population ON home_ownership, purpose, application_type
    INTO NAME feature VALUE category
), counts AS (
    SELECT split, feature, category, count(*) AS loans
    FROM categories GROUP BY split, feature, category
)
SELECT counts.*, EXISTS (
    SELECT 1 FROM counts training
    WHERE training.split = 'train' AND training.feature = counts.feature
        AND training.category = counts.category
) AS seen_in_training
FROM counts;

SELECT * FROM model_category_coverage ORDER BY split, feature, category;
