# LOCKED PARAMETERS — Props Experiment 006: Role-Change Mechanisms

**Status: dev complete 2026-10-01. Parameters frozen from dev (2021–2022) only. No 2023–2024 computation.**
**Do not refit. The locked test evaluates these exact values.**

Machine-readable: `LOCKED_PARAMETERS.json` (same values).

## M1 — contrast + Ridge (RIDGE ONLY)

Frozen feature order (same for all three targets — no feature selection):

`["m0", "contrast_snap", "contrast_carries", "contrast_tshare", "contrast_rush1", "contrast_tgt1", "stint_games", "transfer_ind"]`

where `m0` = frozen Model D prediction and the contrasts are
`snap_share_last3 − snap_share_trailing16`, `carries_last3 − carries_trailing16`,
`target_share_last3 − target_share_trailing16`,
`rush_share_last1 − rush_share_season`, `target_share_last1 − target_share_season`.

| Target | Locked alpha | Fitted artifact |
|---|---|---|
| pass_yards | **100.0** | `models/M1_pass_yards_fitted.pkl` (StandardScaler + Ridge) |
| rush_yards | **0.1** | `models/M1_rush_yards_fitted.pkl` |
| receiving_yards | **0.1** | `models/M1_receiving_yards_fitted.pkl` |

Alpha selected from {0.1, 1, 10, 100} by in-sample dev MAE (frozen procedure). Seed 1337.

## M2 — Kalman filter (frozen 3-scalar spec)

| Target | q_share | q_eff | r | prior_share | prior_eff |
|---|---|---|---|---|---|
| pass_yards | 6.1442e-06 | 7.9604 | 0.30037 | 0.90848 | 6.82812 |
| rush_yards | 2.0358e-03 | 7.4716 | 0.19273 | 0.37093 | 4.15230 |
| receiving_yards | 1.8536e-04 | 20.0855 | 0.02756 | 0.12460 | 7.25713 |

Fitted by maximizing one-step-ahead predictive log-likelihood on eligible dev rows
(L-BFGS-B on log-params, deterministic). Positional priors from train (2018–2020);
wide prior variances V0_share=1.0, V0_eff=100.0 (frozen constants, not tuned).
Artifacts: `models/M2_{market}_params.json`.
