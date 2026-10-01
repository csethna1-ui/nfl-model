# PREREGISTRATION — Props Experiment 003D: Anytime Touchdown Scorer

**Status: FROZEN — APPROVED by Cale 2026-10-01 12:25 CDT. Frozen exactly as drafted: nothing added, nothing removed after freeze. Fit once; evaluate per preregistered target and win bar. No production changes regardless of outcome.
This protocol returns to Cale for approval/freezing BEFORE any 2023–2024
computation for this experiment.**

Shared discipline: `MARKET_EXPANSION_PROTOCOL.md`. This document defines
003D's target, structural hypothesis, information audit, and
experiment-specific parameters. **This is a separate model family with its
own statistical protocol** — the MAE framework does not transfer to a
binary target.

## 1. Target

Binary: did the player score a touchdown (rushing or receiving) in the
game? `1{rushing_tds + receiving_tds > 0}` (nflverse weekly `player_stats`;
return/special-teams TDs excluded — the opportunity model covers offensive
role only, stated plainly).

Population: WR/TE/RB (+ mobile-QB rushing TD exposure handled via the
rushing-TD component) with `eligible_hist=1` AND `played_role=1`.

Outcome (2023–2024): 6,235 player-games, **1,830 TD events**, base rate
0.294 — clears the ≥3,000 player-games AND ≥500 events minimum.
Bovada posts 13+ anytime-TD lines per slate.

## 2. Structural hypothesis — expected TD opportunity, NOT TD history

Do not model "player scored recently → likely to score." Touchdowns are
noisy outcomes; **opportunity is measurable**. The model estimates
expected touchdown opportunity from usage where touchdowns happen:

- **RB:** red-zone carries, goal-line carries, inside-10 carries, snap
  share, carry share, team scoring environment, opponent red-zone defense,
  expected game script.
- **WR/TE:** red-zone targets, end-zone targets, target share, route
  participation (via snap proxy — routes unavailable), air yards, team
  scoring environment.

Trailing raw TD rate enters ONLY as the M0 baseline — never as a
"hot hand" feature in challengers.

## 3. Information audit (verified read-only 2026-10-01)

| Candidate feature | Source (verified) | Available keyless? | Since | As-of OK? | Notes |
|---|---|---|---|---|---|
| Red-zone targets | `trail_rz_targets_ewma` (002 precedent, pbp-derived) | Yes | 2018 | Yes | Already built |
| Red-zone carries | `trail_rz_carries_ewma` (002 precedent) | Yes | 2018 | Yes | Already built |
| Goal-line carries | `ruq_goal_line_carries` (yardline_100 ≤ 5, 002 Family H) | Yes | 2018 | Yes | Already built |
| Inside-10 opportunities | Derivable from pbp (`yardline_100 ≤ 10`, carries + targets) | Yes | 2018 | Yes | Derivation needed; same pbp already in-house |
| End-zone targets | Derivable from pbp (`air_yards ≥ yardline_100` on pass plays) | Yes | 2018 | Yes | Derivation needed |
| Target / carry share | `player_stats` team aggregates | Yes | 2018 | Yes | |
| Team scoring environment | Trailing points scored `envs_team_pts_trail` (002 D1) | Yes | 2018 | Yes | **Implied totals EXCLUDED (leakage rule)** — no spread/total; trailing scoring is the proxy, stated |
| Opponent points allowed | `envs_opp_pts_allowed_trail` (002 D1) | Yes | 2018 | Yes | |
| Opponent red-zone defense | Derivable from pbp: trailing opponent red-zone TD rate allowed | Yes | 2018 | Yes | Derivation needed |
| Player role (snap share) | `snap_counts.offense_pct` (local 2018–2026) | Yes | 2018 | Yes | |
| **Route participation** | — | **NO — explicitly unavailable** | — | — | Snap share is the proxy, stated |
| NGS separation / cushion / intended air yards | `import_ngs_data('receiving')` | Yes | 2016 | Trailing only | UNTESTED; catch-point quality for WR/TE |
| NGS rushing efficiency / expected rush yards | `import_ngs_data('rushing')` | Yes | 2016 | Trailing only | UNTESTED; goal-line effectiveness |
| QB context / injury as-of | 002 Families I, L | Yes | 2018 | Yes | |
| Game environment / rest | 002 Families D1/D2 | Yes | 2018 | Yes | |

## 4. Fixed ladder (no family selection)

- **M0:** trailing TD-rate EWMA with shrinkage toward position base rate
  (exact shrinkage form frozen at approval), frozen.
- **M1 (opportunity model):** red-zone/goal-line/inside-10/end-zone usage +
  target/carry share + snap share + team scoring environment + opponent
  red-zone defense. Logistic / GBM-classifier per the shared
  hyperparameter procedure (procedure frozen; binary-appropriate grids).
- **M2:** M1 + NGS family (trailing only).
- **M3:** M1 + team/matchup/game-context families.

Each rung vs M0 independently against the 003D win bar (§5).

## 5. Metrics and win bar (binary protocol)

- **Primary: Brier score** (walk-forward, evaluated rows only).
- **Secondary:** log loss; **calibration** — reliability by
  predicted-probability bucket (10 buckets; buckets with n<100 reported
  but excluded from the bar); ROC-AUC / PR-AUC as diagnostics;
  actual event rate vs mean predicted probability.
- Win bar (all must hold):
  1. Pooled 2023–2024: **≥5% relative Brier reduction** vs M0;
  2. **≥2% relative Brier reduction in 2023 AND in 2024 individually**;
  3. **Calibration:** no bucket (n≥100) deviates > 0.06 absolute from the
     diagonal; calibration slope within [0.85, 1.15];
  4. 95% paired bootstrap CI of the Brier difference excludes zero.

**"Likely to score" is NOT a betting recommendation.** This experiment
produces probabilities, not picks. No wagering implication may be drawn
without validated calibration AND a prospective market comparison against
timestamped lines (§7 of shared protocol). A well-calibrated 0.35 is
information; it is not a bet.

## 6. What this experiment will not claim

- It does not claim an edge vs the anytime-TD market (no historical
  lines exist).
- It does not use raw TD history as a predictive feature (M0 only).
- Return/special-teams TDs are out of scope (opportunity model covers
  offensive role).
- A null does not mean "touchdowns are unpredictable" — it means
  *expected opportunity as specified* did not beat trailing TD rate by
  the bar.

## 7. Approval gate

Cale's approval freezes: target/population (§1), the
expected-opportunity specification (§2), feature audit (§3), fixed ladder
(§4), the binary win bar and the no-betting-recommendation rule (§5).
After freezing: dev diagnostics (including calibration on dev), then the
single locked-test evaluation.

## Freeze notes (Cale 2026-10-01 12:25 CDT)
- Binary-event framework stands alone: Brier score + calibration are the primary language. Do NOT force the 5% MAE rule onto this experiment. "Likely to score" is never a betting recommendation without validated calibration.
