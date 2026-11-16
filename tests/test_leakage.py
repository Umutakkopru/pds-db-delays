"""
Automated leakage checks. Run with `pytest` before every training run.

The tests here check the feature lists and the split definition: no forbidden
column in any scenario, no propagation feature in scenario A, scenario B adds
only propagation features, splits chronological, disjoint and inside the data
period, one test period for both scenarios, scenario B training from full
coverage on. They compare column names and dates only. The checks on the data
itself (feature tables equal the whitelist, time-travel test of the history
features, earlier stops before the Würzburg arrival) are in
tests/test_features.py; the guard on the test period is in
tests/test_final_run.py.
"""
import pandas as pd
import pytest

import config
import features_config


@pytest.mark.parametrize("scenario", ["A", "B"])
def test_no_forbidden_column_in_features(scenario):
    used = set(features_config.FEATURES[scenario])
    leaked = used & features_config.FORBIDDEN_COLUMNS
    assert not leaked, f"Forbidden columns in scenario {scenario}: {sorted(leaked)}"


def test_no_propagation_features_in_scenario_a():
    # Scenario A must not see anything from earlier stops of the same trip.
    # Naming rule (src/features_config.py): earlier-stop features start with "prev_".
    prefix = features_config.PROPAGATION_PREFIX
    prev_like = [c for c in features_config.FEATURES["A"] if c.startswith(prefix)]
    assert not prev_like, f"Earlier-stop features in scenario A: {prev_like}"


def test_scenario_b_adds_only_propagation_features():
    # B = everything in A plus earlier-stop features (D3).
    a, b = features_config.FEATURES["A"], features_config.FEATURES["B"]
    extra = [c for c in b if c not in a]
    not_prev = [c for c in extra if not c.startswith(features_config.PROPAGATION_PREFIX)]
    assert not not_prev, f"Scenario B features that are neither in A nor earlier-stop features: {not_prev}"


@pytest.mark.parametrize("scenario", ["A", "B"])
def test_splits_are_chronological_and_disjoint(scenario):
    s = config.SPLITS[scenario]
    bounds = [pd.Timestamp(x) for part in ("train", "val", "test") for x in s[part]]
    tr0, tr1, va0, va1, te0, te1 = bounds
    assert tr0 < tr1 <= va0 < va1 <= te0 < te1


def test_same_test_period_for_both_scenarios():
    assert config.SPLITS["A"]["test"] == config.SPLITS["B"]["test"]


def test_scenario_b_trains_only_with_full_coverage():
    # Literal date on purpose (decision log D6): comparing the split start with
    # config.FULL_COVERAGE_START would compare the constant with itself.
    # tests/test_data.py checks the same date against the data.
    first_full_day = pd.Timestamp("2025-11-03")
    assert pd.Timestamp(config.FULL_COVERAGE_START) >= first_full_day
    assert pd.Timestamp(config.SPLITS["B"]["train"][0]) >= first_full_day


def test_splits_inside_data_period():
    first = pd.Timestamp(config.FIRST_MONTH + "-01")
    last_end = pd.Timestamp(config.LAST_MONTH + "-01") + pd.offsets.MonthBegin(1)
    for scenario, s in config.SPLITS.items():
        assert pd.Timestamp(s["train"][0]) >= first, scenario
        assert pd.Timestamp(s["test"][1]) <= last_end, scenario
