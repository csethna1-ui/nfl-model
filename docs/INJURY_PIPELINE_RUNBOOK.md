# Injury Pipeline Runbook — Phase 1 (production plumbing)

**What this is:** automated injury awareness for the NFL model. It makes the
system actually *know* the current injury state instead of relying solely on
Friday hand-researched `qb_news`. It is a production bug fix, not a research
experiment: V1's prediction logic is untouched and no model is fit.

**Policy change 2026-10-01 ("show adjusted, don't void"):** the pipeline no
longer auto-voids picks when a starting QB is out. It shows the
backup-adjusted prediction *alongside* the frozen V1 number — the overlay
explains the prediction rather than rewriting the model's historical output.
Raw and adjusted are recorded separately so later backtesting can test
whether the adjustment adds information. The adjusted prediction is an
**experimental derived overlay**, never a V1 rerun.

**What it is NOT:** injury-based margin adjustments to V1 itself,
player-projection adjustments, and PFT/news integration are explicitly out
of scope — those need separately preregistered experiments.

---

## Components

| Script | Job |
|---|---|
| `scripts/26_pull_injuries.py` | Daily nflverse pull → versioned snapshot |
| `scripts/27_injury_diff.py` | Diff snapshots; rebuild live availability; Friday freeze |
| `scripts/injury_lib.py` | Shared: paths, availability builder, starter/backup resolution, logging |
| `scripts/11_injury_adjust.py` | QB availability overlay: preserves V1 raw, emits expected QB, QB shift, adjusted prediction, raw/adjusted edges, final status (PICK / NO PLAY / VETOED), double-count-risk flag. Manual `qb_news` > recorder > frozen auto state |
| `scripts/28_injury_audit.py` | Per-week audit table: what was known at cutoff and what the overlay did (keep / vetoed / noted) |
| `scripts/29_qb_expectation.py` | **QB-expectation record** (v2 rule — primary automated QB source for the overlay; see below) |
| `scripts/15_export_ui_json.py` | Exports `injuries.json` + per-game `qb_overlay` block in `predictions.json` for the dashboard |

### Data layout (`data/injuries/`)

- `snapshots/injuries_YYYY-MM-DD.parquet` — one per day, **never overwritten**.
  Each carries `pulled_at` + `snapshot_day` columns.
- `availability_current.json` — rebuilt after every pull/diff. **Live view.**
- `availability_friday_2026_w<N>.json` — frozen once per week at the Friday
  18:00 CT cutoff. **The Friday prediction reads only this file.**
- `audit/audit_2026_w<N>.parquet` — persistent per-week audit table
  (see below). Written once per week after the overlay layer; **never overwritten**.
- `logs/pull_log.jsonl` — one record per pull (rows, weeks, status distribution).
- `logs/diff_log.jsonl` — one record per diff (new out/doubtful/questionable,
  status changes, starting-QB flags) + Friday-freeze events.
- `logs/void_disposition.jsonl` — one record per overlay decision
  (game, player, status, source=manual|recorder|auto, action=keep|vetoed|noted,
  v1_spread, qb_shift_pts, adj_spread, edge_before/after, double_count_risk,
  stale_qb_veto). Legacy pre-2026-10-01 void/survive records remain for
  archaeology; the audit table reads overlay-era records only.
- `logs/audit_log.jsonl` — one record per audit-table write (week, rows,
  vetoes, overrides, output path, cutoff + cutoff note).

### Availability record fields

Per injury: player, team, position, week, `report_status` (OUT/DOUBTFUL/
QUESTIONABLE/LIMITED/FULL as the feed provides), `practice_status`
(DNP/Limited/Full), `primary_injury`. Starting-QB entries add
`is_expected_starter` and `triggers_void`.

---

## Running it

```bash
# Daily pull (never overwrites; skips if today's snapshot exists)
./venv/bin/python scripts/26_pull_injuries.py --season 2026

# Diff latest vs previous snapshot, rebuild live availability
./venv/bin/python scripts/27_injury_diff.py

# Diff two explicit days (backfill / investigation)
./venv/bin/python scripts/27_injury_diff.py --from 2026-10-02 --to 2026-10-03

# Friday 18:00 CT: freeze the availability for the prediction cutoff
./venv/bin/python scripts/27_injury_diff.py --freeze-friday --season 2026 --week 5

# QB availability overlay with automated state (Friday flow uses the frozen file)
./venv/bin/python scripts/11_injury_adjust.py --season 2026 --week 5 \
    --predictions-csv data/predictions_2026_w5.csv \
    --market-json data/market_2026_w5.json \
    --injury-state data/injuries/availability_friday_2026_w5.json \
    --expected-qb data/qb_expectations/qb_expected_2026_w5.parquet

# Audit table: run AFTER the overlay layer, every Friday
./venv/bin/python scripts/28_injury_audit.py --season 2026 --week 5
# (writes data/injuries/audit/audit_2026_w5.parquet; refuses to overwrite)
# Mid-week re-run without a Friday freeze (cutoff recorded honestly):
# ./venv/bin/python scripts/28_injury_audit.py --season 2026 --week 5 --no-freeze

# Ad-hoc weekend re-check against the live view (does NOT touch Friday outputs)
./venv/bin/python scripts/11_injury_adjust.py --season 2026 --week 5 \
    --predictions-csv /tmp/pred_w5_recheck.csv \
    --market-json data/market_2026_w5.json \
    --injury-state data/injuries/availability_current.json

# Dashboard export (injuries.json block)
./venv/bin/python scripts/15_export_ui_json.py --model-version V1
```

Without `--injury-state`, `11_injury_adjust.py` uses manual `qb_news` plus the
recorder (if `--expected-qb` is given), with live cross-check warnings.

---

## Precedence (overlay layer)

Per (game, side): manual `qb_news` **>** expected-QB recorder (29, v2 rule)
**>** frozen automated state (the feed lags breaking news — e.g. a Saturday
ruling the weekly snapshot hasn't picked up yet). Questionable alone never
triggers; the QB delta can only REMOVE picks (via the stale-QB veto), never
create or flip them. Every decision is logged with its source.

**Stale-QB veto** (replaces the old auto-void): when a raw V1 pick is on the
downgraded team AND the market confirms the QB-adjusted number
(`|adj_spread − market| ≤ 1.0`, a judgment parameter), the raw "edge" was
stale QB news — V1's rating was built on the starter, the market priced the
backup — and the pick is vetoed to "no play", transparently, with every
number shown. If the market does NOT confirm the adjusted number, the
disagreement is about team strength, not the QB: the raw pick stands.

**QB_ADJUSTMENT_DOUBLE_COUNT_RISK:** TRUE when the replacement QB already
started a game for that team in the sample feeding V1's current ratings
(PBP-derived). The backup's performance is already inside the team rating, so
the mechanical full-value shift double-counts — treat the adjusted number as
the conservative bound and raw V1 as the aggressive bound.

---

## Cutoff discipline (binding)

1. The Friday prediction uses **only** `availability_friday_2026_w<N>.json`,
   frozen at 18:00 CT. The freeze refuses to overwrite an existing file.
2. Saturday/Sunday diffs update `availability_current.json` only. They must
   never rewrite a Friday-frozen file or a Friday predictions CSV.
3. Weekend re-checks run against **copies** of the predictions CSV
   (`/tmp/...`), never the canonical `data/predictions_2026_w<N>.csv`.
4. Post-cutoff information can update the live dashboard view; it cannot
   retroactively enter the Friday prediction.

---

## Injury audit table (28)

`scripts/28_injury_audit.py` runs in the Friday flow **after** the overlay
layer and writes `data/injuries/audit/audit_2026_w<N>.parquet` — one row per
player-game-week present in the frozen automated state, the recorder, manual
`qb_news`, or the overlay disposition log for that week's games. It answers:
*"What exactly did the system know at the cutoff, and what did the overlay
do?"* (`--no-freeze` permits mid-week re-runs; the cutoff is then recorded
as the run time, honestly labeled.)

Columns:

| Column | Meaning |
|---|---|
| `game_id` | `AWAY_HOME` key from the market JSON |
| `player` | Player name (manual `qb_news` name preferred when present) |
| `team` | Team abbreviation |
| `role` | `expected_starter` / `backup` / `other`. From the frozen availability's `is_expected_starter` flag. Manual/recorder/dispo-only rows name a starting QB by construction, but are cross-checked against the `qb1` list: `expected_starter` only on a last-name match, otherwise `backup` — so a manual entry naming a non-qb1 player surfaces as an auditable discrepancy |
| `automated_status` | Status from the frozen snapshot (`OUT`/`DOUBTFUL`/`QUESTIONABLE`/`LIMITED`/`FULL`), or null if the player-week row is not in the feed |
| `recorder_status` | QB1 status from the expected-QB recorder (v2 rule), or null |
| `manual_status` | Status from `qb_news` for that team/side, or null |
| `final_status` | Merged per the precedence rule: manual > recorder > auto |
| `expected_qb` | Expected QB for the team (recorder, all 32 teams) |
| `first_seen_at` | Earliest snapshot `pulled_at` where this player-week row carried the same automated status. **Provenance for our snapshots only** — the nflverse feed has no per-row `date_modified`, so this is NOT when the market learned it. Null when the row is manual/recorder-only |
| `recorder_captured_at` | When the recorder captured this QB state |
| `prediction_cutoff` | The freeze file's `frozen_at` timestamp (Friday 18:00 CT boundary), or the run time for `--no-freeze` re-runs |
| `overlay_action` | What the overlay did: `keep` / `vetoed` / `noted` (null when the overlay logged nothing for the row) |
| `void_triggered` | Legacy name kept for cross-week continuity. True only when `final_status` is in the trigger set (OUT/DOUBTFUL) **and** `overlay_action` is `vetoed` — i.e. the stale-QB veto removed a live pick |
| `override_used` | True when the winning source's status differs from a lower-precedence source's status (a genuine conflict the precedence rule resolved). A higher source filling a lower source's gap is not an override |
| `source` | `+`-joined contributing sources: `auto` / `recorder` / `manual` (e.g. `manual+recorder`) |
| `qb_shift_pts` / `adj_spread` / `edge_before` / `edge_after` | Overlay numbers from the disposition log (null when the overlay logged nothing) |
| `double_count_risk` / `stale_qb_veto` | Overlay flags from the disposition log |

Every manual override is fully auditable in its row: `automated_status`,
`recorder_status`, `manual_status`, the `prediction_cutoff`, and the final
disposition (`overlay_action`, plus the per-decision records in
`void_disposition.jsonl`).

The output file is never overwritten — a re-run for the same week exits
rather than clobbering the record.

---

## QB-expectation recording (29) — primary automated QB source

`scripts/29_qb_expectation.py` records, per team per week, the QB the system
expects to start. Since 2026-10-01 it is the **primary automated QB-state
source for the overlay** (precedence: manual `qb_news` > recorder > frozen
feed auto entries). It also continues to build the historical dataset a
future preregistered experiment ("does knowing the expected QB improve
frozen-V1 margin prediction?") needs. **It is not modeling: no prediction is
made and V1 is untouched.**

**Deterministic v2 rule** (2026-10-01; documented in the script):
- Prefer the target week's injury report when available; otherwise use the
  latest **played week with team report coverage**.
- If QB1 has no row in that covered week, infer he was not listed → available.
- Never carry an older week's Out/Doubtful tag forward as present truth.
- expected QB = QB1 from the latest nflverse depth chart (`pos_rank == 1`),
  **unless** QB1's status is Out/Doubtful → then depth-chart QB2.
- `starter_or_backup`: `starter` / `backup` / `unknown`.
- `confidence`: `high` (healthy QB1) / `medium` (QB1 questionable/limited —
  still expected per rule, but less certain) / `low` (expected QB is the
  backup, or QB1/QB2 unresolvable).
- `qb_status_inferred` flags rows where availability was inferred from
  no-row-in-covered-week; `qb_status_week` records which report week the
  status came from.

**Sources (free/keyless):** nflverse depth charts via
`nfl_data_py.import_depth_charts` (dated snapshots; `gsis_id` joins to the
injury feed) + the versioned daily injury snapshot from step 26. The
depth-chart QB1 is cross-checked against the maintained `qb1` list in
`data/qb_point_values.json`; mismatches are logged as warnings with the
depth chart as source of truth. QBs are never invented or backfilled from
memory.

**Storage:** `data/qb_expectations/qb_expected_<season>_w<week>.parquet` —
**append-only, never overwritten** (the script refuses if the file exists).
Logs to `data/qb_expectations/logs/capture_log.jsonl`. **No historical
backfill**: reconstructing past expectations after the fact would violate
timestamp validity and poison the future experiment's dataset. The series
starts at Week 4 of 2026.

**Friday wiring:** runs as step 2a, **before** the 18:00 CT freeze (step 2b),
so the capture sits inside the same information-set boundary as the injury
freeze. `captured_at` must be ≤ the freeze time.

### Relationship to the overlay layer (no conflicting sources of truth)

- The overlay layer (`11_injury_adjust.py`) reads, per (game, side):
  manual `qb_news` first, then the expected-QB recorder, then the
  Friday-frozen availability as fallback — with the Out/Doubtful trigger set
  for QB changes.
- The QB-expectation record never feeds any prediction input. It is a
  timestamped operational QB-state source plus the parallel research dataset.
- The frozen availability answers "what did the system know at the cutoff"
  (audited by step 28); the expectation record answers "who did the system
  expect to start, as a timestamped fact."
- If the two ever appear to disagree (e.g. expectation says backup while the
  frozen feed shows nothing), that is expected and auditable: the feed lags
  breaking news and the precedence rule resolves it. Do not "fix" one from
  the other.

```bash
# Friday flow (before the freeze)
./venv/bin/python scripts/29_qb_expectation.py --season 2026 --week 5
# (writes data/qb_expectations/qb_expected_2026_w5.parquet; refuses to overwrite)
```

---

## Starter/backup resolution

- **Expected starting QB:** from `data/qb_point_values.json` (`qb1` per team,
  all 32 teams). This is the same source the void rule already trusted.
- **Backup QB:** best-effort — non-starter QB on the team with the most 2026
  pass attempts in `data/player_games.parquet`, matched on last name (name
  formats differ across sources: "Baker Mayfield" vs "B.Mayfield"). Falls
  back to `"TBD"`. The overlay prefers the recorder/manual backup name when
  available.
- **Key skill starters (WR1/RB1/TE1):** not resolved to named starters in
  Phase 1 — the overlay acts only on QBs, so non-QB injuries are carried
  in the availability state and dashboard for awareness only. Documented as
  a known limit.

## Known limits

- The nflverse injury feed is a **weekly snapshot with no `date_modified`**:
  it tells you the current status, not when the market learned it. News
  timing is the PFT branch's job (separate, not integrated here).
- Week-4 (and later) rows appear only as the league publishes that week's
  reports; early-week snapshots mostly carry prior-week rows.
- Only starting-QB Out/Doubtful triggers a QB-change event, by design.
  Questionable alone never triggers; the stale-QB veto can only remove
  picks, never create them.
- The QB point values (`data/qb_point_values.json`) are market-implied
  preseason deltas, capped at 7. When the backup already started games in
  V1's rating sample, the mechanical shift double-counts — flagged via
  `QB_ADJUSTMENT_DOUBLE_COUNT_RISK`, not corrected.

---

## Cron schedule (described — the parent owns job creation)

| Job | When (America/Chicago) | Command |
|---|---|---|
| Daily injury pull | Daily ~8:00 AM | `26_pull_injuries.py --season 2026` then `27_injury_diff.py` |
| Saturday re-check | Saturday ~9:00 AM | `26_pull_injuries.py` then `27_injury_diff.py` (surfaces NEW OUT/DOUBTFUL before kickoff) |
| Sunday re-check | Sunday ~9:00 AM | same as Saturday (inactives) |
| Friday freeze | Friday 6:00 PM CT, before the weekly build | `27_injury_diff.py --freeze-friday --season 2026 --week N`, then the Friday flow runs `11_injury_adjust.py --injury-state data/injuries/availability_friday_2026_wN.json --expected-qb data/qb_expectations/qb_expected_2026_wN.parquet`, then `28_injury_audit.py --season 2026 --week N` (audit table, after the overlay layer) |
| Dashboard refresh | With the existing UI export | `15_export_ui_json.py --model-version V1` (injuries.json + per-game `qb_overlay` in predictions.json) |

Alert rule for the Saturday/Sunday jobs: if the diff reports any
`STARTING QB STATUS CHANGE` flag, that needs a human look before kickoff —
it is exactly the blind spot that cost us the Jayden Daniels game in Week 3.

---

## V1 freeze verification (canonical method)

After any overlay re-run, verify the raw V1 predictions are untouched:

```bash
./venv/bin/python -c "
import pandas as pd, hashlib
pred = pd.read_csv('data/predictions_2026_w4.csv').sort_values('game')
print(hashlib.md5(pred[['game','model_spread']].to_csv(index=False).encode()).hexdigest())
"
```

Reference value for the authorized 2026-09-30 mid-week re-run state:
`83038e1bc832b2f4b351debc5432878d`. (An older checksum string recorded in
notes, `6914b8f7ee1fef7e`, could not be reproduced by any documented method
on 2026-10-01 and is retired — do not cite it.) Structural guarantee:
`11_injury_adjust.py` never assigns to `model_spread`; it writes only the
`model_spread_adj` / `edge_adj` / `spread_pick_final` / `void_reason` /
overlay columns.
