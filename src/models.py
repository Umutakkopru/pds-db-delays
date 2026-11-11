"""
LightGBM models (M-A, M-A', M-B): data preparation, fitting with early stopping
and the small hyperparameter search (decision log D5, D13, D21).

Rules that this module keeps:
  - category lists come from the training rows only (leakage rule 4);
  - no class weights, so that predicted probabilities stay calibrated (D13);
  - at most MAX_TUNING_SETTINGS settings per model, fixed before the first run (D21);
  - everything is seeded with config.SEED.

Reads:  nothing (functions only; src/05_train.py passes the data)
Writes: nothing
"""
import lightgbm as lgb
import numpy as np
import pandas as pd

import config
import evaluate
import features_config

TARGET = "delayed"
MAX_TUNING_SETTINGS = 20
MAX_TREES = 2000            # upper limit; early stopping decides the real number
EARLY_STOPPING_ROUNDS = 50

# Settings shared by every model and every tuning run.
BASE_PARAMS = {
    "objective": "binary",
    "learning_rate": 0.05,
    "n_estimators": MAX_TREES,
    "random_state": config.SEED,
    "deterministic": True,
    "force_row_wise": True,     # needed for identical results between runs
    "n_jobs": 4,
    "verbose": -1,
}

# Hyperparameter settings tried for each model. Every entry is a dict of
# LightGBM parameters that overrides BASE_PARAMS; the search fits one model per
# entry on the training rows and compares them on validation (PR-AUC).
# Fixed on 11 Nov 2026 before any tuning result was seen (D21): a ladder from
# simple to flexible trees (num_leaves) crossed with two leaf sizes
# (min_child_samples), LightGBM's default setting, and three regularised
# variants (fewer features per tree, stronger L2 penalty) against memorising
# sparse categories such as the 123 destinations.
TUNING_GRID: list[dict] = [
    {"num_leaves": 7, "min_child_samples": 50},
    {"num_leaves": 7, "min_child_samples": 200},
    {"num_leaves": 15, "min_child_samples": 50},
    {"num_leaves": 15, "min_child_samples": 200},
    {"num_leaves": 31, "min_child_samples": 20},      # LightGBM default
    {"num_leaves": 31, "min_child_samples": 50},
    {"num_leaves": 31, "min_child_samples": 200},
    {"num_leaves": 63, "min_child_samples": 50},
    {"num_leaves": 63, "min_child_samples": 200},
    {"num_leaves": 15, "min_child_samples": 100, "colsample_bytree": 0.7, "reg_lambda": 5.0},
    {"num_leaves": 31, "min_child_samples": 100, "colsample_bytree": 0.7, "reg_lambda": 5.0},
    {"num_leaves": 63, "min_child_samples": 300, "colsample_bytree": 0.7, "reg_lambda": 5.0},
]


def learn_categories(train: pd.DataFrame, features: list[str]) -> dict[str, list[str]]:
    """Category lists of the text features, taken from the training rows only."""
    return {
        name: sorted(train[name].dropna().unique())
        for name in features if name in features_config.CATEGORICAL_FEATURES
    }


def prepare(df: pd.DataFrame, features: list[str], categories: dict[str, list[str]]) -> pd.DataFrame:
    """
    Model input: exactly the listed feature columns.

    Text features become pandas categories with the given (training) category
    lists; a value that is not in the list becomes missing, like any unseen
    category at prediction time. True/False columns become 0/1.
    """
    X = df[features].copy()
    for name in features:
        if name in categories:
            X[name] = pd.Categorical(X[name], categories=categories[name])
        elif X[name].dtype == bool:
            X[name] = X[name].astype("int8")
        else:
            X[name] = X[name].astype("float64")
    return X


def fit(train: pd.DataFrame, val: pd.DataFrame, features: list[str], params: dict) -> dict:
    """
    Fit one LightGBM model on training rows; validation rows stop the training early.

    Returns the model, its category lists, the number of trees chosen and the
    validation probabilities.
    """
    categories = learn_categories(train, features)
    X_train, X_val = prepare(train, features, categories), prepare(val, features, categories)
    model = lgb.LGBMClassifier(**{**BASE_PARAMS, **params})
    model.fit(
        X_train, train[TARGET],
        eval_X=X_val, eval_y=val[TARGET], eval_metric="binary_logloss",
        callbacks=[lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False)],
    )
    return {
        "model": model,
        "categories": categories,
        "n_trees": int(model.best_iteration_),
        "val_proba": model.predict_proba(X_val)[:, 1],
    }


def refit(train_and_val: pd.DataFrame, features: list[str], params: dict, n_trees: int) -> dict:
    """Final model on training + validation rows with the tree count found before (D21: unchanged)."""
    categories = learn_categories(train_and_val, features)
    X = prepare(train_and_val, features, categories)
    model = lgb.LGBMClassifier(**{**BASE_PARAMS, **params, "n_estimators": n_trees})
    model.fit(X, train_and_val[TARGET])
    return {"model": model, "categories": categories, "n_trees": n_trees}


def predict(fitted: dict, df: pd.DataFrame, features: list[str]) -> np.ndarray:
    """Probabilities of a fitted model for new rows (uses the model's own category lists)."""
    return fitted["model"].predict_proba(prepare(df, features, fitted["categories"]))[:, 1]


def tune(train: pd.DataFrame, val: pd.DataFrame, features: list[str], grid: list[dict] | None = None) -> tuple[dict, pd.DataFrame]:
    """
    Fit one model per setting of the grid and pick the best validation PR-AUC.

    Returns the best fitted model (as from fit(), plus its "params") and a table
    with one row per setting.
    """
    grid = TUNING_GRID if grid is None else grid
    if not grid:
        raise ValueError("TUNING_GRID is empty: add the settings to try in src/models.py.")
    if len(grid) > MAX_TUNING_SETTINGS:
        raise ValueError(f"{len(grid)} settings; the protocol allows at most {MAX_TUNING_SETTINGS} (D21).")
    rows, best = [], None
    for i, params in enumerate(grid):
        fitted = fit(train, val, features, params)
        scores = evaluate.score_metrics(val[TARGET], fitted["val_proba"])
        rows.append({"setting": i, **params, "n_trees": fitted["n_trees"], **scores})
        if best is None or scores["pr_auc"] > best["pr_auc"]:
            best = {**fitted, "params": params, "pr_auc": scores["pr_auc"]}
    return best, pd.DataFrame(rows)
