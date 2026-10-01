# REPRODUCIBILITY MANIFEST — Props Experiment 002

## Environment
- Python: /home/hatch/workspace/nfl-model/venv (python3.12)
- Key packages: pandas, pyarrow, numpy, scikit-learn 1.9.1, scipy 1.18.1,
  nfl_data_py 0.3.3 (NGS pull only)
- Seeds: bootstrap RNG seed 1337; HistGBM random_state=11 (B),
  quantile GBM random_state=7 (C, fixed params); RidgeCV default

## Pipeline (in order)
1. `scripts/audit_features.py` → `data/feature_audit.csv`
   Feature availability/leakage audit. Declaration + verification notes.
2. NGS pull (one-off, 2026-09-30):
   `nfl_data_py.import_ngs_data('receiving', [2018..2024])`
   → `data/ngs_receiving_2018_2024.parquet`
3. `scripts/build_extended_features.py`
   → `data/extended_features_2018_2024.parquet` (34,275 rows × 98 cols)
   Base: `experiments/player_props_projection/data/modeling_table.parquet`
   (frozen 001 table; untouched). Adds 51 Family B–Q features (see protocol
   §5 for exact definitions). Validation printed on train+dev only.
   - Name matching: initial.last|team keys; injury collisions resolved by
     position group (25 residual same-posg collisions dropped, counted).
   - All trailing EWMAs strictly prior; as-of discipline per protocol.
4. `scripts/run_experiment_002.py --phase dev`
   → `data/experiment_002_dev.json` (+ `data/dev_phase.log`)
   Fit on train (2018–2020), select on dev (2021–2022). Test slice never
   loaded (load() filters to train/dev; assertion guards).
   Fits M0–M10, M11 (selected), M12 (gate check). Per rung/market: A-alpha
   from {0.1,1,10,100} on dev; B from 8-combo grid on dev; C fixed.
   M11 families via §7 rule (≥1% dev gain vs M0, no market >1% worse).
   M12 = mean(RidgeCV, HistGBM) on ALL0+all-51-new; test only if dev gate
   passes (≥1% in ≥1 market, no market >1% worse).
   Calibration (§10a–c) on dev for M0 and each rung.
5. `scripts/run_experiment_002.py --phase test`
   → `data/experiment_002_test.json`,
     `data/experiment_002_test_predictions.parquet`
   Requires `PROTOCOL_FROZEN` marker + dev outputs. Refits M0/M11/M12 (and
   M1–M10 for diagnostics) on train with dev-selected hyperparams; SINGLE
   locked-test evaluation (2023–2024). Paired bootstrap (2000, seed 1337)
   CIs; by-season MAE; win-bar check (§9); calibration on test with dev
   cutoffs.

## Protocol clarifications (documented, not changes to win bar/rules)
- Families O (exp_*), P (rec2_*), Q (xq_*) have no standalone ladder rung
  in the frozen §6 table; they enter via M12's all-family set. M11 selection
  covers families B,C,D1,D2,E,F,RQ/RUQ/QBE(via M6),QB(via M7),J,L.
- M12 spec: RidgeCV(alphas=logspace(-1,3,10), cv=5) + HistGBM (B-grid
  dev-selected), mean prediction, on ALL0 + all 51 new features.
- Injury (N) family classified as context (both A stages + B/C).

## Frozen references (never modified by this experiment)
- `experiments/player_props_projection/scripts/run_experiment_001.py`
- `experiments/player_props_projection/data/modeling_table.parquet`
- `scripts/16_prod_player_projection.py` (production)
- `experiments/player_props_projection/` (Experiment 001 artifacts)

## Protocol
- `experiment_002_protocol.md` — frozen 2026-09-30 before any fitting.
- `PROTOCOL_FROZEN` — marker file gating `--phase test`.
