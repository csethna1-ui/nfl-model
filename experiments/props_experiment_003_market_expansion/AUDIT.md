# Props Experiment 003 — Market Expansion Audit

**Date:** 2026-10-01
**Type:** RESEARCH AUDIT ONLY. No model building, no fitting, no tuning, no
predictions. Read-only investigation of data availability and market structure.
**Status:** AUDIT COMPLETE — awaiting Cale's selection of 2–4 markets for
formal (preregistered) experiments.

## 0. Research philosophy carried forward

Experiments 001/002 established the discipline this audit serves: frozen
protocols before any locked-test computation; train 2018–2020 / dev
2021–2022 / locked test 2023–2024; a ≥5% relative-MAE win bar (002 §9);
honest nulls reported as successful experiments; **no historical prop lines
exist — projection error vs actuals only** (001/002 precedent). Any market
selected from this audit will get its own frozen protocol before it is
touched. Nothing in this document selects, fits, or evaluates a model.

## 1. Line availability: what exists today

### 1a. Current-season lines (Bovada public coupon API, keyless)

`scripts/30_pull_prop_lines.py` pulls Bovada's unauthenticated coupon API
(`preMatchOnly=true`). Each pulled line records `{player, market, line,
source, captured_at}` — **timestamped at capture**, satisfying the timing
discipline for 2026 paper-tracking. The coupon offers **only upcoming games**:
no historical seasons, no backfill. Market inventory from the live coupon
(pulled 2026-10-01, Week 5 slate):

| Display group | Player markets found (main lines) | Count |
|---|---|---|
| Passing Props | Total Completions, Total Passing Attempts, Total Passing TDs, Total Interceptions, Longest Pass Completion (+ alternates) | 12/12/16/12/2 |
| Receiving Props | Total Receptions (+ alternates), Longest Reception, 10+/15+/20+/30+ yard reception yes/no | 55 / 11 / 1 each |
| Rushing Props | Total Rush Attempts (+ alternates), Longest Rushing Attempt | 2 / 4 |
| Rushing Yards group | QB rushing yards lines present for mobile QBs (e.g. Maye, Daniels-era names, Prescott) | 28 players |
| TD Scorer Props | Anytime Touchdown Scorer, First TD Scorer, 2+ TDs, 3+ TDs | 13 / 8 / 8 / 1 |
| Defensive props | **NONE — no tackles, sacks, QB hits, INTs, PD** | 0 |
| Combined props | **NONE — no rush+receiving, pass+rush, etc.** | 0 |

Two coverage notes: (i) **Total Rush Attempts is thin** — 2 lines vs 55 for
receptions; Bovada barely posts this market, and coverage may vary by week.
(ii) Counts above are per-slate snapshots; the script currently parses only
the three yardage markets and would need extending for the new markets.

### 1b. Historical lines: none keyless

- **Bovada coupon:** current slate only. No history.
- **The Odds API:** historical player props since May 2023 at snapshot
  granularity — **paid ($29–99/mo), key-gated**. Fails the keyless
  constraint; noted for completeness, not recommended.
- **Third-party archives (GitHub):** FanDuel prop-history CSVs
  (receptions, pass yards) circulate in public repos, but provenance is
  unverified and at least one documented case carries week-labeling bugs
  (2023 off-by-one) and odds-format inconsistencies. Not a foundation for a
  preregistered experiment without a full validation build.
- **nflverse:** does not ship prop lines.

**Verdict:** the 001/002 precedent stands — formal experiments evaluate
projection error vs actuals; Bovada provides timestamped current-season lines
for paper-tracking and eventual market comparison. A market with no Bovada
line can still be *modeled*, but the "does an edge exist" question cannot be
answered against a market.

## 2. NGS / tracking-data availability: verified honestly

Cale's premise ("the tracking ecosystem is richer now") was checked
empirically via `nfl_data_py.import_ngs_data`, which works **keyless today**.

- **Available 2016–2026** (covers train/dev/test), three stat types:
  - *receiving:* avg_cushion, avg_separation, avg_intended_air_yards,
    percent_share_of_intended_air_yards, receptions, targets,
    catch_percentage, yards
  - *passing:* avg_time_to_throw, avg_completed_air_yards,
    avg_intended_air_yards, avg_air_yards_differential, aggressiveness,
    max_completed_air_distance, avg_air_yards_to_sticks, attempts
  - *rushing:* efficiency, percent_attempts_gte_eight_defenders,
    avg_time_to_los, rush_attempts, rush_yards, avg_rush_yards,
    rush_touchdowns
- **NOT in the keyless feed:** routes run / route participation (002 already
  documented: no local source), coverage/man-zone splits, expected
  completion % / CPOE (those come from nflverse pbp's `cpoe`, not NGS),
  xYAC, or any defensive tracking (no tackling/pressure/coverage NGS feed
  here). "Expected rushing yards" exists only implicitly inside the
  `efficiency` metric, not as a raw column.
- **As-of discipline:** NGS weekly releases are post-game; trailing
  (strictly prior weeks) use is timestamp-safe — the same rule 002 applied
  to `rq_ngs_separation`.
- **Defense-side tracking gap is real:** pass-rush/pressure/tackling
  *tracking* is not keyless-available. What exists is PFR advanced stats
  (weekly, local 2018–2026): `def_tackles_combined`, `def_sacks`,
  `def_times_hitqb`, `def_pressures`, `def_missed_tackles`,
  `def_times_blitzed` — box-score-derived, not tracking.

**Bottom line:** the keyless NGS feed is a genuine incremental feature
source for the *offensive* candidate markets (separation, intended air
yards, time-to-throw, aggressiveness were never tested as predictors in
001/002 — 002's NGS test died with the M12 gate). It does not unlock the
defensive markets.

## 3. Outcome modelability from existing data

All outcomes below are derivable without new data buys:

| Outcome | Source | Notes |
|---|---|---|
| Receptions / targets | nflverse weekly player_stats | + target_share, air_yards_share, wopr |
| Rush attempts | player_stats `carries` | |
| Pass attempts / completions | player_stats `attempts`, `completions` | |
| Anytime TD (binary) | `rushing_tds` + `receiving_tds` > 0 | opportunity features already in-house: `trail_rz_targets_ewma`, `trail_rz_carries_ewma`, `ruq_goal_line_carries`; end-zone targets derivable from pbp (`air_yards >= yardline_100`) |
| Longest reception / rush | pbp: max `yards_gained` per player-game on receptions/carries | verified: 2024 median longest rec 14.0, p90 33.0 |
| Tackles (+assists) | PFR advstats `def_tackles_combined` (weekly, 2018–2026) | name-matching required (002 precedent); snap-join for role threshold |
| Sacks | PFR advstats `def_sacks` | sparse: 2,630 sack-rows vs 15,894 defender-weeks (2023–24) — supports deprioritizing |

## 4. Per-market audit table

Sample sizes are 2023–2024 outcome player-games (the locked-test window
001/002 used), under 001-style role thresholds unless noted.

| # | Market | Current lines (Bovada) | Historical lines (keyless) | Outcome n (23–24) | Timestampable lines | Distribution | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | **Receptions** | Yes — 55 (widest non-yardage coverage) | None | ~3,625 | Yes (captured_at) | Count, mean ~4, Poisson-ish, stable | **RECOMMEND — strongest candidate** |
| 2 | **Rush Attempts** | Thin — 2 lines | None | ~1,528 | Yes | Count; zero-inflated below role threshold (≥5 carries keeps it clean) | **RECOMMEND — flag thin live lines** |
| 3 | **Pass Attempts** | Yes — 12 | None | ~1,010–1,190 | Yes | ~33±9, stable, game-script driven; a *volume* target, not redundant with 002's yardage work | **RECOMMEND** |
| 4 | **QB Completions** | Yes — 12 | None | ~1,010–1,190 | Yes | attempts×rate; r≈0.95+ with attempts — the incremental question is completion% | **FOLD INTO #3 hierarchically** (attempts → completions), not standalone |
| 5 | **Anytime TD** | Yes — 13+ | None | 6,235 pg, **1,830 TD events**, base rate 0.294 | Yes | Binary — needs Brier/log-loss + calibration, **separate model family** (Cale's own framing) | **RECOMMEND — own protocol** |
| 6 | **Longest Reception** | Yes — 11 | None | ~3,400 | Yes | Extreme-value (max of ~4 draws); intrinsically high-variance | **DEPRIORITIZE — noise-dominated** |
| 7 | **Longest Rush** | Yes — 4 | None | ~1,500 | Yes | Extreme-value (max of ~13 draws) | **DEPRIORITIZE — noise-dominated** |
| 8 | **Tackles (+assists)** | **No — zero defensive props on Bovada** | None | ~15,900 defender-weeks (role-thresholded ~6–8k) | N/A | Count, stable for every-down players; **official-scorer bias** (home/crew effects) is a documented confounder | **HOLD — modelable but no market to test against** |
| — | Combined props (rush+rec yds, etc.) | **None** | None | Derivable | N/A | Joint-distribution question; a modeling extension, not a market expansion | **NOT RECOMMENDED for formal experiment** |
| — | Sacks / QB hits / INTs / PD | None | None | Sparse (sacks: 2,630 rows) | N/A | Rare-event, noisy | **DEPRIORITIZE** (agrees with Cale) |
| — | First TD / 2+ TDs / exact score | Yes (First TD 8, 2+ TDs 8) | None | Rare, path-dependent | Yes | Extremely noisy | **DEPRIORITIZE** (agrees with Cale) |

## 5. Minimum-sample rule (proposed, with reasoning)

Following 002's precedent (pooled ≥700 pass / ≥1000 rush / ≥2500 receiving):

- **Count targets (receptions, rush attempts, pass attempts, completions,
  tackles):** pooled n ≥ the 002 analogue for the population —
  receptions ≥2,500; rush attempts ≥1,000; pass attempts/completions ≥700;
  tackles ≥2,000 *with* a defensive-snap role threshold (the raw 15.9k
  includes part-timers; median tackles across all rows is only 3.0).
  Reasoning: count outcomes with these n give MAE standard errors small
  enough to resolve a 5% relative improvement — the same power logic as 002.
- **Binary target (anytime TD):** pooled ≥3,000 player-games **AND** ≥500 TD
  events. Reasoning: the 10-events-per-parameter rule for probability
  models; with ~6 candidate opportunity features, 500 events is the floor
  for stable calibration. (We have 1,830 — clears comfortably.)
- **Extreme-value targets (longest rec/rush):** same n as the count
  analogues, **plus** an honest power caveat — the irreducible variance of
  a max-of-draws statistic means the bar may be unreachable even with
  n=3,400. If tested, the protocol should prespecify this.

All recommended markets clear their minimum on 2023–2024 alone.

## 6. Recommendation: 4 markets for formal experiments

**1. Receptions — the strongest candidate.** Largest outcome sample
(~3,625), most stable distribution of the new targets, widest current line
coverage (55), and every ingredient already in-house: targets, target
share, wopr, snap share, plus genuinely untested NGS features
(separation, intended air yards, cushion — 002's NGS test never ran).
Cale's hierarchy (routes→targets→receptions→yards) is the right structural
bet, and it converts the existing receiving-yards engine into a process
model rather than a parallel number. Lowest risk of the four.

**2. Anytime TD — the biggest missing market, as its own experiment.**
13+ live lines, 1,830 TD events at a 0.294 base rate, and the opportunity
features are already built (`trail_rz_targets_ewma`,
`trail_rz_carries_ewma`, `ruq_goal_line_carries`). It needs its own
protocol because the target is binary: Brier score / log-loss /
calibration instead of MAE, and the win bar must be restated in
probability terms (a ≥5% MAE bar does not transfer). This is the one
recommendation that changes the evaluation machinery — flag it in the
protocol.

**3. Rush attempts — the clean opportunity target.** n≈1,528, well-behaved
above the role threshold, and conceptually the "opportunity half" of the
rush market where 002 found its only directional signals (M3/M6 −0.6%/−0.7%
on rush yards). If volume is more predictable than efficiency, this is
where it shows. Caveat for the protocol: live line coverage is currently
thin (2 lines) — the experiment is valid as projection research per the
001/002 precedent, but paper-tracking will be sparse until coverage
improves.

**4. Pass attempts, with completions as a hierarchical extension.**
n≈1,100, stable ~33±9 distribution, 12 live lines — and crucially *not
redundant* with 002, which tested efficiency/context features for passing
*yards*. Attempts is a volume target driven by game script, team pass
rate, and QB role. Completions should not be a standalone experiment
(r≈0.95+ with attempts); Cale's hierarchy (expected plays → attempts →
completion probability → yards) is the right design — test whether
completion% adds anything *given* attempts.

## 7. Where evidence overrides the queue order

- **Longest reception/rush (queue #6):** deprioritized on distributional
  grounds, not just queue position. A max-of-draws statistic concentrates
  variance in a single play; the modelable component (ADOT, deep-target
  rate) is small relative to the luck component. An honest protocol would
  likely conclude "unresolvable" — which is itself an answer, but a poor
  use of the next experiment slot.
- **Tackles (queue #7, Cale "really interested"):** the override. The
  outcome is modelable and the sample is large, but **no sportsbook in our
  keyless source posts defensive props** — so there is no market to
  paper-track and no market-efficiency question to answer. A projection-only
  tackles experiment is legitimate research, but it cannot serve the
  program's goal (determining whether an edge exists vs a market). **Hold
  until a line source is identified;** do not spend a formal experiment
  slot on it now.
- **Completions (queue #4):** folded into #3 rather than standalone —
  near-collinearity with attempts makes a separate experiment mostly a
  re-test of the same signal.
- **Combined props:** no lines exist anywhere keyless; the
  joint-distribution question is real but it is a *modeling* extension for
  after the marginal markets are built, not a market-expansion experiment.

## 8. Top findings (summary)

1. **No historical prop lines exist keyless, for any market.** The Odds API
   has them (paid/key-gated, May 2023+); third-party GitHub archives are
   provenance-unverified. Formal experiments continue under the 001/002
   precedent: projection error vs actuals, with Bovada's timestamped
   current-season lines for paper-tracking.
2. **Bovada's current menu covers 6 of 7 queue markets** — everything
   except tackles/defense, which has zero coverage. Rush-attempt lines are
   notably thin (2 vs 55 for receptions).
3. **NGS is genuinely available keyless (2016–2026)** and genuinely useful
   for the offensive markets — separation, intended air yards, time-to-throw,
   aggressiveness were never tested in 001/002. But it does **not** include
   routes, coverage splits, xYAC, or defensive tracking; the "richer
   ecosystem" claim needs those asterisks.
4. **All four recommended markets clear minimum-sample bars on 2023–2024
   alone.** The binding constraints are distributional (longest-play noise,
   TD binarity needing its own metric), not sample size.
5. **Recommended: Receptions → Anytime TD (own protocol) → Rush Attempts →
   Pass Attempts (+ Completions hierarchically).** Tackles held for lack of
   a market; longest-play markets deprioritized as noise-dominated;
   combined props deferred to modeling work, not market expansion.
