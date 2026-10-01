# Deployment

## Hosting: GitHub Pages ($0/month)

The public site is the static `dashboard/` directory served by GitHub Pages.
There is no server, no build step, no backend, no database, and no API key
anywhere in the serving path.

- **Source:** the `dashboard/` directory in this repo.
- **Deploys:** automatically on push to `main` (via `.github/workflows/deploy.yml`),
  or manually from the Actions tab (`workflow_dispatch`).
- **URL:** `https://<owner>.github.io/<repo>/` (set after the first deploy;
  recorded here once known).

## How a deploy works (`deploy.yml`)

Two jobs, sequential:

1. **validate** — checks out the repo and runs the data-layer gate:
   - all 11 required JSON files exist under `dashboard/data/`
     (`versions.json`, `v1/meta|predictions|props|teams|record|clv|backtest|injuries|model_facts.json`,
     `v1/experimental_markets.json`)
   - every file parses as JSON
   - no `NaN` / `Infinity` / `-Infinity` literals (same gate as the exporter)
   - `versions.json` default matches a version label or data directory
     (case-insensitive — the exporter writes `"default": "V1"`, the directory
     is lowercase `v1`)
   - `dashboard/index.html`, `js/app.js`, `css/styles.css` exist
   - any failure → the workflow stops, **nothing deploys**
2. **deploy** — uploads `dashboard/` as the Pages artifact and deploys it
   via the official `actions/deploy-pages`.

The workflow triggers on pushes to `main` that touch `dashboard/**`,
`data/ui_json/**`, or the workflow file itself.

## How data updates ship (`update-data.yml`)

Manual trigger only (Actions → "Update Model Data" → Run workflow), with
`season` and `week` inputs. It is **not scheduled**: the Friday pipeline has
human inputs (researched market lines, QB-news judgment) that must be
committed first.

The workflow:

1. Installs dependencies from `requirements.txt`.
2. Fails loudly if `data/market_{season}_w{week}.json` (human-researched
   Friday lines) is missing.
3. Runs the pipeline in Friday order: `29` → `27 --freeze-friday` →
   `07` → `11` → `28` → `16/17/19` (+`--refresh`) → `30` → `15` → `18`.
4. Validates the exporter outputs (JSON parses, no non-finite literals,
   all required files present).
5. Syncs `data/ui_json/` → `dashboard/data/` (byte-identical).
6. Commits and pushes — which triggers `deploy.yml`, which re-validates and
   deploys.

If any step fails, the workflow stops before committing. The live site keeps
serving the last good week.

## First-time setup (repository owner)

1. Push this repo to GitHub.
2. Repository → Settings → Pages → Source: **GitHub Actions**.
3. Push to `main` (or run `deploy.yml` manually) — the site goes live at
   `https://<owner>.github.io/<repo>/`.
4. No secrets, no environment variables, no custom domain required.

## Rollback

Every deploy is a git commit. To roll back the site: revert the
`dashboard/data/` + `data/ui_json/` commit and push — `deploy.yml`
re-validates and redeploys the previous good state. The dashboard's own
fail-safe also means a bad data push surfaces as an explicit error page,
never as silently wrong predictions.

## What deployment never does

- Run model, training, backtest, or experiment code (nothing in `scripts/`
  executes at deploy time except the update workflow's explicit pipeline).
- Modify weights, methodology, frozen artifacts, timestamps, or research
  conclusions.
- Require credentials, API keys, or paid services.
