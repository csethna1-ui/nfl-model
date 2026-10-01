# PREREGISTRATION — Props Experiment 005: Player Role Transition Model

**Status: FROZEN — APPROVED by Cale 2026-10-01. Frozen exactly as drafted plus the additive-candidate clarification (§4, Cale's 2026-10-01 approval). Fit once on dev; evaluate per preregistered target and win bar. No production changes regardless of outcome.
This protocol returns to Cale for approval/freezing BEFORE any 2023–2024 computation for this experiment — that approval is now recorded here. Approval to freeze is NOT approval of any candidate or production change.**
**Numbering:** props sub-series 005. (004 = defensive matchup, frozen 2026-10-01, NOT RUN — untouched by this document.)
**Experiment record:** `RECONSTRUCTABILITY_AUDIT.md` (verified read-only 2026-10-01) is a frozen part of this experiment's record. The absence of historical depth-chart data is itself a research finding and the documented reason candidate C was excluded from the ladder.

Shared discipline: `props_experiment_003_market_expansion/MARKET_EXPANSION_PROTOCOL.md` (§1 research philosophy, §2 as-of discipline, §4 hyperparameter procedure, §8 production gate) applies unless this document states otherwise. This document defines 005's target, structural hypothesis, reconstructability-constrained candidate list, and experiment-specific parameters.

## 0. Motivation (diagnostic, not a feature)

Week 4 2026 production showed C. Rodriguez (JAX) rushing yards: model 59.2 vs market line 19.5 — a 39.7-yard gap. The underlying data: 16-game trailing history with a 37.8 baseline EWMA, but Jacksonville Weeks 1–3 showed 6/6/8 carries (11.7 expected) while the trailing window still carried Washington-era 10–16-carry games. The market is not assumed right ("the market can be wrong") — the gap is a diagnostic clue that the model's trailing window can overweight stale opportunity after a team/role change.

## 1. Target

The three yardage targets of the 001/002 research line: **passing yards** (QB), **rushing yards** (RB), **receiving yards** (WR/TE/RB). Each target is evaluated independently with the shared win bar (§5). Population per target: `eligible_hist=1` AND `played_role=1` (001/002 role thresholds); evaluated rows per each target's frozen role definition.

## 2. Structural hypothesis

Player ability/efficiency transfers across teams; **current role/opportunity does not necessarily transfer**. The production engine's 16-game trailing window implicitly assumes historical opportunity remains representative after a team or role change. The experiment tests a hierarchical alternative:

> **expected opportunity** (driven primarily by current-team/current-role evidence) × **expected efficiency** (informed by both current and historical evidence — talent carries over)

Concretely: when a player changes teams, prior-team carries/targets should decay in influence while current-team usage — even a 1–3 game sample — should dominate the opportunity estimate. Efficiency (yards per carry, yards per target) may still draw on the longer history.

## 3. Information audit (binding — from RECONSTRUCTABILITY_AUDIT.md, verified read-only 2026-10-01)

| Candidate signal | Verdict | Source |
|---|---|---|
| Team per player-week / team-change indicator / games with current team | RECONSTRUCTABLE | `player_games.parquet` team stints, 2018–2026 |
| Current-team carries, targets, touches (trailing) | RECONSTRUCTABLE | `player_games.parquet` |
| Current-team efficiency (ypc, ypt, catch rate) | RECONSTRUCTABLE | Derived |
| Snap share (trailing) | RECONSTRUCTABLE | `data/v2/raw/snap_counts_<season>.csv`, 2018–2026 |
| Red-zone usage (trailing) | RECONSTRUCTABLE | Derived from `data/pbp_<season>.parquet` |
| Routes / route participation | NOT AVAILABLE | — (003A freeze note stands) |
| Depth-chart position (RB1/2/3, WR1/2/3/4) | **NOT AVAILABLE historically** — 2026 snapshots only | `data/prod_aux_depth_charts.parquet` (all 208 snapshots Aug–Sep 2026) |
| Market line as a feature | **EXCLUDED** | Leakage rule — diagnostic only, never an input |

**Binding design consequence:** the explicit depth-chart candidate (Cale's candidate C as sketched) is **excluded from the frozen ladder** — there is no historical depth-chart data to evaluate it on. It is retained as a **2026-prospective-only** research candidate (§7). The ladder below uses only reconstructable signals.

## 4. Fixed ladder (no family selection; 002 lesson binding)

**Additive-candidate rule (binding, Cale 2026-10-01):** M1–M3 are additive candidates evaluated against the exact frozen M0 implementation. No candidate may alter, refit, retrain, or otherwise modify the underlying Model D training pipeline or fitted artifacts. The experiment changes the role/opportunity treatment, not the frozen player projection model. The causal question stays clean: does explicitly modeling a player's transition in role/opportunity improve the existing projection?

- **M0 (baseline):** frozen Props Model D predictions, used read-only. Model D is not modified, refit, or touched in any way.
- **M1 (current-team opportunity blend):** M0's trailing opportunity component is replaced by a hierarchical blend: current-team trailing EWMA (games within the current team stint) + prior-team trailing EWMA, with the blend weight, a team-change indicator, and current-team game count as inputs. **The blend weight is learned on dev (2021–2022) and frozen before the locked test — never hand-set, never chosen to fix any individual player.**
- **M2 (M1 + team-transition decay):** M1 plus exponential decay of prior-team history as a function of games since the team change. Decay rate learned on dev, frozen before the locked test.
- **M3 (M1 + opportunity/efficiency separation):** the full hierarchical form — projection = expected opportunity (current-role-driven, per M1) × expected efficiency (blended across current-team and prior-team history, since talent carries over). Blend parameters learned on dev, frozen before the locked test.

Each rung vs M0 independently against the win bar (§5). No union models, no dev-gated mega-model. **The ladder does not change after dev results are seen** — if M1–M3 all fail on dev, that is reported as-is; a dev pass still has to clear the preregistered locked-test criteria.

**Hyperparameter/structural-parameter procedure:** Ridge alpha grid {0.1, 1, 10, 100} and the 8-combo GBM grid re-selected on dev per rung (003 §4 precedent); structural parameters (blend weights, decay rates) grid-searched on dev only. Seeds fixed (1337). The procedure is frozen; its outcomes may differ per rung.

## 5. Metrics, slices, and win bar

**Primary metric:** walk-forward MAE of point projections vs actuals, per target. Also RMSE, bias, MAE by season. Paired bootstrap (2000 resamples, seed 1337) CIs for M0-vs-challenger differences.

**Win bar — ALL must hold, per target:**
1. Pooled 2023–2024: **≥5% relative MAE reduction** vs M0, on the overall eligible population;
2. Pooled 2023–2024: **≥5% relative MAE reduction** vs M0, on the **transfer-stint population** (player-games in a team-change stint) — the mechanism must show where the hypothesis says it should;
3. **≥2% relative reduction in 2023 AND in 2024 individually** (overall population);
4. **95% paired bootstrap CI** of the MAE difference excludes zero (overall and transfer-stint);
5. **Regression guard:** on non-transfer player-games, the challenger must not degrade more than **1%** relative MAE vs M0.

**Diagnostic slices (reported, not win/loss):**
- Transfer stint, games 1–3 with new team (~287 pooled rows — adequate pooled; per-season ~143, reported as exploratory if <150);
- Transfer stint, games 4–6 with new team (~86 pooled rows — **underpowered**; directional only, never a verdict slice);
- Transfer stint, games 7+;
- Passing-yards transfer slice (QB team changes are rare — expected underpowered; reported as such, not forced).

Per the audit's minimum-sample rule: slices with <150 player-games per season are reported as underpowered, not as wins or nulls.

## 6. What this experiment will not claim

- It does not claim the market is right or wrong about any player — the market line is never an input, and no rule of the form "if the model is X above the line, reduce" will be created.
- It does not test depth-chart position historically — that data does not exist (audit §3). Any depth-chart finding is 2026-prospective only.
- A null here does not invalidate the role-transition hypothesis in general; it answers whether these reconstructable signals add value on the locked test.
- No betting-edge claims: projection accuracy only, per the paper-tracking discipline.

## 7. 2026-prospective companion (not part of the frozen ladder)

Depth-chart snapshots exist for 2026 (`pos_rank` ordering within formation groups). A separate, non-preregistered research track may build current-role signals from 2026 depth charts + snap shares into the **2026 monitoring stream only**, evaluated prospectively against timestamped outcomes. It cannot inherit this experiment's locked-test verdict and cannot enter production without its own preregistered test. This document does not authorize it — it only records that the audit leaves the door open.

## 8. Approval gate

Cale's approval freezes: the targets/population (§1), the structural hypothesis (§2), the reconstructability-constrained audit (§3), the fixed ladder and additive-candidate rule (§4), the metrics/slices/win bar (§5), and the production gate (shared protocol §8). After freezing: dev fitting and diagnostics, then the single locked-test evaluation. **No production changes regardless of outcome** — on a MATERIAL WIN, produce the research verdict plus the production-change package (changed features, data dependencies, freshness requirements, failure behavior, rollback plan), then STOP and wait for Cale's explicit authorization.

## Freeze notes (Cale 2026-10-01)
- Approved to freeze exactly as drafted, with the §4 additive-candidate clarification added verbatim: the experiment changes role/opportunity treatment, not the underlying frozen Model D. Approval to freeze is NOT approval of any candidate or production change.
- The audit (`RECONSTRUCTABILITY_AUDIT.md`) is preserved as part of the frozen experiment record; the absence of historical depth-chart data is the documented reason candidate C was excluded.
- Sequence authorized: FREEZE → RUN DEV ONLY → LOCK PARAMETERS → ONE LOCKED-TEST EVALUATION. Do not compute anything on 2023–2024 until parameters are locked from dev.
