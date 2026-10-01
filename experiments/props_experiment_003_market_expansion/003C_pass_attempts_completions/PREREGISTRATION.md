# PREREGISTRATION — Props Experiment 003C: Pass Attempts + Hierarchical Completions

**Status: FROZEN — APPROVED by Cale 2026-10-01 12:25 CDT. Frozen exactly as drafted: nothing added, nothing removed after freeze. Fit once; evaluate per preregistered target and win bar. No production changes regardless of outcome.
This protocol returns to Cale for approval/freezing BEFORE any 2023–2024
computation for this experiment.**

Shared discipline: `MARKET_EXPANSION_PROTOCOL.md`. This document defines
003C's targets, structural hypothesis, information audit, and
experiment-specific parameters.

## 1. Targets

- **Primary target:** `attempts` — player-game pass attempts (nflverse
  weekly `player_stats`), walk-forward MAE vs trailing-history baseline M0.
- **Hierarchical extension:** `completions` — evaluated ONLY as downstream
  of attempts. Completions is NOT a standalone experiment: at r≈0.95+ with
  attempts it would mostly re-test the same signal. The question is whether
  a completion-probability model adds anything *given* attempts.

Population: QB with `eligible_hist=1` AND `played_role=1` under the 002
expected-starter reconstruction (the QB with most attempts over the team's
trailing 4 games, adjusted for as-of Out/Doubtful status — actual game
starter never used).

Outcome n (2023–2024): ~1,010–1,190 player-games — clears the ≥700 minimum.
Bovada posts 12 pass-attempt and 12 completion lines per slate.

## 2. Structural hypothesis

The QB opportunity hierarchy — a volume target, explicitly NOT redundant
with 002 (which tested efficiency/context features for passing *yards*):

```
expected plays → pass rate → pass attempts → completion probability → completions → passing yards
```

Attempts is driven by game script, team pass rate, and QB role — a
different information set from the efficiency features 002 tested.
Completions then test the incremental value of completion% modeling
(accuracy, aggressiveness, time-to-throw, expected completion %) *on top
of* the attempts projection.

## 3. Information audit (verified read-only 2026-10-01)

| Candidate feature | Source (verified) | Available keyless? | Since | As-of OK? | Notes |
|---|---|---|---|---|---|
| Team pace / expected plays | `pace_team_plays`, `pace_combined` (002 Family E) | Yes | 2018 | Yes | |
| Team pass rate / neutral pass rate | `pace_neutral_pass_rate` (002 Family E) | Yes | 2018 | Yes | |
| Spread | — | **EXCLUDED (leakage rule)** | — | — | No timestamped Friday lines. Proxy: `ctx_elo_adv` |
| Total | — | **EXCLUDED (leakage rule)** | — | — | Same. Proxy: `pace_combined` + team scoring trails |
| QB identity (expected starter) | 002 reconstruction algorithm | Yes | 2018 | Yes | No post-game info |
| QB injury/status (as-of) | `inj_player_status` for expected starter (002 Family L) | Yes | 2018 | Yes | date_modified ≤ cutoff |
| QB trailing efficiency | `qb_epa_trail`, `qb_cpoe_trail`, `qb_adot_trail`, `qb_pressure_trail` (002 Family I) | Yes | 2018 | Yes | |
| Opponent pass defense | Pre-week `oppd_def_pass_epa` (002 Family C) | Yes | 2018 | Yes | |
| Expected game script | `ctx_elo_adv` + pace features (no spread) | Yes | 2018 | Yes | Stated proxy, not hidden |
| NGS time to throw | `import_ngs_data('passing').avg_time_to_throw` | Yes | 2016 | Trailing only | UNTESTED in 001/002 |
| NGS aggressiveness | `aggressiveness` | Yes | 2016 | Trailing only | UNTESTED; downfield tendency |
| NGS intended air yards | `avg_intended_air_yards` | Yes | 2016 | Trailing only | UNTESTED |
| NGS expected completion % | `expected_completion_percentage` (**verified raw column**) | Yes | 2016 | Trailing only | UNTESTED; audit understated — this IS in the keyless feed |
| NGS CPOE | `completion_percentage_above_expectation` (**verified raw column**) | Yes | 2016 | Trailing only | UNTESTED; feeds the completions leg |
| NGS air yards to sticks | `avg_air_yards_to_sticks` | Yes | 2016 | Trailing only | UNTESTED; situational aggression |
| Team offensive context | `ctx_*` (002 Family B) | Yes | 2018 | Yes | |
| Game environment / rest | `envs_*`, `envf_*` (002 Families D1/D2) | Yes | 2018 | Yes | |

## 4. Fixed ladder (no family selection)

Attempts rungs:
- **M0:** trailing attempts EWMA, frozen.
- **M1 (volume model):** expected plays × pass rate × ELO-diff script
  adjustment × QB-identity/role context.
- **M2:** M1 + NGS passing family (time to throw, aggressiveness, intended
  air yards, air yards to sticks — trailing only).
- **M3:** M1 + team/matchup/game-context families (B, C, D1, D2, E, L)
  + QB efficiency trails.

Completions leg (hierarchical — evaluated only if the attempts rungs exist):
- **C0:** attempts-projection × trailing completion% (naive downstream).
- **C1:** attempts-projection × modeled completion probability (NGS
  expected completion %, CPOE trail, aggressiveness, ADOT, pressure).
- The completions question is answered by C1 vs C0: does completion%
  modeling add value *given* attempts? A C1 win is not a standalone
  "completions model win."

Each rung vs its baseline independently against the shared win bar.

## 5. What this experiment will not claim

- Completions is not an independent model and gets no independent verdict.
- No spread/total features — the ELO-diff + pace proxy is stated, not
  smuggled in as "game script."
- A null on attempts does not invalidate 002's passing-yards work; volume
  and efficiency are different targets.

## 6. Approval gate

Cale's approval freezes: targets/population (§1), hierarchy specification
(§2, including the completions-as-downstream rule), feature audit (§3),
fixed ladder (§4), shared win bar. After freezing: dev diagnostics, then
the single locked-test evaluation.

## Freeze notes (Cale 2026-10-01 12:25 CDT)
- Game-script information stays weak by design: spread/total/implied scoring EXCLUDED per the 002 leakage rule. Pre-week ELO differential + trailing scoring are the frozen proxies. Do NOT substitute historical spread/total data after the fact.
