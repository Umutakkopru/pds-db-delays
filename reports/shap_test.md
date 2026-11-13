# SHAP explanations on the test set

Written by `src/07_explain.py`. Values are in log-odds (+0.7 roughly doubles the odds of a delay); "mean |SHAP|" is the average size of a feature's contribution over the test rows. For every row the contributions plus the base value add up to the model's raw score (checked).

## M-A (31,956 rows, base value -1.514)

| rank | feature | group | mean_abs_shap | share |
| --- | --- | --- | --- | --- |
| 1 | hist_rate_service_hour | history | 0.377 | 20.1% |
| 2 | hist_rate_route | history | 0.319 | 17.0% |
| 3 | dwell_min | timetable | 0.192 | 10.3% |
| 4 | stop_position | timetable | 0.165 | 8.8% |
| 5 | weekday | timetable | 0.156 | 8.3% |
| 6 | service | timetable | 0.153 | 8.2% |
| 7 | destination | timetable | 0.146 | 7.8% |
| 8 | planned_hour | timetable | 0.110 | 5.9% |
| 9 | line_id | timetable | 0.097 | 5.2% |
| 10 | temperature_c | weather | 0.083 | 4.4% |
| 11 | is_school_holiday | calendar | 0.018 | 1.0% |
| 12 | precipitation_mm | weather | 0.018 | 1.0% |

Share per feature group: timetable 54.4%, history 38.0%, weather 5.8%, calendar 1.8%.

Watch features:

- `destination` (many categories; could memorise single trains): rank 7, 7.8% of the total; fine.
- `hist_n_route` (a count, not a rate; could stand in for the line or the period): rank 18, 0.1% of the total; fine.
- `stop_position` (position in the route; could stand in for the line): rank 4, 8.8% of the total; fine.

Values outside the range seen in training (the model cannot extrapolate there): none above 5% of the rows.

## M-A′ (15,898 rows, base value -0.809)

| rank | feature | group | mean_abs_shap | share |
| --- | --- | --- | --- | --- |
| 1 | hist_rate_route | history | 0.546 | 22.7% |
| 2 | stop_position | timetable | 0.322 | 13.4% |
| 3 | hist_rate_service_hour | history | 0.292 | 12.1% |
| 4 | dwell_min | timetable | 0.239 | 10.0% |
| 5 | temperature_c | weather | 0.183 | 7.6% |
| 6 | weekday | timetable | 0.183 | 7.6% |
| 7 | hist_rate_all | history | 0.126 | 5.3% |
| 8 | planned_hour | timetable | 0.099 | 4.1% |
| 9 | destination | timetable | 0.097 | 4.0% |
| 10 | hist_n_route | history | 0.096 | 4.0% |
| 11 | is_school_holiday | calendar | 0.043 | 1.8% |
| 12 | wind_gust_kmh | weather | 0.042 | 1.8% |

Share per feature group: history 44.1%, timetable 41.2%, weather 11.9%, calendar 2.9%.

Watch features:

- `destination` (many categories; could memorise single trains): rank 9, 4.0% of the total; fine.
- `hist_n_route` (a count, not a rate; could stand in for the line or the period): rank 10, 4.0% of the total; fine.
- `stop_position` (position in the route; could stand in for the line): rank 2, 13.4% of the total; **look closer**.

Values outside the range seen in training (the model cannot extrapolate there): none above 5% of the rows.

## M-B (15,898 rows, base value -0.483)

| rank | feature | group | mean_abs_shap | share |
| --- | --- | --- | --- | --- |
| 1 | prev_delay | previous stops | 2.284 | 50.9% |
| 2 | prev_delay_2 | previous stops | 0.376 | 8.4% |
| 3 | dwell_min | timetable | 0.344 | 7.7% |
| 4 | hist_rate_route | history | 0.224 | 5.0% |
| 5 | destination | timetable | 0.206 | 4.6% |
| 6 | prev_minutes_to_departure | previous stops | 0.199 | 4.4% |
| 7 | weekday | timetable | 0.141 | 3.1% |
| 8 | temperature_c | weather | 0.123 | 2.7% |
| 9 | service | timetable | 0.122 | 2.7% |
| 10 | hist_n_route | history | 0.086 | 1.9% |
| 11 | hist_rate_all | history | 0.072 | 1.6% |
| 12 | hist_rate_service_hour | history | 0.065 | 1.5% |

Share per feature group: previous stops 63.8%, timetable 20.5%, history 10.0%, weather 5.1%, calendar 0.7%.

Watch features:

- `destination` (many categories; could memorise single trains): rank 5, 4.6% of the total; fine.
- `hist_n_route` (a count, not a rate; could stand in for the line or the period): rank 10, 1.9% of the total; fine.
- `stop_position` (position in the route; could stand in for the line): rank 16, 0.8% of the total; fine.

Values outside the range seen in training (the model cannot extrapolate there): none above 5% of the rows.

## M-A inside one service (mean |SHAP|, top 5 without `service`)

- **regional** (20,751 rows; `service` itself contributes -0.09 on average): `hist_rate_service_hour` 0.325, `hist_rate_route` 0.244, `dwell_min` 0.174, `destination` 0.172, `weekday` 0.146
- **long-distance** (10,410 rows; `service` itself contributes +0.27 on average): `hist_rate_service_hour` 0.449, `hist_rate_route` 0.441, `stop_position` 0.225, `dwell_min` 0.223, `weekday` 0.175

## M-B: effect of the previous-stop delay

| bin | rows | mean_shap |
| --- | --- | --- |
| 0 or early | 3831 | -2.054 |
| 1–2 | 3312 | -1.736 |
| 3–5 | 2196 | -1.408 |
| 6–9 | 1648 | -0.351 |
| 10–19 | 2069 | 2.707 |
| 20+ | 2842 | 4.579 |

Figures: `reports/figures/shap_importance_test.png`, `reports/figures/shap_dependence_test.png`.
