-- Candidate bureau fields only; never read payment, recovery, settlement, or last-FICO inputs.
-- Availability of added snapshot fields remains a deployment-validation caveat.
-- This experiment deliberately excludes the 2015 evaluation population.
CREATE OR REPLACE TABLE auc_population AS
WITH raw AS (
    SELECT try_cast(id AS BIGINT) AS loan_id,
        try_cast(inq_last_6mths AS DOUBLE) AS inq_last_6mths,
        try_cast(total_acc AS DOUBLE) AS total_acc,
        try_cast(pub_rec AS DOUBLE) AS pub_rec,
        try_cast(collections_12_mths_ex_med AS DOUBLE) AS collections_12_mths_ex_med,
        try_cast(mths_since_last_delinq AS DOUBLE) AS mths_since_last_delinq,
        try_cast(mths_since_last_record AS DOUBLE) AS mths_since_last_record,
        try_cast(mths_since_last_major_derog AS DOUBLE) AS mths_since_last_major_derog,
        try_cast(acc_now_delinq AS DOUBLE) AS acc_now_delinq,
        try_cast(tot_coll_amt AS DOUBLE) AS tot_coll_amt,
        try_cast(tot_cur_bal AS DOUBLE) AS tot_cur_bal,
        try_cast(total_rev_hi_lim AS DOUBLE) AS total_rev_hi_lim,
        try_cast(acc_open_past_24mths AS DOUBLE) AS acc_open_past_24mths,
        try_cast(avg_cur_bal AS DOUBLE) AS avg_cur_bal,
        try_cast(bc_open_to_buy AS DOUBLE) AS bc_open_to_buy,
        try_cast(bc_util AS DOUBLE) AS bc_util,
        try_cast(mort_acc AS DOUBLE) AS mort_acc,
        try_cast(num_accts_ever_120_pd AS DOUBLE) AS num_accts_ever_120_pd,
        try_cast(num_actv_bc_tl AS DOUBLE) AS num_actv_bc_tl,
        try_cast(num_actv_rev_tl AS DOUBLE) AS num_actv_rev_tl,
        try_cast(num_bc_sats AS DOUBLE) AS num_bc_sats,
        try_cast(num_bc_tl AS DOUBLE) AS num_bc_tl,
        try_cast(num_il_tl AS DOUBLE) AS num_il_tl,
        try_cast(num_op_rev_tl AS DOUBLE) AS num_op_rev_tl,
        try_cast(num_rev_accts AS DOUBLE) AS num_rev_accts,
        try_cast(num_rev_tl_bal_gt_0 AS DOUBLE) AS num_rev_tl_bal_gt_0,
        try_cast(num_sats AS DOUBLE) AS num_sats,
        try_cast(num_tl_30dpd AS DOUBLE) AS num_tl_30dpd,
        try_cast(num_tl_90g_dpd_24m AS DOUBLE) AS num_tl_90g_dpd_24m,
        try_cast(num_tl_op_past_12m AS DOUBLE) AS num_tl_op_past_12m,
        try_cast(pct_tl_nvr_dlq AS DOUBLE) AS pct_tl_nvr_dlq,
        try_cast(percent_bc_gt_75 AS DOUBLE) AS percent_bc_gt_75,
        try_cast(tax_liens AS DOUBLE) AS tax_liens,
        try_cast(tot_hi_cred_lim AS DOUBLE) AS tot_hi_cred_lim,
        try_cast(total_bal_ex_mort AS DOUBLE) AS total_bal_ex_mort,
        try_cast(total_bc_limit AS DOUBLE) AS total_bc_limit,
        try_cast(total_il_high_credit_limit AS DOUBLE) AS total_il_high_credit_limit,
        try_cast(mo_sin_old_rev_tl_op AS DOUBLE) AS mo_sin_old_rev_tl_op,
        try_cast(mo_sin_old_il_acct AS DOUBLE) AS mo_sin_old_il_acct,
        try_cast(mo_sin_rcnt_rev_tl_op AS DOUBLE) AS mo_sin_rcnt_rev_tl_op,
        try_cast(mo_sin_rcnt_tl AS DOUBLE) AS mo_sin_rcnt_tl,
        try_cast(mths_since_recent_bc AS DOUBLE) AS mths_since_recent_bc,
        try_cast(mths_since_recent_inq AS DOUBLE) AS mths_since_recent_inq,
        CASE WHEN nullif(trim(inq_last_6mths), '') IS NOT NULL AND try_cast(inq_last_6mths AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(total_acc), '') IS NOT NULL AND try_cast(total_acc AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(pub_rec), '') IS NOT NULL AND try_cast(pub_rec AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(collections_12_mths_ex_med), '') IS NOT NULL AND try_cast(collections_12_mths_ex_med AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(mths_since_last_delinq), '') IS NOT NULL AND try_cast(mths_since_last_delinq AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(mths_since_last_record), '') IS NOT NULL AND try_cast(mths_since_last_record AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(mths_since_last_major_derog), '') IS NOT NULL AND try_cast(mths_since_last_major_derog AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(acc_now_delinq), '') IS NOT NULL AND try_cast(acc_now_delinq AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(tot_coll_amt), '') IS NOT NULL AND try_cast(tot_coll_amt AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(tot_cur_bal), '') IS NOT NULL AND try_cast(tot_cur_bal AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(total_rev_hi_lim), '') IS NOT NULL AND try_cast(total_rev_hi_lim AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(acc_open_past_24mths), '') IS NOT NULL AND try_cast(acc_open_past_24mths AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(avg_cur_bal), '') IS NOT NULL AND try_cast(avg_cur_bal AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(bc_open_to_buy), '') IS NOT NULL AND try_cast(bc_open_to_buy AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(bc_util), '') IS NOT NULL AND try_cast(bc_util AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(mort_acc), '') IS NOT NULL AND try_cast(mort_acc AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(num_accts_ever_120_pd), '') IS NOT NULL AND try_cast(num_accts_ever_120_pd AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(num_actv_bc_tl), '') IS NOT NULL AND try_cast(num_actv_bc_tl AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(num_actv_rev_tl), '') IS NOT NULL AND try_cast(num_actv_rev_tl AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(num_bc_sats), '') IS NOT NULL AND try_cast(num_bc_sats AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(num_bc_tl), '') IS NOT NULL AND try_cast(num_bc_tl AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(num_il_tl), '') IS NOT NULL AND try_cast(num_il_tl AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(num_op_rev_tl), '') IS NOT NULL AND try_cast(num_op_rev_tl AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(num_rev_accts), '') IS NOT NULL AND try_cast(num_rev_accts AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(num_rev_tl_bal_gt_0), '') IS NOT NULL AND try_cast(num_rev_tl_bal_gt_0 AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(num_sats), '') IS NOT NULL AND try_cast(num_sats AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(num_tl_30dpd), '') IS NOT NULL AND try_cast(num_tl_30dpd AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(num_tl_90g_dpd_24m), '') IS NOT NULL AND try_cast(num_tl_90g_dpd_24m AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(num_tl_op_past_12m), '') IS NOT NULL AND try_cast(num_tl_op_past_12m AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(pct_tl_nvr_dlq), '') IS NOT NULL AND try_cast(pct_tl_nvr_dlq AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(percent_bc_gt_75), '') IS NOT NULL AND try_cast(percent_bc_gt_75 AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(tax_liens), '') IS NOT NULL AND try_cast(tax_liens AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(tot_hi_cred_lim), '') IS NOT NULL AND try_cast(tot_hi_cred_lim AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(total_bal_ex_mort), '') IS NOT NULL AND try_cast(total_bal_ex_mort AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(total_bc_limit), '') IS NOT NULL AND try_cast(total_bc_limit AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(total_il_high_credit_limit), '') IS NOT NULL AND try_cast(total_il_high_credit_limit AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(mo_sin_old_rev_tl_op), '') IS NOT NULL AND try_cast(mo_sin_old_rev_tl_op AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(mo_sin_old_il_acct), '') IS NOT NULL AND try_cast(mo_sin_old_il_acct AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(mo_sin_rcnt_rev_tl_op), '') IS NOT NULL AND try_cast(mo_sin_rcnt_rev_tl_op AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(mo_sin_rcnt_tl), '') IS NOT NULL AND try_cast(mo_sin_rcnt_tl AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(mths_since_recent_bc), '') IS NOT NULL AND try_cast(mths_since_recent_bc AS DOUBLE) IS NULL THEN 1 ELSE 0 END +
        CASE WHEN nullif(trim(mths_since_recent_inq), '') IS NOT NULL AND try_cast(mths_since_recent_inq AS DOUBLE) IS NULL THEN 1 ELSE 0 END AS source_parse_failures
    FROM read_csv(getvariable('raw_path'), header = true, all_varchar = true)
    WHERE try_strptime(issue_d, '%b-%Y')::DATE >= DATE '2011-01-01'
      AND try_strptime(issue_d, '%b-%Y')::DATE < DATE '2015-01-01'
)
SELECT clean.*,
    raw.inq_last_6mths,
    raw.total_acc,
    raw.pub_rec,
    raw.collections_12_mths_ex_med,
    raw.mths_since_last_delinq,
    raw.mths_since_last_record,
    raw.mths_since_last_major_derog,
    raw.acc_now_delinq,
    raw.tot_coll_amt,
    raw.tot_cur_bal,
    raw.total_rev_hi_lim,
    raw.acc_open_past_24mths,
    raw.avg_cur_bal,
    raw.bc_open_to_buy,
    raw.bc_util,
    raw.mort_acc,
    raw.num_accts_ever_120_pd,
    raw.num_actv_bc_tl,
    raw.num_actv_rev_tl,
    raw.num_bc_sats,
    raw.num_bc_tl,
    raw.num_il_tl,
    raw.num_op_rev_tl,
    raw.num_rev_accts,
    raw.num_rev_tl_bal_gt_0,
    raw.num_sats,
    raw.num_tl_30dpd,
    raw.num_tl_90g_dpd_24m,
    raw.num_tl_op_past_12m,
    raw.pct_tl_nvr_dlq,
    raw.percent_bc_gt_75,
    raw.tax_liens,
    raw.tot_hi_cred_lim,
    raw.total_bal_ex_mort,
    raw.total_bc_limit,
    raw.total_il_high_credit_limit,
    raw.mo_sin_old_rev_tl_op,
    raw.mo_sin_old_il_acct,
    raw.mo_sin_rcnt_rev_tl_op,
    raw.mo_sin_rcnt_tl,
    raw.mths_since_recent_bc,
    raw.mths_since_recent_inq, raw.source_parse_failures,
    loan_amnt / annual_inc AS loan_to_income,
    revol_bal / annual_inc AS revolving_balance_to_income,
    CASE WHEN dti IS NULL THEN NULL ELSE (dti > 100)::INTEGER END AS high_dti_flag,
    CASE WHEN revol_util IS NULL THEN NULL ELSE (revol_util > 100)::INTEGER END AS over_limit_flag,
    CASE WHEN issue_year <= 2013 THEN 'train' ELSE 'validation' END AS split
FROM read_parquet(getvariable('clean_path')) clean JOIN raw USING (loan_id)
WHERE term_months = 36 AND issue_year BETWEEN 2011 AND 2014 AND charged_off IN (0, 1);
