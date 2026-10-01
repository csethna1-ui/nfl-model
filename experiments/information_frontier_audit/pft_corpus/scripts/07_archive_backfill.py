#!/usr/bin/env python3
"""
07_archive_backfill.py — Fetch pending PFT articles from web.archive.org.

WHY: robots.txt on www.nbcsports.com demands Crawl-delay: 10 for all
user-agents, capping the polite live crawl at ~11.5s/article (~29h remaining).
The Wayback Machine puts ZERO load on NBC's live servers and has ~93%
coverage of the old-style PFT URLs, so this backfills the bulk of the corpus
in a few hours. Articles with no archived capture stay pending for the live
crawler (03_crawl_articles.py), which resumes afterward.

Provenance: rows written here carry archive_url/archive_ts columns so the
pilot report can disclose the mixed provenance. Article content is the
contemporaneous archived HTML (earliest 200 capture), parsed with an
old-markup parser (pre-2023 PFT theme: NewsArticle JSON-LD, h1.entry-title,
span.entry-date, div.entry-content).

- Old-style URL: https://profootballtalk.nbcsports.com/YYYY/MM/DD/<slug>/
  derived from sitemap lastmod (tries exact date, then +/-1 day, https+http).
- Checkpointed per-article in sqlite; safe to interrupt and resume.
- Respects archive.org: modest concurrency (5 workers), no hammering.

Usage: ./venv/bin/python scripts/07_archive_backfill.py [--limit N] [--workers N]
"""
import hashlib, json, re, sqlite3, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
from threading import Lock
import requests
import urllib.parse

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
DB = DATA / "pft_sitemap.db"
UA = "NFLResearchBot/1.0 (academic injury-news timing research pilot; contact via nfl-model repo)"
COMMIT_EVERY = 20

JSONLD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
H1_ENTRY_RE = re.compile(r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>(.*?)</h1>', re.S)
ENTRY_DATE_RE = re.compile(r'<span[^>]*class="[^"]*entry-date[^"]*"[^>]*>(.*?)</span>', re.S)
BYLINE_RE = re.compile(r'<span[^>]*class="[^"]*byline[^"]*"[^>]*>(.*?)</span>', re.S)
ENTRY_CONTENT_RE = re.compile(r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>(.*?)</div>\s*<!--\s*\.entry-content\s*-->', re.S)
# fallbacks for the current (new-style) theme, in case a capture postdates the migration
H1_NEW_RE = re.compile(r'<h1[^>]*class="[^"]*Page-headline[^"]*"[^>]*>(.*?)</h1>', re.S)
DATEPUB_DIV_RE = re.compile(r'<div class="Page-datePublished">(.*?)</div>', re.S)
BODY_NEW_RE = re.compile(r'<div class="[^"]*ArticlePage-articleBody[^"]*"[^>]*>(.*?)</div>\s*</div>', re.S)
TAG_STRIP = re.compile(r"<[^>]+>")

def clean(s):
    s = TAG_STRIP.sub(" ", s or "")
    s = unescape(s)
    s = s.replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()

def parse_old_article(canonical_url, html):
    """Parse pre-2023 PFT article HTML (WordPress theme)."""
    d = {"url": canonical_url}
    ld = None
    for b in JSONLD_RE.findall(html):
        try:
            j = json.loads(b.strip())
        except Exception:
            continue
        items = j if isinstance(j, list) else [j]
        for it in items:
            if isinstance(it, dict) and it.get("@type") in ("NewsArticle", "Article"):
                ld = it
                break
        if ld:
            break
    if ld:
        d["date_published"] = ld.get("datePublished")
        d["date_modified"] = ld.get("dateModified")
        d["headline_ld"] = clean(ld.get("headline"))
        auth = ld.get("author")
        if isinstance(auth, list) and auth:
            a0 = auth[0]
            d["author"] = a0.get("name") if isinstance(a0, dict) else str(a0)
        elif isinstance(auth, dict):
            d["author"] = auth.get("name")
        else:
            d["author"] = None
    else:
        d["date_published"] = d["date_modified"] = d["author"] = None
        d["headline_ld"] = None

    m = H1_ENTRY_RE.search(html)
    if not m:
        m = H1_NEW_RE.search(html)
    d["headline"] = clean(m.group(1)) if m else d.get("headline_ld")

    m = ENTRY_DATE_RE.search(html)
    if not m:
        m = DATEPUB_DIV_RE.search(html)
    d["human_date_raw"] = clean(m.group(1)) if m else None

    if not d.get("author"):
        m = BYLINE_RE.search(html)
        if m:
            d["author"] = re.sub(r"^Posted by\s+", "", clean(m.group(1)), flags=re.I)

    m = ENTRY_CONTENT_RE.search(html)
    if not m:
        m = BODY_NEW_RE.search(html)
    body = clean(m.group(1)) if m else None
    # strip common junk blocks that survive tag-stripping
    d["body_text"] = body
    d["body_len"] = len(body) if body else 0
    d["content_hash"] = hashlib.sha1(body.encode()).hexdigest() if body else None
    d["parsely_pub_date"] = d["parsely_title"] = d["parsely_tags"] = None
    return d

def old_style_candidates(slug, lastmod):
    """Yield candidate old-style URLs: exact lastmod date, then +/-1 day, https then http."""
    try:
        base = datetime.fromisoformat(lastmod)
    except Exception:
        return
    seen = set()
    for delta in (0, -1, 1):
        dt = base + timedelta(days=delta)
        for scheme in ("https", "http"):
            u = f"{scheme}://profootballtalk.nbcsports.com/{dt:%Y/%m/%d}/{slug}/"
            if u not in seen:
                seen.add(u)
                yield u

def cdx_lookup(session, old_url):
    """Return (timestamp, archived_url) of earliest 200 capture, or None."""
    q = ("http://web.archive.org/cdx/search/cdx?url="
         + urllib.parse.quote(old_url, safe="")
         + "&output=json&limit=5&filter=statuscode:200&collapse=digest")
    try:
        r = session.get(q, timeout=60)
        rows = r.json()
    except Exception:
        return None
    if not rows or len(rows) < 2:
        return None
    # rows[0] is header; take earliest timestamp
    cands = sorted(rows[1:], key=lambda x: x[1])
    ts, url = cands[0][1], cands[0][2]
    return ts, url

def fetch_archived(session, ts, old_url):
    url = f"https://web.archive.org/web/{ts}id_/{old_url}"
    try:
        r = session.get(url, timeout=90)
        if r.status_code == 200 and r.text:
            return r.text
    except requests.RequestException:
        pass
    return None

UPSERT = """INSERT INTO articles
    (url,slug,month,sitemap_lastmod,date_published,date_modified,
     date_created,parsely_pub_date,parsely_title,parsely_tags,author,
     human_date_raw,headline,body_text,body_len,content_hash,
     http_status,fetch_error,fetched_at,archive_url,archive_ts)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),?,?)
    ON CONFLICT(url) DO UPDATE SET
     date_published=excluded.date_published, date_modified=excluded.date_modified,
     human_date_raw=excluded.human_date_raw, headline=excluded.headline,
     body_text=excluded.body_text, body_len=excluded.body_len,
     content_hash=excluded.content_hash, author=excluded.author,
     http_status=excluded.http_status, fetch_error=excluded.fetch_error,
     fetched_at=excluded.fetched_at, archive_url=excluded.archive_url,
     archive_ts=excluded.archive_ts"""

def main():
    workers = 5
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    if "--workers" in sys.argv:
        workers = int(sys.argv[sys.argv.index("--workers") + 1])

    con = sqlite3.connect(DB, check_same_thread=False)
    con.execute("PRAGMA busy_timeout=60000")
    for col in ("archive_url", "archive_ts"):
        try:
            con.execute(f"ALTER TABLE articles ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass  # already exists
    con.commit()

    rows = con.execute(
        """SELECT u.url, u.slug, u.month, u.lastmod FROM urls u
           LEFT JOIN articles a ON a.url=u.url
           WHERE u.relevant=1 AND u.in_scope=1 AND a.url IS NULL ORDER BY u.month, u.url""").fetchall()
    if limit:
        rows = rows[:limit]
    total = len(rows)
    print(f"archive backfill: {total} pending articles, {workers} workers", flush=True)
    if not total:
        return

    lock = Lock()
    stats = {"ok": 0, "no_capture": 0, "fetch_fail": 0, "parse_empty": 0, "n": 0}
    t0 = time.time()

    def worker(item):
        url, slug, month, lastmod = item
        session = requests.Session()
        session.headers.update({"User-Agent": UA})
        hit = None
        for cand in old_style_candidates(slug, lastmod):
            hit = cdx_lookup(session, cand)
            if hit:
                break
            time.sleep(0.2)
        if not hit:
            return ("no_capture", item, None)
        ts, old_url = hit
        html = fetch_archived(session, ts, old_url)
        time.sleep(0.3)
        if not html:
            return ("fetch_fail", item, None)
        d = parse_old_article(url, html)
        if not d["body_text"]:
            return ("parse_empty", item, None)
        return ("ok", item, (d, f"https://web.archive.org/web/{ts}id_/{old_url}", ts))

    def write_result(status, item, payload):
        url, slug, month, lastmod = item
        with lock:
            if status == "ok":
                d, archive_url, archive_ts = payload
                con.execute(UPSERT, (url, slug, month, lastmod, d["date_published"],
                    d["date_modified"], None, None, None, None, d.get("author"),
                    d["human_date_raw"], d["headline"], d["body_text"], d["body_len"],
                    d["content_hash"], 200, None, archive_url, archive_ts))
            else:
                # leave pending for the live crawler; record nothing
                pass
            stats[status] += 1
            stats["n"] += 1
            n = stats["n"]
            if n % COMMIT_EVERY == 0:
                con.commit()
                el = time.time() - t0
                print(f"  {n}/{total} | ok={stats['ok']} nocap={stats['no_capture']} "
                      f"fetchfail={stats['fetch_fail']} parseempty={stats['parse_empty']} | "
                      f"{el/n:.1f}s/article | elapsed {el/3600:.1f}h", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(worker, item) for item in rows]
        try:
            for f in as_completed(futs):
                try:
                    status, item, payload = f.result()
                except Exception as e:
                    print(f"    WORKER ERROR: {e}", flush=True)
                    continue
                write_result(status, item, payload)
        except KeyboardInterrupt:
            print("interrupted — progress committed, resume any time", flush=True)
    con.commit()
    el = time.time() - t0
    print(f"backfill finished: {stats['n']}/{total} in {el/3600:.1f}h | "
          f"ok={stats['ok']} no_capture={stats['no_capture']} "
          f"fetch_fail={stats['fetch_fail']} parse_empty={stats['parse_empty']}", flush=True)
    con.close()

if __name__ == "__main__":
    main()
