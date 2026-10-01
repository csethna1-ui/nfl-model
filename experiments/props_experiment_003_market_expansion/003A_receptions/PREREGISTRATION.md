# PREREGISTRATION — Props Experiment 003A: Receptions

**Status: FROZEN — APPROVED by Cale 2026-10-01 12:25 CDT. Frozen exactly as drafted: nothing added, nothing removed after freeze. Fit once; evaluate per preregistered target and win bar. No production changes regardless of outcome.
This protocol returns to Cale for approval/freezing BEFORE any 2023–2024
computation for this experiment.**

Shared discipline: `MARKET_EXPANSION_PROTOCOL.md` (as-of rules, splits,
fixed ladder, win bar, paper-tracking, production gate). This document
defines 003A's target, structural hypothesis, information audit, and
experiment-specific parameters.

## 1. Target

`receptions` — player-game receptions (nflverse weekly `player_stats`),
walk-forward MAE vs the trailing-history baseline M0 (§3 of shared
protocol). Population: WR/TE/RB with `eligible_hist=1` AND `played_role=1`
(001/002 role thresholds); evaluated rows require trailing targets > 0.

Outcome n (2023–2024): ~3,625 player-games — clears the ≥2,500 minimum.

## 2. Structural hypothesis

Receptions is the natural expansion of the existing receiving model, but
built as a **process model** rather than a parallel number:

```
routes → target probability → expected targets → expected receptions → receiving yards
```

Concretely: P(target) from role/snap context × P(reception | target) from
catch-point quality (separation, cushion, ADOT, QB accuracy context) gives
expected receptions; receiving yards becomes downstream of the same
process. The experiment tests whether modeling the *mechanism* beats
naive trailing history — and later, whether it feeds back into the
receiving-yard distribution.

## 3. Information audit (verified read-only 2026-10-01)

Trailing convention: EWMA half-life 3, max 16 games, strictly prior weeks.
"As-of OK" = usable at Friday 18:00 CT under the shared protocol.

| Candidate feature | Source (verified) | Available keyless? | Since | As-of OK? | Notes |
|---|---|---|---|---|---|
| Targets (trailing) | nflverse `player_stats.targets` | Yes | 2018 | Yes | Core process input |
| Target share | `player_stats.target_share` | Yes | 2018 | Yes | |
| Air-yard share / WOPR | `player_stats.air_yards_share`, `wopr` | Yes | 2018 | Yes | |
| Receiving air yards / ADOT | `receiving_air_yards` / targets | Yes | 2018 | Yes | ADOT = air_yards/targets |
| **Routes / route participation** | — | **NO — explicitly unavailable** | — | — | No keyless source (002 documented; re-verified: absent from nflverse and NGS feed). Proxy: snap share + NGS intended-air-yard share |
| Snap share | nflverse `snap_counts.offense_pct` (local 2018–2026) | Yes | 2018 | Yes | Route proxy |
| NGS separation | `import_ngs_data('receiving').avg_separation` | Yes | 2016 | Trailing only | UNTESTED in 001/002 |
| NGS cushion | `avg_cushion` | Yes | 2016 | Trailing only | UNTESTED |
| NGS intended air yards | `avg_intended_air_yards` | Yes | 2016 | Trailing only | UNTESTED |
| NGS intended-air-yard share | `percent_share_of_intended_air_yards` | Yes | 2016 | Trailing only | UNTESTED; role proxy |
| NGS expected YAC / YAC over expected | `avg_expected_yac`, `avg_yac_above_expectation` | Yes | 2016 | Trailing only | Catch-point quality |
| QB context (expected starter) | 002 Family I reconstruction (no post-game info) | Yes | 2018 | Yes | Includes CPOE/ADOT/pressure trails |
| Opponent pass defense | Pre-week `oppd_def_pass_epa` (002 Family C) | Yes | 2018 | Yes | Strictly prior-week ratings |
| Team pass rate | `pace_neutral_pass_rate` (002 Family E) | Yes | 2018 | Yes | |
| Expected plays | `pace_team_plays`, `pace_combined` (002 Family E) | Yes | 2018 | Yes | |
| Team offensive context | `ctx_*` (002 Family B) | Yes | 2018 | Yes | |
| Injury/personnel (as-of) | `inj_*` (002 Family L, date_modified ≤ cutoff) | Yes | 2018 | Yes | Feed-available info only |
| Game environment / rest | `envs_*`, `envf_*` (002 Families D1/D2) | Yes | 2018 | Yes | Pre-known |
| Market spread/total | — | **EXCLUDED (leakage rule)** | — | — | No timestamped Friday lines historically (006 backfill: zero A-class). ELO-diff is the proxy |

## 4. Fixed ladder (no family selection)

- **M0:** trailing receptions EWMA (shared §3), frozen.
- **M1 (process model):** two-stage — (1) expected targets from
  targets/target-share/snap-share/team-pass-rate/expected-plays/opponent
  context; (2) catch probability from ADOT/separation-proxy/QB context →
  expected receptions. Ridge + GBM per the shared hyperparameter procedure.
- **M2:** M1 + NGS family (`avg_separation`, `avg_cushion`,
  `avg_intended_air_yards`, `percent_share_of_intended_air_yards`,
  `avg_expected_yac`, `avg_yac_above_expectation` — trailing only). Named
  family, tested not assumed.
- **M3:** M1 + team/matchup/game-context families (B, C, D1, D2, E, L).

Each rung vs M0 independently against the shared win bar
(≥5% pooled, ≥2% per season, bootstrap CI excludes zero).

## 5. What this experiment will not claim

- It does not claim a betting edge (no historical lines; §7 of shared
  protocol governs the prospective stream).
- It does not test routes directly — route participation is unavailable;
  the audit states the proxy plainly.
- A null here does not invalidate the receiving-yards engine; it answers
  whether the process decomposition adds value for the receptions target.

## 6. Approval gate

Cale's approval freezes: the target/population (§1), the process-model
specification (§2), the feature audit (§3), the fixed ladder (§4), and the
shared win bar. After freezing: dev diagnostics, then the single
locked-test evaluation.

## Freeze notes (Cale 2026-10-01 12:25 CDT)
- No routes/route-participation data exist keyless. Snap share + NGS air-yard share are the frozen documented proxies. Do NOT reconstruct routes from another source after freezing.
