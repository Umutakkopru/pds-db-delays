# Validation results (scenario A baselines)

Written by `src/05_train.py`. Models are fitted on the scenario A training split (152,384 departures, 25.7% delayed) and scored on the validation split (45,993 departures on 181 days, 22.0% delayed). Intervals: 1000 bootstrap resamples of whole days. The threshold maximises F1 on validation (B0 has a constant score and keeps 0.5). The test period is not used.

B2 uses only timetable columns so far (`service`, `line_id`, `planned_hour`, `weekday`, `is_through`); holidays follow with step 03.

| Model | PR-AUC [95% CI] | ROC-AUC [95% CI] | Threshold | F1 | Precision | Recall | F1 at 0.5 | Accuracy at 0.5 | Brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 majority | 0.220 [0.209, 0.231] | 0.500 [0.500, 0.500] | 0.500 | 0.000 | 0.000 | 0.000 | 0.000 | 0.780 | 0.1729 |
| B1 service x hour | 0.513 [0.493, 0.533] | 0.785 [0.777, 0.793] | 0.281 | 0.570 | 0.473 | 0.716 | 0.532 | 0.791 | 0.1364 |
| B2 logistic regression | 0.528 [0.507, 0.550] | 0.797 [0.789, 0.806] | 0.320 | 0.571 | 0.470 | 0.728 | 0.523 | 0.795 | 0.1349 |

## Paired differences (same day resamples)

| Comparison | Metric | Difference [95% CI] | Interval above zero |
| --- | --- | --- | --- |
| B1 service x hour − B0 majority | pr_auc | +0.293 [+0.280, +0.307] | yes |
| B1 service x hour − B0 majority | roc_auc | +0.285 [+0.277, +0.293] | yes |
| B2 logistic regression − B1 service x hour | pr_auc | +0.015 [+0.007, +0.024] | yes |
| B2 logistic regression − B1 service x hour | roc_auc | +0.013 [+0.009, +0.017] | yes |
