# Predicting Train Delays at Würzburg Hbf — rules, decisions, status

Last updated: 10 Nov 2026 · PDS Group 18 · Practical Data Science, Information Systems M.Sc., Uni Würzburg, WiSe 2026/27

This is the working context for every session with an AI assistant (Claude Code reads it automatically). It holds the working rules, decisions, pipeline and current status. Details live in two more files that are read **only when the task needs them** (see Read-when).

**Status of decisions (10 Nov 2026):** all decisions and the plan so far (D1–D22, timeline, roles) were prepared by one member and are **proposals** until the whole group has discussed and confirmed them. From now on, decisions are made by the group together.

## Instructions for the AI assistant

- Treat the decisions in this document as the current working basis (proposals until the group confirms them, see status above); do not change them unless we explicitly ask.
- Prefer the simplest solution that satisfies the assignment.
- Respect the leakage rules, safeguards and watch-list in every piece of code. When you write feature or split code, add or update the matching automated check in `tests/test_leakage.py`.
- Use Python, DuckDB (SQL), pandas, scikit-learn, LightGBM, SHAP and Streamlit unless we ask otherwise.
- Report, code, comments and slides are in English.
- Only project facts and decisions go into this file, the report and the slides; no personal goals or private details of team members. Personal instructions live in `CLAUDE.local.md` (gitignored).
- When a data or method decision is made, add an entry to `docs/decision_log.md` (template at its end) with the evidence (script, output file, numbers), and add a one-line summary to "Decisions so far" below.

### Read-when (mandatory)

Before starting a task of the kind on the left, read the file on the right with the Read tool, even if it seems familiar. Say in one line that you read it.

| Task | Read first |
| --- | --- |
| Proposal, report, slides, presentation; grading criteria; roles; timeline or deadlines beyond the table below; risks; dashboard levels or other extensions; GenAI documentation; open questions; sources and citations | `docs/project_plan.md` |
| Making or changing a data or method decision; writing the Data or Methodology section; tracing a number to its script; questions about raw columns, data-check results, coverage or category history | `docs/decision_log.md` |
| Start of every session, if the file exists | `CLAUDE.local.md` |

## Project at a glance

| Item | Value |
| --- | --- |
| Task | Own end-to-end ML project, group of 3 (Group 18; all three members confirmed on 9 Nov 2026; registration in the course room by 15 Nov) |
| Goal | For every train departing Würzburg Hbf, predict the probability that it departs **6 or more minutes late**, before the trip (A) and en route (B), and compare the two |
| Data | Deutsche Bahn Data archive (Hugging Face `piebro/deutsche-bahn-data`, CC BY 4.0), Jul 2024 – Oct 2026; 365,502 Würzburg rows; 247,716 planned departures, of which 230,333 are modelling rows (A: 152,384 train, 45,993 validation, 31,956 test); 24.8% delayed in training + validation |
| Models | B0 majority, B1 rule-based, B2 logistic regression, B3 persistence rule (scenario B), LightGBM (M-A, M-A′, M-B) |
| Committed extras | DuckDB/SQL pipeline, Streamlit dashboard (deployed), SHAP |
| Pass condition | A baseline plus at least one more approach, implemented with care |

| Hard deadline | When |
| --- | --- |
| Group registration (3 members) | **15 Nov 2026, 23:59** |
| Topic proposal (max. 2 pages); we aim for ~20 Nov | 30 Nov 2026, 23:59 |
| Supervisor feedback (none = accepted) | 7 Dec 2026 |
| Final PDF report and documentation | 18 Jan 2027, 23:59 |
| Presentation (10 min) | 25 Jan 2027, 15:00 |

Proposed plan (to be agreed by the group): minimum version (baselines, LightGBM, results table) frozen by **1 Dec 2026**, extensions by **8 Dec 2026**, everything finished by **15 Dec 2026**; the rest is buffer until the submission on 18 Jan. The plan is written as one sequential track that a single member can follow from start to finish; steps can be shared or done in parallel by other members and the results compared.

## Decisions so far (proposals, to be confirmed by the group; details and evidence: `docs/decision_log.md`)

| # | Decision |
| --- | --- |
| D1 | Topic: DB departure delays at Würzburg Hbf; fallback topic German electricity demand |
| D2 | Target `delayed = 1` if departure delay ≥ 6 min (DB's punctuality threshold, which DB defines for arrivals, applied here to departures); classification, not regression (skewed delays) |
| D3 | Scenario A before the trip, scenario B en route; B applies only to through trains |
| D4 | Chronological split, test = Jul – Oct 2026 for both scenarios; test used once |
| D5 | LightGBM as main model (tabular data, interactions, NaN and categories, fast, SHAP) |
| D6 | Scenario B trains from 3 Nov 2025 (earlier-stop coverage complete only from then) |
| D7 | `line_id` and `service` instead of raw `train_type` (ARV relabel and line-format change in Dec 2025) |
| D8 | Exclude buses, rows without timetable record, rows without planned time |
| D9 | Cancelled departures excluded from the main target; sensitivity check counts them as delayed |
| D10 | Naive local time (Europe/Berlin) everywhere; DST nights 00–05 h excluded |
| D11 | Target = last time reported by DB's API; no days excluded for collection gaps |
| D12 | Drop duplicate ids (none found); earlier stops searched within the same monthly file |
| D13 | Control model M-A′; paired day-block bootstrap; refit on train + val; no class weights; B reported by horizon |
| D14 | B1 = service × hour; history window [D − 29, D − 1 00:00); `train_number` is a key, not a feature |
| D15 | Dashboard replays real test-period departures; no free future dates |
| D16 | Disruption flags (`is_additional_stop`, `is_replacement_train`, `replaced_train_*`, `has_plan_record`) are filters only |
| D17 | Baseline B3 for scenario B: delayed at the previous stop → delayed at Würzburg; M-B is judged against it |
| D18 | Rows without timetable record stay excluded, are counted per split, and get a sensitivity check (scenario A) |
| D19 | `02_clean` flags rows with `exclude_reason` instead of deleting them; delays below −30 min invalid; `line_id` by format, line prefix wins |
| D20 | `is_through` = planned arrival present; `has_prev_stop` separate; scenario B rows need both |
| D21 | Refit keeps tree count and threshold; at most 20 tuning settings; weather ablation on validation |
| D22 | Baselines before enrichment; simple history features first; Bavarian school holidays first; freeze 1 Dec (minimum) and 8 Dec (extensions) |

## Problem definition

- **Target:** `delayed = 1` if `departure_change_time − departure_planned_time ≥ 6 min`, else 0. Computed by us, not taken from `delay_in_min`. Trains that end at Würzburg (no departure) are not in the target.
- **What the target measures:** the last departure time DB's Timetables API reported (collected four times a day, each run reaching back 6+ hours), normally the realised time; not an independent measurement (limitation, D11).
- **Cancellations:** cancelled = `departure_is_canceled` at Würzburg. A train whose arrival is cancelled but which still departs is a normal departure. Main target excludes cancellations; sensitivity check with cancellations = delayed (`CANCELED_AS_DELAYED_SENSITIVITY` in `src/config.py`); EDA shows the cancellation share by month, service and hour (falls from about 3.2% on average until Dec 2025 to about 2.1% in 2026; single months 1.0–4.5%).
- **Scope:** Würzburg Hbf; trains only; rows without a timetable record excluded.

| Scenario | Question | Allowed information |
| --- | --- | --- |
| A: Before the trip | Asked the day before | Timetable, line/service, destination, calendar, holidays, weather, history up to D − 1 00:00 |
| B: En route | Asked when the train leaves its previous stop | Everything in A plus the delay at stops the train has already passed (last non-cancelled earlier stop) |

- **Metrics:** primary PR-AUC; ROC-AUC; F1, precision, recall at the max-F1 threshold chosen on validation (also at 0.5); Brier score and reliability diagram; accuracy only next to B0; MAE only for the optional regression.
- **Realistic expectation:** scenario A moderate, scenario B clearly better. **Scenario A ROC-AUC above ~0.95 means leakage, not success.**

## Split (`SPLITS` in `src/config.py`; half-open intervals on the Würzburg planned departure)

| Scenario | Train | Validation | Test |
| --- | --- | --- | --- |
| A | Jul 2024 – Dec 2025 | Jan – Jun 2026 | Jul – Oct 2026 |
| B (and M-A′) | 3 Nov 2025 – Apr 2026 (`FULL_COVERAGE_START`) | May – Jun 2026 | Jul – Oct 2026 |

Why: start = first month in the archive (two winters); end = last complete month (data fixed); validation A contains winter; test = most recent data (limitation: no winter in test; season effects checked on validation). Scenario B starts on 3 Nov 2025 because before November 2025 the directly preceding stop is missing for 100% of RB/RE trains (D6).

## Pipeline (one script per step; `python run_pipeline.py` runs all, leakage tests before step 05)

1. **Download and filter** (`src/01_download.py`, `src/sql/01_filter_month.sql`) — done. Per month: Würzburg rows plus earlier stops of the same trip (same `train_line_ride_id`, lower stop number, planned within 12 h before the Würzburg arrival), linked by `wuerzburg_id`, with `row_role` and `source_month`. Output `data/interim/wuerzburg_YYYY-MM.parquet`; checks in `reports/checks/`.
2. **Clean** (`src/02_clean.py` + `src/sql/02_clean.sql`) — done (10 Nov 2026: 247,716 planned departures, 230,333 modelling rows; counts in `reports/checks/cleaning_counts.csv` and `through_train_counts.csv`). Input = `row_role = 'wuerzburg'` rows with a planned departure (trains that end at Würzburg are not part of the target). **No departure is deleted** (D19): each one gets `exclude_reason` (first matching rule: `bus`, `no_plan_record`, `canceled`, `dst_night` via `config.dst_change_days()` and `DST_EXCLUDE_HOURS`, `invalid_delay` = delay below −30 min, `duplicate_id`); modelling rows have `exclude_reason` NULL. Compute `dep_delay` and `delayed`; `service_date` = date of the Würzburg planned departure; build `line_id`, `service`, `is_through` (planned arrival present) and `has_prev_stop` (a non-cancelled earlier stop exists) (D20). Write the count per reason and split to `reports/checks/cleaning_counts.csv`. Save earlier stops separately (`wuerzburg_prev_stops.parquet`), keyed by `wuerzburg_id` and `id`. Output `data/processed/wuerzburg_clean.parquet`.
3. **Enrich** (`src/03_enrich.py`), after the baselines (D22): hourly weather (Open-Meteo, `timezone=Europe/Berlin`; downloaded once and stored in `data/raw/weather/`), public holidays (Bavaria, `holidays` package), school holidays (Bavaria first, official list as CSV; neighbouring states only if time allows).
4. **Features** (`src/04_features.py` + `src/sql/04_features.sql`): scenario A and B tables; history from a daily aggregate table (key × day) joined over [D − 29, D − 1). First version: keys `service` × hour and `line_id` / route group; the train-number key with its fallback comes after the first full results table (D22).
5. **Train and evaluate** (`src/05_train.py`, shared metrics and the day-block bootstrap in `src/evaluate.py`): fixed seeds; `src/evaluate.py` and the baselines B0–B2 are written directly after step 2 and scored on validation; one results table `reports/results.md`; figures in `reports/figures/`. The test run is a single command (`--final`) that refuses to run twice.

**Category columns (D7):**
- `line_id` (by format, not by date, D19): a line with a letter prefix is used as it is ("RB53", "RE10", "RE8"); a digit-only line gets the train type as prefix ("RB" + "53"); ARV rows keep their line (RE8, RB8, RE80); NULL for long-distance trains. If train type and line prefix disagree (1,901 departures have type RB with an RE line), the line prefix wins. **To verify in `02_clean`:** via `train_number`, the RE/RB label before Dec 2025 matches the line prefix after (line 8 has both RE8 and RB8).
- `service`: `long_distance` (ICE, IC, EC), `night` (NJ, EN), `regional` (RE, RB, ARV, regional lines labelled otherwise), `other`.
- `train_type`: reporting only, never a feature. ICE rows have no line: use a route group (origin/destination direction).

## Features (whitelist per scenario in `src/features_config.py`)

| Group | Examples | Scenario |
| --- | --- | --- |
| Timetable | Service, line_id / route group, destination, planned hour, weekday, stop position in route | A, B |
| Calendar | Public holiday, school holiday, bridge day, Friday and Sunday evening peaks | A, B |
| Weather | Temperature, precipitation, wind speed, snow (observed weather stands in for a forecast) | A, B |
| History | Delay rate over [D − 29, D − 1 00:00) per service × hour and per line_id / route group; later: train number with fallback → line_id / route group → service when a cell is sparse | A, B |
| Propagation | Delay at the previous stop and two stops before (departure delay, else arrival delay); planned minutes from that stop to Würzburg; stops between (from `train_line_station_num`) | B only |

## Leakage rules

1. `arrival_change_time`, `departure_change_time`, `delay_in_min` and anything derived from them **at Würzburg** are never features.
2. History uses only departures planned before D − 1 00:00 for a departure on day D.
3. In scenario B, only stops the train has already passed count (planned before the Würzburg planned arrival).
4. Scalers, encoders, category lists, target encodings and the threshold are fitted on training (threshold: validation) data only.
5. Weather is observed, not forecast (limitation); joined on local time.
6. Disruption flags and bookkeeping columns are filters only (D16). Excluding cancelled rows is a filter on later information; accepted because the target is undefined (D9).

**Safeguards**

1. **Feature whitelist and forbidden list** (`src/features_config.py`): models use only whitelisted columns; `FORBIDDEN_COLUMNS` holds change times, delays, target, cancellation flags, ids, `time`, `train_number`, disruption flags, `source_month`, `row_role`.
2. **Automated tests** (`pytest`, before every training run) — exist: no forbidden column in features (name check only; passes trivially while the lists are empty); no propagation features in A (`prev_` prefix); splits chronological and disjoint; same test period; B starts at full coverage (literal date and data check); DST days; filter SQL on a small fixture (12-hour window, midnight, ride id on two days); local row counts equal `monthly_summary.csv`; every raw column is classified as allowed or forbidden; cleaning rules on a small fixture and on the real output (ids unique, no bus/DST/cancelled/invalid rows among modelling rows, stable `line_id`, no test-period delay rate in the count files). **To add:** with `04` — time-travel test (history for day D identical when data is truncated at D − 1 00:00), every earlier stop planned before the Würzburg arrival, no row in two splits, identical test rows for M-A′/M-B (through-train subset); with `05` — encoders/categories from training data only; columns given to each model equal `FEATURES[scenario]`; the test run is one command that writes `reports/results.md` and refuses to run a second time.
3. **Sanity checks on results:** each single feature clearly below ROC-AUC 0.9; shuffled target → ROC-AUC ≈ 0.5; validation and test in the same range; SHAP top features make domain sense (not IDs or timestamps).
4. **Second pair of eyes:** a second member reviews feature and split code; an AI review ("Check this code for data leakage against the leakage rules in CLAUDE.md") is extra, not a replacement.

## Evaluation protocol (D13)

| ID | Model | Training rows | Purpose |
| --- | --- | --- | --- |
| B0 | Majority class ("on time") | – | Shows why accuracy misleads |
| B1 | Delay rate of service × hour | A train | Rule-based baseline (brief) |
| B2 | Logistic regression, timetable + calendar (one-hot `handle_unknown="ignore"`) | A train | Interpretable baseline |
| B3 | Persistence rule: previous-stop delay ≥ 6 min (score: previous-stop delay in minutes) | – (no fitting) | Baseline for scenario B (D17) |
| M-A | LightGBM, A features | A train | Main model, before the trip |
| M-A′ | LightGBM, A features | B train window, through trains | Control: isolates propagation effect |
| M-B | LightGBM, B features | B train | Main model, en route |

1. Tuning (small grid, at most 20 settings per model, fixed in advance; D21), number of trees (early stopping) and threshold are chosen with training-only models on validation. No class weighting (`is_unbalance`, `scale_pos_weight`): probabilities must stay calibrated.
2. Final models are refitted on training + validation with those settings (tree count and threshold unchanged, D21), then **all models are scored once on the test set at the same time**. Nothing changes after seeing test results. Until then features, tuning, SHAP checks, error-analysis code and the dashboard are developed on validation data, and no further label statistics are computed on the test period.
3. Same rows for all models: A on all test departures; M-A, M-A′, M-B and B3 also on the identical scenario B subset (`is_through` and `has_prev_stop`, D20). Propagation effect = M-B − M-A′; gain over the simple rule = M-B − B3 (D17).
4. Uncertainty: 1,000 bootstrap resamples **of whole days**; a model is better only if the 95% interval of the paired metric difference lies above zero.
5. Slices: service, line (incl. 8 and 80), hour, weekday, month, holiday, weather; scenario B also by minutes from the previous stop (< 10, 10–30, > 30). Confusion matrix; 20 largest errors grouped into failure types; two sensitivity checks: cancellations counted as delayed (D9) and departures without timetable record included (scenario A, D18).
6. SHAP global (M-A, M-B) and per prediction (dashboard).
7. Weather ablation: M-A without weather features, compared on validation (D21; dropped first if time is short).

Results table (`reports/results.md`, written by `05_train.py`): Model | Scenario | Rows (n) | Base rate | PR-AUC [95% CI] | ROC-AUC [95% CI] | F1 | Precision | Recall | Brier — rows B0, B1, B2, M-A on all departures; M-A, M-A′, B3, M-B on the scenario B subset. Row sets with different base rates are not compared with each other (through trains are delayed more often than all departures: 36% vs 24% in the B training window).

## Environment and conventions

- Python 3.10 on macOS (Apple Silicon); `.venv/`; minimum versions in `requirements.txt`, exact in `requirements-lock.txt`. LightGBM needs `brew install libomp`.
- Split dates, months, paths, station, seed and time-zone constants live in `src/config.py`; never hard-code them elsewhere. Reuse `config.month_range()`, `config.dst_change_days()`.
- English code and comments; one docstring per script stating what it reads and writes; paths via `pathlib` from `Path(__file__)` (folder names contain spaces); seed 42 everywhere; SQL in `src/sql/` files, not long strings; figures to `reports/figures/` with descriptive names; notebooks for EDA only, no pipeline logic.
- Download: `huggingface_hub.hf_hub_download(repo_id="piebro/deutsche-bahn-data", repo_type="dataset", revision=config.HF_REVISION, filename="monthly_processed_data/data-YYYY-MM.parquet")`; `HF_TOKEN` makes it faster. The revision is fixed in `src/config.py` because the maintainer reprocesses past months; `tests/test_data.py` compares the local row counts with `reports/checks/monthly_summary.csv`.
- Verified code: `src/01_download.py` + `src/sql/01_filter_month.sql` on all 28 months (12,975 Würzburg rows in Oct 2026, identical to the first data check).

Files marked * are planned and do not exist yet (10 Nov 2026).

```text
pds-db-delays/
├── CLAUDE.md, CLAUDE.local.md (gitignored), README.md, requirements*.txt, pytest.ini, run_pipeline.py
├── data/{raw,interim,processed}/  # gitignored
├── checks/                          # coverage_check.py, category_check.py, data_quality_check.py
├── docs/decision_log.md, docs/project_plan.md, docs/audit_2026-11-10.md
├── src/config.py, features_config.py, 01_download.py, 02_clean.py, 03_enrich.py* … 05_train.py*, evaluate.py*, sql/
├── tests/test_leakage.py, test_config.py, test_data.py, test_filter_sql.py, test_clean.py
├── notebooks/, app/streamlit_app.py*, models/
└── reports/{figures,checks}/, reports/results.md*
```

## Known gotchas

- Relative paths resolve from the terminal's folder, not the script's: always build paths from `Path(__file__)`.
- Older versions of the dataset's GitHub README listed outdated column names (corrected upstream; the README matched the files when checked on 10 Nov 2026); real columns: `train_number`, `line_number`, `arrival_is_canceled`, `departure_is_canceled`; no `train_name`, no `is_canceled` (full list: decision log D1).
- `delay_in_min` is the departure delay where a departure exists (matches 100% of departure differences, 61.9% of arrival differences); compute the target yourself.
- ~33% of planned arrival or departure times are NaT by design (trains starting or ending at Würzburg); `.dt.date` gives NaN, so `dropna()` before `min()`/`max()`. 47% of departures start at Würzburg → no scenario B features.
- `train_line_ride_id` repeats on every day of the month: one trip = ride ID + day (12-hour window in step 01).
- Monthly files for Germany are large (~15 million rows; ~62 MB until Oct 2025, ~345 MB from Nov 2025; ~5 GB total): filter with DuckDB before pandas; never load several full months.
- **Time zone:** timestamps are naive Europe/Berlin local time (`TIMEZONE`); features and split boundaries use local time, nothing is converted to UTC. Weather from Open-Meteo with `timezone=Europe/Berlin`, joined on the local hour; the doubled October hour is averaged. On the five DST days (27 Oct 2024, 30 Mar 2025, 26 Oct 2025, 29 Mar 2026, 25 Oct 2026) departures planned 00:00–05:00 are excluded and counted. Collection runs at 03/09/15/21 UTC (= 04/10/16/22 h winter, 05/11/17/23 h summer local); matters only for collection gaps.
- Earlier stops are searched only inside the same monthly file: a train arriving shortly after midnight on the 1st loses earlier stops from the previous month (a few trains per month, B only).
- `train_line_station_num` is the position in the full route, not in the data: gaps mean missing stations. Use it for "stops between"; never assume `num − 1` exists before Nov 2025.
- A monthly file can contain rows planned on the last day of the previous month (Oct 2026: 2 ICE rows on 30 Sep); `source_month` is stored; cleaning drops duplicate ids.
- ICE rows have no `line_number` (22.6–30.7% of the Würzburg rows per month have none); `train_type` is NaN for some rows (no planned times; removed by cleaning) and has odd values such as `RE8`.
- Bus rows are rail replacement (lines EV, SEV, or the replaced line such as RE7/RB80; up to 1,884 rows in Jul 2024): excluded and counted. IC disappears after Oct 2025 (→ `long_distance`).
- Line format changes in Dec 2025 ("53" → "RB53"); ARV appears in Dec 2025. Among all Würzburg rows (arrivals and departures, by source file) it is 692 of 238,850 in Jul 2024 – Dec 2025 and 17.1% in Jul – Oct 2026; among modelling rows (approximate cleaning rules) 330 of 152,421 A training departures and 13.2% of test departures. Never use raw `train_type` as a feature.
- `check_db.py` (outside the repo) saved only Würzburg rows; scenario B needs the earlier stops from `data/interim/`.
- The share of exactly-on-time departures rises from ~34% (2024) to ~42% (2026); show in the EDA. Early departures (negative delay) fall from 1–2% of departures per month to ~0.1% from Dec 2025, which explains part of the rise (D11). If errors cluster in single time blocks, re-check collection gaps (D11).

## Watch-list

- [ ] Is every feature known at the prediction moment of its scenario, and on the whitelist?
- [ ] Do `pytest` tests pass before every training run?
- [ ] Is the split chronological, and has the test set been touched only once?
- [ ] Encoders, scalers, categories fitted on training data only?
- [ ] Scenario A ROC-AUC above ~0.95 → stop and check leakage.
- [ ] Does the pipeline run from raw files to results with one command; seeds fixed; raw data out of Git; docstrings present?
- [ ] Minimum version (baselines B0–B3 + LightGBM + evaluation) works before any extension; minimum version frozen 1 Dec, extensions 8 Dec, after that only writing.
- [ ] Is the report section for this week's work drafted this week?
- [ ] Every number in the report traceable to a script or output; sources and licenses cited (DB Data CC BY 4.0, weather, holidays)?
- [ ] Has each member logged their own AI use?

## Session routine

1. Start: "Read CLAUDE.md. Today's task: <task from the to-do list>." Follow Read-when.
2. Work in small steps; run each script and check its output before moving on.
3. End: update the to-do checkboxes and Current status below (and the week list in `docs/project_plan.md`); add a decision-log entry if a decision was made.

## Current status and to-do

**Current status (10 Nov 2026).** Step 1 (download, filter) and step 2 (cleaning) are done; data checks, an independent audit (`docs/audit_2026-11-10.md`, 37 findings, none critical) and its fixes are merged into `main`; the audit's recommendations are recorded as proposals D17–D22. `data/processed/wuerzburg_clean.parquet` holds every planned departure with `exclude_reason`, target, `service`, `line_id`, `is_through`, `has_prev_stop` and the split of both scenarios. Tests: 49 passed. Work on step 2 is on branch `02-clean` (to merge). **Next action:** `src/evaluate.py` (metrics, day-block bootstrap) and the baselines B0–B2 on validation.

**Now (week 2, until 17 Nov)** — in this order

- [ ] **Register the group by 15 Nov** (all three members found; registration in the course room still to do)
- [x] Merge branch `audit-2026-11-10` into `main` (10 Nov)
- [ ] Push the repository to GitHub and add collaborators
- [ ] Share `docs/project_plan.md`, `docs/decision_log.md` and `CLAUDE.md` with both members and get agreement (D1–D22)
- [ ] Download the chair's report template; collect names and matriculation numbers for the proposal
- [x] `02_clean` with `exclude_reason`, `is_through`, `has_prev_stop` + tests + `cleaning_counts.csv` per split (D19, D20) — 10 Nov; branch `02-clean` to merge
- [ ] `src/evaluate.py` (metrics, day-block bootstrap, tests) + baselines B0, B1, B2 on validation (D22)
- [ ] EDA notebook: core figures only (delay by service, hour, month; cancellations; coverage; rows without plan record)
- [ ] Draft the two-page proposal; collect 6–10 related-work references; ask the supervisor about the GenAI documentation with the proposal

**Next (week 3, until 24 Nov):** submit the proposal (~20 Nov); `03_enrich` (weather, public and Bavarian school holidays); `04_features` (simple history first) + time-travel, earlier-stop and same-rows tests; B3; Data section draft. **Week 4 (until 1 Dec):** LightGBM A, A′, B with tuning (≤ 20 settings) and refit; sanity checks; weather ablation; final test run once; results table; minimum version frozen. Later weeks: `docs/project_plan.md`.
