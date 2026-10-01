# Experiment 006 — Prospective 2026 Information-Timing Study: Methodology

**Status:** infrastructure built and smoke-tested 2026-09-29. Observational only.
**Frozen:** V1 code and scripts 01–21 are untouched. This experiment fits no model,
optimizes nothing, and cannot promote anything to V2.

## Objective

Measure how model information and market information evolve from Tuesday to
Friday on the live 2026 stream, to test the hypothesis (from Experiment 004)
that the market–V1 gap is substantially an information-*timing* gap: V1's
effective information state is ~Tuesday AM, while the historical market
benchmark may reflect a later-week state. Historical data cannot answer this
because the historical `spread_line` is an undated single snapshot
(`line_provenance = nflverse_proxy_open`, contradicted elsewhere in the repo).
This study collects timestamped Tuesday and Friday snapshots prospectively.

## Design

For each 2026 game, three records:

**Tuesday snapshot** (`data/timing_study/tuesday_2026_w{N}.csv`, via `scripts/22_tuesday_snapshot.py`)
- V1 prediction from the frozen pipeline (`07_update_weekly.py`, model-only, no market)
- Tuesday market line, if the operator researched one (never backfilled)
- ELO/EPA ratings state (same code path as the Friday pipeline)
- capture timestamps (UTC + America/New_York), timing_flag (OK if Tuesday ET)

**Friday snapshot** (`data/timing_study/friday_2026_w{N}.csv`, via `scripts/23_friday_snapshot.py`)
- Runs AFTER the regular Friday pipeline (07 + 11_injury_adjust)
- V1-compatible prediction with Friday information, Friday market line, edge,
  final pick, void reason, QB news, wind, ratings state
- Thursday-night games flagged `already_played=1` (excluded from movement analysis)

**Anti-optimization rule (binding):** the Friday snapshot must always be produced by
the *same frozen V1 machinery* as the Tuesday snapshot and the production
pipeline — only the input information state may differ (ratings refresh, Friday
injury/weather research). The Friday prediction must never be independently
tuned, reweighted, or re-architected. Any change to the Friday prediction
machinery is a change to V1 itself, which is forbidden during this study.
Friday measures information timing, not a new model.

**Postgame grading** (`data/timing_study/graded.csv`, via `scripts/24_timing_grade.py`)
- actual margin, Tue/Fri model error, Tue/Fri market error,
  model movement (Fri−Tue), market movement (Fri−Tue), CLV from `clv_picks.csv`
- Idempotent: re-running replaces the week's rows.

## Timing cutoffs

- **Tuesday capture:** target ~9:00 AM ET Tuesday. `timing_flag=LATE` if run on any
  other weekday (data kept, flagged for exclusion).
- **Tuesday market lines:** `data/market_tue_2026_w{N}.json`, same format as the
  Friday market JSON (`{"AWAY_HOME": [spread, total]}`), researched Tuesday AM.
  If the file is absent at snapshot time, `market_tue_missing=1`. A missed
  Tuesday is never reconstructed later.
- **Friday snapshot:** runs after the Friday pipeline completes (any time Friday
  before the week's first unplayed kickoff; Thursday games are excluded anyway).

## What counts as "newly available information" (Tue→Fri)

1. Games played between snapshots (esp. Thursday night) entering ELO/EPA/GBM
   via the Friday ratings refresh.
2. QB/injury news researched Friday (`qb_news` in the market JSON; the
   11_injury_adjust void layer).
3. Weather/wind forecasts in the Friday market JSON.
4. Market line movement itself (observed, never used as a model input).

## Missing-data rules

- Missing Tuesday market → row kept; market-movement questions unanswerable for
  that game/week (recorded, not imputed).
- `already_played=1` (Thursday games at Friday capture) → excluded from all
  Tue→Fri movement comparisons; kept for Tuesday-only accuracy.
- No imputation anywhere. No winners declared on small samples (n<~200 games
  is descriptive only).

## Weekly operating procedure (cron)

**Tuesday ~9:00 AM ET** (new step):
1. Research Tuesday market lines (same browser procedure as Friday lines) →
   `data/market_tue_2026_w{N}.csv`... i.e. `data/market_tue_2026_w{N}.json`.
2. Run: `./venv/bin/python scripts/22_tuesday_snapshot.py --season 2026 --week N
   --market-json data/market_tue_2026_w{N}.json`
   (omit `--market-json` if Tuesday lines were not captured).
3. Confirm `data/timing_study/tuesday_2026_w{N}.csv` exists with 16 rows.

**Friday** (existing pipeline, then):
1. Existing: grade last week → research Friday lines → run 07 → run 11 →
   props → sheet → UI export.
2. New: `./venv/bin/python scripts/23_friday_snapshot.py --season 2026 --week N`
3. Confirm `data/timing_study/friday_2026_w{N}.csv` exists.

**After the week's games are graded** (existing 08 run):
1. New: `./venv/bin/python scripts/24_timing_grade.py --season 2026 --week N`
2. `data/timing_study/graded.csv` grows by the week's rows.

N = the week whose games begin the coming Thursday.

## Analysis plan (when n is sufficient)

1. How much does V1's prediction change Tue→Fri? (mean |model_move|)
2. How much does the market line move? (mean |market_move|)
3. Does the Friday information state reduce model margin error?
4. Does market movement go in directions V1 doesn't capture?
5. Friday vs Tuesday V1 error.
6. Does eventual CLV support the timing interpretation?
7. Which information categories drive observed model changes?

Report must distinguish: **A)** prediction accuracy, **B)** information timing,
**C)** market movement, **D)** tradable-signal evidence — and these four
sub-questions must never be collapsed into one:

1. **Model movement** — "Our estimate changed because new information entered
   the ratings." (Observed quantity, not a virtue.)
2. **Market movement** — "The market moved during the same period." (Observed
   quantity, not a virtue.)
3. **Prediction improvement** — "The updated estimate was closer to the actual
   margin." (Accuracy claim, requires the error comparison.)
4. **Tradability** — "The movement translated into subsequent CLV." (Separate
   prospective evidence; CLV is tracked in `clv_picks.csv`, never inferred
   from error reduction.)

Movement without improvement is noise. Improvement without tradability is
diagnostics, not signal. No V2 promotion is possible from this study alone. No V2 promotion is
possible from this experiment alone.

## Cold start

- **Week 5** is the first scheduled week (first Tuesday with the full procedure).
- **Week 4 (2026-09-29):** opportunistic partial capture during infrastructure
  testing — Tuesday model snapshot captured live on Tuesday (timing_flag=OK),
  no Tuesday market lines (market_tue_missing=1). Friday snapshot consolidated
  from pipeline outputs generated 2026-09-25 (noted in the file).
- Weeks 1–3: not reconstructed.

## Tuesday line-source feasibility

No new tooling required: Tuesday lines are researched with the same browser
procedure already used for Friday lines, written to
`data/market_tue_2026_w{N}.json`. The binding constraint is operational
discipline — a Tuesday-AM research step must actually happen each week. If it
is missed, the week's model-timing observations (Q1/Q3/Q5) remain valid;
market-movement questions (Q2/Q4) do not.
