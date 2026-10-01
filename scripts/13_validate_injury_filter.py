#!/usr/bin/env python3
"""Step 13: validate the stale-news filter on historical walk-forward picks.

Question: when the model's QB assumption was stale (actual starter differed
from the most recent starter — the QB the ELO/EPA ratings were built on), did
the model's spread picks do worse? If yes, voiding those picks is justified.

Method (no lookahead anywhere):
- Walk-forward predictions + closing lines: data/games_with_preds.parquet
  (ens_margin vs spread_line, 2023-2025 regular seasons).
- Model's QB assumption per game: each team's starter in its most recent
  prior game (this season, else last season), from nflverse schedules.
- Actual starter: the game's home_qb_name / away_qb_name.
- Injury-driven change: the assumed starter appears on that week's nflverse
  injury report as Out/Doubtful.

Compares ATS% of threshold picks (|edge| >= 3.0) in stale-QB games vs stable
games, and reports what the record would have been with injury-driven stale
picks voided. Small samples — directional evidence, not proof.
"""
import sys

import numpy as np
import pandas as pd

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
THRESH = 3.0
SEASONS = [2023, 2024, 2025]


def main():
    preds = pd.read_parquet(f"{DATA}/games_with_preds.parquet")
    preds = preds[preds["season"].isin(SEASONS) & (preds["week"] <= 18)].copy()
    sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    sched = sched[sched["season"].isin(SEASONS + [2022])].copy()

    # actual starters per game
    actual = {}
    for _, g in sched.iterrows():
        actual[g["game_id"]] = (g.get("away_qb_name"), g.get("home_qb_name"))

    # most-recent-prior starter per team (no lookahead)
    prior = {}
    last_starter = {}
    for (s, w), grp in sched.sort_values(["season", "week"]).groupby(["season", "week"]):
        if s not in SEASONS:
            # 2022 only seeds last_starter
            for _, g in grp.iterrows():
                if pd.notna(g.get("away_qb_name")):
                    last_starter[g["away_team"]] = g["away_qb_name"]
                if pd.notna(g.get("home_qb_name")):
                    last_starter[g["home_team"]] = g["home_qb_name"]
            continue
        for _, g in grp.iterrows():
            prior[g["game_id"]] = (last_starter.get(g["away_team"]),
                                   last_starter.get(g["home_team"]))
        for _, g in grp.iterrows():
            if pd.notna(g.get("away_qb_name")):
                last_starter[g["away_team"]] = g["away_qb_name"]
            if pd.notna(g.get("home_qb_name")):
                last_starter[g["home_team"]] = g["home_qb_name"]

    # injury-driven: assumed starter listed Out/Doubtful that week
    import nfl_data_py as nfl
    inj = nfl.import_injuries(SEASONS)
    inj = inj[(inj["position"] == "QB")
              & inj["report_status"].isin(["Out", "Doubtful"])]
    out_qb = set(zip(inj["season"], inj["week"],
                     inj["team"], inj["full_name"]))

    def norm(n):
        return str(n).lower().strip() if pd.notna(n) else ""

    rows = []
    for _, p in preds.iterrows():
        gid = p["game_id"]
        if gid not in actual or gid not in prior:
            continue
        (a_act, h_act), (a_pr, h_pr) = actual[gid], prior[gid]
        if not a_pr or not h_pr or not a_act or not h_act:
            continue
        stale_a = norm(a_act) != norm(a_pr)
        stale_h = norm(h_act) != norm(h_pr)
        inj_a = (p["season"], p["week"], p["away_team"], a_pr) in out_qb or \
                any((p["season"], p["week"], p["away_team"], n) in out_qb
                    for n in [a_pr])
        inj_h = (p["season"], p["week"], p["home_team"], h_pr) in out_qb
        edge = p["ens_margin"] - p["spread_line"]
        if abs(edge) < THRESH or pd.isna(p["spread_line"]):
            continue
        diff = p["home_margin"] - p["spread_line"]
        if diff > 0:
            result = "home"
        elif diff < 0:
            result = "away"
        else:
            result = "push"
        pick = "home" if edge > 0 else "away"
        rows.append({
            "season": p["season"], "week": p["week"],
            "game_id": gid, "pick": pick, "result": result,
            "stale": stale_a or stale_h,
            "inj_stale": (stale_a and inj_a) or (stale_h and inj_h),
            # did the raw edge point at the team whose QB info was stale?
            "edge_on_stale_side": ((stale_a and pick == "away")
                                   or (stale_h and pick == "home")),
        })
    df = pd.DataFrame(rows)
    print(f"threshold picks 2023-2025: {len(df)}")

    def summary(d, label):
        d = d[d["result"] != "push"]
        if len(d) == 0:
            print(f"{label}: n=0")
            return
        w = int((d["pick"] == d["result"]).sum())
        n = len(d)
        print(f"{label}: {w}-{n - w} ATS ({w / n:.1%}, n={n})")

    summary(df, "all picks                    ")
    summary(df[~df["stale"]], "stable-QB picks              ")
    summary(df[df["stale"]], "stale-QB picks (any change)  ")
    summary(df[df["inj_stale"]], "injury-stale picks (O/D)     ")
    summary(df[~df["inj_stale"]], "excl. injury-stale (filter)  ")

    sub = df[df["inj_stale"] & (df["result"] != "push")]
    if len(sub):
        on_stale = sub[sub["edge_on_stale_side"]]
        w = int((on_stale["pick"] == on_stale["result"]).sum())
        print(f"\nof {len(sub)} graded injury-stale picks, {len(on_stale)} had the "
              f"raw edge pointing at the stale-QB side: {w}-{len(on_stale) - w} ATS")
    print("\n(push games excluded from ATS%; filter voids injury-stale picks only)")


if __name__ == "__main__":
    main()
