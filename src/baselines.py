"""
Baseline models B0, B1 and B2 (decision log D5, D14).

B0  majority class: every departure gets the training delay rate as probability
    (so it never predicts "delayed"); shows why accuracy misleads.
B1  rule: delay rate of service x planned hour in the training data, with a
    fallback to the service rate and then the overall rate for unseen cells.
B2  logistic regression on one-hot timetable columns (features_config.BASELINE_FEATURES).

Reads:  nothing (functions only; src/05_train.py passes the data)
Writes: nothing
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

import config
import features_config

TARGET = "delayed"


def add_timetable_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add planned hour and weekday of the Würzburg planned departure (known in advance)."""
    out = df.copy()
    out["planned_hour"] = out["departure_planned_time"].dt.hour
    out["weekday"] = out["departure_planned_time"].dt.dayofweek
    return out


class MajorityBaseline:
    """B0: constant probability = delay rate of the training data."""

    def fit(self, train: pd.DataFrame) -> "MajorityBaseline":
        self.rate_ = float(train[TARGET].mean())
        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        return np.full(len(df), self.rate_)


class RateBaseline:
    """B1: historical delay rate of service x planned hour (training data only)."""

    min_rows = 30  # cells with fewer training rows fall back to the service rate

    def fit(self, train: pd.DataFrame) -> "RateBaseline":
        cell = train.groupby(["service", "planned_hour"])[TARGET].agg(["mean", "size"])
        self.cell_ = cell.loc[cell["size"] >= self.min_rows, "mean"].rename("cell_rate")
        self.service_ = train.groupby("service")[TARGET].mean().rename("service_rate")
        self.overall_ = float(train[TARGET].mean())
        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        out = df[["service", "planned_hour"]].join(self.cell_, on=["service", "planned_hour"])
        out = out.join(self.service_, on="service")
        return out["cell_rate"].fillna(out["service_rate"]).fillna(self.overall_).to_numpy()


def make_logistic_baseline() -> Pipeline:
    """B2: one-hot encoding (unknown categories ignored) + logistic regression, no class weights."""
    columns = features_config.BASELINE_FEATURES
    encode = ColumnTransformer(
        [("onehot", OneHotEncoder(handle_unknown="ignore"), columns)],
        remainder="drop",
    )
    model = LogisticRegression(max_iter=1000, random_state=config.SEED)
    return Pipeline([("encode", encode), ("model", model)])


def logistic_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Columns of B2 as strings; a missing line (long-distance trains) becomes its own category."""
    return df[features_config.BASELINE_FEATURES].astype("string").fillna("none").astype(str)
