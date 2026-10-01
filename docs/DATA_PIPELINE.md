# Website Data Pipeline

How the public dashboard gets its data: what generates it, when, and what
happens when something breaks. (Phase 7 deliverable.)

## The pipeline in one sentence

Python scripts run on a schedule, the exporters (`15`, `18`) write versioned
JSON to `data/ui_json/`, the JSON is synced into `dashboard/data/`, and the
static site fetches it at load — the website never runs Python and never
computes anything.

## Generation

### Game model data (`data/ui_json/v1/*.json` except experimental_markets)

| Step | Script | Input | Output |
|---|---|---|---|
| 1 | (human) | news, odds screens | `data/market_2026_w{N}.json` — Friday game lines, `{"AWAY_HOME": [spread, total]}` |
| 2 | `29_qb_expectation.py --season 2026 --week N` | injury reports | `data/qb_expectations/qb_expected_2026_w{N}.parquet` (append-only) |
| 3 | `27_injury_diff.py --freeze-friday --season 2026 --week N` | injury feeds | `data/injuries/availability_friday_2026_w{N}.json` (refuses overwrite) |
| 4 | `07_update_weekly.py --season 2026 --week N --market-json …` | nflverse (keyless) | `data/predictions_2026_w{N}.csv` — V1 raw (frozen) |
| 5 | `11_injury_adjust.py` (full args in workflow) | predictions + market + injury state + expected QB | overlay columns: expected QB, QB shift, adjusted prediction, final status |
| 6 | `28_injury_audit.py --season 2026 --week N` | all of the above | `data/injuries/audit/audit_2026_w{N}.parquet` (refuses overwrite) |
| 7 | `15_export_ui_json.py --week N` | predictions, props, record, injuries, markets | `data/ui_json/v1/*.json` + `data/ui_json/versions.json` |

### Props data

| Step | Script | Output |
|---|---|---|
| 1 | `16_prod_player_projection.py --refresh` then `--season 2026 --week N` | `data/prop_v2_2026_w{N}.json` — Model D yard projections |
| 2 | `17_prod_rush_attempts.py --season 2026 --week N` | 003B rush-attempt projections (experimental, frozen M2) |
| 3 | `19_prod_receptions.py --season 2026 --week N` | 003A reception projections (experimental, frozen) |
| 4 | `30_pull_prop_lines.py --season 2026 --week N` | `data/market_props/market_props_2026_w{N}.json` — Bovada lines |
| 5 | `18_export_experimental_markets.py --week N` | `data/ui_json/v1/experimental_markets.json` |

`--week N` auto-detects the latest week when omitted; passing it explicitly
is preferred for reproducibility.

### Continuous inputs (not Friday-gated)

- **Hourly market lines** (`31_pull_market_lines_hourly.py`, hourly cron):
  append-only snapshots in `data/market_hourly/`; the exporters join the
  latest successful snapshot additively (`market_live_books`). Friday numbers
  are never overwritten by this feed.
- **Daily injury pull** (daily 08:20 CT cron): refreshes the injury state the
  dashboard's Data Health page reports on.
- **Tuesday grading** (`08_grade_week.py`, Tuesdays 08:20 CT): appends the
  finished week's result to `data/record.csv`; **Tuesday snapshot**
  (`22_tuesday_snapshot.py`) captures the timing-study observation.

## Cadence

| Cadence | What | Trigger |
|---|---|---|
| Weekly (Fri ~18:20 CT) | Full pipeline: predictions, props, exports, site update | Manual workflow dispatch after human commits Friday market lines |
| Weekly (Tue ~08:20 CT) | Grade finished week, timing snapshot | Scheduled |
| Daily (~08:20 CT) | Injury pull | Scheduled |
| Hourly | Market line snapshots | Scheduled |
| On push to `main` | Validate JSON → deploy `dashboard/` to Pages | `deploy.yml` (paths: `dashboard/**`, `data/ui_json/**`) |

The `update-data.yml` workflow is **manual-trigger only, never scheduled**:
the Friday flow has human inputs (researched lines, QB-news judgment) that
must land before the pipeline runs. Automation runs the deterministic steps;
humans supply the judgment.

## The sync step (canonical → deployed)

`dashboard/data/` must stay byte-identical to `data/ui_json/`. The sync is a
plain copy:

```
cp data/ui_json/v1/*.json dashboard/data/v1/
cp data/ui_json/versions.json dashboard/data/versions.json
```

The `update-data.yml` workflow performs it after validation. For local runs,
do it by hand and commit both trees together — never commit one without the
other.

## Failure behavior

**Generation fails → nothing ships.** Every stage is fail-loud:

- Missing manual input (`data/market_2026_w{N}.json`) → workflow exits
  before running anything.
- Any script exits non-zero → the workflow stops; no commit, no push.
- Exporter validation fails (non-finite literal, schema violation) →
  `data/ui_json/` is not updated.
- Post-generation validation fails → the sync does not happen.
- Deploy validation fails → GitHub Pages keeps serving the previous build.

**The public site never shows a half-updated week.** Either the full set of
JSON files for week N validates and ships together, or week N−1 stays up
with its original timestamps.

**Dashboard load fails → fail-safe page.** If any required JSON file is
missing, returns non-200, or fails to parse, the dashboard aborts boot and
renders a "data unavailable" error. It does not render partial predictions,
does not reuse stale data silently, and does not fabricate values.

**Stale data is visible, not hidden.** Every page shows generation
timestamps and as-of dates from the JSON itself. If the pipeline hasn't run,
the timestamps say so.

## Data provenance (what the JSON carries)

- `meta.json`: `generated_at`, season, week, model version.
- `predictions.json`: per-game `market_line` with book + capture timestamp;
  `market_live_books` from the hourly snapshots; QB overlay fields carry
  their source (`manual` / `recorder` / `frozen feed`).
- `props.json`: `market_line` per prop with capture timestamp; unoffered
  markets are listed, never fabricated.
- `injuries.json`: `as_of`, snapshot row counts, status counts.
- `versions.json`: manifest of model versions and generation times.

## What this pipeline will not do

- Retrain or modify V1, Props Model D, or any frozen experiment artifact.
- Change weights, timestamps, as-of dates, freeze logic, or cutoffs.
- Add features or data sources (all sources are keyless: nflverse, Bovada,
  ESPN).
- Present a projection as a proven edge. The dashboard carries the standing
  honest verdict: no verified betting edge; experimental outputs are labeled
  experimental.
