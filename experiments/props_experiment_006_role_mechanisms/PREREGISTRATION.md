# PREREGISTRATION — Props Experiment 006: Role-Change Mechanisms

**Status: FROZEN — APPROVED by Cale 2026-10-01 ("just do what you have to do to test it"). Frozen exactly as drafted. Fit once on dev; evaluate per preregistered target and win bar. No production changes regardless of outcome. Approval to freeze is NOT approval of any candidate or production change.**
**Numbering:** props sub-series 006. (004 = defensive matchup, frozen 2026-10-01 NOT RUN; 005 = role transition, complete NULL 2026-10-01 — both untouched.)

Shared discipline: `props_experiment_003_market_expansion/MARKET_EXPANSION_PROTOCOL.md` (§1 research philosophy, §2 as-of discipline, §8 production gate) applies unless this document states otherwise.

**Lineage:** 005 tested "weight current-team more" via learned global blend/decay weights + max-capacity GBM stacking corrections and NULLed cleanly — the dev procedure selected overfit configs (in-sample dev MAE less than half the 5-fold CV MAE). The 2026-10-01 prop-modeling research survey (`../props_experiment_005_role_transition/PROP_MODELING_RESEARCH.md`) found no repo doing explicit team-change regime detection, but two concrete mechanisms that avoid 005's failure mode. This experiment preregisters those two.

## 1. Target

The three yardage targets: **passing yards** (QB), **rushing yards** (RB), **receiving yards** (WR/TE/RB). Each evaluated independently. Population per target: `eligible_hist=1` AND `played_role=1` (001/002 role thresholds).

## 2. Structural hypothesis

Role change is detectable from **recent-vs-baseline contrasts** in opportunity shares, while efficiency is sticky. Two candidate formalizations:

- **M1 (contrast features + weak learner):** the gap between recent usage and trailing baseline *is* the regime detector — no learned regime parameter exists to overfit. The learner is deliberately weak (Ridge only).
- **M2 (Kalman filter):** opportunity shares evolve with high process noise (roles change fast); efficiency evolves with low process noise (talent is sticky). A team change inflates the share-state variance while the efficiency state carries over — the formal version of "talent carries over, role does not." The Kalman gain derives the recency weighting analytically from 2–3 global noise parameters; there is no high-capacity selection step.

## 3. Information audit (all reconstructable per the 005 audit)

| Signal | Source | As-of OK? |
|---|---|---|
| Contrast features: `snap_share_last3 − snap_share_trailing16`, `carries_last3 − carries_trailing16`, `target_share_last3 − target_share_trailing16`, `rush_share_last1 − rush_share_season`, `target_share_last1 − target_share_season` | `player_games.parquet`, `data/v2/raw/snap_counts_<season>.csv` | Yes — trailing completed games only |
| `stint_games`, team-change indicator | team stints from `player_games.parquet` | Yes |
| Per-player weekly shares and rates (Kalman observations) | `player_games.parquet` (attempts/targets/yards) | Yes |
| Team-level volume (trailing EWMA of team rush attempts / dropbacks) | `player_games.parquet` aggregated | Yes |
| Market line as a feature | **EXCLUDED** | — |
| Vacated-volume features | **EXCLUDED — measured ≈ 0 effect** (crumblip; research §4) | — |
| Depth-chart position (historical) | **NOT AVAILABLE** (005 audit; 2026-prospective only) | — |

**Capacity discipline (binding — the 005 lesson):** no GBM with in-sample dev selection. M1 is Ridge-only (single alpha grid {0.1, 1, 10, 100}, selected on dev). M2 fits exactly 3 scalars by one-step-ahead predictive likelihood on dev. Any candidate that cannot be expressed within these capacity limits does not belong in this experiment.

## 4. Fixed ladder

**Additive-candidate rule (binding, carried from 005):** M1–M2 are additive candidates evaluated against the exact frozen M0 implementation. No candidate may alter, refit, retrain, or otherwise modify the underlying Model D training pipeline or fitted artifacts. The experiment changes the role/opportunity treatment, not the frozen player projection model.

- **M0 (baseline):** frozen Props Model D predictions, used read-only.
- **M1 (contrast + Ridge):** frozen M0 prediction as a feature + the contrast features (§3) + `stint_games` + team-change indicator → Ridge regression (alpha from {0.1, 1, 10, 100} on dev, seed 1337). Nothing else. In particular: no GBM, no interaction grid, no feature selection.
- **M2 (Kalman):** per-player state `[share_t, eff_t]` where share = rush_share (RB) / target_share (receiving) and eff = YPC / (catch_rate × YPR).
  - Predict: `share_t = share_{t-1} + N(0, q_share)`; `eff_t = eff_{t-1} + N(0, q_eff)`.
  - Update: game-t observation with variance `r / n_t` (`n_t` = attempts; low-volume games update less).
  - Team change: at the first game of a new stint, the share state's variance is inflated (reset to the positional prior with wide variance); the efficiency state carries over unchanged.
  - Players with fewer than 3 trailing games use the positional prior with wide variance (frozen spec, not tuned).
  - Projection for week T: `team_volume_T × share_{T|T-1} × eff_{T|T-1}`, where `team_volume_T` is the trailing EWMA (half-life 3, max 16, strictly prior weeks) of team rush attempts / dropbacks.
  - Exactly 3 global parameters `(q_share, q_eff, r)`, fit by maximizing one-step-ahead predictive log-likelihood on dev 2021–2022. No grid beyond the likelihood optimization; seed 1337.

Each rung vs M0 independently against the win bar (§5). No union models. **The ladder does not change after dev results are seen.**

## 5. Metrics, slices, and win bar

Primary metric: walk-forward MAE per target; also RMSE, bias, MAE by season. Paired bootstrap (2000 resamples, seed 1337) CIs for M0-vs-challenger differences.

**Win bar — ALL must hold, per target:**
1. Pooled 2023–2024: **≥5% relative MAE reduction** vs M0 — overall eligible population AND transfer-stint population (co-primary, carried from 005);
2. **≥2% relative reduction in 2023 AND in 2024 individually** (overall);
3. **95% paired bootstrap CI** excludes zero (overall and transfer-stint);
4. **Regression guard:** non-transfer rows must not degrade more than **1%** vs M0.

**Diagnostic slices (reported, not win/loss):** transfer-stint games 1–3 and 4–6 (underpowered rule applies); high-contrast-magnitude rows (top decile of |carries/target-share contrast| — the rows M1 is designed to fire on); non-transfer rows. Slices with <150 player-games per season are underpowered, not wins or nulls.

## 6. What this experiment will not claim

- It does not claim the market is right or wrong about any player; the market line is never an input.
- It does not test depth-chart position historically (data does not exist).
- It does not test vacated-volume features (measured ≈ 0 effect; excluded by design).
- A null on M2 does not invalidate Kalman approaches generally — it answers whether this 3-parameter specification adds value over Model D on the locked test.
- No betting-edge claims: projection accuracy only.

## 7. 2026-prospective companion (not part of the frozen ladder)

Depth-chart snapshots exist for 2026. A separate, non-preregistered research track may build current-role signals into the 2026 monitoring stream only, evaluated prospectively. It cannot inherit this experiment's locked-test verdict and cannot enter production without its own preregistered test. This document does not authorize it.

## 8. Approval gate

Cale's approval freezes: the targets/population (§1), the structural hypothesis (§2), the information audit and capacity discipline (§3), the fixed ladder (§4), the metrics/slices/win bar (§5), and the production gate (shared protocol §8). After freezing: dev fitting and diagnostics, then the single locked-test evaluation. **No production changes regardless of outcome** — on a MATERIAL WIN, produce the research verdict plus the production-change package (changed features, data dependencies, freshness requirements, failure behavior, rollback plan), then STOP and wait for Cale's explicit authorization.

## Freeze notes (Cale 2026-10-01)
- Approved to freeze exactly as drafted: "just do what you have to do to test it." Approval to freeze is NOT approval of any candidate or production change.
- Sequence authorized: FREEZE → RUN DEV ONLY → LOCK PARAMETERS → ONE LOCKED-TEST EVALUATION. Do not compute anything on 2023–2024 until parameters are locked from dev.
