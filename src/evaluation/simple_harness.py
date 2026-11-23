from pathlib import Path

import pandas as pd

def make_price_band(price, lower_cut=10000, upper_cut=25500):
    if pd.isna(price):
        return "unknown"
    if price < lower_cut:
        return "cheap"
    if price < upper_cut:
        return "mid"
    return "expensive"

def metrics(df, pred_col, price_band_cutoffs=(10000, 25500)):
    required = {"price", "brand", pred_col}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    scored = df.loc[df["price"].notna() & df[pred_col].notna()].copy()
    if scored.empty:
        raise ValueError("No rows with both an actual price and a prediction")

    scored["error"] = (scored["price"] - scored[pred_col]).abs()
    lower_cut, upper_cut = price_band_cutoffs
    if lower_cut >= upper_cut:
        raise ValueError("price_band_cutoffs must be in ascending order")
    scored["price_band"] = scored["price"].apply(
        make_price_band, args=(lower_cut, upper_cut)
    )

    mae = scored["error"].mean()
    medae = scored["error"].median()
    print("Overall -> MAE:", round(mae, 2), "| MedAE:", round(medae, 2))

    print("\nBy brand:")
    by_brand = scored.assign(_brand=scored["brand"].fillna("unknown")).groupby("_brand")["error"].agg(["mean", "median", "count"])
    print(by_brand)

    print("\nBy price band:")
    print(scored.groupby("price_band")["error"].agg(["mean", "median", "count"]))

    return mae, medae

def add_to_log(log, exp_id, description, mae, medae, notes=""):
    new_row = {
        "id": exp_id,
        "description": description,
        "MAE": round(mae, 2),
        "MedAE": round(medae, 2),
        "notes": notes,
    }
    log.append(new_row)

def save_log(log, path="data/processed/experiment_log.csv"):
    """Persist the current experiment log as a CSV file."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(log, columns=["id", "description", "MAE", "MedAE", "notes"]).to_csv(
        output_path, index=False
    )
    return output_path
