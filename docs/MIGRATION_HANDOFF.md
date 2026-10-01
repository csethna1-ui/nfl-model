# Ownership Handoff Report — NFL Model GitHub Migration

**Date:** 2026-10-01
**Staging repo:** `~/workspace/nfl-model-github/` (383MB, venv excluded)
**Target:** Cale's GitHub account (`csethna1-ui`) → GitHub Pages, $0/month
**Status:** READY FOR PUSH APPROVAL — Phases 0–11, 14–16 complete; Phases 12–13 blocked on your go-ahead.

## What was built

A complete, push-ready Git repository staging copy of the NFL model project,
restructured for free static hosting with **zero changes** to any model,
weight, experiment, timestamp, or research conclusion.

**Same model / same results / new ownership / new hosting.**

## Architecture (the short version)

- **Model pipeline** (Python, keyless data) runs on schedule → exporters
  (`scripts/15`, `scripts/18`) write versioned JSON to `data/ui_json/`.
- **Dashboard** (`dashboard/`) is static HTML/CSS/JS on **GitHub Pages**.
  It fetches the JSON at load; no Python runs at view time, no backend,
  no API keys, no database.
- **Deploy** (`deploy.yml`): validates all 11 JSON files (parse + no-NaN gate
  + manifest check) → deploys `dashboard/` only. Validation failure blocks
  the deploy; the old site keeps serving.
- **Weekly update** (`update-data.yml`): **manual trigger only** — runs the
  Friday pipeline in exact cron order (29 → 27 freeze → 07 → 11 overlay →
  28 audit → 16/17/19 props → 30 lines → 15/18 export), validates, syncs
  `data/ui_json/` → `dashboard/data/`, commits, pushes. Not scheduled: the
  Friday flow needs your researched market lines and QB-news judgment first.

## What changed vs the live project (regression-verified)

Full `diff -rq` between `~/workspace/nfl-model/` and staging:

- **Exactly 50 scripts differ** — all mechanical: `/home/hatch/workspace/nfl-model`
  → repo-relative `REPO_ROOT` paths; `sys.executable` in one; `--week`
  auto-detection added to the two exporters; one PDF output path moved inside
  the repo; one ESPN URL http→https. Zero model-logic changes (verified hunk
  by hunk; all non-path hunks are `import os`, argparse, and week detection).
- **Zero data, experiment, or doc files modified.** `data/` and `experiments/`
  are byte-identical (the only exception: `props_experiment_006_role_mechanisms/`,
  which changed in the live project *after* the snapshot because the authorized
  006 DEV run is still in progress there — re-sync at push time).
- **11/11 public data checksums match** the pre-migration baseline
  (`docs/DEPLOYMENT_BASELINE_CHECKSUMS.txt`).
- **New files only:** `dashboard/` (split static site), `.github/workflows/`
  (2 workflows), `requirements.txt` (pinned), `.gitignore`, `.env.example`,
  `LICENSE` (MIT, © 2026 Cale Sethna), `README.md`, and 4 new docs
  (`ARCHITECTURE`, `DATA_PIPELINE`, `LOCAL_DEVELOPMENT`, `DEPLOYMENT`).

## Dashboard verification (done locally)

- Split from the 821KB single-file artifact into `index.html` (3KB shell) +
  `css/styles.css` + `js/app.js` + 11 JSON data files.
- Loader fetches JSON with `cache: 'no-store'`; shows loading state; **fails
  closed** ("data unavailable", renders nothing) if any file is missing or
  invalid — never partial predictions.
- `pr.uncertainty ??= pr.confidence` fallback present (canonical exporter
  emits `confidence`; dashboard displays `uncertainty`).
- `dashboard/data/` is **byte-identical** to the canonical exporter output
  `data/ui_json/` (not the stale embedded copy — the embedded copy was two
  generations behind: missing `market_live_books`, older injury pull).
- All assets + data served HTTP 200 locally; JS syntax valid.
- No secrets, no `/home/hatch` leaks, no personal info in the public surface.

## Two bugs found and fixed during the build

1. **`update-data.yml` used wrong CLI args** (drafted before checking argparse:
   missing `--season`, wrong `11_injury_adjust.py` args, missing `29_qb_expectation.py`
   step). Rewritten from the actual Friday cron invocations.
2. **`deploy.yml` validation would have failed every deploy**: it checked
   `(root / 'V1').is_dir()` but the exporter writes `"default": "V1"` (label,
   uppercase) while the directory is lowercase `v1`. Fixed to case-insensitive.

## What's intentionally NOT in the push

- `venv/` (795MB), `__pycache__/`, `*.pyc` — ignored.
- `pft_sitemap.db` (92MB harvest cache) — ignored via `*.db`; the PFT research
  record is preserved through scripts, reports, and derived results.
- No secrets/tokens/keys exist in the repo (swept); `.env.example` documents
  the (empty) contract.

## Blocked items — your approval needed

**Phase 12 (deploy) is BLOCKED on one decision: approve creating the GitHub
repository and pushing.** Per your rule, nothing has been pushed. When you
approve, I will:

1. Re-sync `experiments/` + `data/` from the live project (to capture the
   finished 006 DEV work), re-verify checksums.
2. `git init`, commit (~383MB first push), create the repo under `csethna1-ui`,
   push via your connected GitHub account.
3. Enable GitHub Pages (source: GitHub Actions), run `deploy.yml`.
4. **Phase 13:** QA the public URL at 1280/1440/1920 + 375/390/430 viewports,
   console/network/404 checks, all tabs and states.

**Until then:** the live Friday/Tuesday/hourly crons keep running against
`~/workspace/nfl-model/` unchanged. The muse.ai dashboard link stays the public
URL. Nothing is half-migrated.

## Docs for the new repo

`README.md` (with the honest Model Status section: no verified edge, totals
never played, experimental markets labeled), `docs/ARCHITECTURE.md`,
`docs/DATA_PIPELINE.md`, `docs/LOCAL_DEVELOPMENT.md`, `docs/DEPLOYMENT.md`,
`docs/DEPLOYMENT_AUDIT.md`, `docs/DEPLOYMENT_SAFETY_RULES.md`, plus the
existing runbooks. License: MIT.

## One-line verdict

The migration is complete and verified except the push itself: **say the word
and I'll create the repo, push, deploy to Pages, and QA the public URL.**

## Deployment record (2026-10-01)

- Repository: https://github.com/csethna1-ui/nfl-model (public, owner csethna1-ui)
- Pushed via one-time classic PAT (repo + workflow scopes), used transiently and discarded after push. **PAT revocation is UNCONFIRMED — the owner still needs to delete/revoke it in GitHub Settings → Developer settings → Personal access tokens.** The local git remote was scrubbed of the token (origin is now the plain HTTPS URL); no token remains in the assistant's files. Never reproduce or reuse the old token.
- Commits: c776c32b (full migration, 758 files) + d071b02c (removed binary-transfer test file)
- GitHub Pages: enabled via API, build_type=workflow
- Public URL: https://csethna1-ui.github.io/nfl-model/
- Deploy workflow "Validate and Deploy Dashboard": completed success on first run
- Data verification: all 11 dashboard JSON files byte-identical between live site and canonical exporter output
- 006 experiment re-synced from live before push (clean NULL verdict 2026-10-01)
- Live crons in ~/workspace/nfl-model/ UNCHANGED (still active; handoff pending QA pass)
- Old Muse dashboard URL remains active until QA passes
