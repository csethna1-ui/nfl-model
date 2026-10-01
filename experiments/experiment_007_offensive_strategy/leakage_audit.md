# Experiment 007 — Leakage Audit

- n_validation: 569
- feature_weeks_strictly_before_prediction_week: True
- min_games_rule: 2
- share_zero_proe_diff: 0.05799648506151142
- share_zero_ed_diff: 0.05799648506151142
- share_zero_pace_diff: 0.05799648506151142
- outcome_columns_used_in_features: []
- market_variables_used: []
- vault_accessed: False
- experiment_006_data_used: False

Feature timing: for a prediction game in week W of season S, each team's strategy value is the pooled mean over qualifying plays from that team's games with week < W in season S (weekly batching). No plays from week W or later. Offseason hard reset (no cross-season carryover). Residual target uses frozen V1 predictions; the strategy ridge is fit out-of-fold (two-fold season cross-fit), so no in-sample V1 information leaks into the candidate.
