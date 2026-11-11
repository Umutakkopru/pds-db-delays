# Decision log: data and method decisions

> Read this file (rule "Read-when" in `CLAUDE.md`) before making or changing a data or method decision, before writing the Data or Methodology section, and whenever a number has to be traced to its source.

Purpose: a chronological record of every data and method decision, with the question, the evidence, the decision and where it goes in the report. Numbers here are traceable to a script and an output file in this repository, with three exceptions that the cleaning step (`02_clean`, `cleaning_counts.csv`) will replace: the D1 table (scripts in `../pds-db-check/`, outside the repository) and the counts in D13 and D16 (ad hoc DuckDB queries). All three were reproduced on 10 Nov 2026; the queries are in the appendix of `docs/audit_2026-11-10.md`. The report's Data and Methodology sections are written from this log.

How to add an entry: copy the template at the end, give it the next number, link the script and the output file. One entry per decision, written when the decision is made.

Who decided: D1–D25 were prepared by one member and are **proposals until confirmed by the group** (to be discussed after 9 Nov 2026). When the group confirms or changes a decision, note it in that entry ("Confirmed by the group on …" or a new entry). New decisions are made together.

Status: 10 Nov 2026, end of week 1 (data acquisition and data checks complete; evaluation protocol refined in D13–D15; disruption flags forbidden in D16; independent audit on 10 Nov, its recommendations recorded as D17–D22; cleaning step next).

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
| D17 | Baseline for scenario B | B3: "delayed at the previous stop → delayed at Würzburg", scored on the same rows as M-A′ and M-B | Rule alone: 85.3% accuracy, F1 ≈ 0.81 in the B training window | 4, 5 |
| D18 | Rows without timetable record | Stay excluded; counts per split reported; sensitivity check for scenario A | Share grows from 1.4% to 6.3%; delayed 54% vs 23% in the test period | 3, 5, 6 |
| D19 | Cleaning step design | Rows are flagged with `exclude_reason`, not deleted; delays below −30 min invalid; `line_id` by format, line prefix wins | 4 impossible delays; 2,442 digit-only lines after Dec 2025 | 3 |
| D20 | Through trains | `is_through` = planned arrival present; `has_prev_stop` separate; scenario B rows need both | 72 test departures arrive without an earlier stop in the data | 4 |
| D21 | Evaluation details | Tree count and threshold kept in the refit; tuning at most 20 settings; weather ablation on validation | Refit data is 30–34% larger; weather is observed, not forecast | 4, 6 |
| D22 | Order and scope of the remaining steps | Baselines before enrichment; simple history features first; Bavarian school holidays first; minimum version frozen 1 Dec, extensions 8 Dec | One working track must reach a full results table early | – |
| D23 | Enrichment | Weather from Open-Meteo in UTC, converted to local time; Bavarian public and school holidays; bridge days | Open-Meteo's "local time" ignores summer time; official holiday announcement | 3, 4 |
| D24 | Feature tables | 21 scenario A features (timetable, calendar, weather, 28-day history), 4 more for scenario B (previous stops) | Time-travel test; single-feature ROC-AUC at most 0.80 | 4 |
| D25 | Final run | One code path with three modes; lock file; rehearsal one step back in time | Rehearsal: validation optimism 0.002–0.023 PR-AUC; conclusions unchanged | 4, 5 |

Key numbers (all 28 months, Würzburg Hbf):

| Quantity | Value | Source |
| --- | --- | --- |
| Months | 28 (Jul 2024 – Oct 2026), none missing | `reports/checks/monthly_summary.csv` |
| Würzburg rows (arrivals and departures) | 365,502 | same |
| Planned departures at Würzburg (all, before exclusions) | 247,716 | `reports/checks/cleaning_counts.csv` (`src/02_clean.py`) |
| Excluded: cancelled 6,431; without timetable record 7,290; bus 3,607; DST nights 51; invalid delay 4; duplicate id 0 | 17,383 | same |
| Modelling rows (scenario A: train / validation / test) | 230,333 (152,384 / 45,993 / 31,956) | same |
| Share delayed, modelling rows of training + validation | 24.8% (train 25.7%, validation 22.0%) | same; test-period rates are not written before the final run |
| Scenario B rows (`is_through` and `has_prev_stop`; train / validation / test) | 23,926 / 8,020 / 15,898 | `reports/checks/through_train_counts.csv` |
| Planned departures per month (trains, before cleaning) | 7,549 – 9,622 | `reports/checks/quality_by_month.csv` |
| Share of all planned departures that depart 6+ min late, per month (cancelled departures in the denominator) | 19.2% – 30.0% | same (`pct_delayed_6`) |
| Share departing 6+ min late per month among departures that ran (as in the target) | 19.4% – 31.1% | same (`pct_delayed_6_not_canceled`; row added 10 Nov 2026, audit D-06) |
| Share of cancelled departures per month | 1.0% – 4.5% | same |
| Duplicate ids across all files | 0 | `checks/data_quality_check.py` output |
| Stations in the archive | 107–108 until 1 Nov 2025; ~5,300 from 2 Nov 2025 | `checks/coverage_check.py` output |
| ARV rows among all Würzburg rows (arrivals and departures) of the Jul 2024 – Dec 2025 files | 692 of 238,850 (Dec 2025 only) | `reports/checks/train_types_by_month.csv` |
| ARV share of all Würzburg rows in the Jul – Oct 2026 files | 17.1% | same |
| ARV among modelling rows: scenario A training departures; test departures | 330 of 152,384 (0.2%); 4,226 of 31,956 (13.2%) | `reports/checks/service_counts.csv` (`src/02_clean.py`; confirms the audit query Q6) |

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

**Actual columns** (the dataset's GitHub README was outdated on 4 Nov 2026 and lists the same 23 columns since at least 10 Nov 2026):

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
  - *Clarification (10 Nov 2026, audit E-03):* DB defines punctuality on arrivals (a stop is punctual if the planned arrival time is exceeded by less than 6 minutes). We apply the same threshold to departures, because a passenger waiting at Würzburg experiences the departure. The report says so explicitly. Times in the data have no seconds, so "≥ 6 min" equals DB's "more than 5:59".
- The delay distribution is highly skewed (Oct 2026: median 1 min, mean 5.2 min, maximum 396 min). A regression would be dominated by rare extreme delays; the passenger's question ("will I make my connection?") is binary.
- `delay_in_min` matches the departure time difference in 100% of rows and the arrival difference in only 61.9%, so it is a departure delay, but computing the target ourselves makes the definition explicit.

**Alternatives kept as optional.** Regression on delay minutes; three classes (0–5, 6–15, 16+ min).

**Report.** Introduction (problem definition), Methodology (target).

## D3 Two prediction scenarios (4 Nov 2026)

**Question.** At which moment is the prediction made, and which information is allowed?

**Decision.**
- Scenario A, before the trip (asked the day before): timetable, service and line (`service`, `line_id`; not the raw `train_type`, see D7), destination, calendar, holidays, weather, historical delay rates.
- Scenario B, en route (asked when the train leaves its previous stop): everything in A plus the delay at stops the train has already passed.

**Why.** Delays propagate along a route (6 Oct 2026: an RB53 was 18 min late at Oberhaid and still 13 min late at Würzburg Hbf). Comparing A and B answers a research question of its own: how much of a delay is predictable in advance, and how much builds up on the way?

**Scope consequence (6 Nov 2026).** Most regional trains start or end at Würzburg (Oct 2026: only 743 of 3,681 RB stops and 464 of 3,802 RE stops belong to trains that arrive and depart again). Scenario B therefore applies to through trains only; A is reported on all departures and additionally on the through-train subset, so that A and B are compared on identical rows.

**Report.** Introduction (research questions), Methodology (scenarios), Results.

## D4 Chronological split (4 Nov 2026, revised 6 Nov 2026)

**Decision.** Never random. Scenario A: train Jul 2024 – Dec 2025 (18 months), validation Jan – Jun 2026 (6 months), test Jul – Oct 2026 (4 months). The test set is used once, at the very end, for all models at the same time. Split dates live only in `src/config.py` and are checked by `tests/test_leakage.py`.

**Why this range.**
- Start July 2024: earliest month in the archive; gives two full winters. July 2024 is complete (13,887 Würzburg rows, median 467 per day), so no later start is needed.
- End October 2026: last complete month when the plan was made; the dataset stays fixed during the project.
  - *Correction (10 Nov 2026, audit D-01):* the archive itself is not fixed; the maintainer reprocessed all past months several times in 2026. The download now uses a fixed dataset revision (`HF_REVISION` in `src/config.py`, the commit 26 of the 28 raw files were downloaded from on 6 Nov 2026; the March 2025 and October 2026 files were downloaded on 4 Nov and have the same Würzburg row counts). `tests/test_data.py` checks the local row counts against `reports/checks/monthly_summary.csv`.
- Validation contains winter and spring, so tuning sees bad-weather conditions.
- Test = most recent data, mimicking real use. Limitation: no winter months in the test period; season effects are checked on the validation set.

**Alternatives considered.** Winter test period (would break "test = most recent"), 12-month test (too little training and validation data), rolling-origin evaluation (more effort; optional if time allows).

**Report.** Methodology (evaluation design), Discussion (limitations).

## D5 Model choice (6 Nov 2026)

**Decision.** Baselines: B0 majority class, B1 historical delay rate of service × hour (originally "train type × hour"; changed by D14 because of D7), B2 logistic regression. Main model: LightGBM (scenario A and B). Optional: Random Forest as a check.

**Why LightGBM.** The data is tabular; gradient-boosted trees are the established strong choice for tabular data (Grinsztajn et al., 2022). They learn interactions (e.g. long-distance train × Friday evening × rain) without hand-built terms, handle missing values (no earlier stop) and categorical features natively, train in seconds on ~230,000 rows (the modelling rows; 365,502 is the number of all Würzburg rows), and SHAP's TreeExplainer gives exact explanations for the report and the dashboard.

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

**Why not use the earlier period.** The model would learn that earlier-stop information exists almost only for ICE trains, a pattern that changes abruptly in November 2025 and does not exist in the test period. The shorter period still contains a winter (Nov 2025 – Feb 2026) and ~24,000 through-train departures (23,946, see D13).

**Report.** Data (coverage table as evidence), Methodology (scenario B split).

## D7 Train type labels: ARV, line format (6–7 Nov 2026)

**Question.** Are the categories stable over the 28 months?

**Method.** Per-month train-type and line-format tables from `src/01_download.py` (`reports/checks/train_types_by_month.csv`, `line_formats_by_month.csv`); `checks/category_check.py` (`reports/checks/line_types_over_time.csv`).

**Results.**
- **ARV** appears in December 2025 (692 rows), reaches ~2,200 rows per month from March 2026 (1,741 in February), while RE falls by about the same number (~6,000 → ~3,800 per month). ARV runs exactly the lines RE8, RB8 and RE80, which ran as RE/RB before. ARV stands for Arverio, which operated RE 8 since 2019 and RE 80 since December 2022, i.e. during the whole data period: only the label in the data changed, not the operator.
- Delay rates of these lines are similar before and after (line 8: 12.4% → 15.4%, partly explained by construction work on RE 8 Würzburg–Lauda, 21 Dec 2025 – 6 Feb 2026; line 80: 8.9% → 7.0%).
- **Line format** changes at the same time: "53" until November 2025, "RB53" from December 2025. In some 2026 rows `train_type` and the line prefix disagree (line RE10 with type RB).
- ARV is almost absent in the scenario A training period (692 of 238,850 rows) but 17.1% of test-period rows: a raw `train_type` feature would meet an unseen category in the test set.
  - *Correction (10 Nov 2026, audit C-01):* these two numbers count all Würzburg rows (arrivals and departures, by source file). Among the departures the models see it is 330 of 152,421 training departures (0.2%) and 13.2% of test departures. The conclusion is unchanged.
- **IC** disappears after October 2025 (~150 → 0 per month).

**Decision.**
- `line_id`: line prefix when present ("RB53", "RE8"); otherwise `train_type` + digits for RE/RB rows before December 2025; ARV rows keep their line; NULL for long-distance trains. To verify while cleaning: the RE/RB label of a train number before December 2025 matches its line prefix after.
  - *Correction (10 Nov 2026, audit E-07):* the line format is not a clean function of the date. Among modelling rows, 2,442 departures from 1 Dec 2025 on have digit-only lines (December 2025 is mixed; August 2026 has some again) and 825 departures before December 2025 already carry a prefix. The rule is therefore applied by format (prefix present or not), not by date. From December 2025, 1,901 departures have type RB with a line starting with RE; which label wins is still to be settled with the planned `train_number` check.
- `service`: long_distance (ICE, IC, EC), night (NJ, EN), regional (RE, RB, ARV), other.
- `train_type` kept for reporting only, not as a model feature.
- ICE rows have no line number (22.6–30.7% of the Würzburg rows per month have none); for ICE the train number or route is used instead.

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

**Evidence.** 1.0% – 4.5% of planned departures per month are cancelled; the share falls from about 3.2% on average in Jul 2024 – Dec 2025 (2.0–4.5% per month) to about 2.1% in 2026 (1.0–3.5%) (`reports/checks/quality_by_month.csv`).

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
  - *Correction (11 Nov 2026, step 03):* with `timezone=Europe/Berlin` the Open-Meteo archive applies a fixed offset of +1 hour all year (checked for 1 July 2026: `utc_offset_seconds = 3600`), so its "local" times are one hour off during summer time. The weather is therefore downloaded in UTC and converted to Europe/Berlin local time in `src/03_enrich.py`; the rest of the rule is unchanged (see D23).
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

*Added 10 Nov 2026 (audit E-05):* departures recorded before their planned time make up 1.1–2.4% of planned departures per month until November 2025 and at most 0.14% from December 2025 (the month in which the line format and the ARV label also change). Part of the rise in exactly-on-time departures is therefore early departures that are now recorded as 0. The binary target is not affected (an early departure is "not delayed"); the optional regression would be, so delays are clipped at 0 there. The cause is unknown (no entry in the dataset changelog).

**Report.** Data (data quality), Discussion (limitations).

## D12 Duplicates, month boundaries, earlier-stop matching (6 Nov 2026)

**Evidence.** A monthly file can contain a few rows planned on the last day of the previous month (Oct 2026 file: 2 ICE rows planned on 30 Sep). Duplicate ids within and across all 28 files: 0. `train_line_ride_id` repeats on every day of a month.

**Decision.**
- Each row stores its `source_month`; cleaning drops duplicate ids (none expected).
- Earlier stops of a trip = same `train_line_ride_id`, lower stop number, planned within the 12 hours before the Würzburg arrival (handles trips across midnight). Each earlier stop is linked to its Würzburg row via `wuerzburg_id`.
- *Added 10 Nov 2026 (audit D-04):* "0 duplicate ids" holds for the Würzburg rows. Among the 1,285,032 earlier-stop rows 60 ids occur twice, because 23 pairs of Würzburg rows share a ride id within 12 hours (the same train listed twice with different stop numbers); 7 Würzburg rows have two earlier stops with the same stop number and 76 stop pairs are planned in an order that contradicts their stop number. None of the duplicated Würzburg rows is a modelling row. The feature step therefore keys earlier stops by `wuerzburg_id` plus `id` and takes "the previous stop" by the latest planned time before the Würzburg arrival.
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
  - *Note (10 Nov 2026, EDA):* these bins do not fit the data. Measured to the Würzburg departure, no scenario B row is under 10 minutes (regional through trains stop about 10 minutes at Würzburg) and every long-distance train is over 30 minutes; medians are 16 min (regional), 54 min (long-distance) and 78 min (night). Proposed instead: report by service, and within it by 10–20, 20–45 and over 45 minutes. To settle with the results table.
  - *Implemented (11 Nov 2026):* `src/06_error_analysis.py` reports scenario B by service and by the horizon bins 10–20, 20–45 and over 45 minutes.

**Alternatives considered.** Training M-A on the B window only (loses the long history that is A's advantage); rolling-origin evaluation (more effort; still optional).

**Report.** Methodology (evaluation design), Results (A vs. A′ vs. B, horizon slices).

## D14 Baseline 1 and history features (7 Nov 2026)

**Question.** Which grouping does the rule-based baseline use, and which data may history features see?

**Decision.**
- **B1 = historical delay rate of `service` × planned hour** (training data only). Raw `train_type` is not used, because ARV is almost absent from the training period but 13% of test departures (17% of all test-period Würzburg rows; D7, corrected 10 Nov 2026).
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

## D17 Baseline for scenario B: persistence rule B3 (10 Nov 2026; proposal from the audit, E-01)

**Question.** B0–B2 are scenario A baselines. Against what is the en-route model M-B judged?

**Method.** DuckDB query on `data/interim/` (appendix of `docs/audit_2026-11-10.md`, Q5): B training window (3 Nov 2025 – Apr 2026), through trains with a non-cancelled earlier stop, approximate cleaning rules.

**Result.** 23,931 departures, 36.4% delayed. The delay at the previous stop and the departure delay at Würzburg correlate with 0.919. The rule "6+ min late at the previous stop → 6+ min late at Würzburg" has accuracy 85.3%, precision 77.2%, recall 84.5% (F1 ≈ 0.81). In 5.6% of the rows the train left its previous stop after the planned Würzburg departure.

**Decision.** Add baseline **B3** for scenario B: as a class rule (previous-stop delay ≥ 6 min) for F1, precision and recall, and with the previous-stop delay in minutes as the score for PR-AUC and ROC-AUC. B3 is evaluated on the same through-train test rows as M-A′ and M-B; the gain of the model is M-B − B3 with the paired day-block bootstrap (D13). If the gain is small, that is reported as a finding. Implemented in `src/evaluate.py` and `05_train.py`.

**Result on validation (11 Nov 2026).** On the scenario B validation rows (8,020 through trains with an earlier stop, May – June 2026, `reports/results_validation.md`) B3 reaches PR-AUC 0.877 [0.857, 0.893], ROC-AUC 0.909 [0.900, 0.918] and, with its fixed 6-minute rule, F1 0.806 (precision 0.775, recall 0.839). The scenario A baselines on the same rows reach PR-AUC 0.549 (B1) and 0.564 (B2). B3 − B2 = +0.312 PR-AUC [+0.287, +0.338]. This is the bar for M-B.

**Alternatives considered.** Logistic regression on the previous-stop delay alone (same information, one more model; optional); no B baseline (M-B could not be judged).

**Report.** Methodology (baselines), Results.

## D18 Rows without a timetable record: reported and tested (10 Nov 2026; proposal from the audit, E-02)

**Question.** D8 excludes rows with `has_plan_record` = false. Does this bias the data?

**Method.** DuckDB query on `data/interim/` (audit appendix, Q3): planned, non-cancelled train departures.

**Result.**

| Period | Departures | Without record | Share | Delayed, with record | Delayed, without record | Delayed, all |
| --- | --- | --- | --- | --- | --- | --- |
| Jul 2024 – Nov 2025 | 146,351 | 2,063 | 1.41% | 25.83% | 57.6% | 26.28% |
| Dec 2025 | 8,357 | 224 | 2.68% | 22.67% | 35.3% | 23.01% |
| Jan – Jun 2026 | 48,425 | 2,426 | 5.01% | 22.00% | 45.8% | 23.19% |
| Jul – Oct 2026 (test) | 34,118 | 2,150 | 6.30% | 23.01% | 54.0% | 24.97% |

These rows exist only because DB's change feed reported something for them; in 2026, 4,302 of 4,576 are long-distance trains.

**Decision.** The rows stay excluded from training and from the main evaluation (the flag is known only afterwards, D16). The cleaning step keeps them with `exclude_reason = 'no_plan_record'` (D19) and `cleaning_counts.csv` shows them per split. A second sensitivity check, next to the cancellation one (D9), scores the final scenario A models once on the test departures including these rows. The Data section shows the table; the Discussion names the selection.

**Alternatives considered.** Including them in training (their existence depends on the outcome); ignoring the issue (a reviewer can call it selection on the outcome).

**Report.** Data (exclusions), Results (sensitivity), Discussion (limitations).

## D19 Cleaning step design (10 Nov 2026; proposal from the audit, E-06 and E-07)

**Question.** How does `02_clean` apply the exclusion rules so that counts and sensitivity checks stay simple?

**Evidence.** Four departures have impossible delays (−1,438, −59, −59 and −54 min: a wrong date or hour in the change time); the largest positive delay is 396 min. The line format does not follow the date exactly (D7, correction note): 2,442 departures from December 2025 on have digit-only lines, 825 earlier ones have a prefix; 1,901 departures have type RB with a line starting with RE.

**Decision.**
- `02_clean` writes **every** planned Würzburg departure and adds a column `exclude_reason` (first matching rule: `bus`, `no_plan_record`, `canceled`, `dst_night`, `invalid_delay`, `duplicate_id`; NULL = modelling row). Nothing is deleted. `cleaning_counts.csv` is the count per reason and split; both sensitivity checks (D9, D18) select their rows by reason.
- A departure delay below −30 minutes is invalid (`invalid_delay`).
- `line_id` is built by format, not by date: a line with a letter prefix is used as it is; a digit-only line gets the train type as prefix. If train type and line prefix disagree, the line prefix wins; the check via `train_number` (D7) stays.

**Implemented (10 Nov 2026).** `src/02_clean.py`, `src/sql/02_clean.sql`, constants `DELAY_THRESHOLD_MIN` and `INVALID_DELAY_BELOW_MIN` in `src/config.py`, tests in `tests/test_clean.py`. Result: 247,716 planned departures, 230,333 modelling rows; excluded 7,290 without timetable record, 6,431 cancelled, 3,607 buses, 51 in DST nights, 4 with invalid delay, 0 duplicates (`reports/checks/cleaning_counts.csv`). One detail was added while implementing: a digit-only line of an ARV row (178 departures, mainly line 8 in August 2026) cannot take the train type as prefix, so it takes the usual prefixed line of the same train number (RE8 or RB8) and falls back to "RE" + digits. The result is 13 regional lines with the same names before and after December 2025; no regional modelling row is without `line_id`. The four services are regional (RE, RB, ARV), long_distance (ICE, IC, EC), night (NJ, EN) and other (UEX, DBK).

**Alternatives considered.** Deleting rows as planned before (each sensitivity check would need its own cleaning run).

**Report.** Data (cleaning rules with counts).

## D20 Definition of through trains (10 Nov 2026; proposal from the audit, E-04)

**Question.** D3 calls a train "through" when it arrives and departs again; the pipeline plan said "has an earlier stop". Which one defines the scenario B rows?

**Evidence.** Modelling rows before 3 Nov 2025: 73,275 with a planned arrival, 67,105 with an earlier stop in the data. Test period: 15,993 and 15,921 (72 differ).

**Decision.** Two columns: `is_through` = planned arrival at Würzburg present; `has_prev_stop` = at least one non-cancelled earlier stop in the data. Scenario B (M-A′, M-B, B3) uses rows where both are true, because its prediction moment is the departure from the previous stop. Through trains without an earlier stop are counted per split and reported.

**Implemented (10 Nov 2026).** In `src/02_clean.py`; an earlier stop counts when its departure is not cancelled and it has a reported time. Modelling rows with both flags: 23,926 (B train), 8,020 (B validation), 15,898 (test). Through trains without a usable earlier stop: 54, 30 and 88 (the 72 above counted any earlier stop, cancelled ones included). In training and validation, through trains are delayed far more often than trains that start at Würzburg (about 36% against 8–9%; `reports/checks/through_train_counts.csv`).

*Correction (10 Nov 2026, EDA):* that gap is a service effect, not an effect of passing through. Almost all long-distance trains pass through (71,650 of 71,855 in training + validation, 49.0% delayed), while most regional trains start at Würzburg. Inside regional trains the difference disappears: 7.4% delayed when passing through against 8.9% when starting here (`notebooks/01_eda.ipynb`, section 3). `is_through` therefore adds little once the service is known, and scenario B results are reported by service.

**Report.** Methodology (scenario B rows).

## D21 Evaluation details (10 Nov 2026; proposal from the audit, E-08 and E-09)

**Decision.**
- **Refit:** the number of trees found by early stopping and the max-F1 threshold are kept unchanged when the final models are refitted on training + validation (A: 152,421 → 198,420 rows; B through trains: 23,946 → 31,977). The report says so; PR-AUC, ROC-AUC and Brier do not depend on the threshold.
- **Tuning budget:** at most 20 hyperparameter settings per model, fixed before the first run.
- **Weather ablation:** M-A is trained once without the weather features and compared on validation. It bounds the limitation that observed weather stands in for a forecast. It is the first item dropped if time is short.
- **Order of work:** features, tuning, SHAP checks, error-analysis code and the dashboard are developed on validation data; the test run is one command at the end (see `CLAUDE.md`, evaluation protocol).

**Implemented (11 Nov 2026).** `src/models.py` (grid of 12 settings, fixed before any tuning result was seen: `num_leaves` 7/15/31/63 × `min_child_samples` 50/200, LightGBM's default, three regularised variants; learning rate 0.05; early stopping on the validation log loss) and `src/05_train.py`. Chosen on validation: M-A and M-A′ `num_leaves=7, min_child_samples=50` (226 and 296 trees), M-B `num_leaves=31, min_child_samples=100, colsample_bytree=0.7, reg_lambda=5` (182 trees). All settings per model: `reports/checks/tuning_*.csv`.

**Validation results (11 Nov 2026; `reports/results_validation.md`, 1,000 day resamples).** These numbers are optimistic for the LightGBM models, because the same validation rows stop the training, choose the setting and choose the threshold; the unbiased comparison is the final test run.

| Rows | Model | PR-AUC [95% CI] | ROC-AUC |
| --- | --- | --- | --- |
| All departures (45,993) | B2 | 0.535 [0.515, 0.557] | 0.800 |
| | M-A | 0.603 [0.583, 0.622] | 0.822 |
| Scenario B rows (8,020) | B3 | 0.877 [0.857, 0.893] | 0.909 |
| | M-A | 0.651 [0.615, 0.683] | 0.789 |
| | M-A′ | 0.664 [0.632, 0.694] | 0.794 |
| | M-B | 0.931 [0.919, 0.941] | 0.942 |

Paired differences (PR-AUC): M-A − B2 = +0.068 [+0.059, +0.077]; M-B − M-A′ = +0.267 [+0.244, +0.292] (effect of the earlier-stop features); M-B − B3 = +0.055 [+0.045, +0.066] (gain over the simple rule); M-A′ − M-A = +0.013 [+0.001, +0.025] (training period; ROC-AUC interval includes zero).

**Weather ablation.** M-A without the six weather features: PR-AUC 0.597 against 0.603; difference +0.006 [+0.002, +0.010]. Weather helps a little; the limitation that observed weather stands in for a forecast therefore costs at most about 0.006 PR-AUC on validation.

**Sanity checks.** M-A ROC-AUC 0.822 (alarm limit 0.95). Shuffled training labels, five shuffles with M-A's setting and tree count, no early stopping: validation ROC-AUC mean 0.477, range 0.443–0.506. *Correction of the check itself:* the first version fitted one shuffled model with early stopping on the true validation labels and gave 0.543; early stopping then picks the iteration that happens to fit the validation labels best, so the check was biased. A single shuffle also scatters around 0.5 because a random function of strong features such as the service still orders the trains; the mean of several shuffles is judged (tolerance ± 0.03).

**Alternatives considered.** Scaling the tree count with the data size (one more assumption for little gain).

**Report.** Methodology (evaluation design), Discussion (limitations).

## D22 Order and scope of the remaining steps (10 Nov 2026; proposal from the audit)

**Question.** How does one working track reach a complete results table as early as possible?

**Decision.**
- **Baselines before enrichment:** `src/evaluate.py` and B0–B2 come directly after cleaning (they need only timetable and calendar columns), so the first end-to-end result exists in week 2. Weather and holidays follow.
- **History features start simple:** delay rate over [D − 29, D − 1 00:00) per `service` × hour and per `line_id` (route group for long-distance trains). The train-number level with its fallback chain (D14) is added only after the first full results table.
- **School holidays:** Bavaria first; neighbouring states only if time allows.
- **Weather** is downloaded once and stored under `data/raw/` (the API can revise values).
- **Earlier stops stay within the monthly file** (D12 unchanged): reading the previous month as well would save the earlier stops of about 32 trains and is not worth a new data run.
- **Freeze in two steps:** minimum version (B0–B3, M-A, M-A′, M-B, results table, test run) by 1 Dec 2026; extensions (SHAP, error analysis, sensitivity checks, dashboard) by 8 Dec 2026; everything by 15 Dec 2026.

**Report.** –

## D23 Enrichment: weather and calendar (11 Nov 2026; proposal)

**Question.** Which weather and calendar information is added, from where, and how is it aligned with the departures?

**Decision.**
- **Weather:** hourly values at the station's location (49.80° N, 9.94° E) from the Open-Meteo archive (reanalysis; CC BY 4.0): temperature, precipitation, wind speed, wind gusts, snowfall, snow depth. Downloaded once in UTC and stored as raw JSON under `data/raw/weather/`; converted to naive local time; the hour that occurs twice when clocks go back is averaged, the hour that does not exist when clocks go forward has no row (D10, corrected). One location only: weather along the route is not used.
- **Public holidays:** Bavaria from the `holidays` package (version in `requirements-lock.txt`), categories public and catholic, so that Mariä Himmelfahrt (15 August) counts, which Würzburg observes.
- **School holidays:** Bavaria only (D22), from the official announcement BayMBl. 2022 Nr. 747, stored in `reference/school_holidays_bavaria.csv` with its source; the school-free Buß- und Bettag is added by its rule.
- **Bridge days:** a working Friday after a public holiday on Thursday, or a working Monday before one on Tuesday.
- The two tables (`weather_hourly.parquet`, `calendar_daily.parquet`) are joined to the departures in step 04, on the local hour and the service date. Observed weather stands in for a forecast in scenario A (limitation; weather ablation in D21).

**Result** (`reports/checks/enrichment_summary.csv`). 853 days, 28 public holidays, 226 school holiday days, 10 bridge days; 20,470 local hours of weather, no missing values, 2 local hours without a row (the clock changes of March 2025 and March 2026); temperature −10.2 to 37.7 °C; 2,965 hours with precipitation, 232 with snowfall. Every modelling departure gets a weather and a calendar row (test).

**Effect on the baseline.** With the three calendar flags, B2 reaches PR-AUC 0.535 and ROC-AUC 0.800 on validation (before: 0.528 and 0.797); B2 − B1 = +0.022 PR-AUC [+0.014, +0.030].

**Alternatives considered.** Weather of the German Weather Service station Würzburg (more exact, more work to parse); neighbouring states' school holidays (if time allows).

**Report.** Data (additional sources), Methodology (features).

## D24 Feature tables (11 Nov 2026; proposal)

**Question.** Which columns do the models get, and how are the history and propagation features built so that the leakage rules hold?

**Decision** (`src/04_features.py`, `src/sql/04_features.sql`, `src/sql/04_features_b.sql`; lists in `src/features_config.py`).

| Group | Columns | Notes |
| --- | --- | --- |
| Timetable | `service`, `line_id`, `destination`, `planned_hour`, `weekday`, `is_through`, `stop_position`, `dwell_min` | `destination` is the final destination and serves as the route group of long-distance trains (D7, D14); `dwell_min` is the planned stop time at Würzburg (missing for trains that start here) |
| Calendar | `is_public_holiday`, `is_school_holiday`, `is_bridge_day` | D23 |
| Weather | `temperature_c`, `precipitation_mm`, `wind_speed_kmh`, `wind_gust_kmh`, `snowfall_cm`, `snow_depth_m` | at the planned departure hour; observed, not forecast |
| History | `hist_rate_service_hour`, `hist_rate_route`, `hist_n_route`, `hist_rate_all` | delay rate over the service dates D − 29 … D − 2 (28 days), i.e. [D − 29, D − 1 00:00); "route" = line for regional trains, destination otherwise; a rate is missing when its window holds fewer than 20 departures (`MIN_HISTORY_ROWS`) |
| Propagation (B only) | `prev_delay`, `prev_delay_2`, `prev_minutes_to_departure`, `prev_stops_between` | last and second-to-last usable earlier stop by planned time (not cancelled, with a reported time) |

- History is computed from modelling rows only, on all periods: for a test-period day it uses the outcomes of earlier test-period days, as a live system would.
- The train-number history key with its fallback chain (D14) is not built yet (D22: only after the first full results table).
- Not included: month or year (the models should not memorise periods; season enters through weather and history), Friday/Sunday evening flags (weekday and hour are given; trees combine them).
- Scenario B rows carry the same scenario A feature values, so M-A′, M-B and B3 are scored on identical rows.

**Result.** `features_a.parquet`: 230,333 rows, 21 features. `features_b.parquet`: 47,844 rows (23,926 train, 8,020 validation, 15,898 test), 25 features. Missing values (`reports/checks/feature_summary.csv`): `dwell_min` 47% in A (trains starting at Würzburg), `line_id` 36% in A (non-regional trains), history rates 0.2–2.1%, `prev_delay_2` 5.5%; weather and calendar never.

*Correction (11 Nov 2026, Data section draft):* `line_id` is missing for 38.6% of the scenario A rows, not 36% (`feature_summary.csv`: 38.58%; 61.4% of the modelling rows are regional trains, `reports/checks/service_counts.csv`). Nothing else changes.

**Safeguards (tests/test_features.py).** History window recomputed by hand; time-travel test on made-up data and on three real days (changing every label from D − 1 on leaves the features of day D unchanged; changing D − 2 does change them); excluded rows do not feed history; the previous stop is the last usable stop and lies before the Würzburg arrival; tables contain exactly the whitelisted columns; no row in two splits; no single scenario A feature reaches ROC-AUC 0.9 on validation (highest: `hist_rate_route` 0.80). Widening the window by one day on purpose makes six tests fail.

**Report.** Methodology (features, leakage safeguards).

## Error analysis on validation: findings (11 Nov 2026)

Not a decision; recorded here because the Results and Discussion sections are written from it. Source: `src/06_error_analysis.py` → `reports/error_analysis_validation.md`, `reports/checks/error_slices_validation.csv`. The same script runs unchanged on the test period after the final run.

- **M-A is more than a service detector, but only for long-distance and night trains.** Inside a service (where the service itself cannot help) M-A reaches ROC-AUC 0.701 for long-distance trains (B2: 0.616), 0.832 for night trains (0.721) and 0.661 for regional trains (0.628). For regional trains the PR-AUC is 0.158 at a base rate of 0.086, and at M-A's overall threshold (0.289) the recall is 0 for 10 of the 11 regional lines: the day before, the model practically never calls a regional train delayed.
- **Bad months are underestimated.** In January 2026 the observed delay rate is 29.4%, the mean prediction 21.7%; in the other validation months they differ by at most 2.5 points. The 28-day history reacts too slowly to a sudden bad period.
- **Weather slices.** Below 0 °C the delay rate is 27.7% (against 21.3%) and the mean prediction 20.8%: frost days are underestimated. Rain or snow in the departure hour makes no difference to the delay rate (22.0% in both).
- **Scenario B, rule against model.** The 6-minute rule B3 is right in 37.4% of the cases when the train was 6–9 minutes late at the previous stop; M-B in 72.7% (454 against 198 wrong predictions among 725 departures). For 10–19 minutes: 80.1% against 90.0%. Below 6 minutes the two are equal. The whole gain of M-B over B3 comes from trains that are moderately late at the previous stop.
- **Scenario B by service.** PR-AUC M-A′ / B3 / M-B: long-distance 0.650 / 0.922 / 0.940; regional 0.151 / 0.670 / 0.764; night 0.868 / 0.901 / 0.947. The en-route information helps regional trains most in relative terms.
- **Calibration.** Expected calibration error 0.017 (M-A) and 0.016 (M-B) without any calibration step; M-A is slightly too low between 40% and 60%, M-B slightly too high between 50% and 70%.
- **The 20 largest errors per model, by failure type.** M-A: all 20 are missed delays of regional trains with a history rate of a few percent (19 of them the two-hourly RE to Nürnberg); 12 were only 6–8 minutes late, 7 were 9–29 minutes late, 1 was 62 minutes late. The day before, nothing distinguishes these departures from the punctual ones of the same train. M-B: 9 missed delays just over the threshold; 6 missed delays that arose after an on-time previous stop (regional trains, previous stop 14–33 minutes before the departure); 3 false alarms where a train 18–34 minutes late at a stop about two hours away made up its delay; 2 false alarms that ended 4–5 minutes late. About half of the worst errors of both models sit within two minutes of the 6-minute threshold, which is a property of a binary target, not of the models.
- **Confusion matrices (validation thresholds).** M-A: 6,734 hits, 3,382 missed delays, 5,929 false alarms. M-B: 2,291 hits, 512 missed, 275 false alarms. B3: 2,352 hits, 451 missed, 682 false alarms.

## D25 Final run: one command, a lock and a rehearsal (11 Nov 2026; proposal)

**Question.** How is "the test period is used once" guaranteed, and how do we know the final code works before it is used?

**Decision** (`src/05_train.py`).
- **One code path, three modes.** `validation` (default): fit on training, score validation. `--final`: settings, tree counts and thresholds from training-only models on validation; refit of all models (baselines included) on training + validation; one scoring of the test period; then the final models are saved under `models/`. `--rehearsal`: the final procedure one step back in time (`REHEARSAL_SPLITS` in `src/config.py`): scenario A trains on Jul 2024 – Jun 2025, validates on Jul – Dec 2025 and is scored on Jan – Jun 2026; scenario B trains on 3 Nov 2025 – Feb 2026, validates on Mar – Apr 2026 and is scored on May – Jun 2026.
- **Lock.** `--final` writes `reports/final_run.json` (time, git commit, thresholds, row counts) and refuses to start when that file exists or when tracked files have uncommitted changes. Outside `--final` no function returns test-period rows (`load_modelling_rows`, `load_sensitivity_rows`; tested).
- **Thresholds** are always the ones chosen on validation rows; they are saved (`reports/checks/thresholds_*.json`) and reused by the error analysis, also on the test scores.
- **Sensitivity checks** (D9, D18) are part of every mode: `src/04_features.py` writes `features_a_sensitivity.parquet` with the scenario A features of cancelled departures and of departures without timetable record; their history comes from modelling rows only.
- After the final run: `python src/06_error_analysis.py --set test`.

**Result of the rehearsal** (`reports/results_rehearsal.md`; the scored rows are the validation rows, but no choice was made on them).

| Rows | Model | Validation mode (optimistic) | Rehearsal (unbiased) |
| --- | --- | --- | --- |
| All departures | B2 | 0.535 | 0.535 |
| | M-A | 0.603 | 0.597 [0.578, 0.616] |
| Scenario B rows | B3 | 0.877 | 0.877 |
| | M-A′ | 0.664 | 0.641 [0.608, 0.673] |
| | M-B | 0.931 | 0.929 [0.916, 0.939] |

PR-AUC. The optimism of the validation numbers is small (0.002–0.006) except for M-A′ (0.023), whose training set is small. The conclusions hold in the rehearsal: M-A − B2 = +0.062 [+0.053, +0.071]; M-B − M-A′ = +0.287 [+0.263, +0.312]; M-B − B3 = +0.052 [+0.042, +0.063]. M-A′ − M-A = −0.002 [−0.017, +0.013]: the training period makes no measurable difference, so the gain of M-B is the earlier-stop information. With fixed validation thresholds, F1 is 0.591 (M-A), 0.806 (B3) and 0.847 (M-B). The chosen settings differ between the modes while the scores barely move: the grid is flat (see `reports/checks/tuning_*.csv`).

**Sensitivity checks on validation** (`reports/results_validation.md`). Counting the 1,009 cancelled departures as delayed raises the delay rate from 22.0% to 23.7%; PR-AUC of M-A 0.603 → 0.607, ROC-AUC 0.822 → 0.811. Adding the 2,426 departures without timetable record: delay rate 23.2%, PR-AUC 0.606, ROC-AUC 0.820. Neither exclusion changes the picture.

**Alternatives considered.** A separate script for the final run (two code paths that can drift apart); no rehearsal (the final code would run for the first time on the test period).

**Report.** Methodology (evaluation design), Results, Discussion (limitations).

---

## Pipeline and checks so far

| Step | Script | Output |
| --- | --- | --- |
| Download and filter | `src/01_download.py`, `src/sql/01_filter_month.sql` | `data/interim/wuerzburg_YYYY-MM.parquet` (88 MB for 28 months; raw files 5 GB); `reports/checks/monthly_summary.csv`, `train_types_by_month.csv`, `line_formats_by_month.csv` |
| Coverage check | `checks/coverage_check.py` | `reports/checks/coverage_by_month.csv` |
| Category check | `checks/category_check.py` | `reports/checks/line_types_over_time.csv` |
| Data quality check | `checks/data_quality_check.py` | `reports/checks/quality_by_month.csv`, `low_count_days.csv`, `coverage_nov_2025_daily.csv`, `suspicious_days.csv` |
| Clean | `src/02_clean.py`, `src/sql/02_clean.sql` | `data/processed/wuerzburg_clean.parquet`, `wuerzburg_prev_stops.parquet`; `reports/checks/cleaning_counts.csv`, `through_train_counts.csv`, `service_counts.csv` (modelling rows per split and service, added 11 Nov 2026 for the Data section) |
| Enrich | `src/03_enrich.py`, `reference/school_holidays_bavaria.csv` | `data/processed/weather_hourly.parquet`, `calendar_daily.parquet`; `reports/checks/enrichment_summary.csv` |
| Features | `src/04_features.py`, `src/sql/04_features.sql`, `src/sql/04_features_b.sql` | `data/processed/features_a.parquet`, `features_b.parquet`; `reports/checks/feature_summary.csv` |
| Evaluation code, baselines and LightGBM | `src/evaluate.py`, `src/baselines.py`, `src/models.py`, `src/05_train.py` (validation only so far) | `reports/results_validation.md` (B0–B3, M-A, M-A′, M-B, weather ablation, sanity checks; 1,000 day resamples); `reports/checks/tuning_*.csv` |
| EDA | `notebooks/01_eda.ipynb` (training and validation period only) | `reports/figures/eda_*.png` (12 figures) |
| Error analysis | `src/06_error_analysis.py`, `src/plot_style.py` | `reports/error_analysis_validation.md`, `reports/checks/error_slices_validation.csv`, `reports/figures/errors_*_validation.png` |
| Tests | `tests/test_leakage.py`, `test_config.py`, `test_data.py`, `test_filter_sql.py`, `test_clean.py`, `test_evaluate.py`, `test_enrich.py`, `test_features.py`, `test_models.py`, `test_error_analysis.py`, `test_final_run.py` | 136 passing (11 Nov 2026) |
| Independent audit | – | `docs/audit_2026-11-10.md` |

## Sources

- Deutsche Bahn Data, Hugging Face: https://huggingface.co/datasets/piebro/deutsche-bahn-data (CC BY 4.0)
- Deutsche Bahn, "Erläuterung Pünktlichkeitswerte" (definition of punctuality on arrivals): https://www.deutschebahn.com/de/konzern/konzernprofil/zahlen_fakten/puenktlichkeitswerte-1187696
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
