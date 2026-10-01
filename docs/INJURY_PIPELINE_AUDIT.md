# Injury Pipeline Audit — 2026-09-30

Diagnostic only. No model logic, weights, or architecture were changed. No
model was fit. PFT/news stays a separate research branch.

## TL;DR

There is no automated injury pipeline. The production injury path is
**100% manual**: a Friday-morning hand-researched `qb_news` block in
`data/market_2026_w{N}.json`, consumed by `scripts/11_injury_adjust.py`.
The nflverse injury feed is fetched live at runtime but used **only for
warnings** — it never feeds the void logic. There is no local injury cache,
no refresh job, and no injury input anywhere in V1's feature generation.
Consequences:

1. Any injury first reported after the Friday research (Saturday rulings,
   Sunday inactives) is invisible until the next Friday run.
2. Non-QB injuries are invisible by design — the pipeline only knows
   starting-QB Out/Doubtful.
3. `questionable` never triggers anything; practice participation,
   LIMITED/FULL, and expected-starter-vs-backup are not tracked.
4. Week 3 case in point: nflverse had WAS QB Jayden Daniels OUT (elbow);
   the pipeline did not know (no `qb_news` entry). The game happened to be
   "no play," so no void was at stake — but the blind spot is real.

Nothing was "restored" because there is no cache to restore: the failure is
structural (manual-only pipeline), not a stale file. Fixes require
operational/code changes — documented in §8, not implemented.

---

## Stage A — Source freshness (nflverse)

Checked 2026-09-30 via `nfl_data_py.import_injuries([2026])`: 744 rows,
weeks 1–4 present, fetch succeeds live. The source is fresh.

Caveats found in the feed itself:
- **No `date_modified` column** in this feed version (KeyError on access).
  The feed is a weekly snapshot; there is no per-row timestamp of when a
  status was set. "When did the market learn this" cannot come from this
  source — that is the PFT branch's job.
- `report_status` values present: out / doubtful / questionable (+ blanks).
- `practice_status` IS present (e.g. "Did Not Participate In Practice",
  "Limited Participation In Practice", "Full Participation in Practice") —
  the pipeline ignores it entirely.

## Stage B — Local cache

No injury cache exists. `data/` contains no `injuries*.parquet` or similar.
`11_injury_adjust.py::cross_check_injuries` calls
`nfl.import_injuries([season])` live on every run; nothing is persisted.
There is no stale cache — there is no cache at all.

## Stage C — Refresh scheduling

No script or job refreshes injury data. `07_update_weekly.py` (the weekly
model update) contains zero references to injuries or `qb_news` (verified by
grep). Injury knowledge enters the system exclusively through the Friday
cron worker (`nfl-picks-weekly-build`, Fridays 18:20 CT), which hand-researches
`qb_news` into `data/market_2026_w{N}.json` (step 2 of the cron body) and then
runs `11_injury_adjust.py` (step 3b, mandatory).

Operational gaps:
- Single capture point per week (Friday). Saturday/Sunday news — e.g. a
  Saturday ruling-out, Sunday-morning inactives — has no capture mechanism.
- The cross-check warnings ("FEED: ... Out/Doubtful but not in qb_news —
  check this game before publishing") print to the worker's stdout; whether
  they are investigated before publishing depends on the run, and there is
  no record of disposition.

## Stage D — Feature generation

V1 has no injury inputs by design (ELO + EPA + GBM on team strength; the
docstring in `11_injury_adjust.py` explains why). Nothing is "filtered out"
in feature generation — injuries never enter. The only injury consumer is
the post-prediction void rule in step 11.

## Stage E — Status handling

`TRIGGER = {"out", "doubtful"}` in `11_injury_adjust.py`, applied to
**starting QBs only** (manual `qb_news` entries). Specifically not handled:
- `questionable` (deliberate: "QBs play through the tag most weeks")
- any non-QB position (WR/RB/TE/OL/defense invisible by design)
- practice participation (`practice_status` ignored)
- LIMITED / FULL designations
- expected starter vs backup as a data field (only free-text `note`)

## Stage F — Entity resolution

Manual: the Friday worker writes team abbreviations and names by hand
(`LA = Rams` convention documented in the cron). The automated cross-check
matches nflverse `team` + `position == "QB"` against `qb_news` team keys, so
a name misspelling in manual news would silently fail to match the feed
warning (warning keys on team, names are free text). No roster-based
QB1-identification exists in production; the "normal starter" is the
worker's judgment.

## Stage G — UI export

`15_export_ui_json.py` exports `qb_news` and `void_reason` per game
(lines 112–113); verified live in `data/ui_json/v1/predictions.json`
(Week 4: ARI@NYG shows the Dart→Winston void with reason). The interface
faithfully shows what the pipeline knows. The Week 3 gap was upstream
(no `qb_news` entry for Daniels), not in the export.

---

## Confirmation table — Week 3 (2026-09-30 nflverse vs pipeline)

| Player | nflverse report_status (W3) | Pipeline knew? | Action taken |
|---|---|---|---|
| Caleb Williams (CHI QB) | out — hamstring | YES (manual `qb_news`, Fri) | PHI@CHI pick VOIDED (edge +5.2 → +1.2) |
| Jayden Daniels (WAS QB) | out — elbow | NO — not in `qb_news`; cross-check would have warned | None — SEA@WAS was "no play" anyway |
| Tyson Bagent (CHI QB2) | questionable — concussion | NO (backup; questionable never triggers) | None (by design) |
| Zay Flowers (BAL WR) | questionable — hamstring | NO (non-QB invisible) | None (by design) |
| Dallas Goedert (PHI TE) | out — knee | NO (non-QB invisible) | None (by design) |
| Nick Bosa (SF DE) | out — knee | NO (non-QB invisible) | None (by design) |

Week 4 spot-check (pipeline working as designed): Jaxson Dart (NYG QB) out
→ ARI@NYG voided; Jayden Daniels (WAS QB) doubtful → IND@WAS handled via
manual `qb_news`. Both were Friday hand-research catches, not feed-driven.

---

## 8. Required production injury architecture (doc only — not implemented)

To make injury information a first-class input rather than a Friday manual
patch, the pipeline must carry these fields end-to-end (source → cache →
features → prediction input → UI JSON):

1. **report_status** with full granularity: OUT / DOUBTFUL / QUESTIONABLE
   (not just the void trigger set).
2. **practice_status**: DNP / LIMITED / FULL per practice day — it leads the
   official report and is the earliest structured signal.
3. **expected starter vs backup**: a resolved data field per team/position,
   not free text — who is expected to start, and who replaces them.
4. **as-of timestamp**: the feed has no `date_modified`; record when each
   snapshot was pulled and, where available, when the status was first
   reported (this is where the PFT news-timing branch plugs in — it must
   remain a separate layer until validated).
5. **prediction cutoff discipline**: every injury snapshot stamped against
   the Friday 18:00 CT prediction timestamp; anything arriving after the
   cutoff is flagged as post-cutoff, never silently merged.

Refresh requirements:
- Automated daily pull of the nflverse injury feed to a versioned local
  cache (one snapshot per day, never overwritten in place).
- A Saturday-morning and Sunday-morning re-check that diffs the cache and
  surfaces NEW Out/Doubtful designations (especially QBs) before kickoff —
  this closes the timing hole the current Friday-only flow has.
- Cross-check warnings must be logged with disposition (investigated /
   dismissed + reason), not printed to a transient stdout.

Modeling principle (future, separately authorized — NOT implemented here):
injury information should eventually become an **adjustment to the predicted
margin and to player opportunity**, not only a void trigger:

Injury → changed expected personnel → changed opportunity/efficiency →
changed projection → changed edge

rather than:

Injury → delete pick

The void rule stays as a risk control in the meantime. Any adjustment layer
must be preregistered and tested on the same information-timing discipline
as Experiment 006 (no future information), and the PFT news-timing layer
must remain a separate, independently validated branch before it is allowed
to move the adjustment earlier than the official report.
