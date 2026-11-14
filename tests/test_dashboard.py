"""
Tests of the dashboard's model connection (dashboard/predictor.py) and its lookup tables
(src/08_dashboard_data.py). Run with `pytest`.

The central check: the predictor gives exactly the probabilities that the final run saved.

Reads:  dashboard/data/*, models/*, data/processed/* (tests are skipped when a file is missing)
Writes: nothing
"""
import json
import sys
from datetime import date

import numpy as np
import pandas as pd
import pytest

import config

sys.path.insert(0, str(config.ROOT / "dashboard"))
import predictor as dash  # noqa: E402

DATA = config.ROOT / "dashboard" / "data"
PROCESSED = config.DATA_PROCESSED
needs_dashboard = pytest.mark.skipif(
    not ((DATA / "meta.json").exists() and (config.ROOT / "models" / "m_b.txt").exists()),
    reason="run src/05_train.py --final and src/08_dashboard_data.py first")
needs_scores = pytest.mark.skipif(not (PROCESSED / "predictions_test_b.parquet").exists(), reason="processed data missing")
DAY = date(2026, 9, 15)


@pytest.fixture(scope="module")
def model():
    return dash.ModelPredictor()


def _through_line(model) -> str:
    return next(label for label, row in model._lines.items() if row["has_scenario_b"])


def _starting_line(model) -> str:
    return next(label for label, row in model._lines.items() if not row["is_through"])


# ----------------------------------------------------------------- probability points

def test_probability_points_add_up_and_keep_their_signs():
    log_odds = [1.2, -0.4, 0.05, -0.9]
    probability, base, points = dash.to_probability_points(log_odds, base_log_odds=-1.5)
    assert probability == pytest.approx(1 / (1 + np.exp(-(-1.5 + sum(log_odds)))))
    assert base + sum(points) == pytest.approx(probability, abs=1e-12)
    assert [np.sign(p) for p in points] == [np.sign(v) for v in log_odds]
    assert points[0] / points[1] == pytest.approx(log_odds[0] / log_odds[1])     # shares are kept


def test_probability_points_when_the_contributions_cancel():
    probability, base, points = dash.to_probability_points([0.3, -0.3], base_log_odds=0.2)
    assert probability == pytest.approx(base) and points == [0.0, 0.0]


def test_feature_labels_cover_every_model_feature():
    import features_config
    for name in features_config.FEATURES["B"]:
        assert name in dash.FEATURE_LABELS
    assert dash.feature_label("planned_hour", 7) == "Hour = 07:00"
    assert dash.feature_label("prev_delay", 10.0) == "Delay at previous stop = 10 min"
    assert dash.feature_label("hist_rate_route", float("nan")).endswith("not available")


# ----------------------------------------------------------------- contract of the page

@needs_dashboard
def test_predictor_is_the_model_and_not_the_placeholder(model):
    assert model.is_demo is False
    assert isinstance(dash.load_predictor(), dash.ModelPredictor)
    lines = model.lines()
    assert len(lines) == len(set(lines)) > 10


@needs_dashboard
def test_scenario_a_without_and_scenario_b_with_a_previous_stop_delay(model):
    line = _through_line(model)
    before = model.predict(dash.Query(line, DAY, 17, None))
    en_route = model.predict(dash.Query(line, DAY, 17, 10))
    assert (before.scenario, en_route.scenario) == ("A", "B")
    assert en_route.stops[-1] == "Würzburg Hbf" and len(en_route.stops) >= 2
    for prediction in (before, en_route):
        assert 0 < prediction.probability < 1
        assert prediction.base_value + sum(v for _, v in prediction.contributions) == pytest.approx(prediction.probability, abs=1e-9)
        sizes = [abs(v) for _, v in prediction.contributions]
        assert sizes == sorted(sizes, reverse=True)
    assert en_route.contributions[0][0] == "Delay at previous stop = 10 min"


@needs_dashboard
def test_more_delay_at_the_previous_stop_means_more_risk(model):
    line = _through_line(model)
    p0, p10, p30 = (model.predict(dash.Query(line, DAY, 17, d)).probability for d in (0, 10, 30))
    assert p0 < p10 < p30


@needs_dashboard
def test_a_line_that_starts_at_wuerzburg_is_always_scenario_a(model):
    line = _starting_line(model)
    with_delay = model.predict(dash.Query(line, DAY, 17, 15))
    without = model.predict(dash.Query(line, DAY, 17, None))
    assert with_delay.scenario == "A" and with_delay.stops == ["Würzburg Hbf"]
    assert with_delay.probability == without.probability


@needs_dashboard
def test_thresholds_are_the_ones_chosen_on_validation(model):
    saved = json.loads((config.CHECKS / "thresholds_test.json").read_text(encoding="utf-8"))
    line = _through_line(model)
    assert model.predict(dash.Query(line, DAY, 17, None)).threshold == saved["m_a"]
    assert model.predict(dash.Query(line, DAY, 17, 5)).threshold == saved["m_b"]


@needs_dashboard
def test_delay_rate_grid_is_seven_days_by_nineteen_hours(model):
    for line in model.lines():
        grid = model.delay_rate_grid(line)
        assert len(grid) == 7 and all(len(row) == len(dash.HOURS) == 19 for row in grid)
        values = [v for row in grid for v in row if v is not None]
        assert values and all(0 <= v <= 1 for v in values)


@needs_dashboard
@pytest.mark.parametrize("prev_stop_delay", [None, 10])
def test_hourly_profile_matches_single_predictions(model, prev_stop_delay):
    line = _through_line(model)
    profile = model.hourly_profile(dash.Query(line, DAY, 17, prev_stop_delay))
    assert len(profile) == len(dash.HOURS) and all(0 < p < 1 for p in profile)
    for hour in (5, 17, 23):                                    # same model and inputs as the result card
        single = model.predict(dash.Query(line, DAY, hour, prev_stop_delay)).probability
        assert profile[dash.HOURS.index(hour)] == pytest.approx(single, abs=1e-9)


def test_hourly_profile_in_demo_mode():
    demo = dash.DemoPredictor()
    query = dash.Query(demo.lines()[0], DAY, 8, None)
    profile = demo.hourly_profile(query)
    assert len(profile) == 19 and profile[dash.HOURS.index(8)] == demo.predict(query).probability


def test_html_charts_draw_one_cell_per_weekday_and_hour_and_one_bar_per_hour():
    from ui import charts
    grid = [[0.1 * (d + 1) if h != 5 else None for h in dash.HOURS] for d in range(7)]
    heatmap = charts.delay_heatmap(grid, dash.WEEKDAYS, dash.HOURS, "dark", selected=(4, 17))
    assert heatmap.count('class="hm-cell') == 7 * 19 and heatmap.count("hm-cell empty") == 7
    assert heatmap.count('hm-cell sel"') == 1 and "Fri 17:00" in heatmap
    profile = charts.day_profile([0.2] * 19, dash.HOURS, 17, 0.3, "A")
    assert profile.count('class="dp-col"') == 19 and profile.count(' sel"') == 1
    assert charts._mix(["#000000", "#FFFFFF"], 0) == "#000000" and charts._mix(["#000000", "#FFFFFF"], 1) == "#FFFFFF"


def test_best_hour_is_a_clearly_better_hour_close_to_the_chosen_one():
    from ui import charts
    hours = dash.HOURS
    flat = [0.40] * 19
    assert charts.best_hour(flat, hours, 17, 0.3) is None                       # no real difference
    dip = flat.copy(); dip[hours.index(16)] = 0.30
    assert charts.best_hour(dip, hours, 17, 0.3) == 16
    far = flat.copy(); far[hours.index(6)] = 0.05
    assert charts.best_hour(far, hours, 17, 0.3) is None                        # too far from 17:00
    small = flat.copy(); small[hours.index(18)] = 0.39
    assert charts.best_hour(small, hours, 17, 0.3) is None                      # 1 point is noise
    tie = flat.copy(); tie[hours.index(15)] = tie[hours.index(18)] = 0.30
    assert charts.best_hour(tie, hours, 17, 0.3) == 18                          # closest wins a tie
    assert charts.best_hour(dip, hours, 5, 0.3) is None                         # first hour: only later hours count
    assert "Best nearby choice: 16:00" in charts.day_profile(dip, hours, 17, 0.3, "A")


@needs_dashboard
def test_calibration_note_quotes_the_reliability_table(model):
    line = _through_line(model)
    prediction = model.predict(dash.Query(line, DAY, 17, None))
    note = model.calibration_note(prediction.probability)
    index = min(int(prediction.probability * 10), 9)
    row = next(r for r in model._meta["calibration"]["A"] if r["range"].startswith(f"{index / 10:.1f}"))
    assert f"{row['n']:,}" in note and f"{100 * row['observed_rate']:.0f}%" in note


@needs_dashboard
def test_a_day_outside_the_lookup_tables_does_not_break_the_page(model):
    first, last = model.date_range
    assert (first, last) == (date(2026, 7, 1), date(2026, 10, 31))
    prediction = model.predict(dash.Query(_through_line(model), date(2027, 1, 25), 17, None))
    assert 0 < prediction.probability < 1
    assert any(label.endswith("not available") for label, _ in prediction.contributions)


def test_missing_files_fall_back_to_the_placeholder(tmp_path):
    with pytest.raises(FileNotFoundError):
        dash.ModelPredictor(data_dir=tmp_path, models_dir=tmp_path)


# ----------------------------------------------------------------- same numbers as the final run

@needs_dashboard
@needs_scores
@pytest.mark.parametrize("scenario, features, scores, column", [
    ("A", "features_a.parquet", "predictions_test_a.parquet", "m_a"),
    ("B", "features_b.parquet", "predictions_test_b.parquet", "m_b"),
])
def test_predictor_reproduces_the_scores_of_the_final_run(model, scenario, features, scores, column):
    saved = pd.read_parquet(PROCESSED / scores)[["id", column]]
    rows = pd.read_parquet(PROCESSED / features).merge(saved, on="id")
    assert len(rows) == len(saved) > 10_000
    probabilities = np.array(model.probabilities(rows.to_dict("records"), scenario))
    assert np.abs(probabilities - rows[column].to_numpy()).max() < 1e-9


# ----------------------------------------------------------------- lookup tables

@needs_dashboard
def test_lookup_tables_are_small_and_hold_no_single_departures():
    total = sum(f.stat().st_size for f in DATA.iterdir())
    assert total < 1_000_000                                   # the app never ships the data set
    forbidden = {"id", "delayed", "dep_delay", "train_number", "departure_planned_time"}
    for file in DATA.glob("*.parquet"):
        assert not forbidden & set(pd.read_parquet(file).columns), file.name


@needs_dashboard
def test_step_08_is_refused_before_the_final_run(tmp_path, monkeypatch):
    import importlib
    step = importlib.import_module("08_dashboard_data")
    monkeypatch.setattr(step.train_step, "FINAL_MARKER", tmp_path / "final_run.json")
    with pytest.raises(RuntimeError, match="only after the final run"):
        step.require_final_run()
    assert step.line_label("regional", "RB53", "Bamberg", False) == "RB53 to Bamberg (starts at Würzburg)"
    assert step.line_label("long_distance", None, "München Hbf", True) == "ICE/IC to München Hbf"


# ----------------------------------------------------------------- "How does this work?"

@needs_dashboard
def test_explanation_quotes_the_final_run_and_no_typed_numbers(model):
    import about
    facts = model.facts()
    text = about.how_it_works(facts, is_demo=False)
    saved = json.loads((config.CHECKS / "thresholds_test.json").read_text(encoding="utf-8"))
    assert facts["performance"]["A"]["rows"] == 31_956 and facts["training_rows"] == 198_377
    # the same class metrics as reports/results.md (M-A: precision 0.540, recall 0.718; M-B: 0.903, 0.807)
    assert round(facts["performance"]["A"]["precision"], 3) == 0.540 and round(facts["performance"]["A"]["recall"], 3) == 0.718
    assert round(facts["performance"]["B"]["precision"], 3) == 0.903 and round(facts["performance"]["B"]["recall"], 3) == 0.807
    for expected in ("198,377", "31,956", "54 of 100", "72 of 100", "90 of 100", "81 of 100", "6 or more minutes late"):
        assert expected in text
    assert "Demo mode" not in text and saved["m_a"] > 0


def test_explanation_in_demo_mode_and_without_facts():
    import about
    demo = about.how_it_works(None, is_demo=True)
    assert "Demo mode" in demo and "of 100" not in demo
    plain = about.how_it_works(None, is_demo=False)
    assert "Demo mode" not in plain and "Two moments" in plain
