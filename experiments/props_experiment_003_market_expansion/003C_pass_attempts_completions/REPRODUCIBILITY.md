# Reproducibility manifest — Props Experiment 003C

Experiment: pass attempts + hierarchical completions (frozen preregistration
`PREREGISTRATION.md`, approved by Cale 2026-10-01 12:25 CDT).
Executed: 2026-10-01 (single run; fit-once discipline).

## Code

- `scripts/01_build_003c_table.py` — data prep only (no fitting).
- `scripts/02_run_003c.py` — `--phase dev`, then `--phase test` exactly once.
- Frozen inputs (read-only, untouched):
  - `experiments/props_experiment_002/data/extended_features_2018_2024.parquet`
  - local `data/pbp_2018.parquet` … `data/pbp_2024.parquet`
  - keyless nflverse NGS `passing` via nfl_data_py `import_ngs_data`
    (pulled 2026-10-01; cached as `data/ngs_passing_2016_2024.parquet`).

## Procedure

- Splits by season: train 2018–2020, dev 2021–2022, locked test 2023–2024
  (from the frozen 002 table's `period` column).
- Rung projection = mean(Ridge, HistGradientBoostingRegressor).
- Hyperparameter grids (fixed): Ridge alpha ∈ {0.1, 1, 10, 100};
  GBM 8-combo {learning_rate ∈ {0.05, 0.1}, max_depth ∈ {3, 5},
  max_iter ∈ {200, 500}}.
- Dev-selected (frozen for test): alpha=100.0, GBM
  {learning_rate: 0.05, max_depth: 3, max_iter: 200} for every rung and C1.
- Test refit on train only with frozen hyperparams (002 precedent).
- Bootstrap: 2,000 paired resamples, seed 1337.
- GBM random_state=11 (002 precedent).
- EWMA: half-life 3, max 16 rows, most-recent-first, strictly prior rows.
- Clip: C0 completion% [0,1]; C1 completion probability [0.05, 0.98].
- C1 fit target: actual_comp / actual_att, sample_weight = actual_att.
- Completions feeder: M1 test attempts projection (predetermined).

## Environment

- `~/workspace/nfl-model/venv` (Python 3.12), scikit-learn
  HistGradientBoostingRegressor + Ridge, pandas, nfl_data_py (keyless).

## Outputs (all under this directory)

- `data/table_003c.parquet` (3,266 rows × 114 cols)
- `data/experiment_003C_dev.json`, `data/experiment_003C_test.json`
- `data/experiment_003C_test_predictions.parquet` (1,010 rows)
- `feature_audit.csv`, `RESULTS.md`, this file.

## Rerun

```bash
cd ~/workspace/nfl-model
venv/bin/python experiments/props_experiment_003_market_expansion/003C_pass_attempts_completions/scripts/01_build_003c_table.py
venv/bin/python experiments/props_experiment_003_market_expansion/003C_pass_attempts_completions/scripts/02_run_003c.py --phase dev
venv/bin/python experiments/props_experiment_003_market_expansion/003C_pass_attempts_completions/scripts/02_run_003c.py --phase test
```

Note: rerunning `--phase test` reproduces the single evaluation
deterministically (fixed seeds, frozen inputs); the protocol's
"single evaluation" refers to the evaluation event, not to
reproducibility of the computation.
