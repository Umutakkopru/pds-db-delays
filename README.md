# Predicting Train Delays at Würzburg Hbf

Practical Data Science capstone, Information Systems M.Sc., University of Würzburg, WiSe 2026/27 (Group 18).

We predict whether a train departs Würzburg Hbf 6 or more minutes late (Deutsche Bahn's punctuality threshold), once before the trip (scenario A) and once while the train is en route (scenario B), and compare the two. Start here: [`docs/project_plan.md`](docs/project_plan.md) (course requirements, timeline, roles), [`docs/decision_log.md`](docs/decision_log.md) (data and method decisions with evidence), [`CLAUDE.md`](CLAUDE.md) (working rules and current status, also read by AI assistants).

**Data:** [Deutsche Bahn Data](https://huggingface.co/datasets/piebro/deutsche-bahn-data) (CC BY 4.0, Deutsche Bahn), July 2024 – October 2026.

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

# Whole pipeline (steps that exist so far)
python run_pipeline.py
```

Outputs of step 1: `data/interim/wuerzburg_YYYY-MM.parquet` (Würzburg rows plus earlier stops of the same trips) and per-month checks in `reports/checks/`.

```bash
# Data checks (after step 1); results in reports/checks/
python checks/coverage_check.py      # earlier-stop coverage per period (needs the raw files of 5 sample months in data/raw)
python checks/category_check.py      # train types and line numbers over time
python checks/data_quality_check.py  # duplicates, cancellations, collection gaps
```

## Repository layout

| Path | Content |
| --- | --- |
| `src/` | Pipeline steps `01`–`05`, `config.py` (paths, splits, seed), `features_config.py` (feature whitelist) |
| `src/sql/` | SQL used by the pipeline (DuckDB) |
| `tests/` | Leakage and configuration tests, run before every training run |
| `checks/` | Data check scripts (coverage, categories, data quality) |
| `docs/` | Project plan (requirements, timeline, roles) and decision log (decisions with evidence) |
| `notebooks/` | EDA only, no pipeline logic |
| `app/` | Streamlit dashboard |
| `models/` | Saved models |
| `reports/` | Results table, figures, data checks |
| `data/` | Raw, interim and processed data (not in Git) |

## AI use

AI use is documented in the "Use of generative AI" section of the report.
