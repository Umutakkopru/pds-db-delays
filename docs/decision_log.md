# Decision log: data and method decisions

> Read this file (rule "Read-when" in `CLAUDE.md`) before making or changing a data or method decision, before writing the Data or Methodology section, and whenever a number has to be traced to its source.

Purpose: a chronological record of every data and method decision, with the question, the evidence, the decision and where it goes in the report. Every number here is traceable to a script and an output file in this repository. The report's Data and Methodology sections are written from this log.

How to add an entry: copy the template at the end, give it the next number, link the script and the output file. One entry per decision, written when the decision is made.

Who decided: D1–D16 were prepared by one member and are **proposals until confirmed by the group** (to be discussed after 9 Nov 2026). When the group confirms or changes a decision, note it in that entry ("Confirmed by the group on …" or a new entry). New decisions are made together.

Status: 7 Nov 2026, end of week 1 (data acquisition and data checks complete; evaluation protocol refined in D13–D15; disruption flags forbidden in D16; cleaning step next).

---

## Summary for the report

| # | Topic | Decision | Evidence | Report section |
| --- | --- | --- | --- | --- |
| D1 | Topic and data | Deutsche Bahn departure delays at Würzburg Hbf, open DB archive (CC BY 4.0), Jul 2024 – Oct 2026 | Topic comparison; first data check | 1 Introduction, 3 Data |
| D2 | Target | `delayed = 1` if departure delay ≥ 6 min; binary classification | DB punctuality threshold; skewed delay distribution | 1, 4 Methodology |
| D3 | Scenarios | A: before the trip; B: en route (with earlier-stop delays) | Delay propagation along routes | 1, 4 |
| D4 | Split | Chronological; A: train Jul 24–Dec 25, val Jan–Jun 26, test Jul–Oct 26 | Real-use setting; leakage avoidance | 4 |
| D5 | Main model | LightGBM, compared with rule-based and logistic baselines | Tabular data, interactions, missing values | 4 |
| D6 | Scenario B period | Train from 3 Nov 2025 (val May–Jun 26, same test) | Coverage check: 0% → 100% preceding stops | 3, 4 |
| D7 | Train type labels | Use `line_id` and `service`, not raw `train_type` | ARV relabel Dec 2025; line format change | 3 |
| D8 | Excluded rows | Buses, rows without timetable record, no planned time | Category check | 3 |
| D9 | Cancellations | Excluded from main target; sensitivity check counts them as delayed | DB definition; 1–4.5% of departures | 3, 5 Results |
| D10 | Time zone | Naive local time throughout; DST nights 00–05 h excluded | Dataset documentation; 5 DST days | 3 |
| D11 | Target validity and collection gaps | Target = last reported time from DB's API; no days excluded | Data quality check sections 1–4 | 3, 6 Discussion |
| D12 | Duplicates and month boundaries | Drop duplicate ids (none found); earlier stops searched within the monthly file | Data quality check; download step | 3 |
| D13 | Evaluation protocol | Control model M-A′; paired day-block bootstrap; refit on train + val; no class weights; B by horizon | Split sizes per scenario; B horizon by service | 4, 5 |
| D14 | Baseline and history features | B1 = service × hour; history window [D − 29, D − 1); `train_number` not a feature | D7 (unstable `train_type`); prediction moment of scenario A | 4 |
| D15 | Dashboard scope | Replay of real test-period departures, no free future dates | No live weather/history without API calls | 5 |
| D16 | Disruption flags | `is_additional_stop`, `is_replacement_train`, `replaced_train_*`, `has_plan_record` are filters only, never features | Additional stops 43.8% delayed vs. 24.6% | 4 |

Key numbers (all 28 months, Würzburg Hbf):

| Quantity | Value | Source |
| --- | --- | --- |
| Months | 28 (Jul 2024 – Oct 2026), none missing | `reports/checks/monthly_summary.csv` |
| Würzburg rows (arrivals and departures) | 365,502 | same |
| Planned departures per month (trains, before cleaning) | 7,549 – 9,622 | `reports/checks/quality_by_month.csv` |
| Share departing 6+ min late per month | 19.2% – 30.0% | same |
| Share of cancelled departures per month | 1.0% – 4.5% | same |
| Duplicate ids across all files | 0 | `checks/data_quality_check.py` output |
| Stations in the archive | 107–108 until 1 Nov 2025; ~5,300 from 2 Nov 2025 | `checks/coverage_check.py` output |
| ARV rows in scenario A training period | 692 of 238,850 (Dec 2025 only) | `reports/checks/train_types_by_month.csv` |
| ARV share of test-period rows | 17.1% | same |

---

## D1 Topic and data source (4 Nov 2026)

**Question.** Which prediction problem and dataset fit the brief (clear target, enough data, clean license, no textbook dataset, practical relevance) and can be understood quickly?

**Considered.** About a dozen topics. Rejected: Uber/Lyft prices (target almost fully explained by distance), French bakery sales (too small), ImmoScout24 rents (very common on Kaggle), NYC restaurant inspections (leakage-prone), BASt Autobahn counts and the energy register MaStR (hard-to-read formats). Shortlist: Munich bicycle counters, German electricity demand (OPSD/SMARD), Deutsche Bahn delays.

**Decision.** Deutsche Bahn departure delays at Würzburg Hbf, using the open archive `piebro/deutsche-bahn-data` (Hugging Face, CC BY 4.0, one Parquet file per month, ~15 million rows per month for Germany). Fallback topic: German electricity demand.

**Evidence.** First data check on Oct 2026 and Mar 2025 (`check_db.py` and `check_old.py`, outside the repository in `../pds-db-check/`):

| Check | Result |
| --- | --- |
| Rows per month | 12,975 (Oct 2026), 13,174 (Mar 2025); ~430 stops per day |
| Daily continuity | Median ~436 rows/day; lowest days are weekends and the 3 Oct holiday; no gaps |
| Missing delay values | 0.2% |
| Stops delayed 6+ min (cancelled excluded) | 20.2% |
| Cancelled stops | 1.1% |
| Duplicate IDs | 0 |
| Both planned times missing | 22 rows (0.2%) |
| `has_plan_record` = False | 411 rows (3.2%) |
| Delay range | −17 to 396 min; median 1, mean 5.2 |
| Planned arrival or departure empty (train starts or ends at Würzburg) | ~33% |

Share of stops departing 6+ min late by train type (Oct 2026, cancelled excluded); ICE trains are delayed about four times as often as RB trains:

| Train type | Delayed 6+ min | Stops (n) |
| --- | --- | --- |
| NJ (Nightjet) | 80.2% | 249 |
| ICE | 42.6% | 2,919 |
| ARV | 16.3% | 2,283 |
| RE | 11.5% | 3,802 |
| RB | 9.7% | 3,681 |
| All stops | 20.2% | – |

Over all 28 months (approximate cleaning rules, 7 Nov 2026): 230,388 non-cancelled train departures with a timetable record, 24.6% departing 6+ min late; 109,085 (47%) of them start at Würzburg (no planned arrival).

**Actual columns** (the GitHub README of the dataset is outdated; these are the real names):

| Column | Meaning | Use |
| --- | --- | --- |
| `station_name`, `xml_station_name`, `eva` | Station name and ID | Filter: `station_name = 'Würzburg Hbf'` |
| `train_type`, `line_number`, `train_number` | ICE, RE, RB, ARV, NJ…; line such as RB53; train number | Build `line_id`, `service`; `train_number` as history key only |
| `final_destination_station` | Final stop of the train | Feature (checked for leakage, D16) |
| `arrival_planned_time`, `departure_planned_time` | Timetable times | Features, split, target |
| `arrival_change_time`, `departure_change_time` | Last reported (realised) times | Target only at Würzburg; earlier-stop delays in scenario B |
| `delay_in_min` | Departure delay where a departure exists | Check only |
| `time` | Event timestamp | Never a feature |
| `arrival_is_canceled`, `departure_is_canceled` | Cancellation flags | Filter |
| `train_line_ride_id`, `train_line_station_num` | Scheduled-run ID and position in the full route | Join earlier stops; stops between |
| `has_plan_record`, `is_additional_stop`, `is_replacement_train`, `replaced_train_*` | Data-quality and disruption flags | Filter only (D16) |
| `row_role`, `wuerzburg_id`, `source_month` | Added by `01_filter_month.sql` | Pipeline bookkeeping |

Example of delay propagation: on 6 Oct 2026 an RB53 was 18 min late at Oberhaid and still 13 min late at Würzburg Hbf.

**About the source** (dataset documentation): collected from DB's public Timetables API (`plan` and `fchg` endpoints) four times a day at 03, 09, 15 and 21 UTC; each run stores the changes of the previous 6+ hours; timestamps are German local time; the ~100 largest stations are covered from July 2024, all stations from 2 November 2025; API errors caused collection gaps between November 2025 and July 2026.

**Report.** Introduction (motivation), Data (source, license, size).

## D2 Target variable (4 Nov 2026)

**Question.** What exactly do we predict?

**Decision.** `delayed = 1` if `departure_change_time − departure_planned_time ≥ 6 min`, else 0. Trains that end at Würzburg (no departure) are not part of the target. We compute the delay ourselves instead of using `delay_in_min`.

**Why.**
- 6 minutes is Deutsche Bahn's official punctuality threshold (a train is punctual if it is less than 6 minutes late), so the threshold is not arbitrary.
- The delay distribution is highly skewed (Oct 2026: median 1 min, mean 5.2 min, maximum 396 min). A regression would be dominated by rare extreme delays; the passenger's question ("will I make my connection?") is binary.
- `delay_in_min` matches the departure time difference in 100% of rows and the arrival difference in only 61.9%, so it is a departure delay, but computing the target ourselves makes the definition explicit.

**Alternatives kept as optional.** Regression on delay minutes; three classes (0–5, 6–15, 16+ min).

**Report.** Introduction (problem definition), Methodology (target).

## D3 Two prediction scenarios (4 Nov 2026)

**Question.** At which moment is the prediction made, and which information is allowed?

**Decision.**
- Scenario A, before the trip (asked the day before): timetable, train type/line, destination, calendar, holidays, weather, historical delay rates.
- Scenario B, en route (asked when the train leaves its previous stop): everything in A plus the delay at stops the train has already passed.

**Why.** Delays propagate along a route (6 Oct 2026: an RB53 was 18 min late at Oberhaid and still 13 min late at Würzburg Hbf). Comparing A and B answers a research question of its own: how much of a delay is predictable in advance, and how much builds up on the way?

**Scope consequence (6 Nov 2026).** Most regional trains start or end at Würzburg (Oct 2026: only 743 of 3,681 RB stops and 464 of 3,802 RE stops belong to trains that arrive and depart again). Scenario B therefore applies to through trains only; A is reported on all departures and additionally on the through-train subset, so that A and B are compared on identical rows.

**Report.** Introduction (research questions), Methodology (scenarios), Results.

## D4 Chronological split (4 Nov 2026, revised 6 Nov 2026)

**Decision.** Never random. Scenario A: train Jul 2024 – Dec 2025 (18 months), validation Jan – Jun 2026 (6 months), test Jul – Oct 2026 (4 months). The test set is used once, at the very end, for all models at the same time. Split dates live only in `src/config.py` and are checked by `tests/test_leakage.py`.

**Why this range.**
- Start July 2024: earliest month in the archive; gives two full winters. July 2024 is complete (13,887 Würzburg rows, median 467 per day), so no later start is needed.
- End October 2026: last complete month when the plan was made; the dataset stays fixed during the project.
- Validation contains winter and spring, so tuning sees bad-weather conditions.
- Test = most recent data, mimicking real use. Limitation: no winter months in the test period; season effects are checked on the validation set.

**Alternatives considered.** Winter test period (would break "test = most recent"), 12-month test (too little training and validation data), rolling-origin evaluation (more effort; optional if time allows).

**Report.** Methodology (evaluation design), Discussion (limitations).

## D5 Model choice (6 Nov 2026)

**Decision.** Baselines: B0 majority class, B1 historical delay rate of train type × hour, B2 logistic regression. Main model: LightGBM (scenario A and B). Optional: Random Forest as a check.

**Why LightGBM.** The data is tabular; gradient-boosted trees are the established strong choice for tabular data (Grinsztajn et al., 2022). They learn interactions (e.g. long-distance train × Friday evening × rain) without hand-built terms, handle missing values (no earlier stop) and categorical features natively, train in seconds on ~365,000 rows, and SHAP's TreeExplainer gives exact explanations for the report and the dashboard.

**Not taken on faith.** LightGBM is only called better if the 95% interval of its PR-AUC difference to B2 lies above zero (paired day-block bootstrap; revised 7 Nov 2026, see D13; the original criterion was non-overlapping confidence intervals). Alternatives considered: XGBoost/CatBoost (same family, no clear advantage), Random Forest (usually slightly weaker), neural networks (more effort, harder to explain, no expected gain on this data).

**Metrics.** Primary PR-AUC (only ~20–25% positives); ROC-AUC; F1, precision and recall at a threshold chosen on validation; Brier score and reliability diagram. A scenario A ROC-AUC above ~0.95 is treated as a leakage warning.

**Report.** Methodology (models, metrics), Results.

## D6 Scenario B training period: station coverage (6–7 Nov 2026)

**Question.** Scenario B needs the train's earlier stops. Are they in the data for the whole period?

**Method.** `checks/coverage_check.py` on Jul 2024, Mar 2025, Oct 2025, Nov 2025, Oct 2026: for trains that arrive at Würzburg and depart again, the share with at least one earlier stop and with the directly preceding stop. `checks/data_quality_check.py` section 3: the same per day around the change.

**Result.**

| Train type | Jul 2024 | Mar 2025 | Oct 2025 | Nov 2025 | Oct 2026 |
| --- | --- | --- | --- | --- | --- |
| Stations in file | 108 | 107 | 107 | 5,295 | 5,245 |
| ICE | 99.9% | 98.1% | 99.4% | 99.8% | 99.9% |
| RB | 0.0% | 0.0% | 0.0% | 93.1% | 100.0% |
| RE | 0.0% | 0.0% | 0.0% | 93.5% | 100.0% |
| NJ | 98.3% | 96.7% | 99.2% | 97.4% | 95.9% |

Share of trains with the directly preceding stop. Per day (RB/RE through trains): 0% until 1 Nov 2025, 2.6% on 2 Nov, 100% from 3 Nov 2025.

Before November 2025 the only earlier stop of an RB/RE train is a distant large station (RB53: Bamberg, 14 stops before Würzburg, where the delay is almost always 0); "at least one earlier stop" (RE 99.8%) therefore looks fine but is misleading. `train_line_station_num` numbers the full route, so gaps in the numbering show missing stations.

**Decision.** Scenario B trains from 3 Nov 2025 (first full day): train 3 Nov 2025 – Apr 2026, validation May – Jun 2026, test Jul – Oct 2026 (same as A). Set as `FULL_COVERAGE_START` in `src/config.py`; tested.

**Why not use the earlier period.** The model would learn that earlier-stop information exists almost only for ICE trains, a pattern that changes abruptly in November 2025 and does not exist in the test period. The shorter period still contains a winter (Nov 2025 – Feb 2026) and ~25,000 through-train departures.

**Report.** Data (coverage table as evidence), Methodology (scenario B split).

## D7 Train type labels: ARV, line format (6–7 Nov 2026)

**Question.** Are the categories stable over the 28 months?

**Method.** Per-month train-type and line-format tables from `src/01_download.py` (`reports/checks/train_types_by_month.csv`, `line_formats_by_month.csv`); `checks/category_check.py` (`reports/checks/line_types_over_time.csv`).

**Results.**
- **ARV** appears in December 2025 (692 rows), reaches ~2,200 rows per month from February 2026, while RE falls by about the same number (~6,000 → ~3,800 per month). ARV runs exactly the lines RE8, RB8 and RE80, which ran as RE/RB before. ARV stands for Arverio, which operated RE 8 since 2019 and RE 80 since December 2022, i.e. during the whole data period: only the label in the data changed, not the operator.
- Delay rates of these lines are similar before and after (line 8: 12.4% → 15.4%, partly explained by construction work on RE 8 Würzburg–Lauda, 21 Dec 2025 – 6 Feb 2026; line 80: 8.9% → 7.0%).
- **Line format** changes at the same time: "53" until November 2025, "RB53" from December 2025. In some 2026 rows `train_type` and the line prefix disagree (line RE10 with type RB).
- ARV is almost absent in the scenario A training period (692 of 238,850 rows) but 17.1% of test-period rows: a raw `train_type` feature would meet an unseen category in the test set.
- **IC** disappears after October 2025 (~150 → 0 per month).

**Decision.**
- `line_id`: line prefix when present ("RB53", "RE8"); otherwise `train_type` + digits for RE/RB rows before December 2025; ARV rows keep their line; NULL for long-distance trains. To verify while cleaning: the RE/RB label of a train number before December 2025 matches its line prefix after.
- `service`: long_distance (ICE, IC, EC), night (NJ, EN), regional (RE, RB, ARV), other.
- `train_type` kept for reporting only, not as a model feature.
- ICE rows have no line number (~22.5% of rows); for ICE the train number or route is used instead.

**Report.** Data (data preparation, category harmonisation), Discussion (error analysis on lines 8 and 80).

## D8 Rows excluded in cleaning (6 Nov 2026)

**Decision and evidence.**
- **Rail replacement buses** (`train_type = 'Bus'`, lines EV/SEV or the replaced line, up to 1,884 rows in July 2024): not trains; excluded and counted.
- **`train_type` missing** (2–391 rows per month, most in 2026): none has a planned departure or a timetable record; removed by the rules below.
- **Rows without a timetable record** (`has_plan_record` false; 3.2% in Oct 2026) and rows without any planned time (0.2%): excluded.
- **Rare train types** (IC, DZ, UEX, EC, single odd values such as RE8 as a type): kept and grouped via `service = other` / `long_distance`.

**Report.** Data (cleaning rules, with counts from the cleaning step).

## D9 Cancellations (6–7 Nov 2026)

**Question.** How are cancelled departures treated?

**Evidence.** 1.0% – 4.5% of planned departures per month are cancelled; the share falls from ~3–4% (2024/25) to ~1–2% (2026) (`reports/checks/quality_by_month.csv`).

**Decision.**
- Cancelled = `departure_is_canceled` at Würzburg. A train whose arrival is cancelled but which still departs (e.g. now starts at Würzburg) is a normal departure.
- Main target: cancelled departures excluded, as in DB's punctuality statistic (measured for trains that run).
- Sensitivity check: final models evaluated once more with cancellations counted as `delayed = 1`; change in PR-AUC/ROC-AUC reported (`CANCELED_AS_DELAYED_SENSITIVITY` in `src/config.py`).
- Scenario B: if an earlier stop is cancelled, the last earlier stop that was not cancelled is used.
- EDA shows the cancellation share by month, train type and hour, including the falling trend.

**Report.** Data (exclusions), Results (sensitivity), Discussion (limitation: a passenger experiences a cancellation as the worst delay).

## D10 Time zone and daylight saving time (6–7 Nov 2026)

**Evidence.** The dataset documentation states that timestamps are German local time (Europe/Berlin) as returned by the API, without conversion; collection runs at UTC times.

**Decision.**
- All features and split boundaries use naive local time; nothing is converted to UTC (`TIMEZONE` in `src/config.py`).
- Weather from Open-Meteo with `timezone=Europe/Berlin`, joined on the local hour of the planned departure; the doubled October hour is averaged.
- On DST-change days a difference between two naive local times can be off by 60 minutes. Departures planned between 00:00 and 05:00 local time on the five DST days in the data period (27 Oct 2024, 30 Mar 2025, 26 Oct 2025, 29 Mar 2026, 25 Oct 2026) are excluded and counted. The days are computed by `config.dst_change_days()` and tested in `tests/test_config.py`.

**Report.** Data (preprocessing), one sentence.

## D11 What the target measures; collection gaps (6–7 Nov 2026)

**Question.** Is `departure_change_time` the realised departure time, and do the documented collection gaps distort the target?

**Reasoning.** Runs every 6 hours store changes reaching back 6+ hours, so a stop is normally captured after it happened and the value is (close to) the realised time. If a run was skipped, a stop could be missing or carry the last forecast.

**Method and results** (`checks/data_quality_check.py`):
1. `departure_change_time` is never empty (0.0% in every month); planned departures per day are complete (only 2 days below 70% of the weekday median: 2 Feb and 8 Apr 2026, both weekdays, kept). So a gap would not show as missing data but as departures with change time = planned time.
2. "Too punctual" days (share of exactly-on-time departures above the 99th percentile or 20 points above the month median): 11 days, all holidays or Sundays with light traffic: 24, 25, 26, 28, 30, 31 Dec 2025 and 1 Jan 2026; Easter weekend 4–5 Apr 2026; Sundays 14 Jun and 27 Sep 2026.
3. July 2026, the month with the largest documented gap (102 hours), has a normal share of exactly-on-time departures (36.5%) and delay rate (28.5%).

**Decision.** No days are excluded; holidays stay in the data (covered by calendar features). The report defines the target as "the last departure time reported by DB's Timetables API", not an independent measurement.

**Remaining risk.** Gaps of a few hours cannot be seen at day level. If the error analysis shows errors concentrated in single time blocks, this is checked again. The share of exactly-on-time departures rises from ~34% (2024) to ~42% (2026); shown in the EDA.

**Report.** Data (data quality), Discussion (limitations).

## D12 Duplicates, month boundaries, earlier-stop matching (6 Nov 2026)

**Evidence.** A monthly file can contain a few rows planned on the last day of the previous month (Oct 2026 file: 2 ICE rows planned on 30 Sep). Duplicate ids within and across all 28 files: 0. `train_line_ride_id` repeats on every day of a month.

**Decision.**
- Each row stores its `source_month`; cleaning drops duplicate ids (none expected).
- Earlier stops of a trip = same `train_line_ride_id`, lower stop number, planned within the 12 hours before the Würzburg arrival (handles trips across midnight). Each earlier stop is linked to its Würzburg row via `wuerzburg_id`.
- Known limitation: earlier stops are searched only within the same monthly file; a train arriving shortly after midnight on the 1st loses earlier stops on the last day of the previous month (a few trains per month, scenario B only).

**Report.** Data or Methodology (pipeline), one sentence each.

## D13 Evaluation protocol refined (7 Nov 2026)

**Question.** Does the evaluation design answer the research question (how much of a delay builds up en route) without confounding, and are model differences judged correctly?

**Method.** Plan review; DuckDB count on `data/interim/` with approximate cleaning rules (non-cancelled train departures with a timetable record, no buses; DST and duplicate rules not yet applied).

**Result.**

| Period | Departures | Through trains | Departing 6+ min late | Median planned minutes from last earlier stop |
| --- | --- | --- | --- | --- |
| Before 3 Nov 2025 | 137,087 | 67,105 | 25.6% | 55 |
| B train (3 Nov 2025 – Apr 2026) | 45,261 | 23,946 | 23.6% | 41 |
| B validation (May – Jun 2026) | 16,072 | 8,031 | 21.3% | 41 |
| Test (Jul – Oct 2026) | 31,968 | 15,921 | 23.0% | 40 |

M-A is trained on 18 months of all departures, M-B on 6 months of through trains, so M-B − M-A mixes the effect of the propagation features with the effect of a different training period and size. The minutes from the previous stop differ strongly by service (ICE ~30–60 min, RB/RE often a few minutes).

**Decision.**
- **Control model M-A′:** scenario A features, scenario B training window, through trains. The contribution of propagation features is M-B − M-A′ on identical test rows.
- **Model comparison:** paired bootstrap of the metric difference on the same test rows, resampling whole days (1,000 resamples), because delays within one day are correlated. A model counts as better if the 95% interval of the difference lies above zero. Replaces "non-overlapping confidence intervals" (D5), which is overly conservative and ignored within-day correlation.
- **Final refit:** hyperparameters, number of trees (early stopping) and the threshold (max F1) are chosen with training-only models on validation; final models are refitted on training + validation with these settings and scored once on the test set.
- **No class weighting** in LightGBM or logistic regression (keeps probabilities calibrated for the Brier score and the dashboard); the threshold handles the 23% positive rate.
- **Scenario B results by horizon:** reported by `service` and by planned minutes from the previous stop (< 10, 10–30, > 30 min).

**Alternatives considered.** Training M-A on the B window only (loses the long history that is A's advantage); rolling-origin evaluation (more effort; still optional).

**Report.** Methodology (evaluation design), Results (A vs. A′ vs. B, horizon slices).

## D14 Baseline 1 and history features (7 Nov 2026)

**Question.** Which grouping does the rule-based baseline use, and which data may history features see?

**Decision.**
- **B1 = historical delay rate of `service` × planned hour** (training data only). Raw `train_type` is not used, because ARV is almost absent from the training period but 17% of test rows (D7).
- **History window:** for a departure on day D, departures planned in [D − 29, D − 1 00:00). Scenario A is asked the day before, so day D − 1 is not complete at prediction time. The time-travel test truncates the data at D − 1 00:00.
- **Keys and fallback:** train number → `line_id` (regional) or route group (ICE, origin/destination direction) → `service`, used when a cell has too few departures in the window.
- **`train_number` is not a model feature** (high cardinality, can change at the December timetable change); added to `FORBIDDEN_COLUMNS` in `src/features_config.py`. It remains a key for history rates.

**Report.** Methodology (baselines, features).

## D15 Dashboard scope (7 Nov 2026)

**Question.** Can the dashboard predict for any future date?

**Reasoning.** Scenario A features include weather and recent history; for a future date both would need live API calls, which are out of scope.

**Decision.** The dashboard replays real departures of the test period (Jul – Oct 2026): the user picks a date and a departure and sees the predicted probability, the actual outcome and the SHAP explanation; for scenario B a slider changes the previous-stop delay. The app loads a saved model and a small table of test-period feature rows.

**Report.** Results (dashboard), appendix link.

## D16 Disruption flags are filters, not features (7 Nov 2026)

**Question.** Which raw columns besides the change times carry information that exists only once a disruption has happened?

**Method.** DuckDB query on `data/interim/` (230,388 non-cancelled train departures with a timetable record, buses excluded), comparing the delay rate per flag value and per destination.

**Result.**
- `is_additional_stop` = true: 16 departures, 43.8% departing 6+ min late, vs. 24.6% otherwise. Additional stops, replacement trains (`is_replacement_train`, `replaced_train_type`, `replaced_train_number`) and missing timetable records (`has_plan_record`) come from DB's change feed and are set when the disruption is known, not the day before.
- `final_destination_station`: departures whose destination differs from the usual destination of their train number are delayed 24.3% of the time vs. 24.6%; no sign that changed destinations leak disruptions. Allowed as a feature.

**Decision.** The disruption flags plus `source_month` and `row_role` are added to `FORBIDDEN_COLUMNS` in `src/features_config.py`; they may only be used to filter rows. Excluding cancelled departures is also a filter based on information known only later; it is standard because the target is undefined for a train that does not run (D9) and is named in the Discussion.

**Report.** Methodology (leakage rules), one sentence.

---

## Pipeline and checks so far

| Step | Script | Output |
| --- | --- | --- |
| Download and filter | `src/01_download.py`, `src/sql/01_filter_month.sql` | `data/interim/wuerzburg_YYYY-MM.parquet` (92 MB for 28 months; raw files 5 GB); `reports/checks/monthly_summary.csv`, `train_types_by_month.csv`, `line_formats_by_month.csv` |
| Coverage check | `checks/coverage_check.py` | `reports/checks/coverage_by_month.csv` |
| Category check | `checks/category_check.py` | `reports/checks/line_types_over_time.csv` |
| Data quality check | `checks/data_quality_check.py` | `reports/checks/quality_by_month.csv`, `low_count_days.csv`, `coverage_nov_2025_daily.csv`, `suspicious_days.csv` |
| Leakage and config tests | `tests/test_leakage.py`, `tests/test_config.py` | 10 passing (1 skipped by design) |

## Sources

- Deutsche Bahn Data, Hugging Face: https://huggingface.co/datasets/piebro/deutsche-bahn-data (CC BY 4.0)
- deutsche-bahn-data project (collection method, coverage, changelog): https://github.com/piebro/deutsche-bahn-data
- Arverio: https://en.wikipedia.org/wiki/Arverio
- Arverio BW construction notice RE 8, 21 Dec 2025 – 6 Feb 2026: https://www.arverio-bw.de/fileadmin/user_upload/Arverio_Baden-Wuerttemberg/Fahrplanabweichungen/141b_ABW_UPDATE_Baustelle_RE8_21.12.-06.02.26_Wuerzburg-Lauda.pdf
- Grinsztajn, L., Oyallon, E., Varoquaux, G. (2022). Why do tree-based models still outperform deep learning on tabular data? NeurIPS Datasets and Benchmarks Track.
- Ke, G. et al. (2017). LightGBM: A Highly Efficient Gradient Boosting Decision Tree. NeurIPS.

---

## Template for new entries

```markdown
## Dn Title (date)

**Question.** What had to be decided?

**Method.** Script and output file.

**Result.** Numbers.

**Decision.** What we do, and where it is implemented (file, constant, test).

**Alternatives considered.** And why not.

**Report.** Section(s).
```
