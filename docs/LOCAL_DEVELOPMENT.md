# Local Development

## Prerequisites

- Python 3.12
- `pip install -r requirements.txt` (pinned; includes `nfl_data_py==0.3.3`)
- No API keys. All data sources are keyless (nflverse GitHub releases,
  Bovada public coupon API, ESPN scoreboard API).

## First run

```bash
git clone <this-repo>
cd <this-repo>
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## Preview the dashboard locally

The dashboard is static — any static file server works:

```bash
cd dashboard
python3 -m http.server 8000
# open http://localhost:8000/
```

The page fetches `data/versions.json` and `data/v1/*.json` relative to the
site root. It shows a loading state, then renders. If a data file is missing
or invalid, it renders a "data unavailable" error instead of partial content.

## Regenerate the public data layer

The exporters are the gatekeepers — they are the only writers of
`data/ui_json/`:

```bash
# Game model JSON (predictions, props, teams, record, clv, backtest, injuries, meta, model_facts)
./venv/bin/python scripts/15_export_ui_json.py --week 4

# Experimental markets JSON (003A receptions, 003B rush attempts)
./venv/bin/python scripts/18_export_experimental_markets.py --week 4
```

`--week` auto-detects the latest week when omitted. The exporters fail loudly
on non-finite values and validate their output schema.

After regenerating, sync the deployed copy and verify byte-identity:

```bash
cp data/ui_json/v1/*.json dashboard/data/v1/
cp data/ui_json/versions.json dashboard/data/versions.json
diff -r data/ui_json dashboard/data   # must be silent
```

Commit both trees together.

## Run the weekly pipeline (Friday)

The full Friday sequence is documented in `docs/DATA_PIPELINE.md` and encoded
in `.github/workflows/update-data.yml` (manual trigger). In short:

1. Commit the human-researched `data/market_2026_w{N}.json` first — the
   pipeline refuses to run without it.
2. `29` (QB expectations) → `27 --freeze-friday` (injury cutoff) →
   `07` (predictions) → `11` (injury overlay) → `28` (injury audit).
3. `16 --refresh` + `16/17/19` (props) → `30` (prop lines).
4. `15 --week N` + `18 --week N` (exporters).
5. Validate, sync to `dashboard/data/`, commit, push.

See `docs/INJURY_PIPELINE_RUNBOOK.md` for the QB/injury overlay rules and
`docs/MARKET_LINES_RUNBOOK.md` for the hourly market snapshots.

## Repository-relative paths

All scripts resolve paths from the repository root (`pathlib.Path(__file__).resolve().parent.parent` or equivalent). There are no hardcoded absolute paths in `scripts/`. Do not reintroduce any — CI and other contributors' machines will not have your home directory.

## What not to touch

Per `docs/DEPLOYMENT_SAFETY_RULES.md`:

- `scripts/` model, training, backtest, and experiment code — frozen.
- `experiments/` — the research archive, including all NULL results.
- `data/ui_json/` by hand — only the exporters write it.
- Timestamps, as-of dates, freeze logic, version labels.

If a deployment change could alter any model output: **stop and report**
instead of changing it silently.

## Validate before pushing

```bash
# JSON validity + non-finite gate (mirrors deploy.yml)
python3 - <<'EOF'
import json
from pathlib import Path
for p in sorted(Path("dashboard/data").rglob("*.json")):
    raw = p.read_text()
    assert "NaN" not in raw and "Infinity" not in raw, p
    json.loads(raw)
print("data layer OK")
EOF
node --check dashboard/js/app.js   # JS syntax
```

The `deploy.yml` workflow re-runs the JSON validation on every push to
`main` and blocks deployment if it fails.
