# Personnel/Availability Information Frontier — Audit Dossier

**Date:** 2026-09-29 | **Author:** research subagent (read-only; no data downloaded, no modeling)
**Scope:** free/keyless sources only; reconstructability assessed for **2018–2022** (2023–2025 vault untouched).
**Governing question per class:** historically reconstructable (2018+) AND genuinely available before the prediction timestamp?
**Timing vocabulary:** Tuesday-AM (V1's info state) → Friday → pre-kickoff (incl. 90-min inactives) → postgame.

**Status tags:** VERIFIED = fetched/inspected or confirmed by a third-party audit doc that fetched it directly (cited).
INFERRED = reasoned from structure, not directly fetched. Links below are verbatim from search/fetch results.

---

## Class 1 — EXACT INJURY/NEWS TIMING (when the market learned, not the final designation)

**What it is concretely:** Per-event timestamps of injury/availability news breaking (e.g., "QB limps off Sunday," "DNP Wednesday per beat reporter," "Schefter: expected to play"), as distinct from nflverse's final weekly designation + `date_modified` (which is 81% Friday filings — the official-report cadence, not the news cadence).

**Why the market might have it and we don't:** The betting market reprices within minutes of Schefter/Rapoport tweets and team announcements; V1's effective info state is ~Tuesday AM. News that breaks Mon–Wed (severity reports, practice news, coach comments) is a genuinely different information channel from the Wed–Fri official filings nflverse records.

**Free/keyless source candidates (exact):**
1. **ProFootballTalk via NBC Sports sitemap — VERIFIED workable.** `https://www.nbcsports.com/sitemap.xml` → monthly `sitemap-YYYYMM.xml` chunks; PFT NFL articles Sept 2009–present (~1,900/mo, ~13% injury-relevant). Per-article timestamps via sitemap `<lastmod>` AND article JSON-LD `datePublished` (third-party audit fetched a 2020-09-28–10-01 sample: they agree to the minute). robots.txt: `Crawl-delay: 10`. Audit doc: https://github.com/ryanpmcintire/nfl_py3/blob/HEAD/docs/injury_news_sourcing.md (2026-08-19 session; 299,739 dated PFT NFL URLs, 202/202 months, 0 failures).
2. **Pro Football Reference player news archives — VERIFIED to exist, depth spot-checked.** `https://www.pro-football-reference.com/players/news.fcgi?id={pfr_id}` — dated aggregation from RotoWire, RotoBaller, KFFL "Hot off the Wire," and team beat sites. Search results show dated entries back to **2012** (e.g., KFFL 9/27, 9/23 entries for Brandon Jacobs). Free, no key. Cross-player coverage depth not fully measured.
3. **RotoWire news sitemap — plausible, NOT bulk-verified.** `https://www.rotowire.com/sitemap.xml` + `https://www.rotowire.com/news-sitemap.php` declared in robots.txt (no blanket disallow). Player pages like `https://www.rotowire.com/football/player/mike-evans-9253` carry dated news items. Same audit doc flagged it as a live alternative, never bulk-built.
4. **Wayback Machine on `espn.com/nfl/injuries` — works but REDUNDANT.** CDX shows real captures from 2016 onward (~130+/yr by 2017) with provable crawl timestamps, but it captures the same official status board already in nflverse. Slower path to owned data.
5. **Wayback on rotoworld player-news — INSUFFICIENT.** Only 9 captures across all of 2019, clustered offseason (same audit doc).
6. **ESPN news API (`site.api.espn.com/.../news`) — DEAD for history.** `limit=1000` silently capped at 50; `dates=` param ignored (returns today's news). Live snapshot only.
7. **Sleeper API (`api.sleeper.app/v1/players/nfl`) — DEAD for history.** One row/player with single `news_updated` field; live snapshot only.
8. **X/Twitter beat-reporter archives — INACCESSIBLE** (see Inaccessible list).

**Historical reconstructability (2018+):** YES. PFT corpus covers 2009+ at daily/article granularity; PFR news archives cover at least 2012+ (spot-verified). Both satisfy 2018–2022.

**Timestamp availability:** Per-article to the minute (`datePublished` / human-readable date strings). Covers Sunday-night injury news, Monday beat updates, Wed–Fri practice news — i.e., Tuesday-AM, Friday, and pre-kickoff windows all representable. Caveat from the audit doc: treat `<lastmod>`/`datePublished` as a "known no later than" bound (one sampled article showed an earlier human-readable date than its ISO stamp).

**Expected mechanism:** Earlier + more precise knowledge of injury severity and expected availability than the official Wed–Fri filings convey; could sharpen Tuesday-state estimates and enable a Sunday-morning QB-decision layer (see Class 6). New information = *when* and *how bad*, not just the final designation.

**Overlap risk with V1:** LOW for the timing dimension. nflverse injuries (exp 005's source) captures the official-report *outcome*; this captures the *news arrival*. The final designation overlaps; the timestamped path to it does not.

**Feasibility: HIGH.** The PFT bulk path is proven by an independent audit; the remaining work is body-fetch + timestamp extraction + player-name resolution.

**Effort:** Medium — sitemap crawl is ~275 monthly chunks (fast); per-article fetch for the injury-relevant subset only (~250/mo × 60 months); player-name → team mapping via slug/headline NLP.

---

## Class 2 — CONFIRMED INACTIVE LISTS (90-min pre-kickoff)

**What it is concretely:** The official 7-man inactive list per team, announced 90 minutes before kickoff. This is ground truth for "who actually sits," resolving Questionable uncertainty and capturing healthy scratches (coaching decisions).

**Why the market might have it and we don't:** Market prices the Sunday 11:30am ET inactive release directly (RotoWire notes this explicitly as the Sunday-morning adjustment point). V1 only knows Friday designations.

**Free/keyless source candidates (exact):**
1. **nflverse `weekly_rosters` — VERIFIED.** Release pattern `weekly_rosters/roster_weekly_{season}.csv`, coverage 2002+. Status enum includes **`INA` = game-day inactive (weekly data only)** plus `status_description_abbr` (e.g., `I01` = Inactive). Verified via nflverse GitHub issue nflverse/nflverse-rosters#56 (2021 Week 1 Browns: 7 rows "Inactive") and two independent project docs (mistakia/league: "`INA` (2020+) → active=false (game-day inactive)"). Free/keyless.
2. **NFL GSIS gamebook PDFs — VERIFIED to exist, free.** URL pattern `www.nflgsis.com/{season}/{type}/{week}/{gameid}/Gamebook.pdf` (e.g., http://www.nflgsis.com/2022/reg/12/59004/Gamebook.pdf). Every gamebook has "Not Active" and "Did Not Play" sections. Search results confirm availability 2004–2024. No login. Bulk reconstruction = PDF fetch + parse (heavy but mechanical).
3. **NFL Pro `teams/rosterWeek` endpoint — UNVERIFIED for history.** A third-party doc (mistakia/league) reports it returns the 48-man dressed roster, verified only for 2023–2025 live. Historical query capability unknown.
4. **ESPN game pages via Wayback / PFR box scores — no inactive lists** (INFERRED from page structure; PFR box scores show season-level starting lineups, not weekly inactives).

**Historical reconstructability (2018+):** YES via `weekly_rosters`. One caveat: the `INA` token is documented as 2020+; for 2018–2019 the enum may encode inactives differently — verify token presence per season before use (VERIFIED gap, not a blocker: the GitHub issue example is 2021; mistakia validated sampled years 2009/2014/2016/2018/2020 for resolution but the INA-specific token history needs a per-season check).

**Timestamp availability:** Weekly grain only — the 90-minute *announcement time* is not timestamped anywhere free. The list *content* (the actual information) is fully reconstructable; the *timing edge* (knowing it at 11:30am vs postgame) is not, except via the Class 1 news corpus (beat writers tweet the lists).

**Expected mechanism:** Converts Questionable/Doubtful uncertainty into ground truth; healthy scratches reveal coaching intent. Small-sample by construction (only affects the ~30% of games with meaningful inactive news), but directionally the market's Sunday move.

**Overlap risk with V1:** HIGH with the injuries table for Out designations (≈ inactives), LOW for the *resolution of Questionable* and healthy scratches, which nflverse designations never settle.

**Feasibility: HIGH.** **Effort:** Low — `weekly_rosters` is one file per season; join `INA` rows to injuries. (Per-season token check for 2018–2019 first.)

---

## Class 3 — LATE PRACTICE PARTICIPATION (day-level Wed/Thu/Fri)

**What it is concretely:** Per-day practice participation (DNP / Limited / Full) for Wednesday, Thursday, Friday — the trajectory signal (e.g., DNP→Limited→Full vs DNP→DNP→DNP) that the market reads mid-week.

**Why the market might have it and we don't:** Beat writers report each day's practice; the market digests the trajectory. Our injuries table collapses the week to one value.

**Free/keyless source candidates (exact):**
1. **nflverse injuries `practice_status` — VERIFIED weekly-only, NOT day-level.** Two independent docs confirm: mistakia/league — "nflverse carries one value per week and pinning it to any specific day fabricates day-resolved data"; the gesmith0606 data dictionary shows one `practice_status` per player-week. `date_modified` is the *filing* timestamp, not the practice day. The official NFL rule requires the first practice report Wednesday, so the field is effectively the last-reported status.
2. **Official NFL injury-report PDFs (nflcommunications.com) — day-level EXISTS, archive FRAGMENTED.** The league's official report has Wednesday/Thursday/Friday Participation columns. Team sites host weekly PDFs (VERIFIED example: Patriots 2014 Week 16 report with "Wednesday Participation / Thursday Participation / Friday Participation" columns at `https://media.patriots.1rmg.com/wp-content/uploads/2018/03/25162603/2192014-Week-16-Injury-Report.pdf`). No central historical archive; per-team URL schemes differ; ~32 teams × 18 weeks × 5 seasons ≈ 2,880 PDFs to locate, many dead links.
3. **Class 1 news corpus (PFT/RotoWire/KFFL via PFR news) — the practical substitute.** Day-level practice news ("did not practice Wednesday") is routinely reported with dates for fantasy-relevant players, but coverage is editorial, not systematic (role players often unreported).

**Historical reconstructability (2018+):** PARTIAL. Systematic day-level = NO at reasonable effort. Notable-player day-level via news = YES.

**Timestamp availability:** Day-level by construction (Wednesday/Thursday/Friday), where available.

**Expected mechanism:** Practice trajectory predicts Questionable→active/inactive conversion better than a single Friday status; the market demonstrably trades on Wednesday/Thursday reports.

**Overlap risk with V1:** MEDIUM — the final Friday status is already in V1's info set (via injuries); the *trajectory* is the new part.

**Feasibility: LOW** for systematic bulk; **MEDIUM** via news corpus for notable players. **Effort:** High for the PDF route (per-team Wayback archaeology); medium for news-mining.

---

## Class 4 — STARTING LINEUP CHANGES ANNOUNCED PRE-GAME (non-injury)

**What it is concretely:** Benchings, depth-chart promotions, and lineup changes announced before kickoff for non-injury reasons (performance, matchup, discipline).

**Why the market might have it and we don't:** A starting-OL or CB benching announced Friday/Saturday moves the line; V1 never sees it (depth charts are weekly and post-hoc).

**Free/keyless source candidates (exact):**
1. **PFR historical starting lineups — EXISTS but wrong grain.** `https://www.pro-football-reference.com/teams/{abbr}/lineups.htm` (e.g., /teams/min/lineups.htm) — season-level, post-hoc. VERIFIED via search results. Useless for week-level pre-game announcements.
2. **nflverse depth_charts — weekly grain historically.** Pre-2025 files are the old NFL Data Exchange weekly structure; only 2026+ has daily `dt` snapshots (ESPN source). No announcement timestamps; weekly snapshots can't distinguish a Tuesday benching from a Sunday one.
3. **Class 1/5 news corpora (PFT, PFRumors) — the only reconstructable route.** Benching announcements are news events with dates (e.g., "Team benches X, promotes Y"). Requires NLP event extraction; coverage skews to notable players/positions.

**Historical reconstructability (2018+):** NO structured source; YES-ISH via news mining for high-profile cases only.

**Timestamp availability:** Article-dated (day granularity) where reported; intraday timing generally unavailable.

**Expected mechanism:** Non-injury lineup downgrades (especially OL/DB) are pure "who is playing" information orthogonal to V1's team-strength estimates.

**Overlap risk with V1:** LOW — V1 has no lineup-change signal at all. (Snap counts reveal it ex-post, which is leakage, not signal.)

**Feasibility: LOW-MEDIUM.** **Effort:** High — event-extraction NLP over the news corpus; precision/recall unproven.

---

## Class 5 — REAL-TIME ROSTER TRANSACTIONS (elevations, signings, IR moves)

**What it is concretely:** Dated roster moves: practice-squad elevations (often Saturday), signings, IR placements, activations, waivers — with day-level timing. These are the team publicly announcing where it is scrambling for cover.

**Why the market might have it and we don't:** Elevations/IR moves cluster Thu–Sat, after V1's Tuesday info state and after most line movement; the market's late-week pricing absorbs them. V1 never sees a roster move.

**Free/keyless source candidates (exact):**
1. **Pro Football Rumors transaction-wire archive — VERIFIED workable, best candidate.** `https://www.profootballrumors.com/category/transactions` + sitemap `https://www.profootballrumors.com/sitemap.xml` → yearly `sitemap-posttype-post.YYYY.xml`. Real article coverage **2014+**; 72,368 articles 2014–2026, ~29,414 transaction-relevant; daily "Minor NFL Transactions" round-ups with dates. Per-article JSON-LD `datePublished` verified on a 325-article stratified sample (100% match to URL year/month). robots.txt: `Crawl-delay: 1`, no block encountered. **Caveat (VERIFIED):** sitemap `<lastmod>` is contaminated by a 2025-12 bulk site retouch — use JSON-LD `datePublished` from the article body, never `<lastmod>`. Audit doc: https://github.com/ryanpmcintire/nfl_py3/blob/HEAD/docs/pfr_transactions_sourcing.md (2026-08-20 session).
2. **nfltraderumors.co transactions category — EXISTS, less structured.** `http://nfltraderumors.co/category/nfl-transactions/` — dated daily posts ("NFL Transactions: Friday 9/25"), paginated (~3,265 pages). Free. No sitemap verification done.
3. **nflverse `load_trades` — EXISTS but insufficient.** Lee Sharpe's historical trades table (`trades/trades`); trades only, no elevations/signings/IR, coarse timing.
4. **nfl_data_py — NO transaction function.** VERIFIED absent from the package's documented imports (README function list: pbp, weekly, seasonal, rosters, win totals, scoring lines — no transactions).
5. **NFL.com transaction wire — live only;** no free historical archive found.
6. **PFR `years/{Y}/transactions.htm` — Cloudflare-blocked** (HTTP 403, verified by the audit doc; bypass would fight the site's active anti-scraping posture).

**Historical reconstructability (2018+):** YES — PFRumors covers 2014+ with day-level `datePublished` on transaction posts.

**Timestamp availability:** Day-level (`datePublished`); intraday hour available from JSON-LD where needed. Moves are typically Thu–Sat → Friday/pre-kickoff knowable, generally NOT Tuesday-knowable.

**Expected mechanism:** An IR placement or Saturday elevation is a direct, dated downgrade/upgrade signal at a position; cluster of moves = depth crisis. Orthogonal to V1's inputs.

**Overlap risk with V1:** LOW. V1 never sees roster moves; partial overlap with `weekly_rosters` status changes (RES tokens) but without timing.

**Feasibility: HIGH.** **Effort:** Medium — sitemap crawl is 13 yearly chunks (fast); JSON-LD fetch per transaction-relevant article (~2,200/yr × 5 yrs ≈ 11k fetches at ~1s each ≈ 3 hrs, polite).

---

## Class 6 — LATE QB DECISIONS (Sunday-morning game-time calls)

**What it is concretely:** QB-specific availability news announced Sunday morning (e.g., "Schefter: QB expected to start," pregame warmup reports, 11:30am inactive confirmation).

**Why the market might have it and we don't:** This is the highest-leverage personnel news in the sport; the market moves points on it Sunday morning. V1's QB handling is the stale-news filter (voids), not a prediction of the decision.

**Free/keyless source candidates (exact):**
1. **PFT corpus filtered to Sunday mornings — reconstructable subset of Class 1.** Timestamps to the minute; filter `datePublished` weekday=Sunday + hour<kickoff + QB entity. VERIFIED corpus, INFERRED Sunday-morning density (not measured).
2. **PFR player news archives (QB pages) — dated Sunday entries exist** (same `news.fcgi` mechanism as Class 1).
3. **RotoWire Sunday-morning inactive updates — live only;** historical via PFR news archives or Wayback (not measured).
4. **`weekly_rosters` INA rows — the outcome, not the news.** Confirms whether the QB dressed, but gives no Sunday-morning timing.
5. **X/Twitter — INACCESSIBLE** (the actual wire these reports travel on).

**Historical reconstructability (2018+):** YES for the news layer (PFT/PFR-news); the *decision* outcome is ground-truthed by INA rows + snap counts (did the QB play?).

**Timestamp availability:** Sunday-morning representable from article timestamps; the canonical 90-min announcement itself is not independently timestamped free.

**Expected mechanism:** Same as Class 1 but QB-concentrated: the market's Sunday QB repricing is the largest single personnel-driven move; a historical record of "what was reported Sunday AM vs what happened" is the dataset the stale-QB filter's validation lacks.

**Overlap risk with V1:** LOW-MEDIUM — overlaps the existing QB injury filter's inputs (designations) but adds the Sunday-morning *resolution* layer V1 never sees.

**Feasibility: MEDIUM.** **Effort:** Medium — builds on Class 1 corpus; needs QB entity filtering + weekday/time slicing.

---

## Class 7 — PLAYER-SPECIFIC AVAILABILITY/VALUE (snap-weighted, starter-vs-backup)

**What it is concretely:** Not "3 players out" but "how much on-field value is missing": snap-share-weighted availability loss, with starter-vs-backup distinction.

**Why the market might have it and we don't:** The market prices *which* player is out (a starting LT vs a backup WR); count-based features (exp 005) treat them equally — and 005 failed. Snap-weighting is the strictly better aggregation of the same underlying table.

**Free/keyless source candidates (exact) — all nflverse, all covering 2018–2022:**
1. **`load_snap_counts` (2012+)**: per-player-game offense/defense/ST snaps and pct.
2. **`load_injuries` (2009+)**: Out/Doubtful/Questionable with `date_modified`.
3. **`load_depth_charts` (2001+)**: weekly positional depth; `pos_rank` identifies starters (pre-2025 = weekly NDE structure; 2026+ = daily ESPN `dt` — for 2018–2022, weekly grain).
4. Construction (INFERRED, standard): rolling pre-week average snap pct per player (no postgame leakage) × designation weight × starter flag → team-week "value lost" by position group.

**Historical reconstructability (2018+):** YES — all three inputs fully cover the window.

**Timestamp availability:** Inherits injuries `date_modified` (mostly Friday filings) — Friday-knowable, not Tuesday-knowable.

**Expected mechanism:** Replaces 005's raw counts with value-weighted loss; a starting QB/LT/CB absence moves margin far more than a backup ST absence. This is a *feature-engineering* improvement on owned data, not new information — distinguish from Classes 1–6.

**Overlap risk with V1:** HIGH on inputs (same injuries table 005 used), but the *aggregation* (snap × starter) is new. Note: 005's null result was for counts; this tests whether the failure was aggregation, not information. **Program note:** the research program is FROZEN on "better math on the same data" — this class sits closest to that boundary; it is documented here as an audit finding, not a proposal.

**Feasibility: HIGH.** **Effort:** Low-medium — three nflverse joins + rolling snap averages; no scraping.

---

## INACCESSIBLE LIST (paywalled but clearly valuable)

| Source | What it would give | Cost (VERIFIED via 2026 pricing docs) |
|---|---|---|
| **X/Twitter full-archive search** | Beat-reporter timestamp gold standard: Schefter/Rapoport tweets with exact timestamps 2018+ | Pro $5,000/mo (legacy, **closed to new signups**); Enterprise ~$42k/mo; pay-per-use default for new devs since Feb 2026. Free tier is effectively write-only (reads 403). |
| **DonBest / real-time odds APIs** | Timestamped line-movement history (when the market moved, not just where it closed) | Paywalled (DonBest = subscription product; The Odds API free tier is current-lines-only, 500 calls/mo — historical odds require paid). |
| **PFF premium grades** | Player-level grades (would sharpen Class 7 value-weighting beyond snap counts) | Subscription paywall (price not verified — not stated). |
| **Next Gen Stats premium / AWS tracking** | Player tracking data (separation, speed) beyond the free nflverse NGS aggregates | Premium tier paywalled; free `load_nextgen_stats` aggregates (2016+) exist but are coarse. |
| **Sportradar NFL API** | Real-time + historical play/injury/odds feeds with timestamps | Paid tiers only. |
| **FantasyPros historical news API** | Structured timestamped news archive | Unauthenticated API returns 403; historical/bulk requires commercial license (per audit doc measurement + search). |
| **ESPN+ Insider** | Beat-reporter analysis behind paywall | Subscription. |
| **Stathead** | Queryable historical splits | Paid subscription. |
| **PFR transactions pages** | Structured transaction history | Not paywalled but **Cloudflare-blocked** (403) — effectively inaccessible without fighting active anti-scraping; listed here as a blocked-free source. |

---

## Cross-class ranking (auditor's read)

1. **Class 5 (PFRumors transaction wire)** — highest value/effort: proven bulk path, 2014+, day-level timestamps, genuinely new info (V1 never sees roster moves), Thu–Sat timing = the market's late-week edge.
2. **Class 1 (PFT news corpus)** — proven bulk path, 2009+, minute-level timestamps; the timing layer over official reports. Prerequisite for Class 6.
3. **Class 2 (INA rows in weekly_rosters)** — lowest effort, ground-truth inactives; verify 2018–2019 token semantics.
4. **Class 7 (snap-weighted availability)** — no new info, but the strictly better aggregation of owned data; closest to the freeze boundary.
5. **Class 6 (Sunday QB news)** — high leverage per-event, but a filtered subset of Class 1; do after Class 1.
6. **Class 3 (day-level practice)** — systematic bulk infeasible; news-mining only for notable players.
7. **Class 4 (non-injury lineup changes)** — no structured source; NLP event extraction, unproven recall.

**What was verified vs inferred:** PFT bulk path, PFRumors bulk path + lastmod contamination, ESPN/Sleeper/FantasyPros dead-ends, PFR transactions Cloudflare block, nflverse weekly-only practice_status, X pricing, nfl_data_py's missing transactions function, nflgsis gamebook URL pattern — all VERIFIED (fetched directly or by the cited third-party audit docs that fetched directly, 2026-08 sessions). Sunday-morning PFT density, PFR news archive cross-player depth, RotoWire sitemap bulk viability, NFL Pro rosterWeek history, OTC transaction archive depth — INFERRED/plausible, flagged as such. No 2023+ data was touched.
