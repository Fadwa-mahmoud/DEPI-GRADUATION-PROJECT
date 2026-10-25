# Data folders

- `raw/`: place the authorized `dubizzle_phones_clean.csv` source file here. It is intentionally not included in the repository.
- `splits/`: committed development validation and development-test CSVs. They are distinct from the frozen 20% final test set.
- `processed/`: generated S0 artifacts such as `frozen_test_set.csv`, `train_set.csv`, and `experiment_log.csv`. These are created by the notebook and are not automatically committed.
