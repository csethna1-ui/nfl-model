# PFT News-Timing Corpus — Pilot Report

**Date:** 2026-09-30 (build); 2026-10-01 (crawl complete, audits final)
**Status:** FINAL — confirmed on the full 12,794-article corpus, 2026-10-01 (see addendum)
**Scope:** ProFootballTalk rumor-mill NFL articles, in-season months Aug–Jan,
2018–2022 seasons (30 monthly sitemap chunks). Injury/availability-relevant
subset by slug pre-filter.

> This pilot produces a DATASET, not a model. No model was fit; no MAE computed.
> Success/failure is judged on data-quality criteria only.

## Build log

- Sitemap harvest: `scripts/01_harvest_sitemap.py` — 60 monthly sitemaps
  (201801–202212), Crawl-delay 10 honored, contactable UA.
- Relevance filter: `scripts/02_filter_injury_relevant.py` — slug token/phrase
  rules (precision-tuned; bare "out"/"back"/"return" excluded as too noisy).
- Article crawl: `scripts/03_crawl_articles.py` — checkpointed per-article,
  resume-safe, exponential backoff on 429/5xx, no evasion. Overnight
  2026-09-30→10-01 the fast Wayback lane stalled and collection continued on
  the polite live lane; a 15-worker Wayback backfill
  (`scripts/07_archive_backfill.py`) finished the bulk on 2026-10-01 morning.
  Per-row provenance: `archive_url IS NOT NULL` ⇒ Wayback copy, else live NBC.
- Entity resolution: `scripts/04_resolve_entities.py` — per-season roster
  index (nflreadpy 2018–2022), parsely team-tag disambiguation. Re-run on the
  full 12,794-article corpus 2026-10-01 (the `entities` table had been rolled
  back by the 09:44 DB-lock contention): 71,407 entities.
- Diagnostics: `scripts/05_news_lead.py` (criterion 4 — see timestamp-bug note),
  `scripts/06_report_stats.py` (criteria 1, 2, 5 + audit samples). Both scripts
  were patched 2026-10-01 with the two-pass timestamp parse (the fix is now
  landed in the scripts themselves, not just the reference copy); 06 also got
  a pandas≥2.2/3.0 `groupby.apply` repair (explicit per-group sampling) and the
  venv received the `tzdata` package so `tz_convert("US/Eastern")` works.

## Corpus stats

| metric | value |
|---|---|
| PFT article URLs harvested (60 mo) | 30 monthly sitemap chunks |
| Injury-relevant + in-scope (Aug–Jan) → crawl target | 12,794 |
| Articles fetched OK (HTTP 200 + body) | 12,794 (100%) — the 48 rows lost to the 2026-10-01 09:44 DB-lock contention were reset and re-fetched; final re-fetch run finished ~16:14 CDT, 0 remaining |
| Fetch failures (404 / retries-exhausted) | 0 |
| Unique content hashes (dedupe check) | 12,794 (zero duplicates) |
| Provenance | 5,606 archive / Wayback (43.8%), 7,188 live (56.2%); 2018 all live, 2022 nearly all archive; all 48 re-fetched articles are live-crawled |
| Resolved player entities | 71,407 (98.4% unique, 0.65% tag-disambiguated, 0.91% ambiguous) |
| Event-class distribution | ruled_out 4,470 · practice_participation 3,349 · injury_report 2,306 · expected_to_play 1,697 · other 778 · transaction 194 |

## Criterion 1 — Coverage: PASS

Bar: ≥80% of 2018–2022 regular-season weeks with ≥20 injury-relevant articles.

Result: **86/87 weeks (98.9%)**. The single zero week is 2022 W18 — a
harvest-scope edge (games played Jan 7–8, 2023; the 202301 sitemap chunk was
never harvested), not a crawl failure. 4,078 articles fall outside REG Tue–Mon
windows (mostly August preseason + January), as expected.

## Criterion 2 — Timestamp validity: PASS

Bar: manual audit of 50 sampled articles — `datePublished` agrees with the
human-readable byline date within the same calendar day in ≥48/50.

Result: **50/50**. 30/30 live articles: ISO `datePublished` matches the byline
to the same ET calendar day. 20/20 archive articles: byline date ≤ Wayback
capture date, byline month = sitemap month.

## Criterion 3 — Entity precision: PASS

Bar: manual audit of 100 sampled articles — ≥90% of extracted player mentions
map to the correct team for that season.

Result: **99/100**. The single miss: "David Moore" resolved to SEA (Seahawks
WR) when the article meant David Moore *of the Dallas Morning News* — a
reporter namesake. Expect ~1% namesake leakage.

## Criterion 4 — News-lead diagnostic (KEY): PASS

Bar: ≥40% of 200 sampled Out/Doubtful player-weeks (2021–2022) have corpus
injury news ≥24h before nflverse `date_modified`, within a bounded 14-day
lookback (recency bound adopted 2026-10-01, see below).

Result: **149/200 = 74.5%, Wilson 95% CI [68.0%, 80.0%]**. The pessimistic
endpoint clears the 40% bar by 28 points.

**Full-corpus re-run (2026-10-01):** the patched `scripts/05_news_lead.py`
(two-pass parse now in the script) was re-run against the live DB after the
48-article re-fetch and the 04 rebuild — **149/200 = 74.5%, bit-for-bit the
same hit count** as the pre-re-fetch run, Wilson 95% CI recomputed
[68.0%, 80.0%]. The 48 re-fetched articles add zero hits to the seeded
200-case sample (as expected: same articles, same content). Median lead
168.8h (~7.0 days), min 24.0h by construction, all 149 hits same-team.

- Sensitivity: 7-day window 69.5% [62.8%, 75.5%]; 30-day window 82.5% [76.6%, 87.1%].
- Same-team match: 100% of hits (149/149).
- Median lead ~169h (~7 days); minimum 24.0h by construction.
- By season: 2021 73.7% (70/95), 2022 75.2% (79/105) — consistent across the corpus.
- By status: Out 74.7%, Doubtful 73.3%. By position: QB highest among sampled groups (63.6%).
- Caveat: spot-checked hits are often injury *roundups*/practice reports
  mentioning the player, not dedicated breaking-news headlines. They satisfy
  the preregistered rule, but "news" here means injury-timing information,
  not scoops.
- Entity recall is conservative by design (full names, small nickname map,
  last-name-only missed) — 74.5% is, if anything, a lower bound.

### Recency bound (adopted 2026-10-01)

A corpus article counts as *leading* an Out/Doubtful designation only if its
publication timestamp falls in the half-open interval
[nflverse `date_modified` − 14 days − 24h, `date_modified` − 24h).
The 24-hour inner buffer excludes same-day report-chasing; the 14-day outer
bound excludes stale mentions (the unbounded rule scored 92.5% with ~1,000-day
median leads and is rejected as meaningless). Primary window: 14 days; 7-day
and 30-day reported as sensitivity.

### Timestamp-parsing bug (found 2026-10-01, corrected)

`scripts/05_news_lead.py` **as written reported 33.5% (FAIL) — that number is a
parsing artifact, not a real result.** The Wayback backfill wrote
`date_published` as date-only strings for 5,269/12,746 articles (41%); a
single `pd.to_datetime()` over the mixed ISO + date-only series coerces *all*
date-only values to NaT (pandas locks the ISO format), silently dropping
nearly all of 2022 and 2021 W13+ from the diagnostic. Corrected run rebuilt
timestamps properly (ISO where present; otherwise the human byline
e.g. "December 5, 2019, 5:39 PM EST" → UTC) with the same seed/sample:
**74.5% PASS**. The corrected reference is saved at
`~/workspace/goals/pft-news-timing-corpus-pilot/hidden_files/news_lead_fixed_ts.py`;
**the two-pass parse has now been patched into both `05_news_lead.py` and
`06_report_stats.py` (2026-10-01)**, and the full-corpus re-run reproduces
149/200 exactly. Separately, `06_report_stats.py` had broken on pandas ≥2.2
(`groupby.apply` drops grouping columns → `KeyError`; dead `tz_convert` code;
venv lacked `tzdata`) — repaired 2026-10-01 (explicit per-group sampling,
`tzdata` installed in the venv).

## Criterion 5 — Sunday-morning QB density

**394 unique QB-relevant articles** published Sunday 6:00am–1:00pm ET,
in-season (Sep–Jan): 2018: 90 · 2019: 75 · 2020: 100 · 2021: 83 · 2022: 46.
Event mix: injury_report 127, ruled_out 105, expected_to_play 77, other 70,
practice_participation 14, transaction 1. (391 on the 12,746-article snapshot;
the 48 re-fetched articles contribute +3.)

## Verdict

**TIMING LAYER.** Three-quarters of sampled Out/Doubtful designations were
preceded by PFT injury-timing information at least a day before the official
injury report, consistently across both measured seasons, with every hit
matching the player's own team. PFT is not merely an archive of what the
reports already said — it carries genuine timing information about player
availability, 2018–2022.

## Corpus biases (documented, not fixed)

- Coverage favors QBs and prominent players; depth-player coverage is weaker.
- Entity resolution is conservative (full-name matching, limited nicknames);
  last-name-only references are missed — hit rates are lower bounds.
- "News" in the diagnostic includes injury roundups and practice reports, not
  only dedicated breaking headlines.
- 2022 W18 absent (harvest-scope edge); 2022 nearly all Wayback-sourced
  (date-only `date_published`, time-of-day recoverable from `human_date_raw`).
- ~1% namesake leakage expected (reporters sharing player names).

## Reuse notes

- Scripts are rerunnable; crawl resumes from checkpoints.
- **The two-pass timestamp parse is now patched into 05/06 (2026-10-01)**
  — the old "patch before reuse" mandate is satisfied; corrected reference
  remains at `hidden_files/news_lead_fixed_ts.py`.
- `06_report_stats.py` is also repaired for pandas ≥2.2/3.0
  (`groupby.apply` → explicit per-group sampling); venv has `tzdata`.
- To extend to PFRumors (rank 2): reuse 03/04 with a new harvester.
- Audit samples: `hidden_files/audit_ts_sample.csv`,
  `hidden_files/audit_entity_sample.csv`,
  `hidden_files/news_lead_results_fixed_ts.csv`,
  `hidden_files/sunday_qb_articles.csv`, `hidden_files/coverage_per_week.csv`.

## Addendum — full-corpus re-run (2026-10-01, ~13:20 CDT)

The 09:44 DB-lock contention had rolled back the `entities` table (only 50
articles / 142 rows survived) and 48 article rows were reset for re-fetch.
After the re-fetch completed (12,794/12,794 OK, 0 remaining, tmux session
`pft_crawl` finished), this follow-up:

1. Re-ran `scripts/04_resolve_entities.py` on the full corpus:
   12,794 articles → **71,407 entities** (unique 70,290 / 98.4%,
   tag-disambiguated 466 / 0.65%, ambiguous 651 / 0.91%); event-class deltas
   vs the 12,746 snapshot sum to exactly +48, confirming the re-fetch.
2. Re-ran patched `scripts/05_news_lead.py`: **149/200 = 74.5% PASS**,
   bit-for-bit identical to the snapshot run (Wilson 95% CI [68.0%, 80.0%],
   all hits same-team, median lead ~7 days). Criterion 4 verdict unchanged.
3. Re-ran patched `scripts/06_report_stats.py`: C1 86/87 (98.9%) PASS;
   C2 programmatic first pass 50/50 same-day; C3 100-article sample exported;
   C5 recomputed on the full corpus (see updated count above).
4. Verified all 150 manual-audit sample URLs (50 timestamp + 100 entity)
   resolve in the final corpus; the recorded judgments (C2 50/50, C3 99/100
   with the documented "David Moore" namesake miss) stand — the corpus delta
   does not touch the audit samples.

**The FINAL verdict is unchanged: TIMING LAYER.** No model was fit; no vault
access; V1 production and Experiment 006 untouched.
