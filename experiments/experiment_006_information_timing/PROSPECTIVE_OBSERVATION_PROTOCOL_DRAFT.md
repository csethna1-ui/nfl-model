# Prospective-Observation Protocol — DRAFT

**Status:** DRAFT — for Cale's review. Nothing here is frozen; no capture
beyond what already runs (006 Tue/Fri snapshots, Friday pipeline, prop-line
puller) is authorized until he approves.

**Purpose:** A written definition of what gets captured at each timestamp from
the Friday V1 freeze through kickoff, so the 2026 season accumulates a
timestamped information-arrival record: Friday freeze → news → roster changes
→ inactives → market movement → kickoff → outcome. This is the prospective
stream he ordered on 2026-10-01 as the next information-timing instrument
after PFT (PASS), Experiment 010 (NULL), and Experiment 011 (shelved).

**Binding analysis contract (non-negotiable):** this stream is MEASUREMENT,
never tuning. No model is fit on it, no weight is changed because of it, no
market is promoted to production-validated because of it. Any future use of
stream data to alter V1, the QB overlay, or the props engines requires a
separately preregistered experiment. The stream answers one question at a
time, descriptively: *what information arrived, when, and did the market move
on it before V1 could?*

## Stage 0 — Tuesday baseline (already running)

`data/timing_study/tuesday_2026_w{N}.csv` via `scripts/22_tuesday_snapshot.py`
(Tuesday ~9:00 AM ET cron). V1 prediction from frozen machinery, Tuesday
market line if researched, ELO/EPA state, capture timestamps, timing_flag.
Unchanged.

## Stage 1 — Friday 18:00 CT freeze (T0)

Artifacts (all timestamped UTC + America/Chicago, never overwritten):
- `data/predictions_2026_w{N}.csv` — Friday pipeline output (07 + overlay):
  V1 raw, expected QB, QB adjustment, adjusted prediction, market line,
  raw edge, adjusted edge, final status (PICK / NO PLAY / VETOED),
  QB_ADJUSTMENT_DOUBLE_COUNT_RISK.
- **Frozen injury-state file, 18:00 CT** — the file the 9/25 postmortem
  requires (verified by the Friday-evening check; see standing verification
  item). If missing, the week's stream is flagged INCOMPLETE — not
  reconstructed.
- `data/market_2026_w{N}.json` — Friday researched lines + qb_news + wind.
- `data/timing_study/friday_2026_w{N}.csv` — 006 Friday snapshot (existing).

Thursday-night games: flagged `already_played=1` at Friday capture; they
enter the stream at Stage 0 only and skip Stages 1–5.

## Stage 2 — News arrival (T0 → kickoff)

**New capture (to be built, lightweight):** a weekly injury-news log,
`data/timing_study/news_2026_w{N}.csv`, one row per event:
`{team, player, event_type, source, published_at, first_seen_at}`.
- Automated lane: reuse the PFT corpus machinery weekly (live PFT only,
  same injury-relevance filter, timestamped). The corpus proved PFT is a
  timing layer; the weekly pull makes it a live instrument.
- Manual lane (best-effort, clearly marked): breaking non-PFT news
  (Schefter et al.) logged with source URL and publication timestamp.
  Manual rows carry `source_reliability=manual`; they are never silently
  merged with the automated lane.

Purpose: replicate the PFT verdict's ≥24h-lead test *prospectively*, and date
exactly when each piece of news arrived relative to Stages 3–5.

## Stage 3 — Roster changes (T0 → kickoff)

**New capture:** weekly roster diffs (nflverse, keyless, in-hand),
`data/timing_study/roster_changes_2026_w{N}.csv`:
`{team, player, change_type, effective_week, first_seen_at}`.
Change types use the 011 exclusion hierarchy (trades / signings / releases /
IR / elevations / settlements), so the prospective stream stays consistent
with the shelved 011 design. Week-granular timing, documented as such —
no pretended day-level precision.

## Stage 4 — Gameday inactives (T-90 min)

**New capture:** the official inactive list per team-game, captured before
kickoff, `data/timing_study/inactives_2026_w{N}.csv`:
`{game, team, player, captured_at}`.
- The prospective continuation of Experiment 010: compute the *same*
  burden variable (trailing-4-week snap-share-weighted, signed away−home)
  so the stream extends the 010 measurement rather than inventing a new one.
- If a list can't be captured before kickoff, the game is flagged
  `inactives_missing=1` — never reconstructed from postgame reports.

## Stage 5 — Market movement (T0 → kickoff)

- Friday line: already researched (`market_2026_w{N}.json`).
- **New capture:** Sunday-morning line snapshot, same research procedure as
  Friday, `data/market_sunam_2026_w{N}.json` with capture timestamp.
  A missed Sunday is never backfilled.
- Movement per game: `sunam_line − friday_line`, timestamped at both ends.
  This is the leg the historical work could never reconstruct
  (006 backfill: zero timestamped Friday lines) — prospectively it is
  directly observable.

## Stage 6 — Kickoff → outcome

`data/timing_study/graded.csv` via `scripts/24_timing_grade.py` (existing,
Tuesday grading cron): actual margin, per-stage errors, model vs market
movement, CLV. Extended with per-game stage flags
(`injury_file_ok`, `news_events_n`, `inactives_missing`, `sunam_missing`)
so any analysis can condition on capture completeness.

## The props stream (003A / 003B paper-tracking)

Runs alongside, same contract:
- Projections frozen pre-Friday 18:00 CT from the experimental engines
  (003B live-experimental; 003A once integrated), full provenance per row
  (prediction timestamp, NGS data-as-of, latest game included, feature
  window, model version, line source + capture timestamp, fallback flags).
- Timestamped Bovada lines via `scripts/30_pull_prop_lines.py` (existing;
  note 003B's ~2 lines/slate — the receptions market is the one that
  resolves on a useful timescale).
- Grading vs actuals accumulates the out-of-sample market dataset.
- **Minimum-n rule:** no market-efficiency verdict before ~200 matched
  observations per market (mirrors 006's n<~200 descriptive-only rule).
  Below that, the stream is reported as accumulating, never as evidence
  for or against an edge. Projection quality (the 003A/003B results) and
  market efficiency are separate questions; the stream is the bridge, and
  the bridge takes time.

## What this deliberately does NOT do

- No fitting, no selection, no tuning on the stream (the 002 overfitting
  lesson applies to prospective data too).
- No betting-edge claims from projection accuracy alone (standing rule).
- No reconstruction of missed captures — a missed stage is a flagged gap,
  not a backfilled row.
- No vault touches. The locked 2023–2025 test is never consulted by this
  protocol.

## Judgment calls needing Cale's word

1. **Sunday-AM line research** adds a manual step to the Sunday routine.
   Worth it for the only directly-observable market-reaction leg, or keep
   the stream to Friday lines only?
2. **Weekly PFT live pull** — automated, same filter as the corpus. OK to
   run weekly?
3. **Inactive burden** — reuse 010's exact variable definition prospectively
   (recommended: keeps one measurement continuous), or keep inactives as
   raw lists only?
4. **Props minimum-n** — ~200 matched observations per market before any
   efficiency verdict. Right bar, or too strict/loose?
5. **News manual lane** — keep the best-effort Schefter-style log, or
   automated PFT only to avoid manual-reliability questions?

Drafted 2026-10-01 by the proactivity research pass, from his 17:09 UTC
authorization ("Yes") and his 18:07 UTC framing of the next question:
*do the 003A/003B improvements translate into an advantage over the actual
sportsbook line?* This protocol is the instrument for that question.
