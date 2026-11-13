"""
Tests of the three run modes of src/05_train.py and of the lock on the final run. Run with `pytest`.

Nothing here runs the final mode on real data: the test period stays untouched.

Reads:  data/processed/features_*.parquet (tests marked needs_features)
Writes: only temporary files
"""
import importlib

import numpy as np
import pandas as pd
import pytest

import config

train_step = importlib.import_module("05_train")  # module name starts with a digit
feat = importlib.import_module("04_features")

needs_features = pytest.mark.skipif(
    not (all(f.exists() for f in train_step.FEATURE_FILES.values()) and train_step.SENSITIVITY_FILE.exists()),
    reason="run src/04_features.py first")
TEST_START = pd.Timestamp(config.SPLITS["A"]["test"][0])


# ----------------------------------------------------------------- the lock

def test_final_run_is_refused_when_the_marker_exists(tmp_path):
    marker = tmp_path / "final_run.json"
    train_step.check_final_run_allowed(marker, dirty=False)          # first time: allowed
    marker.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="already been done"):
        train_step.check_final_run_allowed(marker, dirty=False)


def test_final_run_is_refused_with_uncommitted_changes(tmp_path):
    with pytest.raises(RuntimeError, match="[Uu]ncommitted"):
        train_step.check_final_run_allowed(tmp_path / "final_run.json", dirty=True)


def test_marker_records_the_commit(tmp_path):
    marker = tmp_path / "final_run.json"
    train_step.write_final_marker({"rows_a": 1}, marker)
    text = marker.read_text(encoding="utf-8")
    assert '"commit"' in text and '"finished"' in text and '"rows_a": 1' in text


def test_the_final_run_has_not_happened_yet_or_is_complete():
    # Either no final run yet, or all of its outputs exist together.
    outputs = [train_step.FINAL_MARKER, train_step.MODES["final"][1], train_step.prediction_file("final", "A")]
    assert len({f.exists() for f in outputs}) == 1, "partial outputs of a final run found"


def test_modes_write_to_different_files():
    results = {train_step.MODES[m][1] for m in train_step.MODES}
    predictions = {train_step.prediction_file(m, "A") for m in train_step.MODES}
    assert len(results) == 3 and len(predictions) == 3


# ----------------------------------------------------------------- rehearsal periods

@pytest.mark.parametrize("scenario", ["A", "B"])
def test_rehearsal_periods_are_in_order_and_inside_development_data(scenario):
    r = config.REHEARSAL_SPLITS[scenario]
    bounds = [pd.Timestamp(x) for part in ("train", "val", "eval") for x in r[part]]
    tr0, tr1, va0, va1, ev0, ev1 = bounds
    assert tr0 < tr1 == va0 < va1 == ev0 < ev1 <= TEST_START
    assert r["eval"] == config.SPLITS[scenario]["val"]               # the validation period plays the test period
    assert r["train"][0] == config.SPLITS[scenario]["train"][0]


@needs_features
@pytest.mark.parametrize("mode", ["validation", "rehearsal"])
@pytest.mark.parametrize("scenario", ["A", "B"])
def test_development_modes_never_see_the_test_period(mode, scenario):
    frames = train_step.frames_for(mode, scenario)
    for part in ("train", "val", "eval"):
        assert len(frames[part]) > 0
        assert frames[part]["departure_planned_time"].max() < TEST_START, (mode, scenario, part)
    assert frames["train"]["departure_planned_time"].max() < frames["val"]["departure_planned_time"].min()
    if mode == "rehearsal":
        assert frames["val"]["departure_planned_time"].max() < frames["eval"]["departure_planned_time"].min()
        assert not (set(frames["train"]["id"]) | set(frames["val"]["id"])) & set(frames["eval"]["id"])


@needs_features
def test_rehearsal_scores_the_same_rows_as_validation():
    for scenario in ("A", "B"):
        rehearsal = train_step.frames_for("rehearsal", scenario)["eval"]
        validation = train_step.frames_for("validation", scenario)["eval"]
        assert set(rehearsal["id"]) == set(validation["id"])


# ----------------------------------------------------------------- sensitivity rows

def test_sensitivity_rows_of_the_test_period_are_refused():
    with pytest.raises(ValueError):
        train_step.load_sensitivity_rows(config.SPLITS["A"]["test"])


@needs_features
def test_sensitivity_rows_are_not_modelling_rows_and_have_the_right_outcome():
    extra = pd.read_parquet(train_step.SENSITIVITY_FILE)
    main = pd.read_parquet(train_step.FEATURE_FILES["A"], columns=["id"])
    assert not set(extra["id"]) & set(main["id"])
    assert set(extra["sensitivity_set"]) == {"canceled", "no_plan_record"}
    assert (extra.loc[extra["sensitivity_set"] == "canceled", "delayed"] == 1).all()     # D9: counted as delayed
    assert extra["delayed"].isin([0, 1]).all()
    assert list(extra.columns) == list(pd.read_parquet(train_step.FEATURE_FILES["A"]).columns) + ["sensitivity_set"]


def test_sensitivity_table_adds_the_extra_rows():
    rng = np.random.default_rng(0)
    def rows(n, rate):
        y = (rng.random(n) < rate).astype(int)
        return pd.DataFrame({"delayed": y, "x": 0.5 * y + rng.random(n) * 0.5})
    main = rows(400, 0.2)
    extra = pd.concat([rows(50, 1.0).assign(delayed=1, sensitivity_set="canceled"),
                       rows(80, 0.5).assign(sensitivity_set="no_plan_record")], ignore_index=True)
    table = train_step.sensitivity_table(main, extra, {"B2 model": lambda df: df["x"].to_numpy()})
    assert list(table["n"]) == ["400", "450", "480"]
    assert {"PR-AUC B2", "ROC-AUC B2"} <= set(table.columns)


def test_excluded_rows_never_feed_history_of_sensitivity_rows():
    # A cancelled departure gets the history of its key, built from modelling rows only.
    import duckdb
    from datetime import date, timedelta
    start = date(2026, 1, 1)
    rows = []
    for i in range(40):
        day = start + timedelta(days=i)
        for k in range(10):
            planned = pd.Timestamp(day) + pd.Timedelta(hours=8, minutes=k)
            rows.append({"id": f"{day}-{k}", "service_date": day, "departure_planned_time": planned,
                         "arrival_planned_time": pd.NaT, "split_a": "train", "split_b": None, "delayed": int(k < 2),
                         "service": "regional", "line_id": "RB53", "final_destination_station": "X",
                         "is_through": False, "has_prev_stop": False, "train_line_station_num": 1,
                         "exclude_reason": None, "canceled": False, "dep_delay": 7.0 if k < 2 else 0.0})
    clean = pd.DataFrame(rows)
    target = start + timedelta(days=35)
    cancelled = clean[clean["service_date"] == target].head(1).assign(
        id="cancelled", exclude_reason="canceled", canceled=True, delayed=0,
        departure_planned_time=pd.Timestamp(target) + pd.Timedelta(hours=9))     # an hour without other departures
    con = duckdb.connect()
    con.register("clean_t", pd.concat([clean, cancelled], ignore_index=True))
    hours = pd.date_range(pd.Timestamp(start), periods=41 * 24, freq="h")
    con.register("weather_t", pd.DataFrame({"local_hour": hours, **{c: 0.0 for c in config.WEATHER_VARIABLES.values()}}))
    con.register("calendar_t", pd.DataFrame({"service_date": sorted(clean["service_date"].unique()),
                                             "is_public_holiday": False, "is_school_holiday": False, "is_bridge_day": False}))
    out = con.sql(feat.sensitivity_sql("clean_t", "weather_t", "calendar_t")).df()
    assert list(out["id"]) == ["cancelled"] and out.loc[0, "delayed"] == 1
    assert out.loc[0, "hist_rate_route"] == pytest.approx(0.2)       # 2 of 10 delayed on each of the 28 window days
    assert pd.isna(out.loc[0, "hist_rate_service_hour"])              # no modelling departure at 9 o'clock: no rate


# ----------------------------------------------------------------- operating points per service (P1), ablations (P2)

def _service_rows() -> tuple[pd.DataFrame, np.ndarray]:
    """Regional trains are rarely late and get low scores; long-distance trains are often late."""
    rows = pd.DataFrame({
        "service": ["regional"] * 6 + ["long_distance"] * 6 + ["other"],
        "delayed": [0, 0, 0, 0, 1, 1,  0, 0, 1, 1, 1, 1,  1],
    })
    score = np.array([0.02, 0.03, 0.04, 0.05, 0.20, 0.25,  0.30, 0.35, 0.60, 0.70, 0.80, 0.90,  0.50])
    return rows, score


def test_service_thresholds_come_from_validation_rows_and_small_services_keep_the_overall_one(monkeypatch):
    monkeypatch.setattr(train_step, "MIN_ROWS_OWN_THRESHOLD", 5)
    val, score = _service_rows()
    thresholds = train_step.service_thresholds(val, score, overall=0.6)
    assert thresholds["regional"] == pytest.approx(0.20)        # separates the two late regional trains
    assert thresholds["long_distance"] == pytest.approx(0.60)
    assert thresholds["other"] == 0.6                           # one row only: overall threshold


def test_operating_point_table_applies_the_given_thresholds(monkeypatch):
    monkeypatch.setattr(train_step, "MIN_ROWS_OWN_THRESHOLD", 5)
    rows, score = _service_rows()
    table = train_step.operating_point_table(rows, score, overall=0.6, per_service={"regional": 0.20, "long_distance": 0.60})
    table = table.set_index("Service")
    # overall threshold 0.6: no regional train is flagged; own threshold 0.2: both late ones, no false alarm
    assert table.loc["regional", "Overall threshold: P / R / F1"].split(" / ")[1] == "0.000"
    assert table.loc["regional", "Own threshold: P / R / F1"] == "1.000 / 1.000 / 1.000"
    assert table.loc["other", "Own threshold"] == "0.600"       # not in per_service: overall threshold
    assert table.loc["other", "Delayed in top 5%"] == "–"       # too few rows to say anything
    assert table.loc["All departures", "Rows"] == "13"
    # changing the outcomes of the scored rows must not move any threshold
    flipped = rows.assign(delayed=1 - rows["delayed"])
    again = train_step.operating_point_table(flipped, score, 0.6, {"regional": 0.20, "long_distance": 0.60}).set_index("Service")
    assert list(again["Own threshold"]) == list(table["Own threshold"])


def test_ablation_models_are_not_saved_with_the_predictions(tmp_path):
    rows = pd.DataFrame({"id": ["a", "b"], "service_date": pd.to_datetime(["2026-01-01", "2026-01-02"]), "delayed": [0, 1]})
    path = tmp_path / "predictions.parquet"
    train_step.save_predictions(rows, {train_step.M_B: np.array([0.1, 0.9]),
                                       train_step.M_B_NO_WEATHER: np.array([0.5, 0.5]),
                                       train_step.M_A_PRIME_NO_WEATHER: np.array([0.5, 0.5])}, path)
    saved = pd.read_parquet(path)
    assert list(saved.columns) == ["id", "service_date", "delayed", "m_b"]
    assert list(saved["m_b"]) == [0.1, 0.9]                     # not overwritten by the ablation model


def test_saved_thresholds_include_the_per_service_ones():
    import json
    for mode in ("validation", "rehearsal"):
        path = train_step.threshold_file(mode)
        if not path.exists():
            pytest.skip("run src/05_train.py first")
        saved = json.loads(path.read_text(encoding="utf-8"))
        per_service = saved["m_a_per_service"]
        assert {"regional", "long_distance"} <= set(per_service)
        assert per_service["regional"] < saved["m_a"]           # rare delays need a lower threshold
        assert all(0 < t < 1 for t in per_service.values())
