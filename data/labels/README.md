# S1 gold labels

`gold_set_template.csv` is a deterministic 200-title sample stratified by brand from the S0 training partition. The notebook pre-fills predictions for reference; those columns are not labels.

Fill `gold_model_key` by hand using the same lowercase, brand-prefixed canonical format as `predicted_model_key`. Use `unknown` when the title is a non-phone listing or its phone model cannot be identified; add context such as "accessory" in `review_notes`. Do not edit `predicted_model_key`, `predicted_match_rule`, or `confidence`; the notebook refreshes those from the current rules.

After labeling, rerun the S1 notebook. It reports coverage and exact-match precision, exports mismatches, and estimates per-rule confidence only when at least five labeled examples support that rule. Confidence remains blank for rules without enough evidence.
