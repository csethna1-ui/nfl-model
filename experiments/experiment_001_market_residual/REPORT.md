# Experiment 001 — Market-Residual Model

**Status: NULL RESULT on validation. Vault (2023–2025) untouched by design.**
**V1 remains the production model. Nothing is labeled V2.**

Generated 2026-09-29. Config: `config.json`. Results: `results.json`.
Dataset: `data/experiments/games_features.parquet` (2,227 games, 2018–2025).
Leakage audit: `leakage_audit.md`.

## The three concepts, kept separate

1. **Prediction accuracy** — how well does the model predict actual margin?
   Measured by margin MAE of `market_spread + predicted_residual` vs actual margin.
2. **Market-residual accuracy** — how well does the model predict `actual_margin − market_proxy`?
   Measured by residual MAE/RMSE. **This is not the same as (1), and neither is proof of (3).**
3. **Tradable-signal evidence** — would this have been actionable at the line
   available at prediction time? **Cannot be established from this experiment**
   (see provenance flag). The separate prospective arbiter is live 2026 CLV
   tracking, which is not combined with these historical results.

## Provenance flag (read first)

Historical `market_spread` values are **nflverse consensus/opening proxies, NOT
verified executable closing lines**. The residual target
(`actual_margin − market_proxy`) therefore bakes in line movement toward close.
A model can score well on concept (2) partly by learning information embedded in
a *later* market proxy — that is not evidence it could have captured the
difference at the earlier line. **Never present residual-MAE improvement as
proof of a tradable edge.**

## Method

- Target: `residual = actual_margin − market_spread`, ridge regression (α=1.0,
  fixed — no hyperparameter search on a small NFL sample) on 12 walk-forward
  features (ELO/EPA differentials, rest, divisional, week). Features standardized
  on training data only.
- Approaches (selection on **2021–2022 validation only**):
  - **A — fixed window:** one ridge fit on 2018–2020, applied to 2021–2022.
  - **B — expanding walk-forward:** weekly refit on all strictly-earlier games.
  - **C — recency-weighted expanding:** same as B with sample weights
    `exp(−λ·weeks_ago)`; λ chosen on validation only.
- Baselines: **market-only** (predicted residual = 0) and **V1**.
- Pre-registered rule: winner = lowest validation residual MAE; vault run only if
  the winner's validation margin MAE beats market-only. Otherwise null, vault untouched.

## Validation results (2021–2022, n=569)

| Approach | Resid MAE | Resid RMSE | Margin MAE (mkt+resid) | Market MAE | V1 MAE | Calib slope |
|---|---|---|---|---|---|---|
| Market-only | **9.727** | 12.562 | **9.727** | 9.727 | 10.042 | — |
| A fixed 2018–20 | 9.761 | 12.597 | 9.761 | 9.727 | 10.042 | 0.65 |
| B expanding | 9.783 | 12.601 | 9.783 | 9.727 | 10.042 | 0.49 |
| C recency λ=0.0025 | 9.798 | 12.610 | 9.798 | 9.727 | 10.042 | 0.44 |

λ grid (resid MAE): 0.0025→9.798, 0.005→9.814, 0.01→9.844, 0.02→9.896, 0.04→10.046
— more recency weighting is monotonically *worse*.

By season (margin MAE, adjusted vs market): 2021: 10.61 vs 10.67 (tiny win);
2022: 8.91 vs 8.78 (loss). Unstable across seasons.

ATS at |edge|≥3 (secondary): residual-model picks 25–28 (47.2%, n=53),
27–25 (51.9%), 30–30 (50.0%) — noise. V1 on the same games: 103–88 (53.9%).

## Interpretation

The market-only baseline — predicting the residual is exactly zero — beats every
ridge variant on both residual MAE and margin MAE. Calibration slopes well below
1.0 show the classic signature: the model finds a whisper of signal
(correlation with actual margin 0.437 vs market's 0.432) but adds more noise than
signal, systematically overshooting residual predictions. Expanding windows and
recency weighting do not help; heavier recency weighting hurts monotonically.

This mirrors the earlier v2 (QB EPA + wind) story: plausible in-sample, decays
out-of-sample. The NFL spread market's residual is, to first order,
unpredictable from pregame team-strength features.

## Decision

**Null result. The 2023–2025 vault was not touched** — per the pre-registered
rule, a validation failure ends the experiment. No methodology was iterated, no
vault result was peeked at, nothing is promoted. V1 stays production.

## What this rules out / leaves open

- Ruled out (for now): linear residual modeling on team-strength differentials
  beats the market. It doesn't — it loses to predicting zero.
- Left open: nonlinear residual structure, interaction with market-movement
  features (requires timestamped lines we don't have), player-availability
  features. Any future attempt restarts at validation (2021–2022) under the same
  vault discipline.
