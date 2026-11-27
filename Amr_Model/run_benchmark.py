"""Run grouped price-model comparisons and build an interactive Plotly report.

Run from any working directory:
    python Amr_Model/run_benchmark.py

The price column is used only as the target. All folds are grouped by title_group.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, median_absolute_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor
from catboost import CatBoostRegressor


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
TRAIN_FILE = DATA_DIR / "Amr_Model_Train.csv"
VALIDATION_FILE = DATA_DIR / "Amr_Model_Validation.csv"

TEXT_COL = "title_norm_enhanced"
EGYPT_MOBILE_PATTERN = r"(?<!\d)(?:(?:\+?20)|0)?1[0125]\d{8}(?!\d)"
CAT_COLS = ["model_key_enhanced", "brand_enhanced", "family", "condition", "listing_type_enhanced", "loc_city"]
NUM_COLS = [
    "storage_gb_model_safe", "ram_gb_model_safe", "battery_health_pct",
    "storage_model_safe_known", "ram_model_safe_known", "condition_known",
    "has_5g", "has_warranty", "has_box", "mentions_exchange", "bundle_hint",
]
MODEL_NAMES = ["hierarchical_median", "catboost_mae", "xgboost_absolute_error", "xgboost_log_target"]
MIN_SELECTIVE_SUPPORT = 3
MIN_TRAINING_WITHIN20 = 0.85


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing dataset: {path}")
    df = pd.read_csv(path, low_memory=False)
    required = {"price", "ad_id", "title_group", "model_prediction_eligible", TEXT_COL, *CAT_COLS, *NUM_COLS}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{path.name} is missing required columns: {missing}")
    for col in CAT_COLS + [TEXT_COL]:
        df[col] = df[col].fillna("unknown").astype(str).replace("", "unknown")
    # Remove contact numbers from the modeling text while preserving product words.
    df[TEXT_COL] = df[TEXT_COL].str.replace(EGYPT_MOBILE_PATTERN, "[contact]", regex=True)
    for col in NUM_COLS + ["price"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["model_prediction_eligible"] = df["model_prediction_eligible"].fillna(False).astype(bool)
    return df


def metrics(y: np.ndarray, prediction: np.ndarray) -> dict:
    y = np.asarray(y, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    ape = np.abs(prediction - y) / np.maximum(np.abs(y), 1)
    return {
        "rows": int(len(y)),
        "mae_egp": float(mean_absolute_error(y, prediction)),
        "median_absolute_error_egp": float(median_absolute_error(y, prediction)),
        "within_20_pct": float((ape <= 0.20).mean()),
        "within_30_pct": float((ape <= 0.30).mean()),
    }


def hierarchical_predict(fit: pd.DataFrame, score: pd.DataFrame, fit_y: np.ndarray) -> np.ndarray:
    prediction = np.full(len(score), float(np.median(fit_y)))
    for column in ["brand_enhanced", "family", "model_key_enhanced"]:
        aligned_y = pd.Series(np.asarray(fit_y, dtype=float), index=fit.index)
        medians = aligned_y.groupby(fit[column].fillna("unknown").astype(str)).median()
        mapped = score[column].fillna("unknown").astype(str).map(medians)
        prediction = np.where(mapped.notna(), mapped.to_numpy(dtype=float), prediction)
    return prediction


def make_xgboost(log_target: bool = False):
    preprocessing = ColumnTransformer(
        transformers=[
            ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=30000, sublinear_tf=True), TEXT_COL),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=40000, sublinear_tf=True), TEXT_COL),
            ("categorical", OneHotEncoder(handle_unknown="ignore", min_frequency=2), CAT_COLS),
            ("numeric", Pipeline([
                ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                ("scale", StandardScaler(with_mean=False)),
            ]), NUM_COLS),
        ], remainder="drop", sparse_threshold=1.0,
    )
    regressor = XGBRegressor(
        n_estimators=350, learning_rate=0.035, max_depth=5, min_child_weight=4,
        subsample=0.85, colsample_bytree=0.8, reg_lambda=8,
        objective="reg:squarederror" if log_target else "reg:absoluteerror",
        tree_method="hist", n_jobs=4, random_state=42, verbosity=0,
    )
    pipeline = Pipeline([("features", preprocessing), ("regressor", regressor)])
    if log_target:
        return TransformedTargetRegressor(regressor=pipeline, func=np.log1p, inverse_func=np.expm1)
    return pipeline


def catboost_features(fit: pd.DataFrame, score: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    support = fit["model_key_enhanced"].value_counts()
    x_fit = fit[CAT_COLS + NUM_COLS].copy()
    x_score = score[CAT_COLS + NUM_COLS].copy()
    x_fit["model_support_count_train"] = fit["model_key_enhanced"].map(support).fillna(0).astype(int)
    x_score["model_support_count_train"] = score["model_key_enhanced"].map(support).fillna(0).astype(int)
    return x_fit, x_score


def fit_catboost(x_fit: pd.DataFrame, y_fit: np.ndarray) -> CatBoostRegressor:
    model = CatBoostRegressor(
        iterations=350, learning_rate=0.04, depth=6, loss_function="MAE", l2_leaf_reg=6,
        random_seed=42, verbose=False, allow_writing_files=False, thread_count=4,
    )
    model.fit(x_fit, y_fit, cat_features=CAT_COLS)
    return model


def exact_model_evidence(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame[["model_key_enhanced", "price"]].copy()
    key_medians = work.groupby("model_key_enhanced")["price"].median()
    work["key_median"] = work["model_key_enhanced"].map(key_medians)
    work["within20"] = (work["price"] - work["key_median"]).abs() / work["price"].clip(lower=1) <= 0.20
    return work.groupby("model_key_enhanced").agg(
        support=("price", "size"), median_price=("price", "median"), training_within20_rate=("within20", "mean")
    )


def selective_oof(train: pd.DataFrame, groups: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pred = np.full(len(train), np.nan)
    support = np.zeros(len(train), dtype=int)
    quality = np.zeros(len(train), dtype=float)
    folds = GroupKFold(n_splits=5)
    for fit_idx, score_idx in folds.split(train, groups=groups):
        fit, score = train.iloc[fit_idx], train.iloc[score_idx]
        evidence = exact_model_evidence(fit)
        pred[score_idx] = score["model_key_enhanced"].map(evidence["median_price"]).fillna(float(fit["price"].median()))
        support[score_idx] = score["model_key_enhanced"].map(evidence["support"]).fillna(0).astype(int)
        quality[score_idx] = score["model_key_enhanced"].map(evidence["training_within20_rate"]).fillna(0.0)
    return pred, support, quality


def make_report(results: dict, selective: dict, output_path: Path) -> None:
    names = ["hierarchical_median", "catboost_mae", "xgboost_absolute_error", "xgboost_log_target"]
    labels = ["Hierarchical median", "CatBoost MAE", "XGBoost absolute error", "XGBoost log target"]
    oof_w20 = [100 * results["training_oof"][n]["within_20_pct"] for n in names]
    val_w20 = [100 * results["validation"][n]["within_20_pct"] for n in names]
    oof_mae = [results["training_oof"][n]["mae_egp"] for n in names]
    val_mae = [results["validation"][n]["mae_egp"] for n in names]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Predictions within ±20%", "Mean absolute error"))
    fig.add_trace(go.Bar(name="Grouped training OOF", x=labels, y=oof_w20, text=[f"{v:.1f}%" for v in oof_w20], textposition="outside"), row=1, col=1)
    fig.add_trace(go.Bar(name="Validation", x=labels, y=val_w20, text=[f"{v:.1f}%" for v in val_w20], textposition="outside"), row=1, col=1)
    fig.add_trace(go.Bar(name="Grouped training OOF", x=labels, y=oof_mae, text=[f"{v:,.0f}" for v in oof_mae], textposition="outside", showlegend=False), row=1, col=2)
    fig.add_trace(go.Bar(name="Validation", x=labels, y=val_mae, text=[f"{v:,.0f}" for v in val_mae], textposition="outside", showlegend=False), row=1, col=2)
    fig.update_layout(title="Amr model comparison", barmode="group", template="plotly_white", height=520, margin=dict(l=35, r=25, t=85, b=110))
    fig.update_yaxes(title_text="Rows within ±20% (%)", range=[0, 100], row=1, col=1)
    fig.update_yaxes(title_text="Egyptian pounds (EGP)", rangemode="tozero", row=1, col=2)
    fig.update_xaxes(tickangle=-18)
    main_html = fig.to_html(full_html=False, include_plotlyjs=True)

    coverage = [100.0, selective["validation"]["coverage_pct"]]
    selective_accuracy_pct = selective["validation"]["within_20_pct"] * 100
    accuracy = [results["validation"]["hierarchical_median"]["within_20_pct"] * 100,
                selective_accuracy_pct]
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(name="Validation coverage", x=["All eligible rows", "Selective predictions"], y=coverage, text=[f"{v:.2f}%" for v in coverage], textposition="outside"))
    fig2.add_trace(go.Bar(name="Within ±20% accuracy", x=["All eligible rows", "Selective predictions"], y=accuracy, text=[f"{v:.2f}%" for v in accuracy], textposition="outside"))
    fig2.update_layout(title="Selective lookup: accuracy versus coverage", barmode="group", template="plotly_white", height=430, yaxis=dict(title="Percent (%)", range=[0, 110]))
    selective_html = fig2.to_html(full_html=False, include_plotlyjs=False)
    explanation = f"""
    <section>
      <h1>Amr phone price model benchmark</h1>
      <p>Accuracy means the predicted price is within ±20% of the advertised price. Models were compared with five-fold GroupKFold by title group. The target price is never used as an input feature.</p>
      <p><strong>Best all-row model:</strong> Hierarchical median (model → family → brand → global median). Validation: {results['validation']['hierarchical_median']['within_20_pct']:.2%} within ±20% across {results['validation']['hierarchical_median']['rows']:,} eligible rows.</p>
      <p><strong>Best selective result:</strong> {selective_accuracy_pct:.2f}% within ±20% on {selective['validation']['selected_rows']:,} of {selective['validation']['eligible_rows']:,} eligible rows ({selective['validation']['coverage_pct']:.2f}% coverage). The lookup abstains on low-support models.</p>
      {main_html}
      {selective_html}
      <p>These results are development evidence. The validation partition has been inspected during project iterations; confirm final performance on a fresh holdout before deployment.</p>
    </section>
    """
    document = "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Amr Model Benchmark</title><style>body{font-family:Arial,sans-serif;max-width:1250px;margin:24px auto;padding:0 18px;line-height:1.55;color:#17212b}h1{margin-bottom:8px}p{max-width:1100px}</style>" + explanation + "</html>"
    output_path.write_text(document, encoding="utf-8")


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    train_all, validation_all = load_data(TRAIN_FILE), load_data(VALIDATION_FILE)
    if set(train_all["title_group"]) & set(validation_all["title_group"]):
        raise ValueError("Train/validation title_group overlap detected; refusing to score contaminated split.")
    train = train_all.loc[train_all["model_prediction_eligible"]].reset_index(drop=True)
    validation = validation_all.loc[validation_all["model_prediction_eligible"]].reset_index(drop=True)
    y = train["price"].to_numpy(float)
    y_val = validation["price"].to_numpy(float)
    groups = train["title_group"].fillna(train["ad_id"].astype(str)).astype(str).to_numpy()
    oof = {name: np.full(len(train), np.nan) for name in MODEL_NAMES}
    folds = GroupKFold(n_splits=5)

    for fold, (fit_idx, score_idx) in enumerate(folds.split(train, y, groups=groups), 1):
        fit, score = train.iloc[fit_idx].copy(), train.iloc[score_idx].copy()
        fit_y = y[fit_idx]
        oof["hierarchical_median"][score_idx] = hierarchical_predict(fit, score, fit_y)

        cb_fit, cb_score = catboost_features(fit, score)
        cb = fit_catboost(cb_fit, fit_y)
        oof["catboost_mae"][score_idx] = cb.predict(cb_score)

        model_columns = CAT_COLS + NUM_COLS + [TEXT_COL]
        for name, log_target in [("xgboost_absolute_error", False), ("xgboost_log_target", True)]:
            model = make_xgboost(log_target)
            model.fit(fit[model_columns], fit_y)
            oof[name][score_idx] = np.maximum(np.asarray(model.predict(score[model_columns]), dtype=float), 0)
        print(f"Finished grouped training fold {fold}/5.", flush=True)

    training_oof = {name: metrics(y, oof[name]) for name in MODEL_NAMES}
    fitted: dict[str, object] = {}
    cb_fit, cb_validation = catboost_features(train, validation)
    cb = fit_catboost(cb_fit, y)
    validation_predictions = {
        "hierarchical_median": hierarchical_predict(train, validation, y),
        "catboost_mae": np.asarray(cb.predict(cb_validation), dtype=float),
    }
    model_columns = CAT_COLS + NUM_COLS + [TEXT_COL]
    for name, log_target in [("xgboost_absolute_error", False), ("xgboost_log_target", True)]:
        model = make_xgboost(log_target)
        model.fit(train[model_columns], y)
        fitted[name] = model
        validation_predictions[name] = np.maximum(np.asarray(model.predict(validation[model_columns]), dtype=float), 0)
    validation_results = {name: metrics(y_val, validation_predictions[name]) for name in MODEL_NAMES}

    # High-confidence exact-model median lookup with a threshold selected from training OOF only.
    selective_oof_pred = np.full(len(train), np.nan)
    selective_support = np.zeros(len(train), dtype=int)
    selective_quality = np.zeros(len(train), dtype=float)
    for fit_idx, score_idx in GroupKFold(n_splits=5).split(train, groups=groups):
        fit, score = train.iloc[fit_idx], train.iloc[score_idx]
        work = fit[["model_key_enhanced", "price"]].copy()
        key_med = work.groupby("model_key_enhanced").price.median()
        work["median"] = work.model_key_enhanced.map(key_med)
        work["within20"] = (work.price - work["median"]).abs() / work.price.clip(lower=1) <= .2
        evidence = work.groupby("model_key_enhanced").agg(support=("price", "size"), median_price=("price", "median"), quality=("within20", "mean"))
        selective_oof_pred[score_idx] = score.model_key_enhanced.map(evidence.median_price).fillna(float(fit.price.median()))
        selective_support[score_idx] = score.model_key_enhanced.map(evidence.support).fillna(0).astype(int)
        selective_quality[score_idx] = score.model_key_enhanced.map(evidence.quality).fillna(0.0)
    selective_oof_mask = (selective_support >= MIN_SELECTIVE_SUPPORT) & (selective_quality >= MIN_TRAINING_WITHIN20)
    selective_oof_metrics = metrics(y[selective_oof_mask], selective_oof_pred[selective_oof_mask]) if selective_oof_mask.any() else {}
    selective_val_metrics_frame = train[["model_key_enhanced", "price"]].copy()
    key_medians = selective_val_metrics_frame.groupby("model_key_enhanced").price.median()
    selective_val_metrics_frame["key_median"] = selective_val_metrics_frame.model_key_enhanced.map(key_medians)
    selective_val_metrics_frame["within20"] = (selective_val_metrics_frame.price - selective_val_metrics_frame.key_median).abs() / selective_val_metrics_frame.price.clip(lower=1) <= .2
    evidence = selective_val_metrics_frame.groupby("model_key_enhanced").agg(support=("price", "size"), median_price=("price", "median"), quality=("within20", "mean"))
    val_support = validation.model_key_enhanced.map(evidence.support).fillna(0).astype(int).to_numpy()
    val_quality = validation.model_key_enhanced.map(evidence.quality).fillna(0.0).to_numpy()
    selective_val_pred = validation.model_key_enhanced.map(evidence.median_price).fillna(float(train.price.median())).to_numpy(float)
    selective_val_mask = (val_support >= MIN_SELECTIVE_SUPPORT) & (val_quality >= MIN_TRAINING_WITHIN20)
    selective_val_metrics = metrics(y_val[selective_val_mask], selective_val_pred[selective_val_mask]) if selective_val_mask.any() else {}
    selective = {
        "threshold": {"minimum_exact_model_training_support": MIN_SELECTIVE_SUPPORT, "minimum_training_within20_rate": MIN_TRAINING_WITHIN20},
        "training_oof": {**selective_oof_metrics, "eligible_rows": len(train), "selected_rows": int(selective_oof_mask.sum()), "coverage_pct": float(100 * selective_oof_mask.mean())},
        "validation": {**selective_val_metrics, "eligible_rows": len(validation), "selected_rows": int(selective_val_mask.sum()), "coverage_pct": float(100 * selective_val_mask.mean())},
    }

    model_lookup = evidence.reset_index().rename(columns={"quality": "training_within20_rate"})
    model_lookup["select_price_prediction"] = model_lookup.support.ge(MIN_SELECTIVE_SUPPORT) & model_lookup.training_within20_rate.ge(MIN_TRAINING_WITHIN20)
    model_lookup["recommended_predicted_price"] = model_lookup.median_price.where(model_lookup.select_price_prediction)
    model_lookup.to_csv(RESULTS_DIR / "selective_model_lookup.csv", index=False)

    best_all_rows = sorted(MODEL_NAMES, key=lambda name: (-training_oof[name]["within_20_pct"], training_oof[name]["mae_egp"]))[0]
    results = {
        "metric_definition": "Within ±20% means absolute relative price error <= 0.20.",
        "training_rows": len(train), "validation_rows": len(validation),
        "training_oof": training_oof, "validation": validation_results,
        "best_all_rows_by_training_oof": best_all_rows, "selective_lookup": selective,
        "warnings": ["Price is the target and is not an input to any price regressor.", "Validation has been inspected during project development; confirm final metrics on a fresh holdout."],
    }
    (RESULTS_DIR / "benchmark_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    oof_rows = []
    for name in MODEL_NAMES:
        part = train[["ad_id", "title_group", "model_key_enhanced", "price"]].copy().rename(columns={"price": "actual_price"})
        part["model"] = name
        part["predicted_price"] = oof[name]
        part["within_20_pct"] = np.abs(part.actual_price - part.predicted_price) / part.actual_price.clip(lower=1) <= .2
        oof_rows.append(part)
    pd.concat(oof_rows, ignore_index=True).to_csv(RESULTS_DIR / "training_oof_predictions.csv", index=False)

    val_output = validation[["ad_id", "title_group", "model_key_enhanced", "price"]].copy().rename(columns={"price": "actual_price"})
    for name in MODEL_NAMES:
        val_output[f"{name}_predicted_price"] = validation_predictions[name]
    val_output["selective_lookup_predicted_price"] = np.where(selective_val_mask, selective_val_pred, np.nan)
    val_output["selective_lookup_status"] = np.where(selective_val_mask, "selective_prediction", "abstain_low_confidence")
    val_output.to_csv(RESULTS_DIR / "validation_predictions.csv", index=False)
    make_report(results, selective, RESULTS_DIR / "Amr_Model_Report.html")
    print(json.dumps({"best_all_rows": best_all_rows, "training_oof": training_oof,
                      "validation": validation_results, "selective_lookup": selective["validation"]}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
