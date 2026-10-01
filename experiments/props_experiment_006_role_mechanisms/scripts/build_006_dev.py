"""
Props Experiment 006 — DEV phase (frozen preregistration 2026-10-01).

DEV ONLY: fits candidates M1/M2 on 2021-2022. NO 2023-2024 data is loaded,
inspected, or summarized anywhere in this script (hard rule, asserted).

M0 = frozen Props Model D (Experiment 001), reproduced read-only by
re-executing the frozen 001 training procedure on train (2018-2020) with the
frozen dev-selected hyperparameters from dry_run_dev.json (same procedure as
005 dev). No 001 pipeline code or artifact is modified; reproduction is
verified bit-identical against the recorded 001 dev MAE before any candidate
fitting.

M1 (contrast + Ridge): frozen contrast features + frozen M0 prediction as a
feature -> Ridge, alpha selected from {0.1, 1, 10, 100} by in-sample dev MAE.
RIDGE ONLY - no GBM, no interaction grid, no feature selection. The capacity
limit is the point of the experiment (the 005 lesson).

M2 (Kalman): per-player state [share, eff] with stat-specific process noise.
Team change resets the share state to the positional prior (wide variance)
while efficiency carries over. Exactly 3 global scalars (q_share, q_eff, r)
fit by one-step-ahead predictive log-likelihood on eligible dev rows
(L-BFGS-B on log-params, deterministic, seed 1337).

Outputs (experiments/props_experiment_006_role_mechanisms/):
  scripts/build_006_dev.py
  data/dev_predictions.parquet   (M0/M1/M2 dev predictions, dev rows only)
  models/M1_{market}_fitted.pkl  (Ridge + scaler + alpha + feature order)
  models/M2_{market}_params.json (locked q_share, q_eff, r + priors)
  DEV_DIAGNOSTICS.md
  LOCKED_PARAMETERS.md / .json
"""
import json
import math
import os
import pickle
import re
import sys
import time

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from scipy.optimize import minimize

EXP = "/home/hatch/workspace/nfl-model/experiments/props_experiment_006_role_mechanisms"
TABLE = "/home/hatch/workspace/nfl-model/experiments/player_props_projection/data/modeling_table.parquet"
SEL = "/home/hatch/workspace/nfl-model/experiments/player_props_projection/data/dry_run_dev.json"
PG = "/home/hatch/workspace/nfl-model/data/player_games.parquet"
SNAP_DIR = "/home/hatch/workspace/nfl-model/data/v2/raw"

SEED = 1337
rng = np.random.default_rng(SEED)
np.random.seed(SEED)
HALF_LIFE = 3.0
MAX_TRAIL = 16
DEV_SEASONS = (2021, 2022)
TRAIN_SEASONS = (2018, 2019, 2020)

MARKETS = ["pass_yards", "rush_yards", "receiving_yards"]
RIDGE_ALPHAS = [0.1, 1.0, 10.0, 100.0]

# ---- frozen 001 feature lists (copied verbatim from 005's build_005_dev.py) ----
OPPORTUNITY_FEATS = [
    "trail_targets_ewma", "trail_rush_att_ewma", "trail_pass_att_ewma",
    "trail_target_share_ewma", "trail_rush_share_ewma", "trail_air_share_ewma",
    "trail_team_targets_ewma", "trail_team_pass_att_ewma", "trail_team_rush_att_ewma",
    "trail_rz_targets_ewma", "trail_rz_carries_ewma", "trail_air_yards_ewma",
    "trail_games",
]
EFFICIENCY_FEATS = [
    "trail_ypt_ewma", "trail_ypc_ewma", "trail_ypa_ewma",
    "trail_comp_rate_ewma", "trail_yac_pt_ewma",
]
YARDS_FEATS = ["trail_pass_yards_ewma", "trail_rush_yards_ewma", "trail_receiving_yards_ewma"]
OPP_FEATS = ["opp_trail_pass_allowed_ewma", "opp_trail_rush_allowed_ewma"]
ENV_FEATS = ["spread_line", "total_line", "is_home", "team_spread",
             "team_implied_total", "opp_implied_total"]
ALL_FEATS = OPPORTUNITY_FEATS + EFFICIENCY_FEATS + YARDS_FEATS + OPP_FEATS + ENV_FEATS
C_PARAMS = dict(loss="quantile", learning_rate=0.1, max_depth=3,
                max_iter=300, min_samples_leaf=20, random_state=7)

EXPECTED_D_DEV_MAE = {"pass_yards": 57.774014152193786,
                      "rush_yards": 25.14778096197956,
                      "receiving_yards": 23.976700644236963}

# ---- 006 frozen specs ----
# M1 contrast feature order (frozen; same list for all three targets - no feature selection)
M1_ORDER = ["m0", "contrast_snap", "contrast_carries", "contrast_tshare",
            "contrast_rush1", "contrast_tgt1", "stint_games", "transfer_ind"]
# team volume column per market (trailing EWMA hl=3/max16 of team attempts - prereg team_volume_T)
TEAM_VOL_COL = {"rush_yards": "trail_team_rush_att_ewma",
                "receiving_yards": "trail_team_targets_ewma",
                "pass_yards": "trail_team_pass_att_ewma"}
# market -> (share obs, eff obs, n obs, eligible positions)
MKT_DEF = {
    "rush_yards":      dict(pos=("RB",),          share="rush_share_g",  eff_num="rush_yards",      eff_den="rush_att", n="rush_att"),
    "receiving_yards": dict(pos=("RB", "WRTE"),    share="target_share_g", eff_num="receiving_yards", eff_den="targets",  n="targets"),
    "pass_yards":      dict(pos=("QB",),          share="pass_share_g",  eff_num="pass_yards",      eff_den="pass_att", n="pass_att"),
}
# Kalman frozen constants (not tuned): wide prior variances
V0_SHARE, V0_EFF = 1.0, 100.0
# high-contrast slice: market -> primary contrast magnitude column
CONTRAST_MAG = {"rush_yards": "contrast_carries",
                "receiving_yards": "contrast_tshare",
                "pass_yards": "contrast_snap"}


def mae(y, p):
    return float(np.mean(np.abs(y - p)))


def ewma(v):
    """Frozen 001 convention: half-life 3, most-recent-first, NaN dropped."""
    v = np.asarray(v, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return np.nan
    w = 0.5 ** (np.arange(len(v)) / HALF_LIFE)
    return float(np.sum(w * v) / np.sum(w))


def ukey(name):
    """Name key for the snap-count join (002 recipe, verbatim from 19_prod_receptions.py)."""
    s = str(name).lower().strip()
    s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)\.?$", "", s)
    s = re.sub(r"\.", " ", s)
    toks = [t for t in s.split() if t]
    if len(toks) < 2:
        return None
    return f"{toks[0][0]}.{toks[-1]}"


# ---------------- M0 reproduction (frozen 001 procedure, read-only; verbatim from 005) ----------------
def fit_A(train, alpha):
    X1 = train[OPPORTUNITY_FEATS].to_numpy(float)
    X2 = train[EFFICIENCY_FEATS].to_numpy(float)
    att = train["actual_att"].to_numpy(float)
    eff = train["actual_yards"].to_numpy(float) / np.maximum(att, 1e-6)
    s1, s2 = StandardScaler(), StandardScaler()
    r1 = Ridge(alpha=alpha).fit(s1.fit_transform(X1), att)
    r2 = Ridge(alpha=alpha).fit(s2.fit_transform(X2), eff)
    return (s1, r1, s2, r2)


def pred_A(model, df):
    s1, r1, s2, r2 = model
    o = np.maximum(r1.predict(s1.transform(df[OPPORTUNITY_FEATS].to_numpy(float))), 0.0)
    e = r2.predict(s2.transform(df[EFFICIENCY_FEATS].to_numpy(float)))
    return np.maximum(o * e, 0.0)


def fit_B(train, params):
    from sklearn.ensemble import HistGradientBoostingRegressor
    m = HistGradientBoostingRegressor(random_state=11, **params)
    return m.fit(train[ALL_FEATS].to_numpy(float), train["actual_yards"].to_numpy(float))


def pred_B(model, df):
    return np.maximum(model.predict(df[ALL_FEATS].to_numpy(float)), 0.0)


def fit_C(train):
    from sklearn.ensemble import HistGradientBoostingRegressor
    X = train[ALL_FEATS].to_numpy(float)
    y = train["actual_yards"].to_numpy(float)
    return {q: HistGradientBoostingRegressor(quantile=q, **C_PARAMS).fit(X, y)
            for q in (0.25, 0.5, 0.75)}


def pred_C(model, df, q=0.5):
    return np.maximum(model[q].predict(df[ALL_FEATS].to_numpy(float)), 0.0)

# ---------------- per-game history table (train+dev only) ----------------
def build_history():
    """
    One row per player-week (2018-2022) with raw per-game opportunity data.
    All values are completed-game records -> Friday 18:00 CT safe by construction.
    """
    pg = pd.read_parquet(PG)
    pg = pg[pg["season"].between(TRAIN_SEASONS[0], DEV_SEASONS[1])].copy()
    assert pg["season"].max() <= 2022 and pg["season"].min() >= 2018

    # team totals per game (verified complete: median 25 rush / 33 targets / 37 pass att)
    tm = (pg.groupby(["game_id", "team"], as_index=False)[["rush_att", "targets", "pass_att"]]
            .sum().rename(columns={"rush_att": "team_rush", "targets": "team_targets",
                                    "pass_att": "team_pass"}))
    pg = pg.merge(tm, on=["game_id", "team"], how="left")
    pg["rush_share_g"] = pg["rush_att"] / pg["team_rush"].replace(0, np.nan)
    pg["target_share_g"] = pg["targets"] / pg["team_targets"].replace(0, np.nan)
    pg["pass_share_g"] = pg["pass_att"] / pg["team_pass"].replace(0, np.nan)
    for c in ("rush_share_g", "target_share_g", "pass_share_g"):
        pg[c] = pg[c].fillna(0.0)

    # snap share via the 002 ukey recipe (verbatim)
    sn_parts = [pd.read_csv(os.path.join(SNAP_DIR, f"snap_counts_{s}.csv"))
                for s in range(TRAIN_SEASONS[0], DEV_SEASONS[1] + 1)]
    sn = pd.concat(sn_parts, ignore_index=True)
    sn = sn[sn["game_type"] == "REG"].copy()
    sn["sukey"] = sn["player"].map(ukey) + "|" + sn["team"]
    sn = (sn.sort_values("offense_pct")
            .drop_duplicates(["sukey", "season", "week"], keep="last"))
    pg["sukey"] = pg["player_name"].map(ukey) + "|" + pg["team"]
    pg = pg.merge(sn[["sukey", "season", "week", "offense_pct"]],
                  on=["sukey", "season", "week"], how="left")
    print(f"  snap merge rate: {pg['offense_pct'].notna().mean():.4f}", flush=True)
    # missing snap row ~= zero-snap game (player has a stat row but no snap record)
    pg["snap_g"] = pg["offense_pct"].fillna(0.0)

    # name collisions: keep the max-touches row per player-week for the history chain
    ndup = int(pg.duplicated(["player_name", "season", "week"]).sum())
    if ndup:
        pg = (pg.sort_values("touches", ascending=False)
                .drop_duplicates(["player_name", "season", "week"])
                .reset_index(drop=True))
        print(f"  history: dropped {ndup} phantom player-week rows (name collisions)", flush=True)
    assert pg.duplicated(["player_name", "season", "week"]).sum() == 0
    return pg.sort_values(["player_name", "season", "week"]).reset_index(drop=True)


def add_stints(hist):
    """
    Team stints on the history walk. A stint = maximal run of consecutive
    player-games with the same team.
      stint_games       # prior games played within the current stint
      transfer_ind      # 1 on the single game where a transfer stint begins
      in_transfer_stint # 1 for every game of a stint that began with a team change
    """
    hist = hist.sort_values(["player_name", "season", "week"]).reset_index(drop=True)
    n = len(hist)
    stint_games = np.zeros(n)
    transfer_ind = np.zeros(n)
    in_ts = np.zeros(n)
    stint_start_flag = np.zeros(n, dtype=bool)
    teams = hist["team"].to_numpy()
    idx = 0
    for player, grp in hist.groupby("player_name", sort=False):
        g = grp.sort_values(["season", "week"])
        pos = g.index.to_numpy()
        start = 0
        cur_transfer = False
        for j in range(len(g)):
            if j > 0 and teams[pos[j]] != teams[pos[j - 1]]:
                start = j
                cur_transfer = True
                stint_start_flag[pos[j]] = True
            stint_games[pos[j]] = j - start
            transfer_ind[pos[j]] = 1.0 if (j == start and start > 0) else 0.0
            in_ts[pos[j]] = 1.0 if cur_transfer else 0.0
        idx += 1
    hist["stint_games"] = stint_games
    hist["transfer_ind"] = transfer_ind
    hist["in_transfer_stint"] = in_ts
    hist["stint_start"] = stint_start_flag
    return hist


# ---------------- contrast features (frozen M1 list) ----------------
def last3_mean(a):
    a = np.asarray(a, dtype=float)
    return float(np.mean(a[-3:])) if len(a) else np.nan


def add_contrast_features(hist):
    """
    For every walk game, compute from STRICTLY PRIOR games:
      contrast_snap    = snap_last3 - snap_trailing16
      contrast_carries = carries_last3 - carries_trailing16
      contrast_tshare  = tshare_last3 - tshare_trailing16
      contrast_rush1   = rush_share_last1 - rush_share_season
      contrast_tgt1    = target_share_last1 - target_share_season
    where last3 = mean of up to 3 most recent prior games,
    trailing16 = EWMA(hl=3, max 16, most-recent-first) of prior games,
    last1 = most recent prior game, season = mean of prior same-season games.
    NaN -> 0 per modeling-table convention (no prior info -> no contrast).
    """
    cols = ["contrast_snap", "contrast_carries", "contrast_tshare",
            "contrast_rush1", "contrast_tgt1"]
    out = {c: np.zeros(len(hist)) for c in cols}
    snap = hist["snap_g"].to_numpy(float)
    car = hist["rush_att"].to_numpy(float)
    tsh = hist["target_share_g"].to_numpy(float)
    rsh = hist["rush_share_g"].to_numpy(float)
    season = hist["season"].to_numpy()

    for player, grp in hist.groupby("player_name", sort=False):
        g = grp.sort_values(["season", "week"])
        pos = g.index.to_numpy()
        for k in range(len(g)):
            j = pos[k]
            if k == 0:
                continue  # no priors -> contrasts stay 0
            pr = pos[:k]
            s3 = lambda a: last3_mean(a[pr])
            t16 = lambda a: ewma(a[pr][::-1][:MAX_TRAIL])
            out["contrast_snap"][j] = s3(snap) - t16(snap)
            out["contrast_carries"][j] = s3(car) - t16(car)
            out["contrast_tshare"][j] = s3(tsh) - t16(tsh)
            same_season = pr[season[pr] == season[j]]
            if len(same_season):
                out["contrast_rush1"][j] = rsh[pr[-1]] - float(np.mean(rsh[same_season]))
                out["contrast_tgt1"][j] = tsh[pr[-1]] - float(np.mean(tsh[same_season]))
    for c in cols:
        hist[c] = np.nan_to_num(out[c], nan=0.0)
    return hist

# ---------------- M2 Kalman machinery (frozen spec) ----------------
def build_player_bundles(hist, ev, market):
    """
    Per-player time-ordered game arrays for the Kalman walk.
    Only players with >=1 eligible dev row are walked (others cannot affect
    the dev likelihood or dev predictions).
    Each bundle: share/eff observations, n, stint_start, eval_mask,
    team_vol_T and actual_yards at eval rows.
    """
    d = MKT_DEF[market]
    # DEV ONLY for the likelihood/predictions: the filter state is still walked
    # over each player's full train+dev history for continuity, but eval rows
    # (likelihood contributions and saved predictions) are dev-period only.
    evm = ev[(ev["market"] == market) & (ev["period"] == "dev")].reset_index(drop=True)
    keys = set(zip(evm["player_name"], evm["season"], evm["week"]))
    # namesake duplicates (documented 005 deviation #4): dedupe for the scalar lookup;
    # evaluated duplicates rejoin m:1 and share the prediction in main()
    evm_lookup = (evm.drop_duplicates(["player_name", "season", "week"])
                     .set_index(["player_name", "season", "week"]))
    sub = hist[hist["player_name"].isin(evm["player_name"].unique())].copy()
    sub = sub.sort_values(["player_name", "season", "week"]).reset_index(drop=True)
    sub["is_eval"] = [k in keys for k in
                      zip(sub["player_name"], sub["season"], sub["week"])]
    # team volume + actuals from the modeling table (trailing EWMA, strictly prior weeks)
    evm2 = evm_lookup
    sub["team_vol"] = np.nan
    sub["actual"] = np.nan
    has = sub["is_eval"].to_numpy()
    idx_keys = list(zip(sub.loc[has, "player_name"], sub.loc[has, "season"], sub.loc[has, "week"]))
    sub.loc[has, "team_vol"] = [evm2.loc[k, TEAM_VOL_COL[market]] for k in idx_keys]
    sub.loc[has, "actual"] = [evm2.loc[k, "actual_yards"] for k in idx_keys]
    assert sub.loc[has, "team_vol"].notna().all()

    share = sub[d["share"]].to_numpy(float)
    n = sub[d["n"]].to_numpy(float)
    eff_num = sub[d["eff_num"]].to_numpy(float)
    eff_den = sub[d["eff_den"]].to_numpy(float)
    eff = np.where(eff_den > 0, eff_num / np.maximum(eff_den, 1e-9), np.nan)

    bundles = []
    for player, grp in sub.groupby("player_name", sort=False):
        g = grp.sort_values(["season", "week"])
        if not g["is_eval"].any():
            continue
        bundles.append(dict(
            name=player,
            keys=list(zip(g.loc[g["is_eval"], "player_name"],
                          g.loc[g["is_eval"], "season"],
                          g.loc[g["is_eval"], "week"])),
            share=share[g.index.to_numpy()],
            eff=eff[g.index.to_numpy()],
            n=n[g.index.to_numpy()],
            stint_start=g["stint_start"].to_numpy(),
            is_eval=g["is_eval"].to_numpy(),
            team_vol=g["team_vol"].to_numpy(dtype=float),
            actual=g["actual"].to_numpy(dtype=float),
        ))
    return bundles


def kalman_run(bundles, qs, qe, r, prior_s, prior_e):
    """
    One walk over all bundles. Returns (total_ll, preds) where preds maps
    bundle-order eval rows to (pred_yards). LL sums one-step-ahead predictive
    log-likelihood of observed share/eff at eligible dev rows with n>0.
    State maintained as posterior; predictive = posterior + process noise.
    """
    LOG2PI = math.log(2 * math.pi)
    total_ll = 0.0
    pred_list, act_list = [], []
    for b in bundles:
        m_s, v_s = prior_s, V0_SHARE
        m_e, v_e = prior_e, V0_EFF
        seen = 0
        sh, ef, nn = b["share"], b["eff"], b["n"]
        for j in range(len(sh)):
            # --- predictive distribution ---
            if seen < 3:
                ps_m, ps_v, pe_m, pe_v = prior_s, V0_SHARE, prior_e, V0_EFF
                post_s, post_e = (prior_s, V0_SHARE), (prior_e, V0_EFF)
            else:
                ps_m, ps_v = m_s, v_s + qs
                pe_m, pe_v = m_e, v_e + qe
                if b["stint_start"][j]:
                    # team change: share state reset to positional prior (wide);
                    # efficiency state carries over unchanged (frozen spec)
                    ps_m, ps_v = prior_s, V0_SHARE
                post_s, post_e = (ps_m, ps_v), (pe_m, pe_v)
            # --- prediction + likelihood at eligible dev rows ---
            if b["is_eval"][j]:
                pred = float(b["team_vol"][j] * ps_m * pe_m)
                pred_list.append(max(pred, 0.0))
                act_list.append(float(b["actual"][j]))
                if nn[j] > 0:
                    for y, pm, pv in ((sh[j], ps_m, ps_v), (ef[j], pe_m, pe_v)):
                        if np.isnan(y):
                            continue
                        var = pv + r / nn[j]
                        total_ll += -0.5 * (LOG2PI + math.log(var) + (y - pm) ** 2 / var)
            # --- update (skip when no observation) ---
            if nn[j] > 0 and not np.isnan(sh[j]):
                R = r / nn[j]
                K = post_s[1] / (post_s[1] + R)
                m_s = post_s[0] + K * (sh[j] - post_s[0])
                v_s = (1.0 - K) * post_s[1]
            else:
                m_s, v_s = post_s
            if nn[j] > 0 and not np.isnan(ef[j]):
                R = r / nn[j]
                K = post_e[1] / (post_e[1] + R)
                m_e = post_e[0] + K * (ef[j] - post_e[0])
                v_e = (1.0 - K) * post_e[1]
            else:
                m_e, v_e = post_e
            seen += 1
    return total_ll, np.array(pred_list), np.array(act_list)


def fit_kalman(bundles, prior_s, prior_e):
    """Maximize one-step-ahead predictive LL over (log q_share, log q_eff, log r)."""
    def nll(theta):
        qs, qe, r = np.exp(theta)
        ll, _, _ = kalman_run(bundles, qs, qe, r, prior_s, prior_e)
        return -ll
    theta0 = np.log([0.005, 0.5, 1.0])
    res = minimize(nll, theta0, method="L-BFGS-B",
                   bounds=[(-12.0, 3.0)] * 3,
                   options={"maxiter": 500, "ftol": 1e-10, "gtol": 1e-8})
    assert res.success, f"Kalman fit failed: {res.message}"
    qs, qe, r = np.exp(res.x)
    return float(qs), float(qe), float(r), float(-res.fun)


def positional_priors(hist, market):
    """Positional prior means from TRAIN (2018-2020) per-game observations, n>0."""
    d = MKT_DEF[market]
    tr = hist[(hist["season"].isin(TRAIN_SEASONS)) & (hist["position"].isin(d["pos"]))].copy()
    n = tr[d["n"]].to_numpy(float)
    m = n > 0
    ps = float(np.mean(tr[d["share"]].to_numpy(float)[m]))
    num = tr[d["eff_num"]].to_numpy(float)[m]
    den = np.maximum(tr[d["eff_den"]].to_numpy(float)[m], 1e-9)
    pe = float(np.mean(num / den))
    return ps, pe

# ---------------- M1: contrast + Ridge (RIDGE ONLY) ----------------
def fit_ridge(X, y, alpha):
    s = StandardScaler()
    m = Ridge(alpha=alpha).fit(s.fit_transform(X), y)
    return (s, m)


def pred_ridge(model, X):
    s, m = model
    return m.predict(s.transform(X))


def cv_mae_ridge(X, y, alpha, k=5, seed=SEED):
    """Honesty diagnostic ONLY (reported; does not affect the frozen selection)."""
    r = np.random.default_rng(seed)
    idx = np.arange(len(y))
    r.shuffle(idx)
    folds = np.array_split(idx, k)
    ms = []
    for f in folds:
        tr = np.concatenate([g for g in folds if g is not f])
        mdl = fit_ridge(X[tr], y[tr], alpha)
        ms.append(mae(y[f], pred_ridge(mdl, X[f])))
    return float(np.mean(ms))


def cv_mae_kalman(bundles, prior_s, prior_e, k=5, seed=SEED):
    """
    Honesty diagnostic ONLY for M2 (reported; does not affect selection).
    Player-level 5-fold CV: fit (q_share, q_eff, r) on 4/5 of players' dev
    games, evaluate MAE on the held-out players' dev games. Each player's
    filter state is walked on their own history only - no cross-player leakage.
    """
    r = np.random.default_rng(seed)
    order = np.arange(len(bundles))
    r.shuffle(order)
    folds = np.array_split(order, k)
    ms = []
    for f in folds:
        tr_b = [bundles[i] for i in np.concatenate([g for g in folds if g is not f])]
        te_b = [bundles[i] for i in f]
        qs, qe, rr, _ = fit_kalman(tr_b, prior_s, prior_e)
        _, pred, act = kalman_run(te_b, qs, qe, rr, prior_s, prior_e)
        ms.append(mae(act, pred))
    return float(np.mean(ms))


# ---------------- main: DEV ONLY ----------------
def main():
    t0 = time.time()
    sel = json.load(open(SEL))["selection"]
    os.makedirs(f"{EXP}/data", exist_ok=True)
    os.makedirs(f"{EXP}/models", exist_ok=True)

    full = pd.read_parquet(TABLE)
    # HARD RULE: the locked test (2023-2024) is never loaded for this experiment.
    work = full[full["period"].isin(["train", "dev"])].copy()
    assert "test" not in work["period"].unique(), "locked-test rows present - ABORT"
    assert not ((work["season"] == 2023) | (work["season"] == 2024)).any(), "2023/2024 rows present - ABORT"
    assert not (work["season"] > 2024).any(), "post-2024 rows present - ABORT"
    print("HARD RULE OK: train+dev only, no 2023-2024 rows", flush=True)

    print("building per-game history (train+dev)...", flush=True)
    hist = build_history()
    hist = add_stints(hist)
    print("computing contrast features...", flush=True)
    hist = add_contrast_features(hist)

    ev = work[(work["eligible_hist"] == 1) & (work["played_role"] == 1)].copy()
    FEAT_COLS = ["player_name", "season", "week"] + M1_ORDER[1:] + ["in_transfer_stint"]
    dev = {}
    for m in MARKETS:
        direct = ev[(ev["period"] == "dev") & (ev["market"] == m)].reset_index(drop=True)
        mg = direct.merge(hist[FEAT_COLS].drop_duplicates(["player_name", "season", "week"]),
                          on=["player_name", "season", "week"], how="left",
                          validate="m:1", indicator=True)
        rate = (mg["_merge"] == "both").mean()
        print(f"[{m}] feature join rate: {rate:.4f} (n={len(direct)})", flush=True)
        assert rate >= 0.99, f"feature join rate too low for {m}"
        dev[m] = mg[mg["_merge"] == "both"].reset_index(drop=True)
    train = {m: ev[(ev["period"] == "train") & (ev["market"] == m)].reset_index(drop=True)
             for m in MARKETS}

    results, locked, pred_rows = {}, {}, {}
    for market in MARKETS:
        tr, dv = train[market], dev[market]
        y = dv["actual_yards"].to_numpy(float)
        print(f"\n===== {market} (n={len(dv)}) =====", flush=True)

        # ---- M0: reproduce frozen Model D read-only, verify bit-identical ----
        A = fit_A(tr, sel[market]["a_alpha"])
        B = fit_B(tr, sel[market]["b_params"])
        C = fit_C(tr)
        m0 = (pred_A(A, dv) + pred_B(B, dv) + pred_C(C, dv)) / 3.0
        m0_mae = mae(y, m0)
        exp = EXPECTED_D_DEV_MAE[market]
        assert abs(m0_mae - exp) < 1e-6, (
            f"M0 reproduction mismatch for {market}: got {m0_mae}, frozen 001 recorded {exp}")
        print(f"[{market}] M0 reproduced bit-identical (dev MAE {m0_mae:.4f})", flush=True)

        # ---- M1: contrast + Ridge ----
        X1 = dv[M1_ORDER[1:]].to_numpy(float)
        X1 = np.column_stack([m0, X1])
        best = {"mae": np.inf}
        for alpha in RIDGE_ALPHAS:
            mdl = fit_ridge(X1, y, alpha)
            p = pred_ridge(mdl, X1)
            m = mae(y, p)
            print(f"[{market}] M1 Ridge alpha={alpha}: dev MAE {m:.4f}", flush=True)
            if m < best["mae"]:
                best = {"mae": m, "alpha": alpha, "model": mdl, "pred": p}
        m1_cv = cv_mae_ridge(X1, y, best["alpha"])
        print(f"[{market}] M1 locked alpha={best['alpha']} "
              f"in-sample {best['mae']:.4f} | 5-fold CV {m1_cv:.4f} (M0 {m0_mae:.4f})", flush=True)
        with open(f"{EXP}/models/M1_{market}_fitted.pkl", "wb") as f:
            pickle.dump({"alpha": best["alpha"], "model": best["model"],
                         "order": M1_ORDER}, f)

        # ---- M2: Kalman ----
        prior_s, prior_e = positional_priors(hist, market)
        print(f"[{market}] positional priors: share={prior_s:.4f} eff={prior_e:.4f}", flush=True)
        bundles = build_player_bundles(hist, ev, market)
        print(f"[{market}] walking {len(bundles)} players...", flush=True)
        qs, qe, rr, ll = fit_kalman(bundles, prior_s, prior_e)
        print(f"[{market}] M2 locked: q_share={qs:.6f} q_eff={qe:.6f} r={rr:.6f} (LL={ll:.1f})",
              flush=True)
        _, m2_pred, m2_act = kalman_run(bundles, qs, qe, rr, prior_s, prior_e)
        # map predictions back to dev rows via bundle keys
        key2pred = {}
        i = 0
        for b in bundles:
            for k in b["keys"]:
                key2pred[k] = m2_pred[i]
                i += 1
        dv_keys = list(zip(dv["player_name"], dv["season"], dv["week"]))
        p2 = np.array([key2pred[k] for k in dv_keys])
        assert len(p2) == len(dv)
        # dev MAE on the full evaluated set (incl. namesake duplicates, as for M0/M1)
        m2_mae = mae(y, p2)
        m2_cv = cv_mae_kalman(bundles, prior_s, prior_e)
        print(f"[{market}] M2 in-sample dev MAE {m2_mae:.4f} | player-5fold CV {m2_cv:.4f} "
              f"(M0 {m0_mae:.4f})", flush=True)
        with open(f"{EXP}/models/M2_{market}_params.json", "w") as f:
            json.dump({"q_share": qs, "q_eff": qe, "r": rr,
                       "prior_share": prior_s, "prior_eff": prior_e,
                       "V0_share": V0_SHARE, "V0_eff": V0_EFF,
                       "dev_loglik": ll, "market_def": MKT_DEF[market]}, f, indent=1)

        # ---- slice diagnostics ----
        in_ts = (dv["in_transfer_stint"] == 1.0).to_numpy()
        sg = dv["stint_games"].to_numpy()
        mag = np.abs(dv[CONTRAST_MAG[market]].to_numpy(float))
        hi_thr = np.quantile(mag, 0.9)
        slices = {
            "overall": np.ones(len(dv), bool),
            "transfer_stint": in_ts,
            "stint_1_3": in_ts & (sg <= 2),
            "stint_4_6": in_ts & (sg >= 3) & (sg <= 5),
            "high_contrast": mag >= hi_thr,
            "non_transfer": ~in_ts,
        }
        preds = {"M0": m0, "M1": best["pred"], "M2": p2}
        diag = {}
        for rung in ("M0", "M1", "M2"):
            diag[rung] = {}
            for sname, mask in slices.items():
                n = int(mask.sum())
                diag[rung][sname] = {"mae": mae(y[mask], preds[rung][mask]) if n else None,
                                     "n": n}
        results[market] = {"n": len(dv), "m0_mae": m0_mae, "diag": diag,
                           "m1": {"alpha": best["alpha"], "dev_mae_in_sample": best["mae"],
                                  "dev_mae_cv5": m1_cv},
                           "m2": {"q_share": qs, "q_eff": qe, "r": rr,
                                  "dev_mae_in_sample": m2_mae, "dev_mae_cv5": m2_cv}}
        locked[market] = {
            "M1": {"alpha": best["alpha"], "order": M1_ORDER},
            "M2": {"q_share": qs, "q_eff": qe, "r": rr,
                   "prior_share": prior_s, "prior_eff": prior_e},
        }

        pr = dv[["player_name", "team", "opponent", "season", "week", "actual_yards",
                 "in_transfer_stint"] + M1_ORDER[1:]].copy()
        pr["market"] = market
        pr["pred_M0"] = m0
        pr["pred_M1"] = best["pred"]
        pr["pred_M2"] = p2
        pred_rows[market] = pr

    pd.concat(pred_rows, ignore_index=True).to_parquet(
        f"{EXP}/data/dev_predictions.parquet", index=False)
    json.dump(locked, open(f"{EXP}/LOCKED_PARAMETERS.json", "w"), indent=1)
    print(f"\ndev predictions + locked params written ({time.time()-t0:.0f}s)", flush=True)
    json.dump(results, open(f"{EXP}/data/dev_results.json", "w"), indent=1)
    return results


if __name__ == "__main__":
    main()
