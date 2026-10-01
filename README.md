# NFL Prediction Model

An NFL game + player-prop prediction research project with a public static
dashboard. **Same model, same results, new ownership, new hosting** — this
repository is a migration of the research project to the owner's GitHub with
free static hosting. No model, weight, experiment, or research conclusion was
changed in the move.

## Model Status (read this first)

- **V1 game model** (ELO + EPA + gradient-boosting ensemble, weights 40/50/10,
  frozen): honest verdict is **no verified betting edge**. Walk-forward
  backtest on the locked 2023–2025 test: 52.8% ATS / +0.9% ROI — inside
  statistical noise. The market out-predicts it. **Totals are never played.**
- **Player props** (Model D, frozen): projections vs market lines for
  research. **Experimental markets** 003A (receptions) and 003B (rush
  attempts) showed locked-test improvements but live persistence is **not
  established** — they are labeled experimental and monitored, neither proven
  nor failed.
- **Everything here is paper-tracked research.** Nothing is presented as a
  proven edge or +EV. Never bet on the basis of these outputs.

## Live dashboard

`https://<owner>.github.io/<repo>/` — static site, $0/month hosting.
(Data: generated JSON; no Python runs at view time.)

## Repository layout

| Path | What |
|---|---|
| `dashboard/` | Public static site (`index.html`, `css/`, `js/`, `data/`). Deployed to GitHub Pages. |
| `data/ui_json/` | Canonical public data layer — written **only** by `scripts/15` and `scripts/18`. |
| `scripts/` | Pipeline: weekly predictions, injury overlay, props, exporters. All paths repo-relative. |
| `experiments/` | Research archive: 27 experiments, preregistrations, frozen artifacts, NULL results — preserved intact. |
| `v2_research/` | Frozen research program (all challengers null). |
| `docs/` | Runbooks, audit, architecture, deployment docs. |
| `.github/workflows/` | `deploy.yml` (validate → Pages) and `update-data.yml` (manual weekly pipeline). |

## Quick start

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cd dashboard && python3 -m http.server 8000   # open http://localhost:8000/
```

No API keys needed — all data sources are keyless (nflverse, Bovada, ESPN).

## Docs

- `docs/ARCHITECTURE.md` — system design, export gatekeeper rule, failure behavior
- `docs/DATA_PIPELINE.md` — what generates the dashboard data, cadence, failure behavior
- `docs/LOCAL_DEVELOPMENT.md` — local setup, regeneration, validation
- `docs/DEPLOYMENT.md` — GitHub Pages + Actions, first-time setup, rollback
- `docs/DEPLOYMENT_AUDIT.md` — pre-migration audit
- `docs/DEPLOYMENT_SAFETY_RULES.md` — binding constraints (what the migration may not change)
- `docs/INJURY_PIPELINE_RUNBOOK.md` — QB/injury overlay rules
- `docs/MARKET_LINES_RUNBOOK.md` — hourly market snapshots

## License

MIT — see `LICENSE`.
