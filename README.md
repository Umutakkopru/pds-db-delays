# Predicting Train Delays at Würzburg Hbf

Practical Data Science capstone project · Information Systems M.Sc. · University of Würzburg · WiSe 2026/27 · Group 18

**Live dashboard:** [pds-db-delays.streamlit.app](https://pds-db-delays.streamlit.app)

For every train that departs Würzburg Hbf we predict the probability that it leaves **6 or more minutes late**, the threshold of Deutsche Bahn's punctuality statistic. We make the prediction at two moments and compare them:

| Scenario | When the question is asked | Information the model may use |
| --- | --- | --- |
| **A: before the trip** | The day before departure | Timetable, line and service, destination, calendar and holidays, weather, delay rates of the last four weeks |
| **B: en route** | When the train leaves its previous stop | Everything in A, plus the delays at stops the train has already passed |

The comparison answers our research question: *how much of a departure delay can be predicted in advance, and how much builds up on the way?*

## Results

Held-out test period July – October 2026, scored once, after every choice had been fixed on earlier data. PR-AUC is the main metric; 95% intervals from 1,000 bootstrap resamples of whole days.

| Rows | Model | PR-AUC [95% CI] | ROC-AUC |
| --- | --- | --- | --- |
| All departures (31,956; 23.0% delayed) | B1 delay rate of service × hour | 0.523 [0.502, 0.544] | 0.792 |
| | B2 logistic regression | 0.545 [0.522, 0.566] | 0.807 |
| | **M-A LightGBM** | **0.629 [0.610, 0.648]** | **0.833** |
| Through trains with an earlier stop (15,898; 37.6% delayed) | B3 rule "late at the previous stop → late at Würzburg" | 0.885 [0.873, 0.896] | 0.910 |
| | M-A′ LightGBM, scenario A features | 0.690 [0.668, 0.711] | 0.801 |
| | **M-B LightGBM, with earlier stops** | **0.935 [0.928, 0.942]** | **0.942** |

Paired differences on the same day resamples, all with the interval above zero:

- **M-A − B2 = +0.084** [+0.072, +0.097]: the day-ahead model beats the interpretable baseline.
- **M-B − M-A′ = +0.245** [+0.228, +0.263]: the gain from knowing the delay at earlier stops (M-A′ is trained on the same period and rows as M-B, without those features).
- **M-B − B3 = +0.051** [+0.045, +0.057]: the model adds to the simple rule, mostly for trains that were 6–9 minutes late at the previous stop.

Full tables, operating points per service and sensitivity checks: [`reports/results.md`](reports/results.md). Error analysis: [`reports/error_analysis_test.md`](reports/error_analysis_test.md). Feature attributions (SHAP): [`reports/shap_test.md`](reports/shap_test.md).

**Main findings.** Long-distance and night trains are delayed far more often than regional trains (48% and 73% against 9% in the test period). The day before departure, the model ranks departures well but has little signal for single regional trains. Once a train is en route, the delay at its previous stop dominates the prediction (about half of M-B's attribution).

## Data

| Source | Use | License |
| --- | --- | --- |
| [Deutsche Bahn Data](https://huggingface.co/datasets/piebro/deutsche-bahn-data) (archive of DB's public Timetables API, one Parquet file per month) | Planned and actual times, July 2024 – October 2026 (28 months; revision pinned in `src/config.py`) | CC BY 4.0, Deutsche Bahn |
| [Open-Meteo](https://open-meteo.com/) historical weather API | Hourly weather at Würzburg | CC BY 4.0 |
| Bavarian State Ministry of Education, BayMBl. 2022 Nr. 747 | School holidays ([`reference/`](reference/README.md)) | Official publication |
| [`holidays`](https://pypi.org/project/holidays/) package | Bavarian public holidays | MIT |

From 365,502 rows at Würzburg Hbf we keep 230,333 planned train departures for modelling. Buses, cancelled departures, departures without a timetable record and the nights of clock changes are flagged and counted, not silently dropped (`reports/checks/cleaning_counts.csv`).

## Method

- **Target:** `delayed = 1` if the departure is 6 or more minutes after the planned departure; computed from the planned and the last reported departure time.
- **Chronological split:** scenario A trains on July 2024 – December 2025 and validates on January – June 2026. Scenario B trains from 3 November 2025, the first day on which the archive covers every station, and validates on May – June 2026. Both share the test period July – October 2026.
- **Models:** majority class (B0), delay rate of service × hour (B1), logistic regression (B2), the previous-stop rule (B3), and LightGBM for scenario A (M-A), for scenario B (M-B) and as a control model (M-A′).
- **Features:** 21 for scenario A (timetable, calendar, weather, four-week delay history), plus 4 previous-stop features for scenario B. A whitelist in [`src/features_config.py`](src/features_config.py) defines what a model may see.
- **Tuning:** a grid of 12 settings fixed in advance, early stopping, and thresholds chosen on validation data; no class weights, so that the probabilities stay calibrated.
- **Single test run:** one command with three modes (`validation`, `--rehearsal`, `--final`). The final mode writes a lock file ([`reports/final_run.json`](reports/final_run.json)) and refuses a second run. A rehearsal one step back in time checked the whole procedure before the test period was touched.
- **Leakage safeguards:** automated tests check the feature lists, the split dates, that history features only use days before the prediction (a "time-travel" test), that earlier stops lie before the Würzburg arrival, that no single feature is suspiciously strong, and that shuffled labels give chance-level scores.

Every data and method decision is recorded with its evidence in [`docs/decision_log.md`](docs/decision_log.md).

## Dashboard

The Streamlit app answers a query for a line, a day and an hour of the test period. Without a previous-stop delay it uses M-A; with one, M-B. It shows the probability against the model's threshold, the features that drove it, the risk through the day and a weekday × hour map of historical delay rates. On real test rows it returns exactly the scores of the final run (checked by `tests/test_dashboard.py`). Details: [`dashboard/README_DASHBOARD.md`](dashboard/README_DASHBOARD.md).

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py      # from the repository root
```

## Setup

Tested with Python 3.10 on macOS (Apple Silicon).

```bash
brew install libomp                   # LightGBM on macOS
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements-lock.txt  # exact versions
pytest                                # 175 tests; in a fresh clone without data, 37 data-dependent tests are skipped
```

## Reproducing

```bash
python run_pipeline.py                # all steps; the tests run first
```

| Step | Script | Output |
| --- | --- | --- |
| 1 Download and filter (~5 GB download) | `src/01_download.py` | Würzburg rows and earlier stops per month, `data/interim/` |
| 2 Clean | `src/02_clean.py` | One row per planned departure with target and exclusion reason |
| 3 Enrich | `src/03_enrich.py` | Hourly weather, holiday calendar |
| 4 Features | `src/04_features.py` | Feature tables for scenario A and B |
| 5 Train and evaluate | `src/05_train.py` | Baselines and LightGBM on validation (`--rehearsal`: the final procedure one step back in time) |
| 6 Error analysis | `src/06_error_analysis.py` | Slices, calibration, largest errors |
| 7 Explain | `src/07_explain.py` | SHAP attributions |
| 8 Dashboard data | `src/08_dashboard_data.py` | Lookup tables in `dashboard/data/` |

The final run on the test period took place once, on 13 November 2026, and is not repeated: `python src/05_train.py --final` is refused while `reports/final_run.json` exists. Its outputs are tracked in `reports/` and `models/`. From a fresh clone the pipeline reproduces everything up to the validation and rehearsal results; the test-period steps (`06`/`07 --set test`, `08`) also need the scored predictions, which are not in Git because of their size.

Data checks (coverage of earlier stops, train categories over time, data quality) live in `checks/` and write to `reports/checks/`.

## Repository layout

| Path | Content |
| --- | --- |
| `src/` | Pipeline steps `01`–`08`, shared code (`config.py`, `features_config.py`, `evaluate.py`, `baselines.py`, `models.py`) and SQL for DuckDB in `src/sql/` |
| `tests/` | Leakage, split, cleaning, feature, model, final-run, SHAP and dashboard tests |
| `checks/` | Data check scripts |
| `notebooks/` | Exploratory data analysis (training and validation period only) |
| `models/` | Final models M-A, M-A′, M-B with their features, setting and threshold |
| `reports/` | Results for validation, rehearsal and test; error analysis; SHAP; figures; data checks |
| `dashboard/` | Streamlit app, model connection, design components, lookup tables |
| `docs/` | Project plan, decision log, reviews of the project, report drafts (PDFs in `docs/pdf/`) |
| `reference/` | School holiday table with its source |
| `tools/` | PDF export of the report drafts |
| `data/` | Raw, interim and processed data (not in Git; recreated by the pipeline) |

## Report

The written report (PDF) describes the project in full, including the use of generative AI and the contributions of each group member.

## License

Code: [MIT](LICENSE). Data: Deutsche Bahn Data and Open-Meteo, both CC BY 4.0; the tables and models in this repository are derived from them.
