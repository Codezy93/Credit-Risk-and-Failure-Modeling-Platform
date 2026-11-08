-- Profiles do not use 2015. Removal decisions use training rows only.
SELECT split, 'loan_amnt' AS feature, count(*) AS rows, count(loan_amnt) AS nonmissing,
    count(*) - count(loan_amnt) AS missing, count(DISTINCT loan_amnt) AS distinct_nonmissing,
    100.0 * (count(*) - count(loan_amnt)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'annual_inc' AS feature, count(*) AS rows, count(annual_inc) AS nonmissing,
    count(*) - count(annual_inc) AS missing, count(DISTINCT annual_inc) AS distinct_nonmissing,
    100.0 * (count(*) - count(annual_inc)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'dti' AS feature, count(*) AS rows, count(dti) AS nonmissing,
    count(*) - count(dti) AS missing, count(DISTINCT dti) AS distinct_nonmissing,
    100.0 * (count(*) - count(dti)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'revol_util' AS feature, count(*) AS rows, count(revol_util) AS nonmissing,
    count(*) - count(revol_util) AS missing, count(DISTINCT revol_util) AS distinct_nonmissing,
    100.0 * (count(*) - count(revol_util)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'revol_bal' AS feature, count(*) AS rows, count(revol_bal) AS nonmissing,
    count(*) - count(revol_bal) AS missing, count(DISTINCT revol_bal) AS distinct_nonmissing,
    100.0 * (count(*) - count(revol_bal)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'open_acc' AS feature, count(*) AS rows, count(open_acc) AS nonmissing,
    count(*) - count(open_acc) AS missing, count(DISTINCT open_acc) AS distinct_nonmissing,
    100.0 * (count(*) - count(open_acc)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'delinq_2yrs' AS feature, count(*) AS rows, count(delinq_2yrs) AS nonmissing,
    count(*) - count(delinq_2yrs) AS missing, count(DISTINCT delinq_2yrs) AS distinct_nonmissing,
    100.0 * (count(*) - count(delinq_2yrs)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'pub_rec_bankruptcies' AS feature, count(*) AS rows, count(pub_rec_bankruptcies) AS nonmissing,
    count(*) - count(pub_rec_bankruptcies) AS missing, count(DISTINCT pub_rec_bankruptcies) AS distinct_nonmissing,
    100.0 * (count(*) - count(pub_rec_bankruptcies)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'emp_length_years' AS feature, count(*) AS rows, count(emp_length_years) AS nonmissing,
    count(*) - count(emp_length_years) AS missing, count(DISTINCT emp_length_years) AS distinct_nonmissing,
    100.0 * (count(*) - count(emp_length_years)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'fico_mid' AS feature, count(*) AS rows, count(fico_mid) AS nonmissing,
    count(*) - count(fico_mid) AS missing, count(DISTINCT fico_mid) AS distinct_nonmissing,
    100.0 * (count(*) - count(fico_mid)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'credit_history_years' AS feature, count(*) AS rows, count(credit_history_years) AS nonmissing,
    count(*) - count(credit_history_years) AS missing, count(DISTINCT credit_history_years) AS distinct_nonmissing,
    100.0 * (count(*) - count(credit_history_years)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'home_ownership' AS feature, count(*) AS rows, count(home_ownership) AS nonmissing,
    count(*) - count(home_ownership) AS missing, count(DISTINCT home_ownership) AS distinct_nonmissing,
    100.0 * (count(*) - count(home_ownership)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'purpose' AS feature, count(*) AS rows, count(purpose) AS nonmissing,
    count(*) - count(purpose) AS missing, count(DISTINCT purpose) AS distinct_nonmissing,
    100.0 * (count(*) - count(purpose)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'inq_last_6mths' AS feature, count(*) AS rows, count(inq_last_6mths) AS nonmissing,
    count(*) - count(inq_last_6mths) AS missing, count(DISTINCT inq_last_6mths) AS distinct_nonmissing,
    100.0 * (count(*) - count(inq_last_6mths)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'total_acc' AS feature, count(*) AS rows, count(total_acc) AS nonmissing,
    count(*) - count(total_acc) AS missing, count(DISTINCT total_acc) AS distinct_nonmissing,
    100.0 * (count(*) - count(total_acc)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'pub_rec' AS feature, count(*) AS rows, count(pub_rec) AS nonmissing,
    count(*) - count(pub_rec) AS missing, count(DISTINCT pub_rec) AS distinct_nonmissing,
    100.0 * (count(*) - count(pub_rec)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'collections_12_mths_ex_med' AS feature, count(*) AS rows, count(collections_12_mths_ex_med) AS nonmissing,
    count(*) - count(collections_12_mths_ex_med) AS missing, count(DISTINCT collections_12_mths_ex_med) AS distinct_nonmissing,
    100.0 * (count(*) - count(collections_12_mths_ex_med)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'mths_since_last_delinq' AS feature, count(*) AS rows, count(mths_since_last_delinq) AS nonmissing,
    count(*) - count(mths_since_last_delinq) AS missing, count(DISTINCT mths_since_last_delinq) AS distinct_nonmissing,
    100.0 * (count(*) - count(mths_since_last_delinq)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'mths_since_last_record' AS feature, count(*) AS rows, count(mths_since_last_record) AS nonmissing,
    count(*) - count(mths_since_last_record) AS missing, count(DISTINCT mths_since_last_record) AS distinct_nonmissing,
    100.0 * (count(*) - count(mths_since_last_record)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'mths_since_last_major_derog' AS feature, count(*) AS rows, count(mths_since_last_major_derog) AS nonmissing,
    count(*) - count(mths_since_last_major_derog) AS missing, count(DISTINCT mths_since_last_major_derog) AS distinct_nonmissing,
    100.0 * (count(*) - count(mths_since_last_major_derog)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'acc_now_delinq' AS feature, count(*) AS rows, count(acc_now_delinq) AS nonmissing,
    count(*) - count(acc_now_delinq) AS missing, count(DISTINCT acc_now_delinq) AS distinct_nonmissing,
    100.0 * (count(*) - count(acc_now_delinq)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'tot_coll_amt' AS feature, count(*) AS rows, count(tot_coll_amt) AS nonmissing,
    count(*) - count(tot_coll_amt) AS missing, count(DISTINCT tot_coll_amt) AS distinct_nonmissing,
    100.0 * (count(*) - count(tot_coll_amt)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'tot_cur_bal' AS feature, count(*) AS rows, count(tot_cur_bal) AS nonmissing,
    count(*) - count(tot_cur_bal) AS missing, count(DISTINCT tot_cur_bal) AS distinct_nonmissing,
    100.0 * (count(*) - count(tot_cur_bal)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'total_rev_hi_lim' AS feature, count(*) AS rows, count(total_rev_hi_lim) AS nonmissing,
    count(*) - count(total_rev_hi_lim) AS missing, count(DISTINCT total_rev_hi_lim) AS distinct_nonmissing,
    100.0 * (count(*) - count(total_rev_hi_lim)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'acc_open_past_24mths' AS feature, count(*) AS rows, count(acc_open_past_24mths) AS nonmissing,
    count(*) - count(acc_open_past_24mths) AS missing, count(DISTINCT acc_open_past_24mths) AS distinct_nonmissing,
    100.0 * (count(*) - count(acc_open_past_24mths)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'avg_cur_bal' AS feature, count(*) AS rows, count(avg_cur_bal) AS nonmissing,
    count(*) - count(avg_cur_bal) AS missing, count(DISTINCT avg_cur_bal) AS distinct_nonmissing,
    100.0 * (count(*) - count(avg_cur_bal)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'bc_open_to_buy' AS feature, count(*) AS rows, count(bc_open_to_buy) AS nonmissing,
    count(*) - count(bc_open_to_buy) AS missing, count(DISTINCT bc_open_to_buy) AS distinct_nonmissing,
    100.0 * (count(*) - count(bc_open_to_buy)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'bc_util' AS feature, count(*) AS rows, count(bc_util) AS nonmissing,
    count(*) - count(bc_util) AS missing, count(DISTINCT bc_util) AS distinct_nonmissing,
    100.0 * (count(*) - count(bc_util)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'mort_acc' AS feature, count(*) AS rows, count(mort_acc) AS nonmissing,
    count(*) - count(mort_acc) AS missing, count(DISTINCT mort_acc) AS distinct_nonmissing,
    100.0 * (count(*) - count(mort_acc)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'num_accts_ever_120_pd' AS feature, count(*) AS rows, count(num_accts_ever_120_pd) AS nonmissing,
    count(*) - count(num_accts_ever_120_pd) AS missing, count(DISTINCT num_accts_ever_120_pd) AS distinct_nonmissing,
    100.0 * (count(*) - count(num_accts_ever_120_pd)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'num_actv_bc_tl' AS feature, count(*) AS rows, count(num_actv_bc_tl) AS nonmissing,
    count(*) - count(num_actv_bc_tl) AS missing, count(DISTINCT num_actv_bc_tl) AS distinct_nonmissing,
    100.0 * (count(*) - count(num_actv_bc_tl)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'num_actv_rev_tl' AS feature, count(*) AS rows, count(num_actv_rev_tl) AS nonmissing,
    count(*) - count(num_actv_rev_tl) AS missing, count(DISTINCT num_actv_rev_tl) AS distinct_nonmissing,
    100.0 * (count(*) - count(num_actv_rev_tl)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'num_bc_sats' AS feature, count(*) AS rows, count(num_bc_sats) AS nonmissing,
    count(*) - count(num_bc_sats) AS missing, count(DISTINCT num_bc_sats) AS distinct_nonmissing,
    100.0 * (count(*) - count(num_bc_sats)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'num_bc_tl' AS feature, count(*) AS rows, count(num_bc_tl) AS nonmissing,
    count(*) - count(num_bc_tl) AS missing, count(DISTINCT num_bc_tl) AS distinct_nonmissing,
    100.0 * (count(*) - count(num_bc_tl)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'num_il_tl' AS feature, count(*) AS rows, count(num_il_tl) AS nonmissing,
    count(*) - count(num_il_tl) AS missing, count(DISTINCT num_il_tl) AS distinct_nonmissing,
    100.0 * (count(*) - count(num_il_tl)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'num_op_rev_tl' AS feature, count(*) AS rows, count(num_op_rev_tl) AS nonmissing,
    count(*) - count(num_op_rev_tl) AS missing, count(DISTINCT num_op_rev_tl) AS distinct_nonmissing,
    100.0 * (count(*) - count(num_op_rev_tl)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'num_rev_accts' AS feature, count(*) AS rows, count(num_rev_accts) AS nonmissing,
    count(*) - count(num_rev_accts) AS missing, count(DISTINCT num_rev_accts) AS distinct_nonmissing,
    100.0 * (count(*) - count(num_rev_accts)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'num_rev_tl_bal_gt_0' AS feature, count(*) AS rows, count(num_rev_tl_bal_gt_0) AS nonmissing,
    count(*) - count(num_rev_tl_bal_gt_0) AS missing, count(DISTINCT num_rev_tl_bal_gt_0) AS distinct_nonmissing,
    100.0 * (count(*) - count(num_rev_tl_bal_gt_0)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'num_sats' AS feature, count(*) AS rows, count(num_sats) AS nonmissing,
    count(*) - count(num_sats) AS missing, count(DISTINCT num_sats) AS distinct_nonmissing,
    100.0 * (count(*) - count(num_sats)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'num_tl_30dpd' AS feature, count(*) AS rows, count(num_tl_30dpd) AS nonmissing,
    count(*) - count(num_tl_30dpd) AS missing, count(DISTINCT num_tl_30dpd) AS distinct_nonmissing,
    100.0 * (count(*) - count(num_tl_30dpd)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'num_tl_90g_dpd_24m' AS feature, count(*) AS rows, count(num_tl_90g_dpd_24m) AS nonmissing,
    count(*) - count(num_tl_90g_dpd_24m) AS missing, count(DISTINCT num_tl_90g_dpd_24m) AS distinct_nonmissing,
    100.0 * (count(*) - count(num_tl_90g_dpd_24m)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'num_tl_op_past_12m' AS feature, count(*) AS rows, count(num_tl_op_past_12m) AS nonmissing,
    count(*) - count(num_tl_op_past_12m) AS missing, count(DISTINCT num_tl_op_past_12m) AS distinct_nonmissing,
    100.0 * (count(*) - count(num_tl_op_past_12m)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'pct_tl_nvr_dlq' AS feature, count(*) AS rows, count(pct_tl_nvr_dlq) AS nonmissing,
    count(*) - count(pct_tl_nvr_dlq) AS missing, count(DISTINCT pct_tl_nvr_dlq) AS distinct_nonmissing,
    100.0 * (count(*) - count(pct_tl_nvr_dlq)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'percent_bc_gt_75' AS feature, count(*) AS rows, count(percent_bc_gt_75) AS nonmissing,
    count(*) - count(percent_bc_gt_75) AS missing, count(DISTINCT percent_bc_gt_75) AS distinct_nonmissing,
    100.0 * (count(*) - count(percent_bc_gt_75)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'tax_liens' AS feature, count(*) AS rows, count(tax_liens) AS nonmissing,
    count(*) - count(tax_liens) AS missing, count(DISTINCT tax_liens) AS distinct_nonmissing,
    100.0 * (count(*) - count(tax_liens)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'tot_hi_cred_lim' AS feature, count(*) AS rows, count(tot_hi_cred_lim) AS nonmissing,
    count(*) - count(tot_hi_cred_lim) AS missing, count(DISTINCT tot_hi_cred_lim) AS distinct_nonmissing,
    100.0 * (count(*) - count(tot_hi_cred_lim)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'total_bal_ex_mort' AS feature, count(*) AS rows, count(total_bal_ex_mort) AS nonmissing,
    count(*) - count(total_bal_ex_mort) AS missing, count(DISTINCT total_bal_ex_mort) AS distinct_nonmissing,
    100.0 * (count(*) - count(total_bal_ex_mort)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'total_bc_limit' AS feature, count(*) AS rows, count(total_bc_limit) AS nonmissing,
    count(*) - count(total_bc_limit) AS missing, count(DISTINCT total_bc_limit) AS distinct_nonmissing,
    100.0 * (count(*) - count(total_bc_limit)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'total_il_high_credit_limit' AS feature, count(*) AS rows, count(total_il_high_credit_limit) AS nonmissing,
    count(*) - count(total_il_high_credit_limit) AS missing, count(DISTINCT total_il_high_credit_limit) AS distinct_nonmissing,
    100.0 * (count(*) - count(total_il_high_credit_limit)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'mo_sin_old_rev_tl_op' AS feature, count(*) AS rows, count(mo_sin_old_rev_tl_op) AS nonmissing,
    count(*) - count(mo_sin_old_rev_tl_op) AS missing, count(DISTINCT mo_sin_old_rev_tl_op) AS distinct_nonmissing,
    100.0 * (count(*) - count(mo_sin_old_rev_tl_op)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'mo_sin_old_il_acct' AS feature, count(*) AS rows, count(mo_sin_old_il_acct) AS nonmissing,
    count(*) - count(mo_sin_old_il_acct) AS missing, count(DISTINCT mo_sin_old_il_acct) AS distinct_nonmissing,
    100.0 * (count(*) - count(mo_sin_old_il_acct)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'mo_sin_rcnt_rev_tl_op' AS feature, count(*) AS rows, count(mo_sin_rcnt_rev_tl_op) AS nonmissing,
    count(*) - count(mo_sin_rcnt_rev_tl_op) AS missing, count(DISTINCT mo_sin_rcnt_rev_tl_op) AS distinct_nonmissing,
    100.0 * (count(*) - count(mo_sin_rcnt_rev_tl_op)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'mo_sin_rcnt_tl' AS feature, count(*) AS rows, count(mo_sin_rcnt_tl) AS nonmissing,
    count(*) - count(mo_sin_rcnt_tl) AS missing, count(DISTINCT mo_sin_rcnt_tl) AS distinct_nonmissing,
    100.0 * (count(*) - count(mo_sin_rcnt_tl)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'mths_since_recent_bc' AS feature, count(*) AS rows, count(mths_since_recent_bc) AS nonmissing,
    count(*) - count(mths_since_recent_bc) AS missing, count(DISTINCT mths_since_recent_bc) AS distinct_nonmissing,
    100.0 * (count(*) - count(mths_since_recent_bc)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'mths_since_recent_inq' AS feature, count(*) AS rows, count(mths_since_recent_inq) AS nonmissing,
    count(*) - count(mths_since_recent_inq) AS missing, count(DISTINCT mths_since_recent_inq) AS distinct_nonmissing,
    100.0 * (count(*) - count(mths_since_recent_inq)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'loan_to_income' AS feature, count(*) AS rows, count(loan_to_income) AS nonmissing,
    count(*) - count(loan_to_income) AS missing, count(DISTINCT loan_to_income) AS distinct_nonmissing,
    100.0 * (count(*) - count(loan_to_income)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'revolving_balance_to_income' AS feature, count(*) AS rows, count(revolving_balance_to_income) AS nonmissing,
    count(*) - count(revolving_balance_to_income) AS missing, count(DISTINCT revolving_balance_to_income) AS distinct_nonmissing,
    100.0 * (count(*) - count(revolving_balance_to_income)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'high_dti_flag' AS feature, count(*) AS rows, count(high_dti_flag) AS nonmissing,
    count(*) - count(high_dti_flag) AS missing, count(DISTINCT high_dti_flag) AS distinct_nonmissing,
    100.0 * (count(*) - count(high_dti_flag)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'over_limit_flag' AS feature, count(*) AS rows, count(over_limit_flag) AS nonmissing,
    count(*) - count(over_limit_flag) AS missing, count(DISTINCT over_limit_flag) AS distinct_nonmissing,
    100.0 * (count(*) - count(over_limit_flag)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'grade' AS feature, count(*) AS rows, count(grade) AS nonmissing,
    count(*) - count(grade) AS missing, count(DISTINCT grade) AS distinct_nonmissing,
    100.0 * (count(*) - count(grade)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'sub_grade' AS feature, count(*) AS rows, count(sub_grade) AS nonmissing,
    count(*) - count(sub_grade) AS missing, count(DISTINCT sub_grade) AS distinct_nonmissing,
    100.0 * (count(*) - count(sub_grade)) / count(*) AS missing_pct FROM auc_population GROUP BY split
UNION ALL
SELECT split, 'int_rate' AS feature, count(*) AS rows, count(int_rate) AS nonmissing,
    count(*) - count(int_rate) AS missing, count(DISTINCT int_rate) AS distinct_nonmissing,
    100.0 * (count(*) - count(int_rate)) / count(*) AS missing_pct FROM auc_population GROUP BY split
ORDER BY feature, split;
