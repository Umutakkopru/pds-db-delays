"""
Shared evaluation code: metrics, threshold choice and the day-block bootstrap.

Used by src/05_train.py for every model, so that all models are scored in
exactly the same way (decision log D13).

Reads:  nothing
Writes: nothing (functions only)
"""
from typing import Callable

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
)

import config

# Threshold-free metrics that get a bootstrap interval.
RANK_METRICS: dict[str, Callable] = {
    "pr_auc": average_precision_score,
    "roc_auc": roc_auc_score,
}


def best_f1_threshold(y_true, y_score) -> float:
    """Return the score threshold with the highest F1 (prediction = score >= threshold)."""
    precision, recall, thresholds = precision_recall_curve(y_true, y_score)
    precision, recall = precision[:-1], recall[:-1]          # last point has no threshold
    denom = precision + recall
    f1 = np.divide(2 * precision * recall, denom, out=np.zeros_like(denom), where=denom > 0)
    return float(thresholds[int(np.argmax(f1))])


def class_metrics(y_true, y_score, threshold: float) -> dict[str, float]:
    """Precision, recall, F1 and accuracy of the rule `score >= threshold`."""
    y_true = np.asarray(y_true).astype(bool)
    pred = np.asarray(y_score) >= threshold
    tp = int(np.sum(pred & y_true))
    fp = int(np.sum(pred & ~y_true))
    fn = int(np.sum(~pred & y_true))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": float(np.mean(pred == y_true)),
    }


def score_metrics(y_true, y_score) -> dict[str, float]:
    """PR-AUC, ROC-AUC and Brier score of predicted probabilities."""
    return {
        "pr_auc": float(average_precision_score(y_true, y_score)),
        "roc_auc": float(roc_auc_score(y_true, y_score)),
        "brier": float(brier_score_loss(y_true, y_score)),
    }


def day_block_bootstrap(
    y_true,
    scores: dict[str, np.ndarray],
    days,
    n_resamples: int = config.BOOTSTRAP_N,
    seed: int = config.SEED,
) -> dict[str, dict[str, np.ndarray]]:
    """
    Resample whole days with replacement and recompute the rank metrics.

    Departures of one day are correlated (one disruption delays many trains), so
    the day, not the single departure, is the resampling unit. Every model is
    scored on the same resamples, which makes differences between two models
    paired.

    Returns {model: {metric: array of n_resamples values}}.
    """
    y_true = np.asarray(y_true)
    scores = {name: np.asarray(s) for name, s in scores.items()}
    _, day_codes = np.unique(np.asarray(days), return_inverse=True)
    order = np.argsort(day_codes, kind="stable")
    bounds = np.searchsorted(day_codes[order], np.arange(day_codes.max() + 2))
    rows_of_day = [order[bounds[i]:bounds[i + 1]] for i in range(len(bounds) - 1)]

    rng = np.random.default_rng(seed)
    out = {name: {m: np.empty(n_resamples) for m in RANK_METRICS} for name in scores}
    for b in range(n_resamples):
        chosen = rng.integers(0, len(rows_of_day), size=len(rows_of_day))
        idx = np.concatenate([rows_of_day[d] for d in chosen])
        y = y_true[idx]
        for name, s in scores.items():
            for m, fn in RANK_METRICS.items():
                out[name][m][b] = fn(y, s[idx])
    return out


def interval(samples: np.ndarray, level: float = 0.95) -> tuple[float, float]:
    """Percentile interval of bootstrap samples."""
    lo = (1 - level) / 2
    return float(np.quantile(samples, lo)), float(np.quantile(samples, 1 - lo))


def paired_difference(boot: dict, model: str, reference: str, metric: str) -> dict[str, float]:
    """Mean and 95% interval of metric(model) - metric(reference) on the same resamples."""
    diff = boot[model][metric] - boot[reference][metric]
    lo, hi = interval(diff)
    return {"mean": float(diff.mean()), "low": lo, "high": hi, "better": bool(lo > 0)}
