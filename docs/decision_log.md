# Decision log: data and method decisions

Purpose: a chronological record of every data and method decision, with the question, the evidence, the decision and where it goes in the report. Every number here is traceable to a script and an output file in this repository. The report's Data and Methodology sections are written from this log.

How to add an entry: copy the template at the end, give it the next number, link the script and the output file. One entry per decision, written when the decision is made.

Status: 7 Nov 2026, end of week 1 (data acquisition and data checks complete; cleaning step next).

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

**Evidence.** First data check on Oct 2026 and Mar 2025 (`check_db.py`, outside the repository): 12,975 Würzburg rows in Oct 2026, ~430 stops per day, no gaps, 0.2% missing delay values, 20.2% of stops departing 6+ min late, 0 duplicate ids.

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

**Not taken on faith.** LightGBM is only called better if its test PR-AUC is above B2's with non-overlapping 95% bootstrap confidence intervals. Alternatives considered: XGBoost/CatBoost (same family, no clear advantage), Random Forest (usually slightly weaker), neural networks (more effort, harder to explain, no expected gain on this data).

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
