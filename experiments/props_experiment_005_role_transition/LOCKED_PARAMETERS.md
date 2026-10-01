# LOCKED PARAMETERS — Props Experiment 005: Player Role Transition Model

**Status: FROZEN 2026-10-01, from dev (2021–2022) only. These values must not change before or during the single locked-test evaluation (2023–2024).**
**Seed:** 1337 throughout. **M0:** frozen Props Model D (Experiment 001), reproduced bit-identical (see `DEV_DIAGNOSTICS.md`).

## Selection procedure (frozen)

Per rung and target: structural parameters grid-searched on dev
(M1: w ∈ {0, .25, .5, .75, 1}; M2: w × λ ∈ {0, .25, .5, 1, 2};
M3: w × v, same w grid) × Ridge α ∈ {0.1, 1, 10, 100} × GBM 8-combo
(lr ∈ {0.05, 0.1}, depth ∈ {3, 5}, iter ∈ {200, 500}, random_state=11).
Selected by in-sample dev MAE. Fitted objects in `models/`.

Structural definitions:
- `opp_blend(w[, λ]) = w·opp_cur + (1−w)·exp(−λ·stint_games)·opp_prior`
  (λ=0 reduces M2 to M1 exactly)
- `eff_blend(v) = v·eff_cur + (1−v)·eff_prior`
- `opp_cur`/`eff_cur`: trailing EWMA (half-life 3, max 16, most-recent-first)
  of actual_att / actual_yards-per-att over strictly-prior games **within**
  the current team stint; `opp_prior`/`eff_prior`: same over games
  **before** the current stint. NaN→0 per modeling-table convention.

## pass_yards (dev n=986; M0 dev MAE 57.7740)

| Rung | w | λ/v | Class | Hyperparameters | Feature order | Dev MAE (in-sample) | Dev MAE (5-fold CV) |
|---|---|---|---|---|---|---|---|
| M1 | 0.50 | — | gbm | lr=0.1, depth=5, iter=500 | m0, opp_blend, transfer_ind, stint_games | 35.7870 | 63.5571 |
| M2 | 0.75 | λ=0.50 | gbm | lr=0.1, depth=5, iter=500 | m0, opp_blend, transfer_ind, stint_games | 35.4914 | 63.9786 |
| M3 | 1.00 | v=0.50 | gbm | lr=0.1, depth=5, iter=500 | m0, opp_blend, eff_blend, opp_x_eff, transfer_ind, stint_games | 26.3341 | 63.8440 |

## rush_yards (dev n=1500; M0 dev MAE 25.1478)

| Rung | w | λ/v | Class | Hyperparameters | Feature order | Dev MAE (in-sample) | Dev MAE (5-fold CV) |
|---|---|---|---|---|---|---|---|
| M1 | 0.50 | — | gbm | lr=0.1, depth=5, iter=500 | m0, opp_blend, transfer_ind, stint_games | 17.4843 | 27.9044 |
| M2 | 0.25 | λ=2.00 | gbm | lr=0.1, depth=5, iter=500 | m0, opp_blend, transfer_ind, stint_games | 17.1588 | 28.0341 |
| M3 | 0.50 | v=1.00 | gbm | lr=0.1, depth=5, iter=500 | m0, opp_blend, eff_blend, opp_x_eff, transfer_ind, stint_games | 13.5131 | 27.8657 |

## receiving_yards (dev n=3689; M0 dev MAE 23.9767)

| Rung | w | λ/v | Class | Hyperparameters | Feature order | Dev MAE (in-sample) | Dev MAE (5-fold CV) |
|---|---|---|---|---|---|---|---|
| M1 | 1.00 | — | gbm | lr=0.1, depth=5, iter=500 | m0, opp_blend, transfer_ind, stint_games | 18.9050 | 25.8429 |
| M2 | 0.50 | λ=0.50 | gbm | lr=0.1, depth=5, iter=500 | m0, opp_blend, transfer_ind, stint_games | 18.8889 | 25.8302 |
| M3 | 0.50 | v=0.50 | gbm | lr=0.1, depth=5, iter=500 | m0, opp_blend, eff_blend, opp_x_eff, transfer_ind, stint_games | 16.4868 | 25.6868 |

## Readout for the locked test

- All 9 selections are the maximum-capacity GBM; 5-fold CV MAE is 7–12%
  worse than M0 on every rung×target. The locked configs are therefore
  expected to underperform M0 out-of-sample; the locked test decides.
- The w/λ/v values above are noise fits under in-sample selection and carry
  no mechanistic interpretation. Do not interpret them.
- Machine-readable copy: `LOCKED_PARAMETERS.json` (same values).
- Fitted models: `models/M{1,2,3}_{pass_yards,rush_yards,receiving_yards}_fitted.pkl`
  (each: struct, class, hyper, fitted model, feature order).
- **Do NOT run the locked test until authorized. Do not modify these values.**
