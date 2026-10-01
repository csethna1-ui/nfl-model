#!/usr/bin/env python3
"""Step 3: Walk-forward ELO + EPA ratings, 2018-2025. No lookahead:
ratings attached to a game use only data through the prior week."""
import math
import numpy as np
import pandas as pd

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")

# ---------------- ELO ----------------
K = 20.0
HFA_ELO = 55.0          # ~2.2 points
REGRESS = 1.0 / 3.0     # offseason regression toward 1500

def mov_multiplier(margin, elo_diff):
    return math.log(abs(margin) + 1.0) * 2.2 / (2.2 + 0.001 * abs(elo_diff))

def run_elo(games):
    """games: DataFrame sorted by (season, week) with home_team, away_team, home_margin.
    Weekly batching: all games in a week use pre-week ELO; updates applied after."""
    elos = {}
    out_rows = []
    for (season, week), grp in games.groupby(["season", "week"], sort=True):
        if week == 1:
            for t in list(elos.keys()):
                elos[t] = 1500.0 + (elos[t] - 1500.0) * (1 - REGRESS)
        updates = {}
        for _, g in grp.iterrows():
            h, a = g["home_team"], g["away_team"]
            he = elos.get(h, 1500.0)
            ae = elos.get(a, 1500.0)
            diff = he - ae + HFA_ELO
            exp_h = 1.0 / (1.0 + 10 ** (-diff / 400.0))
            actual = 1.0 if g["home_margin"] > 0 else (0.5 if g["home_margin"] == 0 else 0.0)
            mm = mov_multiplier(g["home_margin"], diff)
            delta = K * mm * (actual - exp_h)
            updates[h] = updates.get(h, 0.0) + delta
            updates[a] = updates.get(a, 0.0) - delta
            out_rows.append({"game_id": g["game_id"], "elo_home": he, "elo_away": ae,
                             "elo_diff": he - ae})
        for t, d in updates.items():
            elos[t] = elos.get(t, 1500.0) + d
    return pd.DataFrame(out_rows), elos

# ---------------- EPA ratings ----------------
ALPHA = 0.25   # weekly EWMA weight on new games
PRIOR_WT = 0.35  # offseason regression toward league avg (0.0)

def run_epa(pbp, games):
    """Weekly-batch EPA ratings. Returns per-game pre-game ratings + final 2025 state."""
    use = pbp[(pbp["play_type"].isin(["pass", "run"])) & pbp["epa"].notna()].copy()
    use["is_pass"] = (use["play_type"] == "pass").astype(int)

    # weekly team aggregates: offense and defense
    off = use.groupby(["season", "week", "posteam"]).agg(
        off_plays=("epa", "size"), off_epa=("epa", "mean"),
        off_pass_epa=("epa", lambda s: s[use.loc[s.index, "is_pass"] == 1].mean()),
        off_rush_epa=("epa", lambda s: s[use.loc[s.index, "is_pass"] == 0].mean()),
        off_sr=("success", "mean")).reset_index()
    dff = use.groupby(["season", "week", "defteam"]).agg(
        def_plays=("epa", "size"), def_epa=("epa", "mean"),
        def_pass_epa=("epa", lambda s: s[use.loc[s.index, "is_pass"] == 1].mean()),
        def_rush_epa=("epa", lambda s: s[use.loc[s.index, "is_pass"] == 0].mean()),
        def_sr=("success", "mean")).reset_index()

    metrics = ["off_epa", "off_pass_epa", "off_rush_epa", "off_sr",
               "def_epa", "def_pass_epa", "def_rush_epa", "def_sr"]
    ratings = {m: {} for m in metrics}   # current rating per team
    out_rows = []
    final_state = {}

    for (season, week), grp in games.groupby(["season", "week"], sort=True):
        if week == 1:
            # offseason regression toward 0 (league avg)
            for m in metrics:
                for t in list(ratings[m].keys()):
                    ratings[m][t] *= (1 - PRIOR_WT)
        # attach pre-week ratings
        for _, g in grp.iterrows():
            row = {"game_id": g["game_id"]}
            for m in metrics:
                row[f"home_{m}"] = ratings[m].get(g["home_team"], 0.0)
                row[f"away_{m}"] = ratings[m].get(g["away_team"], 0.0)
            out_rows.append(row)
        # update with this week's games
        wk_off = off[(off["season"] == season) & (off["week"] == week)].set_index("posteam")
        wk_def = dff[(dff["season"] == season) & (dff["week"] == week)].set_index("defteam")
        teams = set(wk_off.index) | set(wk_def.index)
        for t in teams:
            for m in metrics:
                src = wk_off if m.startswith("off") else wk_def
                val = src.loc[t, m] if t in src.index else np.nan
                if pd.isna(val):
                    continue
                old = ratings[m].get(t, 0.0)
                ratings[m][t] = ALPHA * val + (1 - ALPHA) * old
        if season == 2025 and week == games[games["season"] == 2025]["week"].max():
            for m in metrics:
                final_state[m] = dict(ratings[m])

    return pd.DataFrame(out_rows), final_state

def main():
    sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    g = sched[sched["home_score"].notna()].copy()
    g = g.sort_values(["season", "week"]).reset_index(drop=True)
    g["home_margin"] = g["home_score"] - g["away_score"]
    g["total_pts"] = g["home_score"] + g["away_score"]
    print("games with scores 2018-2025:", len(g))

    elo_df, final_elos = run_elo(g)
    print("ELO done. sample final:", {k: round(v) for k, v in list(final_elos.items())[:5]})

    pbp = pd.read_parquet(f"{DATA}/pbp_2018_2025.parquet")
    print("pbp rows:", len(pbp))
    epa_df, final_epa = run_epa(pbp, g)
    print("EPA done.")

    out = g[["game_id", "season", "week", "game_type", "home_team", "away_team",
             "home_score", "away_score", "home_margin", "total_pts",
             "spread_line", "total_line", "home_rest", "away_rest", "div_game"]].merge(
        elo_df, on="game_id").merge(epa_df, on="game_id")
    out.to_parquet(f"{DATA}/games_with_ratings.parquet", index=False)
    print("saved games_with_ratings:", len(out))

    import pickle
    with open(f"{DATA}/final_2025_state.pkl", "wb") as f:
        pickle.dump({"elos": final_elos, "epa": final_epa}, f)
    print("saved final_2025_state.pkl")

if __name__ == "__main__":
    main()
