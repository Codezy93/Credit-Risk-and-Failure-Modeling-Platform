-- Outcome fields belong ONLY to loss targets/audits, never to PD predictors.
-- model_contract is registered from the hashed prepared train/validation files.
CREATE OR REPLACE TABLE loss_population AS
WITH raw AS (
    SELECT try_cast(id AS BIGINT) AS loss_source_id,
        try_cast(funded_amnt AS DOUBLE) AS funded_amnt,
        try_cast(total_rec_prncp AS DOUBLE) AS total_rec_prncp,
        try_cast(recoveries AS DOUBLE) AS recoveries,
        try_cast(collection_recovery_fee AS DOUBLE) AS collection_recovery_fee
    FROM read_csv(getvariable('raw_path'), header=true, all_varchar=true)
    WHERE try_strptime(issue_d, '%b-%Y')::DATE >= DATE '2011-01-01'
      AND try_strptime(issue_d, '%b-%Y')::DATE < DATE '2015-01-01'
), joined AS (
    SELECT c.*, r.*,
        funded_amnt - total_rec_prncp AS ead_snapshot_proxy,
        recoveries - collection_recovery_fee AS net_recoveries
    FROM model_contract c LEFT JOIN raw r ON c.loan_id = r.loss_source_id
), targets AS (
    SELECT *, ead_snapshot_proxy / nullif(funded_amnt, 0) AS ead_ratio_proxy,
        1 - net_recoveries / nullif(ead_snapshot_proxy, 0) AS lgd_snapshot_proxy,
        funded_amnt > 0 AND isfinite(funded_amnt) AS funded_valid,
        total_rec_prncp BETWEEN 0 AND funded_amnt AND isfinite(total_rec_prncp)
            AND recoveries >= 0 AND isfinite(recoveries)
            AND collection_recovery_fee >= 0 AND isfinite(collection_recovery_fee) AS loss_inputs_valid
    FROM joined
)
SELECT *, coalesce(funded_valid AND loss_inputs_valid AND ead_snapshot_proxy > 0
        AND lgd_snapshot_proxy BETWEEN 0 AND 1, false) AS bounded_target_valid,
    CASE WHEN charged_off=0 THEN 0.0
         ELSE ead_snapshot_proxy - net_recoveries END AS observed_loss_proxy
FROM targets;
