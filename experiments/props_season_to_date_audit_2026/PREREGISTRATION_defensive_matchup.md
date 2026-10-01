# Preregistration: Defensive Matchup Experiment (004) — FROZEN

**Status: FROZEN 2026-10-01 (Cale). No model fit. No locked-test computation.
Do not run until Cale explicitly authorizes the run.**
**Scope: design only.**

## 0. Availability audit (pre-freeze gate — completed 2026-10-01, no fitting)

Each specified feature checked against local keyless nflverse pbp
(data/pbp_2018–2025.parquet). Result:

| Feature | Verdict | Keyless derivation |
|---|---|---|
| opp_catch_rate_allowed | KEEP | complete_pass / (complete_pass + incomplete_pass), by defteam, pbp |
| opp_yac_allowed | KEEP | yards_after_catch per reception allowed, by defteam, pbp |
| opp_air_yards_allowed | KEEP | air_yards per target allowed, by defteam, pbp |
| opp_pressure_rate | KEEP (redefined) | (sack + qb_hit) per dropback, by defteam, pbp. `qb_hurry` is not in nflverse pbp, so hurries are excluded from the formula by availability, not by selection. |
| opp_target_concentration | DROPPED | `receiver_player_position` is not in nflverse pbp and no roster/position data is on hand. No keyless derivation. |
| Own-QB context (002 Family I) | KEEP | Already verified keyless in Experiment 002. |
| opp_rush_epa_allowed | KEEP | epa per rush allowed, by defteam, pbp |
| opp_rush_success_allowed | KEEP | success per rush allowed, by defteam, pbp |
| opp_stuff_rate | KEEP | tackled_for_loss rate vs rushes, by defteam, pbp |
| opp_early_down_rush_rate_faced | KEEP | rush rate on early downs faced, by defteam, pbp |
| Coverage-shell tendencies (man/zone) | DROPPED | No verified keyless source. |
| Separation allowed | DROPPED | No verified keyless source. |
| Defense-imposed 8+ box rate | DROPPED | NGS box data is rusher-side; no keyless opponent-side source. |
| Run-front tendencies | DROPPED | No verified keyless source. |

Drops are for availability only, documented here before any fitting. They are
not selection on results. The frozen feature sets are §4a (5 features) and
§4b (4 features) as amended above.

## 1. Research question

Do opponent-specific, mechanism-relevant matchup features add *incremental*
predictive value **on top of** the frozen NGS-enhanced models:

- 003A-M2-verified (receptions)
- 003B-M2-frozen (rush attempts)

Generic opponent strength (opponent EPA) already failed to add value in
Experiment 002. This experiment tests *mechanism-specific* matchup
information only — not another generic opponent-quality feature.

## 2. Design: stacked challenger vs frozen null

For each market independently:

- **Null (M0-matchup):** the frozen model's prediction alone
  (003A-M2-verified for receptions; 003B-M2-frozen for rush attempts).
  No refit. No changes.
- **Challenger (M1-matchup):** a fixed Ridge regression on
  `[frozen_prediction, matchup_features...]`, fit on train, with the
  Ridge penalty chosen on dev from a fixed grid {0.01, 0.1, 1.0, 10.0}.
  No other model family. No feature selection on dev beyond the penalty.

Primary comparison: locked-test MAE(M1-matchup) vs MAE(M0-matchup).
This directly answers "does matchup info add anything the NGS model
doesn't already capture," and mirrors how the features would actually
be deployed (as an overlay, not a rebuild).

Secondary diagnostic: residual-on-matchup regression
(residual = actual − frozen_prediction regressed on matchup features);
reported descriptively, never as the verdict.

## 3. Splits and as-of discipline

- Train: 2018–2020. Dev: 2021–2022 (penalty choice only). Locked test: 2023–2024.
- Friday 18:00 CT America/Chicago as-of; all matchup features trailing-only,
  strictly prior weeks.
- Spread, total, implied scoring: EXCLUDED (002 leakage rule).
- NGS: trailing-only, same conventions as 003A/003B.
- Each market evaluated independently. No pooled verdict across markets.

## 4. Feature families (mechanism-specific only)

### 4a. Receptions matchup features (trailing, opponent-side)
1. `opp_catch_rate_allowed` — opponent completions/targets faced (pbp).
2. `opp_yac_allowed` — opponent YAC per reception allowed (pbp).
3. `opp_air_yards_allowed` — opponent air yards per target allowed (pbp).
4. `opp_pressure_rate` — opponent (sacks + QB hits) per dropback (pbp;
   hurries unavailable in nflverse pbp — see §0).
5. ~~`opp_target_concentration`~~ — DROPPED pre-freeze (§0): no keyless
   receiver-position derivation.
6. Own-QB context (frozen 002 Family I QB features) — tests whether QB quality
   modulates the matchup effect.

Frozen receptions matchup set: features 1–4 + 6 (5 features).

### 4b. Rush-attempt matchup features (trailing, opponent-side)
1. `opp_rush_epa_allowed` — opponent EPA per rush allowed (pbp).
2. `opp_rush_success_allowed` — opponent rushing success rate allowed (pbp).
3. `opp_stuff_rate` — opponent stuff/TFL rate vs expected (pbp).
4. `opp_early_down_rush_rate_faced` — how often opponents' foes run
   (tests game-script environment the defense creates).

Frozen rush matchup set: features 1–4 (4 features).

~~Availability-gated: defense-imposed 8+ box rate and run-front tendencies
have **no verified keyless opponent-side source** (NGS box data is
rusher-side). Same pre-freeze availability rule as §4a.~~
DROPPED pre-freeze (§0): no keyless opponent-side source.

## 5. Availability audit — COMPLETED pre-freeze (see §0)

The gate ran 2026-10-01 with no fitting and no locked-test computation.
Frozen spec lists only derivable features (§4a: 5 features; §4b: 4 features).

## 6. Win bar (MAE family, same as 003)

- ≥5% pooled relative MAE improvement (M1-matchup vs M0-matchup),
- ≥2% improvement in EACH locked-test season (2023, 2024),
- bootstrap 95% CI on the pooled improvement excludes zero.

All three prongs required. Failure on any prong = NULL (reported narrowly).

## 7. Sample requirements

Minimum 800 player-games per market on the locked test; fewer → experiment
does not run (same power logic as 011: an underpowered test is shelved,
not run-and-nullified).

## 8. What this experiment does NOT do

- Does not modify the frozen 003A/003B models or their production heads.
- Does not add matchup features silently to production on a pass —
  a pass produces a *recommendation package*, stopped for authorization,
  per the 003 protocol.
- Does not test generic opponent EPA (already failed in 002).
- No production changes regardless of outcome.

## 9. Reproducibility (to be filled at run time)

- Feature audit CSV, frozen scripts, seeds, fit-once discipline per 003.
- Bit-for-bit deployment verification required before any production use,
  per the 003A precedent.

---
*Drafted 2026-10-01 as the prepared follow-on to the Season-to-Date Audit.
Availability audit completed 2026-10-01 (no fitting). FROZEN 2026-10-01
per Cale's decision. Not run — awaiting Cale's explicit run authorization.
Once frozen, features, win bar, and evaluation protocol do not change based
on 2026 outcomes.*
