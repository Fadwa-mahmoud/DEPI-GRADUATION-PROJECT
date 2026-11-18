# Egyptian Used-Phone Price Intelligence

A DEPI graduation project for estimating used-phone prices from Egyptian listings. The notebooks are organized by the 10-day plan. Some S0 and S1 tasks run in parallel, so the file order is a navigation guide rather than a claim that every earlier task blocks every later one.

## Repository layout

```text
.
├── data/
│   ├── raw/                 # authorized source CSV; local only
│   ├── labels/              # gold set and review files
│   ├── splits/              # validation, development-test, and frozen-test partitions
│   └── processed/           # generated training data, metrics, and stage outputs
├── docs/                    # planning, literature review, requirements
├── notebooks/
│   ├── 00_Viola_initial_inspection.ipynb
│   ├── 01_Amr_S0_split_and_baseline.ipynb
│   ├── 02_Fadwa_end_of_stage1_inspect_data.ipynb
│   ├── 03_Aya_stage2_error_analysis.ipynb
│   ├── 04_error_analysis_and_remeasure.ipynb
│   ├── 05_hand_review_unknown_cases.ipynb
│   ├── 2.1_Family_column.ipynb
│   ├── 2.1_Features_Pipeline.ipynb
│   ├── 2.2_Baseline_notebook.ipynb
│   ├── 2.3_catboost_with_model_key.ipynb
│   └── archive/             # combined reference notebooks and older copies
├── src/evaluation/          # evaluation metrics and experiment logging
├── src/preprocessing/       # normalization, split helpers, and model-key rules
├── requirements.txt
└── README.md
```

## Notebook roadmap

| Order | Notebook | Plan area | Purpose |
|---|---|---|---|
| Optional | `00_Viola_initial_inspection.ipynb` | Exploration | Inspect raw listing titles; does not create project splits. |
| 1 | `01_Amr_S0_split_and_baseline.ipynb` | S0 | Create grouped splits and the frozen test; calculate the initial price baselines. |
| 2 | `02_Fadwa_end_of_stage1_inspect_data.ipynb` | S1 | Apply the current model-key rules to the training partition and produce Stage 1 outputs. |
| 3 | `03_Aya_stage2_error_analysis.ipynb` | S1 | Review Gold Set errors and model-key rules. Despite “stage2” in the filename, its content belongs to S1. |
| 4 | `04_error_analysis_and_remeasure.ipynb` | S1 | Fix selected Gold Set misses and measure the updated rules. |
| 5 | `05_hand_review_unknown_cases.ipynb` | S1 | Prepare and review unknown or low-confidence validation cases. |
| 6a | `2.1_Family_column.ipynb` | S2 | Build the phone-family feature from model keys. |
| 6b | `2.1_Features_Pipeline.ipynb` | S2 | Assemble and encode the modeling features; run after the family step. |
| 7 | `2.2_Baseline_notebook.ipynb` | S2 | Compare price baselines and TF-IDF/Ridge. |
| 8 | `2.3_catboost_with_model_key.ipynb` | S2 | Train and evaluate CatBoost price models and price ranges. |

There are two files numbered `01`: `01_Amr_S0_split_and_baseline.ipynb` is the canonical S0 notebook referenced by this guide; `01_S0_split_and_baseline.ipynb` is an alternate copy, not another workflow step. There are also two `2.1` notebooks; run the family-column notebook before the feature-pipeline notebook. The combined notebooks under `notebooks/archive/` are references, not additional steps.

## Start here

1. Put the authorized source file at `data/raw/dubizzle_phones_clean.csv`. Raw data is local and should not be committed.
2. Install dependencies with `pip install -r requirements.txt`.
3. Optionally run the Viola inspection notebook.
4. Run the canonical Amr S0 notebook. It creates disjoint train, validation, development-test, and frozen-test groups and records the split manifest and baseline metrics.
5. Run the Fadwa S1 notebook. It reads the S0 training partition and writes model-key predictions under `data/processed/stage1/`.
6. Use `data/labels/gold_set_Aya.csv` for the existing labeled 200-title Gold Set. The template is for preparing a new labeling set. Review and adjust rules in the Aya and remeasurement notebooks, then use the hand-review notebook for validation cases.
7. For S2, run the family-column notebook, then the feature-pipeline notebook, then the baseline and CatBoost notebooks.

Follow the dependencies in the spreadsheet plan when tasks run in parallel. Use the Gold Set as the designated S1 rule-tuning set. If a planned task reviews validation or development-test rows, report those results as development evidence. Keep the frozen test untouched until the final evaluation.

## S0 outputs

- `data/processed/train_set.csv`: training partition used for model development.
- `data/splits/validation.csv` and `data/splits/dev_test.csv`: development partitions.
- `data/processed/frozen_test_set.csv`: locked final test.
- `data/processed/experiment_log.csv`: baseline MAE and MedAE.
- `data/processed/split_manifest.json`: source hash, split settings, and partition counts.

The frozen test is created once. If a later run proposes different `ad_id` values, the S0 helper stops rather than replacing it. Review the source and normalization change, archive the old holdout, and approve a new holdout explicitly before rerunning.

## S1 outputs

- `data/processed/stage1/stage1_model_keys.csv`: input rows plus unified `model_key`, `match_rule`, and `confidence`.
- `data/processed/stage1/coverage_by_brand.csv`.
- Gold Set reports: `gold_set_metrics.csv`, `gold_set_metrics_by_brand.csv`, `gold_set_errors.csv`, and `rule_confidence.csv`.
- Review candidates are written under `data/labels/`.

Generated `data/processed/` files and raw data are local artifacts; commit them only when the team deliberately approves doing so.

