"""Grouped-CV feature ablation for phone-price CatBoost models.

This script compares predefined feature groups. It selects the best group by
grouped training OOF only; validation is reported as a secondary check.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
import plotly.graph_objects as go
from sklearn.model_selection import GroupKFold

from run_benchmark import (
    CAT_COLS,
    NUM_COLS,
    RESULTS_DIR,
    TRAIN_FILE,
    VALIDATION_FILE,
    load_data,
    metrics,
)


ROOT = Path(__file__).resolve().parent
OUTPUT_CSV = RESULTS_DIR / "feature_selection_results.csv"
OUTPUT_JSON = RESULTS_DIR / "feature_selection_results.json"


def candidate_sets() -> dict[str, tuple[list[str], list[str]]]:
    """Return deliberate feature groups; IDs and split keys are never features."""
    all_cat = list(CAT_COLS)
    all_num = list(NUM_COLS)
    core_cat = ["model_key_enhanced", "brand_enhanced", "family", "condition"]
    core_num = [
        "storage_gb_model_safe", "ram_gb_model_safe",
        "storage_model_safe_known", "ram_model_safe_known", "condition_known",
    ]
    low_support_flags = ["has_5g", "has_warranty", "has_box", "mentions_exchange", "bundle_hint"]
    return {
        "all_current": (all_cat, all_num),
        "drop_constant_listing_type": ([c for c in all_cat if c != "listing_type_enhanced"], all_num),
        "core_identity_specs": (core_cat, core_num),
        "identity_only": (["model_key_enhanced", "brand_enhanced", "family"], []),
        "family_brand_specs_no_exact_model": (["brand_enhanced", "family", "condition"], core_num),
        "drop_rare_flags": (
            [c for c in all_cat if c != "listing_type_enhanced"],
            [c for c in all_num if c not in low_support_flags],
        ),
    }


def make_features(fit: pd.DataFrame, score: pd.DataFrame, cats: list[str], nums: list[str]):
    support = fit["model_key_enhanced"].value_counts()
    fit_x = fit[cats + nums].copy()
    score_x = score[cats + nums].copy()
    if "model_key_enhanced" in cats:
        fit_x["model_support_count_train"] = fit["model_key_enhanced"].map(support).fillna(0).astype(int)
        score_x["model_support_count_train"] = score["model_key_enhanced"].map(support).fillna(0).astype(int)
    return fit_x, score_x


def fit_model(x: pd.DataFrame, y: np.ndarray, cats: list[str]) -> CatBoostRegressor:
    model = CatBoostRegressor(
        iterations=350,
        learning_rate=0.04,
        depth=6,
        loss_function="MAE",
        l2_leaf_reg=6,
        random_seed=42,
        verbose=False,
        allow_writing_files=False,
        thread_count=4,
    )
    model.fit(x, y, cat_features=cats)
    return model


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    train_all = load_data(TRAIN_FILE)
    validation_all = load_data(VALIDATION_FILE)
    if set(train_all["title_group"]) & set(validation_all["title_group"]):
        raise ValueError("Train/validation title_group overlap detected.")
    train = train_all.loc[train_all.model_prediction_eligible].reset_index(drop=True)
    validation = validation_all.loc[validation_all.model_prediction_eligible].reset_index(drop=True)
    y = train.price.to_numpy(float)
    y_val = validation.price.to_numpy(float)
    groups = train.title_group.fillna(train.ad_id.astype(str)).astype(str).to_numpy()
    folds = list(GroupKFold(n_splits=5).split(train, y, groups=groups))
    outputs: list[dict] = []
    oof_by_set: dict[str, np.ndarray] = {}
    validation_by_set: dict[str, np.ndarray] = {}

    for set_name, (cats, nums) in candidate_sets().items():
        oof = np.full(len(train), np.nan)
        for fold, (fit_idx, score_idx) in enumerate(folds, 1):
            fit, score = train.iloc[fit_idx], train.iloc[score_idx]
            x_fit, x_score = make_features(fit, score, cats, nums)
            model = fit_model(x_fit, y[fit_idx], cats)
            oof[score_idx] = np.maximum(np.asarray(model.predict(x_score), dtype=float), 0)
            print(f"{set_name}: finished fold {fold}/5", flush=True)
        oof_by_set[set_name] = oof

        x_train, x_val = make_features(train, validation, cats, nums)
        final_model = fit_model(x_train, y, cats)
        val_pred = np.maximum(np.asarray(final_model.predict(x_val), dtype=float), 0)
        validation_by_set[set_name] = val_pred
        outputs.append({
            "feature_set": set_name,
            "categorical_features": ",".join(cats),
            "numeric_features": ",".join(nums),
            "oof": metrics(y, oof),
            "validation": metrics(y_val, val_pred),
        })

    outputs.sort(key=lambda item: (-item["oof"]["within_20_pct"], item["oof"]["mae_egp"]))
    best_name = outputs[0]["feature_set"]
    results = {
        "metric_definition": "within_20_pct means absolute relative price error <= 0.20",
        "selection_basis": "Best grouped training OOF within_20_pct, then lower OOF MAE as tie-breaker.",
        "train_rows": len(train),
        "validation_rows": len(validation),
        "folds": 5,
        "best_feature_set_by_oof": best_name,
        "feature_sets": outputs,
        "warnings": [
            "Validation has been inspected during prior development; use a fresh holdout for an unbiased final estimate.",
            "This experiment selects feature groups for CatBoost only; it does not guarantee a target accuracy.",
        ],
    }
    OUTPUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    flat = []
    for item in outputs:
        row = {"feature_set": item["feature_set"], "categorical_features": item["categorical_features"], "numeric_features": item["numeric_features"]}
        for split in ("oof", "validation"):
            row.update({f"{split}_{key}": value for key, value in item[split].items()})
        flat.append(row)
    pd.DataFrame(flat).to_csv(OUTPUT_CSV, index=False)
    chart = go.Figure()
    ordered = list(reversed(outputs))
    labels = [item["feature_set"].replace("_", " ") for item in ordered]
    chart.add_trace(go.Bar(name="Grouped training OOF", x=[100 * item["oof"]["within_20_pct"] for item in ordered], y=labels, orientation="h", text=[f"{100 * item['oof']['within_20_pct']:.1f}%" for item in ordered], textposition="outside"))
    chart.add_trace(go.Bar(name="Validation", x=[100 * item["validation"]["within_20_pct"] for item in ordered], y=labels, orientation="h", text=[f"{100 * item['validation']['within_20_pct']:.1f}%" for item in ordered], textposition="outside"))
    chart.update_layout(title="CatBoost feature ablation: predictions within ±20%", barmode="group", template="plotly_white", height=620, xaxis={"title": "Rows within ±20% (%)", "range": [0, 75]}, margin={"l": 210, "r": 90, "t": 80, "b": 55})
    chart.write_html(RESULTS_DIR / "Amr_Feature_Selection_Report.html", include_plotlyjs=True, full_html=True)
    print(json.dumps({"best_feature_set_by_oof": best_name, "feature_sets": outputs}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
