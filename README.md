# Predicting Train Delays at Würzburg Hbf

Practical Data Science capstone, Information Systems M.Sc., University of Würzburg, WiSe 2026/27 (Group 18).

We predict whether a train departs Würzburg Hbf 6 or more minutes late (Deutsche Bahn's punctuality threshold), once before the trip (scenario A) and once while the train is en route (scenario B), and compare the two. Project context, decisions and plan: [`CLAUDE.md`](CLAUDE.md).

**Data:** [Deutsche Bahn Data](https://huggingface.co/datasets/piebro/deutsche-bahn-data) (CC BY 4.0, Deutsche Bahn), July 2024 – October 2026.

## Setup (macOS, Apple Silicon)

```bash
brew install libomp                 # needed by LightGBM on macOS
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip freeze > requirements-lock.txt  # once; commit the lock file
pytest                              # leakage tests must pass
```

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

## Repository layout

| Path | Content |
| --- | --- |
| `src/` | Pipeline steps `01`–`05`, `config.py` (paths, splits, seed), `features_config.py` (feature whitelist) |
| `src/sql/` | SQL used by the pipeline (DuckDB) |
| `tests/` | Leakage tests, run before every training run |
| `checks/` | One-off exploration scripts (coverage check) |
| `notebooks/` | EDA only, no pipeline logic |
| `app/` | Streamlit dashboard |
| `models/` | Saved models |
| `reports/` | Results table, figures, data checks |
| `data/` | Raw, interim and processed data (not in Git) |

## AI use

AI use is documented in the "Use of generative AI" section of the report.
