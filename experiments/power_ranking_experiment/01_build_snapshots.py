#!/usr/bin/env python3
"""Power-ranking experiment — 01: build weekly pre-week team snapshots, 2018-2022.

For each season/week, each team's pre-week state:
  ELO, off_epa, def_epa, off_sr, def_sr (production pre-game ratings),
  W-L-T and point-differential/game from REG games through the prior week.
Bye-week teams carry forward prior-week values. No lookahead anywhere.

READ-ONLY: reads data/games_with_ratings.parquet, writes only into
experiments/power_ranking_experiment/.
"""
import numpy as np
import pandas as pd

DATA = "/home/hatch/workspace/nfl-model/data"
OUT = "/home/hatch/workspace/nfl-model/experiments/power_ranking_experiment"
SEASONS = [2018, 2019, 2020, 2021, 2022]

g = pd.read_parquet(f"{DATA}/games_with_ratings.parquet")
reg = g[(g["game_type"] == "REG") & (g["season"].isin(SEASONS))].copy()
reg = reg.sort_values(["season", "week"]).reset_index(drop=True)

# results ledger for W-L / point differential (team perspective)
res = []
for _, r in reg.iterrows():
    hm = r["home_margin"]
    res.append({"season": r["season"], "week": r["week"], "team": r["home_team"],
                "pf": r["home_score"], "pa": r["away_score"],
                "w": 1 if hm > 0 else 0, "l": 1 if hm < 0 else 0, "t": 1 if hm == 0 else 0})
    res.append({"season": r["season"], "week": r["week"], "team": r["away_team"],
                "pf": r["away_score"], "pa": r["home_score"],
                "w": 1 if hm < 0 else 0, "l": 1 if hm > 0 else 0, "t": 1 if hm == 0 else 0})
res = pd.DataFrame(res)

snaps = []
for season in SEASONS:
    gs = reg[reg["season"] == season]
    rs = res[res["season"] == season]
    max_week = gs["week"].max()
    carry = {}  # team -> last ratings dict (for bye weeks)
    for week in range(1, max_week + 1):
        gw = gs[gs["week"] == week]
        # pre-week ratings from this week's games (weekly batching: all use pre-week values)
        wk_ratings = {}
        for _, r in gw.iterrows():
            wk_ratings[r["home_team"]] = {
                "elo": r["elo_home"], "off_epa": r["home_off_epa"],
                "def_epa": r["home_def_epa"], "off_sr": r["home_off_sr"],
                "def_sr": r["home_def_sr"]}
            wk_ratings[r["away_team"]] = {
                "elo": r["elo_away"], "off_epa": r["away_off_epa"],
                "def_epa": r["away_def_epa"], "off_sr": r["away_off_sr"],
                "def_sr": r["away_def_sr"]}
        carry.update(wk_ratings)
        # W-L / PD through prior week
        past = rs[rs["week"] < week]
        agg = past.groupby("team").agg(w=("w", "sum"), l=("l", "sum"), t=("t", "sum"),
                                       pf=("pf", "sum"), pa=("pa", "sum"),
                                       gp=("w", "size")).reset_index()
        agg["win_pct"] = (agg["w"] + 0.5 * agg["t"]) / agg["gp"].replace(0, np.nan)
        agg["pd_pg"] = (agg["pf"] - agg["pa"]) / agg["gp"].replace(0, np.nan)
        agg = agg.fillna({"win_pct": 0.0, "pd_pg": 0.0, "gp": 0})
        ad = agg.set_index("team").to_dict("index")
        for team, rt in carry.items():
            a = ad.get(team, {"w": 0, "l": 0, "t": 0, "gp": 0, "win_pct": 0.0, "pd_pg": 0.0})
            snaps.append({"season": season, "week": week, "team": team,
                          "elo": rt["elo"], "off_epa": rt["off_epa"],
                          "def_epa": rt["def_epa"], "off_sr": rt["off_sr"],
                          "def_sr": rt["def_sr"], "w": a["w"], "l": a["l"],
                          "t": a["t"], "gp": a["gp"], "win_pct": a["win_pct"],
                          "pd_pg": a["pd_pg"]})

snaps = pd.DataFrame(snaps)
snaps.to_parquet(f"{OUT}/snapshots_2018_2022.parquet", index=False)
print("snapshots:", snaps.shape)
print(snaps.groupby("season")["week"].max())
print(snaps.head(3).to_string())
# sanity: 32 teams every week
chk = snaps.groupby(["season", "week"]).size()
assert (chk == 32).all(), chk[chk != 32]
print("32 teams x every week: OK")
