#!/usr/bin/env python3
"""Step 32: V2 PFR pressure features (walk-forward SAFE source table).

From nflverse pfr_advstats weekly files (player-grain), builds team x
played-week aggregates:
  OFFENSE (pass protection):
    - pressure_allowed_pct: primary passer's times_pressured_pct
      (primary = max times_pressured, proxy for most dropbacks; attempts not
      published in this file -- documented limitation)
    - sacks_allowed, hits_taken, hurries_taken, blitzed_taken (team sums)
    - drop_rate: team passing_drops / team dropbacks (dropbacks unavailable;
      uses max-QB proxy -- see leakage_audit.md)
    - bad_throw_pct: primary passer passing_bad_throw_pct
  DEFENSE (pass rush):
    - blitzes, hurries, qb_hits, sacks, pressures (team sums of
      def_times_blitzed / def_times_hurried / def_times_hitqb /
      def_sacks / def_pressures)
    - def_adot_allowed, def_yards_per_tgt_allowed, def_passer_rating_allowed
      (means across qualifying defenders, documented approximation)

Grain: team x season x played-week. Script 35 -> prediction-week grain.
NO model fitting. Feature architecture only.
"""
import glob
import os

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
RAW = f"{DATA}/v2/raw"
OUT = f"{DATA}/v2/team_week_pfr.parquet"


def main():
    os.makedirs(f"{DATA}/v2", exist_ok=True)

    # ---------- offense: pass protection (from advstats_week_pass) ----------
    frames = []
    for f in sorted(glob.glob(f"{RAW}/advstats_week_pass_*.parquet")):
        frames.append(pd.read_parquet(f))
    p = pd.concat(frames, ignore_index=True)
    p = p[p["week"] <= 22]
    p = p[(p["season"] >= 2018) & (p["season"] <= 2022)]  # vault/2026 excluded
    p["times_pressured"] = pd.to_numeric(p["times_pressured"], errors="coerce").fillna(0)

    def prot(g):
        g = g.sort_values("times_pressured", ascending=False)
        prim = g.iloc[0]
        return pd.Series({
            "pressure_allowed_pct": prim["times_pressured_pct"],
            "sacks_allowed": g["times_sacked"].sum(),
            "hits_taken": g["times_hit"].sum(),
            "hurries_taken": g["times_hurried"].sum(),
            "blitzed_taken": g["times_blitzed"].sum(),
            "pressures_taken": g["times_pressured"].sum(),
            "drops": g["passing_drops"].sum(),
            "bad_throw_pct": prim["passing_bad_throw_pct"],
            "primary_passer": prim["pfr_player_name"],
        })

    off = p.groupby(["team", "season", "week"], observed=True).apply(
        prot, include_groups=False).reset_index()

    # ---------- defense: pass rush + coverage (from advstats_week_def) ----------
    frames = []
    for f in sorted(glob.glob(f"{RAW}/advstats_week_def_*.parquet")):
        frames.append(pd.read_parquet(f))
    d = pd.concat(frames, ignore_index=True)
    d = d[d["week"] <= 22]
    d = d[(d["season"] >= 2018) & (d["season"] <= 2022)]  # vault/2026 excluded
    num = ["def_times_blitzed", "def_times_hurried", "def_times_hitqb",
           "def_sacks", "def_pressures", "def_tackles_combined",
           "def_missed_tackles"]
    for c in num:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)
    deff = d.groupby(["team", "season", "week"], observed=True).agg(
        def_blitzes=("def_times_blitzed", "sum"),
        def_hurries=("def_times_hurried", "sum"),
        def_qb_hits=("def_times_hitqb", "sum"),
        def_sacks=("def_sacks", "sum"),
        def_pressures=("def_pressures", "sum"),
        def_missed_tackles=("def_missed_tackles", "sum"),
        def_adot_allowed=("def_adot", "mean"),
        def_ypt_allowed=("def_yards_allowed_per_tgt", "mean"),
        def_prating_allowed=("def_passer_rating_allowed", "mean"),
    ).reset_index()

    out = off.merge(deff, on=["team", "season", "week"], how="outer")
    out = out.sort_values(["team", "season", "week"]).reset_index(drop=True)
    out.to_parquet(OUT, index=False)
    print(f"wrote {OUT}: {out.shape}")
    print("seasons:", sorted(out["season"].unique()))
    print("pressure_allowed_pct median:",
          out["pressure_allowed_pct"].median())


if __name__ == "__main__":
    main()
