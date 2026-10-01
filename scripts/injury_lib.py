#!/usr/bin/env python3
"""Shared helpers for the Phase-1 injury plumbing (production bug fix, not research).

Layout under data/injuries/:
    snapshots/injuries_YYYY-MM-DD.parquet   versioned daily pulls, never overwritten
    availability_current.json               rebuilt after every pull/diff (live view)
    availability_friday_2026_w<N>.json      frozen at the Friday 18:00 CT cutoff
    logs/pull_log.jsonl                     one record per pull
    logs/diff_log.jsonl                     one record per diff
    logs/void_disposition.jsonl             one record per void-layer decision

Cutoff discipline: the Friday prediction uses ONLY the Friday-frozen
availability file. Saturday/Sunday diffs update availability_current.json,
which feeds the live dashboard view and ad-hoc void re-checks, but must
NEVER rewrite a Friday-frozen file or the Friday predictions CSV.
"""
import json
import os
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
INJ_DIR = f"{DATA}/injuries"
SNAP_DIR = f"{INJ_DIR}/snapshots"
LOG_DIR = f"{INJ_DIR}/logs"
CURRENT_PATH = f"{INJ_DIR}/availability_current.json"

TRIGGER = {"out", "doubtful"}          # void rule trigger set (unchanged)
NOTABLE = {"out", "doubtful", "questionable"}


def ensure_dirs():
    for d in (INJ_DIR, SNAP_DIR, LOG_DIR):
        os.makedirs(d, exist_ok=True)


def utcnow_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def snapshot_path(day=None):
    return f"{SNAP_DIR}/injuries_{(day or today_str())}.parquet"


def friday_path(season, week):
    return f"{INJ_DIR}/availability_friday_{season}_w{week}.json"


def append_log(name, record):
    ensure_dirs()
    record = dict(record)
    record.setdefault("ts", utcnow_iso())
    with open(f"{LOG_DIR}/{name}.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")


def norm_status(s):
    try:
        import math
        if s is None or (isinstance(s, float) and math.isnan(s)):
            return ""
    except Exception:
        pass
    s = str(s).strip().lower()
    return "" if s in ("nan", "none") else s


def load_qb1():
    """Expected starting QB per team, from the maintained qb_point_values file."""
    with open(f"{DATA}/qb_point_values.json") as f:
        raw = json.load(f)
    return {t: d["qb1"] for t, d in raw["teams"].items()}


def _last_name(name):
    parts = str(name).replace(".", " ").split()
    return parts[-1].lower() if parts else ""


def resolve_backup_qb(team, starter_name):
    """Best-effort backup: non-starter QB on the team with the most 2026 pass
    attempts in the local player_games cache. Compares on last name because
    name formats differ across sources ('Baker Mayfield' vs 'B.Mayfield').
    Returns 'TBD' when unresolvable."""
    try:
        import pandas as pd
        pg = pd.read_parquet(f"{DATA}/player_games.parquet")
        qbs = pg[(pg["season"] == 2026) & (pg["team"] == team)].copy()
        sl = _last_name(starter_name)
        qbs = qbs[qbs["player_name"].map(_last_name) != sl]
        qbs = qbs.groupby("player_name")["pass_att"].sum().sort_values(ascending=False)
        if len(qbs):
            return str(qbs.index[0])
    except Exception:
        pass
    return "TBD"


def load_snapshot(day=None):
    import pandas as pd
    p = snapshot_path(day)
    if not os.path.exists(p):
        return None
    return pd.read_parquet(p)


def latest_snapshot_day():
    if not os.path.isdir(SNAP_DIR):
        return None
    files = sorted(f for f in os.listdir(SNAP_DIR)
                   if f.startswith("injuries_") and f.endswith(".parquet"))
    if not files:
        return None
    return files[-1][len("injuries_"):-len(".parquet")]


def build_availability(df, pulled_at, season=2026):
    """Build the current-availability state from a snapshot DataFrame.

    Returns a dict with as_of metadata, per-team QB status (starter-resolved),
    full notable-injury list (all positions), and status counts. Never touches
    the Friday-frozen files.
    """
    qb1 = load_qb1()
    df = df.copy()
    df["status_norm"] = df["report_status"].map(norm_status)
    df["prac_norm"] = df["practice_status"].map(norm_status)

    qb_flags = []
    notable = []
    for _, r in df.iterrows():
        st = r["status_norm"]
        pn = r["prac_norm"]
        if st not in NOTABLE and not pn:
            continue
        entry = {
            "player": r["full_name"],
            "team": r["team"],
            "position": r["position"],
            "week": int(r["week"]),
            "report_status": (str(r["report_status"]).strip()
                              if norm_status(r["report_status"]) else None),
            "practice_status": (str(r["practice_status"]).strip()
                                if norm_status(r["practice_status"]) else None),
            "primary_injury": (str(r["report_primary_injury"]).strip()
                               if norm_status(r["report_primary_injury"]) else None),
        }
        if st in NOTABLE:
            notable.append(entry)
        if r["position"] == "QB" and st in NOTABLE:
            is_starter = str(r["full_name"]).lower() == str(qb1.get(r["team"], "")).lower()
            qb_flags.append({**entry, "is_expected_starter": is_starter,
                             "triggers_void": is_starter and st in TRIGGER})

    counts = {s: int((df["status_norm"] == s).sum()) for s in sorted(set(df["status_norm"])) if s}
    return {
        "as_of": pulled_at,
        "season": season,
        "snapshot_rows": int(len(df)),
        "status_counts": counts,
        "starting_qb_flags": sorted(qb_flags, key=lambda e: (e["team"], e["player"])),
        "notable_injuries": sorted(notable, key=lambda e: (e["team"], e["position"], e["player"])),
        "note": ("Statuses are the latest nflverse weekly snapshot; the feed has no "
                 "per-row date_modified, so 'when the market learned it' is NOT in this data."),
    }


def write_current(avail):
    ensure_dirs()
    with open(CURRENT_PATH, "w") as f:
        json.dump(avail, f, indent=1)
    return CURRENT_PATH


def freeze_friday(season, week, cutoff_label="Friday 18:00 America/Chicago"):
    """Copy the current availability into the Friday-frozen file for (season, week).
    Called once by the Friday flow. Refuses to overwrite an existing freeze
    (delete it explicitly if a re-freeze is truly intended)."""
    ensure_dirs()
    if not os.path.exists(CURRENT_PATH):
        raise SystemExit("no availability_current.json — run 26_pull_injuries.py and 27_injury_diff.py first")
    dest = friday_path(season, week)
    if os.path.exists(dest):
        raise SystemExit(f"refusing to overwrite existing Friday freeze {dest}")
    with open(CURRENT_PATH) as f:
        avail = json.load(f)
    avail["frozen_for_prediction"] = {
        "season": season, "week": week,
        "cutoff": cutoff_label,
        "frozen_at": utcnow_iso(),
    }
    with open(dest, "w") as f:
        json.dump(avail, f, indent=1)
    append_log("diff_log", {"event": "friday_freeze", "season": season,
                            "week": week, "dest": dest})
    return dest
