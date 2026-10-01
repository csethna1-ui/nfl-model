# PREREGISTRATION — Props Experiment 003B: Rush Attempts

**Status: FROZEN — APPROVED by Cale 2026-10-01 12:25 CDT. Frozen exactly as drafted: nothing added, nothing removed after freeze. Fit once; evaluate per preregistered target and win bar. No production changes regardless of outcome.
This protocol returns to Cale for approval/freezing BEFORE any 2023–2024
computation for this experiment.**

Shared discipline: `MARKET_EXPANSION_PROTOCOL.md`. This document defines
003B's target, structural hypothesis, information audit, and
experiment-specific parameters.

## 1. Target

`carries` (rush attempts) — player-game carries (nflverse weekly
`player_stats`), walk-forward MAE vs trailing-history baseline M0.
Population: RB (position_group) with `eligible_hist=1` AND `played_role=1`;
evaluated rows require trailing carries ≥ 5/game (the audit's clean-role
cut — below this the distribution is zero-inflated).

Outcome n (2023–2024): ~1,528 player-games — clears the ≥1,000 minimum.

**Coverage flag:** Bovada currently posts ~2 rush-attempt lines per slate
(vs 55 for receptions). The experiment is valid as projection research per
the 001/002 precedent; paper-tracking will be sparse until coverage
improves. Recorded as a market fact, not a modeling caveat.

## 2. Structural hypothesis

Rush attempts is **closer to pure opportunity than rushing yards** — volume
is more predictable than efficiency, and 002's only directional signals on
the rush side (M3/M6 ≈ −0.6%/−0.7% on rush yards) lived in opportunity
features. The hypothesis:

```
team plays × RB role share × game-script adjustment → expected attempts
```

If attempts are predictable, the result feeds back into the rushing-yard
distribution later (attempts as the volume half of a yards decomposition).
This experiment tests the volume half only.

## 3. Information audit (verified read-only 2026-10-01)

| Candidate feature | Source (verified) | Available keyless? | Since | As-of OK? | Notes |
|---|---|---|---|---|---|
| Snap share | nflverse `snap_counts.offense_pct` (local 2018–2026) | Yes | 2018 | Yes | Role anchor |
| Carry share | Derivable: `carries` / team carries (`player_stats` team aggregates) | Yes | 2018 | Yes | Build-time derivation, trailing only |
| Team plays | `pace_team_plays` (002 Family E) | Yes | 2018 | Yes | |
| Neutral rush rate | Derivable from pbp: 1 − neutral pass rate (002 precedent) | Yes | 2018 | Yes | Game-script-free run tendency |
| Game spread | — | **EXCLUDED (leakage rule)** | — | — | No timestamped Friday lines (006: zero A-class). Proxy: pre-week ELO diff `ctx_elo_adv` |
| Injury/personnel (as-of) | `inj_*` (002 Family L); `inj_team_out_share` captures backfield injuries | Yes | 2018 | Yes | Depth-chart *changes* feed-available via injury report |
| **Historical depth-chart position** | — | **NO — explicitly unavailable** | — | — | Local depth charts are 2026-only (002 documented). Injury report is the historical personnel-change source |
| Goal-line / red-zone role | `ruq_goal_line_carries`, `trail_rz_carries_ewma` (002 precedent, pbp-derived) | Yes | 2018 | Yes | |
| Opponent rush defense | Pre-week `oppd_def_rush_epa` (002 Family C) | Yes | 2018 | Yes | |
| Team offensive context | `ctx_*` (002 Family B) | Yes | 2018 | Yes | |
| NGS rushing efficiency | `import_ngs_data('rushing').efficiency` | Yes | 2016 | Trailing only | UNTESTED in 001/002 |
| NGS expected rush yards | `expected_rush_yards` (raw column — verified) | Yes | 2016 | Trailing only | UNTESTED; audit understated this |
| NGS rush yards over expected | `rush_yards_over_expected`, `rush_pct_over_expected` | Yes | 2016 | Trailing only | UNTESTED; efficiency signal |
| NGS 8-man-box rate | `percent_attempts_gte_eight_defenders` | Yes | 2016 | Trailing only | UNTESTED; defensive respect / role proxy |
| NGS time to LOS | `avg_time_to_los` | Yes | 2016 | Trailing only | UNTESTED |
| Game environment / rest | `envs_*`, `envf_*` (002 Families D1/D2) | Yes | 2018 | Yes | |

## 4. Fixed ladder (no family selection)

- **M0:** trailing carries EWMA, frozen.
- **M1 (opportunity model):** team plays × carry share × snap share ×
  neutral rush rate × ELO-diff game-script adjustment × red-zone role.
- **M2:** M1 + NGS rushing family (efficiency, expected rush yards, yards
  over expected, 8-man-box rate, time to LOS — trailing only).
- **M3:** M1 + team/matchup/game-context families (B, C, D1, D2, E, L).

Each rung vs M0 independently against the shared win bar.

## 5. What this experiment will not claim

- No betting-edge claim (2 live lines; the prospective stream accumulates
  what the market posts).
- It does not model rushing efficiency — attempts only. The yards
  decomposition is future work, contingent on this result.
- Depth-chart *levels* are not a feature (unavailable historically);
  depth-chart *changes* enter only via the as-of injury feed, stated
  plainly.

## 6. Approval gate

Cale's approval freezes: target/population/coverage-flag (§1), opportunity
specification (§2), feature audit (§3), fixed ladder (§4), shared win bar.
After freezing: dev diagnostics, then the single locked-test evaluation.

## Freeze notes (Cale 2026-10-01 12:25 CDT)
- Include the confirmed NGS fields (expected rush yards, rush yards over expected, rush % over expected) where the preregistration specifies them — prespecified available candidates, not a rewrite.
