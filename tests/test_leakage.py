"""
Automated leakage checks. Run with `pytest` before every training run.

Current tests cover the feature whitelist and the split definition.
To add with step 04 (week 3): time-travel test for history features and the
earlier-stop timing test for scenario B (see CLAUDE.md, Leakage safeguards).
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


@pytest.mark.parametrize("scenario", ["A", "B"])
def test_no_propagation_features_in_scenario_a(scenario):
    # Scenario A must not see anything from earlier stops of the same trip.
    if scenario != "A":
        pytest.skip("only relevant for scenario A")
    prev_like = [c for c in features_config.FEATURES["A"] if c.startswith("prev")]
    assert not prev_like, f"Earlier-stop features in scenario A: {prev_like}"


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
