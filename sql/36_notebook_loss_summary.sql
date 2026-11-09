-- The notebook registers the saved component metrics as component_metrics.
SELECT component, model, rows AS defaulted_validation_loans,
    bounded_mae, bounded_rmse, bounded_r2, observed_mean, predicted_mean,
    predictions_clipped
FROM component_metrics WHERE split='validation'
ORDER BY component, bounded_mae, model;
