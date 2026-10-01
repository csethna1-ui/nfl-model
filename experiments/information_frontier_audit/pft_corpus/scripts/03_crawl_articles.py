#!/usr/bin/env python3
"""
03_crawl_articles.py — Fetch injury-relevant PFT articles, politely.

- Honors robots.txt Crawl-delay: 10 (minimum 10s between requests, incl. retries).
- Contactable user-agent. Exponential backoff on 429/5xx. No evasion.
- Checkpointed per-article in sqlite; safe to interrupt and resume (Ctrl-C / reboot).
- Stores RAW timestamps only (datePublished JSON-LD, parsely, human byline).
  Derived cutoff labels (Tuesday-AM / Friday / pre-kickoff) are computed in
  analysis, never at crawl time.

Usage: ./venv/bin/python scripts/03_crawl_articles.py [--limit N]
Run long: tmux new -s pft_crawl "./venv/bin/python scripts/03_crawl_articles.py >> data/crawl.log 2>&1"

DB: data/pft_sitemap.db -> table articles
"""
import hashlib, json, re, sqlite3, sys, time
from html import unescape
from pathlib import Path
import requests

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
DB = DATA / "pft_sitemap.db"
UA = "NFLResearchBot/1.0 (academic injury-news timing research pilot; contact via nfl-model repo)"
CRAWL_DELAY = 10
COMMIT_EVERY = 5

JSONLD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
DATEPUB_DIV_RE = re.compile(r'<div class="Page-datePublished">(.*?)</div>', re.S)
H1_RE = re.compile(r'<h1[^>]*class="[^"]*Page-headline[^"]*"[^>]*>(.*?)</h1>', re.S)
BODY_RE = re.compile(r'<div class="[^"]*ArticlePage-articleBody[^"]*"[^>]*>(.*?)</div>\s*</div>', re.S)
PARSELY_DATE_RE = re.compile(r'<meta name="parsely-pub-date" content="([^"]+)"')
PARSELY_TITLE_RE = re.compile(r'<meta name="parsely-title" content="([^"]+)"')
PARSELY_TAG_RE = re.compile(r'<meta name="parsely-tags" content="([^"]+)"')
PARSELY_AUTHOR_RE = re.compile(r'<meta name="parsely-author" content="([^"]+)"')
TAG_STRIP = re.compile(r"<[^>]+>")

def clean(s):
    s = TAG_STRIP.sub(" ", s or "")
    s = unescape(s)
    return re.sub(r"\s+", " ", s).strip()

def parse_article(url, html):
    d = {"url": url}
    ld = None
    for b in JSONLD_RE.findall(html):
        try:
            j = json.loads(b.strip())
        except Exception:
            continue
        items = j if isinstance(j, list) else [j]
        for it in items:
            if isinstance(it, dict) and it.get("@type") == "Article":
                ld = it
                break
        if ld:
            break
    if ld:
        d["date_published"] = ld.get("datePublished")
        d["date_modified"] = ld.get("dateModified")
        d["date_created"] = ld.get("dateCreated")
        auth = ld.get("author")
        if isinstance(auth, list) and auth:
            d["author"] = auth[0].get("name") if isinstance(auth[0], dict) else str(auth[0])
        elif isinstance(auth, dict):
            d["author"] = auth.get("name")
    else:
        d["date_published"] = d["date_modified"] = d["date_created"] = d["author"] = None

    m = PARSELY_DATE_RE.search(html)
    d["parsely_pub_date"] = m.group(1) if m else None
    m = PARSELY_TITLE_RE.search(html)
    d["parsely_title"] = unescape(m.group(1)) if m else None
    d["parsely_tags"] = json.dumps([unescape(t) for t in PARSELY_TAG_RE.findall(html)])
    m = PARSELY_AUTHOR_RE.search(html)
    if m and not d.get("author"):
        d["author"] = unescape(m.group(1))

    m = DATEPUB_DIV_RE.search(html)
    d["human_date_raw"] = clean(m.group(1)) if m else None
    m = H1_RE.search(html)
    d["headline"] = clean(m.group(1)) if m else d.get("parsely_title")
    m = BODY_RE.search(html)
    d["body_text"] = clean(m.group(1)) if m else None
    body = d["body_text"] or ""
    d["body_len"] = len(body)
    d["content_hash"] = hashlib.sha1(body.encode()).hexdigest() if body else None
    return d

def fetch(session, url):
    """Returns (status, html_or_None, error). Implements backoff on 429/5xx."""
    backoff = 60
    for attempt in range(5):
        try:
            r = session.get(url, timeout=45)
            if r.status_code == 200:
                return 200, r.text, None
            if r.status_code in (404, 410):
                return r.status_code, None, f"http_{r.status_code}"
            if r.status_code == 429 or 500 <= r.status_code < 600:
                print(f"    {r.status_code} -> backoff {backoff}s (attempt {attempt+1})", flush=True)
                time.sleep(backoff)
                backoff = min(900, backoff * 2)
                continue
            return r.status_code, None, f"http_{r.status_code}"
        except requests.RequestException as e:
            print(f"    req error {e} -> backoff {backoff}s (attempt {attempt+1})", flush=True)
            time.sleep(backoff)
            backoff = min(900, backoff * 2)
    return None, None, "retries_exhausted"

def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS articles(
        url TEXT PRIMARY KEY, slug TEXT, month TEXT, sitemap_lastmod TEXT,
        date_published TEXT, date_modified TEXT, date_created TEXT,
        parsely_pub_date TEXT, parsely_title TEXT, parsely_tags TEXT, author TEXT,
        human_date_raw TEXT, headline TEXT, body_text TEXT, body_len INT,
        content_hash TEXT, http_status INT, fetch_error TEXT, fetched_at TEXT)""")
    rows = con.execute(
        """SELECT u.url, u.slug, u.month, u.lastmod FROM urls u
           LEFT JOIN articles a ON a.url=u.url
           WHERE u.relevant=1 AND u.in_scope=1 AND a.url IS NULL ORDER BY u.month, u.url""").fetchall()
    if limit:
        rows = rows[:limit]
    total_todo = con.execute(
        "SELECT COUNT(*) FROM urls u LEFT JOIN articles a ON a.url=u.url "
        "WHERE u.relevant=1 AND u.in_scope=1 AND a.url IS NULL").fetchone()[0]
    done = con.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    print(f"relevant todo this run={len(rows)} | overall pending={total_todo} | already done={done}", flush=True)

    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    last_req = 0.0
    n = 0
    t0 = time.time()
    try:
        for url, slug, month, lastmod in rows:
            # enforce crawl delay
            wait = CRAWL_DELAY - (time.time() - last_req)
            if wait > 0:
                time.sleep(wait)
            try:
                status, html, err = fetch(session, url)
                last_req = time.time()
                if status == 200 and html:
                    d = parse_article(url, html)
                    con.execute("""INSERT INTO articles
                        (url,slug,month,sitemap_lastmod,date_published,date_modified,
                         date_created,parsely_pub_date,parsely_title,parsely_tags,author,
                         human_date_raw,headline,body_text,body_len,content_hash,
                         http_status,fetch_error,fetched_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
                        ON CONFLICT(url) DO UPDATE SET
                         date_published=excluded.date_published, date_modified=excluded.date_modified,
                         date_created=excluded.date_created, parsely_pub_date=excluded.parsely_pub_date,
                         parsely_title=excluded.parsely_title, parsely_tags=excluded.parsely_tags,
                         author=excluded.author, human_date_raw=excluded.human_date_raw,
                         headline=excluded.headline, body_text=excluded.body_text,
                         body_len=excluded.body_len, content_hash=excluded.content_hash,
                         http_status=excluded.http_status, fetch_error=excluded.fetch_error,
                         fetched_at=excluded.fetched_at""",
                        (url, slug, month, lastmod, d["date_published"], d["date_modified"],
                         d["date_created"], d["parsely_pub_date"], d["parsely_title"],
                         d["parsely_tags"], d.get("author"), d["human_date_raw"],
                         d["headline"], d["body_text"], d["body_len"], d["content_hash"],
                         status, err))
                else:
                    con.execute("""INSERT INTO articles
                        (url,slug,month,sitemap_lastmod,http_status,fetch_error,fetched_at)
                        VALUES(?,?,?,?,?,?,datetime('now'))
                        ON CONFLICT(url) DO UPDATE SET
                         http_status=excluded.http_status, fetch_error=excluded.fetch_error,
                         fetched_at=excluded.fetched_at""",
                        (url, slug, month, lastmod, status, err))
                n += 1
            except Exception as e:
                # one bad article must never kill the run; record and continue
                print(f"    ARTICLE ERROR {url}: {e}", flush=True)
                try:
                    con.execute("""INSERT INTO articles
                        (url,slug,month,sitemap_lastmod,http_status,fetch_error,fetched_at)
                        VALUES(?,?,?,?,?,?,datetime('now'))
                        ON CONFLICT(url) DO UPDATE SET
                         http_status=excluded.http_status, fetch_error=excluded.fetch_error,
                         fetched_at=excluded.fetched_at""",
                        (url, slug, month, lastmod, -1, f"article_error:{e}"))
                except Exception as e2:
                    print(f"    DB ERROR recording failure: {e2}", flush=True)
                n += 1
            if n % COMMIT_EVERY == 0:
                con.commit()
                el = time.time() - t0
                print(f"  {done+n} fetched this session (run total {n}) | {el/n:.1f}s/article | elapsed {el/3600:.1f}h",
                      flush=True)
    except KeyboardInterrupt:
        print("interrupted — progress committed, resume any time", flush=True)
    finally:
        con.commit()
        con.close()
    print(f"crawl run finished: {n} attempted", flush=True)

if __name__ == "__main__":
    main()
