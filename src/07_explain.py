"""
Step 7 (extension): SHAP explanations of the LightGBM models (M-A, M-A', M-B).

Answers the sanity check "do the most important features make domain sense?"
(CLAUDE.md, safeguards 3) and produces the global importance for the report.

SHAP values are computed by LightGBM itself (`pred_contrib=True`, the exact
TreeSHAP algorithm that shap.TreeExplainer also calls for LightGBM models).
They are in log-odds: a value of +0.7 roughly doubles the odds of a delay.
For every row, the values plus the base value add up to the model's raw score;
the script checks this.

Validation set: the training-only models are fitted again with the setting that
src/05_train.py chose (reports/checks/tuning_*.csv) and explained on the
validation rows. Test set: the saved final models (models/) are explained on the
test rows; allowed only after the final run (reports/final_run.json exists).

Reads:  data/processed/features_a.parquet, features_b.parquet    (step 4)
        reports/checks/tuning_m_a.csv, tuning_m_a_prime.csv, tuning_m_b.csv   (step 5; validation set)
        models/*.txt, models/*.json                                (step 5 --final; test set)
Writes: reports/shap_<set>.md
        reports/checks/shap_importance_<set>.csv
        reports/figures/shap_importance_<set>.png
        reports/figures/shap_dependence_<set>.png

Usage: python src/07_explain.py                # validation
       python src/07_explain.py --set test     # after src/05_train.py --final
"""
import argparse
import importlib
import json
from pathlib import Path

import lightgbm as lgb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
import features_config
import models
import plot_style

train_step = importlib.import_module("05_train")  # module name starts with a digit

M_A, M_A_PRIME, M_B = "M-A", "M-A′", "M-B"
SLUGS = {M_A: "m_a", M_A_PRIME: "m_a_prime", M_B: "m_b"}
SCENARIO = {M_A: "A", M_A_PRIME: "B", M_B: "B"}            # rows the model is trained and explained on
FEATURE_SET = {M_A: "A", M_A_PRIME: "A", M_B: "B"}         # feature list the model uses
GROUPS = {
    "timetable": features_config.TIMETABLE_FEATURES,
    "calendar": features_config.CALENDAR_FEATURES,
    "weather": features_config.WEATHER_FEATURES,
    "history": features_config.HISTORY_FEATURES,
    "previous stops": features_config.PROPAGATION_FEATURES,
}
# Features that could let a model memorise single trains or periods instead of
# learning a pattern. They are allowed; the report shows their rank so that a
# reader can judge them.
WATCH_FEATURES = {
    "destination": "many categories; could memorise single trains",
    "hist_n_route": "a count, not a rate; could stand in for the line or the period",
    "stop_position": "position in the route; could stand in for the line",
}
WATCH_RANK = 3              # a watch feature at this rank or better is flagged
OUTSIDE_RANGE_REPORTED = 0.05   # features with at least this share of rows outside the training range are listed
ADDITIVITY_TOLERANCE = 1e-6
TOP_N = 12


# ----------------------------------------------------------------- models

def best_setting(name: str) -> tuple[dict, int]:
    """Setting and tree count that the validation run chose for a model (best validation PR-AUC)."""
    table = pd.read_csv(config.CHECKS / f"tuning_{SLUGS[name]}.csv")
    row = table.loc[table["pr_auc"].idxmax()]
    keys = [k for k in models.TUNING_GRID[int(row["setting"])]]
    params = {k: (int(row[k]) if float(row[k]).is_integer() else float(row[k])) for k in keys}
    return params, int(row["n_trees"])


def validation_models() -> dict:
    """Fit the three training-only models again; returns {name: {booster, features, categories, rows}}."""
    out = {}
    for name in (M_A, M_A_PRIME, M_B):
        rows = train_step.load_modelling_rows(SCENARIO[name])
        train, val = rows[rows["split"] == "train"], rows[rows["split"] == "val"]
        features = features_config.FEATURES[FEATURE_SET[name]]
        params, n_trees = best_setting(name)
        fitted = models.fit(train, val, features, params)
        if fitted["n_trees"] != n_trees:
            raise RuntimeError(f"{name}: refit has {fitted['n_trees']} trees, the validation run had {n_trees}. "
                               "Run src/05_train.py again before explaining the models.")
        out[name] = {"booster": fitted["model"].booster_, "features": features,
                     "categories": fitted["categories"], "rows": val, "fitted_on": train}
    return out


def final_models(models_dir: Path | None = None, marker: Path | None = None) -> dict:
    """Load the saved final models and the test rows. Refused before the final run."""
    models_dir = train_step.MODELS_DIR if models_dir is None else models_dir
    marker = train_step.FINAL_MARKER if marker is None else marker
    if not marker.exists():
        raise RuntimeError("The test period is explained only after the final run (src/05_train.py --final).")
    out = {}
    for name in (M_A, M_A_PRIME, M_B):
        rows = train_step.load_modelling_rows(SCENARIO[name], ("test",), allow_test=True)
        out[name] = {**load_saved_model(models_dir, name), "rows": rows,
                     "fitted_on": train_step.load_modelling_rows(SCENARIO[name])}   # final models: training + validation
    return out


def load_saved_model(models_dir: Path, name: str) -> dict:
    """One model as saved by src/05_train.py --final: booster, feature list and category lists."""
    info = json.loads((models_dir / f"{SLUGS[name]}.json").read_text(encoding="utf-8"))
    return {"booster": lgb.Booster(model_file=str(models_dir / f"{SLUGS[name]}.txt")),
            "features": info["features"], "categories": info["categories"]}


# ----------------------------------------------------------------- SHAP

def shap_values(booster: lgb.Booster, X: pd.DataFrame) -> tuple[np.ndarray, float]:
    """SHAP values (rows x features, log-odds) and the base value; checks that they add up to the raw score."""
    contrib = booster.predict(X, pred_contrib=True)
    values, base = contrib[:, :-1], contrib[:, -1]
    raw = booster.predict(X, raw_score=True)
    gap = float(np.abs(values.sum(axis=1) + base - raw).max())
    if gap > ADDITIVITY_TOLERANCE:
        raise RuntimeError(f"SHAP values do not add up to the model output (largest gap {gap:.2e}).")
    return values, float(base[0])


def group_of(feature: str) -> str:
    return next(group for group, members in GROUPS.items() if feature in members)


def importance_table(values: np.ndarray, features: list[str]) -> pd.DataFrame:
    """Mean absolute SHAP value per feature, its share of the total, rank and feature group."""
    mean_abs = np.abs(values).mean(axis=0)
    table = pd.DataFrame({"feature": features, "group": [group_of(f) for f in features], "mean_abs_shap": mean_abs})
    table["share"] = table["mean_abs_shap"] / table["mean_abs_shap"].sum()
    table = table.sort_values("mean_abs_shap", ascending=False, ignore_index=True)
    table.insert(0, "rank", np.arange(1, len(table) + 1))
    return table


def watch_notes(importance: pd.DataFrame) -> list[str]:
    """One line per watch feature: rank, share and whether it needs a closer look."""
    notes = []
    for feature, why in WATCH_FEATURES.items():
        row = importance[importance["feature"] == feature]
        if row.empty:
            continue
        rank, share = int(row["rank"].iloc[0]), float(row["share"].iloc[0])
        verdict = "**look closer**" if rank <= WATCH_RANK else "fine"
        notes.append(f"`{feature}` ({why}): rank {rank}, {share:.1%} of the total; {verdict}.")
    return notes


def dependence_table(shap_column: np.ndarray, x: pd.Series, edges: list[float], labels: list[str]) -> pd.DataFrame:
    """Mean SHAP value of one feature per bin of its own value (bins are [edge, next edge))."""
    bins = pd.cut(x, edges, labels=labels, right=False)
    table = pd.DataFrame({"bin": bins, "shap": shap_column}).groupby("bin", observed=True)["shap"].agg(["size", "mean"])
    return table.rename(columns={"size": "rows", "mean": "mean_shap"}).reset_index()


def outside_training_range(fitted_on: pd.DataFrame, rows: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """
    Share of the explained rows whose value lies outside the range the model saw in training.

    A tree model cannot extrapolate: such a row gets the contribution of the
    nearest value it knows. Numeric features only; missing values are ignored.
    """
    out = []
    for name in features:
        if name in features_config.CATEGORICAL_FEATURES or fitted_on[name].dtype == bool:
            continue
        low, high = fitted_on[name].min(), fitted_on[name].max()
        x = rows[name].dropna()
        out.append({"feature": name, "training_min": float(low), "training_max": float(high),
                    "share_outside": float(((x < low) | (x > high)).mean()) if len(x) else 0.0})
    table = pd.DataFrame(out)
    return table[table["share_outside"] >= OUTSIDE_RANGE_REPORTED].sort_values("share_outside", ascending=False, ignore_index=True)


# ----------------------------------------------------------------- output

def importance_figure(tables: dict[str, pd.DataFrame], path: Path, period: str) -> None:
    fig, axes = plt.subplots(1, len(tables), figsize=(5.2 * len(tables), 4.6))
    for ax, (name, table) in zip(np.atleast_1d(axes), tables.items()):
        top = table.head(TOP_N).iloc[::-1]
        colours = [plot_style.ORANGE if g == "previous stops" else plot_style.BLUE for g in top["group"]]
        ax.barh(top["feature"], top["mean_abs_shap"], color=colours, height=0.7)
        ax.set_title(f"{name}: mean |SHAP| ({period})")
        ax.set_xlabel("log-odds")
        ax.grid(axis="x")
        ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def dependence_figure(prev: pd.DataFrame, hour: pd.DataFrame, path: Path) -> None:
    fig, (left, right) = plt.subplots(1, 2, figsize=(10.5, 3.8))
    left.bar(prev["bin"].astype(str), prev["mean_shap"], color=plot_style.ORANGE, width=0.7)
    left.axhline(0, color=plot_style.AXIS, linewidth=0.8)
    left.set_title("M-B: effect of the delay at the previous stop")
    left.set_xlabel("delay at the previous stop (min)")
    left.set_ylabel("mean SHAP (log-odds)")
    for service, colour in (("long_distance", plot_style.BLUE), ("regional", plot_style.AQUA)):
        part = hour[hour["service"] == service]
        right.plot(part["planned_hour"], part["mean_shap"], marker="o", color=colour, label=service.replace("_", "-"))
    right.axhline(0, color=plot_style.AXIS, linewidth=0.8)
    right.set_title("M-A: effect of the planned hour, by service")
    right.set_xlabel("planned hour")
    right.set_ylabel("mean SHAP (log-odds)")
    right.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def md(df: pd.DataFrame, digits: int = 3) -> str:
    out = df.copy()
    for column in out.columns:
        if column == "share":
            out[column] = out[column].map(lambda v: f"{v:.1%}")
        elif column == "share_outside":
            out[column] = out[column].map(lambda v: f"{v:.1%}")
        elif out[column].dtype.kind == "f":
            out[column] = out[column].map(lambda v: f"{v:.{digits}f}")
    header = "| " + " | ".join(out.columns) + " |\n| " + " | ".join("---" for _ in out.columns) + " |\n"
    return header + "\n".join("| " + " | ".join(str(v) for v in row) + " |" for row in out.itertuples(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--set", choices=["validation", "test"], default="validation")
    which = parser.parse_args().set
    plot_style.apply()

    fitted = validation_models() if which == "validation" else final_models()
    period = "validation rows" if which == "validation" else "test rows"

    values, tables, parts = {}, {}, []
    for name, m in fitted.items():
        X = models.prepare(m["rows"], m["features"], m["categories"])
        values[name], base = shap_values(m["booster"], X)
        tables[name] = importance_table(values[name], m["features"])
        tables[name].insert(0, "model", name)
        m["X"], m["base"] = X, base

    all_tables = pd.concat(tables.values(), ignore_index=True)
    all_tables.round(5).to_csv(config.CHECKS / f"shap_importance_{which}.csv", index=False)
    importance_figure({k: tables[k] for k in (M_A, M_B)}, config.FIGURES / f"shap_importance_{which}.png", period)

    # Dependence: previous-stop delay (M-B) and planned hour by service (M-A).
    b, a = fitted[M_B], fitted[M_A]
    j = b["features"].index("prev_delay")
    prev = dependence_table(values[M_B][:, j], b["rows"]["prev_delay"],
                            [-np.inf, 1, 3, 6, 10, 20, np.inf], ["0 or early", "1–2", "3–5", "6–9", "10–19", "20+"])
    j = a["features"].index("planned_hour")
    hour = (pd.DataFrame({"service": a["rows"]["service"].to_numpy(), "planned_hour": a["rows"]["planned_hour"].to_numpy(),
                          "shap": values[M_A][:, j]})
            .groupby(["service", "planned_hour"])["shap"].agg(["size", "mean"]).reset_index()
            .rename(columns={"size": "rows", "mean": "mean_shap"}))
    hour = hour[hour["rows"] >= 100]
    dependence_figure(prev, hour, config.FIGURES / f"shap_dependence_{which}.png")

    # M-A inside each service: which features separate trains of the same service?
    j_service = a["features"].index("service")
    inside = []
    for service in ("regional", "long_distance"):
        mask = (a["rows"]["service"] == service).to_numpy()
        table = importance_table(values[M_A][mask], a["features"])
        table = table[table["feature"] != "service"].head(5)
        inside.append(f"- **{service.replace('_', '-')}** ({mask.sum():,} rows; `service` itself contributes "
                      f"{values[M_A][mask, j_service].mean():+.2f} on average): "
                      + ", ".join(f"`{f}` {v:.3f}" for f, v in zip(table["feature"], table["mean_abs_shap"])))

    parts.append(f"# SHAP explanations on the {which} set\n")
    parts.append(f"Written by `src/07_explain.py`. Values are in log-odds (+0.7 roughly doubles the odds of a delay); "
                 f"\"mean |SHAP|\" is the average size of a feature's contribution over the {period}. "
                 "For every row the contributions plus the base value add up to the model's raw score (checked).\n")
    for name in (M_A, M_A_PRIME, M_B):
        m, table = fitted[name], tables[name]
        groups = table.groupby("group")["share"].sum().sort_values(ascending=False)
        parts.append(f"## {name} ({len(m['rows']):,} rows, base value {m['base']:+.3f})\n")
        parts.append(md(table.drop(columns="model").head(TOP_N)) + "\n")
        parts.append("Share per feature group: " + ", ".join(f"{g} {s:.1%}" for g, s in groups.items()) + ".\n")
        parts.append("Watch features:\n\n" + "\n".join(f"- {n}" for n in watch_notes(table)) + "\n")
        outside = outside_training_range(m["fitted_on"], m["rows"], m["features"])
        parts.append("Values outside the range seen in training (the model cannot extrapolate there): "
                     + ("none above 5% of the rows.\n" if outside.empty else "\n\n" + md(outside, digits=3) + "\n"))
    parts.append("## M-A inside one service (mean |SHAP|, top 5 without `service`)\n\n" + "\n".join(inside) + "\n")
    parts.append("## M-B: effect of the previous-stop delay\n\n" + md(prev) + "\n")
    parts.append(f"Figures: `reports/figures/shap_importance_{which}.png`, `reports/figures/shap_dependence_{which}.png`.\n")
    report = config.REPORTS / f"shap_{which}.md"
    report.write_text("\n".join(parts), encoding="utf-8")
    print("\n".join(parts))
    print(f"Saved: {report}")


if __name__ == "__main__":
    main()
