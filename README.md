# Egyptian Used-Phone Price Intelligence

A DEPI graduation project organized in the order of the 10-day plan: S0 data preparation and baseline, followed by S1 model-key extraction and later modeling and project wrap-up.

## Repository layout

```text
.
├── data/
│   ├── raw/                 # local source data; not committed
│   ├── splits/              # development validation and dev-test sets
│   └── processed/           # generated S0 outputs
├── docs/                    # project planning, literature review, requirements
├── notebooks/
│   ├── 01_S0_split_and_baseline.ipynb
│   ├── 02_end_of_stage1_inspect_data.ipynb
│   └── archive/              # earlier exploratory notebook, retained for history
├── src/evaluation/          # reusable evaluation utilities
├── requirements.txt
└── README.md
```

## Notebook order

1. **S0 baseline:** `notebooks/01_S0_split_and_baseline.ipynb` is the baseline notebook originally uploaded as `task2.ipynb`. It covers the S0 data split and baseline workflow.
2. **S1 model extraction:** `notebooks/02_end_of_stage1_inspect_data.ipynb` is the later stage notebook. It contains brand/model extraction work through Lenovo and also has an LG section after Lenovo. Keep this notebook after S0 in the project sequence.
3. `notebooks/archive/00_S0_initial_inspection.ipynb` preserves the earlier `inspect_data.ipynb` exploratory work for reference; it is not the primary entry point for the staged workflow.

## S0 workflow

1. Install the Python dependencies with `pip install -r requirements.txt`.
2. Put the authorized source CSV at `data/raw/dubizzle_phones_clean.csv`, or use the upload prompt when running in Google Colab.
3. Open and run `notebooks/01_S0_split_and_baseline.ipynb` from the repository root (it also detects the root when started from `notebooks/`).
4. The notebook writes the frozen holdout and training output under `data/processed/`, development validation/test splits under `data/splits/`, and baseline experiment results under `data/processed/experiment_log.csv`.

`data/splits/dev_test.csv` is a development-only split. The final frozen holdout is `data/processed/frozen_test_set.csv` and must remain untouched until the final evaluation.

## Plan order

- **S0 — Safe evaluation and baselines:** normalization, grouped split, frozen test set, baseline ladder and metrics.
- **S1 — Model-key extraction:** gold labels, brand rules, integration, and accuracy review. The current stage notebook includes content through Lenovo and an additional LG section.
- **S2 onward:** modeling, feature/data-quality stages, and closing deliverables as listed in the project plan.

Update the planning workbook as the team completes and reviews each task.
