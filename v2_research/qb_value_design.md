# Blocker 1 — Historical QB Value: design document

Date: 2026-09-29. Built: `scripts/37_v2_qb_value.py` → `data/v2/qb_value_pred.parquet`.
Scope: 2018–2022 only. Vault (2023–2025), Experiment 006 observations, and all
V1 code: untouched. **No model training, no fitted coefficients, no validation
evaluation anywhere in this work.**

## 1. Objective

A historically valid per-QB value, generated ONLY from games completed strictly
before the prediction week, at team × season × pred_week grain (mirrors script
35's walk-forward discipline). The value answers: "how good has THIS quarterback
been, on his own prior record," so the modeling stage can separate QB identity
from team strength.

## 2. Inputs and per-season feasibility (2018–2022)

| Input | Source | 2018 | 2019 | 2020 | 2021 | 2022 | Notes |
|---|---|---|---|---|---|---|---|
| qb_epa per dropback | PBP `qb_epa`, `qb_dropback` | ✓ | ✓ | ✓ | ✓ | ✓ | 100% nonnull on dropbacks; mean ≈ +0.09 EPA/db |
| pass-play split | PBP `pass` flag | ✓ | ✓ | ✓ | ✓ | ✓ | sacks count as pass plays (`pass==1`, `qb_dropback==1`) |
| **CPOE** | PBP `cpoe` | ✓ | ✓ | ✓ | ✓ | ✓ | **Completions only.** ~81–82% of pass plays nonnull in every season; every `complete_pass==1` play has non-null CPOE; incompletions have none. Component denominator = completions, not attempts |
| air yards | PBP `air_yards` | ✓ | ✓ | ✓ | ✓ | ✓ | ~84% of pass plays nonnull (spikes/throwaways null) |
| sack rate | PBP `sack` flag | ✓ | ✓ | ✓ | ✓ | ✓ | full |
| pressure response | PBP `qb_hit` + `qb_epa` | ✓ | ✓ | ✓ | ✓ | ✓ | `qb_hit` 100% populated, ≈13.8% of dropbacks; response = qb_epa/db on hit plays |
| QB rushing EPA | `rusher_player_name` + `qb_scramble` | ✓ | ✓ | ✓ | ✓ | ✓ | scrambles have NaN passer but named rusher; designed runs attributed via rusher name |
| times_pressured_pct | PFR `advstats_week_pass_*` | ✓ | ✓ | ✓ | ✓ | ✓ | 100% populated, 646–706 QB rows/season; PFR team agrees with PBP team on 98.95% of matched rows |
| QB identity | schedules `home/away_qb_name` | ✓ | ✓ | ✓ | ✓ | ✓ | 0% null, 2018–2022 |

**Cannot be built honestly:** per-play "qb_epa under pressure" — PBP 2018–2022
has no per-play pressure indicator (the `qb_hit` proxy above is the honest
substitute). Fitted multi-component composite weights (see §6, UNRESOLVED).

## 3. QB identity and carryover rules

- Prediction-time identity = **scheduled starter** (`qb_sched`, schedules
  `home/away_qb_name`; repo pregame convention inherited from script 33).
- Canonical QB key: last alpha token + "_" + first char of first token,
  suffixes (jr/sr/ii/iii/iv/v) stripped. Handles `K.Murray`, `C.J. Beathard`,
  `Patrick Mahomes`, `Gardner Minshew II` uniformly. Only observed collision is
  same-person suffix variants (`Gardner Minshew` / `Gardner Minshew II` → one
  key — correct).
- **Carryover:** history is keyed by QB, team-agnostic. A mid-season team
  change travels with the QB (e.g. Matt Ryan's 2022 IND value uses his ATL
  history; Marcus Mariota's 2022-wk1 ATL value uses his prior-team games).
  65 pred rows (2018–2022) have `qb_team_changed == 1`; `qb_prior_teams`
  records how many distinct teams contributed.
- Schedule data-entry errors found and handled deterministically (not fitted):
  `herbery_j` ("Justin Herbery" typo) → aliased to `herbert_j`; `murray_t`
  ("Taysom Kyler Murray", ambiguous) → left unmatched → NaN, logged.

## 4. Cold start and backups

Value exists iff **≥ 4 prior games AND ≥ 40 prior dropbacks** (stated rules, not
fitted); otherwise NaN with `qb_cold_start = 1`. Backups degrade the same way:
small-sample recency-weighted mean, NaN below the minimum — no fitted
imputation. The existing `qb_backup_flag` (script 33/35) carries the
starter-vs-backup identity signal; the modeling stage decides how to handle
NaN (replacement-level prior is UNRESOLVED, §7).

Coverage 2018–2022: 2,744 pred rows; 2,434 (88.7%) have a value; 310 cold-start
rows (rookies, first games of the 2018 window, one-off emergency starters).

## 5. Deterministic composite — exact formula

Games ordered most-recent-first, g = 1..G. Decay weights (stated parameter,
NOT fitted):

    w_g = 0.5 ** ((g - 1) / HALF_LIFE),  HALF_LIFE = 8 games

Volume enters through the per-dropback denominators (weighting by dropbacks as
well would square-count volume, since the numerators are game totals).

Primary feature:

    qb_value_historical = Σ_g w_g · epa_sum_g / Σ_g w_g · n_db_g
                        = recency-weighted qb_epa per dropback

Components (same weights; each Σ w·numerator / Σ w·denominator):

- `qb_pass_epa_db_rw`  = Σw·pass_epa / Σw·n_pass        (pass-play qb_epa/db)
- `qb_cpoe_rw`         = Σw·cpoe_sum / Σw·n_cpoe        (mean CPOE, completions)
- `qb_sack_rate_rw`    = Σw·n_sack / Σw·n_db
- `qb_hit_epa_db_rw`   = Σw·hit_epa / Σw·n_hit          (pressure response)
- `qb_rush_epa_db_rw`  = Σw·rush_epa / Σw·n_db          (QB rushing contribution)
- `qb_pressured_pct_rw`= Σw·n_db·pressured_pct / Σw·n_db (PBR pressure rate; see §7 lag note)

Sample metadata: `qb_value_n_games`, `qb_value_n_dropbacks` (unweighted),
`qb_prior_teams`, `qb_team_changed` (NaN when cold start).

Sanity (descriptive, not evaluative): `qb_value_historical` mean 0.066,
median 0.076, IQR −0.009…+0.149 EPA/db; one row independently recomputed from
raw PBP matches to 6 decimals.

## 6. Refined filter — priority ranking (correlation is priority, NOT exclusion)

Low correlation with the existing latent team-strength signal is a PRIORITY
criterion, not a hard filter. Nothing was dropped for being correlated.

1. `qb_hit_epa_db_rw` — pressure response; most orthogonal to team EPA; a
   QB-specific trait the team averages wash out. Highest priority.
2. `qb_cpoe_rw` — accuracy skill partly orthogonal to team outcomes; high
   priority. (Caveat: completions-only denominator; already partially flows
   into qb_epa — see §7.)
3. `qb_sack_rate_rw` — decision-making under pressure, but partly OL-driven;
   medium priority.
4. `qb_rush_epa_db_rw` — scheme-dependent; medium-low priority.
5. `qb_value_historical` / `qb_pass_epa_db_rw` — WILL correlate with team EPA
   (good QBs play on good teams) but add conditional information: identity-level
   skill vs the team's average, and starter↔backup replacement deltas. Kept
   deliberately; ranked on incremental value, not excluded on correlation.
6. `qb_pressured_pct_rw` — largely OL/scheme-driven; lowest priority as a *QB*
   value; also Tuesday-lag restricted (§7).

## 7. Quarantine note — `qb_value_poll`

`qb_value_poll` (2026-anchored oddsmaker poll, `data/qb_point_values.json`) is
**quarantined**: script 37 does not read it; it remains a placeholder only and
must not enter historical, vault, or live-2026 work. Tag patch in
`v2_research/tag_updates_qb.json` marks it QUARANTINED and superseded by
`qb_value_historical` for 2018–2022.

## 8. UNRESOLVED (documented, not fitted around)

1. **Multi-component composite weights.** An honest single number combining
   EPA + CPOE + sack + pressure + rushing needs fitted coefficients — not
   authorized. Equal/transparent weighting was rejected: it is arbitrary and
   double-counts (CPOE/pressure/sack outcomes already flow into qb_epa).
   `qb_value_historical` (rw EPA/db) is the deterministic primary value; the
   components are emitted so a future *authorized* experiment can fit weights
   on a proper validation window.
2. **Cold-start / backup NaN handling.** A replacement-level prior for
   backups/rookies is a modeling-stage decision (needs an assumption or a
   fit); left as NaN here.
3. **PFR Tuesday lag.** `times_pressured_pct` is published post-game; at a
   Tuesday prediction snapshot the prior week may not be refreshed (blocker 3).
   `qb_pressured_pct_rw` is Friday-safe; the modeling/production stage must
   exclude it from Tuesday-snapshot features.
4. **qb_sched pregame assumption.** Inherits script 33's convention (schedule
   QB names treated as pregame-known, not timestamped). Mid-week starter
   changes are handled downstream by the script-11 stale-news filter in the
   Friday production flow.
5. **Name-key collisions.** Only same-person suffix variants observed
   2018–2022; cross-person collisions (same last name + first initial at QB)
   would silently merge — none found, risk documented.

## 9. Output spec

`data/v2/qb_value_pred.parquet` — 2,744 rows × 17 cols:
`team, season, pred_week, qb_sched, qb_key, qb_value_historical,
qb_pass_epa_db_rw, qb_cpoe_rw, qb_sack_rate_rw, qb_hit_epa_db_rw,
qb_rush_epa_db_rw, qb_pressured_pct_rw, qb_value_n_games,
qb_value_n_dropbacks, qb_cold_start, qb_prior_teams, qb_team_changed`.
Grain joins to `team_features_pred` on (team, season, pred_week); week-1 rows
are included (valid for veterans via prior-season history; team_features_pred
starts at game 2, so they left-join harmlessly).
