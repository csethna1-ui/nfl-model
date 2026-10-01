# Experiment 009 — Reproducibility manifest

Frozen protocol: `PREREGISTRATION.md` (frozen 2026-09-30 before any locked-test computation).
Protocol amendments during execution (documented, none alter selection rules):
- Baseline table corrected to n=816 REG-only (2 2026 Week 1 rows in the parquet excluded).
- Training-pool disclosure for W1/W2/W3 at S=2022 (includes validation year 2021 — strict walk-forward).
- Part 3D skipped: no surviving feature families (preregistered condition met).
- Home-bias diagnostic added as post-hoc (labeled exploratory, not a preregistered candidate).

Data:
- Input: `data/games_with_preds.parquet` (canonical backtest artifact). Read-only; never written.
- Locked test: 2023–2025 REG only (n=816). 2026 rows excluded. No 2026 observations used.

Code:
- `01_validation_analyses.py` — Parts 3A–C (validation), 5 (windows), 7 (segments), 8 (edge buckets), 6 (ELO–EPA corr).
- Locked-test §5G: one-off inline script (fixed w*=0.15 blend), run once; see `results_locked.json`.
- Seed: 42. Bootstrap: 2000-iteration paired, 95% CI.
- No PFT corpus use, no Experiment 006 use, no production/dashboard/V1 changes.

Outputs:
- `results_validation.json` — all validation numbers.
- `results_locked.json` — the single locked-test evaluation.
- `frontier_table.csv` — Part 1 (38 rows).
- `leakage_audit.md` — Part 10 (7/7 PASS).
- `REPORT.md` — final report (9 required sections).

Statistical standard: MAE primary; materiality ≥0.15 MAE + 95% paired bootstrap CI
excluding zero + holds across validation seasons (for candidates; none passed).
