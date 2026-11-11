"""
Tests of the SHAP step (src/07_explain.py). Run with `pytest`.

Made-up data only, plus name checks on the written importance file. Nothing
here loads test-period rows.

Reads:  reports/checks/shap_importance_validation.csv (test marked needs_output)
Writes: only temporary files
"""
import importlib

import numpy as np
import pandas as pd
import pytest

import config
import features_config
import models

explain = importlib.import_module("07_explain")  # module name starts with a digit

IMPORTANCE_FILE = config.CHECKS / "shap_importance_validation.csv"
needs_output = pytest.mark.skipif(not IMPORTANCE_FILE.exists(), reason="run src/07_explain.py first")
FEATURES = ["service", "planned_hour", "temperature_c"]


def _made_up(n: int = 3000, seed: int = 0) -> pd.DataFrame:
    """Delay depends on the service and a little on the hour; temperature is noise."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "service": rng.choice(["regional", "long_distance"], n),
        "planned_hour": rng.integers(5, 24, n),
        "temperature_c": rng.normal(10, 8, n),
    })
    p = 0.08 + 0.45 * (df["service"] == "long_distance") + 0.01 * (df["planned_hour"] - 5)
    df["delayed"] = (rng.random(n) < p).astype(int)
    return df


@pytest.fixture(scope="module")
def fitted():
    train, val = _made_up(seed=0), _made_up(seed=1)
    out = models.fit(train, val, FEATURES, {"num_leaves": 7, "min_child_samples": 50})
    return {**out, "val": val, "X": models.prepare(val, FEATURES, out["categories"])}


def test_shap_values_add_up_and_rank_the_real_cause_first(fitted):
    values, base = explain.shap_values(fitted["model"].booster_, fitted["X"])   # raises if they do not add up
    assert values.shape == (len(fitted["val"]), len(FEATURES))
    raw = fitted["model"].booster_.predict(fitted["X"], raw_score=True)
    assert np.allclose(values.sum(axis=1) + base, raw, atol=1e-6)
    table = explain.importance_table(values, FEATURES)
    assert table["feature"].iloc[0] == "service"
    assert table["feature"].iloc[-1] == "temperature_c"
    assert table["share"].sum() == pytest.approx(1.0)
    assert list(table["rank"]) == [1, 2, 3]


def test_shap_check_fails_when_values_do_not_add_up(fitted, monkeypatch):
    booster = fitted["model"].booster_
    real = booster.predict

    def broken(X, **kwargs):
        out = real(X, **kwargs)
        return out + 0.01 if kwargs.get("raw_score") else out

    monkeypatch.setattr(booster, "predict", broken)
    with pytest.raises(RuntimeError, match="do not add up"):
        explain.shap_values(booster, fitted["X"])


def test_every_feature_has_exactly_one_group():
    for scenario in ("A", "B"):
        for feature in features_config.FEATURES[scenario]:
            assert sum(feature in members for members in explain.GROUPS.values()) == 1, feature
    assert set(explain.WATCH_FEATURES) <= set(features_config.FEATURES["A"])


def test_watch_notes_flag_only_the_top_ranks():
    table = pd.DataFrame({"rank": [1, 2, 3, 4], "feature": ["service", "destination", "weekday", "stop_position"],
                          "share": [0.4, 0.3, 0.2, 0.1]})
    notes = explain.watch_notes(table)
    assert len(notes) == 2                                   # hist_n_route is not in the table
    assert "look closer" in next(n for n in notes if "destination" in n)
    assert "fine" in next(n for n in notes if "stop_position" in n)


def test_dependence_table_bins_are_closed_on_the_left():
    table = explain.dependence_table(np.array([1.0, 3.0, 5.0, 7.0]), pd.Series([0, 5, 6, 30]),
                                     [-np.inf, 6, np.inf], ["under 6", "6+"])
    assert list(table["rows"]) == [2, 2]
    assert list(table["mean_shap"]) == [2.0, 6.0]            # the value 6 belongs to "6+"


def test_outside_training_range_counts_values_the_model_never_saw():
    train = pd.DataFrame({"service": ["a", "b"], "is_through": [True, False],
                          "temperature_c": [0.0, 20.0], "planned_hour": [5, 23]})
    rows = pd.DataFrame({"service": ["c"] * 4, "is_through": [True] * 4,
                         "temperature_c": [10.0, 25.0, 30.0, np.nan], "planned_hour": [6, 7, 8, 9]})
    table = explain.outside_training_range(train, rows, ["service", "is_through", "temperature_c", "planned_hour"])
    assert list(table["feature"]) == ["temperature_c"]       # text and True/False columns are skipped
    assert table["share_outside"].iloc[0] == pytest.approx(2 / 3)   # missing values are ignored


def test_best_setting_is_one_of_the_grid_settings():
    for name in (explain.M_A, explain.M_A_PRIME, explain.M_B):
        if not (config.CHECKS / f"tuning_{explain.SLUGS[name]}.csv").exists():
            pytest.skip("run src/05_train.py first")
        params, n_trees = explain.best_setting(name)
        assert params in models.TUNING_GRID
        assert 0 < n_trees <= models.MAX_TREES


# ----------------------------------------------------------------- test set

def test_test_set_is_refused_before_the_final_run(tmp_path):
    with pytest.raises(RuntimeError, match="only after the final run"):
        explain.final_models(models_dir=tmp_path, marker=tmp_path / "final_run.json")


def test_saved_model_gives_the_same_explanation(fitted, tmp_path, monkeypatch):
    """The files written by the final run are enough to explain a model again."""
    monkeypatch.setattr(explain.train_step, "MODELS_DIR", tmp_path)
    name = explain.train_step.M_B
    explain.train_step.save_final_models(
        {name: {"model": fitted["model"], "features": FEATURES, "categories": fitted["categories"],
                "params": {"num_leaves": 7}, "n_trees": fitted["n_trees"]}}, {name: 0.5})
    loaded = explain.load_saved_model(tmp_path, explain.M_B)
    assert loaded["features"] == FEATURES
    X = models.prepare(fitted["val"], loaded["features"], loaded["categories"])
    before, _ = explain.shap_values(fitted["model"].booster_, fitted["X"])
    after, _ = explain.shap_values(loaded["booster"], X)
    assert np.allclose(before, after, atol=1e-6)


# ----------------------------------------------------------------- written output

@needs_output
def test_output_explains_only_whitelisted_features():
    table = pd.read_csv(IMPORTANCE_FILE)
    assert not set(table["feature"]) & features_config.FORBIDDEN_COLUMNS
    for name, scenario in explain.FEATURE_SET.items():
        assert list(table.loc[table["model"] == name, "feature"].sort_values()) == sorted(features_config.FEATURES[scenario])
    a_models = table[table["model"].isin([explain.M_A, explain.M_A_PRIME])]
    assert not a_models["feature"].str.startswith(features_config.PROPAGATION_PREFIX).any()
