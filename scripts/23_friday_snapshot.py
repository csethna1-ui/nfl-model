#!/usr/bin/env python3
"""Step 23: Friday snapshot for Experiment 006 (information-timing study).

OBSERVATIONAL ONLY. Consolidates the Friday information state AFTER the
regular Friday pipeline (07_update_weekly + 11_injury_adjust) has run.
Reads pipeline outputs; never modifies them.

Usage:
    ./venv/bin/python scripts/23_friday_snapshot.py --season 2026 --week 5

Reads:
    data/predictions_2026_w{N}.csv   (Friday 07 output, post-11 voids)
    data/market_2026_w{N}.json       (Friday researched lines + qb_news + wind)
Ratings state (ELO/EPA) is recomputed with the same code path as the Tuesday
snapshot for comparability. Thursday-night games (already played at Friday
capture) are flagged already_played=1 and excluded from movement analysis.

Writes: data/timing_study/friday_2026_w{N}.csv
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

DATA = os.path.join(REPO_ROOT, "data")
TS = f"{DATA}/timing_study"
ET = ZoneInfo("America/New_York")


def compact_qb_news(qb_news, key):
    """'OUT: Jaxson Dart -> Jameis Winston; ...' or ''."""
    d = (qb_news or {}).get(key, {})
    parts = []
    for side in ("away", "home"):
        s = d.get(side)
        if s:
            parts.append(f"{s.get('status', '?').upper()}: "
                         f"{s.get('starter', '?')} -> {s.get('backup', '?')}")
    return "; ".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    args = ap.parse_args()
    S, W = args.season, args.week

    pred_csv = f"{DATA}/predictions_{S}_w{W}.csv"
    mkt_json = f"{DATA}/market_{S}_w{W}.json"
    if not os.path.exists(pred_csv):
        raise SystemExit(f"missing {pred_csv}: run the Friday pipeline first")
    if not os.path.exists(mkt_json):
        raise SystemExit(f"missing {mkt_json}: research Friday lines first")

    os.makedirs(TS, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(ET)

    pred = pd.read_csv(pred_csv)
    with open(mkt_json) as f:
        market = json.load(f)
    qb_news = market.get("qb_news", {})
    wind = market.get("wind", {})

    # ---- ratings state as of Friday (same code path as Tuesday snapshot) ----
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
    print(f"Friday ratings state: through {S} w{W-1} ({len(played)} played games)")

    up = sched[(sched["season"] == S) & (sched["week"] == W)].copy()
    rows = []
    for _, g in up.iterrows():
        h, a = g["home_team"], g["away_team"]
        key = f"{a}_{h}"
        ko = pd.Timestamp(f"{g['gameday']} {g['gametime']}").tz_localize(ET)
        already = int(ko <= now_et)
        pr = pred[pred["game"] == f"{a} @ {h}"]
        r = pr.iloc[0] if len(pr) else {}
        mk = market.get(key, [None, None])
        rows.append({
            "game_id": g["game_id"], "game": f"{a} @ {h}",
            "season": S, "week": W,
            "kickoff_et": ko.isoformat(),
            "already_played": already,
            "model_spread_fri": r.get("model_spread"),
            "model_total_fri": r.get("model_total"),
            "market_spread_fri": mk[0], "market_total_fri": mk[1],
            "edge_fri": r.get("edge"),
            "spread_pick_fri": r.get("spread_pick"),
            "model_spread_adj": r.get("model_spread_adj"),
            "edge_adj": r.get("edge_adj"),
            "spread_pick_final": r.get("spread_pick_final"),
            "void_reason": r.get("void_reason", ""),
            "qb_news_fri": compact_qb_news(qb_news, key),
            "wind_fri": wind.get(key),
            "elo_diff_fri": round(elos.get(h, 1500.0) - elos.get(a, 1500.0), 1),
            "off_epa_diff_fri": round(epa_state["off_epa"].get(h, 0.0)
                                      - epa_state["off_epa"].get(a, 0.0), 4),
            "def_epa_diff_fri": round(epa_state["def_epa"].get(h, 0.0)
                                      - epa_state["def_epa"].get(a, 0.0), 4),
            "captured_at_utc": now_utc.strftime("%Y-%m-%d %H:%M UTC"),
            "captured_at_et": now_et.strftime("%Y-%m-%d %H:%M %Z"),
            "notes": "",
        })
    out = pd.DataFrame(rows).sort_values("kickoff_et")
    path = f"{TS}/friday_{S}_w{W}.csv"
    out.to_csv(path, index=False)
    n_played = int(out["already_played"].sum())
    print(f"wrote {path} ({len(out)} games, {n_played} already played "
          f"(excluded from movement analysis))")


if __name__ == "__main__":
    main()
