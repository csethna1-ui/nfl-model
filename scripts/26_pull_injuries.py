#!/usr/bin/env python3
"""Step 26: daily nflverse injury pull -> versioned snapshot.

Writes data/injuries/snapshots/injuries_YYYY-MM-DD.parquet. NEVER overwrites
a previous day's file: if today's file already exists the pull is skipped
(unless --force, which still writes a new timestamped variant, never clobbering).

Captures the full status/practice fields nflverse provides plus a pulled_at
timestamp. Appends one record to data/injuries/logs/pull_log.jsonl.

Usage:
    ./venv/bin/python scripts/26_pull_injuries.py [--season 2026] [--force]
"""
import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
from injury_lib import (ensure_dirs, utcnow_iso, today_str, snapshot_path,
                        append_log)

DATA = os.path.join(REPO_ROOT, "data")

KEEP_COLS = ["season", "season_type", "game_type", "team", "week", "gsis_id",
             "position", "full_name", "first_name", "last_name",
             "report_primary_injury", "report_secondary_injury", "report_status",
             "practice_primary_injury", "practice_secondary_injury",
             "practice_status"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--force", action="store_true",
                    help="re-pull even if today's snapshot exists (writes a "
                         "-repull variant; never overwrites)")
    args = ap.parse_args()
    ensure_dirs()

    day = today_str()
    dest = snapshot_path(day)
    if os.path.exists(dest) and not args.force:
        print(f"snapshot {dest} already exists — skipping pull (use --force to re-pull)")
        append_log("pull_log", {"event": "skipped", "day": day,
                                "reason": "snapshot already exists"})
        return
    if os.path.exists(dest) and args.force:
        dest = dest.replace(".parquet", "-repull.parquet")

    import nfl_data_py as nfl
    import pandas as pd
    pulled_at = utcnow_iso()
    inj = nfl.import_injuries([args.season])
    cols = [c for c in KEEP_COLS if c in inj.columns]
    inj = inj[cols].copy()
    inj["pulled_at"] = pulled_at
    inj["snapshot_day"] = day

    inj.to_parquet(dest, index=False)
    n = len(inj)
    weeks = sorted(int(w) for w in inj["week"].dropna().unique())
    statuses = inj["report_status"].fillna("").str.lower().value_counts().to_dict()
    print(f"pulled {n} injury rows (season {args.season}, weeks {weeks}) -> {dest}")
    print(f"report_status distribution: {statuses}")
    append_log("pull_log", {"event": "pull", "day": day, "season": args.season,
                            "rows": n, "weeks": weeks,
                            "status_distribution": statuses, "dest": dest,
                            "pulled_at": pulled_at})


if __name__ == "__main__":
    main()
