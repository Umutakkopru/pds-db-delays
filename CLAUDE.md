# Predicting Train Delays at Würzburg Hbf — Project Context & Plan

Last updated: 6 Nov 2026 · PDS Group 18

## How to use this document

This is the single source of truth for our Practical Data Science (PDS) capstone. Paste or attach it at the start of any session with an AI assistant (Claude, ChatGPT, Claude Code) before asking for help with code, the proposal, the report or the slides.

**Instructions for the AI assistant reading this:**

- Treat the decisions in this document as fixed unless we explicitly ask to change them.
- Prefer the simplest solution that satisfies the assignment.
- Respect the leakage rules, the leakage safeguards and the watch-list in every piece of code you suggest. When you write feature or split code, add or update the matching automated check in `tests/test_leakage.py`.
- Use Python, DuckDB (SQL), pandas, scikit-learn, LightGBM, SHAP and Streamlit unless we ask otherwise.
- Report, code comments and slides are in English.
- This document contains only project facts and decisions. Do not add personal goals, career plans or private details of team members to it, to the report or to the slides.
- Individual members may keep personal instructions in `CLAUDE.local.md` (not in Git); those apply only to that member's sessions.

## Project at a glance

| Item | Value |
| --- | --- |
| Course | Practical Data Science, Information Systems M.Sc., Uni Würzburg, WiSe 2026/27 |
| Task | Own end-to-end ML project, group of 3 |
| Group | Group 18; two members confirmed, third member being recruited |
| Topic | Predicting train departure delays at Würzburg Hbf |
| Target | Departure delay ≥ 6 min (binary classification) |
| Data | Deutsche Bahn Data archive, CC BY 4.0, ~360,000 rows for Würzburg Hbf (Jul 2024 – Oct 2026) |
| Core models | Rule-based baseline, logistic regression, LightGBM |
| Committed extras | DuckDB/SQL pipeline, Streamlit dashboard (deployed), SHAP |
| Team goal | Finish code by end of November and everything by 20 December |
| Status (6 Nov 2026) | Topic chosen, data checked, plan written; coverage check done, scenario B split decided (train from Nov 2025) |

## Decisions and requirements so far

We chose Deutsche Bahn delays after comparing about a dozen candidate topics, because the data is easy to understand, openly licensed and already verified.

**How the topic was chosen (4 Nov 2026):**

1. Criteria: a clear prediction target, enough data, a clean license, no textbook dataset, practical relevance, and above all **data that is easy to understand** and quick to work with.
2. Considered and rejected: Uber/Lyft prices (target almost fully explained by distance), French bakery sales (too small), ImmoScout24 rents (very common on Kaggle), NYC restaurant inspections (leakage-prone), BASt Autobahn counts and the energy register MaStR (hard-to-read formats).
3. Shortlist: Munich bicycle counters, German electricity demand (OPSD/SMARD) and Deutsche Bahn delays. DB delays won on interest and grade potential; electricity demand stays as the fallback topic.
4. Data check run on the October 2026 and March 2025 files; results in the Data section.

**Team requirements (fixed):**

- Finish on the timeline below, with at least a passing and ideally a good grade.
- Keep everything easy to understand; no exotic tools.
- **The SQL pipeline (DuckDB) and the Streamlit dashboard are committed**, as long as they stay within the scope described below.
- Each member documents their own AI use from day one (see GenAI documentation).

## Assignment brief: key facts

To pass, we need a baseline plus at least one more approach, implemented with sufficient care; everything else raises the grade.

**Deadlines.**

| What | When |
| --- | --- |
| Group registration (3 members) via "Capstone Project Groups" | 15 Nov 2026, 23:59 (no group = no participation) |
| Topic proposal, max. 2 pages, via "Topic Proposal" | 30 Nov 2026, 23:59 |
| Supervisor feedback; no feedback means accepted | by 7 Dec 2026 |
| Final PDF report and code | To confirm in the course room (last year 31 January) |
| Presentation | Last lecture week; lectures end 5 Feb 2027 |

**Proposal must contain:** group members (name, matriculation number), working title and problem statement, dataset (source, size, license), target variable and evaluation metric, planned baseline and modelling approaches.

**Required subgoals:** problem definition and motivation; EDA; clean, reproducible data pipeline; simple interpretable baseline; at least one more advanced approach; evaluation on a held-out test set with suitable metrics and error analysis.

**Optional extensions in the brief:** domain feature engineering or extra data sources; explainability (SHAP, LIME); prototype app or dashboard; systematic hyperparameter optimisation or robustness analysis.

**Report format:** scientific paper structure using the chair's template, 15–20 pages of main text (excluding title page, tables of contents, references, appendix), consistent citations, one final PDF that may link to notebooks or a documented GitHub repository. Mandatory sections: **Use of generative AI** (which parts, which prompts) and **Contributions** (role of each member).

**Grading criteria:** clarity and relevance of the problem; data preparation and EDA; variety and appropriateness of models; originality; methodological rigour (splits, leakage, metrics) and performance against the baseline; documentation of failures, improvements and next steps; code and report documentation and template adherence; presentation quality; dashboard functionality if implemented.

## Dataset and data check

The open [Deutsche Bahn Data](https://huggingface.co/datasets/piebro/deutsche-bahn-data) archive is clean, large enough and confirmed to cover Würzburg Hbf; nothing blocks the project.

**Source.** Collected from DB's public timetable API several times a day; one Parquet file per month in `monthly_processed_data/data-YYYY-MM.parquet` ([project page](https://github.com/piebro/deutsche-bahn-data)). The ~100 largest stations are covered from July 2024, all stations from November 2025 (confirmed by our own coverage check, finding 6). License CC BY 4.0 (Deutsche Bahn). One month for all of Germany is ~15.2 million rows; one row = one train at one station on one day.

**Actual columns** (the GitHub README is outdated; these are the real names):

| Column | Meaning | Use |
| --- | --- | --- |
| `station_name`, `xml_station_name`, `eva` | Station name and ID | Filter: `station_name = 'Würzburg Hbf'` |
| `train_type`, `line_number`, `train_number` | ICE, RE, RB, ARV, NJ…; line such as RB53 | Features |
| `final_destination_station` | Final stop of the train | Feature |
| `arrival_planned_time`, `departure_planned_time` | Timetable times | Features, split, target |
| `arrival_change_time`, `departure_change_time` | Actual or updated times | Target only, never features |
| `delay_in_min` | Departure delay where a departure exists | Check only |
| `time` | Event timestamp | Fallback date |
| `arrival_is_canceled`, `departure_is_canceled` | Cancellation flags | Filter |
| `train_line_ride_id`, `train_line_station_num` | Scheduled-run ID and stop order | Join earlier stops |
| `has_plan_record`, `is_additional_stop`, `is_replacement_train`, `replaced_train_*` | Data-quality flags | Filter |

**Check results (Würzburg Hbf).**

| Check | Result |
| --- | --- |
| Rows per month | 12,975 (Oct 2026), 13,174 (Mar 2025); ~430 stops per day |
| Daily continuity | Median ~436 rows/day; lowest days are weekends and 3 Oct holiday; no gaps |
| Missing delay values | 0.2% |
| Stops delayed 6+ min (cancelled excluded) | 20.2% |
| Cancelled stops | 1.1% |
| Duplicate IDs | 0 |
| Both planned times missing | 22 rows (0.2%) |
| `has_plan_record` = False | 411 rows (3.2%) |
| Delay range | −17 to 396 min; median 1, mean 5.2 |

**Share of stops departing 6+ min late by train type (Oct 2026, cancelled excluded).** ICE trains are delayed about four times as often as RB trains.

| Train type | Delayed 6+ min | Stops (n) |
| --- | --- | --- |
| NJ (Nightjet) | 80.2% | 249 |
| ICE | 42.6% | 2,919 |
| ARV | 16.3% | 2,283 |
| RE | 11.5% | 3,802 |
| RB | 9.7% | 3,681 |
| All stops | 20.2% | – |

**Findings that shape the design:**

1. **`delay_in_min` is the departure delay:** it matches the departure time difference in 100% of rows, the arrival difference in only 61.9%. We compute our own target.
2. **`train_line_ride_id` identifies a scheduled run, not one day's trip:** the same ID appears on every day of the month. Earlier stops are joined by ride ID plus service date; trips can cross midnight.
3. **~33% of planned arrival or departure times are empty by design:** trains that start or end at Würzburg.
4. **Delays propagate along a route:** on 6 Oct 2026 an RB53 was 18 min late at Oberhaid and still 13 min late at Würzburg Hbf.
5. **Rare train types** (IC, DZ, bus, UEX) will be grouped as Other; the Nightjet rate rests on only 249 stops.
6. **Earlier-stop coverage is incomplete before November 2025 (confirmed by `coverage_check.py`, 6 Nov 2026):** the archive contains 107–108 stations until October 2025 and ~5,300 from November 2025. Before November 2025 the directly preceding stop is missing for 100% of RB and RE trains arriving at Würzburg; the only earlier stop in the data is a distant large station (e.g. Bamberg, 14 stops before Würzburg for the RB53). ICE and NJ are covered in both periods. This affects only scenario B; see Split.

**Coverage check results** (trains arriving at Würzburg and departing again; share with the directly preceding stop in the data):

| Train type | Jul 2024 | Mar 2025 | Oct 2025 | Nov 2025 | Oct 2026 |
| --- | --- | --- | --- | --- | --- |
| Stations in file | 108 | 107 | 107 | 5,295 | 5,245 |
| ICE | 99.9% | 98.1% | 99.4% | 99.8% | 99.9% |
| RB | 0.0% | 0.0% | 0.0% | 93.1% | 100.0% |
| RE | 0.0% | 0.0% | 0.0% | 93.5% | 100.0% |
| NJ | 98.3% | 96.7% | 99.2% | 97.4% | 95.9% |

7. **Most regional trains start or end at Würzburg:** in October 2026 only 743 of 3,681 RB stops and 464 of 3,802 RE stops belong to trains that arrive and depart again; no ARV train in the five sample months passes through Würzburg. Scenario B (earlier stops) therefore applies only to through trains (mainly ICE, NJ and part of RB/RE). Trains that start at Würzburg have no earlier stops; for them scenario B equals scenario A.
8. **Categories change over time:** `line_number` is "53" until at least November 2025 and "RB53" in October 2026, and train types may appear or disappear (e.g. ARV). Line numbers are normalised in the cleaning step, and `01_download.py` writes per-month train-type and line-format tables to `reports/checks/` so such changes are visible before modelling.

When an earlier stop exists, its delay information exists too. `train_line_station_num` numbers the full route (Bamberg 1, Würzburg Hbf 15 for the RB53 even when the stops in between are missing), so gaps in the numbering show missing stations.

## Problem definition

**Goal in one sentence:** for every train departing Würzburg Hbf, predict the probability that it departs 6 or more minutes late, both before the trip and while the train is en route, and compare the two.

**Target.** `delayed = 1` if `departure_change_time − departure_planned_time ≥ 6 min`, else 0. Trains that end at Würzburg (no departure) are excluded from the main target.

**Why 6 minutes.** It is Deutsche Bahn's official punctuality threshold: a train counts as punctual if it is less than 6 minutes late. The threshold is therefore defensible, not arbitrary.

**Why classification first, not delay minutes.** The delay distribution is highly skewed (median 1 min, mean 5.2 min, maximum 396 min). A regression model would be dominated by rare extreme delays and its error would be hard to interpret. The passenger's real question is binary ("will I make my connection?"). Delay minutes remain an optional secondary regression task; a three-class variant (0–5, 6–15, 16+ min) is a possible extension.

**Scope.** Würzburg Hbf; ICE, RE, RB, ARV, NJ and Other. Cancelled stops and stops without a timetable record are excluded and reported separately.

**Two prediction scenarios.** The moment of prediction decides which information is allowed.

| Scenario | Question | Allowed information |
| --- | --- | --- |
| A: Before the trip | Asked the day before | Timetable, train type, line, destination, calendar, holidays, weather, historical delay rates |
| B: En route | Asked when the train leaves its previous stop | Everything in A, plus the delay at stops the train has already passed |

Comparing A and B answers a research question of its own: how much of a delay is predictable in advance, and how much builds up on the way?

**Metrics.** Main: PR-AUC and ROC-AUC (PR-AUC matters because only 20% are positive). Also F1, precision and recall at a chosen threshold, and the Brier score for probability quality. Regression variant: MAE. Every model is compared with the baselines.

**Realistic expectation.** Scenario A will reach only moderate scores; scenario B should be clearly better. A scenario A ROC-AUC above about 0.95 would signal leakage, not success.

## Methodology

A DuckDB/SQL pipeline turns ~28 monthly files into one clean Würzburg table; models are then trained and compared on a strictly chronological split.

**Pipeline** (one script per step, rerunnable with a single command, e.g. `python run_pipeline.py`):

1. **Download and filter** (`01_download.py`, SQL in `src/sql/01_filter_month.sql`): per month, download the Parquet file to `data/raw/` (kept for reruns; `--delete-raw` removes it), keep Würzburg Hbf rows plus the earlier stops of the same trips (`row_role`, `wuerzburg_id` link each earlier stop to its Würzburg row), save a small Parquet file to `data/interim/`; afterwards write per-month checks to `reports/checks/`.
2. **Clean** (`02_clean.sql` / `.py`): drop cancelled stops, rows without a timetable record and rows with no planned time; compute departure delay; assign a service date per trip, handling midnight; normalise line numbers ("53" → "RB53"); group rare train types.
3. **Enrich** (`03_enrich.py`): join hourly weather for Würzburg (DWD or Open-Meteo), public holidays (Bavaria) and school holidays (Bavaria and neighbouring states).
4. **Features** (`04_features.sql`): build scenario A and B feature tables with SQL window functions, using only information available at prediction time.
5. **Train and evaluate** (`05_train.py`): fixed random seeds; all results written to one results table and figures folder.

**Features.**

| Group | Examples | Scenario |
| --- | --- | --- |
| Timetable | Train type, line, destination, planned hour, weekday, stop position in route | A, B |
| Calendar | Public holiday, school holiday, bridge day, Friday and Sunday evening peaks | A, B |
| Weather | Temperature, precipitation, wind speed, snow | A, B |
| History | Delay rate of this line and train over the previous 4 weeks, past data only | A, B |
| Propagation | Delay at the previous stop and two stops before; planned minutes from that stop to Würzburg; number of stops between (from `train_line_station_num`) | B only |

**Split.** Chronological, never random. The test period is the same for both scenarios, so A and B can be compared on identical rows.

| Scenario | Train | Validation | Test |
| --- | --- | --- | --- |
| A | Jul 2024 – Dec 2025 (18 months) | Jan – Jun 2026 (6 months) | Jul – Oct 2026 (4 months) |
| B (decided 6 Nov 2026) | Nov 2025 – Apr 2026 (6 months) | May – Jun 2026 (2 months) | Jul – Oct 2026 (4 months) |

Why this date range:

- **Start July 2024:** the earliest month the archive covers Würzburg Hbf; more history means more training data and two full winters (2024/25, 2025/26), which matter for weather-related delays. If the first month is incomplete, training starts in August 2024.
- **End October 2026:** the last complete month at the time of the plan. November 2026 is not used, so the dataset stays fixed for the whole project.
- **Validation Jan – Jun 2026 (scenario A):** contains winter and spring, so tuning sees bad-weather conditions.
- **Test Jul – Oct 2026:** the most recent data, which mimics real use (train on the past, predict the future). Limitation: the test period has no winter months; reported in the Discussion, and season effects are checked on the validation set.

Why scenario B has its own split: the propagation features need the train's earlier stops. The coverage check (Dataset finding 6) showed that before November 2025 the directly preceding stop is missing for every RB and RE train; the only earlier stop is a distant origin station, which carries a different and much weaker signal. Training scenario B on that period would teach the model a pattern that changes abruptly in November 2025 and does not exist in the test period. Scenario B therefore trains from November 2025, when coverage is complete. The training period still contains a winter (Nov 2025 – Feb 2026). November 2025 has slightly lower coverage (~93% for RB/RE), probably a ramp-up in the first days; if a daily check shows a clear start date, training begins on that date. The coverage table goes into the Data section as evidence of the decision.

**Models.**

- **Baseline 1 (rule-based):** historical delay rate of the train type × hour-of-day cell.
- **Baseline 2 (interpretable):** logistic regression on timetable and calendar features.
- **Main model:** LightGBM, tuned on the validation set (small grid or Optuna, time-boxed).
- **Optional:** regression on delay minutes; one extra tree model (Random Forest) as a sanity comparison.

**Why LightGBM as the main model** (answer for the proposal, report and presentation):

1. **The data is tabular** (one row per train departure, a few dozen columns). Gradient-boosted trees are the standard and usually strongest choice for tabular data; benchmarks show they generally match or beat deep learning on such data at a fraction of the effort (Grinsztajn et al., 2022, *Why do tree-based models still outperform deep learning on tabular data?*).
2. **Interactions without manual work:** delay risk depends on combinations (ICE × Friday evening × rain). Logistic regression only sees such combinations if we build them by hand; trees learn them.
3. **Missing values and categories handled natively:** earlier-stop features are missing for trains that start at Würzburg, and train type, line and destination are categorical. LightGBM handles both directly.
4. **Fast:** a few seconds per fit on ~360,000 rows on a laptop, so tuning and repeated runs are cheap.
5. **Explainable:** SHAP's TreeExplainer gives exact explanations for tree models, needed for the report and the dashboard.

The choice is not taken on faith: model settings are chosen on validation only, then all models are scored once on the same test rows, and LightGBM is only called the better model if its test PR-AUC is above B2's and the 95% bootstrap confidence intervals do not overlap. Alternatives considered: XGBoost and CatBoost (same family, similar accuracy, no clear advantage for this project), Random Forest (usually slightly weaker, kept as an optional check), neural networks and sequence models (more effort and harder to explain, with no expected gain on this data size and structure).

**Leakage rules** (also in the report):

1. `arrival_change_time`, `departure_change_time` and `delay_in_min` at Würzburg are never features.
2. Historical delay rates use only data strictly before the prediction date.
3. In scenario B, only stops the train has already passed count.
4. Scalers, encoders and target encodings are fitted on the training set only.
5. Weather: observed weather stands in for a forecast; named as a limitation.

**Leakage safeguards** (automated where possible, so leakage is caught even if nobody notices it by eye):

1. **Feature whitelist:** `src/features_config.py` lists the allowed feature columns per scenario. Models use only these columns; any other column is ignored.
2. **Automated tests** (`tests/test_leakage.py`, run with `pytest` before every training run):
   - no forbidden column (change times, `delay_in_min`, `dep_delay`, `delayed`, any column derived from them at Würzburg) is in the feature list;
   - train, validation and test date ranges do not overlap and are in the right order;
   - history features at date D are identical when recomputed from data truncated at D − 1 ("time-travel test");
   - in scenario B, every earlier stop used has a planned departure before the Würzburg planned departure.
3. **Sanity checks on results:**
   - single-feature check: each feature alone should reach clearly below ROC-AUC 0.9; a feature that predicts the target almost perfectly is investigated;
   - shuffled-target check: training on a randomly shuffled target must give ROC-AUC ≈ 0.5;
   - validation and test scores should be in the same range; a large gap is investigated;
   - SHAP top features must make domain sense (e.g. train type, hour, previous-stop delay), not IDs or timestamps.
4. **Second pair of eyes:** feature and split code is reviewed by a second member before training; an AI review with the prompt "Check this code for data leakage against the leakage rules in CLAUDE.md" is used in addition, not instead.

## Evaluation process

Evaluation happens on two levels: the course grades our deliverables, and we evaluate our models with a fixed protocol whose results feed the report.

### A. How the course grades the project

**Deliverables that are graded:** the two-page proposal (gate: accepted unless feedback by 7 Dec), one final PDF report in the chair's template, the code (GitHub repository and/or notebooks linked from the PDF), the presentation in the last lecture week, and the dashboard (graded if implemented).

**Pass condition:** at least the baseline and one additional approach, implemented with sufficient care. Weights of the criteria are not published; we treat them as equal.

| Grading criterion | Evidence we provide | Where |
| --- | --- | --- |
| Clarity and relevance of the problem | One-sentence goal, DB 6-min threshold, two scenarios, passenger use case | Introduction |
| Data preparation and EDA | Data check table, cleaning rules, coverage check, EDA figures (by type, hour, month, propagation) | Data |
| Variety and appropriateness of approaches | Rule-based baseline, logistic regression, LightGBM with justification; scenario A vs. B | Methodology, Results |
| Originality | Propagation features, scenario comparison, weather and school holidays, connection check | Methodology, Discussion |
| Methodological rigour and performance vs. baseline | Chronological split, leakage rules and automated safeguards, PR-AUC, test set used once, results table | Methodology, Results |
| Failures, improvements, next steps | Error slices, top errors, limitations, next steps | Discussion |
| Documentation of code and report | README, docstrings, one-command pipeline, tests, template adherence, citations | Repository, whole report |
| Presentation | 10-minute talk, live demo plus recorded backup | Slides |
| Dashboard functionality | Deployed Streamlit app with SHAP explanation | Results, appendix link |
| GenAI use and contributions (mandatory sections) | Members' AI-use logs merged into a table; role table | Dedicated sections |

### B. How we evaluate our models

**Protocol.**

1. **Split:** as in the Split table. Tuning, feature choices and threshold selection use validation only.
2. **Test set:** evaluated once, at the very end, for all models at the same time. No changes after looking at test results.
3. **Same rows for all models:** every model is scored on exactly the same test rows. Scenario A is reported on all departures. Scenario B is reported on the through-train subset (trains with at least one earlier stop, finding 7), and scenario A is also reported on that subset, so the A-vs-B comparison uses identical rows.

**Models compared.**

| ID | Model | Purpose |
| --- | --- | --- |
| B0 | Always "on time" (majority class) | Shows why accuracy is misleading (~80% accuracy with zero skill) |
| B1 | Historical delay rate of train type × hour | Rule-based baseline required by the brief |
| B2 | Logistic regression, timetable + calendar features | Interpretable baseline |
| M-A | LightGBM, scenario A features | Main model, before the trip |
| M-B | LightGBM, scenario B features | Main model, en route |

**Metrics** (all computed on the positive class "delayed ≥ 6 min"):

| Metric | Role |
| --- | --- |
| PR-AUC (average precision) | Primary metric; robust with 20% positives |
| ROC-AUC | Secondary ranking metric, widely understood |
| F1, precision, recall | At a threshold chosen on validation (max F1); also reported at 0.5 |
| Brier score + reliability diagram | Quality of predicted probabilities (needed for the dashboard) |
| Accuracy | Reported only next to B0, to show its limits |
| MAE (minutes) | Only for the optional regression variant |

**Uncertainty.** 95% bootstrap confidence intervals (1,000 resamples) for PR-AUC and ROC-AUC on the test set, so differences between models are not over-interpreted.

**Error analysis.** Confusion matrix at the chosen threshold; metrics sliced by train type, hour of day, weekday, month, holiday vs. normal day and weather (rain, wind, snow, heat); the 20 largest errors inspected by hand and grouped into failure types (e.g. disruptions invisible in the data, first train of the day, rare train types).

**Explainability.** SHAP: global importance (summary plot) for M-A and M-B, plus per-prediction explanations reused in the dashboard.

**Results table template** (`reports/results.md`, filled by `05_train.py`):

| Model | Scenario | PR-AUC [95% CI] | ROC-AUC [95% CI] | F1 | Precision | Recall | Brier |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 Majority | – |  |  |  |  |  |  |
| B1 Rule-based | A |  |  |  |  |  |  |
| B2 Logistic regression | A |  |  |  |  |  |  |
| M-A LightGBM | A |  |  |  |  |  |  |
| M-B LightGBM | B |  |  |  |  |  |  |

**Success criteria.**

- **Pass:** B1, B2 and M-A trained and evaluated correctly on the chronological split, with a documented results table.
- **Good grade:** M-A beats B2 on PR-AUC; M-B clearly beats M-A; error analysis and SHAP documented; dashboard deployed.
- **Red flag:** scenario A ROC-AUC above ~0.95, a failed leakage test, or any model far above the others without a clear reason → stop and run the leakage safeguards.

## Committed: SQL pipeline and Streamlit dashboard

Both are part of the plan, not optional, because they make the work easier rather than harder and serve the grading criteria (reproducible pipeline, dashboard functionality).

**SQL (DuckDB).** DuckDB queries Parquet files directly from Python without loading them into memory, so filtering 15 million rows per month is a single SQL statement. SQL is used for:

- filtering each month to Würzburg Hbf and the earlier stops of its trips;
- cleaning rules and the service-date assignment;
- history features with window functions (e.g. delay rate per line over the previous 28 days);
- joining earlier stops for scenario B.

No database server, no extra setup: DuckDB is a `pip install`. Modelling stays in Python.

**Streamlit dashboard.** Scope is fixed in three levels; levels 1 and 2 are committed, level 3 only if time allows.

| Level | What | Effort | Status |
| --- | --- | --- | --- |
| 1 | App: choose a train or line, date and hour → delay probability (scenario A), optional previous-stop delay input (scenario B), SHAP explanation of the prediction | 1–2 days | Committed |
| 2 | Deploy on Streamlit Community Cloud with a public link | ~half a day | Committed |
| 3 | Connection check: probability of catching a transfer at Würzburg (e.g. ICE to RE with 7 min) | ~1 day | If time allows |

The app loads a saved model and a small lookup table, never the raw data, so it stays fast and deployable. Not planned: FastAPI, a separate frontend, user accounts or live API calls; they add effort without improving the grade.

## Other extensions

The minimum version (baselines, LightGBM, evaluation) comes first; extensions start only after it runs end to end.

| Extension | What we do | Criterion | Priority |
| --- | --- | --- | --- |
| Scenario A vs. B | Same model with and without earlier-stop delays | Originality, discussion | Core |
| Weather and holiday features | Hourly weather; Bavarian and neighbouring school holidays | Feature engineering | Core |
| SHAP | Global importance plus per-prediction explanations (reused in the dashboard) | Explainability | Core |
| Error analysis | Largest errors by train type, hour, weather, day type; typical failure cases | Failure documentation | Core |
| Calibration and robustness | Reliability diagram; performance by season (validation) and weather extremes | Rigour | If time allows |
| Random Forest check | Same features as M-A; confirms the LightGBM choice | Variety of models | If time allows |
| Regression or three-class variant | Delay minutes, or 0–5 / 6–15 / 16+ min | Variety of models | If time allows |

## Timeline

All code is planned to be finished and frozen by 1 December and the whole project by 20 December; January is buffer only.

| Phase / milestone | Dates |
| --- | --- |
| Setup and data pipeline, coverage check | 4 – 10 Nov 2026 |
| EDA, baselines, proposal draft | 11 – 17 Nov |
| ◆ Group registration (hard deadline) | 15 Nov |
| LightGBM A and B, evaluation | 18 – 24 Nov |
| ◆ Proposal submitted (official deadline 30 Nov) | ~20 Nov |
| SHAP, error analysis, dashboard | 25 Nov – 1 Dec |
| ◆ **Results frozen** | 1 Dec |
| ◆ Proposal feedback due | 7 Dec |
| Report writing | 2 – 15 Dec |
| Slides, final PDF | 16 – 20 Dec |
| Buffer | 21 Dec – 31 Jan 2027 |
| Presentation week | 1 – 5 Feb 2027 |

The proposal goes in around 20 November, so any feedback (due by 7 December) arrives while modelling is still open. The only fixed dates are group registration (15 Nov), proposal (30 Nov), feedback (7 Dec) and the presentation in the last lecture week (lectures end 5 Feb 2027).

## To-do list in chronological order

Each week ends with a working result; nothing moves to the next week half done.

**Week 1 — setup and data (until 10 Nov 2026)**

- [ ] Recruit the third member (needed for registration on 15 Nov)
- [x] Repository scaffold: folders, `README.md`, `requirements.txt`, `.gitignore`, `pytest.ini`, `src/config.py`, `run_pipeline.py`
- [ ] Push the repository to GitHub and add the team as collaborators
- [x] Write `01_download.py` and `src/sql/01_filter_month.sql`
- [x] Run `01_download.py` for October 2026 with `--show-example`: 12,975 Würzburg rows, 82,842 earlier-stop rows, RB53 shows its 14 earlier stops (6 Nov 2026)
- [ ] Run `01_download.py` for July 2024 – October 2026
- [ ] Review `reports/checks/`: daily row counts per month (note incomplete months), train types by month (when does ARV appear?), line-number formats by month
- [x] `src/features_config.py` (forbidden columns, empty whitelist) and `tests/test_leakage.py` (forbidden columns, split order, same test period, scenario B start)
- [x] **Coverage check** (`coverage_check.py`, 5 sample months): scenario B split decided (train from Nov 2025)
- [ ] Daily coverage check for November 2025 only: find the exact start date of full station coverage
- [ ] Write the cleaning step and save `wuerzburg_clean.parquet`

**Week 2 — EDA, baselines, proposal (until 17 Nov 2026)**

- [ ] Register the group by 15 Nov 2026 (hard deadline)
- [ ] EDA notebook: delay distribution, by train type, hour, weekday, month; propagation example; coverage figure
- [ ] Weather and holiday join
- [ ] Baseline 1 (rule-based) and baseline 2 (logistic regression) on the chronological split
- [ ] Draft the two-page proposal from this document
- [ ] Write the Data section draft while the EDA is fresh

**Week 3 — main model (until 24 Nov 2026)**

- [ ] Submit the proposal around 20 Nov 2026 (official deadline 30 Nov)
- [ ] Scenario A and B feature tables (`04_features.sql`); add time-travel and earlier-stop tests
- [ ] LightGBM for A and B; time-boxed tuning on validation
- [ ] Sanity checks: single-feature AUC, shuffled target
- [ ] Results table: baselines vs. LightGBM, A vs. B (PR-AUC, ROC-AUC, F1, Brier)
- [ ] Write the Methodology section draft (incl. why LightGBM, split rationale, leakage safeguards)

**Week 4 — extensions and dashboard (until 1 Dec 2026)**

- [ ] SHAP global and per prediction
- [ ] Error analysis and failure cases
- [ ] Streamlit app level 1, then deploy (level 2)
- [ ] Final run on the test set, once
- [ ] **Freeze results and figures**; no new features after this point

**Weeks 5–6 — report (until 15 Dec 2026)**

- [ ] Write Results, Discussion, Introduction, Related work, Conclusion in the chair's template
- [ ] Use of generative AI and Contributions sections from the members' AI-use logs
- [ ] Clean the repository: README with setup and run instructions, docstrings
- [ ] Cross-review: each member reads one other member's sections

**Week 7 — slides and finish (until 20 Dec 2026)**

- [ ] 10-minute presentation (format to confirm) with a live dashboard demo and a recorded backup
- [ ] Final PDF export and check against the template
- [ ] Submit as soon as the submission is open

**January – early February:** buffer only; rehearse the presentation once before the last lecture week.

## Roles and report structure

Each member owns one workstream end to end and reviews one other member's work.

| Member | Owns | Report sections |
| --- | --- | --- |
| Member 1 | DuckDB/SQL pipeline, cleaning, coverage check, EDA, weather and holiday joins, Streamlit dashboard and deployment | Data, dashboard |
| Member 2 | Baselines, LightGBM, tuning, evaluation, leakage tests, error analysis | Methodology, Results |
| Member 3 | SHAP, related work, slides, report assembly in the template | Related work, explainability |
| All | Proposal, introduction, discussion, conclusion, cross-review | Introduction, Discussion, Conclusion |

Names are assigned in the Contributions section of the report, not in this document.

Report in the chair's template, 15–20 pages of main text:

| Section | Pages |
| --- | --- |
| 1. Introduction: problem, motivation, research questions | 1.5–2 |
| 2. Related work: train delay prediction | 2–3 |
| 3. Data: source, license, data check, coverage, EDA | 3–4 |
| 4. Methodology: pipeline, features, split, models, leakage rules and safeguards | 3–4 |
| 5. Results: models vs. baselines, scenario A vs. B, SHAP, dashboard | 2–3 |
| 6. Discussion: error analysis, limitations, next steps | 2–3 |
| 7. Conclusion | 0.5–1 |
| Use of generative AI; Contributions (both mandatory) | Check the template |

Code lives in one documented GitHub repository linked from the PDF.

## Risks and mitigations

No risk threatens a pass; the main ones cost effort or points, and each has a fallback.

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Supervisor requests changes to the proposal | Low | Medium | Submit early (~20 Nov); work done so far (data, EDA) stays reusable; no feedback by 7 Dec = accepted |
| Third member not found by 15 Nov | Medium | High | Reply to the group-search emails now; post in the course forum |
| Monthly files large (download time, disk) | Low | Low | ~5 GB in total; raw files kept in `data/raw/` (gitignored), `--delete-raw` if disk gets tight |
| Categories change over time (line format, new train types such as ARV) | Confirmed | Medium | Per-month check tables from `01_download.py`; normalise line numbers in cleaning; train types missing in the training period are named in the error analysis |
| First months incomplete | Medium | Low | Check daily counts; start in August 2024 if needed |
| Earlier stops missing before Nov 2025 | Confirmed | Medium | Scenario B trains from Nov 2025 only; coverage table reported in the Data section |
| Joining earlier stops goes wrong (ride ID per schedule, midnight trips) | Medium | Medium | Ride ID + service date; validate on the RB53 example |
| Data leakage | Medium | High | Leakage rules, feature whitelist, automated tests, sanity checks, code review by a second member |
| Scenario A scores modestly | High | Low | Expected; reported as a finding; scenario B carries performance |
| Dashboard grows beyond scope | Medium | Medium | Fixed three levels; level 3 only after the report draft exists |
| Report left to the end | Medium | High | Write each section in the week its work is done |
| Fallback needed | Low | High | German electricity demand (OPSD/SMARD), same pipeline pattern |

## Watch-list while working

Check these continuously; most lost points in such projects come from one of them.

**Data and leakage**

- [ ] Is every feature known at the moment of prediction for its scenario?
- [ ] Is every model trained only on columns from the feature whitelist?
- [ ] Do the leakage tests pass (`pytest tests/`) before every training run?
- [ ] Are change times and `delay_in_min` at Würzburg kept out of the features?
- [ ] Do history features use only data strictly before the prediction date?
- [ ] Is the split chronological, and has the test set been touched only once?
- [ ] Are encoders and scalers fitted on training data only?
- [ ] Does a suspiciously high score (scenario A ROC-AUC above ~0.95) trigger a leakage check?

**Reproducibility and code**

- [ ] Does the pipeline run from raw files to results with one command?
- [ ] Are random seeds fixed and package versions in `requirements.txt`?
- [ ] Are raw data files kept out of Git (`.gitignore`)?
- [ ] Does each script have a short docstring saying what it reads and writes?

**Scope and time**

- [ ] Does the minimum version (baselines + LightGBM + evaluation) work before any extension?
- [ ] After 1 December: no new features, only writing.
- [ ] Is the report section for this week's work drafted this week?

**Documentation**

- [ ] Has each member logged their own AI use?
- [ ] Is every number in the report traceable to a script or notebook output?
- [ ] Are data sources and licenses cited (DB Data CC BY 4.0, weather source, holiday source)?
- [ ] Do the report and slides contain only project content (no personal goals or private details)?

## Working with Claude Code

Save this document as `CLAUDE.md` in the repository root; Claude Code reads that file at the start of every session, so the context carries over automatically.

**Session routine.**

1. Start: "Read CLAUDE.md. Today's task: <task from the to-do list>."
2. Work in small steps; run each script and check its output before moving on.
3. End: update the to-do checkboxes and **Current status** below.

**Current status (6 Nov 2026).** Plan reviewed; coverage check done and scenario B split decided; repository scaffold created with `01_download.py`, configuration and first leakage tests (8 passing). `01_download.py` has not yet been run on real data. **Next action:** run `python src/01_download.py --months 2026-10 --show-example`, check the RB53 example, then run all months and review `reports/checks/`.

**Repository layout (target).**

```text
pds-db-delays/
├── CLAUDE.md               # this document (shared)
├── CLAUDE.local.md         # personal notes of one member (gitignored, optional)
├── README.md               # setup and run instructions
├── requirements.txt
├── pytest.ini              # pytest finds src/ and tests/
├── run_pipeline.py         # runs steps 01–05 in order (leakage tests before 05)
├── data/                   # gitignored
│   ├── raw/                # monthly files (kept for reruns)
│   ├── interim/            # filtered monthly Würzburg files (incl. earlier stops)
│   └── processed/          # wuerzburg_clean.parquet, feature tables
├── checks/                 # one-off exploration scripts (coverage_check.py)
├── src/
│   ├── config.py           # paths, station, months, splits, seed
│   ├── 01_download.py
│   ├── 02_clean.py         # may call sql/02_clean.sql
│   ├── 03_enrich.py
│   ├── 04_features.py      # runs sql/04_features.sql
│   ├── 05_train.py
│   ├── features_config.py  # feature whitelist per scenario
│   └── sql/
├── tests/
│   └── test_leakage.py     # run before every training run
├── notebooks/              # EDA and exploration only, no pipeline logic
├── app/streamlit_app.py
├── models/                 # saved models (small, may be committed)
└── reports/
    ├── figures/
    ├── checks/             # per-month data checks from 01_download.py
    └── results.md
```

**Environment.** Python 3.10 on macOS (Apple Silicon, M1), packages: `duckdb pandas pyarrow matplotlib scikit-learn lightgbm shap streamlit huggingface_hub holidays pytest jupyter`; minimum versions in `requirements.txt`, exact versions in `requirements-lock.txt` (`pip freeze` after the first install). LightGBM on macOS needs `brew install libomp`. Split dates, months and paths live in `src/config.py`; never hard-code them in other scripts. Weather from Open-Meteo or DWD; public holidays via the `holidays` package; school holidays from an official list saved as CSV.

**Conventions.** English code and comments; one docstring per script stating inputs and outputs; paths built with `pathlib` relative to the repository root (folder names may contain spaces); random seed 42 everywhere; figures saved to `reports/figures/` with descriptive names; SQL kept in `src/sql/` files, not long strings in Python.

**Download source.** Files are at `https://huggingface.co/datasets/piebro/deutsche-bahn-data`, folder `monthly_processed_data/`, names `data-YYYY-MM.parquet`; download with `huggingface_hub.hf_hub_download(repo_id="piebro/deutsche-bahn-data", repo_type="dataset", filename=...)`.

**Verified code** (from the data check; works on the real files):

```python
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parent
FILE = str(ROOT / "data-2026-10.parquet")
con = duckdb.connect()

# Würzburg Hbf rows of one month (~13,000 rows)
df = con.sql(f"""
    SELECT * FROM '{FILE}'
    WHERE station_name = 'Würzburg Hbf'
""").df()

# Our own departure delay in minutes
df["dep_delay"] = (
    (df["departure_change_time"] - df["departure_planned_time"]).dt.total_seconds() / 60
)

# Cancellation flag
df["canceled"] = (df["arrival_is_canceled"].fillna(False).astype(bool)
                  | df["departure_is_canceled"].fillna(False).astype(bool))
```

**Known gotchas (learned the hard way).**

- Relative file paths resolve from the terminal's current folder, not the script's: always build paths from `Path(__file__)`.
- The GitHub README lists outdated column names; use the actual columns listed in the Dataset section (`train_number`, `line_number`, `arrival_is_canceled`, `departure_is_canceled`, no `train_name`, no `is_canceled`).
- `delay_in_min` is the departure delay where a departure exists; compute the target yourself.
- About a third of planned arrival or departure times are NaT by design; `.dt.date` on them gives NaN, so call `dropna()` before `min()` or `max()`.
- `train_line_ride_id` repeats on every day of the month; a single trip = ride ID + service date.
- Monthly files for all of Germany are large (~15 million rows): filter with DuckDB before converting to pandas, and never load several full months into memory.
- Monthly file sizes: ~62 MB until October 2025 (≈108 stations), ~345 MB from November 2025 (≈5,300 stations); total download for July 2024 – October 2026 is roughly 5 GB. Unauthenticated Hugging Face downloads work; setting `HF_TOKEN` makes them faster.
- `train_line_station_num` is the position in the full route, not in the data: gaps mean missing stations. Use it for "stops between" features, never assume `num − 1` exists before November 2025.
- A monthly file can contain a few rows planned on the last day of the previous month (Oct 2026 file: 2 ICE rows planned on 30 Sep). `01_download.py` therefore stores `source_month`; the cleaning step must drop duplicate `id`s across months.
- ICE rows have no `line_number` (~22.5% of Würzburg rows, Oct 2026); for ICE use `train_number` or the route (origin/destination) instead of the line. `train_type` is NaN for 22 rows (the rows without planned times) and contains odd values such as `RE8`; both are handled in cleaning.
- `check_db.py` saved only Würzburg rows (`wuerzburg_hbf.parquet`); that is not enough for scenario B, which also needs the earlier stops of each trip.

## GenAI documentation

The brief requires a dedicated section stating which parts of the work used GenAI and which prompts were used.

- Each member keeps their own AI-use log outside the repository and logs as they go, not at the end.
- Minimum per entry: date, tool, task, 1–3 representative prompts (original language) and how the output was used (as is, edited, or only as a starting point) and that it was checked.
- When the report is written, the logs are merged into the "Use of generative AI" section; non-English prompts get an English translation in the appendix.

## Open questions and sources

**Open questions**

- Final submission date for the report and code (last year 31 January): check the course room.
- Presentation length and format this term (last year 10 minutes per group).
- How detailed the GenAI documentation should be: ask the supervisor in the proposal email if unclear.
- Name and matriculation number of the third member.
- GitHub repository visibility: private with collaborators during the project, public (or supervisor access) at submission? Check what the course expects.

**Sources**

- [Deutsche Bahn Data on Hugging Face](https://huggingface.co/datasets/piebro/deutsche-bahn-data) — monthly Parquet files, CC BY 4.0
- [deutsche-bahn-data project on GitHub](https://github.com/piebro/deutsche-bahn-data) — collection method and coverage
- Grinsztajn, L., Oyallon, E., Varoquaux, G. (2022). *Why do tree-based models still outperform deep learning on tabular data?* NeurIPS Datasets and Benchmarks Track.
- Ke, G. et al. (2017). *LightGBM: A Highly Efficient Gradient Boosting Decision Tree.* NeurIPS.
- Assignment brief "Final Project: Your Own End-to-End Machine Learning Project", PDS course room, WiSe 2026/27
- Own data check: `check_db.py` and `check_old.py` on `data-2026-10.parquet` and `data-2025-03.parquet`; `coverage_check.py` on 2024-07, 2025-03, 2025-10, 2025-11 and 2026-10
