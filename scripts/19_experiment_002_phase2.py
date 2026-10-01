#!/usr/bin/env python3
"""Experiment 002, Phase 2: ONE gated candidate — opponent-adjusted EPA.

Conceptual change (exactly one): the EPA-linear component's inputs change from
raw EPA/SR differentials to opponent-adjusted EPA/SR differentials.
Everything else is identical to V1: ELO component untouched, GBM untouched,
ensemble weights (0.4/0.5/0.1) untouched, linear refit on 2018-2020 only.

Walk-forward discipline: every adjusted rating uses only games strictly before
the target game week. The 2023-2025 vault is never loaded.

Gate (pre-registered): ONE vault evaluation only if on 2021-2022 the candidate
(a) beats market-only MAE by >= 0.15, (b) beats V1 MAE, (c) beats market in
2021 AND 2022 individually, (d) calibration slope in [0.8, 1.2].
"""
import json
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
OUT = os.path.join(REPO_ROOT, "experiments", "experiment_002_v1_error_analysis")

# feature categories and their opponent counterpart
OFF_CATS = ["off_epa", "off_pass_epa", "off_rush_epa", "off_sr"]
DEF_CATS = ["def_epa", "def_pass_epa", "def_rush_epa", "def_sr"]
COUNTER = {"off_epa": "def_epa", "off_pass_epa": "def_pass_epa",
           "off_rush_epa": "def_rush_epa", "off_sr": "def_sr",
           "def_epa": "off_epa", "def_pass_epa": "off_pass_epa",
           "def_rush_epa": "off_rush_epa", "def_sr": "off_sr"}
CATS = OFF_CATS + DEF_CATS
EPA_M_FEATS = ["off_epa_diff", "def_epa_diff", "off_pass_diff", "off_rush_diff",
               "def_pass_diff", "def_rush_diff", "sr_off_diff", "sr_def_diff"]
FEAT2CAT = {"off_epa_diff": "off_epa", "def_epa_diff": "def_epa",
            "off_pass_diff": "off_pass_epa", "off_rush_diff": "off_rush_epa",
            "def_pass_diff": "def_pass_epa", "def_rush_diff": "def_rush_epa",
            "sr_off_diff": "off_sr", "sr_def_diff": "def_sr"}

r = pd.read_parquet(f"{DATA}/games_with_ratings.parquet")
r = r[r["season"] <= 2022].copy().sort_values(["season", "week"]).reset_index(drop=True)
print("games 2018-2022:", len(r), flush=True)

# per-team pre-week ratings: team_weeks[(team, season, week)] = {cat: val}
team_weeks = {}
team_games = {}  # team -> list of (season, week, opp), chronological
for _, row in r.iterrows():
    s, w = int(row["season"]), int(row["week"])
    for side, team in (("home", row["home_team"]), ("away", row["away_team"])):
        team_weeks[(team, s, w)] = {c: float(row[f"{side}_{c}"]) for c in CATS}
    h, a = row["home_team"], row["away_team"]
    team_games.setdefault(h, []).append((s, w, a))
    team_games.setdefault(a, []).append((s, w, h))

teams = sorted(team_games.keys())
# cross-sectional league means per (season, week): league_mean[(s,w)][cat]
# = mean of each team's latest pre-week rating strictly before (s,w)
weeks = sorted({(x[1], x[2]) for x in team_weeks})
league_mean = {}
latest = {t: None for t in teams}  # team -> (s, w)
wi = 0
for (s, w) in weeks:
    while wi < len(weeks) and weeks[wi] < (s, w):
        s2, w2 = weeks[wi]
        for t in teams:
            if (t, s2, w2) in team_weeks:
                latest[t] = (s2, w2)
        wi += 1
    lm = {}
    for c in CATS:
        vals = [team_weeks[(t, latest[t][0], latest[t][1])][c]
                for t in teams if latest[t] is not None]
        lm[c] = float(np.mean(vals)) if vals else 0.0
    league_mean[(s, w)] = lm


def latest_before(team, s, w):
    cands = [(s2, w2) for (s2, w2, _) in team_games.get(team, []) if (s2, w2) < (s, w)]
    return max(cands) if cands else None


def adjusted_rating(team, s, w, cat):
    """Opponent-adjusted pre-week rating. Walk-forward: only past games."""
    raw = team_weeks[(team, s, w)][cat]
    faced = [(s2, w2, opp) for (s2, w2, opp) in team_games.get(team, [])
             if (s2, w2) < (s, w)][-16:]
    if not faced:
        return raw
    cc = COUNTER[cat]
    opp_vals = [team_weeks[(opp, s2, w2)][cc] for (s2, w2, opp) in faced]
    return raw - (float(np.mean(opp_vals)) - league_mean[(s, w)][cc])


print("computing opponent-adjusted features...", flush=True)
adj_rows = []
for _, row in r.iterrows():
    s, w = int(row["season"]), int(row["week"])
    h, a = row["home_team"], row["away_team"]
    adj = {}
    for f, cat in FEAT2CAT.items():
        ah = adjusted_rating(h, s, w, cat)
        aa = adjusted_rating(a, s, w, cat)
        adj["adj_" + f] = ah - aa
    adj_rows.append(adj)
adj_df = pd.DataFrame(adj_rows)
r = pd.concat([r, adj_df], axis=1)

ADJ_FEATS = ["adj_" + f for f in EPA_M_FEATS]
train = r[r["season"] <= 2020]
lr = LinearRegression().fit(train[ADJ_FEATS], train["home_margin"])
print(f"adj EPA->margin train R^2: {lr.score(train[ADJ_FEATS], train['home_margin']):.3f}", flush=True)
r["pred_epa_m_adj"] = lr.predict(r[ADJ_FEATS])

# candidate ensemble: V1 weights, ELO + GBM components from frozen V1 outputs
p = pd.read_parquet(f"{DATA}/games_with_preds.parquet")
p = p[p["season"].isin([2021, 2022])][["game_id", "pred_elo", "pred_gbm_m",
                                       "ens_margin", "spread_line", "home_margin",
                                       "season"]].copy()
r2 = r[r["season"] >= 2021][["game_id", "pred_epa_m_adj"]].copy()
m = p.merge(r2, on="game_id", validate="one_to_one")
assert len(m) == 569 and m["pred_epa_m_adj"].notna().all()
m["cand_margin"] = 0.4 * m["pred_elo"] + 0.5 * m["pred_epa_m_adj"] + 0.1 * m["pred_gbm_m"]


def summ(df, pred):
    e = (df[pred] - df["home_margin"]).abs()
    mk = (df["spread_line"] - df["home_margin"]).abs()
    x = df[pred].values
    slope = round(float(np.polyfit(x, df["home_margin"].values, 1)[0]), 3) if len(df) >= 30 else None
    return {"n": len(df), "mae": round(float(e.mean()), 3),
            "rmse": round(float(np.sqrt(((df[pred] - df["home_margin"]) ** 2).mean())), 3),
            "calib_slope": slope}


overall_c = summ(m, "cand_margin")
overall_v = summ(m, "ens_margin")
overall_m = summ(m, "spread_line")
by_season = {str(s): {"cand": summ(dd, "cand_margin"), "v1": summ(dd, "ens_margin"),
                      "mkt": summ(dd, "spread_line")}
             for s, dd in m.groupby("season")}

gate = {
    "a_beats_market_by_0.15": overall_c["mae"] <= overall_m["mae"] - 0.15,
    "b_beats_v1": overall_c["mae"] < overall_v["mae"],
    "c_holds_both_seasons": all(by_season[s]["cand"]["mae"] < by_season[s]["mkt"]["mae"]
                                for s in ["2021", "2022"]),
    "d_calibrated": overall_c["calib_slope"] is not None
                    and 0.8 <= overall_c["calib_slope"] <= 1.2,
}
gate["pass"] = all(gate[k] for k in ["a_beats_market_by_0.15", "b_beats_v1",
                                     "c_holds_both_seasons", "d_calibrated"])

result = {
    "candidate": "opponent-adjusted EPA (one-step, pre-week opponent ratings, last 16 games, league-centered)",
    "scope": "validation 2021-2022, n=569; linear refit 2018-2020 only; vault never loaded",
    "overall": {"candidate": overall_c, "v1": overall_v, "market": overall_m},
    "by_season": by_season,
    "gate": gate,
    "vault": "untouched" if not gate["pass"] else "WOULD BE EVALUATED ONCE (not run in this script)",
}
with open(f"{OUT}/phase2_candidate.json", "w") as f:
    json.dump(result, f, indent=1)
print(f"wrote {OUT}/phase2_candidate.json")
print(json.dumps({"overall": result["overall"], "gate": gate}, indent=1))
