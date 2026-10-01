# V2 Blocker Resolution — Phase 1 Gate Document

Date: 2026-09-29. Status: all five blockers resolved to "resolved" or
"resolved with documented residual"; nothing fabricated; nothing left in an
ambiguous state. This document is the Phase 1 gate record required before the
research protocol is frozen.

Scope note: architecture/data work only. No model trained, no validation
evaluated, no V2-A:E, no Experiment 008. V1 untouched, 2023–2025 vault
untouched, Experiment 006 observations untouched.

---

## Blocker 1 — Historical QB value: RESOLVED

**Built:** `scripts/37_v2_qb_value.py` → `data/v2/qb_value_pred.parquet`
(2,744 rows × 17 cols, team × season × pred_week, 2018–2022). Design:
`v2_research/qb_value_design.md`.

**What was resolved:**
- Historically valid QB value exists for 2018–2022: `qb_value_historical` =
  recency-weighted (half-life 8 games, stated parameter, NOT fitted) qb_epa
  per dropback, computed only from games strictly before the prediction week.
- QB identity = scheduled starter via canonical key (last-token + first
  initial, suffix-stripped); history is QB-keyed and team-agnostic — a
  mid-season team change travels with the QB (65 rows with `qb_team_changed`).
  Two schedule data-entry errors handled deterministically
  (`herbery_j` → `herbert_j` alias; `murray_t` ambiguous → NaN).
- Cold start: value exists iff ≥ 4 prior games AND ≥ 40 prior dropbacks,
  else NaN + `qb_cold_start=1`. Coverage 88.7% (2,434/2,744); 310 cold-start
  rows. Backups degrade identically — small-sample mean, no fitted imputation.
- Per-season feasibility: qb_epa/db, pass-play split, sack rate, qb_hit
  proxy, QB rushing attribution, PFR `times_pressured_pct`, QB identity —
  all five seasons ✓. CPOE present all five seasons at ~81–82% of pass plays
  but defined on completions only (denominator = completions, not attempts).
- A real bug was caught and fixed in the build: the first version
  double-weighted volume (dropbacks in weights AND game-total numerators),
  producing mean 2.26 EPA/db; after the fix the distribution is sane
  (mean 0.066, median 0.076) and one row was independently recomputed from
  raw PBP to 6 decimals — exact match.
- `qb_value_poll` (2026-anchored) quarantined: never read by the builder,
  tagged QUARANTINED in the inventory, superseded by `qb_value_historical`.
- Refined filter applied: nothing dropped for correlation; priority-ranked
  with pressure response (`qb_hit_epa_db_rw`) and CPOE most orthogonal to
  team EPA; `qb_value_historical` deliberately kept despite expected
  team-EPA correlation (identity-level conditional information).

**What remains (documented, not resolved here):**
1. Multi-component composite weights would need fitted coefficients — not
   authorized in Phase 1. The six components are emitted unfitted for a
   future authorized fitting experiment.
2. Cold-start/backup NaN handling (replacement-level prior) is a
   modeling-stage decision.
3. `qb_pressured_pct_rw` is Tuesday-lag restricted (blocker 3) — Friday-safe
   only; excluded from the Tuesday information set.
4. Per-play "qb_epa under pressure" cannot be built honestly — PBP
   2018–2022 has no per-play pressure indicator (`qb_hit` proxy used).

**Net:** 9 new player_qb features added to the inventory (now 153 total).
V2-C's Tier-1 candidate is `qb_value_historical`.

## Blocker 2 — Injury timestamps: RESOLVED (with one implementation gap flagged)

**Built:** `v2_research/injury_cutoff_policy.md`. Analysis:
`v2_research/tag_updates_avail.json` (12 tag patches applied).

**What was resolved:**
- Hard rule operationalized: `date_modified < prediction_cutoff`, with the
  cutoff explicitly defined per experiment type:
  - Tuesday-AM: `cutoff = 08:00 ET on the most recent Tuesday strictly before
    the team's kickoff` (Sun→5d prior, Thu→2d, Mon→6d).
  - Friday: `cutoff = 23:59:59 ET on the most recent Friday strictly before
    kickoff`, for games not yet played Friday evening.
- Survival fractions, 2021–2022 (2,248 Out/Doubtful rows):
  - `date_modified` < own-game kickoff: **100.0%** (2018–2022: 99.9%; 23
    exceptions are postgame-edited rows on non-Sunday games, e.g. ATL 2019
    W13 Thanksgiving rows re-touched the Friday after).
  - Knowable at Tuesday-AM cutoff: **0.0%** — the weekly injury-report cycle
    starts Wednesday. Under V2's intended Tuesday-AM information set,
    per-team-week availability is identically zero.
  - Knowable at Friday cutoff: **83.9%** overall; 99.1% for Sunday games.
    Shortfall is MNF teams' final designations landing Saturday (genuinely
    not knowable Friday — faithful, not a bug) plus Thursday games out of
    the Friday scope. 16.1% of Out/Doubtful rows are Saturday-or-later:
    known before kickoff, knowable at neither cutoff.
- The mandatory distinction is documented with data examples:
  - Friday-yes/Tuesday-no: Evan Engram, NYG, 2021 W1 — Out,
    `date_modified=2021-09-10T19:14:51Z` (Fri 15:14 ET), game Sun 16:25 ET.
  - Before-kickoff/neither-cutoff: Minkah Fitzpatrick, PIT, 2022 W10 — Out,
    `date_modified=2022-11-12T21:50:44Z` (Sat 16:50 ET), game Sun 13:00 ET.
- 2025/26 implication: those files have **no `date_modified` column at all** —
  no cutoff discipline is possible, so 2025/26 injury rows are **unusable**
  for `avail_value_out`/`avail_n_out` in any experiment that must respect
  prediction-time cutoffs. A week-grain fallback is explicitly rejected as
  the leak it is.
- Kickoff-time source verified: `data/games.csv`, minute-precision ET, 0%
  missing for 2018–2022 REG.

**Known implementation gap (flagged, not fixed here — belongs to the
modeling-stage rebuild):** `scripts/33_v2_features_player.py` reads
`date_modified` and claims a pre-kickoff filter in its docstring, but the
code never applies it — it aggregates all week-grain rows. The rebuild must
implement the row-level rule
`date_modified < min(prediction_cutoff, team_game_kickoff)`. The docstring's
"week's first kickoff" convention is superseded (over-conservative for Sunday
teams, wrong grain).

**Consequence for V2-C:** under the Tuesday information set, availability
features are constants (zero). They remain in the preregistered V2-C spec
with this documented; the model must tolerate constant columns.

## Blocker 3 — PFR Tuesday lag: RESOLVED

**Built:** `v2_research/pfr_lag_audit.md`.
`v2_research/tag_updates_pfr.json` (34 tag patches applied).

**What was resolved:**
- Headline verdict: **all 17 `pressure_pfr` features → LAG ONE WEEK.**
  Zero KEEP, zero DROP. For prediction week W at the Tuesday 08:00 CT
  snapshot, only PFR data from games through week W−2 may enter.
- Verified (PFR's own statement, Sports-Reference blog Oct 11 2019, plus live
  PFR player-page boilerplate): advanced statistics "don't fully update
  until the Wednesday morning following the weekend's games." At the Tuesday
  08:00 CT snapshot, week W−1 advanced stats are incomplete; partially-posted
  rows would silently corrupt team-week sums/means.
- Verified (nflverse side): the nflverse-pfr scraper runs every 6 hours —
  cadence is NOT the binding constraint; PFR's publication timing is.
- Conservative default documented: where publication timing cannot be
  verified, lag one week, never assume timely. PFR's "Wednesday morning" has
  no stated timezone; treated as ~24h after the Tuesday snapshot.
- Raw files carry no publication timestamps or revision markers — the audit
  rests on publication-schedule research + the conservative default.
- Degradation is in effective sample, not feature count: with min_sample = 4
  prior games, prediction week 5 is the casualty (4 games → 3 lagged → NaN);
  week 6+ keeps full expanding history minus the single most form-relevant
  week.
- **Critical:** historical `team_week_pfr.parquet` was built from complete
  files and is NOT Tuesday-timely as stored — any future walk-forward use
  must shift it (week W ← rows ≤ W−2); consuming it raw is information-time
  leakage of exactly the Experiment 006 class. This supersedes
  `leakage_audit.md`'s "consume in the Tuesday batch" note, which understated
  the lag.

**What remains:** the one-week shift is specified but not implemented —
belongs to the modeling stage (not authorized in Phase 1). Experiment 006's
live stream may independently confirm/refine PFR publication timing.

## Blocker 4 — Weeks 1–4 cold start: RESOLVED (policy documented, choice frozen in protocol)

**Built:** `v2_research/cold_start_policy.md`.

**What was resolved:** four alternatives documented with trade-offs, none
silently invented:
- A: prior_games bucketing (0/1/2/3/4+) with bucket-specific priors.
- B: defined preseason/offseason prior (decayed prior-season carryover).
- C: V1 fallback for cold-start games, reported separately (recommended for
  research: simplest, fully honest about what is tested).
- D: exclude with documentation — explicitly rejected as the default.

**Frozen choice (in the research protocol):** Option C. Games where either
team has < 4 prior games use V1's prediction, are logged as fallback games,
and are reported separately from the V2-vs-V1 comparison. Modeling-time
requirements: expose `prior_games` as a first-class column; never fill NaN
with full-sample statistics; log the branch taken per game; keep the prior
frozen within an experiment.

## Blocker 5 — Matchup standardization: RESOLVED (spec frozen)

**Built:** `v2_research/standardization_spec.md`.

**What was resolved:**
- Leakage class documented with a verified numeric example: a week-5 game
  with raw 0.040 goes from z = −1.00 (walk-forward μ/σ over 10 prior games)
  to z = −0.45 once a future week-17 outlier (0.30) enters full-sample
  statistics. Full-sample scaling of ANY kind (z-score, min-max, robust,
  percentiles, winsorization, pre-product component scaling) leaks.
- Transform: z = (x − μ)/σ with μ,σ over S(W) = league games with kickoff
  strictly before the Tuesday prediction-date batch. League-wide expanding
  default; per-team scaling rejected (σ unstable at ~16 games/season);
  population std (ddof=0).
- Window: expanding default (consistent with the components' expanding-mean
  construction); trailing-K ∈ {8,16,32} enumerated but not chosen.
- Min history: two gates — inherited component gate (≥4 prior games/team)
  AND |S(W)| ≥ 30 for the scaling set, else NaN (binds only early-2018).
- Per-feature groups: A rate×rate products → z-score (walk-forward
  percentile allowed); B EPA/points products (records the signed-product
  semantic quirk) → z-score (robust median/IQR allowed); C mixed products →
  z-score; D cross-differentials → z-score, raw passthrough allowed only here.
- Cross-season: options A (continuous expanding, matches scripts/35) / B
  (offseason decay, weights timestamp-functions only) / C (hard season
  reset); non-negotiable constraint: every observation in S(W) has kickoff <
  prediction_date(W); inclusion/weighting never conditions on outcomes.
- 9-item audit checklist (A1–A9) + reviewer spot-check procedure.
- **Frozen choice (in the research protocol):** expanding league-wide,
  option A cross-season (continuous expanding), NaN propagation on gate
  failure (fallback F1) with walk-forward median imputation for feature-level
  missingness downstream — all preregistered, none tuned.

## New gate — feature-family overlap matrix: COMPLETE

**Built:** `v2_research/overlap_matrix.json` (+ `family_overlap_matrix.json`,
identical copy for the Phase 1 gate manifest), `v2_research/overlap_matrix.md`,
`scripts/38_v2_overlap_matrix.py`. Descriptive only, 2021–2022, n=569.

**Key finding:** the families are NOT one latent variable.
- V1/ELO/EPA form the tight cluster (0.93/0.94/0.76).
- **Pressure (−0.10 with V1) and QB (0.06 with V1) are essentially
  orthogonal** to the latent team-strength axis. (QB score caveat: built from
  the inventory's identity/availability markers, not the new historical QB
  value — recompute after blocker 1's value enters the modeling tables.)
- **Matchup / Possession / Explosive form a correlated cluster**
  (0.63–0.80; 0.42–0.51 with V1) — expected, since matchup interactions are
  constructed from possession/explosiveness/pressure inputs. The structural
  claim was never "independent inputs" but "interaction structure V1's scalar
  collapse destroys"; only V2-B can test that.
- Continuity 0.38, special teams 0.03, environment −0.06, availability −0.12
  with V1.
- Methodological note: the mx_* features are side-specific; the score flips
  `_awayoff` variants to home-margin perspective. An unflipped version gave a
  spurious ~0.00 — sign discipline is now documented in the script.
- Priority ranking (priority, NOT exclusion): 1. pressure, 2. QB (pending the
  historical value), 3. special teams / availability / environment,
  4. matchup / possession / explosiveness (test is conditional information
  given the strength axis).

## Residual / quarantined items (carried forward, not blockers)

1. `qb_value_poll` — QUARANTINED (2026-anchored), superseded.
2. `scripts/33` date_modified filter — flagged gap; rebuild implements the
   row-level rule at modeling stage.
3. PFR one-week shift — specified, implemented at modeling stage.
4. Per-play pressure EPA — unbuildable honestly (no PBP pressure indicator).
5. Fitted QB composite weights — needs an authorized fitting experiment.
6. 2025/26 injury rows — unusable for availability features (no
   date_modified).
7. Weather — 36.8% missing (unchanged from the architecture build).
8. `qb_pressured_pct_rw` — Friday-safe only (Tuesday-lag restricted).
9. Cold-start NaN handling beyond the V1 fallback — modeling-stage decision.
