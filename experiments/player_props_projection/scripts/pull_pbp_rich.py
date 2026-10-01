#!/usr/bin/env python3
"""Pull nflverse pbp 2018-2024 with RICH player/opportunity columns for
Player Projection Experiment 001 (modeling-table build).

Separate from scripts/pull_pbp_players.py (slim 13-col cache used by the
production prop projector). This cache lives under the experiment directory
and is NOT read by production code.

Columns add, vs the slim cache: air_yards, yards_after_catch, complete_pass,
yardline_100 (red-zone derivation), season_type (REG filter).

Run: ./venv/bin/python experiments/player_props_projection/scripts/pull_pbp_rich.py
"""
import os
import sys

import pandas as pd

EXP = os.path.expanduser("~/workspace/nfl-model/experiments/player_props_projection")
DATA = os.path.join(EXP, "data")
os.makedirs(DATA, exist_ok=True)

WANT = ["game_id", "season", "week", "season_type", "posteam", "defteam",
        "play_type", "passer_player_name", "rusher_player_name",
        "receiver_player_name", "passing_yards", "rushing_yards",
        "receiving_yards", "air_yards", "yards_after_catch", "complete_pass",
        "yardline_100"]
SEASONS = range(2018, 2025)  # 2018-2024: train/dev/test + trailing history


def main():
    import nfl_data_py as nfl
    for season in SEASONS:
        out = f"{DATA}/pbp_rich_{season}.parquet"
        if os.path.exists(out):
            print(f"{season}: cached, skipping", flush=True)
            continue
        print(f"{season}: downloading...", flush=True)
        df = nfl.import_pbp_data([season])
        cols = [c for c in WANT if c in df.columns]
        missing = set(WANT) - set(df.columns)
        if missing:
            print(f"  WARNING missing cols: {missing}", flush=True)
        df = df[df["season_type"] == "REG"][cols].copy()
        df.to_parquet(out, index=False)
        print(f"  saved {out} ({len(df)} REG rows)", flush=True)
        del df
    parts = [pd.read_parquet(f"{DATA}/pbp_rich_{s}.parquet") for s in SEASONS]
    allp = pd.concat(parts, ignore_index=True)
    allp.to_parquet(f"{DATA}/pbp_rich_2018_2024.parquet", index=False)
    print(f"combined: {len(allp)} rows -> pbp_rich_2018_2024.parquet")


if __name__ == "__main__":
    main()
