# SHAP explanations on the validation set

Written by `src/07_explain.py`. Values are in log-odds (+0.7 roughly doubles the odds of a delay); "mean |SHAP|" is the average size of a feature's contribution over the validation rows. For every row the contributions plus the base value add up to the model's raw score (checked).

## M-A (45,993 rows, base value -1.469)

| rank | feature | group | mean_abs_shap | share |
| --- | --- | --- | --- | --- |
| 1 | hist_rate_service_hour | history | 0.371 | 20.5% |
| 2 | service | timetable | 0.271 | 15.0% |
| 3 | hist_rate_route | history | 0.252 | 14.0% |
| 4 | destination | timetable | 0.172 | 9.5% |
| 5 | weekday | timetable | 0.146 | 8.1% |
| 6 | dwell_min | timetable | 0.137 | 7.6% |
| 7 | stop_position | timetable | 0.126 | 7.0% |
| 8 | planned_hour | timetable | 0.113 | 6.3% |
| 9 | line_id | timetable | 0.084 | 4.7% |
| 10 | temperature_c | weather | 0.047 | 2.6% |
| 11 | precipitation_mm | weather | 0.023 | 1.3% |
| 12 | is_public_holiday | calendar | 0.019 | 1.0% |

Share per feature group: timetable 58.1%, history 35.8%, weather 4.3%, calendar 1.8%.

Watch features:

- `destination` (many categories; could memorise single trains): rank 4, 9.5% of the total; fine.
- `hist_n_route` (a count, not a rate; could stand in for the line or the period): rank 15, 0.3% of the total; fine.
- `stop_position` (position in the route; could stand in for the line): rank 7, 7.0% of the total; fine.

Values outside the range seen in training (the model cannot extrapolate there): 

| feature | training_min | training_max | share_outside |
| --- | --- | --- | --- |
| hist_rate_all | 0.196 | 0.349 | 34.7% |

## M-A′ (8,020 rows, base value -0.801)

| rank | feature | group | mean_abs_shap | share |
| --- | --- | --- | --- | --- |
| 1 | hist_rate_route | history | 0.447 | 19.3% |
| 2 | hist_rate_service_hour | history | 0.310 | 13.4% |
| 3 | stop_position | timetable | 0.297 | 12.8% |
| 4 | weekday | timetable | 0.220 | 9.5% |
| 5 | dwell_min | timetable | 0.181 | 7.8% |
| 6 | destination | timetable | 0.141 | 6.1% |
| 7 | temperature_c | weather | 0.128 | 5.5% |
| 8 | hist_rate_all | history | 0.128 | 5.5% |
| 9 | planned_hour | timetable | 0.098 | 4.2% |
| 10 | hist_n_route | history | 0.076 | 3.3% |
| 11 | wind_gust_kmh | weather | 0.045 | 1.9% |
| 12 | line_id | timetable | 0.045 | 1.9% |

Share per feature group: timetable 43.4%, history 41.4%, weather 12.3%, calendar 2.8%.

Watch features:

- `destination` (many categories; could memorise single trains): rank 6, 6.1% of the total; fine.
- `hist_n_route` (a count, not a rate; could stand in for the line or the period): rank 10, 3.3% of the total; fine.
- `stop_position` (position in the route; could stand in for the line): rank 3, 12.8% of the total; **look closer**.

Values outside the range seen in training (the model cannot extrapolate there): 

| feature | training_min | training_max | share_outside |
| --- | --- | --- | --- |
| hist_rate_all | 0.186 | 0.311 | 43.4% |
| temperature_c | -10.200 | 21.200 | 41.1% |

## M-B (8,020 rows, base value -0.463)

| rank | feature | group | mean_abs_shap | share |
| --- | --- | --- | --- | --- |
| 1 | prev_delay | previous stops | 2.258 | 49.5% |
| 2 | prev_delay_2 | previous stops | 0.389 | 8.5% |
| 3 | dwell_min | timetable | 0.314 | 6.9% |
| 4 | hist_rate_route | history | 0.223 | 4.9% |
| 5 | prev_minutes_to_departure | previous stops | 0.201 | 4.4% |
| 6 | hist_rate_all | history | 0.201 | 4.4% |
| 7 | weekday | timetable | 0.175 | 3.8% |
| 8 | temperature_c | weather | 0.168 | 3.7% |
| 9 | destination | timetable | 0.165 | 3.6% |
| 10 | hist_rate_service_hour | history | 0.080 | 1.7% |
| 11 | hist_n_route | history | 0.058 | 1.3% |
| 12 | planned_hour | timetable | 0.057 | 1.2% |

Share per feature group: previous stops 62.6%, timetable 17.7%, history 12.3%, weather 6.4%, calendar 1.0%.

Watch features:

- `destination` (many categories; could memorise single trains): rank 9, 3.6% of the total; fine.
- `hist_n_route` (a count, not a rate; could stand in for the line or the period): rank 11, 1.3% of the total; fine.
- `stop_position` (position in the route; could stand in for the line): rank 16, 0.7% of the total; fine.

Values outside the range seen in training (the model cannot extrapolate there): 

| feature | training_min | training_max | share_outside |
| --- | --- | --- | --- |
| hist_rate_all | 0.186 | 0.311 | 43.4% |
| temperature_c | -10.200 | 21.200 | 41.1% |

## M-A inside one service (mean |SHAP|, top 5 without `service`)

- **regional** (29,345 rows; `service` itself contributes -0.21 on average): `hist_rate_service_hour` 0.364, `hist_rate_route` 0.227, `destination` 0.205, `weekday` 0.135, `dwell_min` 0.127
- **long-distance** (15,248 rows; `service` itself contributes +0.37 on average): `hist_rate_service_hour` 0.339, `hist_rate_route` 0.279, `weekday` 0.168, `stop_position` 0.159, `dwell_min` 0.143

## M-B: effect of the previous-stop delay

| bin | rows | mean_shap |
| --- | --- | --- |
| 0 or early | 2147 | -2.003 |
| 1–2 | 1831 | -1.728 |
| 3–5 | 1008 | -1.340 |
| 6–9 | 725 | -0.413 |
| 10–19 | 908 | 2.669 |
| 20+ | 1401 | 4.594 |

Figures: `reports/figures/shap_importance_validation.png`, `reports/figures/shap_dependence_validation.png`.
