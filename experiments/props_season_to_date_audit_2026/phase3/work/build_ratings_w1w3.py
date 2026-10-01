#!/usr/bin/env python3
"""Phase 3 as-of helper: reconstruct pre-week ratings snapshots for 2026
W1/W2/W3 using the EXACT code path that produced
data/ratings_current_2026_w4.parquet.

Verified: running this procedure for W4 reproduces the w4 file byte-exact
(ELO max diff 0.0 via 03_ratings.run_elo; EPA max diff 0.0 via
07_update_weekly.run_epa_current on the same inputs).

Per-week recipe (mirrors 07_update_weekly.main):
  played = scored REG games with (season < 2026) | (season == 2026 & week < W)
  elos   = run_elo(played);            W1 only: 1500 + (e-1500)*(2/3)
  epa    = run_epa_current(pbp, played); W1 only: v * 0.65
Output: phase3/work/datamirror/ratings_current_2026_w{W}.parquet
(columns: team, elo, off_epa, off_pass_epa, off_rush_epa, off_sr,
          def_epa, def_pass_epa, def_rush_epa, def_sr)
plus a provenance JSON per week. No lookahead: pbp filtered to weeks < W
(identical result to unfiltered since the walk is driven by `played`).
"""
import importlib.util
import json
import os

import numpy as np
import pandas as pd

REPO = os.path.expanduser("~/workspace/nfl-model")
PH3 = os.path.join(REPO, "experiments/props_season_to_date_audit_2026/phase3")
WORK = os.path.join(PH3, "work")
MIRROR = os.path.join(WORK, "datamirror")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


print("loading rating modules...", flush=True)
r03 = _load("r03", os.path.join(REPO, "scripts/03_ratings.py"))
u07 = _load("u07", os.path.join(REPO, "scripts/07_update_weekly.py"))

METRICS = ["off_epa", "off_pass_epa", "off_rush_epa", "off_sr",
           "def_epa", "def_pass_epa", "def_rush_epa", "def_sr"]

sched = pd.read_parquet(os.path.join(REPO, "data/schedules_2018_2025.parquet"))
pbp_all = pd.read_parquet(os.path.join(REPO, "data/pbp_2018_2025.parquet"))
print(f"sched games: {len(sched)}, pbp rows: {len(pbp_all)}", flush=True)

for W in (1, 2, 3):
    played = sched[sched["home_score"].notna()].copy()
    played = played[(played["season"] < 2026) |
                    ((played["season"] == 2026) & (played["week"] < W))].copy()
    played = played.sort_values(["season", "week"]).reset_index(drop=True)
    played["home_margin"] = played["home_score"] - played["away_score"]
    pbp = pbp_all[(pbp_all["season"] < 2026) |
                  ((pbp_all["season"] == 2026) & (pbp_all["week"] < W))].copy()

    _, elos = r03.run_elo(played)
    _, epa_state = u07.run_epa_current(pbp, played)
    regressed = False
    if W == 1 and not (played["season"] == 2026).any():
        elos = {t: 1500.0 + (e - 1500.0) * (2.0 / 3.0) for t, e in elos.items()}
        epa_state = {m: {t: v * 0.65 for t, v in d.items()}
                     for m, d in epa_state.items()}
        regressed = True
        print("  W1: applied regressed-prior rule (07 lines 240-245)", flush=True)

    teams = sorted(set(elos) | {t for d in epa_state.values() for t in d})
    rows = [{"team": t, "elo": float(elos.get(t, 1500.0)),
             **{m: float(epa_state[m].get(t, 0.0)) for m in METRICS}}
            for t in teams]
    out = pd.DataFrame(rows, columns=["team", "elo"] + METRICS)
    opath = os.path.join(MIRROR, f"ratings_current_2026_w{W}.parquet")
    out.to_parquet(opath, index=False)
    prov = {
        "label": f"Current Ratings - Pre-Game Week {W} (phase3 as-of reconstruction)",
        "season": 2026, "week": W,
        "method": ("byte-verified reproduction of the ratings_current_2026_w4 "
                   "code path: 03_ratings.run_elo + 07_update_weekly.run_epa_current; "
                   "W4 reconstruction matches the shipped w4 file exactly"),
        "played_games": int(len(played)),
        "latest_game_included": str(played.iloc[-1]["game_id"]),
        "regressed_priors_applied": regressed,
        "n_teams": len(out),
    }
    with open(os.path.join(WORK, f"ratings_2026_w{W}.provenance.json"), "w") as f:
        json.dump(prov, f, indent=1)
    print(f"W{W}: {len(out)} teams, {len(played)} played games -> {opath}",
          flush=True)
print("done.", flush=True)
