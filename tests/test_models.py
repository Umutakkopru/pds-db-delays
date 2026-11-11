"""
Tests of the LightGBM helpers (src/models.py). Run with `pytest`.

Reads:  nothing from data/ (small made-up data)
Writes: nothing
"""
import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

import features_config
import models

FEATURES = ["service", "line_id", "planned_hour", "is_through", "dwell_min"]


def _frame(n: int, seed: int, lines=("RB53", "RE10", None)) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "service": rng.choice(["regional", "long_distance"], n),
        "line_id": rng.choice(list(lines), n),
        "planned_hour": rng.integers(5, 23, n),
        "is_through": rng.choice([True, False], n),
        "dwell_min": np.where(rng.random(n) < 0.3, np.nan, rng.integers(1, 15, n)),
    })
    signal = (df["service"] == "long_distance") * 0.5 + df["planned_hour"] / 60
    df["delayed"] = (rng.random(n) < signal).astype(int)
    return df


# ----------------------------------------------------------------- preparation

def test_categories_come_from_training_rows_only():
    train = _frame(300, 1, lines=("RB53", "RE10", None))
    new = _frame(50, 2, lines=("RB53", "RE99", None))            # RE99 never seen in training
    categories = models.learn_categories(train, FEATURES)
    assert categories["line_id"] == ["RB53", "RE10"] and "RE99" not in categories["line_id"]
    X = models.prepare(new, FEATURES, categories)
    assert list(X["line_id"].cat.categories) == ["RB53", "RE10"]
    assert X.loc[new["line_id"] == "RE99", "line_id"].isna().all()    # unseen category -> missing
    assert X.loc[new["line_id"] == "RB53", "line_id"].notna().all()


def test_prepare_returns_exactly_the_feature_columns_in_model_types():
    train = _frame(100, 3)
    train["delayed_copy"] = train["delayed"]                      # an extra column must not get through
    X = models.prepare(train, FEATURES, models.learn_categories(train, FEATURES))
    assert list(X.columns) == FEATURES
    assert X["is_through"].dtype == "int8" and X["dwell_min"].dtype == "float64"
    assert isinstance(X["service"].dtype, pd.CategoricalDtype)


def test_only_declared_text_features_become_categories():
    train = _frame(100, 4)
    categories = models.learn_categories(train, FEATURES)
    assert set(categories) == {"service", "line_id"} <= set(features_config.CATEGORICAL_FEATURES)


# ----------------------------------------------------------------- fitting

def test_fit_is_reproducible_and_predicts_probabilities():
    train, val = _frame(1500, 5), _frame(500, 6)
    a = models.fit(train, val, FEATURES, {"num_leaves": 7})
    b = models.fit(train, val, FEATURES, {"num_leaves": 7})
    assert np.array_equal(a["val_proba"], b["val_proba"])
    assert 1 <= a["n_trees"] <= models.MAX_TREES
    assert ((a["val_proba"] >= 0) & (a["val_proba"] <= 1)).all()
    assert np.allclose(models.predict(a, val, FEATURES), a["val_proba"])


def test_refit_keeps_the_tree_count():
    train, val = _frame(1500, 7), _frame(500, 8)
    first = models.fit(train, val, FEATURES, {"num_leaves": 7})
    final = models.refit(pd.concat([train, val]), FEATURES, {"num_leaves": 7}, first["n_trees"])
    assert final["model"].n_estimators == first["n_trees"] == final["n_trees"]


def test_no_class_weighting_in_base_settings():
    forbidden = {"is_unbalance", "scale_pos_weight", "class_weight"}
    assert not (forbidden & set(models.BASE_PARAMS))


# ----------------------------------------------------------------- tuning protocol

def test_tune_picks_the_best_validation_pr_auc():
    train, val = _frame(1500, 9), _frame(500, 10)
    grid = [{"num_leaves": 3, "min_child_samples": 400}, {"num_leaves": 15}]
    best, table = models.tune(train, val, FEATURES, grid)
    assert len(table) == 2 and best["pr_auc"] == pytest.approx(table["pr_auc"].max())
    assert best["params"] == grid[int(table["pr_auc"].idxmax())]


def test_tune_refuses_an_empty_or_too_large_grid():
    train, val = _frame(200, 11), _frame(100, 12)
    with pytest.raises(ValueError):
        models.tune(train, val, FEATURES, [])
    with pytest.raises(ValueError):
        models.tune(train, val, FEATURES, [{"num_leaves": 3 + i} for i in range(models.MAX_TUNING_SETTINGS + 1)])


@pytest.mark.skipif(not models.TUNING_GRID, reason="TUNING_GRID in src/models.py is not filled in yet")
def test_tuning_grid_follows_the_protocol():
    grid = models.TUNING_GRID
    assert 1 <= len(grid) <= models.MAX_TUNING_SETTINGS
    known = set(lgb.LGBMClassifier().get_params())
    for setting in grid:
        assert isinstance(setting, dict)
        assert set(setting) <= known, f"unknown LightGBM parameter in {setting}"
        assert not ({"is_unbalance", "scale_pos_weight", "class_weight"} & set(setting)), "no class weighting (D13)"
        assert not ({"n_estimators", "random_state"} & set(setting)), "tree count and seed are fixed in BASE_PARAMS"
    assert len({tuple(sorted(s.items())) for s in grid}) == len(grid), "duplicate settings"
