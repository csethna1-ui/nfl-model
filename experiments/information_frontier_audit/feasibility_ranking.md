# Feasibility Ranking — Information Frontier

Ranked by expected value × feasibility. Every entry carries the honest case AGAINST it.
Ratings: HIGH / MEDIUM / LOW / INACCESSIBLE. Window: 2018–2022. Vault untouched.

---

## Top 5

### 1. ProFootballTalk news-timing corpus (injury/news arrival timestamps)
**Feasibility: HIGH** — bulk path independently verified (NBC sitemap → monthly chunks, 2009+, ~1,900 articles/mo, per-article `datePublished` verified to the minute against a fetched sample; robots.txt `Crawl-delay: 10`).
**Why it ranks first:** It is the "when did the market learn it" layer nflverse lacks. Official designations record the *outcome* of the news process; this records the *process*. Serves all three 006 cutoffs (Tuesday-AM via Mon/Tue articles, Friday via Wed–Fri, pre-kickoff via Sunday AM). It is also the general infrastructure that subsumes ranks 4 (Sunday QB news), parts of 3 (practice trajectory for notable players), and 4's lineup-change events.
**The case against:** Entity resolution (headline → player → team) is the hard part and unproven at scale. Timestamps are a "known no later than" bound, not exact wire times. Coverage skews to fantasy-relevant players and contenders — depth injuries that move lines less are underreported. And the official report already captures the final outcome: the timing layer may add little beyond what `date_modified` already gives. This is still a *news* proxy for the market's true wire (Schefter tweets), which is inaccessible.
**Effort:** Medium (~3–5 days: crawl + body fetch + timestamp extraction + name resolution).

### 2. Pro Football Rumors transaction-wire archive
**Feasibility: HIGH** — sitemap-verified bulk path, 2014+, ~29k transaction-relevant articles, per-article JSON-LD `datePublished` verified on a 325-article sample. Known trap: sitemap `<lastmod>` contaminated by a 2025 bulk retouch — must use article-body `datePublished`.
**Why it ranks second:** V1 never sees a roster move. Elevations/IR placements cluster Thu–Sat — after V1's Tuesday info state — which is exactly the market's late-week edge. Day-level timestamps, genuinely new information, zero V1 overlap.
**The case against:** Transactions are low-frequency events; the large majority are practice-squad churn the market ignores. Day-level only (no hour). Per-event market impact is unproven — most moves may carry ~zero signal, making this a sparse, noisy feature family. It is also Friday/pre-kickoff-knowable only, so it cannot help a Tuesday-AM information set.
**Effort:** Medium (~2–4 days: 13 yearly sitemap chunks + ~11k polite fetches + team/position tagging).

### 3. Confirmed inactive lists via nflverse `weekly_rosters` (INA token)
**Feasibility: HIGH** — one file per season, 2002+, verified `INA` = game-day inactive. One verification owed: `INA` token semantics documented 2020+; 2018–2019 needs a per-season check.
**Why it ranks third:** Lowest effort of any source here. Converts Questionable/Doubtful uncertainty into ground truth and captures healthy scratches — the Sunday 11:30am layer the market prices and V1 never sees.
**The case against:** Pre-kickoff-only information — useless for Tuesday or Friday prediction timestamps; it can only ever serve a Sunday-morning model or a diagnostic ("how much did inactives explain?"). It overlaps heavily with Out designations (≈ inactives anyway), so the marginal value is concentrated in the Questionable bucket (~30% of games with meaningful inactive news). Small, conditional, late.
**Effort:** Low (~1 day: token check + join to injuries).

### 4. Sunday-morning QB news (PFT-corpus subset)
**Feasibility: MEDIUM** — no separate source needed; it is a weekday/time/entity slice of rank 1 (Sunday + hour<kickoff + QB entity), ground-truthed by INA rows + snap counts (did the QB play?).
**Why it ranks fourth:** QB availability is the highest-leverage personnel news in the sport; the market's Sunday QB repricing is the largest single personnel-driven move. This is the dataset the stale-QB filter's validation never had: "what was reported Sunday AM vs what happened."
**The case against:** Rare events — a handful of genuine game-time QB decisions per season. It has no standalone value independent of rank 1 (it IS rank 1 filtered). Sunday-morning PFT density is unverified. And V1's existing stale-QB void filter already handles the production side of this — the remaining value is diagnostic, not predictive.
**Effort:** Medium, but only after rank 1 exists (marginal cost low).

### 5. IEM MOS as-issued weather forecasts (Friday 12Z runs)
**Feasibility: HIGH** — every GFS/NAM/NBS run archived with issuance timestamp, full 2018–2022, free/keyless API; stadium→ASOS mapping is ~30 rows. Precip and gust columns nflverse never carries.
**Why it ranks fifth:** It is the only weather route that passes the governing question honestly (forecasts as issued, not observed weather = postgame truth). Tuesday runs are also archived, so it can serve both Tuesday and Friday info states.
**The case against (the serious one):** Forecast ≈ observed + noise, and V1 trains on observed weather — so the incremental margin signal is approximately forecast error, which is noise by construction. This is the honest mechanism assessment, and it is weak. Wind-forecast effects are a *totals* story and this system never bets totals. The genuinely additive columns (precip probability, gusts) have no established margin mechanism. High reconstructability, low expected value.
**Effort:** Medium (~2–3 days: station mapping + per-game run pulls + MOS parse).

---

## Honorable mentions (ranked below the top 5)

- **Snap-weighted availability** (HIGH feasibility, LOW-MEDIUM effort): the strictly better aggregation of exp 005's failed count features — but it is better math on the same data, and the research program is frozen on exactly that. Documented as the boundary case, not a recommendation.
- **Opener-vs-close line movement** (MEDIUM feasibility for 2-point, LOW for intraday): passes reconstructability only via Wayback fallback since the SBR mirror died Sept 2026. Diagnostic value (why did V1 miss?) exceeds additive value; it is market-following, not new football information.
- **Referee assignments** (HIGH feasibility, LOW effort): trivially reconstructable from games.csv — but no credible margin effect (totals-heavy, Rotowire 2026: no significant splits), and a Tuesday-AM leakage trap (announced Tue/Wed).
- **Public ticket% via Wayback** (LOW feasibility): thin/irregular coverage, bet% only, market-following by construction.
- **Day-level practice participation** (LOW systematic feasibility): nflverse is weekly-only (verified); news-mining covers notable players only.
- **Non-injury lineup changes** (LOW-MEDIUM): no structured source; NLP event extraction with unproven recall.
- **Travel/schedule quirks** (HIGH feasibility, LOW effort): ancient public knowledge, market-embedded, ~zero expected residual.

## Explicitly not pursued

- **Beat-reporter information** as structured data: fundamentally un-reconstructable from free sources (verified dead ends). Do not spend effort.
- **Intraday line-movement traces**: no free structured source exists; Wayback reconstruction is high-effort, uneven, and quote-timestamps are unavailable.

---

## Inaccessible under free/keyless constraint (the gap, priced)

These are real information the market plausibly uses that we cannot obtain. Ranked by pain:

1. **X/Twitter full-archive search** — the beat-reporter timestamp gold standard (Schefter/Rapoport, exact timestamps 2018+). Pro $5k/mo **closed to new signups**; Enterprise ~$42k/mo. *This is the single most painful loss: it is the actual wire the market trades on.*
2. **Timestamped historical line-movement feeds** (DonBest / Sportradar / paid odds APIs) — *when* the market moved, not just where it closed. The timing-of-move is the closest observable to "what news arrived."
3. **Action Network PRO money%** (~$100/yr) — sharp-vs-public divergence; the informative half of betting splits is paywalled while bet% is free.
4. **Pinnacle historical odds** — the sharp-book reference line; no free tier.
5. **PFF premium grades** — would sharpen availability value-weighting beyond snap counts.
6. **FantasyPros historical news API** — structured timestamped news feed; commercial license required.
7. **Next Gen Stats premium / AWS tracking** — beyond the coarse free nflverse aggregates.
8. **Visual Crossing historical forecasts** — free tier, no card, but API-key signup violates the keyless rule.
9. **ESPN+ Insider / The Athletic / local papers** — beat texture, paywalled and unstructured.
10. **PFR transactions pages** — Cloudflare-blocked (403); effectively inaccessible without fighting anti-scraping.

**What the gap costs us:** the two most valuable inaccessible sources are *news arrival timing at wire speed* (Twitter) and *market move timing* (DonBest/Pinnacle). Our best free substitutes (PFT corpus, PFRumors) are slower, coarser, and editorially filtered versions of the same channels. Any future "we can't close the 0.33" conclusion should name these two explicitly.
