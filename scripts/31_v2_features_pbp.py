#!/usr/bin/env python3
"""Step 31: V2 PBP-derived team-week features (walk-forward SAFE source table).

Computes, from local nflverse PBP parquets, team x played-week aggregates for:
  - POSSESSION (drive structure): drives, points/drive, EPA/drive, start field
    position, three-and-out rate, scoring-drive rate, red-zone trip rate,
    goal-to-go TD rate, plays/drive, drive-ending turnover rate
  - EXPLOSIVENESS: explosive pass/rush rates (>=16 / >=10 yds), 20+/40+ play
    rates, EPA/play std/median/p10/p90, air yards/attempt, aDOT
  - PRESSURE (PBP proxies): sack rate, QB-hit rate per dropback
  - SPECIAL TEAMS: ST EPA (punt/kickoff/FG/XP), punt EPA, kick EPA,
    FG make rate

Grain: team x season x played-week (the week the games were PLAYED).
Script 35 converts to prediction-week grain (weeks < W only).

Walk-forward safety: this table contains only within-week aggregates; no
future information. Leakage audit: v2_research/leakage_audit.md.

NO model fitting. Feature architecture only.
"""
import glob
import os

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
OUT = f"{DATA}/v2/team_week_pbp.parquet"

DRIVE_POINTS = None  # computed per drive from score deltas


def drive_table(pbp):
    """One row per (game_id, fixed_drive) with drive-level outcomes."""
    g = pbp.groupby(["game_id", "fixed_drive"], sort=False)
    rows = []
    for (gid, fd), d in g:
        d = d.sort_index()
        first, last = d.iloc[0], d.iloc[-1]
        posteam = first["posteam"]
        if pd.isna(posteam):
            continue
        # points scored by posteam on this drive (score delta)
        if posteam == first["home_team"]:
            pts = (last["total_home_score"] - first["total_home_score"])
        elif posteam == first["away_team"]:
            pts = (last["total_away_score"] - first["total_away_score"])
        else:
            pts = 0.0
        res = last["fixed_drive_result"]
        rows.append({
            "game_id": gid, "season": first["season"], "week": first["week"],
            "posteam": posteam, "defteam": first["defteam"],
            "drive_points": float(pts), "drive_epa": float(d["epa"].sum()),
            "drive_plays": int(len(d)),
            "drive_start_y100": float(first["yardline_100"]),
            "result": res,
            "three_and_out": int(first["drive_first_downs"] == 0
                                and res == "Punt"),
            "scoring_drive": int(res in ("Touchdown", "Field goal")),
            "rz_trip": int((d["drive_inside20"] == 1).any()),
            "gtg_drive": int((d["goal_to_go"] == 1).any()),
            "gtg_td": int((d["goal_to_go"] == 1).any() and res == "Touchdown"),
            "end_turnover": int(res == "Turnover"),
        })
    return pd.DataFrame(rows)


def main():
    os.makedirs(f"{DATA}/v2", exist_ok=True)
    frames = []
    for f in sorted(glob.glob(f"{DATA}/pbp_2*.parquet")):
        if "pbp_2018_2025" in f or "players" in f or "qb_" in f:
            continue
        d = pd.read_parquet(f)
        d = d[d["week"] <= 22]
        d = d[(d["season"] >= 2018) & (d["season"] <= 2022)]  # vault/2026 excluded
        frames.append(d)
        print(f, len(d))
    pbp = pd.concat(frames, ignore_index=True)
    pbp = pbp[pbp["posteam"].notna()]
    print("plays:", len(pbp))

    # ---------- drive-level ----------
    drv = drive_table(pbp)
    print("drives:", len(drv))
    off = drv.groupby(["posteam", "season", "week"], observed=True).agg(
        drives=("drive_points", "size"),
        points_per_drive=("drive_points", "mean"),
        epa_per_drive=("drive_epa", "mean"),
        start_y100=("drive_start_y100", "mean"),
        three_and_out_rate=("three_and_out", "mean"),
        scoring_drive_rate=("scoring_drive", "mean"),
        rz_trip_rate=("rz_trip", "mean"),
        gtg_td_rate=("gtg_td", lambda s: s.sum() / max(drv.loc[s.index, "gtg_drive"].sum(), 1)),
        plays_per_drive=("drive_plays", "mean"),
        drive_to_rate=("end_turnover", "mean"),
    ).reset_index().rename(columns={"posteam": "team"})
    deff = drv.groupby(["defteam", "season", "week"], observed=True).agg(
        points_per_drive_allowed=("drive_points", "mean"),
        epa_per_drive_allowed=("drive_epa", "mean"),
        start_y100_allowed=("drive_start_y100", "mean"),
        three_and_out_forced=("three_and_out", "mean"),
        scoring_drive_allowed=("scoring_drive", "mean"),
        rz_trip_allowed=("rz_trip", "mean"),
        drive_to_forced=("end_turnover", "mean"),
    ).reset_index().rename(columns={"defteam": "team"})

    # ---------- play-level explosiveness / pressure proxies ----------
    scr = pbp[pbp["play_type"].isin(["pass", "run"])].copy()
    scr["expl_pass"] = ((scr["pass"] == 1) & (scr["yards_gained"] >= 16)).astype(int)
    scr["expl_rush"] = ((scr["rush"] == 1) & (scr["yards_gained"] >= 10)).astype(int)
    scr["big20"] = (scr["yards_gained"] >= 20).astype(int)
    scr["big40"] = (scr["yards_gained"] >= 40).astype(int)

    def q(p):
        return lambda s: float(s.quantile(p)) if len(s) else np.nan

    eo = scr.groupby(["posteam", "season", "week"], observed=True).agg(
        expl_pass_rate=("expl_pass", "mean"),
        expl_rush_rate=("expl_rush", "mean"),
        big20_rate=("big20", "mean"),
        big40_rate=("big40", "mean"),
        epa_std=("epa", "std"),
        epa_median=("epa", "median"),
        epa_p10=("epa", q(0.10)),
        epa_p90=("epa", q(0.90)),
        air_per_att=("air_yards", lambda s: s[scr.loc[s.index, "pass"] == 1].mean()),
        adot=("air_yards", lambda s: s[scr.loc[s.index, "pass"] == 1].mean()),
        dropbacks=("qb_dropback", "sum"),
        sacks=("sack", "sum"),
        qb_hits=("qb_hit", "sum"),
    ).reset_index().rename(columns={"posteam": "team"})
    eo["sack_rate"] = eo["sacks"] / eo["dropbacks"].replace(0, np.nan)
    eo["qb_hit_rate"] = eo["qb_hits"] / eo["dropbacks"].replace(0, np.nan)

    ed = scr.groupby(["defteam", "season", "week"], observed=True).agg(
        expl_pass_allowed=("expl_pass", "mean"),
        expl_rush_allowed=("expl_rush", "mean"),
        big20_allowed=("big20", "mean"),
        big40_allowed=("big40", "mean"),
        epa_std_allowed=("epa", "std"),
        sacks_made=("sack", "sum"),
        qb_hits_made=("qb_hit", "sum"),
        dropbacks_faced=("qb_dropback", "sum"),
    ).reset_index().rename(columns={"defteam": "team"})
    ed["sack_rate_made"] = ed["sacks_made"] / ed["dropbacks_faced"].replace(0, np.nan)

    # ---------- special teams ----------
    st = pbp[pbp["play_type"].isin(["punt", "kickoff", "field_goal", "extra_point"])].copy()
    stg = st.groupby(["posteam", "season", "week"], observed=True).agg(
        st_epa=("epa", "sum"),
        st_plays=("epa", "size"),
        punt_epa=("epa", lambda s: s[st.loc[s.index, "play_type"] == "punt"].sum()),
        kick_epa=("epa", lambda s: s[st.loc[s.index, "play_type"].isin(
            ["field_goal", "extra_point"])].sum()),
        kickoff_epa=("epa", lambda s: s[st.loc[s.index, "play_type"] == "kickoff"].sum()),
        fg_att=("play_type", lambda s: int((st.loc[s.index, "play_type"] == "field_goal").sum())),
        fg_made=("field_goal_result", lambda s: int((s == "made").sum())),
    ).reset_index().rename(columns={"posteam": "team"})
    stg["fg_make_rate"] = stg["fg_made"] / stg["fg_att"].replace(0, np.nan)
    stg["st_epa_per_play"] = stg["st_epa"] / stg["st_plays"].replace(0, np.nan)

    out = off.merge(deff, on=["team", "season", "week"], how="outer")
    out = out.merge(eo, on=["team", "season", "week"], how="outer")
    out = out.merge(ed, on=["team", "season", "week"], how="outer")
    out = out.merge(stg, on=["team", "season", "week"], how="outer")
    out = out.sort_values(["team", "season", "week"]).reset_index(drop=True)
    out.to_parquet(OUT, index=False)
    print(f"\nwrote {OUT}: {out.shape}")
    print("teams:", out["team"].nunique(), "seasons:", sorted(out["season"].unique()))


if __name__ == "__main__":
    main()
