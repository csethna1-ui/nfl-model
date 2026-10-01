# Architecture

## One-paragraph summary

This repository is an NFL prediction research project with a **static public
dashboard**. The model pipeline (Python) runs on a schedule in a trusted
environment and writes versioned JSON snapshots. The website is plain
HTML/CSS/JS hosted on **GitHub Pages** — it fetches those JSON files at load
time and renders them. **No Python runs at view time. No backend. No
database. No API keys.** Hosting cost: $0/month.

## Components

```
┌─────────────────────────────┐
│  Scheduled pipeline (cron)  │  Fridays 18:20 CT, Tuesdays 08:20 CT,
│  Python 3.12, keyless data  │  daily 08:20 CT, hourly
└──────────────┬──────────────┘
               │ writes
               ▼
┌─────────────────────────────┐
│  data/ui_json/              │  Canonical public data layer.
│  versions.json + v1/*.json  │  Written ONLY by scripts/15 and scripts/18
│                             │  (the export gatekeepers).
└──────────────┬──────────────┘
               │ synced (cp) by the update workflow / operator
               ▼
┌─────────────────────────────┐
│  dashboard/                 │  Static site: index.html + css/ + js/
│  data/versions.json         │  + data/v1/*.json. Fetched via fetch()
│  data/v1/*.json             │  at page load. Fail-safe: any missing or
└──────────────┬──────────────┘  invalid file → "data unavailable", no
               │                 partial rendering.
               ▼
┌─────────────────────────────┐
│  GitHub Pages               │  Deploys dashboard/ only, after JSON
│  (Actions: validate→deploy) │  validation passes. Public URL, $0.
└─────────────────────────────┘
```

## The export gatekeeper rule

`scripts/15_export_ui_json.py` (game model) and
`scripts/18_export_experimental_markets.py` (003A/003B) are the **only**
writers of the public data layer. Pipeline order is always:

**Model → calculations → export normalization → schema validation → JSON → dashboard.**

The model may legitimately produce missing values; the exporter converts
non-finite (NaN/±Infinity) to JSON-safe null and fails loudly if any
non-finite survives serialization. Contract: finite number → number,
missing/non-finite → null. No imputation, no manufactured values.

The dashboard never computes predictions. It renders what the exporters wrote.

## Public data layer

`data/ui_json/` (canonical) and `dashboard/data/` (deployed copy, kept
byte-identical by the sync step):

| File | Contents |
|---|---|
| `versions.json` | Manifest: model versions, default version label, generation timestamps |
| `v1/meta.json` | Week, season, generation time, model version facts |
| `v1/predictions.json` | Game predictions: V1 spread, market lines, edges, picks, QB overlay state |
| `v1/props.json` | Player prop projections (Model D) vs market lines |
| `v1/experimental_markets.json` | 003A receptions + 003B rush attempts (experimental, labeled) |
| `v1/teams.json` | Team ratings, ELO/EPA components |
| `v1/record.json` | Graded weekly record, W-L-push, CLV |
| `v1/clv.json` | Closing-line-value tracking |
| `v1/backtest.json` | Locked 2023–2025 walk-forward test summary |
| `v1/injuries.json` | Injury availability state, QB news, overlay audit surface |
| `v1/model_facts.json` | Frozen model facts: weights, methodology, honest verdict |

### Build contract: props confidence → uncertainty

The canonical exporter (`scripts/15_export_ui_json.py`) emits the key
`confidence` in `data/ui_json/v1/props.json`. The dashboard displays it as
**uncertainty** ("High/Medium/Low Uncertainty" — an Experiment 002
terminology fix). The dashboard JS applies a defensive normalization at
load: `pr.uncertainty ??= pr.confidence`, so canonical exports work without
a manual rename. Do not "fix" the exporter key without updating the
dashboard contract, and vice versa.

## What is NOT in the public path

- `experiments/` — 27 experiment directories, preregistrations, frozen
  artifacts, NULL results. Preserved in the repo for the research record;
  never loaded by the dashboard.
- `v2_research/` — frozen research program (all null). Not deployed.
- `data/` outside `ui_json/` — raw pulls, market snapshots, injury logs.
  Operational data, not served.
- `pft_sitemap.db` (~92MB harvest cache) — excluded from git; regenerable.
- `venv/`, `__pycache__/` — never committed.

## Data flow (Friday)

1. Human researches Friday market lines → `data/market_2026_w{N}.json`
   (manual input; the workflow refuses to run without it).
2. `29_qb_expectation.py` — records expected QB per team (append-only).
3. `27_injury_diff.py --freeze-friday` — Friday 18:00 CT injury cutoff.
4. `07_update_weekly.py` — game predictions (V1 frozen; ratings roll forward).
5. `11_injury_adjust.py` — QB availability overlay (adds, never rewrites V1).
6. `28_injury_audit.py` — persistent audit trail (refuses to overwrite).
7. `16/17/19` — prop projections (Model D yards; 003B rush attempts;
   003A receptions — experimental, additive).
8. `30_pull_prop_lines.py` — Friday prop lines (Bovada, keyless).
9. `15_export_ui_json.py --week N` + `18_export_experimental_markets.py --week N`
   — write the canonical public data layer.
10. Sync `data/ui_json/` → `dashboard/data/`, commit, push.
11. `deploy.yml` validates JSON, then deploys `dashboard/` to GitHub Pages.

Full detail: `docs/DATA_PIPELINE.md`. Runbooks: `docs/INJURY_PIPELINE_RUNBOOK.md`,
`docs/MARKET_LINES_RUNBOOK.md`, `docs/PROP_LINES_RUNBOOK.md`.

## Failure behavior

- Any pipeline step fails → the workflow stops; **nothing is committed**.
  The public site keeps serving the last good data with its original
  timestamps (staleness is visible, not hidden).
- Any dashboard data file missing/invalid at page load → the dashboard
  renders a "data unavailable" error and **nothing else**. It never shows
  partial predictions, never fabricates numbers, never falls back to stale
  data silently.
- Validation gates (exporter + deploy workflow) reject non-finite literals
  (`NaN`, `Infinity`) — the class of bug that once nearly broke a published
  build.

## Research safety

This architecture exists to serve a binding constraint: **same model, same
results, new ownership, new hosting.** The migration changes where bytes
live and how they are served. It does not change V1 methodology, V1
weights, Props Model D, frozen experiment artifacts, the locked 2023–2025
test, the Vault, preregistrations, timestamps, or any research conclusion.
The full rule set is `docs/DEPLOYMENT_SAFETY_RULES.md`; the pre-migration
audit is `docs/DEPLOYMENT_AUDIT.md`.
