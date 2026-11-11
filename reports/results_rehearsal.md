# Rehearsal of the final run

Written by `src/05_train.py` --rehearsal. Scored period: validation (rehearsal of the final run). Intervals: 1000 bootstrap resamples of whole days. Settings, tree counts and thresholds come from training-only models on the validation rows; all models are then refitted on training + validation and scored on the period below, which played no part in any choice. **This is a rehearsal of the final run: the test period is not used.** The periods are those of `REHEARSAL_SPLITS` in `src/config.py`.

## Scenario A: all departures

Models are fitted on training + validation (152,384 departures on 549 days, 25.7% delayed) and scored on 45,993 departures on 181 days, 22.0% delayed. B2 uses timetable and calendar columns (`service`, `line_id`, `planned_hour`, `weekday`, `is_through`, `is_public_holiday`, `is_school_holiday`, `is_bridge_day`); M-A uses the 21 scenario A features.

| Model | PR-AUC [95% CI] | ROC-AUC [95% CI] | Threshold | F1 | Precision | Recall | Accuracy | F1 at 0.5 | Brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 majority | 0.220 [0.209, 0.231] | 0.500 [0.500, 0.500] | 0.500 | 0.000 | 0.000 | 0.000 | 0.780 | 0.000 | 0.1729 |
| B1 service x hour | 0.513 [0.493, 0.533] | 0.785 [0.777, 0.793] | 0.364 | 0.561 | 0.494 | 0.649 | 0.776 | 0.532 | 0.1364 |
| B2 logistic regression | 0.535 [0.515, 0.557] | 0.800 [0.792, 0.809] | 0.355 | 0.570 | 0.482 | 0.699 | 0.768 | 0.525 | 0.1343 |
| M-A LightGBM | 0.597 [0.578, 0.616] | 0.822 [0.814, 0.830] | 0.306 | 0.591 | 0.535 | 0.660 | 0.799 | 0.418 | 0.1262 |

Paired differences (same day resamples):

| Comparison | Metric | Difference [95% CI] | Interval above zero |
| --- | --- | --- | --- |
| B1 service x hour − B0 majority | pr_auc | +0.293 [+0.280, +0.307] | yes |
| B1 service x hour − B0 majority | roc_auc | +0.285 [+0.277, +0.293] | yes |
| B2 logistic regression − B1 service x hour | pr_auc | +0.022 [+0.014, +0.030] | yes |
| B2 logistic regression − B1 service x hour | roc_auc | +0.015 [+0.012, +0.019] | yes |
| M-A LightGBM − B2 logistic regression | pr_auc | +0.062 [+0.053, +0.071] | yes |
| M-A LightGBM − B2 logistic regression | roc_auc | +0.022 [+0.018, +0.025] | yes |

## Scenario B rows: through trains with an earlier stop

Scored on 8,020 departures on 61 days, 35.0% delayed. B1, B2 and M-A are the scenario A models above, scored on these rows. M-A′ and M-B are fitted on training + validation of scenario B (23,926 departures on 179 days, 36.4% delayed). B3 is the persistence rule of D17: its score is the delay in minutes at the previous stop, its class rule is "6 or more minutes late at the previous stop" (nothing is fitted or tuned; it has no probability, hence no Brier score).

| Model | PR-AUC [95% CI] | ROC-AUC [95% CI] | Threshold | F1 | Precision | Recall | Accuracy | F1 at 0.5 | Brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B1 service x hour | 0.549 [0.512, 0.585] | 0.729 [0.714, 0.744] | 0.364 | 0.608 | 0.491 | 0.798 | 0.640 | 0.576 | 0.1956 |
| B2 logistic regression | 0.564 [0.530, 0.598] | 0.734 [0.716, 0.752] | 0.399 | 0.613 | 0.495 | 0.806 | 0.645 | 0.564 | 0.1936 |
| B3 previous-stop delay | 0.877 [0.857, 0.893] | 0.909 [0.900, 0.918] | 6 min (rule) | 0.806 | 0.775 | 0.839 | 0.859 | – | – |
| M-A LightGBM (A training period) | 0.643 [0.608, 0.676] | 0.786 [0.771, 0.803] | 0.317 | 0.645 | 0.543 | 0.792 | 0.695 | 0.486 | 0.1772 |
| M-A′ LightGBM (A features, B period) | 0.641 [0.608, 0.673] | 0.784 [0.766, 0.800] | 0.392 | 0.625 | 0.624 | 0.626 | 0.737 | 0.560 | 0.1771 |
| M-B LightGBM (with earlier stops) | 0.929 [0.916, 0.939] | 0.939 [0.931, 0.947] | 0.402 | 0.847 | 0.864 | 0.829 | 0.895 | 0.849 | 0.0768 |

Paired differences (same day resamples): M-A′ − M-A is the effect of the training period, M-B − M-A′ the effect of the earlier-stop features, M-B − B3 the gain over the simple rule.

| Comparison | Metric | Difference [95% CI] | Interval above zero |
| --- | --- | --- | --- |
| B3 previous-stop delay − B2 logistic regression | pr_auc | +0.312 [+0.287, +0.338] | yes |
| B3 previous-stop delay − B2 logistic regression | roc_auc | +0.175 [+0.157, +0.192] | yes |
| M-A′ LightGBM (A features, B period) − M-A LightGBM (A training period) | pr_auc | -0.002 [-0.017, +0.013] | no |
| M-A′ LightGBM (A features, B period) − M-A LightGBM (A training period) | roc_auc | -0.003 [-0.015, +0.008] | no |
| M-B LightGBM (with earlier stops) − M-A′ LightGBM (A features, B period) | pr_auc | +0.287 [+0.263, +0.312] | yes |
| M-B LightGBM (with earlier stops) − M-A′ LightGBM (A features, B period) | roc_auc | +0.156 [+0.142, +0.171] | yes |
| M-B LightGBM (with earlier stops) − B3 previous-stop delay | pr_auc | +0.052 [+0.042, +0.063] | yes |
| M-B LightGBM (with earlier stops) − B3 previous-stop delay | roc_auc | +0.030 [+0.025, +0.036] | yes |

## Sensitivity checks (scenario A)

The same models scored once more with rows that the main evaluation excludes (D9, D18). These rows are never used for fitting. A cancelled departure counts as delayed here.

| Rows | n | Delayed | PR-AUC B2 | ROC-AUC B2 | PR-AUC M-A | ROC-AUC M-A |
| --- | --- | --- | --- | --- | --- | --- |
| Main evaluation rows | 45,993 | 22.0% | 0.535 | 0.800 | 0.597 | 0.822 |
| + cancelled departures counted as delayed (D9) | 47,002 | 23.7% | 0.542 | 0.789 | 0.601 | 0.810 |
| + departures without timetable record (D18) | 48,419 | 23.2% | 0.536 | 0.797 | 0.600 | 0.820 |

## Chosen settings

Grid of 12 settings fixed in advance (`src/models.py`, D21). Learning rate 0.05, early stopping after 50 rounds without improvement of the validation log loss, no class weights. Trees = number found with the training-only model, kept unchanged in the refit (D21).

| Model | Fitted on | Features | Trees | Setting |
| --- | --- | --- | --- | --- |
| M-A | 152,384 rows | 21 | 125 | num_leaves=31, min_child_samples=100, colsample_bytree=0.7, reg_lambda=5.0 |
| M-A′ | 23,926 rows | 21 | 48 | num_leaves=15, min_child_samples=100, colsample_bytree=0.7, reg_lambda=5.0 |
| M-B | 23,926 rows | 25 | 339 | num_leaves=7, min_child_samples=50 |
