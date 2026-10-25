# Egyptian Used-Phone Price Intelligence

A DEPI graduation project that follows the stages in the 10-day plan: safe evaluation and baselines (S0), model-key extraction (S1), price modeling (S2), and the planned data-quality and closing work.

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
│   └── archive/              # original exploratory notebook, retained for history
├── src/evaluation/          # reusable evaluation utilities
├── requirements.txt
└── README.md
```

## S0 workflow

1. Install the Python dependencies with `pip install -r requirements.txt`.
2. Put the authorized source CSV at `data/raw/dubizzle_phones_clean.csv`, or use the upload prompt when running in Google Colab.
3. Open and run `notebooks/01_S0_split_and_baseline.ipynb` from the repository root (it also detects the root when started from `notebooks/`).
4. The notebook writes the frozen holdout and training output under `data/processed/`, development validation/test splits under `data/splits/`, and baseline experiment results under `data/processed/experiment_log.csv`.

`data/splits/dev_test.csv` is a development-only split. The final frozen holdout is `data/processed/frozen_test_set.csv` and must remain untouched until the final evaluation.

## Plan order

- **S0 — Safe evaluation and baselines:** normalization, grouped split, frozen test set, baseline ladder and metrics.
- **S1 — Model-key extraction:** gold labels, brand rules, integration, and accuracy review.
- **S2 onward:** modeling, feature/data-quality stages, and closing deliverables as listed in the project plan.

The original `inspect_data.ipynb` is preserved under `notebooks/archive/` as an early exploratory record. Use the numbered S0 notebook as the current S0 entry point. The status in the planning workbook should be updated by the team as tasks are completed.
