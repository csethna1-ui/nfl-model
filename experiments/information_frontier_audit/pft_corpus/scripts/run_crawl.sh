#!/bin/bash
# run_crawl.sh — self-healing wrapper for the PFT crawl.
# Relaunches 03_crawl_articles.py on unexpected exit (max 20 restarts).
# The crawler itself is checkpointed per-article and resumes automatically.
# Polite by construction: Crawl-delay 10 inside the crawler, backoff on 429.
cd "$(dirname "$0")/.." || exit 1
for i in $(seq 1 20); do
  ~/workspace/nfl-model/venv/bin/python scripts/03_crawl_articles.py >> data/crawl.log 2>&1
  rc=$?
  echo "$(date -u '+%F %T'): crawler exited rc=$rc (run $i/20)" >> data/crawl.log
  remaining=$(sqlite3 data/pft_sitemap.db \
    "SELECT COUNT(*) FROM urls u LEFT JOIN articles a ON a.url=u.url WHERE u.relevant=1 AND u.in_scope=1 AND a.url IS NULL;")
  echo "$(date -u '+%F %T'): remaining=$remaining" >> data/crawl.log
  if [ "$remaining" -eq 0 ]; then
    echo "$(date -u '+%F %T'): CRAWL COMPLETE" >> data/crawl.log
    break
  fi
  sleep 300
done
echo "$(date -u '+%F %T'): wrapper giving up after 20 restarts" >> data/crawl.log
