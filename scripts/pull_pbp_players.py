#!/usr/bin/env python3
"""Pull nflverse pbp 2018-2026 keeping player-level columns for the prop projector.
Caches per-season then combined as data/pbp_players_2018_2026.parquet.
Resumable: skips seasons whose per-season parquet already exists.
Run: ./venv/bin/python scripts/pull_pbp_players.py
"""
import os
import sys

import pandas as pd

DATA = os.path.expanduser("~/workspace/nfl-model/data")
WANT = ["game_id", "season", "week", "posteam", "defteam", "play_type",
        "passer_player_name", "rusher_player_name", "receiver_player_name",
        "passing_yards", "rushing_yards", "receiving_yards", "epa"]


def main():
    import argparse
    import nfl_data_py as nfl
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-season", type=int, default=None,
                    help="re-pull this season even if cached (e.g. current season in progress)")
    args = ap.parse_args()
    for season in range(2018, 2027):
        out = f"{DATA}/pbp_players_{season}.parquet"
        if os.path.exists(out) and season != args.refresh_season:
            print(f"{season}: cached, skipping", flush=True)
            continue
        print(f"{season}: downloading...", flush=True)
        df = nfl.import_pbp_data([season])
        cols = [c for c in WANT if c in df.columns]
        missing = set(WANT) - set(df.columns)
        if missing:
            print(f"  WARNING missing cols: {missing}", flush=True)
        df[cols].to_parquet(out, index=False)
        print(f"  saved {out} ({len(df)} rows)", flush=True)
        del df
    parts = [pd.read_parquet(f"{DATA}/pbp_players_{s}.parquet") for s in range(2018, 2027)]
    allp = pd.concat(parts, ignore_index=True)
    allp.to_parquet(f"{DATA}/pbp_players_2018_2026.parquet", index=False)
    print(f"combined: {len(allp)} rows -> pbp_players_2018_2026.parquet")


if __name__ == "__main__":
    main()
