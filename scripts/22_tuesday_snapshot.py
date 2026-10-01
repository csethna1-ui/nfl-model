#!/usr/bin/env python3
"""Step 22: Tuesday-AM snapshot for Experiment 006 (information-timing study).

OBSERVATIONAL ONLY. Runs the frozen V1 prediction path (scripts/07) WITHOUT
market lines, captures the Tuesday information state, and records Tuesday
market lines if the operator researched them.

Usage:
    ./venv/bin/python scripts/22_tuesday_snapshot.py --season 2026 --week 5 \
        [--market-json data/market_tue_2026_w5.json]

Tuesday market JSON format: same as the Friday market JSON --
{"AWAY_HOME": [spread, total], ...}, home-spread convention. Optional
"captured_at" field records when the lines were researched.

SAFETY:
- Refuses to run if data/predictions_{S}_w{W}.csv already exists (protects the
  Friday file from being clobbered); pass --force to override (backs up first).
- The Tuesday 07 run writes a market-less predictions CSV; this script copies
  what it needs to data/timing_study/raw/ and then RESTORES/REMOVES the
  canonical file so no market-less predictions file lingers.
- Never backfills: if the Tuesday market JSON is absent, market_tue is
  recorded as missing. A missed Tuesday cannot be reconstructed later.

Writes: data/timing_study/tuesday_2026_w{N}.csv
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

DATA = os.path.join(REPO_ROOT, "data")
TS = f"{DATA}/timing_study"
ET = ZoneInfo("America/New_York")

EARLIEST_WEEK = 5  # Weeks 1-4 cannot be reliably reconstructed (cold start).


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True, help="upcoming week to snapshot")
    ap.add_argument("--market-json", default=None,
                    help="Tuesday market lines JSON (optional)")
    ap.add_argument("--force", action="store_true",
                    help="allow overwrite of an existing predictions CSV (backs up first)")
    args = ap.parse_args()
    S, W = args.season, args.week

    if W < EARLIEST_WEEK:
        print(f"WARNING: week {W} < {EARLIEST_WEEK}; pre-Week-5 snapshots are not "
              f"reliable (cold start). Recording anyway, flagged.")
    cold_start = W < EARLIEST_WEEK

    os.makedirs(TS, exist_ok=True)
    os.makedirs(f"{TS}/raw", exist_ok=True)

    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(ET)
    timing_flag = "OK" if now_et.weekday() == 1 else "LATE"  # Monday=0
    if timing_flag == "LATE":
        print(f"WARNING: not Tuesday ET ({now_et:%A %Y-%m-%d %H:%M %Z}). "
              f"Snapshot recorded with timing_flag=LATE.")

    pred_csv = f"{DATA}/predictions_{S}_w{W}.csv"
    preexisted = os.path.exists(pred_csv)
    if preexisted and not args.force:
        print(f"REFUSING: {pred_csv} already exists (Friday file?). "
              f"Pass --force to override (backs up first).")
        sys.exit(2)
    backup = None
    if preexisted:
        backup = pred_csv + ".tuebak"
        shutil.copy2(pred_csv, backup)
        print(f"backed up existing file -> {backup}")

    # ---- 1. Run the frozen V1 prediction path (no market lines) ----
    # Use the same Python interpreter running this script (sys.executable)
    # rather than a hardcoded venv path, so the snapshot works in any
    # checkout (GitHub repo, local clone, CI).
    print("running 07_update_weekly (model-only, no market)...", flush=True)
    try:
        r = subprocess.run(
            [sys.executable,
             os.path.join(REPO_ROOT, "scripts", "07_update_weekly.py"),
             "--season", str(S), "--week", str(W), "--model", "v1"],
            capture_output=True, text=True)
        print(r.stdout[-2000:])
        if r.returncode != 0:
            print(r.stderr[-2000:])
            raise SystemExit("07_update_weekly failed; aborting Tuesday snapshot")

        tue_pred = pd.read_csv(pred_csv)
        shutil.copy2(pred_csv, f"{TS}/raw/tue_pred_{S}_w{W}.csv")
    finally:
        if backup and os.path.exists(backup):
            shutil.move(backup, pred_csv)
            print("restored pre-existing predictions CSV")
        elif os.path.exists(pred_csv) and not preexisted:
            os.remove(pred_csv)
            print("removed Tuesday-written predictions CSV (Friday run recreates it)")

    # ---- 2. Ratings state as of Tuesday (ELO/EPA only; GBM refit skipped) ----
    from importlib import import_module
    m07 = import_module("07_update_weekly")
    ratings_mod = import_module("03_ratings")
    sched = m07.refresh_schedules(S)
    pbp = m07.refresh_pbp(S)
    played = sched[sched["home_score"].notna()].copy()
    played = played[(played["season"] < S) |
                    ((played["season"] == S) & (played["week"] < W))]
    played = played.sort_values(["season", "week"]).reset_index(drop=True)
    played["home_margin"] = played["home_score"] - played["away_score"]
    played["total_pts"] = played["home_score"] + played["away_score"]
    _, elos = ratings_mod.run_elo(played)
    _, epa_state = m07.run_epa_current(pbp, played)
    print(f"ratings state: {len(elos)} teams, through {S} w{W-1} "
          f"({len(played)} played games)")

    # ---- 3. Tuesday market lines (optional; never backfilled) ----
    tue_market, tue_captured = {}, None
    market_missing = 1
    if args.market_json and os.path.exists(args.market_json):
        with open(args.market_json) as f:
            tue_market = json.load(f)
        tue_captured = tue_market.get("captured_at")
        market_missing = 0
        print(f"Tuesday market lines loaded from {args.market_json}")
    else:
        print("no Tuesday market JSON; market_tue recorded as missing")

    # ---- 4. Assemble snapshot ----
    up = sched[(sched["season"] == S) & (sched["week"] == W)].copy()
    rows = []
    for _, g in up.iterrows():
        h, a = g["home_team"], g["away_team"]
        key = f"{a}_{h}"
        m = tue_market.get(key)
        pm = tue_pred[tue_pred["game"] == f"{a} @ {h}"]
        model_spread = float(pm["model_spread"].iloc[0]) if len(pm) else None
        model_total = float(pm["model_total"].iloc[0]) if len(pm) else None
        ko = pd.Timestamp(f"{g['gameday']} {g['gametime']}").tz_localize(ET)
        rows.append({
            "game_id": g["game_id"], "game": f"{a} @ {h}",
            "season": S, "week": W,
            "kickoff_et": ko.isoformat(),
            "model_spread_tue": round(model_spread, 1) if model_spread is not None else None,
            "model_total_tue": round(model_total, 1) if model_total is not None else None,
            "market_spread_tue": m[0] if m else None,
            "market_total_tue": m[1] if m else None,
            "market_tue_missing": market_missing,
            "market_tue_captured_at": tue_captured,
            "elo_diff_tue": round(elos.get(h, 1500.0) - elos.get(a, 1500.0), 1),
            "off_epa_diff_tue": round(epa_state["off_epa"].get(h, 0.0)
                                      - epa_state["off_epa"].get(a, 0.0), 4),
            "def_epa_diff_tue": round(epa_state["def_epa"].get(h, 0.0)
                                      - epa_state["def_epa"].get(a, 0.0), 4),
            "captured_at_utc": now_utc.strftime("%Y-%m-%d %H:%M UTC"),
            "captured_at_et": now_et.strftime("%Y-%m-%d %H:%M %Z"),
            "timing_flag": timing_flag,
            "cold_start_week": int(cold_start),
            "notes": "",
        })
    out = pd.DataFrame(rows).sort_values("kickoff_et")
    path = f"{TS}/tuesday_{S}_w{W}.csv"
    out.to_csv(path, index=False)
    print(f"\nwrote {path} ({len(out)} games, market_missing={market_missing}, "
          f"timing_flag={timing_flag})")


if __name__ == "__main__":
    main()
