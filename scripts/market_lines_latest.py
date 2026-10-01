#!/usr/bin/env python3
"""market_lines_latest.py — read hourly market-line snapshots.

Snapshots live in data/market_hourly/{game_lines,prop_lines}/ and are named
  {kind}_{season}_w{week}_{utcstamp}.json   (utcstamp = YYYYMMDDTHHMMSSZ)
Files are append-only and never overwritten; this module only reads.

Two selection modes:
  - latest_*: newest *successful* snapshot (skips throttled/failed runs, so a
    throttled hour never blanks live display lines).
  - snapshot_at_or_before(): newest successful snapshot with
    captured_at <= cutoff — the selector for the Friday 18:00 CT evaluation
    rule (docs/PROSPECTIVE_PROTOCOL.md). Pass cutoff as an ISO timestamp with
    offset, e.g. "2026-10-02T18:00:00-05:00".
"""
import glob
import json
import os
from datetime import datetime

DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HOURLY = os.path.join(DATA_ROOT, "market_hourly")


def _files(kind, season, week):
    pat = os.path.join(HOURLY, kind, f"{kind}_{season}_w{week}_*.json")
    return sorted(glob.glob(pat))


def _load(fp):
    with open(fp) as f:
        return json.load(f)


def _is_ok(d):
    return d.get("status") == "ok"


def latest_snapshot(kind, season, week, require_ok=True):
    """Newest snapshot dict, or None. require_ok=True skips throttled/failed."""
    best = None
    for fp in _files(kind, season, week):
        d = _load(fp)
        if require_ok and not _is_ok(d):
            continue
        best = d  # files sort oldest->newest by utcstamp
    return best


def snapshot_at_or_before(kind, season, week, cutoff_iso, require_ok=True):
    """Newest successful snapshot with captured_at <= cutoff_iso.

    The Friday-cutoff selector: evaluation uses the latest snapshot the model
    was allowed to see (<= Friday 18:00 CT), never anything after.
    """
    cutoff = datetime.fromisoformat(cutoff_iso)
    best, best_ts = None, None
    for fp in _files(kind, season, week):
        d = _load(fp)
        if require_ok and not _is_ok(d):
            continue
        try:
            ts = datetime.fromisoformat(d["captured_at"])
        except (KeyError, ValueError):
            continue
        if ts <= cutoff and (best_ts is None or ts > best_ts):
            best, best_ts = d, ts
    return best


def latest_game_lines_by_book(season, week, book):
    """{AWAY_HOME: [spread_home, total]} for one book ('draftkings'|'bovada').

    spread_home follows the existing convention: + means home favored
    (matches data/market_2026_wN.json).
    """
    d = latest_snapshot("game_lines", season, week)
    if not d:
        return {}, None
    out = {}
    for g in d.get("games", []):
        b = g.get("books", {}).get(book)
        if b:
            out[g["game_key"]] = [b["spread_home"], b["total"]]
    return out, d.get("captured_at")


def latest_prop_lines(season, week):
    """(lines, source, captured_at) from the newest successful prop snapshot.

    Each line: {player|None, bovada_player, team, market, line, line_type,
    source, captured_at}. Returns (None, None, None) when no snapshot exists.
    """
    d = latest_snapshot("prop_lines", season, week)
    if not d:
        return None, None, None
    return d.get("lines", []), d.get("source"), d.get("captured_at")


if __name__ == "__main__":
    import sys
    season, week = int(sys.argv[1]), int(sys.argv[2])
    gl, ts = latest_game_lines_by_book(season, week, "draftkings")
    pl, psrc, pts = latest_prop_lines(season, week)
    print(f"game_lines: {len(gl)} games @ {ts}")
    print(f"prop_lines: {len(pl) if pl else 0} lines from {psrc} @ {pts}")
