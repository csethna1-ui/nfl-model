# Feature Discovery Audit — REPORT

**Date:** 2026-09-29 · **Type:** read-only discovery (no models fitted, no validation evaluated, V1 untouched, vault locked) · **Experiment 006 live and unchanged**

## 1. What V1 actually uses (STEP 1)

Read from `scripts/03_ratings.py`, `04_backtest.py`, `05_metrics.py`, `07_update_weekly.py`:

| Component | Signals | Weight |
|---|---|---|
| ELO→margin (linear, fit 2018–20) | elo_diff (K=20, HFA 55 ELO ≈ 2.2 pts, MOV multiplier, ⅓ offseason regression) | 0.4 |
| EPA→margin (linear, fit 2018–20) | off/def EPA, pass/rush splits, success rate — team-level only, weekly EWMA α=0.25, 35% offseason regression | 0.5 |
| GBM (XGBoost, walk-forward expanding) | elo_diff, all EPA diffs, rest_diff, div_game, week | 0.1 |
| Context | rest differential, div_game flag, week number, home field via ELO | — |
| Injury | **None in the prediction.** `11_injury_adjust.py` only *voids* picks on unexpected QB Out/Doubtful (market-implied QB point values); it never adds signal | — |
| Weather | None in V1 (wind researched in market JSON; v2's wind finding was totals-only and v2 failed) | — |

**V1's information in one sentence:** season-to-date team outcome efficiency (ELO + EPA means + success rate) plus rest/division/week structure. It knows *how efficiently teams have played*. It knows nothing about *how they play* (tendencies, explosiveness shape, trench process), *who specifically is playing* beyond the QB void filter, or *special teams*.

## 2. External research: what the field actually claims (STEP 2)

Full citations in `source_references.md`. The pattern across independent projects is striking:

- **Convergent null on team-EPA modeling vs the close:** chmoses98 (encompassing regression 1.01 on spread, 0.03 on model), our Experiments 001–005, colemason6524's ablation — all agree a team-EPA model carries ~nothing beyond the line.
- **Convergent null on QB-form features:** our v2 (QB EPA/play + wind, failed walk-forward), howlscastle97 (per-QB EPA/dropback: held-out −0.0002 on ensemble, not shipped), colemason6524 (QB delta + CPOE: −0.02 MAE, market parity), wadefuller (ESPN QBR 0.79 corr with qb_epa, 0/4 metrics). Four independent nulls. **Do not re-run this family.**
- **Pressure is real signal but substitutive:** wadefuller — pressure rate ranked 41/XGB-real but displaced starter_pass_epa rather than adding. Note: his model *had* QB-EPA features; V1 does not, so the displacement concern is weaker here.
- **Luck-stripping doesn't help OOS:** dgrifka (2,761 games, split-half) — fumble recovery has zero team skill, yet neutralizing luck improved nothing out-of-sample.
- **ST is partly unobservable + structurally broken:** dgrifka — one spot per punt mixes flight and roll; kickoff return rate 0.25 → 0.33 → 0.74 across 2023–2025 (two rule breaks in two years).
- **The stated frontier:** "53–55% selective / +CLV vs openers; nothing public beats the close" (gesmith0606). Our project is consistent with the field, not behind it.

## 3. Data availability (verified 2026-09-29, all keyless)

| Source | Coverage | In-season 2026 | Pregame-safe |
|---|---|---|---|
| nflverse PBP (372 cols: epa, cpoe, air_yards, xpass/pass_oe, sacks, qb_hit, fumbles, punts/kicks, drives, series) | 1999+ | Yes (nightly) | Yes |
| Schedules (rest, div_game, roof, surface, temp, wind, QB names 100%) | 1999+ | Yes | Yes |
| PFR advstats weekly (pressure, drops, bad throws) | 2018+ | Yes (updating) | Yes |
| Snap counts | 2012+ | Yes (updating) | Yes |
| Rosters | 1999+ | Yes (weekly) | Yes |
| Injuries (timestamped) | 2009–2025* | Verify | Yes |
| FTN charting (motion, play action, blitz, contested, drops) | **2022+ only** | Yes (weekly) | Yes w/ date_pulled |
| Participation (time_to_throw, was_pressure, coverage) | 2016+; **2023+ post-season only** | **No** | Historical only |
| NextGen Stats weekly | 2016+ | Yes | Verify release timing |

\* nflverse injury source reported ending after 2024; 2025 needs verification on pull.

License note: FTN-sourced releases (participation 2023+, FTN charting) are CC-BY-SA 4.0 — attribution "FTN Data via nflverse" required wherever surfaced.

## 4. Tier ranking

**TIER 1 — genuinely different + feasible + timestampable + testable under current discipline:**
1. **Offensive strategy: PROE + early-down behavior + pace** — the most structurally absent dimension in V1. `xpass`/`pass_oe` ship in nflfastR PBP (verified locally); early-down/neutral pass rates and pace are simple PBP aggregations. No convergent external null against it.
2. **Explosiveness + EPA distribution shape** — explosive pass/run rates, EPA volatility, aDOT. V1 sees means and thresholds, not tails. Computable from local PBP today.
3. **Trench pressure allowed/created (PFR advstats)** — process signal (how often pressured) vs outcome (pass EPA). Weekly 2018+, in-season. wadefuller's substitution caveat applies to models with QB-EPA; V1 has none.

**TIER 2 — useful but limited:** QB starter continuity/familiarity; ST EPA (observability + rule-break caveats); drive/field position; OL/skill continuity via snap counts; FTN charting (2022+ only — breaks 2018–20 train window); participation time_to_throw/was_pressure (post-season only 2023+ — no live use); NGS aggregates (marginal uniqueness at team grain); aDOT standalone (fold into explosiveness).

**TIER 3 — redundant or convergent-null:** QB EPA/CPOE/recent-form (four independent nulls); matchup interactions (representation, not information; Exp 002 null); turnover-luck features (dgrifka: no OOS gain); travel/time-zone (wadefuller: 0/4, reverted); roof/surface/primetime for spreads (small, likely priced; wind precedent null).

## 5. Recommended candidates for investigation (at most three — none trained)

See `recommended_candidates.json` for full justifications. In brief:

1. **PROE / offensive strategy** — largest structurally-missing dimension; fully feasible.
2. **Explosiveness / EPA distribution** — tails V1 cannot see; fully feasible.
3. **Trench pressure (PFR)** — process-level line play; feasible; must clear the diversification bar (error corr <0.95), not just tell a good story.

**Explicitly not recommended:** any QB EPA/CPOE/form variant. The evidence is in; re-running it would be architecture fishing.

## 6. Most surprising gap

**V1 has no idea how a team plays — only how well its plays have worked.** PROE, early-down tendencies, pace, and explosiveness shape are all computable from data already on disk (the local 372-column PBP has contained `xpass`/`pass_oe` all along) and were never inventoried. Five experiments attacked *representations of efficiency*; none touched *play-calling and distribution shape*. Whether the market prices these is an empirical question — but unlike QB form, nobody has run the experiment yet.

## 7. Files

- `feature_inventory.json` — 12 categories × per-family A–K assessments
- `data_availability.json` — per-source coverage, cadence, pregame safety
- `source_references.md` — 17 sources with URLs and actual claims
- `recommended_candidates.json` — tiers + top-3 justifications
- `REPORT.md` — this file

**No Experiment 007 selected.** The next predictive experiment requires human review of this audit.
