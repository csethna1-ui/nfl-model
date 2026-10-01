#!/usr/bin/env python3
"""Aggregate player-level pbp into one row per player per game.

Input : data/pbp_players_2018_2026.parquet (or per-season pbp_players_{YYYY}.parquet)
Output: data/player_games.parquet with columns:
  player_name, team, opponent, season, week, game_id,
  pass_yards, rush_yards, receiving_yards,
  pass_att, rush_att, targets, touches
Only rows where the player touched the ball (attempt/rush/target) are kept.
A player with multiple roles in a game gets ONE row with all yardage columns.

Run: ./venv/bin/python scripts/aggregate_player_games.py
"""
import os

import numpy as np
import pandas as pd

DATA = os.path.expanduser("~/workspace/nfl-model/data")


def main():
    src = f"{DATA}/pbp_players_2018_2026.parquet"
    if os.path.exists(src):
        pbp = pd.read_parquet(src)
    else:
        parts = []
        for s in range(2018, 2027):
            p = f"{DATA}/pbp_players_{s}.parquet"
            if os.path.exists(p):
                parts.append(pd.read_parquet(p))
        pbp = pd.concat(parts, ignore_index=True)
    print(f"pbp rows: {len(pbp)}", flush=True)
    pbp = pbp[pbp["play_type"].isin(["pass", "run"])].copy()

    frames = []

    # passing
    pm = pbp["passer_player_name"].notna()
    g = pbp[pm].groupby(
        ["passer_player_name", "posteam", "defteam", "season", "week", "game_id"],
        dropna=False)
    d = g.agg(pass_yards=("passing_yards", "sum"),
              pass_att=("passing_yards", "size")).reset_index()
    d = d.rename(columns={"passer_player_name": "player_name",
                          "posteam": "team", "defteam": "opponent"})
    frames.append(d)

    # rushing
    rm = pbp["rusher_player_name"].notna()
    g = pbp[rm].groupby(
        ["rusher_player_name", "posteam", "defteam", "season", "week", "game_id"],
        dropna=False)
    d = g.agg(rush_yards=("rushing_yards", "sum"),
              rush_att=("rushing_yards", "size")).reset_index()
    d = d.rename(columns={"rusher_player_name": "player_name",
                          "posteam": "team", "defteam": "opponent"})
    frames.append(d)

    # receiving
    cm = pbp["receiver_player_name"].notna()
    g = pbp[cm].groupby(
        ["receiver_player_name", "posteam", "defteam", "season", "week", "game_id"],
        dropna=False)
    d = g.agg(receiving_yards=("receiving_yards", "sum"),
              targets=("receiving_yards", "size")).reset_index()
    d = d.rename(columns={"receiver_player_name": "player_name",
                          "posteam": "team", "defteam": "opponent"})
    frames.append(d)

    keys = ["player_name", "team", "opponent", "season", "week", "game_id"]
    pg = frames[0]
    for f in frames[1:]:
        pg = pg.merge(f, on=keys, how="outer")
    for c in ["pass_yards", "rush_yards", "receiving_yards",
              "pass_att", "rush_att", "targets"]:
        pg[c] = pg[c].fillna(0)
    pg["touches"] = pg["pass_att"] + pg["rush_att"] + pg["targets"]
    pg = pg[pg["touches"] > 0].copy()
    pg = pg.sort_values(["player_name", "season", "week"]).reset_index(drop=True)

    # primary position per player-season from touch mix
    mix = pg.groupby(["player_name", "season"]).agg(
        pa=("pass_att", "sum"), ra=("rush_att", "sum"), tg=("targets", "sum"))
    def pos(r):
        if r["pa"] >= 10 and r["pa"] >= r["ra"] and r["pa"] >= r["tg"]:
            return "QB"
        if r["ra"] >= r["tg"]:
            return "RB"
        return "WRTE"
    mix["position"] = mix.apply(pos, axis=1)
    pg = pg.merge(mix[["position"]], on=["player_name", "season"], how="left")

    pg.to_parquet(f"{DATA}/player_games.parquet", index=False)
    print(f"player_games: {len(pg)} rows, "
          f"{pg['player_name'].nunique()} players", flush=True)
    print(pg["position"].value_counts().to_string())


if __name__ == "__main__":
    main()
