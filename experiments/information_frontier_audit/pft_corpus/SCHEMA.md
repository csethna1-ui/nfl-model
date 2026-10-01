# PFT News-Timing Corpus — Schema

**Database:** `data/pft_sitemap.db` (sqlite)
**Rosters:** `data/rosters_2018_2022.parquet` (nflreadpy, free/keyless)
**Schedules:** `data/schedules_2018_2022.parquet` (nflreadpy, free/keyless)

## Table `urls` (sitemap harvest)

| column | source | notes |
|---|---|---|
| url | sitemap `<loc>` | PK. `https://www.nbcsports.com/nfl/profootballtalk/rumor-mill/news/{slug}` |
| month | sitemap file | `YYYYMM` of the monthly sitemap chunk |
| lastmod | sitemap `<lastmod>` | minute resolution; article's sitemap timestamp |
| slug | parsed from URL | dash-joined headline slug |
| relevant | `02_filter_injury_relevant.py` | 1 = injury/availability-relevant by slug rules |
| relevant_reason | filter | token/phrase that triggered, e.g. `token:hamstring` |
| in_scope | filter | 1 = month in Aug–Jan season window (201808–201901, …, 202208–202301) |

## Table `articles` (polite crawl, Crawl-delay 10)

Raw timestamps only — no pre-bucketed cutoff labels at crawl time.

| column | source | notes |
|---|---|---|
| url | — | PK, joins to `urls` |
| slug, month, sitemap_lastmod | urls | carried over |
| date_published | JSON-LD `datePublished` | minute resolution, UTC (`…Z`) |
| date_modified | JSON-LD `dateModified` | minute resolution, UTC |
| date_created | JSON-LD `dateCreated` | CMS migration artifact (often 2023); NOT a news timestamp |
| parsely_pub_date | `<meta name="parsely-pub-date">` | independent machine timestamp, ms resolution |
| parsely_title | `<meta name="parsely-title">` | headline as seen by parser |
| parsely_tags | `<meta name="parsely-tags">` ×N (JSON list) | includes team names, e.g. `"Tennessee Titans"` — used for entity disambiguation |
| author | JSON-LD / parsely-author | PFT author |
| human_date_raw | `<div class="Page-datePublished">` | e.g. `Published September 1, 2021 02:58 AM` (ET) — the byline readers see |
| headline | `<h1 class="Page-headline">` | falls back to parsely_title |
| body_text | `.ArticlePage-articleBody` | plain text, whitespace-normalized |
| body_len | derived | chars of body_text |
| content_hash | sha1(body_text) | duplicate/empty detection |
| event_class | `04_resolve_entities.py` | `ruled_out` / `expected_to_play` / `practice_participation` / `injury_report` / `transaction` / `other` (keyword rules, heuristic) |
| qb_relevant | entity pass | 1 = ≥1 resolved QB entity (or QB keyword + name hit) |
| n_entities | entity pass | count of resolved player mentions |
| http_status, fetch_error, fetched_at | crawler | 200 / 404 / 429-backoff-exhausted etc. |

## Table `entities` (player mentions)

| column | notes |
|---|---|
| article_url | joins to `articles.url` |
| player_name | normalized (`lower`, suffix-stripped, de-punctuated), e.g. `ben roethlisberger` |
| team | resolved team abbr for the article's season; NULL if ambiguous |
| position | roster position for the article's season |
| resolution_method | `unique` (one team in season) / `tag_disambiguated` (parsely team tag broke the tie) / `ambiguous` (recorded, team NULL) |

Resolution: per-season roster name index (full names only — last-name-only
references are NOT matched; documented recall limitation). Nickname map is
curated and small (see `04_resolve_entities.py` NICKNAMES).

## Timestamp semantics

- `date_published` / `parsely_pub_date` / `human_date_raw` should agree to the
  minute (modulo ET vs UTC). Criterion 2 audits this.
- Treat stamps as **"known no later than"**: one audit-sample article showed an
  earlier human-readable date than its ISO stamp. Timestamps are safe for
  pre-cutoff *inclusion* filtering (article provably existed by stamp time),
  not for exact "news broke at HH:MM" claims.
- Derived cutoff labels (Tuesday-AM = article ET date Mon–Tue of game week;
  Friday = Wed–Fri; pre-kickoff = Sat/Sun pre-kickoff) are computed in
  analysis (`06_report_stats.py`), never stored at crawl time.

## Known corpus biases (to quantify in the pilot report)

- PFT covers contenders, fantasy-relevant skill players, and QBs
  disproportionately; linemen depth-chart moves are under-covered.
- Slug pre-filter is precision-tuned; injury news with non-injury slugs
  (e.g. pure transaction slugs hiding an injury) is missed.
- Last-name-only references missed by entity resolution (recall loss).
- `date_created` is a CMS artifact — never use as a news timestamp.
