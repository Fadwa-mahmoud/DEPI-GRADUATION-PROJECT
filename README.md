# Egyptian Used-Phone Price Intelligence

A DEPI graduation project organized by uploaded notebook: Viola's initial inspection, Amr's S0 split and baseline, then Fadwa's S1 model extraction. The plan runs some S0 and S1 tasks in parallel; this notebook order records the files and does not imply that every S0 task must finish before S1 labeling begins.

## Repository layout

```text
.
├── data/
│   ├── raw/                 # source CSV; local only
│   ├── labels/              # hand-labeled gold set
│   ├── splits/              # validation and development-test partitions
│   └── processed/           # frozen test, training partition, metrics and S1 output
├── docs/                    # planning, literature review, requirements
├── notebooks/
│   ├── 00_Viola_initial_inspection.ipynb
│   ├── 01_Amr_S0_split_and_baseline.ipynb
│   ├── 02_Fadwa_end_of_stage1_inspect_data.ipynb
│   └── archive/             # generated combined reference notebooks
├── src/evaluation/          # evaluation metrics and experiment logging
├── src/preprocessing/       # shared normalization and grouped split helpers
├── requirements.txt
└── README.md
```

## Start here

1. Copy the authorized source file `dubizzle_phones_clean.csv` into `data/raw/`. The copy currently found on this machine is `A:\AI\Deep\Scraping\dubizzle_phones_clean.csv`.
2. Install dependencies with `pip install -r requirements.txt`.
3. Optionally run `notebooks/00_Viola_initial_inspection.ipynb` to explore titles. It does not write project split files.
4. Run `notebooks/01_Amr_S0_split_and_baseline.ipynb`. It normalizes titles through the shared helper, creates disjoint train/validation/dev-test/frozen-test groups, measures the global and brand-median baselines, and writes the experiment log.
5. Run `notebooks/02_Fadwa_end_of_stage1_inspect_data.ipynb`. It reads only the S0 `train_set.csv` and writes predictions under `data/processed/stage1/`; it never rewrites S0 splits or the frozen test.
6. Open `data/labels/gold_set_template.csv` and hand-label its 200 sampled titles in `gold_model_key`. Follow `data/labels/README.md`, then rerun the S1 notebook to calculate gold-set precision, coverage, rule confidence and error/review files.

The frozen test is created once. If a later run proposes different `ad_id` values, the S0 helper stops rather than replacing it. Review the source and normalization change, archive the old holdout, and approve a new holdout explicitly before rerunning.

## S0 outputs

- `data/processed/train_set.csv`: only the training partition used by grouped CV.
- `data/splits/validation.csv` and `data/splits/dev_test.csv`: disjoint development partitions.
- `data/processed/frozen_test_set.csv`: locked final test, never used during feature/rule development.
- `data/processed/experiment_log.csv`: baseline MAE and MedAE.
- `data/processed/split_manifest.json`: source SHA-256, split parameters and partition counts.

## S1 outputs

- `data/processed/stage1/stage1_model_keys.csv`: input rows plus unified `model_key`, `match_rule` and calibrated `confidence` (blank until labels support calibration).
- `data/processed/stage1/coverage_by_brand.csv`.
- After labels are entered: `gold_set_metrics.csv`, `gold_set_metrics_by_brand.csv`, `gold_set_errors.csv`, and `rule_confidence.csv`.
- `unknown_low_confidence_review.csv`: up to 100 unknown or low-confidence cases for review.

The three numbered notebooks above are the canonical contributor files, in project order. A combined reference notebook, if needed, is kept under `notebooks/archive/`.

The final holdout is not opened for S0 baselines or S1 rule development. `data/raw/` and generated `data/processed/` files are local artifacts and should not be committed unless the team deliberately approves them.
