#!/usr/bin/env python3
"""Step 30: Pull V2 research sources (read-only data acquisition).

Downloads (keyless, free):
  - PFR advanced weekly stats: release tag `pfr_advstats`,
    files advstats_week_{pass,rush,rec,def}_{season}.parquet, 2018-2026
  - nflverse snap counts: release tag `snap_counts`,
    files snap_counts_{season}.csv, 2018-2026

Writes: data/v2/raw/<file>, data/v2/raw/manifest.json (url, bytes, sha256, retrieved_at).

NO model fitting. Acquisition only.
"""
import csv
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
RAW = f"{DATA}/v2/raw"
BASE = "https://github.com/nflverse/nflverse-data/releases/download"
SEASONS = list(range(2018, 2027))
PFR_TYPES = ["pass", "rush", "rec", "def"]

UA = {"User-Agent": "nfl-model-v2-research/1.0 (keyless research pull)"}


def fetch(url, dest):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        blob = r.read()
    with open(dest, "wb") as f:
        f.write(blob)
    return blob


def main():
    os.makedirs(RAW, exist_ok=True)
    manifest = []
    jobs = []
    for s in SEASONS:
        for t in PFR_TYPES:
            fn = f"advstats_week_{t}_{s}.parquet"
            jobs.append((f"{BASE}/pfr_advstats/{fn}", f"{RAW}/{fn}"))
        jobs.append((f"{BASE}/snap_counts/snap_counts_{s}.csv",
                     f"{RAW}/snap_counts_{s}.csv"))
    ok, fail = 0, []
    for url, dest in jobs:
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            print(f"skip (cached) {os.path.basename(dest)}")
            ok += 1
            continue
        try:
            blob = fetch(url, dest)
            manifest.append({
                "file": os.path.basename(dest),
                "url": url,
                "bytes": len(blob),
                "sha256": hashlib.sha256(blob).hexdigest(),
                "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            })
            print(f"pulled {os.path.basename(dest)} ({len(blob)//1024} KB)")
            ok += 1
        except Exception as e:
            print(f"FAIL {url}: {e}")
            fail.append(url)
    mp = f"{RAW}/manifest.json"
    prev = json.load(open(mp)) if os.path.exists(mp) else []
    prev.extend(manifest)
    json.dump(prev, open(mp, "w"), indent=1)
    print(f"\ndone: {ok} ok, {len(fail)} failed -> {RAW}")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
