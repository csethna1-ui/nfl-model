# Market/Weather/Officiating Information Audit — scratch dossier

Read-only research, 2026-09-29. No model training. No 2023+ data touched.
Governing question per source: historically reconstructable (2018+) AND genuinely
available before the prediction timestamp?

Legend for provenance tags used below:
- **VERIFIED**: checked directly this session (live probe/fetch or official docs page).
- **REPORTED**: claimed by a third-party source found in search (cited); not re-verified.
- **INFERRED**: reasoning from verified/reported facts, flagged as such.

---

## Class 1 — Pre-kickoff weather FORECAST evolution (Tue→Sun), not observed weather

**What the info is, concretely:** The sequence of forecasts as issued during game
week for the stadium location — e.g., "what the Friday 12Z model run said about
Sunday 1pm wind at Soldier Field" — as distinct from the game-time observed
temp/wind already in games.csv.

**Why the market might have it and we don't:** Books move totals (and to a lesser
extent spreads) on wind/precip forecasts Tue→Sun. V1 trains on *observed* weather,
which is postgame information; the market at prediction time only had the forecast.

### Source candidates

**(a) IEM MOS archive — BEST ROUTE (VERIFIED).**
- Archive status page: https://mesonet.agron.iastate.edu/mos/ (VERIFIED via search-result
  capture of the official status table)
- Coverage: GFS MOS **16 Dec 2003 → realtime** (runs 00/06/12/18Z, projections 6h–192h);
  NAM MOS **9 Dec 2008 → realtime** (to 60h); NBS (National Blend of Models, the NWS
  operational guidance) **7 Nov 2018 → realtime**. All cover the full 2018–2022 window.
- Every run is archived **with its issuance timestamp** — so "the Friday 12Z run's
  60-hour projection for Sunday" is exactly reconstructable.
- Resolution: MOS is point guidance at ASOS stations — every NFL stadium city has one
  (station list = 3-letter FAA IDs). Variables include temp, wind, gusts, precip
  probability/amount — **precip and gusts are columns nflverse never carries**.
- Access: free, keyless, no signup. Download interface
  https://mesonet.agron.iastate.edu/mos/fe.phtml and a CSV/JSON API, e.g.
  `/api/1/mos.txt?station=KAMW&runtime=2009-01-10%2012:00Z&model=GFS`
  (REPORTED from the official docs page).
- Effort: MEDIUM — map stadium→nearest ASOS station (~30 mappings), pull one run per
  game-day (e.g., Friday 12Z), parse MOS text/CSV.

**(b) IEM NWS text product (AFOS) archive — human-forecaster alternative (VERIFIED).**
- https://github.com/akrherz/iem/blob/HEAD/docs/datasets/afos.md: "Some data back to
  1996, but archive quality and completeness greatly improves for dates after 1998."
- Contains Zone Forecasts (ZFP PILs) — the actual NWS forecaster-issued text for the
  stadium's zone, issued ~4x/day with timestamps. Finder: http://mesonet.agron.iastate.edu/wx/afos/
- Free, keyless, bulk download at /cgi-bin/afos/retrieve.py (REPORTED).
- Effort: MEDIUM-HIGH — text parsing of ZFP products per stadium zone per Friday.

**(c) Open-Meteo Previous Runs API — partial, late window only (VERIFIED by live probe).**
- Official docs https://open-meteo.com/en/docs/historical-forecast-api: fixed lead-time
  variables (`temperature_2m_previous_day1..7`); archive starts Jan 2024, **GFS from
  Mar 2021**, JMA from 2018 (useless for NFL).
- Live probe this session: `previous-runs-api.open-meteo.com/v1/forecast` for Denver
  2021-11-05→07 with `models=gfs_seamless` returned HTTP 200, all 72 hours populated
  for `temperature_2m_previous_day3` (0 nulls) — so **2021 and 2022 seasons** get
  lead-time-specific GFS forecasts; 2018–2020 do NOT via this source.
- Note conflict: one third-party doc claims ~15-day retention for previous-runs; the
  official docs + my live probe contradict that (2021 data served). Treat official
  docs as authoritative.
- Historical Forecast API (stitched first-hours, ~2021+) is NOT a decision-time
  replay — "contextual history, not exact decision-time replay" per docs.

**(d) Visual Crossing — EXCLUDED by keyless rule.** "Historical forecasts" exist in the
Timeline API and the free tier needs no credit card, but it **requires an API key
signup** (VERIFIED: https://www.visualcrossing.com/weather-api/). Flagged on the
INACCESSIBLE list below (keyed, not paywalled).

**Timestamp availability:** Friday-run MOS/zone forecasts = Friday-knowable. Tuesday
runs also archived (Tue-knowable for opener-time predictions).

**Expected mechanism (honest):** WEAK-to-speculative for margin. V1 trains on observed
weather, which ≈ Friday forecast + noise; the conditional effect of weather on margin
is already largely captured by the observed-weather features. The genuinely new
component is the *forecast itself as priced by the market midweek* — but the market
and NWS guidance derive from the same model runs, so the incremental signal over
observed weather is approximately forecast error, which is noise by construction.
Known exception with real literature: wind forecasts move TOTALS more than outcomes
justify — but this system never bets totals. Precip/gusts columns (absent from
nflverse) are the one plausibly additive piece.

**Overlap risk with V1:** HIGH — forecast ≈ observed + noise; temp/wind already in
env features (55.9% outdoor coverage; 2022 hole noted in prior audits).

**Feasibility: HIGH** (reconstructability) — the data is all there, free and
timestamped. **Effort: MEDIUM** (station mapping + per-game run pulls + parse).

---

## Class 2 — Line movement timing (when/why the historical line moved)

**What the info is:** We hold one undated spread snapshot per game. The market's
information arrives through the *path*: opener (Tue) → injury/weather-driven moves →
close (Sun). Timing tells you *what moved it* (e.g., a Friday move = late news).

### Source candidates

**(a) Opener vs close, free static archive (REPORTED, currently flaky — VERIFY).**
- `https://www.sportsbookreviewsonline.com/scoresoddsarchives/nfl/nfloddsarchives.htm`
  hosted 15 season pages (2007-08 through 2021-22) with Open/Close spread+total
  columns per game, free static HTML, permissive robots.txt — independently measured
  live by a third-party project on 2026-08-19 (100% match 2009–2021 vs their close).
- **As of 2026-09-29 the URL returns 404** (my fetch this session failed; a second
  project notes "sportsbookreviewsonline.com is entirely dead (root 404)" in Sept 2026).
  Do NOT treat as a live dependency. Fallback: Wayback Machine captures of these pages.
- Even at its best this is **2 points, no intraday, and the "Open" column has no
  capture timestamp** (third-party measurement: SBR Open vs true Tuesday opener,
  mean |diff| 1.36 pts, r=0.949 — correlated, not point-identical).

**(b) covers.com SportsOddsHistory — closing archive (REPORTED).**
- e.g. https://www.covers.com/sportsoddshistory/nfl-reg/?y=2017&sa=nfl&a=esbl&p=reg
  Game-level spreads/totals back to 1977, free HTML, but **closing odds only**
  (self-documented as closing, courtesy of PFR) — no opener, no movement.
- Covers' current-season odds pages have "line moves" graphs (timestamped, per the
  2010 SBR forum thread), but **only for current/upcoming games** — completed slates
  disappear. No historical endpoint.

**(c) VegasInsider / SBR current platforms (REPORTED, dead end for history).**
- SBR forum 2023: "I used to use the odds page here to go back and see
  open/close/movement from previous years but it looks like that data is gone here";
  VegasInsider "changed the platform… so you can only see last year."
  (https://www.sportsbookreview.com/forum/players-talk/1999944-where-can-i-find-opening-and-closing-nfl-lines-from-past-seasons)

**(d) Wayback Machine reconstruction of intraday movement (INFERRED viable, LOW feasibility).**
- The technique is demonstrated working for another odds-adjacent dataset:
  Action Network's public-betting page was backfilled 2018–2026 via Wayback CDX
  (153 day-collapsed captures, 800 REG games matched; REPORTED from
  https://github.com/ryanpmcintire/nfl_py3/blob/HEAD/docs/public_betting_sourcing.md).
  The same CDX approach applies to SBR/Covers/Oddsshark odds pages for 2018–2022.
- Reality check: captures are irregular (some days/weeks missing), each snapshot needs
  per-page parsing, and the timestamps are *capture* times, not quote times. Effort HIGH;
  coverage uneven. No free source gives a structured full intraday trace with quote
  timestamps.

**Timestamp availability:** Opener+close = week-level (Tue→Sun), no intraday. Wayback
snapshots = irregular capture timestamps.

**Expected mechanism:** Opener→close movement direction correlates with outcomes
(some of it is informed money). But the *level* of the line already reflects the info
set at snapshot time; the movement itself is mostly useful for CLV-style grading and
for inferring what news arrived midweek — which the injury/news research already
covers via other channels. A pure opener-vs-close feature is a market-following
feature, not new information.

**Overlap risk with V1:** By construction — the line snapshot already embeds this.
Value is diagnostic (why did V1 miss), not additive.

**Feasibility: MEDIUM** for opener-vs-close (if the SBR mirror is revived or via
Wayback; SpreadSpoke/Kaggle open+close CSVs are a non-web fallback), **LOW** for any
intraday trace. **Effort: LOW (2-point) to HIGH (Wayback intraday).**

---

## Class 3 — Market information aggregation (consensus vs sharp-book divergence)

**What the info is:** Which books moved and whether ticket% vs money% diverged
(reverse line movement / "sharp money") — the market's own revealed information that
a single-book snapshot can't show.

### Source candidates

**(a) Action Network public betting splits — partially reconstructable via Wayback (REPORTED).**
- Live page https://www.actionnetwork.com/nfl/public-betting shows **% of bets FREE**;
  **% of money is PRO-gated** ("Unlock all money percentages… with Action PRO")
  — money% is the sharp-revealing half and it is paywalled (forum cites ~$100/yr).
- Historical: a third-party project backfilled the page via **Wayback CDX**:
  153 captures, 1,658 game rows, 800 REG games matched to schedule ≤72h pre-kickoff,
  seasons 2018–2026; 2018–Oct 2022 era has **bet% only, no money%**; median reading
  **45.2h before kickoff**; best season 34% of games (2022).
  (REPORTED: https://github.com/ryanpmcintire/nfl_py3/blob/HEAD/docs/public_betting_sourcing.md)
- So: historical *public ticket%* is partially reconstructable free; historical
  *money%* is not.

**(b) Sharp-book / multi-book historical archives — INACCESSIBLE.**
- Pinnacle (the sharp reference book) publishes no free historical feed.
- The Odds API: key + paid for historical (free tier is current-only).
- Sports Insights / Don Best: paid, keyed.
- A free CC-BY-NC Kaggle sample exists with 2025 opener + nine-book closes (REPORTED)
  — wrong era (outside 2018–2022) and one season only; illustrates format, not a source.
- nflverse's line is a single book's undated snapshot (per the audit brief).

**Timestamp availability:** Wayback snapshots = irregular, ~2 days pre-kickoff typical.
Live splits = current only.

**Expected mechanism (honest):** Reverse-line-movement / money-vs-tickets divergence
is a genuinely informative market microstructure signal (it IS what sharp bettors
watch). But it is *market* information, not *football* information — it tells you the
market moved, not why, and the model would be following the market with a lag. Also
note the circularity: any backtest using it must respect the snapshot timestamp.

**Overlap risk with V1:** Direct — it's a transformation of the same line data.

**Feasibility: LOW** (bet% only, thin coverage, irregular timestamps; money% paywalled).
**Effort: MEDIUM** (Wayback CDX + era-aware parsing).

---

## Class 4 — Beat-reporter information

**What the info is:** Local reporting texture — "team looked flat in Thursday practice,"
beat-writer injury hunches, game-plan leaks — the soft information layer between the
official injury report and kickoff.

**Verdict up front: fundamentally un-reconstructable in structured, timestamped form
from free sources. (VERIFIED dead ends below.)**

### What was checked

- **ESPN news API**: no historical query capability — `dates=` parameter silently
  ignored, returns only current news (REPORTED, measured by a third party 2026-08:
  https://github.com/ryanpmcintire/nfl_py3/blob/HEAD/docs/injury_news_sourcing.md).
- **ESPN injuries API**: live snapshot only; `?season=` ignored.
- **FantasyPros news API**: 403 without key; "historical/bulk access needs a
  commercial license" (REPORTED, same doc). FantasyPros historical projection pages
  are additionally survivorship-biased (retired players dropped) — unusable as history.
- **Sleeper API**: live snapshot only (single `news_updated` field, no event history).
- **The Athletic**: paywalled. **Local newspapers**: paywalled archives, no structured
  API, per-outlet formats.
- **ESPN team pages via Wayback**: technically fetchable but unstructured article HTML
  across 32 teams × 5 seasons — article-level NLP at massive effort, no consistent
  schema, no entity normalization, timestamps are publish times (not event times).
- **ProFootballTalk headline archives**: same Wayback-unstructured problem.

**Timestamp availability:** N/A — no structured source exists.

**Expected mechanism:** Real in principle (local reporters do break injury news hours
before officials), but the official injury-report channel + market repricing already
captures the price-relevant core of it within minutes; the residual "practice looked
flat" texture is unquantifiable and likely noise-dominated.

**Overlap risk with V1:** Partial — the stale-QB filter + official reports cover the
hard core; the soft remainder is what's un-reconstructable.

**Feasibility: INACCESSIBLE** as structured data. Unstructured Wayback-NLP route = LOW
feasibility, VERY HIGH effort, dubious signal. **Say it plainly: do not pursue.**

---

## Class 5 — Referee / crew assignments

**What the info is:** Which referee (crew chief) officiates each game. Crews differ in
penalty rates, which shifts game flow.

### Source candidates

- **Football Zebras weekly assignment posts (REPORTED/VERIFIED index).**
  https://www.footballzebras.com/category/assignments/ — one post per week with every
  game's referee, full historical index (posts found for 2010, 2017, 2020, 2022–2026;
  robots.txt crawlable per third-party measurement:
  https://github.com/ryanpmcintire/nfl_py3/blob/HEAD/docs/referee_assignments_capture.md).
  Posts are published **typically Tuesday for that week's Sunday games** (publish
  dates establish this; one source summarizes "assignments are known by Wednesday of
  the game week").
- **nflverse games.csv `referee` column (REPORTED):** 46-column schema confirmed to
  include `referee` with ~99.6–100% coverage 2021–2025
  (https://github.com/liddar12/nfl2026/blob/HEAD/docs/roadmap/rel18/FEASIBILITY.md).
  This is the box-score-recorded referee = postgame provenance, but crew identity is
  point-in-time-equivalent to Wednesday of game week (per the capture doc above) —
  reconstructable for all of 2018–2022 with zero scraping via games.csv.
- PFR box-score "Officials" sections list the full crew (REPORTED in the task brief;
  not independently re-verified; unnecessary given the above two routes).

**Timestamp availability — THE KEY CAVEAT:** assignments are announced **Tuesday/
Wednesday of game week**. At a **Tuesday-AM prediction timestamp the referee is NOT
yet known** — it is a midweek-known feature. Usable for Friday-prediction info states
only; using it in a Tuesday-AM backtest = lookahead leakage. Any pilot must gate on
post-announcement timestamps.

**Expected mechanism (honest):** Mostly a TOTALS phenomenon, and this system never
bets totals. Evidence: Rotowire's 2026 referee-betting-trends analysis
(https://www.rotowire.com/football/article/nfl-referee-assignments-betting-trends-by-crew-133202)
found **none of the 17 officials' totals splits statistically significant** and labels
the ATS crew trends "suggestive rather than proven." A 2020 fan-compiled ref-stats
table shows home/road ATS wiggles (e.g., Cheffers 42.1% home) that smell like
small-sample noise. No peer-reviewed-quality evidence was found for a *margin*
effect; the plausible channel (penalty-yardage asymmetry favoring home teams) is
worth maybe a fraction of a point and heavily confounded with crew quality.

**Overlap risk with V1:** None — V1 has no officiating features.

**Feasibility: HIGH** (reconstructable 2018+ from games.csv alone). **Expected margin
value: LOW.** **Effort: LOW** (column join + timestamp gate).

---

## Class 6 — Travel / schedule quirks beyond rest differentials

**What the info is:** Schedule-structure effects not captured by rest-day
differentials: international games, altitude, dome↔outdoor transitions, timezone
(circadian) travel, bye-week edges, road-trip clustering.

**What nflverse already provides (REPORTED, games.csv 46-col schema):**
`away_rest`, `home_rest` (bye + short-week edges — IN the model per the brief),
`roof`, `surface`, `stadium`, `stadium_id`, `location`, `temp`, `wind`.

**Quirky-but-reconstructable features NOT already captured (all INFERRED from schema):**
1. **International/neutral-site flag** — computable from stadium (London/Munich/
   Mexico City/São Paulo/Madrid). Counts per season are documented (2018: 3, 2019: 5,
   2021: 2, 2022–24: 5 each; REPORTED). Both teams travel; home-field is muted.
2. **Altitude** — static per stadium (Denver 5,280 ft; Mexico City 7,280 ft). The
   known effect is on *visitors* at altitude. Static lookup, trivially joinable via
   stadium_id.
3. **Timezone travel** — computable from team city ↔ stadium timezone (e.g., West
   Coast team at 1pm ET). Long-studied public effect, partially totals-side.
4. **Dome↔outdoor transitions** — derivable from the `roof` field's per-game values
   (open/closed/outdoors/dome); retractable-roof stadiums show both.
5. **Road-trip clustering / home-away-home stretches** — computable from the schedule
   alone.

**Timestamp availability:** All knowable at schedule release (May) — Tuesday-AM safe.

**Expected mechanism (honest):** These are decades-old public findings; the market has
priced them since long before 2018. Expected residual edge ≈ zero. This class is a
coverage/sanity item, not an information frontier.

**Overlap risk with V1:** Rest/travel differentials already modeled; the remainder is
static schedule metadata.

**Feasibility: HIGH. Effort: LOW (a day). Priority: lowest — brief by design.**

---

## INACCESSIBLE list (paywalled/keyed but clearly valuable)

| Source | What it would give | Why excluded |
|---|---|---|
| Action Network PRO money% splits (~$100/yr, per 2023 forum) | Historical sharp-vs-public money divergence | Paywalled; bet% free but money% is the informative half |
| Pinnacle historical odds API | Sharp-book line history, the true "market" reference | Paid/keyed, no free tier |
| The Odds API historical | Multi-book timestamped history | Key + paid for history |
| Sports Insights / Don Best | Real-time + historical steam/line moves | Paid subscriptions |
| Visual Crossing "historical forecasts" | As-issued forecast archive in one API | Free tier, no card — but **API key signup required**, violates keyless rule |
| FantasyPros news API (historical) | Timestamped injury/news feed | Commercial license required |
| The Athletic / local papers | Beat-reporter texture | Paywalled, unstructured |
| Full intraday line-movement trace (any vendor) | Quote-level movement with timestamps | No free structured source exists at all |

---

## Cross-class ranking (reconstructability × expected margin value)

1. **IEM MOS/GFS as-issued forecasts (Class 1a)** — only class-1 route that fully
   passes the governing question (2018+, Friday-timestamped, keyless). Case against:
   high overlap with V1's observed weather; margin mechanism speculative; precip/gusts
   are the only plausibly additive columns.
2. **Opener-vs-close movement (Class 2a/b)** — passes reconstructability (with the
   SBR-mirror reliability caveat). Case against: it's market data, not new football
   information; diagnostic value > additive value.
3. **Referee assignments (Class 5)** — trivially reconstructable, zero V1 overlap.
   Case against: totals-heavy phenomenon, no credible margin effect, Tuesday-AM
   leakage trap.
4. **Public ticket% via Wayback (Class 3a)** — partially reconstructable. Case
   against: thin/irregular coverage, no money%, market-following by construction.
5. **Travel quirks (Class 6)** — trivially reconstructable. Case against: ancient
   public knowledge, market-embedded, ~zero expected residual.
6. **Beat reporters (Class 4)** — does not pass the governing question. Do not pursue
   in structured form.

## Notes / limitations of this audit
- Web sources verified 2026-09-29; link rot is real (the SBR mirror died between Aug
  and Sep 2026 — treat every free odds archive as perishable; mirror on first use).
- Third-party GitHub docs cited (ryanpmcintire/nfl_py3, liddar12/nfl2026, etc.) are
  other researchers' measured claims, tagged REPORTED — useful corroboration, not
  primary verification, except where I probed directly (Open-Meteo).
- No 2023+ data was read, listed, or computed on. No bulk downloads performed; the
  single Open-Meteo probe was a 2.4 KB API response.
