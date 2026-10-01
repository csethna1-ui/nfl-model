#!/usr/bin/env python3
"""DEV-001: asymmetric offense/defense offseason persistence — DEV-ONLY (2021-2022).

Authorized 2026-10-01 by Cale: 2021-2022 dev evaluation ONLY.
FORBIDDEN: 2023-2025 Vault, production writes, V1 modification, weight changes,
tuning, market info, future info, touching completed experiments.

Design: rebuild V1's EPA ratings walk-forward with ONE code change —
at week 1 of 2021/2022, offseason prior = beta_side,r * prior-season-end rating
instead of symmetric 0.65. Everything else (ELO, linear fits on <=2020,
walk-forward GBM procedure, 0.40/0.50/0.10 weights) identical.

Beta fit: 2018->19 and 2019->20 transitions only (64 per side), league-centered
season-end ratings from OUR construction. See FIT_WINDOW_DECISION.md.
"""
import json
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

DATA = "/home/hatch/workspace/nfl-model/data"
EXP = "/home/hatch/workspace/nfl-model/experiments/external_audit_multirepo/dev001_asymmetric_persistence"

try:
    from xgboost import XGBRegressor
    GBM = "xgboost"
except ImportError:
    from sklearn.ensemble import HistGradientBoostingRegressor
    GBM = "sklearn-hgbr"

ALPHA = 0.25
PRIOR_WT = 0.35  # symmetric offseason regression (V1)
METRICS = ["off_epa", "off_pass_epa", "off_rush_epa", "off_sr",
           "def_epa", "def_pass_epa", "def_rush_epa", "def_sr"]
OFF_M = [m for m in METRICS if m.startswith("off")]
DEF_M = [m for m in METRICS if m.startswith("def")]
EPA_M_FEATS = ["off_epa_diff", "def_epa_diff", "off_pass_diff", "off_rush_diff",
               "def_pass_diff", "def_rush_diff", "sr_off_diff", "sr_def_diff"]
MARGIN_FEATS = ["elo_diff"] + EPA_M_FEATS + ["rest_diff", "div_game", "week"]


def weekly_aggs(pbp):
    use = pbp[(pbp["play_type"].isin(["pass", "run"])) & pbp["epa"].notna()].copy()
    use["is_pass"] = (use["play_type"] == "pass").astype(int)
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
    return off, dff


def run_epa_variant(games, off, dff, betas=None):
    """Exact copy of 03_ratings.run_epa logic, 2018-2022, with mode flag.
    betas=None -> V1 symmetric (x0.65 at every week 1).
    betas=dict -> at week 1 of 2021/2022 use beta per metric; 0.65 otherwise.
    Returns (per-game pre-game ratings df, season_end dict {season: {metric: {team: val}}}).
    """
    ratings = {m: {} for m in METRICS}
    out_rows = []
    season_end = {}
    last_season = None
    for (season, week), grp in games.groupby(["season", "week"], sort=True):
        if last_season is not None and season != last_season:
            season_end[last_season] = {m: dict(ratings[m]) for m in METRICS}
        last_season = season
        if week == 1:
            for m in METRICS:
                if betas is not None and season in (2021, 2022):
                    b = betas[m]
                    for t in list(ratings[m].keys()):
                        ratings[m][t] *= b
                else:
                    for t in list(ratings[m].keys()):
                        ratings[m][t] *= (1 - PRIOR_WT)
        for _, g in grp.iterrows():
            row = {"game_id": g["game_id"]}
            for m in METRICS:
                row[f"home_{m}"] = ratings[m].get(g["home_team"], 0.0)
                row[f"away_{m}"] = ratings[m].get(g["away_team"], 0.0)
            out_rows.append(row)
        wk_off = off[(off["season"] == season) & (off["week"] == week)].set_index("posteam")
        wk_def = dff[(dff["season"] == season) & (dff["week"] == week)].set_index("defteam")
        teams = set(wk_off.index) | set(wk_def.index)
        for t in teams:
            for m in METRICS:
                src = wk_off if m.startswith("off") else wk_def
                val = src.loc[t, m] if t in src.index else np.nan
                if pd.isna(val):
                    continue
                old = ratings[m].get(t, 0.0)
                ratings[m][t] = ALPHA * val + (1 - ALPHA) * old
    season_end[last_season] = {m: dict(ratings[m]) for m in METRICS}
    return pd.DataFrame(out_rows), season_end


def add_features(d):
    d = d.copy()
    d["off_epa_diff"] = d["home_off_epa"] - d["away_off_epa"]
    d["def_epa_diff"] = d["home_def_epa"] - d["away_def_epa"]
    d["off_pass_diff"] = d["home_off_pass_epa"] - d["away_off_pass_epa"]
    d["off_rush_diff"] = d["home_off_rush_epa"] - d["away_off_rush_epa"]
    d["def_pass_diff"] = d["home_def_pass_epa"] - d["away_def_pass_epa"]
    d["def_rush_diff"] = d["home_def_rush_epa"] - d["away_def_rush_epa"]
    d["sr_off_diff"] = d["home_off_sr"] - d["away_off_sr"]
    d["sr_def_diff"] = d["home_def_sr"] - d["away_def_sr"]
    d["rest_diff"] = d["home_rest"] - d["away_rest"]
    return d


def make_gbm():
    if GBM == "xgboost":
        return XGBRegressor(n_estimators=200, max_depth=3, learning_rate=0.05,
                            subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
                            random_state=42, n_jobs=4)
    return HistGradientBoostingRegressor(max_iter=200, max_depth=3,
                                        learning_rate=0.05, l2_regularization=1.0,
                                        random_state=42)


def walkforward_gbm(d):
    """Identical procedure to 04_backtest GBM, margin only.
    d must contain FULL history (2018+); predictions made for 2021-2022 weeks."""
    d = d.copy()
    d["pred_gbm_m"] = np.nan
    dev_weeks = (d[d["season"].isin([2021, 2022])]
                 [["season", "week"]].drop_duplicates().sort_values(["season", "week"]))
    for i, (s, w) in enumerate(dev_weeks.itertuples(index=False)):
        hist = d[(d["season"] < s) | ((d["season"] == s) & (d["week"] < w))]
        cur = (d["season"] == s) & (d["week"] == w)
        if len(hist) < 200 or cur.sum() == 0:
            continue
        gm = make_gbm().fit(hist[MARGIN_FEATS], hist["home_margin"])
        d.loc[cur, "pred_gbm_m"] = gm.predict(d.loc[cur, MARGIN_FEATS])
        if (i + 1) % 12 == 0:
            print(f"  gbm {s} w{w} ({i+1}/{len(dev_weeks)})", flush=True)
    return d


def main():
    print("loading data...", flush=True)
    sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    g = sched[sched["home_score"].notna()].copy()
    g = g[g["season"] <= 2022].sort_values(["season", "week"]).reset_index(drop=True)
    g["home_margin"] = g["home_score"] - g["away_score"]
    print("games 2018-2022:", len(g), "| dev 2021-22:", len(g[g["season"] >= 2021]),
          "| game_types:", g[g["season"] >= 2021]["game_type"].unique().tolist(), flush=True)

    pbp = pd.read_parquet(f"{DATA}/pbp_2018_2025.parquet")
    pbp = pbp[pbp["season"] <= 2022]
    off, dff = weekly_aggs(pbp)
    print("weekly aggs done", flush=True)

    # ---- V1 symmetric run (2018-2022) ----
    epa_v1, season_end = run_epa_variant(g, off, dff, betas=None)
    print("V1 symmetric ratings done", flush=True)

    # ---- beta estimation on pre-dev transitions ONLY ----
    # transitions: 2018->19, 2019->20 (64 per side). 2020->21 EXCLUDED (dev endpoint).
    betas, beta_detail = {}, {}
    for m in METRICS:
        xs, ys = [], []
        for s0, s1 in [(2018, 2019), (2019, 2020)]:
            r0 = season_end[s0][m]
            r1 = season_end[s1][m]
            teams = sorted(set(r0) & set(r1))
            mu0 = np.mean([r0[t] for t in teams])
            mu1 = np.mean([r1[t] for t in teams])
            for t in teams:
                xs.append(r0[t] - mu0)
                ys.append(r1[t] - mu1)
        xs = np.array(xs)
        ys = np.array(ys)
        beta = float(np.dot(xs, ys) / np.dot(xs, xs))
        betas[m] = beta
        beta_detail[m] = {"beta": round(beta, 4), "n": len(xs),
                          "transitions": ["2018->2019", "2019->2020"]}
    print("betas:", {m: round(b, 3) for m, b in betas.items()}, flush=True)

    # ---- candidate asymmetric run ----
    epa_cand, _ = run_epa_variant(g, off, dff, betas=betas)
    print("candidate asymmetric ratings done", flush=True)

    # ---- assemble FULL frames (2018-2022; GBM needs full history), then dev-filter ----
    base = pd.read_parquet(f"{DATA}/games_with_ratings.parquet")
    base = base[base["season"] <= 2022]
    epa_v1_full = epa_v1  # run_epa_variant already returns all games 2018-2022
    epa_cand_full = epa_cand
    keep = ["game_id", "season", "week", "game_type", "home_team", "away_team",
            "home_margin", "spread_line", "elo_diff", "home_rest", "away_rest", "div_game"]
    frames = {}
    for name, epa_df in [("v1", epa_v1_full), ("cand", epa_cand_full)]:
        d = base[keep].merge(epa_df, on="game_id", how="left")
        d = add_features(d).sort_values(["season", "week"]).reset_index(drop=True)
        frames[name] = d
    # train frame for linear fits (<=2020, symmetric features)
    tr = frames["v1"][frames["v1"]["season"] <= 2020].copy()

    lr_elo = LinearRegression().fit(tr[["elo_diff"]], tr["home_margin"])
    lr_epa = LinearRegression().fit(tr[EPA_M_FEATS], tr["home_margin"])
    print(f"lr fits done (train n={len(tr)})", flush=True)

    results = {"betas": beta_detail,
               "beta_note": "64 transitions per side (2018->19, 2019->20); 2020->21 excluded (dev endpoint)"}
    for name, d in frames.items():
        d["pred_elo"] = lr_elo.predict(d[["elo_diff"]])
        d["pred_epa_m"] = lr_epa.predict(d[EPA_M_FEATS])
        d = walkforward_gbm(d)
        d["ens"] = 0.4 * d["pred_elo"] + 0.5 * d["pred_epa_m"] + 0.1 * d["pred_gbm_m"]
        frames[name] = d
        dev = d[d["season"].isin([2021, 2022])]
        print(f"{name}: dev gbm NaNs: {int(dev['pred_gbm_m'].isna().sum())}/{len(dev)}", flush=True)

    # V1 GBM sanity check vs saved production predictions
    try:
        prod = pd.read_parquet(f"{DATA}/games_with_preds.parquet")
        prod = prod[prod["season"].isin([2021, 2022])][["game_id", "pred_gbm_m"]].rename(
            columns={"pred_gbm_m": "prod_gbm"})
        chk = frames["v1"][frames["v1"]["season"].isin([2021, 2022])][["game_id", "pred_gbm_m"]].merge(
            prod, on="game_id")
        print("v1 recomputed GBM vs saved production GBM: max abs diff =",
              round(float((chk["pred_gbm_m"] - chk["prod_gbm"]).abs().max()), 6), flush=True)
    except Exception as e:
        print("gbm sanity check skipped:", e, flush=True)

    v1 = frames["v1"][frames["v1"]["season"].isin([2021, 2022])].reset_index(drop=True)
    cand = frames["cand"][frames["cand"]["season"].isin([2021, 2022])].reset_index(drop=True)
    assert (v1["game_id"].values == cand["game_id"].values).all()
    act = v1["home_margin"].values
    mkt = v1["spread_line"].values

    def mae(p):
        return float(np.mean(np.abs(p - act)))

    e_v1 = np.abs(v1["ens"].values - act)
    e_c = np.abs(cand["ens"].values - act)
    e_epa_v1 = np.abs(v1["pred_epa_m"].values - act)
    e_epa_c = np.abs(cand["pred_epa_m"].values - act)
    e_gbm_v1 = np.abs(v1["pred_gbm_m"].values - act)
    e_gbm_c = np.abs(cand["pred_gbm_m"].values - act)
    e_elo = np.abs(v1["pred_elo"].values - act)  # identical both runs
    diff = e_c - e_v1  # negative = candidate better
    n = len(act)
    se = diff.std(ddof=1) / np.sqrt(n)
    # paired 95% CI via t
    from scipy import stats as sps
    ci_lo, ci_hi = sps.t.interval(0.95, n - 1, loc=diff.mean(), scale=se)

    wk = v1["week"].values
    early = wk <= 4
    late = wk >= 5
    s21 = v1["season"].values == 2021
    s22 = v1["season"].values == 2022

    out = {
        "n_games": int(n),
        "v1_mae": round(mae(v1["ens"].values), 4),
        "cand_mae": round(mae(cand["ens"].values), 4),
        "delta_mae": round(float(diff.mean()), 4),
        "rel_change_pct": round(float(diff.mean() / e_v1.mean() * 100), 3),
        "delta_2021": round(float(diff[s21].mean()), 4),
        "delta_2022": round(float(diff[s22].mean()), 4),
        "n_2021": int(s21.sum()), "n_2022": int(s22.sum()),
        "paired_ci95": [round(float(ci_lo), 4), round(float(ci_hi), 4)],
        "paired_p_two_sided": round(float(sps.ttest_rel(e_c, e_v1).pvalue), 4),
        "weeks1_4_delta": round(float(diff[early].mean()), 4),
        "weeks1_4_n": int(early.sum()),
        "weeks5_18_delta": round(float(diff[late].mean()), 4),
        "weeks5_18_n": int(late.sum()),
        "epa_comp_v1": round(float(e_epa_v1.mean()), 4),
        "epa_comp_cand": round(float(e_epa_c.mean()), 4),
        "epa_comp_delta": round(float((e_epa_c - e_epa_v1).mean()), 4),
        "epa_comp_delta_2021": round(float((e_epa_c - e_epa_v1)[s21].mean()), 4),
        "epa_comp_delta_2022": round(float((e_epa_c - e_epa_v1)[s22].mean()), 4),
        "epa_comp_delta_wks1_4": round(float((e_epa_c - e_epa_v1)[early].mean()), 4),
        "epa_comp_delta_wks5_18": round(float((e_epa_c - e_epa_v1)[late].mean()), 4),
        "gbm_comp_v1": round(float(e_gbm_v1.mean()), 4),
        "gbm_comp_cand": round(float(e_gbm_c.mean()), 4),
        "gbm_comp_delta": round(float((e_gbm_c - e_gbm_v1).mean()), 4),
        "elo_comp_mae": round(float(e_elo.mean()), 4),
        "market_mae": round(float(np.mean(np.abs(mkt - act))), 4),
        "cand_minus_market": round(float(np.mean(np.abs(cand["ens"].values - act)) - np.mean(np.abs(mkt - act))), 4),
        "v1_minus_market": round(float(np.mean(np.abs(v1["ens"].values - act)) - np.mean(np.abs(mkt - act))), 4),
    }
    results["metrics"] = out
    with open(f"{EXP}/results.json", "w") as f:
        json.dump(results, f, indent=2)
    # per-game errors for the registry
    pg = v1[["game_id", "season", "week", "home_team", "away_team", "home_margin"]].copy()
    pg["v1_ens"] = v1["ens"].values
    pg["cand_ens"] = cand["ens"].values
    pg["v1_epa"] = v1["pred_epa_m"].values
    pg["cand_epa"] = cand["pred_epa_m"].values
    pg["v1_gbm"] = v1["pred_gbm_m"].values
    pg["cand_gbm"] = cand["pred_gbm_m"].values
    pg["abs_err_diff"] = diff
    pg.to_csv(f"{EXP}/per_game_errors.csv", index=False)
    print(json.dumps(out, indent=2), flush=True)
    print("saved results.json + per_game_errors.csv (experiment dir only)", flush=True)


if __name__ == "__main__":
    main()
