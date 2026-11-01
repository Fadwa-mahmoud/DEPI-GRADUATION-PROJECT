# Data folders

- `raw/`: the authorized `dubizzle_phones_clean.csv` source. Keep it local; it is not committed.
- `splits/`: S0 validation and development-test CSVs, created from the development portion only.
- `processed/`: S0 `train_set.csv`, locked `frozen_test_set.csv`, experiment log, and S1 outputs under `stage1/`.
- `labels/`: a 200-title stratified template. Fill `gold_model_key` by hand; never treat the prefilled model prediction as the gold answer.

The frozen test helper refuses to replace an existing holdout with a different `ad_id` set. To re-freeze after a source or normalization change, archive the old holdout and make that decision explicitly.
