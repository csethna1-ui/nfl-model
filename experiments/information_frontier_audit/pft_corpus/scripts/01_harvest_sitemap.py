#!/usr/bin/env python3
"""
01_harvest_sitemap.py — Harvest NBC Sports monthly sitemaps (2018-01..2022-12),
extract PFT rumor-mill article URLs + lastmod, store in sqlite.

Polite: honors robots.txt Crawl-delay: 10 between ALL requests (incl. sitemaps).
Contactable user-agent. Checkpointed per-month so reruns are cheap.

Output: data/pft_sitemap.db  (table: urls(url PK, month, lastmod, slug))
"""
import re, sqlite3, sys, time
from pathlib import Path
import requests

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
DB = DATA / "pft_sitemap.db"
UA = "NFLResearchBot/1.0 (academic injury-news timing research pilot; contact via nfl-model repo)"

ARTICLE_RE = re.compile(r"https://www\.nbcsports\.com/nfl/profootballtalk/rumor-mill/news/([a-z0-9\-]+)")
CRAWL_DELAY = 10

def get(url, session, retries=4):
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=45)
            if r.status_code == 429:
                wait = min(600, 60 * (2 ** attempt))
                print(f"  429 on {url} — backing off {wait}s", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            wait = 30 * (2 ** attempt)
            print(f"  error {e} on {url} — retry in {wait}s (attempt {attempt+1})", flush=True)
            time.sleep(wait)
    return None

def main():
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS urls(
        url TEXT PRIMARY KEY, month TEXT, lastmod TEXT, slug TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS months_done(month TEXT PRIMARY KEY, n_articles INT, fetched_at TEXT)""")
    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    months = [f"{y}{m:02d}" for y in range(2018, 2023) for m in range(1, 13)]
    todo = [m for m in months
            if not con.execute("SELECT 1 FROM months_done WHERE month=?", (m,)).fetchone()]
    print(f"months total={len(months)} todo={len(todo)}", flush=True)

    for i, month in enumerate(todo):
        sm = f"https://www.nbcsports.com/sitemap-{month}.xml"
        print(f"[{i+1}/{len(todo)}] {sm}", flush=True)
        r = get(sm, session)
        if r is None:
            print(f"  FAILED {sm} — skipping (not checkpointed, will retry next run)", flush=True)
            continue
        n = 0
        for m in ARTICLE_RE.finditer(r.text):
            url, slug = m.group(0), m.group(1)
            # lastmod: nearest <lastmod> after the <loc>
            tail = r.text[m.end():m.end()+400]
            lm = re.search(r"<lastmod>([^<]+)</lastmod>", tail)
            try:
                con.execute("INSERT OR IGNORE INTO urls(url,month,lastmod,slug) VALUES(?,?,?,?)",
                            (url, month, lm.group(1) if lm else None, slug))
                n += 1
            except sqlite3.Error as e:
                print("  db err", e)
        con.execute("INSERT OR REPLACE INTO months_done VALUES(?, ?, datetime('now'))", (month, n))
        con.commit()
        print(f"  -> {n} PFT article URLs", flush=True)
        time.sleep(CRAWL_DELAY)
    con.close()
    print("done", flush=True)

if __name__ == "__main__":
    main()
