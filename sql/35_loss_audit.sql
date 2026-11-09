SELECT split, count(*) AS rows, sum(charged_off) AS charged_off_rows,
    count(*) FILTER (WHERE loss_source_id IS NULL) AS missing_source,
    count(*) FILTER (WHERE NOT coalesce(funded_valid, false)) AS invalid_funded,
    count(*) FILTER (WHERE charged_off=1 AND NOT coalesce(loss_inputs_valid, false)) AS bad_or_missing_loss_inputs,
    count(*) FILTER (WHERE charged_off=1 AND ead_snapshot_proxy <= 0) AS nonpositive_default_ead,
    count(*) FILTER (WHERE charged_off=1 AND lgd_snapshot_proxy < 0) AS negative_lgd,
    count(*) FILTER (WHERE charged_off=1 AND lgd_snapshot_proxy > 1) AS lgd_above_one,
    count(*) FILTER (WHERE charged_off=1 AND bounded_target_valid) AS eligible_defaults,
    count(*) FILTER (WHERE coalesce(funded_valid, false) AND
        (charged_off=0 OR bounded_target_valid)) AS eligible_portfolio_rows
FROM loss_population GROUP BY split ORDER BY split;
