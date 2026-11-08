-- Includes candidate categories later dropped for being constant in training.
SELECT split, feature, sum(loans) AS nonmissing_loans,
    sum(CASE WHEN seen_in_training THEN 0 ELSE loans END) AS unseen_category_loans,
    100.0 * sum(CASE WHEN seen_in_training THEN 0 ELSE loans END) / sum(loans) AS unseen_pct,
    string_agg(CASE WHEN NOT seen_in_training THEN category END, ', ' ORDER BY category) AS unseen_categories
FROM model_category_coverage GROUP BY split, feature ORDER BY split, feature;
