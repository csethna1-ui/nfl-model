# DEPLOYMENT AUDIT — NFL Model: GitHub Ownership + Free Public Website Migration

**Audit date:** 2026-10-01 (Thu) ~15:45–16:00 CDT
**Auditor:** Scout (subagent), PHASE 1 of 16-phase migration
**Scope:** `~/workspace/nfl-model/` (read-only). Zero existing files were edited, moved, or deleted. No model, training, backtest, or experiment script was executed. Baseline checksums recorded separately at `docs/DEPLOYMENT_BASELINE_CHECKSUMS.txt` before any migration change.
**Binding rules:** `docs/DEPLOYMENT_SAFETY_RULES.md` — SAME MODEL, SAME RESULTS, NEW OWNERSHIP, NEW HOSTING.

---

## 1. INVENTORY (673 files excluding `venv/`)

### A. Python scripts — 66 in `scripts/`, 110 total in tree
- `scripts/`: 66 top-level files (numbered `01_`–`51_` pipeline/experiment scripts + `model_lib.py`, `injury_lib.py`, `qb_ratings.py`, `market_lines_latest.py`, `aggregate_player_games.py`, `pull_pbp_players.py`, `make_report_pdf.py`).
- Additional `.py` files live under `experiments/*/scripts/` (~44 more).
- Production-critical (Friday pipeline): `07_update_weekly.py`, `08_grade_week.py`, `11_injury_adjust.py`, `15_export_ui_json.py`, `16_prod_player_projection.py`, `17_prod_rush_attempts.py`, `19_prod_receptions.py`, `18_export_experimental_markets.py`, `26_pull_injuries.py`, `27_injury_diff.py`, `28_injury_audit.py`, `29_qb_expectation.py`, `30_pull_prop_lines.py`, `31_pull_market_lines_hourly.py`, `market_lines_latest.py`, `model_lib.py`, `injury_lib.py`, plus `22_tuesday_snapshot.py` / `23_friday_snapshot.py` / `24_timing_grade.py` (timing study).
- `scripts/__pycache__/`: build trash (43 `.pyc`), not committed.

### B/C/D. JavaScript / HTML / CSS — **ZERO in the repo**
No `.html`, `.js`, or `.css` files exist anywhere in `~/workspace/nfl-model/`. The public dashboard is the web artifact **`nfl-model-dashboard`** ("NFL Model Dashboard"), built and hosted by Muse's artifact runtime — the migration must reconstitute this dashboard as portable static files for GitHub Pages.

### E. JSON — 137 files
Key production JSON: `data/ui_json/v1/*.json` (10 files, the dashboard data layer — see §2), `data/market_2026_w{1..4}.json` (Friday researched lines), `data/market_props_2026_w{1..4}.json` (legacy Friday prop lines), `data/prop_v2_2026_w4{,_rush_attempts,_receptions}.json` (weekly prop projections), `data/predictions_2026_w{1..4}.provenance.json`, `data/calibration/winprob_v1.json`, `data/qb_point_values.json`, `data/ensemble_params*.json`, hourly snapshots under `data/market_hourly/{game_lines,prop_lines}/` (append-only, timestamped, never overwritten).

### F. Parquet/data files — 145 `.parquet`, 63 `.csv`
Largest in `data/`: per-season PBP `pbp_2018..2025.parquet` (8 files × ~19–20 MB ≈ 156 MB combined), `schedules_2018_2025.parquet`, `ratings_current_2026_w4.parquet` + provenance, weekly predictions CSVs, `record.csv`, `pick_results.csv`, `clv_picks.csv`, `games.csv`, injury/QB-expectation/timing-study stores.

### G. Pickle/model artifacts — 19 `.pkl`, zero `.pickle`/`.joblib`
- `data/gbm_final.pkl` (366 KB), `data/linear_models.pkl`, `data/linear_models_v2.pkl` (frozen V1 components)
- `data/prod_player_models_v2.pkl` (3.1 MB — frozen Model D, weekly prod engine)
- `experiments/props_experiment_003_market_expansion/003A_receptions/models/M{1,2}_verified_deployed.pkl` (1.1/1.2 MB), `003B_rush_attempts/models/M{1,2,3}_fitted.pkl` (424–468 KB)
- 9 role-transition pkls from Experiment 005 (607–880 KB each, null experiment — research archive only)

### H. Experiment directories — 27 under `experiments/`
Frozen nulls: 001–003, 005, 007, 008, 009, 010, 011 (shelved design), feature_discovery, information_frontier (PFT corpus, 97 MB), elo_regression_diagnostic, power_ranking, injury_adjustment_experiment, v1_architecture_audit, weight_generalization. Production-frozen PASS/M2 wins: player_props_projection (Model D), props_experiment_002 (terminology), props_experiment_003_market_expansion (003A/003B additive), props_experiment_005_role_transition (null, closed), props_experiment_006_role_mechanisms (prereg, not run), props_season_to_date_audit_2026, provenance_audit_2026_w4, experiment_006_information_timing (observational, live collection), external audits (gmalbert, multirepo, github_scan). Each carries PREREGISTRATION.md / RESULTS.md / frozen scripts + prediction parquets. **Must be preserved as the research archive (Phase 11).**

### I. Dashboard-related files
- Producer: `scripts/15_export_ui_json.py` → `data/ui_json/v1/*.json` (+ `data/ui_json/versions.json`); `scripts/18_export_experimental_markets.py` → `data/ui_json/v1/experimental_markets.json`.
- Consumer: Muse web artifact `nfl-model-dashboard`, slug `nfl-model-dashboard`, currently shared at `https://muse.ai/s/nfl-model-dashboard-exh6rjxlwxchxfxw`. **Data is embedded in the artifact at build/edit time** (confirmed by script 15's docstring: "the web artifact embeds these files at build/edit time"). No HTML/CSS/JS exists in the repo to reuse directly — the dashboard source must be recovered from the artifact (parent-agent work, e.g. `artifact.export` to a self-contained `.html`, then refactor).
- Key schema note (from `AGENTS.md`): canonical `data/ui_json/v1/props.json` emits the **`confidence`** key; the rename to **`uncertainty`** lives ONLY in the dashboard's embedded copy. Any re-embed must re-apply the rename or add a `pr.uncertainty ?? pr.confidence` fallback.

### J. Configuration files — effectively none
- **No** `requirements.txt`, `pyproject.toml`, `environment.yml`, or `Dockerfile` anywhere in the tree (full-depth find, venv excluded). Dependency manifest must be reconstructed in Phase 3.

### K. Cron/scheduled jobs (live, keep running against ORIGINAL paths per safety rules)
All owned by `goal:nfl-weekly-picks-spreadsheet` (plus unrelated fantasy/oura/tesla jobs out of scope):

| Job id | Schedule (America/Chicago) | Command(s) run | Paths touched |
|---|---|---|---|
| `nfl-picks-weekly-build` | Fri 18:20 | `08_grade_week.py` (grade W−1) → research market lines → `29_qb_expectation.py` → `27_injury_diff.py --freeze-friday` → `07_update_weekly.py` → `11_injury_adjust.py` → `28_injury_audit.py` → prop projector → `23_friday_snapshot.py` → `24_timing_grade.py` | `data/predictions_2026_w*.csv`, `data/market_2026_w*.json`, `data/qb_expectations/`, `data/injuries/`, `data/record.csv`, `data/timing_study/` |
| `nfl-grading-tuesday` | Tue 08:20 | `07_update_weekly.refresh_schedules()` (scores only) → `08_grade_week.py` → `15_export_ui_json.py --model-version V1` | `data/record.csv`, `data/ui_json/v1/*.json` |
| `nfl-injury-daily-pull` | daily 08:20 | `26_pull_injuries.py` → `27_injury_diff.py` | `data/injuries/`, `data/injuries/logs/` |
| `nfl-market-lines-hourly` | every 1h | `31_pull_market_lines_hourly.py` | `data/market_hourly/{game_lines,prop_lines}/` (append-only) |
| `nfl-timing-tuesday-snapshot` | Tue 08:20 | `22_tuesday_snapshot.py` (exp. 006) | `data/timing_study/` |

All run as `cd ~/workspace/nfl-model && ./venv/bin/python scripts/...` — the **absolute venv path is a coupling** (`22_tuesday_snapshot.py:91-93` even shells out to the hardcoded `/home/hatch/workspace/nfl-model/venv/bin/python`).

### L. Environment variables — **NONE referenced**
Zero matches for `os.environ` / `os.getenv` / `getenv` / `ENV[` in `scripts/*.py`. (One experiment script reads `EXP010_SMOKE` as a benign dev-mode flag; no production script uses env vars. Rest of `os.environ` hits are inside `venv/` third-party packages.)

### M. API integrations — all keyless public endpoints (3 hosts)
1. `github.com` — `scripts/30_v2_pull_sources.py:24`: `https://github.com/nflverse/nflverse-data/releases/download` (nflverse data, via `urllib.request.urlopen`)
2. `www.bovada.lv` — `scripts/30_pull_prop_lines.py`, `scripts/31_pull_market_lines_hourly.py`: `/services/sports/event/coupon/events/A/description/football/nfl?preMatchOnly=true&lang=en` (via `subprocess curl -s -m <timeout>`; User-Agent spoof header `Mozilla/5.0 (Windows NT 10.0; Win64; x64)`)
3. `site.api.espn.com` — `scripts/31_pull_market_lines_hourly.py:59`: `http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard` (**note `http://`, not `https://`** — worth hardening during deployment)

### N. External services — **NONE**
No paid APIs, no SaaS, no auth-required services. Everything is public-URL pull + local compute.

### O. Muse-specific dependencies — **NONE functional**
- Zero `muse.ai` URLs, zero artifact API calls (`sandbox://`, `artifact.create/invoke`), zero `/opt/hatch` / `HATCH_*` env vars, zero Hatch CLI usage in project code. (Matches for "hatch" are the Unix username in paths; matches for "muse" are NFL players Nick/Tanner Muse in raw CSVs.)
- Only docs-level mentions: `docs/PLAYER_PROJECTION_V2.md` ("The Friday cron is owned by the parent agent"), two experiment-doc bylines ("research subagent", "Auditor: Scout (subagent)").
- `venv/` contains a false positive: a comment referencing `github.com/pypa/hatch` (Python's unrelated hatch build tool) inside `packaging/`.
- `experiments/information_frontier_audit/pft_corpus/data/crawl.log` shows `host='hatch-egress-proxy'` traceback paths — runtime-proxy infra noise, not a project dependency.

### P. Absolute filesystem paths — **PERVASIVE (dominant code coupling)**
~45 scripts hardcode `DATA = "/home/hatch/workspace/nfl-model/data"` (07, 08, 11, 13, 14, 15, 17, 18, 19, 24, 26, 27, 28, 29, plus v2/experiment scripts), `sys.path.insert(0, "/home/hatch/workspace/nfl-model/scripts")` (06, 07, 11, 12, 22, 23, 27, 28, 29), `REPO = "/home/hatch/workspace/nfl-model"` (experiment scripts). `scripts/make_report_pdf.py` writes **outside the tree** (`~/workspace/your_files/nfl-picks/nfl-model-report.pdf`). Log JSONLs (`data/injuries/logs/*`, `data/qb_expectations/logs/*`) embed absolute `dest` paths — data, not code, but they leak the host layout into committed files.
- No `/tmp/`, `/root/`, or `Path.home()` references in `scripts/*.py`.

### Q. Relative filesystem paths — mixed
Portable pattern already exists in-code and should be copied in Phase 3/4: `os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")` (30, 31, `market_lines_latest.py`), `ROOT = Path(__file__).resolve().parents[1]` (18, 45–49), `os.path.expanduser("~/workspace/nfl-model")` (16, 17, 19, 10, aggregate/pull scripts). Script 15 hardcodes `/home/hatch/...` — must be switched to the `__file__`-relative idiom.

### R. Secrets/API keys/tokens — **NONE found**
No real credentials, keys, tokens, passwords, or auth headers anywhere in the tree. Docs explicitly state the keyless posture (`MARKET_LINES_RUNBOOK.md`, `PROP_LINES_RUNBOOK.md`, `PLAYER_PROJECTION_V2.md`: "no API key, no card", "Keyless data only").

### S. Data-generation pipelines
Friday flow (see §2). Injury/QB plumbing: 26 → 27 (daily pulls + Friday freeze `data/injuries/availability_friday_2026_w{N}.json`, refuses overwrite) → 29 (QB expectations parquet, append-only, refuses overwrite) → 11 (overlay, writes in place to the predictions CSV — preserves raw V1 columns, adds overlay columns) → 28 (audit parquet, refuses overwrite). Market lines: 30 (Friday prop lines → `data/market_props/`) and 31 (hourly game+prop snapshots, dual-sourced DK-via-ESPN + Bovada; `market_lines_latest.py` exposes `latest_snapshot` / `snapshot_at_or_before` for the Friday 18:00 CT cutoff selector). Props: 16 (Model D yards engine: `--refresh` keyless nflverse pulls → `--fit` reproduce frozen fit, `--season/--week` predict → `data/prop_v2_2026_w{N}.json`), 17 (003B rush attempts → `..._rush_attempts.json`), 19 (003A receptions → `..._receptions.json`).

### T. Dashboard-generation pipelines
15 (game/props/teams/performance/record/CLV/injuries/backtest/model_facts JSON) + 18 (experimental markets JSON). Republish path today: parent agent `artifact.edit` on `nfl-model-dashboard` with the re-embedded JSON (standing authorization to publish each checkpoint automatically).

---

## 2. DASHBOARD DATA FLOW (exact)

```
Friday ~18:00 CT freeze
  market research (manual, bet365/DraftKings) → data/market_2026_wN.json
  29_qb_expectation.py  → data/qb_expectations/qb_expected_2026_wN.parquet
  27 --freeze-friday     → data/injuries/availability_friday_2026_wN.json
  07_update_weekly.py   → data/predictions_2026_wN.csv (+ ratings, schedules)
  11_injury_adjust.py   → injury-checked predictions CSV (overlay cols added)
  28_injury_audit.py    → data/injuries/audit/audit_2026_wN.parquet
  16/17/19 --refresh    → cached keyless pulls (nflverse/NGS)
  16 --season 2026 --week N --market-json data/market_props_2026_wN.json
                        → data/prop_v2_2026_wN.json          (Model D yards)
  17 --season 2026 --week N → data/prop_v2_2026_wN_rush_attempts.json (003B)
  19 --season 2026 --week N → data/prop_v2_2026_wN_receptions.json    (003A)
  30_pull_prop_lines.py → data/market_props/market_props_2026_wN.json
  15_export_ui_json.py  → data/ui_json/v1/{meta,predictions,record,clv,backtest,
                          teams,props,injuries,model_facts}.json
  18_export_experimental_markets.py → data/ui_json/v1/experimental_markets.json
Tuesday ~08:20 CT: refresh scores → 08_grade_week.py → data/record.csv →
  15_export_ui_json.py refreshes Performance/Record JSON
Daily 08:20: injury pull/diff (26,27) · Hourly: market lines (31)
Parent agent: artifact.edit → nfl-model-dashboard republished at
  https://muse.ai/s/nfl-model-dashboard-exh6rjxlwxchxfxw (web_static, embedded JSON)
```

**Critical coupling to flag for later phases:** the exporters hardcode the *current week*:
- `15_export_ui_json.py`: `predictions_2026_w4.csv`, `ratings_current_2026_w4.parquet`, `"latest_week": 4`, `"week": 4` — week is a **code literal**, not a `--week` argument. Each new week requires editing the exporter (deployment change, bucket 2 — does not alter model outputs since it only selects which canonical CSV is exported).
- `18_export_experimental_markets.py:20-21`: `RUSH_SRC`/`REC_SRC` hardcode `prop_v2_2026_w4_{rush_attempts,receptions}.json`.
- The `props.json` section of 15 auto-globs the latest `prop_v2_2026_w*.json` (portable), and game/prop `_live` lines are joined from the latest hourly snapshot (`market_lines_latest.latest_snapshot`) with a safe fallback to the Friday files — display only, never touching evaluation numbers.

---

## 3. SIX-BUCKET CLASSIFICATION

**Bucket 1 — Works unchanged on GitHub Pages:** the `data/ui_json/v1/*.json` files themselves (static JSON, `allow_nan=False` gatekept, UI-ready); all markdown docs; experiment RESULTS/PREREGISTRATION reports.

**Bucket 2 — Needs a small deployment change:** hardcoded `/home/hatch/...` paths (~45 scripts → `__file__`-relative `DATA_ROOT`); script 15/18 hardcoded `w4` literals → `--week` parameterization; ESPN `http://` → `https://`; `22_tuesday_snapshot.py` hardcoded venv interpreter path; missing `requirements.txt` (reconstruct: Python 3.12, scikit-learn, pandas, numpy, pyarrow, polars, requests, openpyxl, statsmodels, scipy, beautifulsoup4, lxml, warcio, `nfl_data_py` — **note:** installed in venv from a local wheel `/tmp/nfld/nfl_data_py-0.3.3-...whl`; that path won't exist elsewhere — must reinstall from PyPI or vendor the wheel; `python-dotenv`, `tqdm`, `joblib`, `patsy`, `pydantic` present); `make_report_pdf.py` out-of-tree write path; User-Agent spoof header (document, keep as-is); log JSONLs embedding host paths (fine as research data, exclude from public layer).

**Bucket 3 — Requires a backend/service:** **NONE identified.** No server/listener code exists (zero localhost/port matches); the dashboard is a read-only consumer of static JSON; all computation is batch. GitHub Actions can run the full pipeline (subject to runtime limits); GitHub Pages can serve everything. No backend should be introduced.

**Bucket 4 — Requires a secret:** **NONE.** Fully keyless: nflverse GitHub releases, ESPN public scoreboard API, Bovada public coupon API. Cale declined the free Odds API key (2026-10-01); sourcing stays keyless-only.

**Bucket 5 — Cannot safely be made public / should not be committed:** nothing credential-bearing exists. Exclusion is about size/weight, not secrecy (see §4). One caution: raw `data/v2/raw/injuries_*.csv` contains NFL player names (Nick Muse, Tanner Muse — false positives in the "muse" search) — public already via nflverse; fine.

**Bucket 6 — Muse-specific, must be removed/replaced:** the dashboard's *hosting mechanism* itself — the `nfl-model-dashboard` web artifact is Muse's proprietary runtime (no portable source in the repo). Replace with GitHub Pages static site; dashboard source must be recovered (parent-agent `artifact.export` or rebuild) and re-embedded with the same JSON. Everything else (code, data, crons' logic) has zero Muse-platform coupling.

---

## 4. SIZE / EXCLUSION NOTES

- `venv/` 795 MB — **never committed**. Replaced by `requirements.txt` + GitHub Actions setup.
- `data/` 214 MB; `experiments/` 166 MB. Only **one file >50 MB**: `experiments/information_frontier_audit/pft_corpus/data/pft_sitemap.db` (91.4 MB — exceeds GitHub's 100 MB hard limit per file, fine as-is; git **soft limit is 50 MB** so it will warn). `data/pbp_2018..2025.parquet` (156 MB combined across 8 files) + `pbp_2018_2025.parquet` are the other heavies.
- Recommend: **exclude** `venv/`, `scripts/__pycache__/`, `data/backups/`, `data/retired/`, PFT corpus raw fetches beyond the FINAL pilot report artifacts (or keep in a separate archive repo/release), `.bak_espnid` misc files. **Keep as research archive** (Phase 11): all `experiments/` PREREGISTRATIONS/RESULTS/frozen scripts/frozen model pkls/locked prediction parquets — these are small except noted above; large-but-research-essential parquets can go in a GitHub Release asset or separate archive branch.
- Public website needs only `data/ui_json/v1/*.json` (~732 KB total) — keep the public data layer tiny by design (Phase 4). Do NOT commit raw PBP corpora to the Pages branch; keep them in the repo proper (or LFS/Release) for reproducibility of the weekly runs.

---

## 5. STATIC-HOSTING VERDICT

**YES — the dashboard can run as a pure static site on GitHub Pages.** All dashboard content is precomputed JSON read by client-side rendering; there is no server-side Python at view time, no auth, no fetch at runtime (the current artifact embeds data at build). The architecture collapses to: GitHub repo → Actions (weekly data regeneration, optional) → Pages (static HTML/CSS/JS + `data/` JSON). No backend, $0/month.

### Top 5 deployment blockers (ordered by severity)

1. **No portable dashboard source exists.** The production dashboard lives only inside Muse's web-artifact runtime (`nfl-model-dashboard`); zero HTML/CSS/JS in the repo. Phase 6 must recover it (`artifact.export` → self-contained HTML, then split into repo files) before anything can be published to Pages. Until then there is no website to deploy.
2. **No dependency manifest; local-wheel install.** No `requirements.txt`/lockfile; `nfl_data_py` was installed from a `/tmp/nfld/*.whl` that no longer exists on any other machine. Reproducible installs (Actions or any new host) require reconstructing and testing the manifest from the venv — failure here silently changes numeric outputs (e.g. different sklearn version).
3. **Pervasive hardcoded `/home/hatch/...` paths** in ~45 scripts (all production scripts: 07, 08, 11, 15, 16, 17, 19, 26–29). Any repo clone, any Actions runner, any other host breaks. Must be switched to the `__file__`-relative idiom that already exists in 18/30/31/`market_lines_latest.py`. Output-identical verification required per the safety rules.
4. **Exporters hardcode the current week (`w4`)** instead of taking `--week`: 15 and 18 embed week-4 literals in file selection and JSON fields. Automation cannot advance weeks without a code edit each Friday — must be parameterized, with baseline-checksum verification that the parameterization reproduces the same bytes for W4.
5. **Weekly data regeneration is semi-manual by design.** The Friday pipeline includes manual research steps (market lines from bet365/DraftKings, QB-news checks) that cannot run inside GitHub Actions; the hourly market-line capture, daily injury pull, and Tuesday snapshot likewise run on Muse crons today. A fully automated Actions replacement can cover keyless pulls (nflverse, ESPN, Bovada) but the manual research steps need a documented human-in-the-loop process — the site must fail safe (stale-data banners, no fabricated predictions) when inputs are missing.

---

## 6. PUBLIC VS PRIVATE (security summary)

Nothing in the tree contains API keys, passwords, tokens, private credentials, account IDs, or secret endpoints — verified by credential-pattern grep across the full tree (auth-related hits were prose only: "Human authorization of the V2-A..E protocol", "Hard rules (from the authorization)"). The `.env.example` for Phase 5 is therefore placeholder-only (no secrets to mirror); `.gitignore` must exclude `venv/`, `__pycache__/`, `data/backups/`, `data/retired/`, log JSONLs with host paths, and the 91 MB sitemap DB (soft-limit warn) or document its retention. No personal information beyond what's already public (NFL player names from nflverse).

---

## 7. PHASE 1 GATE CHECK

- [x] Complete inventory by category (A–T)
- [x] Project-wide search for muse.ai / Muse deps / absolute paths / localhost / env vars / credentials / private URLs / auth assumptions / view-time Python deps / non-portable local-file refs
- [x] Six-bucket classification of every dependency found
- [x] Baseline sha256 of `data/ui_json/v1/*` + `data/ui_json/versions.json` → `docs/DEPLOYMENT_BASELINE_CHECKSUMS.txt` (new file, recorded 2026-10-01 before any change)
- [x] Size/exclusion notes (>50 MB file flagged; venv/experiments/PFT/data weights documented)
- [x] Precise Friday-pipeline → dashboard data flow
- [x] Static-hosting verdict + top 5 blockers
- Constraints honored: read-only except the two new files (`DEPLOYMENT_AUDIT.md`, `DEPLOYMENT_BASELINE_CHECKSUMS.txt`); no model/training/backtest/experiment scripts run; nothing pushed; no artifact edits/exports performed.

Nothing in this audit changes V1 methodology, weights, the locked 2023–2025 test, the Vault, any frozen experiment artifact, or any research conclusion.
