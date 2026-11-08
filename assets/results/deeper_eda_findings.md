# Follow-up EDA findings

## Scope

All analyses use clean development loans issued through 2015. The FICO/DTI grid
uses 36-month loans issued in 2011–2014. No model training or cleaning changes were made.

## What the follow-up found

- Annual income above the development p99: 7,967 loans; above $1 million: 153.
- DTI above 100: 9 loans; exactly 999: 1. These counts overlap.
- Revolving utilization above 100%: 3,506 loans. These flags do not prove data errors, so records are retained.
- Missing employment length: 44,835 loans, with 23.65% charged off among 42,577 resolved loans. Present employment: 18.14% among 784,027 resolved loans. These are unadjusted associations.
- The FICO/DTI grid covers 320,563 loans with 100.00% ordinary outcome coverage. Its smaller population must not be confused with the full 887,440-loan development sample.
- Between 2007 and 2015, median principal changed from $6,000 to $14,000; the 60-month share changed from 0.00% to 32.75%. Borrower/loan mix is not constant over time.

## How to read the outputs

Missingness percentages are after cleaning and use each issue year's total loans.
Outcome rates use ordinary Fully Paid / Charged Off loans only. Missingness,
affordability, and interaction rate plots require at least 200 resolved loans per
displayed group; the complete CSV tables retain smaller groups. The tail comparison
suppresses flagged-group rates below 200 resolved loans. No confidence intervals
or causal estimates were calculated. The income p99 is an exploratory development
cutoff, not a future training-time preprocessing rule.

Principal-to-income and installment-to-income are distinct ratios. Installment is
post-pricing information. Neither ratio measures all living costs or total household
debt service. Missing income is shown as its own group rather than filled with zero.

No extreme values were deleted, no new predictor set was selected, and no claim
about protected-group fairness or model performance follows from these charts.

## Verification

Group totals reconcile to the development population. Tail, missingness, and
affordability outcome counts reconcile to the full development label counts.
The FICO/DTI grid reconciles independently to its narrower SQL population.
