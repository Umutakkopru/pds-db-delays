# Validation results

Written by `src/05_train.py`. Scored period: validation. Intervals: 1000 bootstrap resamples of whole days. Thresholds maximise F1 on validation unless stated (B0 has a constant score and keeps 0.5). **The test period is not used.** Validation scores of the LightGBM models are optimistic: the same validation rows stop the training early, choose the setting and choose the threshold. The unbiased comparison is the single final run on the test period.

## Scenario A: all departures

Models are fitted on the scenario A training split (152,384 departures on 549 days, 25.7% delayed) and scored on 45,993 departures on 181 days, 22.0% delayed. B2 uses timetable and calendar columns (`service`, `line_id`, `planned_hour`, `weekday`, `is_through`, `is_public_holiday`, `is_school_holiday`, `is_bridge_day`); M-A uses the 21 scenario A features.

| Model | PR-AUC [95% CI] | ROC-AUC [95% CI] | Threshold | F1 | Precision | Recall | Accuracy | F1 at 0.5 | Brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 majority | 0.220 [0.209, 0.231] | 0.500 [0.500, 0.500] | 0.500 | 0.000 | 0.000 | 0.000 | 0.780 | 0.000 | 0.1729 |
| B1 service x hour | 0.513 [0.493, 0.533] | 0.785 [0.777, 0.793] | 0.281 | 0.570 | 0.473 | 0.716 | 0.762 | 0.532 | 0.1364 |
| B2 logistic regression | 0.535 [0.515, 0.557] | 0.800 [0.792, 0.809] | 0.326 | 0.572 | 0.473 | 0.724 | 0.762 | 0.525 | 0.1343 |
| M-A LightGBM | 0.603 [0.583, 0.622] | 0.822 [0.814, 0.830] | 0.289 | 0.591 | 0.532 | 0.666 | 0.798 | 0.435 | 0.1260 |
| M-A without weather | 0.597 [0.577, 0.616] | 0.819 [0.811, 0.827] | 0.267 | 0.588 | 0.513 | 0.689 | 0.788 | 0.415 | 0.1270 |

Paired differences (same day resamples):

| Comparison | Metric | Difference [95% CI] | Interval above zero |
| --- | --- | --- | --- |
| B1 service x hour − B0 majority | pr_auc | +0.293 [+0.280, +0.307] | yes |
| B1 service x hour − B0 majority | roc_auc | +0.285 [+0.277, +0.293] | yes |
| B2 logistic regression − B1 service x hour | pr_auc | +0.022 [+0.014, +0.030] | yes |
| B2 logistic regression − B1 service x hour | roc_auc | +0.015 [+0.012, +0.019] | yes |
| M-A LightGBM − B2 logistic regression | pr_auc | +0.068 [+0.059, +0.077] | yes |
| M-A LightGBM − B2 logistic regression | roc_auc | +0.021 [+0.018, +0.025] | yes |
| M-A LightGBM − M-A without weather | pr_auc | +0.006 [+0.002, +0.010] | yes |
| M-A LightGBM − M-A without weather | roc_auc | +0.003 [+0.001, +0.005] | yes |

## Scenario B rows: through trains with an earlier stop

Scored on 8,020 departures on 61 days, 35.0% delayed. B1, B2 and M-A are the scenario A models above, scored on these rows. M-A′ and M-B are fitted on the scenario B training split (23,926 departures on 179 days, 36.4% delayed). B3 is the persistence rule of D17: its score is the delay in minutes at the previous stop, its class rule is "6 or more minutes late at the previous stop" (nothing is fitted or tuned; it has no probability, hence no Brier score).

| Model | PR-AUC [95% CI] | ROC-AUC [95% CI] | Threshold | F1 | Precision | Recall | Accuracy | F1 at 0.5 | Brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B1 service x hour | 0.549 [0.512, 0.585] | 0.729 [0.714, 0.744] | 0.334 | 0.617 | 0.482 | 0.855 | 0.629 | 0.576 | 0.1956 |
| B2 logistic regression | 0.564 [0.530, 0.598] | 0.734 [0.716, 0.752] | 0.316 | 0.616 | 0.471 | 0.889 | 0.612 | 0.564 | 0.1936 |
| B3 previous-stop delay | 0.877 [0.857, 0.893] | 0.909 [0.900, 0.918] | 6 min (rule) | 0.806 | 0.775 | 0.839 | 0.859 | – | – |
| M-A LightGBM (A training period) | 0.651 [0.615, 0.683] | 0.789 [0.774, 0.805] | 0.335 | 0.649 | 0.583 | 0.733 | 0.723 | 0.485 | 0.1769 |
| M-A′ LightGBM (A features, B period) | 0.664 [0.632, 0.694] | 0.794 [0.778, 0.810] | 0.337 | 0.655 | 0.585 | 0.744 | 0.726 | 0.596 | 0.1724 |
| M-B LightGBM (with earlier stops) | 0.931 [0.919, 0.941] | 0.942 [0.933, 0.949] | 0.428 | 0.853 | 0.893 | 0.817 | 0.902 | 0.851 | 0.0749 |
| M-A′ without weather | 0.646 [0.612, 0.677] | 0.785 [0.767, 0.803] | 0.310 | 0.647 | 0.575 | 0.740 | 0.718 | 0.567 | 0.1763 |
| M-B without weather | 0.930 [0.918, 0.941] | 0.940 [0.932, 0.948] | 0.397 | 0.851 | 0.885 | 0.819 | 0.900 | 0.850 | 0.0755 |

Paired differences (same day resamples): M-A′ − M-A is the effect of the training period, M-B − M-A′ the effect of the earlier-stop features, M-B − B3 the gain over the simple rule.

| Comparison | Metric | Difference [95% CI] | Interval above zero |
| --- | --- | --- | --- |
| B3 previous-stop delay − B2 logistic regression | pr_auc | +0.312 [+0.287, +0.338] | yes |
| B3 previous-stop delay − B2 logistic regression | roc_auc | +0.175 [+0.157, +0.192] | yes |
| M-A′ LightGBM (A features, B period) − M-A LightGBM (A training period) | pr_auc | +0.013 [+0.001, +0.025] | yes |
| M-A′ LightGBM (A features, B period) − M-A LightGBM (A training period) | roc_auc | +0.005 [-0.004, +0.013] | no |
| M-B LightGBM (with earlier stops) − M-A′ LightGBM (A features, B period) | pr_auc | +0.267 [+0.244, +0.292] | yes |
| M-B LightGBM (with earlier stops) − M-A′ LightGBM (A features, B period) | roc_auc | +0.148 [+0.135, +0.161] | yes |
| M-B LightGBM (with earlier stops) − B3 previous-stop delay | pr_auc | +0.055 [+0.045, +0.066] | yes |
| M-B LightGBM (with earlier stops) − B3 previous-stop delay | roc_auc | +0.032 [+0.027, +0.038] | yes |
| M-A′ LightGBM (A features, B period) − M-A′ without weather | pr_auc | +0.019 [+0.012, +0.025] | yes |
| M-A′ LightGBM (A features, B period) − M-A′ without weather | roc_auc | +0.009 [+0.004, +0.014] | yes |
| M-B LightGBM (with earlier stops) − M-B without weather | pr_auc | +0.001 [-0.000, +0.002] | no |
| M-B LightGBM (with earlier stops) − M-B without weather | roc_auc | +0.001 [-0.000, +0.003] | no |

## M-A: operating points per service

The overall threshold maximises F1 over all departures; with it, M-A flags almost no regional train, because regional trains are delayed far less often than long-distance trains. This table shows in addition what a threshold per service gives (chosen inside each service on the validation rows; services with fewer than 300 validation rows keep the overall threshold of 0.289), and how often the departures with the highest scores are delayed. P / R / F1 = precision / recall / F1. In this mode the thresholds are chosen on the scored rows themselves, so the numbers are optimistic.

| Service | Rows | Delayed | Overall threshold: P / R / F1 | Own threshold | Own threshold: P / R / F1 | Delayed in top 5% | Delayed in top 10% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| long_distance | 15,248 | 43.7% | 0.509 / 0.874 / 0.643 | 0.335 | 0.554 / 0.780 / 0.648 | 76.2% | 71.7% |
| night | 1,384 | 67.7% | 0.757 / 0.958 / 0.846 | 0.347 | 0.778 / 0.947 / 0.854 | 100.0% | 98.6% |
| other | 16 | 50.0% | 0.467 / 0.875 / 0.609 | 0.289 | 0.467 / 0.875 / 0.609 | – | – |
| regional | 29,345 | 8.6% | 0.393 / 0.004 / 0.009 | 0.120 | 0.171 / 0.375 / 0.235 | 22.6% | 19.4% |
| All departures | 45,993 | 22.0% | 0.532 / 0.666 / 0.591 | per service | 0.438 / 0.695 / 0.538 | 76.8% | 69.6% |

## Sensitivity checks (scenario A)

The same models scored once more with rows that the main evaluation excludes (D9, D18). These rows are never used for fitting. A cancelled departure counts as delayed here.

| Rows | n | Delayed | PR-AUC B2 | ROC-AUC B2 | PR-AUC M-A | ROC-AUC M-A |
| --- | --- | --- | --- | --- | --- | --- |
| Main evaluation rows | 45,993 | 22.0% | 0.535 | 0.800 | 0.603 | 0.822 |
| + cancelled departures counted as delayed (D9) | 47,002 | 23.7% | 0.542 | 0.789 | 0.607 | 0.811 |
| + departures without timetable record (D18) | 48,419 | 23.2% | 0.536 | 0.797 | 0.606 | 0.820 |

## Chosen settings

Grid of 12 settings fixed in advance (`src/models.py`, D21). Learning rate 0.05, early stopping after 50 rounds without improvement of the validation log loss, no class weights. Trees = number found with the training-only model; all settings per model are in `reports/checks/tuning_*.csv`.

| Model | Fitted on | Features | Trees | Setting |
| --- | --- | --- | --- | --- |
| M-A | 152,384 rows | 21 | 226 | num_leaves=7, min_child_samples=50 |
| M-A′ | 23,926 rows | 21 | 296 | num_leaves=7, min_child_samples=50 |
| M-B | 23,926 rows | 25 | 182 | num_leaves=31, min_child_samples=100, colsample_bytree=0.7, reg_lambda=5.0 |

## Sanity checks

- Scenario A ROC-AUC of M-A on validation: 0.822 (alarm limit 0.95).
- M-A's setting fitted on shuffled training labels, 5 shuffles, no early stopping: validation ROC-AUC mean 0.477, range 0.443–0.506 (expected about 0.5).
