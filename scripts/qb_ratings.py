#!/usr/bin/env python3
"""Walk-forward QB EPA/play ratings. No lookahead: a QB's rating attached to a
week-W game uses only his pass plays from weeks before W.

Conventions:
- pbp passer names look like "M.Ryan"; schedule starter names look like
  "Matt Ryan". build_name_map() learns the mapping empirically (majority vote
  of top passer per team-game).
- Rating: EWMA (alpha=0.2) of per-game EPA/play over pass plays, weekly
  batched; 35% offseason regression toward league mean; effective rating
  shrinks toward league mean with 60 career attempts of weight.
"""
import numpy as np
import pandas as pd

ALPHA = 0.2
PRIOR_WT = 0.35
SHRINK_ATT = 60.0


def build_name_map(sched, pbp):
    """Return dict schedule_full_name -> pbp 'F.Last' name, by majority vote
    of each team's top passer (by attempts) in each played game."""
    use = pbp[(pbp["play_type"] == "pass") & pbp["passer_player_name"].notna()]
    att = use.groupby(["game_id", "posteam", "passer_player_name"]).size().reset_index(name="n")
    top = att.sort_values("n", ascending=False).drop_duplicates(["game_id", "posteam"])
    g = sched[sched["home_score"].notna()][
        ["game_id", "home_team", "away_team", "home_qb_name", "away_qb_name"]]
    votes = {}
    for _, row in g.iterrows():
        for team, qb_col in ((row["home_team"], "home_qb_name"),
                             (row["away_team"], "away_qb_name")):
            sched_qb = row[qb_col]
            if pd.isna(sched_qb):
                continue
            hit = top[(top["game_id"] == row["game_id"]) & (top["posteam"] == team)]
            if hit.empty:
                continue
            pbp_qb = hit.iloc[0]["passer_player_name"]
            votes.setdefault(sched_qb, {}).setdefault(pbp_qb, 0)
            votes[sched_qb][pbp_qb] += 1
    return {s: max(v, key=v.get) for s, v in votes.items() if v}


def run_qb_ratings(pbp, games, name_map):
    """games: played games sorted by (season, week) with game_id, home_team,
    away_team, home_qb_name, away_qb_name.
    Returns (per-game DataFrame with qb_epa_home/qb_epa_away, state dict
    pbp_name -> {"rating":..., "att":...} after the last week)."""
    use = pbp[(pbp["play_type"] == "pass")
              & pbp["passer_player_name"].notna()
              & pbp["epa"].notna()].copy()
    lg_mean = use["epa"].mean()
    gq = use.groupby(["season", "week", "passer_player_name"]).agg(
        game_epa=("epa", "mean"), n_att=("epa", "size")).reset_index()

    rating, att = {}, {}
    out_rows = []
    state = {}
    last = games[["season", "week"]].drop_duplicates().sort_values(
        ["season", "week"]).iloc[-1]
    last_season, last_week = int(last["season"]), int(last["week"])

    def eff(qb):
        r = rating.get(qb, lg_mean)
        a = att.get(qb, 0.0)
        return (a * r + SHRINK_ATT * lg_mean) / (a + SHRINK_ATT)

    for (season, week), grp in games.groupby(["season", "week"], sort=True):
        if week == 1:
            for qb in list(rating.keys()):
                rating[qb] = lg_mean + (rating[qb] - lg_mean) * (1 - PRIOR_WT)
        for _, g in grp.iterrows():
            h_qb = name_map.get(g["home_qb_name"], None)
            a_qb = name_map.get(g["away_qb_name"], None)
            out_rows.append({"game_id": g["game_id"],
                             "qb_epa_home": eff(h_qb),
                             "qb_epa_away": eff(a_qb)})
        wk = gq[(gq["season"] == season) & (gq["week"] == week)]
        for _, r in wk.iterrows():
            qb = r["passer_player_name"]
            old = rating.get(qb, lg_mean)
            rating[qb] = ALPHA * r["game_epa"] + (1 - ALPHA) * old
            att[qb] = att.get(qb, 0.0) + r["n_att"]
        if season == last_season and week == last_week:
            state = {qb: {"rating": rating[qb], "att": att.get(qb, 0.0),
                          "eff": eff(qb)} for qb in rating}
    return pd.DataFrame(out_rows), state, float(lg_mean)


def qb_effective(qb_pbp_name, state, lg_mean):
    """Effective rating for a QB at prediction time (handles unknowns)."""
    if qb_pbp_name is None or qb_pbp_name not in state:
        return lg_mean
    s = state[qb_pbp_name]
    return (s["att"] * s["rating"] + SHRINK_ATT * lg_mean) / (s["att"] + SHRINK_ATT)
