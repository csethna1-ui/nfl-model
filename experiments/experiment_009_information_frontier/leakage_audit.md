# Experiment 009 — Feature-level leakage audit (Part 10)

Applies only to features actually exercised in 009: frozen V1 prediction, the market
spread snapshot, and the walk-forward refit ratings used in the training-window audit.
All other families are covered by their own experiments' leakage audits (cited, not re-run).

## Features used in this experiment

| Feature | Source column | Look-ahead risk | Verdict |
|---|---|---|---|
| `ens_margin` (frozen V1 margin) | `data/games_with_preds.parquet` | None — saved walk-forward predictions; 2018–2020 rows are null (predictions begin 2021) | PASS |
| `spread_line` (pregame market) | `data/games_with_preds.parquet` | **Medium — timestamp unknown** (Exp 004: single undated snapshot; proxy bakes in line movement + any postgame information if the source page was updated). No evidence of postgame contamination found in the row inventory, but it cannot be timestamp-certified. Consequence: market MAE is a lower-bound-quality benchmark, not a valid live-entry benchmark | PASS WITH CAVEAT |
| `pred_elo` / `pred_epa_m` (component predictions) | parquet | None — saved from the same walk-forward fits | PASS |
| `elo_diff`, `off_epa_diff`, `def_epa_diff`, `off_pass_diff`, `off_rush_diff`, `def_pass_diff`, `def_rush_diff`, `sr_off_diff`, `sr_def_diff` (training-window refits) | parquet | None — features are pre-week ratings produced by `scripts/04_backtest.py`; the audit only refits the linear *coefficients* on past seasons; no future games enter any training window (pool for predicting S is strictly seasons < S) | PASS |
| `pred_gbm_m` (walk-forward GBM in the rebuilt ensemble) | parquet | None — saved walk-forward predictions | PASS |
| Home-bias correction (+1.25pt) | residuals of V1 | Post-hoc descriptive diagnostic only; fit season-by-season cross-fit (2021→2022, 2022→2021); never evaluated on its own fit season | PASS (exploratory, not a candidate) |
| `home_margin` (target) | parquet | None — actual game outcome | PASS |

## Rules enforced

1. No feature computed from any game kicked off after the prediction game's kickoff
   enters any training set or any pregame feature.
2. No 2023+ information enters any selection, weight, window, or threshold choice.
   The only 2023–25 computation is the §5G fixed-weight blend evaluation (diagnostic;
   the market is an *input*, not a candidate — the blend cannot be deployed).
3. No PFT corpus use or disturbance; no Experiment 006 use; no 2026 use except the
   two 2026 Week 1 rows that were excluded from the locked set (see §1).

## Score: 7/7 PASS (1 with timestamp caveat, disclosed in §1 and §8).

## What this audit does NOT cover

- Market timestamp reconstruction: covered by Experiment 004 (finding stands —
  market snapshot is undated and non-reconstructable).
- Betting splits / line movement: hypothesized-inaccessible here; queued separate audit.
- Inactives / transactions / news timing: not used in this experiment; their leakage
  rules belong to their own future protocols.
