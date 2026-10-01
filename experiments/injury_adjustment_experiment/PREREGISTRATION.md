# PREREGISTRATION — Phase 2: Full-Roster Injury Adjustment Experiment

**Status: PROTOCOL PHASE — NOT APPROVED. No model has been fit. No locked-test
data has been read, listed, or computed on. This protocol returns to Cale for
approval/freezing BEFORE any train/dev fitting or locked-test evaluation.**

Branch: NFL spread-margin model (V1) + full-roster injury/availability
information. Separate from Experiment 001 (player props), Experiment 006
(information timing), the PFT corpus branch, and Phase 1 production plumbing.
V1's prediction math is untouched by this experiment; the injury layer is a
strictly additive, separately-frozen adjustment.

---

## 1. Research question and protocol overview

**Question:** Does adding player availability/injury information across the
entire roster improve the frozen V1 game-margin prediction, when restricted
strictly to information knowable by the Friday 18:00 CT prediction cutoff?

**Design (one paragraph):** For each regular-season game, compute the frozen
V1 walk-forward margin (V1 code and weights frozen, predictions generated
without using the game's outcome). Separately, build injury features from the
nflverse injury feed using only rows whose `date_modified` precedes the
Friday 18:00 America/Chicago cutoff of game week. Fit a small,
preregistered set of additive adjustment models
`candidate_margin = v1_margin + adj(injury_features)` on 2018–2020
(train), select among them on 2021–2022 (dev), freeze, then evaluate exactly
once on the 2023–2025 locked test against a preregistered win bar. Primary
metric is MAE; ATS is a secondary diagnostic only.

**Why this experiment is allowed under the research freeze:** the freeze
(2026-09-29) closed "better math on the same free pregame information." Full-
roster injury/availability information is a *new information source* not
present in V1's feature set (V1 has zero injury inputs; Experiment 005 tested
only non-QB counts with a crippled train period and failed). V1's math,
weights, and architecture remain frozen; the injury layer is additive and
cannot silently become a V1 feature.

**Relationship to Experiment 005 (non-QB availability, NULL):** 005 tested
30 signed non-QB injury-count features with Ridge(α=1.0) on a 2021→2022
cross-fit (frozen-V1 margins did not exist pre-2021 in its dataset) and
failed every gate (candidate 10.077 vs V1 10.042, error corr 0.985, unstable
cross-fold coefficients). Phase 2 differs in four preregistered ways:
(1) all positions **including QB**; (2) a real train period (2018–2020) with
walk-forward V1 margins extended back to 2019; (3) role/snap-share-weighted
specifications, not just raw counts; (4) the timing-sanity audit below, which
005 did not run. A second null here is informative, not redundant.

---

## 2. Candidate injury specifications (A–E)

All candidates share the form `candidate_margin = v1_margin + adj`, where
`v1_margin` is the frozen walk-forward V1 prediction and `adj` is the learned
injury adjustment. The target for every learned layer is the V1 residual
`r = actual_margin − v1_margin` (home-margin convention, same as V1).
**No hand-assigned point values anywhere** — no "QB OUT = −6", no manual
severity weights, no intuitive penalties. Anything learned is learned on
train (2018–2020) only, then frozen.

**Position groups (locked, reused from 005 — covers all feed positions):**

| Group | Positions |
|---|---|
| QB | QB |
| OL | C, G, T |
| SKILL | RB, WR, TE, FB |
| FRONT7 | DE, DT, LB |
| DB | CB, S |
| ST | K, P, LS |

**Designation encoding (locked):** `Out`, `Doubtful`, `Questionable` each get
their own feature — no assumed severity ordering. Rows with null
`report_status` (practice-only entries) are excluded.

**Feature sign convention (locked):** all features are signed from the home
perspective: `X = away_team_value − home_team_value` (positive = away team
more injured → favors the home margin).

### Candidate A — Position-based availability adjustments
18 signed features: 6 position groups × 3 designations, each the count of
timing-qualified injured players (`date_modified < T`, §4) on the team for
that game-week. `adj_A = Ridge(α=1.0, fit_intercept=True)` predicting `r`.
α=1.0 is pre-declared (same as 005, for comparability); no tuning.

### Candidate B — Player-impact / snap-share-weighted adjustments
6 signed features: for each team-game, the sum of **trailing snap shares** of
timing-qualified OUT / DOUBTFUL / QUESTIONABLE players, split by unit
(offense vs defense). Snap share for a player = mean of `offense_pct` (or
`defense_pct`) over the player's games in the trailing 4 weeks, strictly
before game week (from `nfl_data_py.import_snap_counts`; missing history →
weight 0, documented). `adj_B = Ridge(α=1.0, fit_intercept=True)` on `r`.
Tests whether weighting by how much the player actually plays beats raw
counts. Position-agnostic except for the offense/defense split.

### Candidate C — Starter / expected-snap availability model
Expected starters are defined **from data only**: the 11 players with the
highest trailing offensive snap% and the 11 with the highest trailing
defensive snap% on each team, computed strictly pre-week (11 starters per
unit is structural, not tuned). 2 signed features: the fraction of expected-
starter snaps missing to timing-qualified OUT/DOUBTFUL injuries, offense and
defense separately
(`missing_starter_snap_pct_off`, `missing_starter_snap_pct_def`).
`adj_C = OLS` (2 features; no regularization hyperparameter) on `r`. Tests
whether it is specifically *starter* availability that matters.

### Candidate D — Aggregate offensive/defensive injury burden
2 signed features: counts of timing-qualified OUT + DOUBTFUL players on
offense vs defense per team-game. Questionable is **excluded by pre-declared
rule** (tests the hypothesis that only hard designations carry signal).
`adj_D = β_off·burden_off + β_def·burden_def`, β fit by OLS on `r` (train).
The most parsimonious candidate: two coefficients, no regularization.

### Candidate E — Combined injury model
**Primary E = equal-weight average of the frozen A–D adjustments**
(`adj_E = (adj_A + adj_B + adj_C + adj_D)/4`). No learned weighting in the
primary — this mirrors the Experiment 001 Model D amendment Cale approved.
An **E-variant** with weights learned on dev (constrained least squares on
dev residuals, weights ≥ 0, frozen before the locked test) is reported
separately and **cannot replace** the preregistered equal-weight E. The
locked test never decides the ensemble.

### Multiple simultaneous injuries (deliverable 8)
Within a team-game, injuries are **additive** — no interaction terms
(interactions would be an untuned search dimension). Across teams, features
are signed away−home as above. No cap on counts (the maximum observed burden
is reported as a diagnostic, not tuned). This is pre-declared, not selected.

### Starter/role importance (deliverable 9)
Determined from data only:
- **B:** trailing snap share (continuous, pre-week).
- **C:** top-11 snap-share starters per unit (discrete, pre-week).
- Depth-chart `position` fields are NOT used for role (the weekly-roster
  `depth_chart_position` is a position slot, not a depth rank — verified
  2026-09-30).
- `data/qb_point_values.json` (2026 market-implied QB values) is **reference
  only**: it may be used after the fact to sanity-check the *sign* of learned
  QB coefficients, never as a model input (it is anachronistic for
  2018–2025 and would leak market information into the layer).

---

## 3. Historical information sources (exact)

| Source | Use | Access |
|---|---|---|
| `nfl_data_py.import_injuries` (2018–2025) | Injury rows: team, week, position, player, `report_status`, `date_modified` | Keyless |
| `nfl_data_py.import_snap_counts` (2018–2025) | Trailing snap shares for B and C role weights | Keyless |
| `nfl_data_py.import_schedules` (2018–2025) | Kickoff times (cutoff/exclusion logic) | Keyless |
| Frozen V1 walk-forward margins (§6) | `v1_margin` baseline; residual target | Repo-internal |
| PFT corpus | **Secondary only** (§4) — never in the primary pipeline | Pending verdict |

Explicitly excluded: market spreads/lines (the layer never sees them),
`practice_status` as a model feature (timing unverifiable in the weekly
snapshot — carried as a descriptive field only, §5), `qb_point_values.json`
as input (reference only, §2), any 2026 production files.

---

## 4. Information-timing methodology

**Prediction timestamp:** `T(game)` = Friday 18:00 America/Chicago of the
game's week — the same cutoff as production. Games kicking off at or before
T (Thursday games and any pre-Friday kickoffs) are **excluded** from the
experiment. Regular season weeks 1–18 only.

**Inclusion rule:** an injury row qualifies for game-week *w* iff
`date_modified < T(game)`, compared in UTC. This is the same hard filter
Experiment 005 used — but Phase 2 adds a validation step 005 lacked.

**Timing-sanity audit (required BEFORE any fitting):** the build script must
report on 2018–2022 injury data:
1. Share of rows with null `date_modified` (→ excluded, counted).
2. Share with `date_modified` after the player's week-*w* kickoff
   (post-game corrections — excluded by the filter regardless; report share).
3. Share with `date_modified` in `(T(game), kickoff]` — the Friday-evening/
   Saturday news window the primary filter excludes; this share measures the
   information the experiment deliberately leaves out.
4. A manual spot-check of 50 random player-weeks confirming `date_modified`
   precedes the week's final injury-report publication.

**Why the audit is non-negotiable:** the Phase 1 audit (2026-09-30) found the
2026-season feed has NO `date_modified` (KeyError), while 2018/2020/2021
pulls do carry it. The field's provenance differs by vintage. If the audit
shows the field is unreliable for a season or player subset (>20% null, or
implausible clustering), those injuries are **excluded from the primary
analysis** and reported in a labeled "timing-unverified" sensitivity
analysis — never assumed known. Per Cale's lock: status tells you what the
feed reports, not when the market learned it. The experiment tests whether
*report-available* injury information adds predictive value over V1; it makes
no claim about market knowledge timing.

**PFT first-reported timing (secondary layer only):** after the PFT corpus
verdict (2026-10-01): if PFT passes as a timing layer, a secondary analysis
re-runs the dev-selected candidate on the PFT-covered injury subset using
first-reported time < T as the inclusion rule, and reports whether the
verdict changes. If PFT fails (archive), this analysis is not run. PFT never
enters the primary pipeline and never moves the primary cutoff earlier.

**No Sunday/final statuses:** any row with `date_modified ≥ T(game)` is
dropped by construction — including game-day inactives (~90 min pre-kickoff),
which postdate the Friday prediction by design.

---

## 5. Missing-data / exclusion rules

- Team-game with no qualifying injury rows → all injury features zero. No
  imputation.
- Player with no trailing snap history (rookie debut, no prior games) →
  snap weight 0 in B; excluded from C's starter pool (cannot be an "expected
  starter" without history). Documented, not imputed.
- `report_status` null → row excluded (practice-only entry).
- Position not in the group mapping → excluded and logged (mapping covers all
  16 observed feed positions; any new value fails loudly, not silently).
- Postseason weeks (19+) → excluded (V1 production scope is regular season).
- Seasons/teams with <90% of games having at least one injury row in the feed
  → flagged in the audit; if a whole season is missing, it is excluded and
  reported (not silently zero-filled).
- `practice_status`: excluded as a model feature (timing unverifiable —
  the weekly snapshot carries one final practice status per player-week with
  no within-week timestamp). Documented as a limitation and future-work item,
  not used.

---

## 6. Train / dev / test boundaries

- **Train: 2018–2020** — all injury-layer fitting (Ridge/OLS coefficients).
- **Dev: 2021–2022** — candidate selection only (which candidates clear the
  bar; E-variant weights). No fitting on dev except the E-variant weights.
- **Locked test: 2023–2025** — evaluated **exactly once**, after Cale
  re-confirms the frozen candidates. No iteration on test results.
- **2025 stays locked.** It is part of the test, never tuning.
- **V1 baseline provenance:** `v1_margin` must be walk-forward out-of-sample
  for every game in the experiment. The existing backtest loop starts at
  2021; the experiment build script extends the **frozen** V1 pipeline
  (identical code, identical hyperparameters — asserted in-script) to start
  predictions in 2019, with 2018 as the ratings/fit burn-in (ELO starts all
  teams at 1500). 2021–2025 reuse the existing frozen backtest margins; the
  build script recomputes them and asserts equality to 1e-9 as a regression
  check. Reproducing frozen V1 on an earlier window is not modifying V1.

---

## 7. Primary metric and the win bar

**Primary metric:** MAE of predicted home margin vs actual home margin,
`candidate` vs `frozen V1`, on the locked test.

**Proposed win bar (ALL must hold — flagged as Cale's decision, §7.1):**
1. Pooled 2023–2025: **MAE reduction ≥ 0.15** vs frozen V1.
2. The 95% **paired game-level bootstrap CI** of the MAE difference
   (10,000 resamples, seed 42) **excludes zero**.
3. **No season regresses**: 2023, 2024, 2025 each within +0.05 of V1 (no
   one-season blip carrying a pooled win).
4. **Injury-game subset** (games with ≥1 timing-verified OUT/DOUBTFUL on
   either team) improves by **≥ 0.10** — the effect must come from games
   where the layer actually fires.
5. **Non-injury-game subset** regresses by **≤ 0.05** — the layer must not
   add noise where it has nothing to say.

**Secondary diagnostics (no bar):** ATS% at |edge| ≥ 3.0 (V1 vs candidate);
RMSE; calibration slope; coefficient-stability check (fit A/B on 2018–2019
vs 2020 and report sign flips — the failure mode that killed 005);
broad-vs-concentrated analysis (share of total MAE improvement from the top
5% of game-level improvements; >50% from ≤5% of games is disclosed as
concentrated, a mechanism-falsification signal).

**Minimum-n:** pooled locked test ≥ 700 games; per-season ≥ 150 games.
2023–2025 regular seasons contain ~816 games pre-exclusions — clear with
margin. Underpowered subsets are labeled, not gated.

### 7.1 Why 0.15 (for Cale's decision)
Experiment 001's 5% bar would be ~0.51 MAE points here — unrealistic for an
additive layer on a 10.19-MAE baseline, and Cale flagged it as such. 0.15 is
~1.5% relative, ~4× the noise scale 005's candidate moved (±0.035), and ~1/3
of the ~0.44 market–V1 gap: big enough to matter, small enough to be
plausible. Alternatives: 0.10 (more permissive) / 0.20 (closer to a third of
the gap with margin). **Cale sets the number before freezing.**

---

## 8. Mechanism hypotheses (recorded as hypotheses, NOT expectations)

> "Later-arriving full-roster availability information — who is actually
> playing, weighted by role — contains signal about game margins that frozen
> V1's team-strength ratings do not capture."

**Support:** a candidate clears the bar; improvement concentrates in the
injury-game subset; QB-OUT games show the largest residual corrections;
the effect holds across all three test seasons; train-fold coefficients are
stable in sign.

**Falsification:** pooled null; improvement driven by a handful of games
(concentration flag); gains appear only in non-injury games (overfit, not
mechanism); coefficient sign flips across train folds (the 005 failure mode);
the dev-selected candidate fails on the locked test while a non-selected
candidate "would have" won (selection noise — reported, not acted on).

---

## 9. Leakage audit plan

The build script must assert each of these; the locked-test script re-asserts
test-relevant ones. Every check logs PASS/FAIL with counts.

| # | Leakage vector | Check |
|---|---|---|
| 1 | Future injury statuses in Friday features | Assert zero rows with `date_modified ≥ T(game)` in feature tables |
| 2 | Sunday/final statuses | Same filter; game-day inactives excluded by construction (§4) |
| 3 | `date_modified` semantics | Timing-sanity audit (§4) before fitting; unreliable vintages excluded, not assumed |
| 4 | Roster hindsight | Starter/snap role from **pre-week** data only (trailing snaps, never game-week depth chart); assert no game-week roster fields in features |
| 5 | V1 residual leakage | `v1_margin` walk-forward for all experiment games (§6); assert no game's outcome was used in its own V1 prediction |
| 6 | Market information | Assert no market spread/line/total columns in any injury-layer input |
| 7 | PFT contamination | PFT corpus not read by the primary pipeline at all; secondary analysis only post-verdict |
| 8 | Test isolation | Build/fit scripts assert `season ≤ 2022`; locked-test evaluation is a separate one-shot script |
| 9 | `qb_point_values.json` | Never loaded as a feature (reference-only, §2); grep-assert in review |
| 10 | Practice-status timing | Excluded as a feature (§5); assert no `practice_status` column in feature tables |
| 11 | Silent promotion | The experiment writes to `experiments/injury_adjustment_experiment/` only; no V1 file, no production script, no dashboard JSON is touched |

---

## 10. Reproducibility and the one-shot procedure

**Directory:** `experiments/injury_adjustment_experiment/` with
`data/` (frozen feature tables + SHA256 checksums), `results/` (empty until
the locked run), and this protocol.

**Scripts (new, 50-series):**
- `scripts/50_injury_exp_build.py` — extends the frozen V1 walk-forward to
  2019+, builds timing-filtered injury features for 2018–2025, runs the
  timing-sanity audit. Validates on train+dev structure only.
- `scripts/51_injury_exp_fit.py` — fits A–D on train (seed 42), evaluates
  A–E on dev, writes the frozen candidate bundle
  (`injury_candidates_frozen.pkl` + JSON manifest of every hyperparameter).
- `scripts/52_injury_exp_locked_test.py` — loads the frozen bundle, asserts
  no 2023+ data entered fitting, evaluates exactly once, writes
  `experiments/injury_adjustment_experiment/RESULTS.md`.

**Seeds:** 42 for all stochastic steps (bootstrap; Ridge/OLS are
deterministic). Library versions pinned from the repo venv.

**Gates (binding):**
1. Cale approves/freezes this protocol (including the §7.1 win-bar number).
2. Build + fit + dev selection run; frozen bundle written.
3. Cale re-confirms before the locked test.
4. `52_injury_exp_locked_test.py` runs **once**. Its output is final —
   no re-runs with tweaks, no "one more specification."

---

## 11. Null-result clause and promotion guardrails

- If no candidate clears the preregistered bar: **report the null cleanly.**
  A null here is evidence about the information content of full-roster
  availability data, not a failure of effort. V1 stays unchanged.
- **Even if the bar is cleared, nothing is promoted to production
  automatically.** Promoting an injury adjustment into the live pipeline
  (or into the void/risk layer's inputs) requires a separate, explicit
  authorization from Cale after reviewing RESULTS.md.
- Phase 1 plumbing remains operational risk-control infrastructure
  throughout; the existing void rule stays byte-for-byte unchanged; Phase 2
  never silently becomes a V1 feature.
- Failed candidates and the full audit trail are preserved as evidence,
  never deleted.

---

## Appendix: what stays locked / out of scope

- V1's math, weights, architecture, and production behavior: untouched.
- Experiment 006 (information timing): untouched; its prospective results
  arrive independently.
- The 2023–2025 spread vault: not opened for selection — one evaluation only.
- PFT/news: separate branch; secondary timing validation only (§4).
- Player-projection (Experiment 001) models: separate; no cross-contamination.
- Totals, moneylines, stakes, real-money recommendations: never in scope.

---

*Protocol drafted 2026-09-30. Awaiting Cale's review, win-bar decision (§7.1),
and freeze authorization before any fitting or locked-test evaluation.*
