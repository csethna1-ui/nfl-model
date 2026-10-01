#!/usr/bin/env python3
"""Step 2: Combine local PBP parquets 2018-2025, keep needed columns, cache."""
import pandas as pd
import glob

KEEP = ["game_id", "season", "week", "posteam", "defteam", "play_type",
        "epa", "success", "pass", "rush", "qb_dropback",
        "home_team", "away_team"]

frames = []
import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for f in sorted(glob.glob(os.path.join(REPO_ROOT, "data", "pbp_2*.parquet"))):
    if "pbp_2018_2025" in f:
        continue
    d = pd.read_parquet(f, columns=[c for c in KEEP if c != "x"])
    cols = [c for c in KEEP if c in d.columns]
    d = d[cols]
    frames.append(d)
    print(f, len(d))
pbp = pd.concat(frames, ignore_index=True)
pbp = pbp[pbp["week"] <= 22]
out = os.path.join(REPO_ROOT, "data", "pbp_2018_2025.parquet")
pbp.to_parquet(out, index=False)
print("saved", out, "rows:", len(pbp))
print("seasons:", sorted(pbp["season"].unique()))
