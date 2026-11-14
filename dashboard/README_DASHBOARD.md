# Dashboard (Streamlit)

Run from the repository root (as Streamlit Community Cloud does): `pip install -r dashboard/requirements.txt` then `streamlit run dashboard/app.py`.
The page needs the final models in `../models/` and the lookup tables in `data/`
(`python src/08_dashboard_data.py` from the repository root; both are tracked in Git).
Without them it falls back to demo mode and says so.

## Status by step (see DESIGN_PLAN.md §8)

| Step | What | Status |
|---|---|---|
| 1 | Tokens + light/dark theme (`ui/tokens.py`, `.streamlit/config.toml`) | Done |
| 2 | Layout: header, inputs, result card, route, explanation, heatmap, footer | Done, with placeholder numbers |
| 3 | Charts bound to the palette (SHAP bars, heatmap) | Done, with placeholder numbers |
| 4 | Motion: rolling counter + risk bar, route, staggered SHAP bars | Done |
| 5 | Connect the trained model (`predictor.py`) | Done (14 Nov 2026): `ModelPredictor`, tests in `tests/test_dashboard.py` |
| 6 | Polish: banded risk bar, vertical route on mobile, selected cell in the heatmap, calibration-note slot | Done |
| 7 | Deploy on Streamlit Community Cloud + recorded backup | Files prepared (14 Nov 2026); deploy on share.streamlit.io and backup video open |

## Connecting the model (step 5)

Write a class in `predictor.py` with `is_demo = False` and the three methods of
`Predictor`, and return it from `load_predictor()`:

- `lines()` – selectable train types / lines from the lookup table.
- `predict(query)` – probability from M-A (no previous-stop delay) or M-B,
  the validation threshold, the SHAP base value and per-feature contributions
  **in probability points**, and the earlier stops ending with "Würzburg Hbf".
- `delay_rate_grid(line)` – 7 x 19 grid (Mon–Sun x 05–23 h) of historical delay rates.
- `calibration_note(probability)` – one sentence from the test-set reliability table, or `None` to show nothing.

The demo banner disappears automatically once `is_demo` is False.

### How `ModelPredictor` answers a query (step 5, done)

The page asks for a line, a day and an hour, not for one real departure. The predictor
therefore builds a **typical departure** and gives it to the saved final models:

| Feature group | Value used |
|---|---|
| Timetable | The chosen line (service, line, destination, through train or not); stop number and planned stop time = median of the line in that hour |
| Calendar, weather | Those of the chosen day and hour (observed weather) |
| 28-day delay rates | The values the feature step computed for that day |
| Previous stop (scenario B) | Delay typed in by the user; the delay at the stop before it is taken to be the same; planned minutes since the previous stop = median of the line |

- **Days:** 1 July – 31 October 2026 (the test period, decision D15). The date field is limited to it.
- **Lines:** 37 line-and-destination pairs with at least 150 departures in that period that run between 05 and 23 h (89% of the departures). Night trains are not offered because the page has no hours before 05.
- **Scenario:** no previous-stop delay → M-A; a delay → M-B. A line that starts at Würzburg has no previous stop and is always answered by M-A; its name says "(starts at Würzburg)".
- **Threshold:** read from `../models/m_a.json` / `m_b.json` (max F1 on validation, saved by the final run).
- **Contributions:** SHAP values are additive in log-odds. They are multiplied by one common factor so that base value + contributions equals the predicted probability exactly; signs and shares are kept. The base value is the probability at the model's average log-odds (18% for M-A, 38% for M-B), which is lower than the average delay rate.
- **Heatmap:** delay rate per weekday and hour over the whole data period (July 2024 – October 2026); cells with fewer than 10 departures stay empty.
- **Calibration note:** from the reliability table of the test period, for the model that made the last prediction.

How close is the typical departure to real ones? Checked on 14 Nov 2026: for real departures the predictor
returns exactly the scores of the final run (difference 0). A typical departure differs from the real
departures of the same line, day and hour by 0.3 percentage points on average for M-A (95% under 1.4) and
by 2.1 points for M-B (95% under 11.3; real trains differ in their stop-before-previous delay and timing).

## "How does this work?" (added 14 Nov 2026)

A collapsed section under the header explains the page in plain language: what is
predicted, the two moments, how the model was built and checked, how good it is, how to
read the page, and its limits. The text is in `about.py`; its numbers come from
`data/meta.json` (`ModelPredictor.facts()`), so they change with the lookup tables and are
never typed in. It uses Streamlit's own expander, so `ui/` is unchanged.

## Deploy on Streamlit Community Cloud (step 7)

Prepared on 14 Nov 2026; tested in a clean Python 3.10 environment with only `dashboard/requirements.txt`, started from the repository root: real models load (no demo banner, 37 lines).

- Community Cloud runs `streamlit run` from the repository root and takes the first `requirements.txt` it finds next to the entrypoint, then at the root. `dashboard/requirements.txt` therefore keeps the app's environment small (streamlit, plotly, lightgbm, pandas, pyarrow); the root `requirements.txt` is for the full pipeline.
- `packages.txt` at the repository root installs `libgomp1`, the OpenMP library LightGBM needs on Linux (Cloud reads `packages.txt` only at the root).
- `dashboard/.streamlit/config.toml` sits next to the entrypoint, which Cloud accepts as the app's own configuration.
- Settings on share.streamlit.io: repository `Umutakkopru/pds-db-delays`, branch `main`, main file path `dashboard/app.py`, Python 3.10 under Advanced settings, no secrets.
- Models (`models/m_*.txt|json`) and lookup tables (`dashboard/data/`) are tracked in Git, so nothing is downloaded at start-up. Every push to `main` redeploys the app.

## Notes

- Streamlit's HTML sanitizer removes inline SVG and any stylesheet containing `<`;
  the train marker and the counter are therefore built with plain CSS.
- After editing files in `ui/`, restart `streamlit run` (the package is cached).
- Animations replay only when the prediction changes and are disabled under
  `prefers-reduced-motion`.
