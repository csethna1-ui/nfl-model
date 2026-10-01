#!/usr/bin/env python3
"""Step 1: Load schedules from local games.csv, check spread/total coverage 2018-2025."""
import pandas as pd

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sched = pd.read_csv(os.path.join(REPO_ROOT, "data", "games.csv"), low_memory=False)
print("all rows:", len(sched), "| seasons:", sched["season"].min(), "-", sched["season"].max())

reg = sched[(sched["season"] >= 2018) & (sched["game_type"].isin(["REG", "WC", "DIV", "CON", "SB"]))].copy()
print("2018+ REG+playoffs rows:", len(reg))

# spread_line sign convention: check a known game
print("\nSample rows w/ lines:")
print(reg[["season","week","away_team","home_team","away_score","home_score","spread_line","total_line"]].head(4).to_string())

for col in ["spread_line", "total_line"]:
    cov = reg[col].notna().groupby(reg["season"]).agg(["mean", "sum"])
    print(f"\n{col} coverage by season:")
    print(cov.round(3).to_string())
    print("overall fraction:", round(reg[col].notna().mean(), 3))

# Check spread sign convention: spread_line negative means home favored?
# Verify: pick games where home won big vs spread
chk = reg.dropna(subset=["spread_line"]).copy()
chk["home_margin"] = chk["home_score"] - chk["away_score"]
# If spread_line = -3 typical for home favorite: home covers if home_margin + spread_line > 0? Let's test correlation
print("\nSpread sign check (home_margin vs spread_line), sample:")
print(chk[["away_team","home_team","home_margin","spread_line"]].head(8).to_string())
print("\nmean home_margin when spread_line<0 (home favored):",
      round(chk[chk["spread_line"]<0]["home_margin"].mean(),2))
print("mean home_margin when spread_line>0 (away favored):",
      round(chk[chk["spread_line"]>0]["home_margin"].mean(),2))

reg.to_parquet(os.path.join(REPO_ROOT, "data", "schedules_2018_2025.parquet"), index=False)
print("\nsaved schedules parquet")
