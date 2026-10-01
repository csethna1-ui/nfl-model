# Player Projection v2 — Experimental Production

Weekly player-yardage projection engine. Productionizes the **frozen
Player Projection Experiment 001** models exactly as tested — this is
productionization, not new research.

## What it is (and is not)

- **Primary projection (all three markets): Model D** = equal-weight
  average of Model A (two-stage opportunity×efficiency), Model B
  (gradient boosting), and Model C (quantile GBM median).
- **Ranges/confidence:** Model C p25/median/p75, with uncertainty and
  High/Medium/Low confidence calibrated on the **dev** slice (2021–2022).
- **Why-decomposition:** Model A stages — expected opportunities ×
  expected efficiency — plus rule-based recent-usage, team-environment,
  and opponent-adjustment notes.
- **Comparison baseline:** EWMA (half-life 3) yards kept alongside every
  projection; the experiment's benchmark, not a challenger.
- **Experimental label, always.** Experiment 001's verdict: the
  preregistered improvement bar was **NOT cleared** (null on the primary
  question; no model declared winner). Pass-market gains were real
  (−7.2% vs EWMA, bootstrap CIs excluding zero, big-miss mechanism
  supported); rush (−4.3%) and receiving (−2.6%) were near-nulls. This
  engine is a better-performing **tested specification**, never a
  "validated best" model. No verified betting edge; no +EV claims;
  paper-track only.

## Provenance (frozen)

- Protocol: `experiments/player_props_projection/PREREGISTRATION.md`
  (approved + re-frozen 2026-09-30, incl. the Model D equal-weight amendment)
- Results: `experiments/player_props_projection/RESULTS.md`
  (dev MAE baseline 65.75/26.82/25.01; D 57.77/25.15/23.98)
- Fit code: `experiments/player_props_projection/scripts/run_experiment_001.py`
  (fit/predict functions are **imported verbatim** by the production engine;
  `scripts/16_prod_player_projection.py` only adds `--fit` verification,
  calibration, and weekly feature construction)

### `--fit` reproduction guarantee

`--fit` re-runs the experiment's own fit functions on the train slice
(2018–2020) and its own selection loop on the dev slice (2021–2022), then
**aborts unless** the reproduced dev MAE matches the published values to
within 0.01 and the selected hyperparameters match (A: ridge α=10.0 all
markets; B: lr=0.05, max_depth=3, max_iter=200 all markets; C fixed a
priori). The 2023–2024 locked test is never touched — it was spent for
these candidates.

## Hard rules

1. **PFT/news = OFF.** No news features anywhere in this pipeline.
2. **No refits on 2023–2024; no architecture changes.** The models are frozen.
3. **Keyless data only.** No API keys, no card-gated services.
4. **Weather excluded** (game-time observations leak into pregame features).
5. **Projection → line → lean.** Market lines are joined *after*
   projections are computed; the engine never sees the line. Rows are
   produced for **all eligible players**, not just lined ones; no line →
   no lean, projection still published.
6. **Do not touch:** V1 spread pipeline, Experiment 006, the PFT corpus,
   the experiment's 2018–2024 cache files.
7. Experimental/no-verified-edge disclaimer language everywhere; the label
   is "Player Projection v2 — Experimental Production", never "validated best".

## Weekly runbook (Friday flow)

The engine runs **after** the spread pipeline (scripts/07) and never blocks
V1. The Friday cron is owned by the parent agent — this doc describes the
player-projection steps only, as docs; do not wire or touch the cron from
this directory.

```
# 1. keyless data refresh (nflverse; re-pulls 2026, rich 2025+2026,
#    rebuilds aggregates, best-effort aux snap/injury/depth)
./venv/bin/python scripts/16_prod_player_projection.py --refresh

# 2. weekly projections for the upcoming games
./venv/bin/python scripts/16_prod_player_projection.py \
    --season 2026 --week N --market-json data/market_props_2026_wN.json
#   -> data/prop_v2_2026_wN.json (validated against docs/props_SCHEMA.md)

# 3. export to the dashboard JSON
./venv/bin/python scripts/15_export_ui_json.py
#   -> data/ui_json/v1/props.json
```

`--fit` is run **once** (persists `data/prod_player_models_v2.pkl` +
`data/prod_player_models_v2_meta.json`); weekly runs load the fitted
artifacts. Re-run `--fit` only to re-verify reproducibility — the fit
procedure is deterministic, so a re-run must reproduce the same models
and verification.

### Market-line input (new schema)

`data/market_props_2026_wN.json` is a JSON list of
`{player, market, line, source, captured_at}`. `captured_at` is the ISO
timestamp of when the line was captured — **recording it is what fixes
the historical no-timestamp gap going forward**; every new capture must
record source + captured_at. Files missing them are tolerated
(source="unknown", captured_at=null) but that is a gap to close, not a
norm. `market` ∈ pass_yards / rush_yards / receiving_yards.

The Friday researcher populates this file alongside the spread lines;
the engine's name-matching reuses `scripts/10_prop_projector.py`'s
matcher (`build_name_index`/`match_player`).

### Cutoff discipline

- Prediction timestamp: **Friday 18:00 America/Chicago** of game week
  (same rule as the experiment; DST-aware).
- Trailing features use games **strictly before** (season, week);
  up to 16 most recent.
- Games kicking off at/before the timestamp (Thursday/early games) are
  **excluded** from the weekly file — their outcomes are known at
  timestamp, so including them would violate the timestamp rule.
- Rate/share trailing features fill NaN → 0 (experiment convention).

### Eligibility per player-market

- Trailing history ≥ 3 games, AND trailing role volume ≥
  (10 pass_att / 5 rush_att / 5 targets) — the experiment's guards.
- Position (and thus market) comes from the **most recent season with
  ≥3 games** (early-season adaptation of the experiment's full-season
  touch-mix rule; the full-season rule is its special case).

### Uncertainty

Relative width = (p75−p25)/max(median, 1), calibrated on dev only:

- `uncertainty_flag` = relative width above the market's dev 90th
  percentile (operationalizes the Experiment 001 finding that the
  models' value concentrates in shrinking top-decile baseline misses).
- `confidence` = High / Medium / Low by the dev 33rd/67th percentiles.
- When flagged, `uncertainty_note` names the primary driver by a fixed
  heuristic (player opportunity vs production efficiency).

### Why-block

From trailing/pre-kickoff data only; all cutoffs fixed and documented:

- `expected_opportunities` (A stage-1), `expected_efficiency` (A stage-2)
  with their units (pass attempts/carries/targets; yards/attempt etc.)
- `recent_usage_note`: last-3 opportunity mean vs trailing EWMA —
  elevated (>1.15×), reduced (<0.85×), stable
- `team_environment`: team implied total vs the week's league average —
  favorable (≥+2), unfavorable (≤−2), neutral
- `opponent_adjustment`: opponent's trailing allowed (market-relevant
  stat) vs league average — favorable (>1.10×), tough (<0.90×), neutral

## Files

| Path | What |
|---|---|
| `scripts/16_prod_player_projection.py` | the engine (`--fit`/`--refresh`/`--season --week`) |
| `data/prod_player_models_v2.pkl` | fitted A/B/C × 3 markets (from `--fit`) |
| `data/prod_player_models_v2_meta.json` | selection, reproduced-vs-published dev MAE, calibration |
| `data/prod_pbp_rich_2025.parquet`, `data/prod_pbp_rich_2026.parquet` | production rich-pbp cache (2025+) |
| `data/prod_aux_*.parquet` + `prod_aux_report.json` | snap/injury/depth aux pulls (context only, never features) |
| `data/prop_v2_2026_wN.json` | weekly output |
| `data/ui_json/v1/props.json` | dashboard export (via `scripts/15_export_ui_json.py`) |
| `docs/props_SCHEMA.md` | field-by-field schema reference |

## Standing caveats for readers

- 2025 is spent/reference-only (old projector diagnostics were published
  on it); do not validate the v2 engine against 2025.
- 2023–2024 are spent for these model candidates — no further modeling
  on this branch without a newly authorized protocol.
- Injury/status information is not yet wired into the player engine;
  the separate injury-pipeline audit is tracking the production injury
  architecture. Until then, projections assume full-strength roles and
  the injury handling is doc-only context.
