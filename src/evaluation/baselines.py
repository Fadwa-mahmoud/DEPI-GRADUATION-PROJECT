import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.metrics import mean_absolute_error, median_absolute_error

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, median_absolute_error


# TODO: maybe clean this up later? works for now though.

def grouped_median_baseline(data,group_col="brand",prediction_col="pred",n_splits=5):
    predictions = data.copy()

    # Setting up arrays to hold our OOF predictions
    group_preds = np.full(len(data), np.nan)

    gkf = GroupKFold(n_splits=n_splits)

    # Let's loop through the splits
    for train_idx, val_idx in gkf.split(
        data, groups=data["title_group"]
    ):
        train_df = data.iloc[train_idx]
        val_df = data.iloc[val_idx]

        # just a sanity check to make sure group kfold is actually working as intended
        overlap = set(train_df["title_group"]) & set(val_df["title_group"])
        assert not overlap, f"Group leakage detected: {len(overlap)} overlapping groups"

        # calc baseline stats on train fold only!! very important to avoid leakage
        global_med = train_df["price"].median()

        # Global Median baseline
        if group_col is None:
            group_preds[val_idx] = global_med

        else:
            # grouping to find median price per group
            group_meds = train_df.groupby(group_col)["price"].median()

            # map the group medians, and if a group wasn't in train, fallback to global median
            mapped_groups = val_df[group_col].map(group_meds)
            filled_groups = mapped_groups.fillna(global_med)

            group_preds[val_idx] = filled_groups.to_numpy()

    # save back into df
    predictions[prediction_col] = group_preds

    # calculate final MAE
    mae = mean_absolute_error(data["price"],predictions[prediction_col])
    median_ae = median_absolute_error(data["price"],predictions[prediction_col])

    scores = {
        "mae": mae,
        "median_ae": median_ae,
    }

    return predictions, scores

###############################################################################################################


def grouped_tfidf_ridge_baseline(data, alpha=10):

    data = data.reset_index(drop=True).copy()

    X = data["title"].fillna("").astype(str)
    y = data["price"]
    groups = data["title_group"]

    predictions = np.full(len(data), np.nan)
    cv = GroupKFold(n_splits=5)

    for fold, (train_idx, val_idx) in enumerate(
        cv.split(X, y, groups), start=1
    ):
        model = Pipeline([("tfidf", FeatureUnion([
                ("word", TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    min_df=2
                )),
                ("char", TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    min_df=2
                ))
            ])),
            ("ridge", Ridge(alpha=alpha))
        ])

        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        predictions[val_idx] = model.predict(X.iloc[val_idx])
        print(
            f"Fold {fold}: MAE = "
            f"{mean_absolute_error(y.iloc[val_idx], predictions[val_idx]):.2f}"
        )
    scores = {
        "tfidf_ridge_mae": mean_absolute_error(y, predictions),
        "tfidf_ridge_median_ae": median_absolute_error(y, predictions)
    }

    result = data.copy()
    result["pred_E4"] = predictions

    return result, scores



