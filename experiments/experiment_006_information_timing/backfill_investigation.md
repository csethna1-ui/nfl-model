# Experiment 006 — Weeks 1–3 Backfill Source-Feasibility Investigation

**Date:** 2026-09-29
**Status:** Source feasibility only. Nothing has been written into the 006 study datasets. No model reconstruction performed.
**Scope:** Can 2026 Weeks 1–3 be legitimately backfilled from free/keyless sources with real historical timestamps?

## Target dates (verified via `date -d`)

| Week | Tuesday snapshot target | Friday snapshot target |
|------|------------------------|------------------------|
| 1 | Tue 2026-09-08 | Fri 2026-09-11 |
| 2 | Tue 2026-09-15 | Fri 2026-09-18 |
| 3 | Tue 2026-09-22 | Fri 2026-09-25 |

## Classification standard (binding)

- **A — Verified timestamped:** a line with a real historical timestamp/date from a source that distinguishes Tuesday from Friday at day-level precision or better. May enter primary analysis.
- **B — Partially verified:** document, exclude from primary.
- **C — Unusable:** undated, inferred, or current-proxy lines. Never use.
- Rules applied: no inferred dates from undated lines; no use of today's nflverse snapshot as a historical Tuesday/Friday line; provenance recorded for every candidate.

---

## Verdict: PARTIAL

**A-class total: 16 game-observations** — one week (Week 2), one snapshot (Tuesday), one book (bet365).

**No A-class Friday source was found for any of Weeks 1–3.** The Friday-side market line — required for the study's core movement and CLV questions — is missing for all three weeks. A partial backfill that cannot answer the preregistered questions is not recommended (see §5).

---

## Per-week / per-game classification

### Week 1 (Tue 9/8 · Fri 9/11)

| Candidate | Timestamp | Class | Notes |
|-----------|-----------|-------|-------|
| `data/market_2026_w1.json` (in-repo) | File mtime 2026-09-11 17:09:51 UTC (= 12:09 CDT, Friday) | **B** | Genuine internal Friday artifact: 14 games as `[spread, total]` arrays. 2 games missing — consistent with the Wednesday and Thursday Week 1 games already being played before Friday (no Friday line can exist for played games; principled exclusion, not missing data). Day-level precision at file level, but **per-game public source is not recorded** (no book, no quote time per game). Excluded from primary. |
| SportsBettingDime Week 1 odds article (explicit odds date Sep 6, 2026) | Sep 6 | **C** (for 006) | Real timestamp, wrong day — not Tue 9/8 or Fri 9/11. Usable as neither Tuesday nor Friday evidence. |
| SportsbookReview Week 1 odds (last updated Sep 13) | Sep 13 | **C** (for 006) | Not Tuesday or Friday. |
| Covers Week 1 promo page (search result dated Sep 8, 5 games shown) | Sep 8 | **B** | Not fetched/verified in full this pass. Partial (5 of 16 games) and line-table "as of" language unconfirmed. Hold as B until verified; likely stays B on incompleteness alone. |
| sports.co.it search result ("as of Sept. 3") | Sep 3 | **C** | Wrong day. |
| FOX/FOXSports "lines and possibilities" Week 1 article | — | Not found | Targeted searches returned only the Week 2 installment. |

### Week 2 (Tue 9/15 · Fri 9/18)

| Candidate | Timestamp | Class | Notes |
|-----------|-----------|-------|-------|
| **DallasCowboysCommunity / Yardbarker article: "2026 NFL Week 2 odds: Lines and possibilities for all 16 games"** | **Lines "as of Sept. 15" (Tuesday)** | **A** | **16 game-observations.** Original page: `https://www.dallascowboyscommunity.com/news/twenty-twenty-six-nfl-week-two-odds-lines-and-possibilities-for-all-sixteen-games/` — explicit sentence: *"Here are the lines for all 16 Week 2 matchups at bet365 Sportsbook as of Sept. 15, including the spread, moneyline and over/under."* Page itself published Sep 16, 11:00 AM; the odds carry their own "as of Sept. 15" date, which is the Tuesday target. Sept 15, 2026 verified as Tuesday. Full slate: spread + moneyline + total for all 16 games (DET@BUF BUF-4.5 through NYG@LAR LAR-7.5). Syndicated on Yardbarker; content attributed to Fox Sports sourcing. Single-book (bet365), not consensus — usable for Tuesday error grading with that provenance noted. |
| `data/market_2026_w2.json` (in-repo) | File mtime 2026-09-17 01:55:41 UTC (= Sep 16 evening CDT, **Wednesday**) | **C for Friday; B as Wednesday mid-week line** | 16 games. Cannot be re-dated to Friday. Documented, excluded from Friday evidence. |
| Wayback: Action Network capture `20260911071320` | Sep 11 | **C** | Archive replay failed to return page text; content unverified. Not retried per protocol. |
| FOX Week 2 article is the same A source above | — | — | — |

### Week 3 (Tue 9/22 · Fri 9/25)

| Candidate | Timestamp | Class | Notes |
|-----------|-----------|-------|-------|
| `data/market_2026_w3.json` (in-repo) | File mtime 2026-09-25 03:16:29 UTC (= Sep 24 evening CDT, **Thursday**) | **C for Friday; B as Thursday mid-week line** | 15 games + `qb_news`. Cannot be re-dated to Friday. Documented, excluded from Friday evidence. |
| Wayback: VegasInsider capture `20260918003411` | Sep 18 UTC = Sep 17 evening Eastern | **C** | Not a Friday observation even if content were retrievable (Thursday evening). Archive replay failed; not retried. |
| Targeted searches for "as of Sept. 22" / "as of Sept. 25" line tables | — | Not found | No credible complete Tuesday- or Friday-dated Week 3 line table located in public sources this pass. |
| sportsbrackets.net pick'em sheets ("lines as of" early-September dates) | various | **C** | Dates did not match Tue 9/22 or Fri 9/25 targets. |
| FOX "lines and possibilities" Week 3 article | — | Not found | Only the Week 2 installment surfaced. |

---

## A-class inventory (final count)

- **16 game-observations:** Week 2 Tuesday, all 16 games, bet365 spreads/totals/moneylines, "as of Sept. 15, 2026" (Tuesday, verified).
- **0 A-class Friday observations** across Weeks 1–3.
- **0 A-class observations** for Week 1 Tuesday, Week 3 Tuesday, Week 1 Friday, Week 3 Friday.

## What the B-class internal files can and cannot do

- W1 Friday file (B): a genuine Friday-dated internal state, usable only as a secondary internal appendix — never as primary A-class Friday evidence, because per-game source provenance is absent.
- W2 Wednesday / W3 Thursday files (B): mid-week lines, documented; they are not Tuesday or Friday lines and cannot stand in for either.
- None of these were written into the 006 datasets, and none may be promoted to A without per-game source recovery, which is not available.

## Model-side reconstruction feasibility (documented, not executed)

Reconstruction is feasible in principle under the frozen-V1 constraint, but is **not authorized until this report's plan is approved**:

1. **Ratings:** ELO/EPA ratings can be recreated from game/PBP data using cutoff-aware weekly batching (only games completed before each snapshot date).
2. **GBM path:** must remain the frozen V1 architecture, fit only on games completed before each snapshot; no refitting on 2026 outcomes observed after the snapshot.
3. **Injuries:** nflverse injury rows can be filtered by `date_modified` before the relevant Tuesday/Friday cutoff (per Experiment 004, 99.86% pregame, timestamped).
4. **Week 1 Friday special case:** Wednesday/Thursday Week 1 games occurred between the Tuesday and Friday snapshots — the Friday model state legitimately excludes them (consistent with the 14-game in-repo file); Tuesday state includes them.
5. **Existing predictions files as stored states:** `predictions_2026_w1.csv` (Friday timestamp), `predictions_2026_w2.csv` (Wednesday — not Friday), `predictions_2026_w3.csv` (late Thursday CDT — not Friday). Only W1's aligns with a snapshot target; the others cannot be re-dated.
6. **QB news / weather:** must be reconstructed from sources dated before each cutoff; no post-cutoff information.

## Timestamp-disciplined plan (conditional)

Because only 16 A-class Tuesday observations exist and **zero A-class Friday observations** exist:

- **Do not backfill.** The preregistered four questions (model movement, market movement, prediction improvement, tradability/CLV) all require paired Tuesday–Friday market lines. Sixteen unpaired Tuesday lines cannot answer any of them; a half-backfill would produce descriptive numbers that look like study output but are not.
- **Allowed, if approved:** enter the 16 Week-2 Tuesday A-class lines into a clearly labeled secondary appendix (not the primary `graded.csv` stream), paired with a reconstructed frozen-V1 Tuesday model state, for one descriptive purpose only — Tuesday model-error vs Tuesday-market-error on a fully timestamped slate. No movement, improvement, or tradability claims.
- **Week 5 onward** remains the primary prospective stream (first full scheduled week; Tuesday cron first run 2026-10-06).
- **Optional follow-up (not authorized here):** the FOX "lines and possibilities" series produced the Week 2 A-class source; installments for Weeks 1, 3, and 4 may exist on foxsports.com or via live-browser lookup. That is a separate task, not part of this verdict.

## Provenance log

- Weekday verification: `date -d` confirms Tue 9/8, Fri 9/11, Tue 9/15, Fri 9/18, Tue 9/22, Fri 9/25 (2026).
- A-class source verified by direct page fetch 2026-09-29; "as of Sept. 15" language quoted verbatim from the original page.
- In-repo file timestamps from filesystem (`stat` mtime), converted UTC→CDT.
- In-repo file contents inspected: `[spread, total]` per-game arrays; per-game source not recorded.
- Wayback captures: CDX-listed only; replay fetches failed and were not retried per protocol.
- No nflverse snapshot was used as a historical line at any point in this investigation.
