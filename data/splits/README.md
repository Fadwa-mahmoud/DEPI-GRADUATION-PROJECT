# Development splits

`validation.csv` and `dev_test.csv` are disjoint group-based partitions drawn from the development data. `data/processed/train_set.csv` is the remaining training partition. The locked final test is `data/processed/frozen_test_set.csv` and is separate from all three development files.

All four partitions are checked for shared `title_group` values. The split helper searches seeded group splits for row counts close to the requested proportions while keeping each title group intact.
