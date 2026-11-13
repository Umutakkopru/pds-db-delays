# Final results (test period)

Written by `src/05_train.py` --final. Scored period: test. Intervals: 1000 bootstrap resamples of whole days. Settings, tree counts and thresholds come from training-only models on the validation rows; all models are then refitted on training + validation and scored on the period below, which played no part in any choice. **This is the single final run on the test period.** Nothing was changed afterwards.

## Scenario A: all departures

Models are fitted on training + validation (198,377 departures on 730 days, 24.8% delayed) and scored on 31,956 departures on 123 days, 23.0% delayed. B2 uses timetable and calendar columns (`service`, `line_id`, `planned_hour`, `weekday`, `is_through`, `is_public_holiday`, `is_school_holiday`, `is_bridge_day`); M-A uses the 21 scenario A features.

| Model | PR-AUC [95% CI] | ROC-AUC [95% CI] | Threshold | F1 | Precision | Recall | Accuracy | F1 at 0.5 | Brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 majority | 0.230 [0.219, 0.242] | 0.500 [0.500, 0.500] | 0.500 | 0.000 | 0.000 | 0.000 | 0.770 | 0.000 | 0.1774 |
| B1 service x hour | 0.523 [0.502, 0.544] | 0.792 [0.782, 0.801] | 0.281 | 0.602 | 0.516 | 0.722 | 0.780 | 0.493 | 0.1366 |
| B2 logistic regression | 0.545 [0.522, 0.566] | 0.807 [0.798, 0.815] | 0.326 | 0.604 | 0.516 | 0.729 | 0.780 | 0.503 | 0.1338 |
| M-A LightGBM | 0.629 [0.610, 0.648] | 0.833 [0.825, 0.842] | 0.289 | 0.616 | 0.540 | 0.718 | 0.794 | 0.575 | 0.1239 |

Paired differences (same day resamples):

| Comparison | Metric | Difference [95% CI] | Interval above zero |
| --- | --- | --- | --- |
| B1 service x hour − B0 majority | pr_auc | +0.293 [+0.278, +0.308] | yes |
| B1 service x hour − B0 majority | roc_auc | +0.292 [+0.282, +0.301] | yes |
| B2 logistic regression − B1 service x hour | pr_auc | +0.022 [+0.011, +0.032] | yes |
| B2 logistic regression − B1 service x hour | roc_auc | +0.015 [+0.010, +0.020] | yes |
| M-A LightGBM − B2 logistic regression | pr_auc | +0.084 [+0.072, +0.097] | yes |
| M-A LightGBM − B2 logistic regression | roc_auc | +0.026 [+0.023, +0.030] | yes |

## Scenario B rows: through trains with an earlier stop

Scored on 15,898 departures on 123 days, 37.6% delayed. B1, B2 and M-A are the scenario A models above, scored on these rows. M-A′ and M-B are fitted on training + validation of scenario B (31,946 departures on 240 days, 36.0% delayed). B3 is the persistence rule of D17: its score is the delay in minutes at the previous stop, its class rule is "6 or more minutes late at the previous stop" (nothing is fitted or tuned; it has no probability, hence no Brier score).

| Model | PR-AUC [95% CI] | ROC-AUC [95% CI] | Threshold | F1 | Precision | Recall | Accuracy | F1 at 0.5 | Brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B1 service x hour | 0.573 [0.549, 0.596] | 0.726 [0.715, 0.736] | 0.334 | 0.634 | 0.520 | 0.814 | 0.647 | 0.548 | 0.1970 |
| B2 logistic regression | 0.593 [0.568, 0.615] | 0.743 [0.731, 0.752] | 0.316 | 0.654 | 0.515 | 0.895 | 0.643 | 0.561 | 0.1925 |
| B3 previous-stop delay | 0.885 [0.873, 0.896] | 0.910 [0.902, 0.917] | 6 min (rule) | 0.811 | 0.775 | 0.849 | 0.851 | – | – |
| M-A LightGBM (A training period) | 0.692 [0.673, 0.713] | 0.803 [0.792, 0.813] | 0.335 | 0.675 | 0.570 | 0.829 | 0.700 | 0.642 | 0.1736 |
| M-A′ LightGBM (A features, B period) | 0.690 [0.668, 0.711] | 0.801 [0.790, 0.811] | 0.337 | 0.677 | 0.594 | 0.787 | 0.718 | 0.641 | 0.1742 |
| M-B LightGBM (with earlier stops) | 0.935 [0.928, 0.942] | 0.942 [0.936, 0.947] | 0.428 | 0.852 | 0.903 | 0.807 | 0.894 | 0.850 | 0.0790 |

Paired differences (same day resamples): M-A′ − M-A is the effect of the training period, M-B − M-A′ the effect of the earlier-stop features, M-B − B3 the gain over the simple rule.

| Comparison | Metric | Difference [95% CI] | Interval above zero |
| --- | --- | --- | --- |
| B3 previous-stop delay − B2 logistic regression | pr_auc | +0.292 [+0.274, +0.312] | yes |
| B3 previous-stop delay − B2 logistic regression | roc_auc | +0.168 [+0.158, +0.178] | yes |
| M-A′ LightGBM (A features, B period) − M-A LightGBM (A training period) | pr_auc | -0.002 [-0.009, +0.004] | no |
| M-A′ LightGBM (A features, B period) − M-A LightGBM (A training period) | roc_auc | -0.002 [-0.005, +0.001] | no |
| M-B LightGBM (with earlier stops) − M-A′ LightGBM (A features, B period) | pr_auc | +0.245 [+0.228, +0.263] | yes |
| M-B LightGBM (with earlier stops) − M-A′ LightGBM (A features, B period) | roc_auc | +0.141 [+0.133, +0.150] | yes |
| M-B LightGBM (with earlier stops) − B3 previous-stop delay | pr_auc | +0.051 [+0.045, +0.057] | yes |
| M-B LightGBM (with earlier stops) − B3 previous-stop delay | roc_auc | +0.032 [+0.028, +0.035] | yes |

## M-A: operating points per service

The overall threshold maximises F1 over all departures; with it, M-A flags almost no regional train, because regional trains are delayed far less often than long-distance trains. This table shows in addition what a threshold per service gives (chosen inside each service on the validation rows; services with fewer than 300 validation rows keep the overall threshold of 0.289), and how often the departures with the highest scores are delayed. P / R / F1 = precision / recall / F1. The thresholds were fixed before these rows were scored.

| Service | Rows | Delayed | Overall threshold: P / R / F1 | Own threshold | Own threshold: P / R / F1 | Delayed in top 5% | Delayed in top 10% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| long_distance | 10,410 | 48.0% | 0.526 / 0.937 / 0.674 | 0.335 | 0.555 / 0.884 / 0.682 | 81.3% | 78.1% |
| night | 766 | 72.7% | 0.727 / 1.000 / 0.842 | 0.347 | 0.733 / 0.995 / 0.844 | 89.5% | 94.8% |
| other | 29 | 41.4% | 0.429 / 1.000 / 0.600 | 0.289 | 0.429 / 1.000 / 0.600 | – | – |
| regional | 20,751 | 8.6% | 0.297 / 0.015 / 0.029 | 0.120 | 0.156 / 0.416 / 0.226 | 23.7% | 19.0% |
| All departures | 31,956 | 23.0% | 0.540 / 0.718 / 0.616 | per service | 0.424 / 0.779 / 0.549 | 79.2% | 73.6% |

## Sensitivity checks (scenario A)

The same models scored once more with rows that the main evaluation excludes (D9, D18). These rows are never used for fitting. A cancelled departure counts as delayed here.

| Rows | n | Delayed | PR-AUC B2 | ROC-AUC B2 | PR-AUC M-A | ROC-AUC M-A |
| --- | --- | --- | --- | --- | --- | --- |
| Main evaluation rows | 31,956 | 23.0% | 0.545 | 0.807 | 0.629 | 0.833 |
| + cancelled departures counted as delayed (D9) | 32,524 | 24.3% | 0.550 | 0.796 | 0.631 | 0.823 |
| + departures without timetable record (D18) | 34,105 | 25.0% | 0.564 | 0.809 | 0.645 | 0.836 |

## Chosen settings

Grid of 12 settings fixed in advance (`src/models.py`, D21). Learning rate 0.05, early stopping after 50 rounds without improvement of the validation log loss, no class weights. Trees = number found with the training-only model, kept unchanged in the refit (D21).

| Model | Fitted on | Features | Trees | Setting |
| --- | --- | --- | --- | --- |
| M-A | 198,377 rows | 21 | 226 | num_leaves=7, min_child_samples=50 |
| M-A′ | 31,946 rows | 21 | 296 | num_leaves=7, min_child_samples=50 |
| M-B | 31,946 rows | 25 | 182 | num_leaves=31, min_child_samples=100, colsample_bytree=0.7, reg_lambda=5.0 |
