"""Leakage-safe train, development and frozen-test splitting helpers."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit


def _groups(frame: pd.DataFrame, column: str) -> set[str]:
    return set(frame[column].dropna().astype(str))


def _closest_group_split(frame: pd.DataFrame, group_column: str, test_size: float, random_state: int, candidates: int = 256):
    splitter = GroupShuffleSplit(n_splits=candidates, test_size=test_size, random_state=random_state)
    target_rows = len(frame) * test_size
    best = None
    best_delta = float("inf")
    for train_idx, test_idx in splitter.split(frame, groups=frame[group_column]):
        delta = abs(len(test_idx) - target_rows)
        if delta < best_delta:
            best = (train_idx, test_idx)
            best_delta = delta
    if best is None:
        raise ValueError("Could not build a grouped split")
    return best


def verify_group_disjoint(splits: dict[str, pd.DataFrame], *, group_column: str = "title_group") -> None:
    """Raise if any group occurs in more than one named split."""
    names = list(splits)
    for i, left_name in enumerate(names):
        left = _groups(splits[left_name], group_column)
        for right_name in names[i + 1:]:
            overlap = left & _groups(splits[right_name], group_column)
            if overlap:
                raise ValueError(f"Group leakage between {left_name} and {right_name}: {len(overlap)} overlapping groups")


def make_grouped_splits(frame: pd.DataFrame, *, group_column: str = "title_group", final_test_size: float = 0.20, development_holdout_size: float = 0.20, random_state: int = 42) -> dict[str, pd.DataFrame]:
    """Create disjoint group-based splits, approximating requested row shares.

    It samples many valid group splits and picks the one whose row count is
    closest to the requested share. Whole groups always stay together.
    """
    if group_column not in frame:
        raise ValueError(f"Missing group column: {group_column}")
    if frame[group_column].isna().any():
        raise ValueError(f"{group_column} contains missing values")
    if frame[group_column].nunique() < 5:
        raise ValueError("At least five distinct groups are required")

    dev_idx, final_idx = _closest_group_split(frame, group_column, final_test_size, random_state)
    development, frozen_test = frame.iloc[dev_idx].copy(), frame.iloc[final_idx].copy()
    train_idx, reserved_idx = _closest_group_split(development, group_column, development_holdout_size, random_state + 1)
    train, reserved = development.iloc[train_idx].copy(), development.iloc[reserved_idx].copy()
    validation_idx, dev_test_idx = _closest_group_split(reserved, group_column, 0.5, random_state + 2)
    validation, dev_test = reserved.iloc[validation_idx].copy(), reserved.iloc[dev_test_idx].copy()

    result = {"train": train, "validation": validation, "dev_test": dev_test, "frozen_test": frozen_test}
    verify_group_disjoint(result, group_column=group_column)
    return result


def save_frozen_test_set(candidate: pd.DataFrame, path: str | Path, *, id_column: str = "ad_id") -> Path:
    """Create the frozen test once; never replace a different split silently."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if id_column not in candidate:
        raise ValueError(f"Cannot freeze test: missing {id_column!r}")
    if candidate[id_column].isna().any() or candidate[id_column].duplicated().any():
        raise ValueError(f"{id_column} must be present and unique in the frozen test")
    if output_path.exists():
        existing = pd.read_csv(output_path)
        if id_column not in existing:
            raise ValueError(f"Cannot verify existing frozen test: missing {id_column!r}")
        same_ids = set(existing[id_column].astype(str)) == set(candidate[id_column].astype(str))
        same_columns = set(existing.columns) == set(candidate.columns)
        same_content = False
        if same_ids and same_columns:
            columns = list(candidate.columns)
            old_values = existing[columns].sort_values(id_column).reset_index(drop=True)
            new_values = candidate[columns].sort_values(id_column).reset_index(drop=True)
            old_values = old_values.astype("string").fillna("")
            new_values = new_values.astype("string").fillna("")
            same_content = old_values.equals(new_values)
        if not (same_ids and same_columns and same_content):
            raise FileExistsError(
                f"Refusing to overwrite frozen test at {output_path}; its rows, columns, or values differ. "
                "Archive the old holdout and approve a new one explicitly before rerunning S0."
            )
        return output_path
    candidate.to_csv(output_path, index=False)
    return output_path
