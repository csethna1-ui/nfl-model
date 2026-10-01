#!/usr/bin/env python3
"""Step 29: QB-expectation recording (data collection ONLY — not modeling).

Records, per team per week, the QB the system expects to start, using a
deterministic rule over free/keyless nflverse sources. This builds the
historical dataset a future preregistered experiment (e.g. "does knowing the
expected QB improve frozen-V1 margin prediction?") needs. It must NEVER be
backfilled: reconstructing past expectations after the fact would violate
timestamp validity and poison that future experiment's dataset.

Deterministic v2 rule (documented, no predictive modeling of who starts):
    expected QB = QB1 from the latest nflverse depth chart,
    UNLESS QB1's injury report_status is Out/Doubtful, then QB2.

    Status lookup (v2 — staleness fix 2026-10-01): prefer a row for the target
    week when the team's report is already out (e.g. Thursday-game teams).
    Otherwise use the latest PLAYED week with report coverage for that team;
    a QB1 with no row in that week is not on the injury report and is
    therefore available. The lookup NEVER falls back to an older week's
    Out/Doubtful tag: a stale tag (e.g. Kyler Murray's cleared week-2
    concussion, which v1 carried into week 4) must not contaminate the
    upcoming week's expectation. v1's fallback caused exactly that.

The void layer (11_injury_adjust.py) reads this record as its primary automated
QB-state source (manual qb_news still overrides per team/side). This table is
the "Expected QB" stage of the pipeline: V1 raw -> expected QB -> QB-adjusted
overlay -> market -> edges -> final status.

Sources (free/keyless):
    - nflverse depth charts via nfl_data_py.import_depth_charts
      (pos_rank 1 = QB1, 2 = QB2; gsis_id joins to the injury feed)
    - nflverse injury report via the versioned daily snapshot from
      scripts/26_pull_injuries.py (data/injuries/snapshots/injuries_YYYY-MM-DD.parquet)

Storage: data/qb_expectations/qb_expected_<season>_w<week>.parquet
    Append-only, NEVER overwritten (refuses if the file exists).
    Logs to data/qb_expectations/logs/capture_log.jsonl.

Usage:
    ./venv/bin/python scripts/29_qb_expectation.py --season 2026 --week 4
    # Friday flow runs this BEFORE the 18:00 CT injury freeze (step 2b),
    # so the capture sits inside the same information-set boundary.
"""
import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
from injury_lib import (ensure_dirs, utcnow_iso, latest_snapshot_day,
                        load_snapshot, norm_status)

DATA = os.path.join(REPO_ROOT, "data")
QB_DIR = f"{DATA}/qb_expectations"
LOG_DIR = f"{QB_DIR}/logs"

RULE_VERSION = "v2"
RULE_DESC = ("expected QB = depth-chart QB1 unless QB1 report_status is "
             "out/doubtful, then depth-chart QB2; status from target week if "
             "reported else latest played week with team coverage, no-row = "
             "available (never carry an older week's tag forward)")
TRIGGER = {"out", "doubtful"}          # same trigger set as the void layer
NOTABLE = {"out", "doubtful", "questionable", "limited", "dnp"}


def qb_path(season, week):
    return f"{QB_DIR}/qb_expected_{season}_w{week}.parquet"


def ensure_qb_dirs():
    for d in (QB_DIR, LOG_DIR):
        os.makedirs(d, exist_ok=True)


def append_capture_log(record):
    ensure_qb_dirs()
    record = dict(record)
    record.setdefault("ts", utcnow_iso())
    with open(f"{LOG_DIR}/capture_log.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")


def confidence_for(qb1_status, starter_or_backup, resolved):
    if not resolved:
        return "low"
    if starter_or_backup == "backup":
        return "low"          # QB1 out/doubtful: emergency QB2, genuinely uncertain
    if qb1_status in ("questionable", "limited", "dnp"):
        return "medium"       # QB1 expected per rule, but designation adds doubt
    return "high"             # healthy QB1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", type=int, required=True,
                    help="upcoming week being predicted (e.g. 4)")
    ap.add_argument("--snapshot-day", default=None,
                    help="injury snapshot day YYYY-MM-DD (default: latest)")
    args = ap.parse_args()
    ensure_qb_dirs()

    dest = qb_path(args.season, args.week)
    if os.path.exists(dest):
        print(f"REFUSING to overwrite existing record {dest} "
              f"(append-only; delete explicitly if a re-capture is intended)")
        append_capture_log({"event": "refused_overwrite", "season": args.season,
                            "week": args.week, "dest": dest})
        return

    captured_at = utcnow_iso()

    # --- inputs ---
    import pandas as pd
    import nfl_data_py as nfl

    day = args.snapshot_day or latest_snapshot_day()
    snap = load_snapshot(day)
    if snap is None:
        raise SystemExit(f"no injury snapshot for day={day} — run 26_pull_injuries.py first")
    snap = snap.copy()
    snap["status_norm"] = snap["report_status"].map(norm_status)

    dc = nfl.import_depth_charts([args.season])
    dc = dc[dc["pos_abb"] == "QB"].copy()
    dc["dt"] = pd.to_datetime(dc["dt"], utc=True)
    depth_chart_dt_max = dc["dt"].max()
    # latest depth-chart view per team / rank
    dc = dc.sort_values("dt").drop_duplicates(["team", "pos_rank"], keep="last")

    # cross-check: maintained qb1 list vs depth-chart QB1 (informational only)
    try:
        with open(f"{DATA}/qb_point_values.json") as f:
            maintained_qb1 = {t: d["qb1"] for t, d in json.load(f)["teams"].items()}
    except Exception:
        maintained_qb1 = {}

    teams = sorted(dc["team"].unique())
    rows = []
    warnings = []
    for team in teams:
        tdc = dc[dc["team"] == team]
        qb1 = tdc[tdc["pos_rank"] == 1]
        qb2 = tdc[tdc["pos_rank"] == 2]
        qb1_name = str(qb1.iloc[0]["player_name"]) if len(qb1) else None
        qb1_gsis = str(qb1.iloc[0]["gsis_id"]) if len(qb1) else None
        qb2_name = str(qb2.iloc[0]["player_name"]) if len(qb2) else None
        qb2_gsis = str(qb2.iloc[0]["gsis_id"]) if len(qb2) else None

        # QB1 injury status (v2 rule): prefer a row for the target week, else
        # the latest PLAYED week with report coverage for this team. No QB1
        # row in that week => not on the injury report => available. Never
        # fall back to an older week's tag (v1 staleness bug).
        # status_week records which report week the status came from;
        # status_inferred is True when availability was inferred from absence.
        status, status_week, status_inferred = "", None, False
        if qb1_gsis:
            prow = snap[snap["gsis_id"] == qb1_gsis]
            exact = prow[prow["week"] == args.week]
            if len(exact):
                use = exact.tail(1)
                status = str(use.iloc[0]["status_norm"])
                status_week = int(use.iloc[0]["week"])
            else:
                played = sorted(w for w in snap["week"].dropna().unique()
                                if int(w) < args.week)
                team_weeks = [w for w in played
                              if ((snap["team"] == team)
                                  & (snap["week"] == w)).any()]
                if team_weeks:
                    lw = int(max(team_weeks))
                    lwrow = prow[prow["week"] == lw]
                    if len(lwrow):
                        status = str(lwrow.iloc[0]["status_norm"])
                        status_week = lw
                    else:
                        status_week = lw
                        status_inferred = True

        # --- deterministic v1 rule ---
        if qb1_name and status in TRIGGER and qb2_name:
            expected_name, expected_gsis = qb2_name, qb2_gsis
            starter_or_backup = "backup"
        elif qb1_name:
            expected_name, expected_gsis = qb1_name, qb1_gsis
            starter_or_backup = "starter"
        else:
            expected_name, expected_gsis = None, None
            starter_or_backup = "unknown"
            warnings.append(f"{team}: QB1 unresolvable from depth chart")

        resolved = expected_name is not None
        conf = confidence_for(status, starter_or_backup, resolved)

        maint = maintained_qb1.get(team)
        if maint and qb1_name and maint.split()[-1].lower() != qb1_name.split()[-1].lower():
            warnings.append(f"{team}: depth-chart QB1 '{qb1_name}' != "
                            f"maintained qb1 '{maint}' (depth chart is source of truth)")

        rows.append({
            "season": args.season,
            "week": args.week,
            "team": team,
            "expected_qb_name": expected_name,
            "expected_qb_gsis_id": expected_gsis,
            "qb1_name": qb1_name,
            "qb1_gsis_id": qb1_gsis,
            "qb1_report_status": status,
            "qb_status": status,                 # driver of the v1 decision
            "qb_status_week": status_week,       # which report week the status came from
            "qb_status_inferred": status_inferred,  # True: no row in latest
                                                   # played week => available
            "qb_status_as_of": captured_at,
            "starter_or_backup": starter_or_backup,
            "confidence": conf,
            "rule_version": RULE_VERSION,
            "rule": RULE_DESC,
            "source": "nflverse depth_charts + nflverse injuries (deterministic v1 rule)",
            "depth_chart_dt_max": depth_chart_dt_max.isoformat(),
            "injury_snapshot_day": day,
            "captured_at": captured_at,
        })

    out = pd.DataFrame(rows)
    out.to_parquet(dest, index=False)
    n_backup = int((out["starter_or_backup"] == "backup").sum())
    n_unknown = int((out["starter_or_backup"] == "unknown").sum())
    print(f"wrote {len(out)} team rows -> {dest}")
    print(f"expected backups: {n_backup}, unknown: {n_unknown}, "
          f"depth_chart_dt_max: {depth_chart_dt_max.isoformat()}, snapshot_day: {day}")
    for w in warnings:
        print("WARNING:", w)
    append_capture_log({"event": "capture", "season": args.season, "week": args.week,
                        "dest": dest, "captured_at": captured_at,
                        "snapshot_day": day,
                        "depth_chart_dt_max": depth_chart_dt_max.isoformat(),
                        "n_teams": len(out), "n_backup": n_backup,
                        "n_unknown": n_unknown, "warnings": warnings})


if __name__ == "__main__":
    main()
