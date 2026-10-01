#!/bin/bash
# check_status.sh — one-line crawl progress report
cd "$(dirname "$0")/.." || exit 1
sqlite3 data/pft_sitemap.db "
SELECT 'done=' || COUNT(*) FROM articles
UNION ALL SELECT 'ok200=' || COUNT(*) FROM articles WHERE http_status=200
UNION ALL SELECT 'failed=' || COUNT(*) FROM articles WHERE http_status!=200 OR http_status IS NULL;"
sqlite3 data/pft_sitemap.db \
  "SELECT 'remaining=' || COUNT(*) FROM urls u LEFT JOIN articles a ON a.url=u.url WHERE u.relevant=1 AND u.in_scope=1 AND a.url IS NULL;"
tail -2 data/crawl.log
tmux ls 2>&1 | grep -c pft_crawl | xargs -I{} echo "tmux_session_alive={}"
