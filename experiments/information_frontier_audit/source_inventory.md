# Information Frontier — Source Inventory

**Date:** 2026-09-29 | **Type:** read-only research inventory. No modeling, no fitting, no evaluation.
**Constraint:** free/keyless sources only. **Vault 2023–2025 untouched.** Analysis window: 2018–2022.
**Governing question per source:** historically reconstructable (2018+) AND genuinely available before the prediction timestamp?
**Timing vocabulary:** Tuesday-AM (V1's info state) → Friday → pre-kickoff (incl. 90-min inactives) → postgame.
**Provenance tags:** VERIFIED = fetched/inspected directly or by a cited third-party audit that fetched directly. INFERRED = reasoned, flagged. REPORTED = third-party claim, not re-verified.

Already covered by prior work and NOT re-audited here: nflverse weekly injury designations (2009+, `date_modified`), rosters_weekly/depth_charts/snap_counts, PBP, game-time observed weather, single undated historical spread snapshot.

---

## 1. Exact injury/news timing (when the market learned, not the final designation)

**What:** Per-event timestamps of injury/availability news breaking (Sunday-night injury, Monday beat updates, Wed–Fri practice news, coach comments) — as distinct from nflverse's final weekly designation + `date_modified` (81% Friday filings = official-report cadence, not news cadence).
**Why the market might have it:** Books reprice within minutes of Schefter/Rapoport tweets and team announcements; V1's effective info state is ~Tuesday AM. Mon–Wed severity/practice news is a genuinely different channel from Wed–Fri official filings.
**Free/keyless sources:**
- **ProFootballTalk via NBC Sports sitemap — VERIFIED workable.** `https://www.nbcsports.com/sitemap.xml` → monthly `sitemap-YYYYMM.xml`; PFT NFL articles Sept 2009–present (~1,900/mo, ~13% injury-relevant). Per-article timestamps via sitemap `<lastmod>` AND article JSON-LD `datePublished` (third-party audit fetched a 2020-09-28–10-01 sample: agree to the minute). robots.txt `Crawl-delay: 10`. Audit doc: `https://github.com/ryanpmcintire/nfl_py3/blob/HEAD/docs/injury_news_sourcing.md` (299,739 dated PFT NFL URLs, 202/202 months, 0 failures).
- **PFR player news archives — VERIFIED to exist, depth spot-checked.** `https://www.pro-football-reference.com/players/news.fcgi?id={pfr_id}` — dated aggregation from RotoWire, RotoBaller, KFFL, beat sites; dated entries back to 2012 (spot-verified).
- **RotoWire news sitemap — plausible, NOT bulk-verified.** `https://www.rotowire.com/sitemap.xml` + `news-sitemap.php` in robots.txt; dated news items on player pages.
- Wayback `espn.com/nfl/injuries` — works but REDUNDANT (same official board as nflverse). ESPN news API — dead for history (`dates=` ignored). Sleeper API — live snapshot only. X/Twitter — INACCESSIBLE (see §14).
**Reconstructability (2018+):** YES — PFT 2009+, PFR-news 2012+.
**Timestamps:** Per-article to the minute; covers Tuesday-AM, Friday, and pre-kickoff windows. Caveat: treat as "known no later than" bound (one sampled article had earlier human-readable date than ISO stamp).
**Mechanism:** Earlier + more precise severity/availability knowledge than official filings; enables Tuesday-state sharpening and a Sunday-morning QB-decision layer. New info = *when* and *how bad*, not the final designation.
**Overlap risk:** LOW on the timing dimension; the final designation overlaps nflverse.
**Feasibility: HIGH.** **Effort:** Medium — sitemap crawl (~275 monthly chunks) + body fetch of injury subset (~250/mo × 60 mo) + player-name resolution.

## 2. Confirmed inactive lists (90-min pre-kickoff)

**What:** Official 7-man inactive list per team, announced 90 min before kickoff — ground truth for who sits; resolves Questionable uncertainty; captures healthy scratches.
**Why the market might have it:** Market prices the Sunday 11:30am ET release directly; V1 only knows Friday designations.
**Free/keyless sources:**
- **nflverse `weekly_rosters` — VERIFIED.** `roster_weekly_{season}.csv`, 2002+; status `INA` = game-day inactive (weekly data only), `status_description_abbr` e.g. `I01`. Verified via nflverse issue nflverse/nflverse-rosters#56 and two project docs (`INA` 2020+). **Caveat: `INA` token documented 2020+; 2018–2019 token semantics need per-season verification.**
- **NFL GSIS gamebook PDFs — VERIFIED to exist, free.** `www.nflgsis.com/{season}/{type}/{week}/{gameid}/Gamebook.pdf` — "Not Active"/"Did Not Play" sections; 2004–2024 confirmed; no login. Bulk = PDF parse (heavy but mechanical).
- PFR box scores / ESPN via Wayback — no inactive lists (INFERRED from page structure).
**Reconstructability:** YES via weekly_rosters (pending 2018–19 token check).
**Timestamps:** Weekly grain only — the 90-min *announcement time* is not timestamped anywhere free; list *content* fully reconstructable; timing edge only via Class 1 news corpus.
**Mechanism:** Converts Questionable/Doubtful uncertainty into ground truth; healthy scratches reveal coaching intent. Small-sample by construction (~30% of games with meaningful inactive news).
**Overlap risk:** HIGH for Out designations (≈ inactives); LOW for Questionable resolution + healthy scratches.
**Feasibility: HIGH.** **Effort:** Low — one file/season; join INA rows to injuries (after token check).

## 3. Late practice participation (day-level Wed/Thu/Fri)

**What:** Per-day DNP/Limited/Full trajectory — the mid-week signal the market reads.
**Why the market might have it:** Beat writers report each day; market digests the trajectory; our injuries table collapses the week to one value.
**Free/keyless sources:**
- **nflverse `practice_status` — VERIFIED weekly-only, NOT day-level** (two independent docs; `date_modified` = filing time, not practice day). Effectively the last-reported status.
- **Official NFL injury-report PDFs (nflcommunications.com) — day-level EXISTS, archive FRAGMENTED.** Wed/Thu/Fri Participation columns (VERIFIED example: Patriots 2014 Week 16 PDF). No central archive; ~2,880 PDFs across per-team URL schemes, many dead.
- **Class 1 news corpus — practical substitute** for fantasy-relevant players only (editorial, not systematic).
**Reconstructability:** Systematic day-level = NO at reasonable effort. Notable-player day-level via news = YES.
**Timestamps:** Day-level by construction where available.
**Mechanism:** Practice trajectory predicts Questionable→active/inactive conversion better than a single Friday status.
**Overlap risk:** MEDIUM — final Friday status already in V1's info set; the *trajectory* is new.
**Feasibility: LOW** systematic / **MEDIUM** via news for notable players. **Effort:** High (PDF archaeology) or medium (news mining).

## 4. Starting lineup changes announced pre-game (non-injury)

**What:** Benchings, depth-chart promotions for non-injury reasons, announced pre-kickoff.
**Why the market might have it:** A starting-OL/CB benching announced Fri/Sat moves the line; V1 never sees it.
**Free/keyless sources:** PFR `teams/{abbr}/lineups.htm` — season-grain, post-hoc (useless weekly). nflverse depth_charts — weekly, no announcement timestamps. **Only route: news-event extraction from Class 1/5 corpora** (benchings are dated news events; coverage skews notable).
**Reconstructability:** NO structured source; YES-ISH via news mining for high-profile cases.
**Timestamps:** Article-dated (day grain) where reported.
**Mechanism:** Pure "who is playing" information orthogonal to V1's team-strength estimates.
**Overlap risk:** LOW — V1 has no lineup-change signal (snap counts reveal it ex-post = leakage, not signal).
**Feasibility: LOW-MEDIUM.** **Effort:** High — event-extraction NLP, unproven recall.

## 5. Real-time roster transactions (elevations, signings, IR moves)

**What:** Dated roster moves — practice-squad elevations (often Saturday), signings, IR placements, activations, waivers — with day-level timing.
**Why the market might have it:** Moves cluster Thu–Sat, after V1's Tuesday state and most line movement; late-week pricing absorbs them; V1 never sees a roster move.
**Free/keyless sources:**
- **Pro Football Rumors transaction wire — VERIFIED workable, best candidate.** `https://www.profootballrumors.com/sitemap.xml` → yearly `sitemap-posttype-post.YYYY.xml`; 2014+, 72,368 articles, ~29,414 transaction-relevant; daily "Minor NFL Transactions" round-ups. Per-article JSON-LD `datePublished` verified on 325-article sample (100% match). robots.txt `Crawl-delay: 1`. **Caveat (VERIFIED): sitemap `<lastmod>` contaminated by a 2025-12 bulk retouch — use JSON-LD `datePublished`, never `<lastmod>`.** Audit: `https://github.com/ryanpmcintire/nfl_py3/blob/HEAD/docs/pfr_transactions_sourcing.md`.
- nfltraderumors.co transactions category — dated daily posts, paginated, no sitemap verification.
- nflverse `load_trades` — trades only, coarse timing. **nfl_data_py has NO transactions function (VERIFIED absent).** NFL.com wire — live only. PFR `years/{Y}/transactions.htm` — Cloudflare-blocked (403).
**Reconstructability:** YES — 2014+, day-level `datePublished`.
**Timestamps:** Day-level (hour in JSON-LD where needed). Typically Thu–Sat → Friday/pre-kickoff knowable, generally NOT Tuesday-knowable.
**Mechanism:** IR/elevation = direct dated downgrade/upgrade at a position; move clusters = depth crisis. Orthogonal to V1.
**Overlap risk:** LOW — V1 never sees roster moves; partial overlap with `weekly_rosters` status changes without timing.
**Feasibility: HIGH.** **Effort:** Medium — 13 yearly sitemap chunks; ~11k article fetches at ~1s polite ≈ 3 hrs.

## 6. Late QB decisions (Sunday-morning game-time calls)

**What:** QB-specific availability news Sunday morning (Schefter "expected to start", warmup reports, 11:30am inactive confirmation) — the highest-leverage personnel news in the sport.
**Free/keyless sources:** **PFT corpus filtered to Sunday mornings** (weekday/time slice on Class 1; Sunday-morning density INFERRED, not measured). PFR QB news pages (dated Sunday entries exist). RotoWire Sunday updates — live only. `weekly_rosters` INA — the outcome, not the news. X/Twitter — INACCESSIBLE.
**Reconstructability:** YES for the news layer; decision outcome ground-truthed by INA rows + snap counts (did the QB play?).
**Timestamps:** Sunday-morning representable from article timestamps; the 90-min announcement not independently timestamped free.
**Mechanism:** Market's Sunday QB repricing is the largest single personnel-driven move; "reported Sunday AM vs happened" is the dataset the stale-QB filter's validation lacks.
**Overlap risk:** LOW-MEDIUM — overlaps designation inputs but adds the Sunday-morning *resolution* layer.
**Feasibility: MEDIUM** (builds on Class 1). **Effort:** Medium — QB entity filtering + time slicing.

## 7. Player-specific availability/value (snap-weighted, starter-vs-backup)

**What:** Not "3 players out" but "how much on-field value is missing": snap-share-weighted loss with starter-vs-backup distinction. (Exp 005 tested raw counts and failed; this is the strictly better aggregation of the same table.)
**Free/keyless sources (all nflverse, all 2018–2022):** `load_snap_counts` (2012+), `load_injuries` (2009+), `load_depth_charts` (2001+, `pos_rank` = starter flag). Construction: rolling pre-week avg snap pct × designation weight × starter flag → team-week "value lost" by position group.
**Reconstructability:** YES — all inputs cover the window.
**Timestamps:** Inherits injuries `date_modified` → Friday-knowable, not Tuesday-knowable.
**Mechanism:** Starting LT/CB absence moves margin more than backup ST absence.
**Overlap risk:** HIGH on inputs (same table 005 used); the *aggregation* is new. **PROGRAM NOTE: this sits at the research-freeze boundary — better math on the same data. Documented as an audit finding, not a proposal.**
**Feasibility: HIGH.** **Effort:** Low-medium — three joins + rolling averages; no scraping.

## 8. Pre-kickoff weather forecast evolution (Tue→Sun)

**What:** Forecasts *as issued* during game week for the stadium (e.g., "Friday 12Z run's Sunday wind forecast") — distinct from game-time observed weather already in games.csv.
**Why the market might have it:** Books move totals/spreads on wind/precip forecasts Tue→Sun; V1 trains on *observed* weather = postgame information.
**Free/keyless sources:**
- **IEM MOS archive — VERIFIED, best route.** `https://mesonet.agron.iastate.edu/mos/` — GFS MOS 2003→now, NAM MOS 2008→now, NBS Nov 2018→now; every run archived **with issuance timestamp**; point guidance at ASOS stations (every NFL stadium city has one); temp/wind/gusts/precip-probability — **precip and gusts are columns nflverse never carries**. Free, keyless, CSV/JSON API (`/api/1/mos.txt?station=KXXX&runtime=...&model=GFS`).
- **IEM NWS text (AFOS) archive — VERIFIED.** Zone Forecasts with timestamps back to ~1998; bulk via `/cgi-bin/afos/retrieve.py`; text parsing per stadium zone.
- **Open-Meteo Previous Runs — VERIFIED by live probe, 2021–2022 only.** `previous-runs-api.open-meteo.com` served real Nov 2021 GFS data (0 nulls/72h); nothing for 2018–2020. IEM MOS wins for the full window.
- Visual Crossing historical forecasts — EXCLUDED (API key signup required).
**Reconstructability:** YES — full 2018–2022 via IEM MOS.
**Timestamps:** Friday 12Z run = Friday-knowable; Tuesday runs archived = Tuesday-knowable.
**Mechanism (honest):** WEAK-to-speculative for margin. Forecast ≈ observed + noise, and V1 trains on observed — incremental margin signal ≈ forecast error (noise by construction). Wind-forecast effects are a *totals* story (never bet). Precip/gusts are the one plausibly additive piece.
**Overlap risk:** HIGH — temp/wind already in env features.
**Feasibility: HIGH** (reconstructability). **Effort:** Medium — stadium→ASOS mapping (~30), per-game run pulls, parse.

## 9. Line movement timing (when/why the line moved)

**What:** The path opener (Tue) → moves → close (Sun). We hold one undated snapshot per game; timing tells you *what moved it* (a Friday move = late news).
**Free/keyless sources:**
- **sportsbookreviewsonline.com open/close archive (2007–2021) — REPORTED, now DEAD.** Verified live Aug 2026 by a third-party project; **returns 404 as of 2026-09-29** ("entirely dead," Sept 2026). Fallback: Wayback captures. Even at best: 2 points, no intraday, "Open" column untimestamped (vs true Tuesday opener: mean |diff| 1.36, r=0.949).
- **covers.com SportsOddsHistory — closing only** (back to 1977, free HTML; self-documented closing). Current-season "line moves" graphs exist but completed slates disappear.
- **Wayback CDX reconstruction of intraday movement — INFERRED viable, LOW feasibility.** Technique demonstrated for Action Network public-betting pages (153 captures, 800 REG games); same applies to SBR/Covers/Oddsshark pages 2018–2022. Irregular captures, per-page parsing, capture-time ≠ quote-time. HIGH effort, uneven coverage.
- VegasInsider/SBR current platforms — historical data removed (REPORTED, 2023 forum).
**Reconstructability:** Opener-vs-close = MEDIUM (Wayback fallback; SpreadSpoke/Kaggle open+close CSVs as non-web fallback). Intraday trace = LOW.
**Timestamps:** Opener+close = week-level; Wayback = irregular capture times.
**Mechanism:** Opener→close direction correlates with outcomes (informed money), but the movement is mostly useful for CLV-style grading and inferring *what news arrived midweek* — which injury/news research covers via other channels. A pure opener-vs-close feature is market-following, not new information.
**Overlap risk:** By construction — the line snapshot already embeds this. Diagnostic > additive.
**Feasibility: MEDIUM** (2-point) / **LOW** (intraday). **Effort:** Low (2-point) to HIGH (Wayback intraday).

## 10. Market information aggregation (consensus vs sharp-book divergence)

**What:** Which books moved; ticket% vs money% divergence (reverse line movement / "sharp money") — the market's revealed information a single-book snapshot can't show.
**Free/keyless sources:**
- **Action Network public betting splits — partially reconstructable via Wayback (REPORTED).** Live page shows **% of bets FREE**; **% of money is PRO-gated** (~$100/yr). Third-party Wayback backfill: 153 captures, 1,658 rows, 800 REG games ≤72h pre-kickoff, 2018–2026; **2018–Oct 2022 = bet% only, no money%**; median reading 45.2h pre-kickoff; best season 34% of games.
- Sharp-book/multi-book history (Pinnacle, The Odds API historical, Sports Insights, Don Best) — all paid/keyed → INACCESSIBLE.
- Free Kaggle sample: 2025 opener + nine-book closes — wrong era, one season.
**Reconstructability:** bet% partially (thin, irregular); money% = NO.
**Timestamps:** Wayback snapshots, ~2 days pre-kickoff typical.
**Mechanism (honest):** Reverse-line-movement is genuinely informative market microstructure — but it is *market* information, not *football* information; the model would follow the market with a lag. Circularity risk in backtest.
**Overlap risk:** Direct — transformation of the same line data.
**Feasibility: LOW** (bet% only, thin coverage; money% paywalled). **Effort:** Medium (Wayback CDX + era-aware parsing).

## 11. Beat-reporter information

**What:** Local reporting texture — "team looked flat Thursday," beat-writer injury hunches, game-plan leaks.
**Verdict: fundamentally un-reconstructable in structured, timestamped form from free sources. Do not pursue.**
**Dead ends (VERIFIED):** ESPN news API ignores date params (current only); ESPN injuries API live-only; FantasyPros news API 403 / commercial license (plus survivorship bias on historical pages); Sleeper live-only; The Athletic + local papers paywalled; ESPN team pages via Wayback = unstructured HTML across 32 teams × 5 seasons, no schema, timestamps are publish not event times.
**Mechanism:** Real in principle, but official-report + market-repricing captures the price-relevant core within minutes; the soft remainder is unquantifiable and likely noise-dominated.
**Feasibility: INACCESSIBLE** as structured data. Unstructured Wayback-NLP = LOW feasibility, VERY HIGH effort, dubious signal.

## 12. Referee/crew assignments

**What:** Which referee (crew chief) officiates each game. Crews differ in penalty rates.
**Free/keyless sources:**
- **Football Zebras weekly assignment posts** (`footballzebras.com/category/assignments/`) — one post/week, historical index back to 2010; published **typically Tuesday for Sunday games**.
- **nflverse games.csv `referee` column (REPORTED)** — ~99.6–100% coverage 2021–2025; box-score-recorded = postgame provenance, but crew identity ≡ Wednesday-of-game-week knowledge → reconstructable 2018–2022 with zero scraping.
**Reconstructability:** YES.
**Timestamps — KEY CAVEAT:** announced Tue/Wed of game week → **NOT known at Tuesday-AM prediction time** (lookahead leakage if used there). Friday-prediction info states only.
**Mechanism (honest):** Mostly a TOTALS phenomenon (never bet). Rotowire 2026: none of 17 officials' totals splits significant; ATS crew trends "suggestive rather than proven." No credible *margin* effect; penalty-asymmetry channel worth maybe a fraction of a point, heavily confounded.
**Overlap risk:** None — V1 has no officiating features.
**Feasibility: HIGH. Expected margin value: LOW. Effort:** Low (column join + timestamp gate).

## 13. Travel/schedule quirks beyond rest differentials

**What:** International games, altitude, dome↔outdoor transitions, timezone travel, bye edges, road-trip clustering. (Rest differentials already modeled.)
**Free/keyless sources:** nflverse schedules (`stadium`, `roof`, `surface`, `location`, `away_rest`, `home_rest`) — all computable: international flag from stadium (London/Munich/Mexico City), altitude (Denver 5,280 ft; Mexico City 7,280 ft) via static lookup, timezone travel from team-city↔stadium, dome↔outdoor from `roof` values, trip clustering from schedule alone.
**Reconstructability:** YES, trivially.
**Timestamps:** Knowable at schedule release (May) — Tuesday-AM safe.
**Mechanism (honest):** Decades-old public findings; market priced them long before 2018. Expected residual ≈ zero. Coverage item, not frontier.
**Overlap risk:** Rest/travel already modeled; remainder is static schedule metadata.
**Feasibility: HIGH. Effort:** Low (~a day). **Priority: lowest.**

---

## 14. Inaccessible under free/keyless constraint (identified but not obtainable)

| Source | What it would give | Why excluded |
|---|---|---|
| **X/Twitter full-archive search** | Beat-reporter timestamp gold standard: Schefter/Rapoport tweets with exact timestamps 2018+ | Pro $5,000/mo **closed to new signups**; Enterprise ~$42k/mo; free tier read-blocked. The single most painful loss. |
| **DonBest / Sportradar / real-time odds APIs** | Timestamped line-movement history (when the market moved, not just where it closed) | Paid subscriptions; The Odds API free tier is current-only. |
| **Action Network PRO money%** (~$100/yr) | Sharp-vs-public money divergence, the informative half of splits | Paywalled; free bet% only. |
| **Pinnacle historical odds** | Sharp-book line history, the true "market" reference | Paid/keyed, no free tier. |
| **PFF premium grades** | Player-level grades to sharpen availability value-weighting beyond snap counts | Subscription paywall. |
| **Next Gen Stats premium / AWS tracking** | Player tracking beyond free nflverse NGS aggregates | Premium paywalled; free aggregates (2016+) are coarse. |
| **FantasyPros historical news API** | Structured timestamped injury/news feed | Commercial license required. |
| **ESPN+ Insider / The Athletic / local papers** | Beat-reporter texture | Paywalled, unstructured. |
| **Visual Crossing historical forecasts** | As-issued forecast archive in one API | Free tier needs no card but **API key signup required** — violates keyless rule. |
| **Stathead** | Queryable historical splits | Paid subscription. |
| **PFR transactions pages** | Structured transaction history | Not paywalled but **Cloudflare-blocked (403)** — effectively inaccessible without fighting anti-scraping. |

## 15. Explicitly rejected (verified dead ends — do not spend effort)

- ESPN news/injuries APIs for history (date params ignored; live-only)
- Sleeper API for history (single `news_updated`; live snapshot only)
- FantasyPros unauthenticated endpoints (403)
- Wayback ESPN injury board (redundant with nflverse)
- Wayback rotoworld player-news (9 captures in all of 2019)
- nfl_data_py transactions function (does not exist)
- sportsbookreviewsonline.com open/close mirror (dead as of 2026-09-29; treat all free odds archives as perishable — mirror on first pull)
- Structured beat-reporter reconstruction (fundamentally un-reconstructable)
