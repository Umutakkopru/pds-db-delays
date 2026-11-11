"""
Tests of the error-analysis helpers (src/06_error_analysis.py). Run with `pytest`.

Reads:  nothing from data/ (small made-up data)
Writes: nothing
"""
import importlib

import numpy as np
import pandas as pd
import pytest

ea = importlib.import_module("06_error_analysis")  # module name starts with a digit


def test_calibration_table_counts_and_rates():
    proba = np.array([0.05, 0.05, 0.15, 0.95, 0.95, 0.95, 0.95])
    y = np.array([0, 0, 1, 1, 1, 1, 0])
    table = ea.calibration_table(y, proba, bins=10).set_index("range")
    assert table["n"].sum() == 7
    assert table.loc["0.0-0.1", "n"] == 2 and table.loc["0.0-0.1", "observed_rate"] == 0
    assert table.loc["0.9-1.0", "observed_rate"] == pytest.approx(0.75)
    assert table.loc["0.9-1.0", "mean_predicted"] == pytest.approx(0.95)


def test_expected_calibration_error():
    perfect = pd.DataFrame({"n": [10, 30], "mean_predicted": [0.2, 0.8], "observed_rate": [0.2, 0.8]})
    off = pd.DataFrame({"n": [10, 30], "mean_predicted": [0.2, 0.8], "observed_rate": [0.4, 0.8]})
    assert ea.expected_calibration_error(perfect) == 0
    assert ea.expected_calibration_error(off) == pytest.approx(0.2 * 10 / 40)


def test_confusion_matrix_counts():
    y = np.array([0, 0, 1, 1, 1])
    score = np.array([0.1, 0.9, 0.2, 0.8, 0.7])
    table = ea.confusion(y, score, 0.5)
    assert list(table["predicted on time"]) == [1, 1]      # one true negative, one missed delay
    assert list(table["predicted delayed"]) == [1, 2]      # one false alarm, two hits


def _slice_frame(n_big: int, n_small: int) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n = n_big + n_small
    y = rng.integers(0, 2, n)
    return pd.DataFrame({
        "group": ["big"] * n_big + ["small"] * n_small,
        "delayed": y,
        "m": np.clip(0.6 * y + rng.normal(0.2, 0.15, n), 0, 1),
    })


def test_small_slices_are_left_out():
    df = _slice_frame(ea.MIN_SLICE_ROWS + 50, ea.MIN_SLICE_ROWS - 50)
    table = ea.slice_table(df, ["group"], {"m": 0.5}, "A: test")
    assert list(table["value"]) == ["big"]
    assert table.loc[0, "n"] == ea.MIN_SLICE_ROWS + 50 and 0.5 < table.loc[0, "roc_auc"] <= 1


def test_pivot_keeps_the_scenarios_apart():
    # Regression test: a slice name used in both scenarios (service, month) must not mix their row counts.
    a = ea.slice_table(_slice_frame(600, 0), ["group"], {"m": 0.5}, "A: all departures")
    b = ea.slice_table(_slice_frame(400, 0), ["group"], {"m": 0.5}, "B: through trains with an earlier stop")
    both = pd.concat([a, b], ignore_index=True)
    assert ea.pivot_slices(both, "A", "group", "pr_auc", ["m"]).loc[0, "n"] == 600
    assert ea.pivot_slices(both, "B", "group", "pr_auc", ["m"]).loc[0, "n"] == 400


def test_rule_against_model_by_hand():
    b = pd.DataFrame({
        "previous_stop_delay": ["6-9 min"] * 4 + ["20+ min"] * 2,
        "delayed": [0, 0, 0, 1, 1, 1],
        "b3": [6.0, 7.0, 8.0, 9.0, 25.0, 30.0],            # the rule says "delayed" for all six
        "m_b": [0.2, 0.3, 0.6, 0.9, 0.95, 0.99],            # the model says "delayed" for the last four
    })
    table = ea.rule_vs_model(b, threshold_m_b=0.5).set_index("previous_stop_delay")
    assert table.loc["6-9 min", "accuracy_rule"] == pytest.approx(1 / 4)
    assert table.loc["6-9 min", "accuracy_model"] == pytest.approx(3 / 4)
    assert table.loc["6-9 min", "errors_rule"] == 3 and table.loc["6-9 min", "errors_model"] == 1
    assert table.loc["20+ min", "accuracy_rule"] == 1 and table.loc["20+ min", "errors_model"] == 0


def _error_row(delayed, dep_delay, prev_delay=None):
    row = {"delayed": delayed, "score": 0.03 if delayed else 0.97, "dep_delay": dep_delay,
           "service": "regional", "planned_hour": 8}
    if prev_delay is not None:
        row.update({"prev_delay": prev_delay, "prev_minutes_to_departure": 20.0})
    return pd.Series(row)


@pytest.mark.parametrize("row, expected", [
    (_error_row(1, 6.0), "missed, just over the threshold"),
    (_error_row(1, 8.0, prev_delay=0.0), "missed, just over the threshold"),        # closeness to the threshold comes first
    (_error_row(1, 24.0, prev_delay=1.0), "missed, delay arose after an on-time previous stop"),
    (_error_row(1, 62.0), "missed, major delay"),                                    # scenario A row: no previous stop
    (_error_row(1, 14.0), "missed, moderate delay"),
    (_error_row(1, 14.0, prev_delay=float("nan")), "missed, moderate delay"),        # missing previous stop = scenario A
    (_error_row(0, 4.0, prev_delay=31.0), "false alarm, just under the threshold"),
    (_error_row(0, 0.0, prev_delay=22.0), "false alarm, train made up its delay"),
    (_error_row(0, 1.0), "false alarm, other"),
])
def test_failure_types(row, expected):
    assert ea.failure_type(row).startswith(expected)
