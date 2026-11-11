# Validation results (baselines)

Written by `src/05_train.py`. Intervals: 1000 bootstrap resamples of whole days. Thresholds maximise F1 on validation unless stated (B0 has a constant score and keeps 0.5). The test period is not used.

## Scenario A: all departures

B0–B2 are fitted on the scenario A training split (152,384 departures on 549 days, 25.7% delayed) and scored on its validation split (45,993 departures on 181 days, 22.0% delayed). B2 uses timetable and calendar columns (`service`, `line_id`, `planned_hour`, `weekday`, `is_through`, `is_public_holiday`, `is_school_holiday`, `is_bridge_day`).

| Model | PR-AUC [95% CI] | ROC-AUC [95% CI] | Threshold | F1 | Precision | Recall | Accuracy | F1 at 0.5 | Brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 majority | 0.220 [0.209, 0.231] | 0.500 [0.500, 0.500] | 0.500 | 0.000 | 0.000 | 0.000 | 0.780 | 0.000 | 0.1729 |
| B1 service x hour | 0.513 [0.493, 0.533] | 0.785 [0.777, 0.793] | 0.281 | 0.570 | 0.473 | 0.716 | 0.762 | 0.532 | 0.1364 |
| B2 logistic regression | 0.535 [0.515, 0.557] | 0.800 [0.792, 0.809] | 0.326 | 0.572 | 0.473 | 0.724 | 0.762 | 0.525 | 0.1343 |

Paired differences (same day resamples):

| Comparison | Metric | Difference [95% CI] | Interval above zero |
| --- | --- | --- | --- |
| B1 service x hour − B0 majority | pr_auc | +0.293 [+0.280, +0.307] | yes |
| B1 service x hour − B0 majority | roc_auc | +0.285 [+0.277, +0.293] | yes |
| B2 logistic regression − B1 service x hour | pr_auc | +0.022 [+0.014, +0.030] | yes |
| B2 logistic regression − B1 service x hour | roc_auc | +0.015 [+0.012, +0.019] | yes |

## Scenario B rows: through trains with an earlier stop

Validation split of scenario B (8,020 departures on 61 days, 35.0% delayed). B1 and B2 are the scenario A models above, scored on these rows. B3 is the persistence rule of D17: its score is the delay in minutes at the previous stop, its class rule is "6 or more minutes late at the previous stop" (a fixed rule, nothing is fitted or tuned; it has no probability, hence no Brier score).

| Model | PR-AUC [95% CI] | ROC-AUC [95% CI] | Threshold | F1 | Precision | Recall | Accuracy | F1 at 0.5 | Brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B1 service x hour | 0.549 [0.512, 0.585] | 0.729 [0.714, 0.744] | 0.334 | 0.617 | 0.482 | 0.855 | 0.629 | 0.576 | 0.1956 |
| B2 logistic regression | 0.564 [0.530, 0.598] | 0.734 [0.716, 0.752] | 0.316 | 0.616 | 0.471 | 0.889 | 0.612 | 0.564 | 0.1936 |
| B3 previous-stop delay | 0.877 [0.857, 0.893] | 0.909 [0.900, 0.918] | 6 min (rule) | 0.806 | 0.775 | 0.839 | 0.859 | – | – |

Paired differences (same day resamples):

| Comparison | Metric | Difference [95% CI] | Interval above zero |
| --- | --- | --- | --- |
| B3 previous-stop delay − B2 logistic regression | pr_auc | +0.312 [+0.287, +0.338] | yes |
| B3 previous-stop delay − B2 logistic regression | roc_auc | +0.175 [+0.157, +0.192] | yes |
