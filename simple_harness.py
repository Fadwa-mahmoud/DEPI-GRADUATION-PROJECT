import pandas as pd


def make_price_band(price):
    if price < 10000:
        return "cheap"
    elif price < 25000:
        return "mid"
    else:
        return "expensive"


def metrics(df, pred_col):
    df = df.copy()

    df["error"] = (df["price"] - df[pred_col]).abs()

    df["price_band"] = df["price"].apply(make_price_band)

    mae = df["error"].mean()
    medae = df["error"].median()
    print("Overall -> MAE:", round(mae, 2), "| MedAE:", round(medae, 2))

    print("\nBy brand:")
    print(df.groupby("brand")["error"].agg(["mean", "median", "count"]))

    print("\nBy price band:")
    print(df.groupby("price_band")["error"].agg(["mean", "median", "count"]))

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
