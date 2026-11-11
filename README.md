# Predicting Train Delays at Würzburg Hbf

Practical Data Science capstone, Information Systems M.Sc., University of Würzburg, WiSe 2026/27 (Group 18).

We predict whether a train departs Würzburg Hbf 6 or more minutes late (the threshold of Deutsche Bahn's punctuality statistic, applied to departures), once before the trip (scenario A) and once while the train is en route (scenario B), and compare the two. Start here: [`docs/project_plan.md`](docs/project_plan.md) (course requirements, timeline, roles), [`docs/decision_log.md`](docs/decision_log.md) (data and method decisions with evidence), [`CLAUDE.md`](CLAUDE.md) (working rules and current status, also read by AI assistants).

**Data:** [Deutsche Bahn Data](https://huggingface.co/datasets/piebro/deutsche-bahn-data) (CC BY 4.0, Deutsche Bahn), July 2024 – October 2026. Weather: [Open-Meteo](https://open-meteo.com/) historical weather API (CC BY 4.0). School holidays: Bavarian State Ministry of Education, BayMBl. 2022 Nr. 747.

## Setup (macOS, Apple Silicon)

```bash
brew install libomp                 # needed by LightGBM on macOS
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements-lock.txt  # exact versions (built with Python 3.10), same for every member
pytest                                # all tests must pass
```

`requirements.txt` lists the direct dependencies with minimum versions. Only when a dependency is added or updated on purpose: `pip install -r requirements.txt`, then `pip freeze > requirements-lock.txt`, and commit both files.

## Run

```bash
# 1. Test the download and filter step on one month first
python src/01_download.py --months 2026-10 --show-example

# 2. All months (July 2024 – October 2026, ~5 GB download)
python src/01_download.py

# 3. Clean: one row per planned departure, target, exclusion reasons
python src/02_clean.py

# 4. Weather (one download from Open-Meteo, about 1 MB) and holiday tables
python src/03_enrich.py

# 5. Feature tables for scenario A and B
python src/04_features.py

# 6. Baselines B0-B3 and LightGBM M-A, M-A', M-B on the validation splits (the test period is not touched)
python src/05_train.py

# 7. Error analysis of the validation scores (slices, calibration, largest errors)
python src/06_error_analysis.py

# 8. SHAP explanations of the LightGBM models on the validation rows
python src/07_explain.py

# Rehearsal of the final procedure, one step back in time (test period untouched)
python src/05_train.py --rehearsal

# The single final run on the test period: ONCE, after the group has agreed; refuses a second run
# python src/05_train.py --final
# python src/06_error_analysis.py --set test
# python src/07_explain.py --set test

# Whole pipeline (steps that exist so far)
python run_pipeline.py
```

Outputs of step 1: `data/interim/wuerzburg_YYYY-MM.parquet` (Würzburg rows plus earlier stops of the same trips) and per-month checks in `reports/checks/`. Outputs of step 2: `data/processed/wuerzburg_clean.parquet` (every planned departure; modelling rows have an empty `exclude_reason`), `data/processed/wuerzburg_prev_stops.parquet`, and `reports/checks/cleaning_counts.csv`.

```bash
# Data checks (after step 1); results in reports/checks/
python checks/coverage_check.py      # earlier-stop coverage per period (needs the raw files of 5 sample months in data/raw)
python checks/category_check.py      # train types and line numbers over time
python checks/data_quality_check.py  # duplicates, cancellations, collection gaps
```

## Repository layout

| Path | Content |
| --- | --- |
| `src/` | Pipeline steps `01`–`05` (steps `01`–`04` and `05` on validation exist; the final test run is planned), `models.py` (LightGBM helpers and the tuning grid), `evaluate.py` (metrics, bootstrap), `baselines.py`, `config.py` (paths, splits, seed, dataset revision), `features_config.py` (feature whitelist) |
| `src/sql/` | SQL used by the pipeline (DuckDB) |
| `tests/` | Leakage, configuration, filter and data tests, run at the start of every pipeline run |
| `checks/` | Data check scripts (coverage, categories, data quality) |
| `reference/` | Small tracked tables with their sources (Bavarian school holidays) |
| `docs/` | Project plan (requirements, timeline, roles) and decision log (decisions with evidence) |
| `notebooks/` | EDA only, no pipeline logic (`01_eda.ipynb`: training and validation period, writes `reports/figures/eda_*.png`) |
| `app/` | Streamlit dashboard (planned) |
| `models/` | Saved models (planned) |
| `reports/` | Data checks (`reports/checks/`), validation results (`results_validation.md`), error analysis (`error_analysis_validation.md`), figures; final results table (planned) |
| `data/` | Raw, interim and processed data (not in Git) |

## Drafts as PDF

```bash
python tools/export_pdf.py   # proposal, report sections and decision sheet → docs/pdf/
```

Needs Google Chrome (or Chromium/Edge) for printing. The layout is a plain A4 page, not the chair's template.

## AI use

AI use is documented in the "Use of generative AI" section of the report.
