#!/usr/bin/env python3
"""Experiment 002 runner: ladder M0-M12, dev selection, single locked-test eval.

Usage:
  run_experiment_002.py --phase dev    # fit on train, select on dev. Test untouched.
  run_experiment_002.py --phase test   # requires PROTOCOL_FROZEN + dev outputs; single eval.

Model D procedure is IDENTICAL to experiments/player_props_projection/scripts/
run_experiment_001.py (copied here with parametrized feature lists; the 001
file is untouched):
  A: two-stage Ridge opportunity x efficiency, alpha dev-selected {0.1,1,10,100}
  B: HistGradientBoostingRegressor direct yards, 8-combo grid dev-selected
  C: quantile GBM P25/median/P75, fixed params (lr=0.1, max_depth=3,
     max_iter=300, min_samples_leaf=20, random_state=7)
  D = equal-weight mean of A/B/C point projections.

Ladder (protocol section 6):
  M0  Model D exactly (frozen)
  M1  D + B (ctx_*)            M2  D + C (oppd_*)      M3  D + D1 (envs_*)
  M4  D + E (pace_*)           M5  D + F (opp2_*)
  M6  D + position quality (pass->qb_eff, rush->ruq_*, rec->rq_*)
  M7  D + full qb_* (qb_eff + qb_ctx) for ALL markets
  M8  D + J (ol_*)             M9  D + L (inj_*)       M10 D + D2 (envf_*)
  M11 D + union of families selected on dev only (section 7 rule)
  M12 regularized all-family model: mean(RidgeCV, HistGBM) on ALL0 + all new
      features; evaluated on test ONLY if the dev gate passes.

Stage assignment (protocol section 6):
  context (B,C,D1,D2,E,J,L,O) -> A stage 1, A stage 2, B/C pool
  opportunity (F)             -> A stage 1, B/C pool
  quality (G,H,qb_eff)        -> A stage 2, B/C pool
  qb_ctx, recency (P)         -> B/C pool only
  (O/P/Q have no standalone ladder rung per the frozen protocol; they enter
  via M12's all-family set.)

Win bar (protocol section 9): >=5% pooled MAE reduction vs M0 in >=2/3
markets; no market worse than -2%; >=2% in 2023 AND 2024 individually per
claimed market; 95% paired bootstrap CI excludes zero.
"""
import argparse
import json
import os
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, RidgeCV
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingRegressor

REPO = os.path.expanduser("~/workspace/nfl-model")
EXP = os.path.join(REPO, "experiments/props_experiment_002")
TABLE = os.path.join(EXP, "data/extended_features_2018_2024.parquet")

RNG = np.random.default_rng(1337)
BOOT = 2000
A_ALPHAS = [0.1, 1.0, 10.0, 100.0]
B_GRID = [{"learning_rate": lr, "max_depth": md, "max_iter": mi}
          for lr in (0.05, 0.1) for md in (3, 5) for mi in (200, 500)]
C_PARAMS = dict(loss="quantile", learning_rate=0.1, max_depth=3,
                max_iter=300, min_samples_leaf=20, random_state=7)
MARKETS = ["pass_yards", "rush_yards", "receiving_yards"]
MARKET_YARDS_COL = {"pass_yards": "trail_pass_yards_ewma",
                    "rush_yards": "trail_rush_yards_ewma",
                    "receiving_yards": "trail_receiving_yards_ewma"}
MARKET_OPP_COL = {"pass_yards": "trail_pass_att_ewma",
                  "rush_yards": "trail_rush_att_ewma",
                  "receiving_yards": "trail_targets_ewma"}
MIN_N = {"pass_yards": 700, "rush_yards": 1000, "receiving_yards": 2500}

# ---- frozen 001 feature lists (verbatim) ----
OPP0 = [
    "trail_targets_ewma", "trail_rush_att_ewma", "trail_pass_att_ewma",
    "trail_target_share_ewma", "trail_rush_share_ewma", "trail_air_share_ewma",
    "trail_team_targets_ewma", "trail_team_pass_att_ewma", "trail_team_rush_att_ewma",
    "trail_rz_targets_ewma", "trail_rz_carries_ewma", "trail_air_yards_ewma",
    "trail_games",
]
EFF0 = [
    "trail_ypt_ewma", "trail_ypc_ewma", "trail_ypa_ewma",
    "trail_comp_rate_ewma", "trail_yac_pt_ewma",
]
YARDS0 = ["trail_pass_yards_ewma", "trail_rush_yards_ewma", "trail_receiving_yards_ewma"]
OPPF0 = ["opp_trail_pass_allowed_ewma", "opp_trail_rush_allowed_ewma"]
ENV0 = ["spread_line", "total_line", "is_home", "team_spread",
        "team_implied_total", "opp_implied_total"]
ALL0 = OPP0 + EFF0 + YARDS0 + OPPF0 + ENV0

# ---- Experiment 002 feature families ----
FAM = {
    "B": ["ctx_team_off_epa", "ctx_team_off_pass_epa", "ctx_team_off_rush_epa",
          "ctx_team_off_sr", "ctx_elo_adv"],
    "C": ["oppd_def_epa", "oppd_def_pass_epa", "oppd_def_rush_epa", "oppd_def_sr"],
    "D1": ["envs_dome", "envs_team_pts_trail", "envs_opp_pts_allowed_trail"],
    "D2": ["envf_days_rest", "envf_rest_diff", "envf_short_week",
           "envf_long_rest", "envf_div_game"],
    "E": ["pace_team_plays", "pace_combined", "pace_neutral_pass_rate"],
    "F": ["opp2_snap_pct", "opp2_snap_trend"],
    "RQ": ["rq_adot", "rq_yac_per_rec", "rq_drop_pct", "rq_broken_tackles",
           "rq_ngs_separation", "rq_ngs_xYAC"],
    "RUQ": ["ruq_ybc_per_att", "ruq_yac_per_att", "ruq_broken_tackles",
            "ruq_explosive_rate", "ruq_stuff_rate", "ruq_goal_line_carries"],
    "QBE": ["qb_epa_trail", "qb_cpoe_trail", "qb_adot_trail"],
    "QBX": ["qb_pressure_trail", "qb_changed"],
    "J": ["ol_team_pressure_allowed", "ol_opp_sack_rate"],
    "L": ["inj_player_status", "inj_team_out_share", "inj_ol_out"],
    "O": ["exp_career_games", "exp_rookie", "exp_second_year"],
    "P": ["rec2_yards_hl1", "rec2_yards_hl8", "rec2_opp_hl1"],
    "Q": ["xq_xYpt"],
}
CONTEXT = FAM["B"] + FAM["C"] + FAM["D1"] + FAM["D2"] + FAM["E"] + FAM["J"] + FAM["L"] + FAM["O"]
POSQ = {"pass_yards": FAM["QBE"], "rush_yards": FAM["RUQ"],
        "receiving_yards": FAM["RQ"]}
ALL_NEW = [c for f in FAM.values() for c in f]
RUNGS = ["M0", "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9", "M10",
         "M11", "M12"]
RUNG_FAM = {"M1": "B", "M2": "C", "M3": "D1", "M4": "E", "M5": "F",
            "M6": "Qpos", "M7": "QB", "M8": "J", "M9": "L", "M10": "D2"}


def rung_features(rung, market, m11_sel=None):
    """Return (stage1_add, stage2_add, pool_add) for a ladder rung."""
    s1, s2, pool = [], [], []
    if rung == "M0":
        pass
    elif rung == "M1":
        s1, s2, pool = FAM["B"], FAM["B"], FAM["B"]
    elif rung == "M2":
        s1, s2, pool = FAM["C"], FAM["C"], FAM["C"]
    elif rung == "M3":
        s1, s2, pool = FAM["D1"], FAM["D1"], FAM["D1"]
    elif rung == "M4":
        s1, s2, pool = FAM["E"], FAM["E"], FAM["E"]
    elif rung == "M5":
        s1, pool = FAM["F"], FAM["F"]
    elif rung == "M6":
        s2, pool = POSQ[market], POSQ[market]
    elif rung == "M7":
        s2, pool = FAM["QBE"], FAM["QBE"] + FAM["QBX"]
    elif rung == "M8":
        s1, s2, pool = FAM["J"], FAM["J"], FAM["J"]
    elif rung == "M9":
        s1, s2, pool = FAM["L"], FAM["L"], FAM["L"]
    elif rung == "M10":
        s1, s2, pool = FAM["D2"], FAM["D2"], FAM["D2"]
    elif rung == "M11":
        for fam in m11_sel[market]:
            if fam == "F":
                s1 += FAM["F"]; pool += FAM["F"]
            elif fam == "Qpos":
                s2 += POSQ[market]; pool += POSQ[market]
            elif fam == "QB":
                s2 += FAM["QBE"]; pool += FAM["QBE"] + FAM["QBX"]
            else:  # context families B,C,D1,D2,E,J,L
                s1 += FAM[fam]; s2 += FAM[fam]; pool += FAM[fam]
    else:
        raise ValueError(rung)
    # dedupe, preserve order
    return (list(dict.fromkeys(s1)), list(dict.fromkeys(s2)),
            list(dict.fromkeys(pool)))


def mae(y, p):
    return float(np.mean(np.abs(y - p)))


# ---- Model D components, identical procedure to run_experiment_001.py ----
def fit_A(tr, opp_feats, eff_feats, alpha):
    s1, s2 = StandardScaler(), StandardScaler()
    att = tr["actual_att"].to_numpy(float)
    r1 = Ridge(alpha=alpha).fit(s1.fit_transform(tr[opp_feats].to_numpy(float)), att)
    eff = tr["actual_yards"].to_numpy(float) / np.maximum(att, 1e-6)
    r2 = Ridge(alpha=alpha).fit(s2.fit_transform(tr[eff_feats].to_numpy(float)), eff)
    return (s1, r1, s2, r2, opp_feats, eff_feats)


def pred_A(model, df):
    s1, r1, s2, r2, of, ef = model
    o = np.maximum(r1.predict(s1.transform(df[of].to_numpy(float))), 0.0)
    e = r2.predict(s2.transform(df[ef].to_numpy(float)))
    return np.maximum(o * e, 0.0)


def fit_B(tr, pool_feats, params):
    m = HistGradientBoostingRegressor(random_state=11, **params)
    return (m.fit(tr[pool_feats].to_numpy(float),
                  tr["actual_yards"].to_numpy(float)), pool_feats)


def pred_B(model, df):
    m, pf = model
    return np.maximum(m.predict(df[pf].to_numpy(float)), 0.0)


def fit_C(tr, pool_feats):
    X = tr[pool_feats].to_numpy(float)
    y = tr["actual_yards"].to_numpy(float)
    return ({q: HistGradientBoostingRegressor(quantile=q, **C_PARAMS).fit(X, y)
             for q in (0.25, 0.5, 0.75)}, pool_feats)


def pred_C(model, df, q=0.5):
    ms, pf = model
    return np.maximum(ms[q].predict(df[pf].to_numpy(float)), 0.0)


def fit_D_rung(tr, dv, market, rung, m11_sel=None, fixed_alpha=None,
               fixed_b_params=None):
    """Fit A/B/C for one rung+market on train; dev-select alpha and B params
    unless fixed_* are given (test phase: use dev-selected hyperparams)."""
    s1a, s2a, pa = rung_features(rung, market, m11_sel)
    opp_f = OPP0 + s1a
    eff_f = EFF0 + s2a
    pool_f = ALL0 + pa

    if fixed_alpha is not None:
        A = fit_A(tr, opp_f, eff_f, fixed_alpha)
        a_alpha = fixed_alpha
    else:
        ydv = dv["actual_yards"].to_numpy(float)
        a_cands = {}
        for a in A_ALPHAS:
            m = fit_A(tr, opp_f, eff_f, a)
            a_cands[a] = (m, mae(ydv, pred_A(m, dv)))
        a_alpha = min(a_cands, key=lambda a: a_cands[a][1])
        A = a_cands[a_alpha][0]

    if fixed_b_params is not None:
        B = fit_B(tr, pool_f, fixed_b_params)
        b_params = fixed_b_params
    else:
        ydv = dv["actual_yards"].to_numpy(float)
        b_cands = {}
        for i, gp in enumerate(B_GRID):
            m = fit_B(tr, pool_f, gp)
            b_cands[i] = (m, mae(ydv, pred_B(m, dv)), gp)
        b_key = min(b_cands, key=lambda i: b_cands[i][1])
        B, b_params = b_cands[b_key][0], b_cands[b_key][2]

    C = fit_C(tr, pool_f)
    dev = None
    if dv is not None:
        pA, pB, pC = pred_A(A, dv), pred_B(B, dv), pred_C(C, dv)
        dev = {"pA": pA, "pB": pB, "pC": pC, "pD": (pA + pB + pC) / 3.0,
               "p25": pred_C(C, dv, 0.25), "p75": pred_C(C, dv, 0.75)}
    return {"A": A, "B": B, "C": C, "a_alpha": a_alpha, "b_params": b_params,
            "feats": {"opp": opp_f, "eff": eff_f, "pool": pool_f}, "dev": dev}


def fit_M12(tr, dv, market, fixed_b_params=None):
    """Regularized all-family model: mean(RidgeCV, HistGBM) on ALL0+ALL_NEW."""
    pool_f = ALL0 + ALL_NEW
    X = tr[pool_f].to_numpy(float)
    y = tr["actual_yards"].to_numpy(float)
    s = StandardScaler()
    rc = RidgeCV(alphas=np.logspace(-1, 3, 10), cv=5).fit(s.fit_transform(X), y)
    if fixed_b_params is not None:
        B = HistGradientBoostingRegressor(
            random_state=11, **fixed_b_params).fit(X, y)
        b_params = fixed_b_params
        dev_pred = None
    else:
        ydv = dv["actual_yards"].to_numpy(float)
        b_cands = {}
        for i, gp in enumerate(B_GRID):
            m = HistGradientBoostingRegressor(random_state=11, **gp).fit(X, y)
            b_cands[i] = (m, mae(ydv, np.maximum(
                m.predict(dv[pool_f].to_numpy(float)), 0.0)), gp)
        b_key = min(b_cands, key=lambda i: b_cands[i][1])
        B, b_params = b_cands[b_key][0], b_cands[b_key][2]
        dev_pred = None  # set below

    def pred(df):
        Xs = s.transform(df[pool_f].to_numpy(float))
        pr = np.maximum(rc.predict(Xs), 0.0)
        pb = np.maximum(B.predict(df[pool_f].to_numpy(float)), 0.0)
        return (pr + pb) / 2.0

    if fixed_b_params is None:
        dev_pred = pred(dv)
    return {"pred": pred, "b_params": b_params,
            "dev_pred": dev_pred, "feats": pool_f}


def load(phase):
    t = pd.read_parquet(TABLE)
    ev = t[(t["eligible_hist"] == 1) & (t["played_role"] == 1)].copy()
    periods = ("train", "dev") if phase == "dev" else ("train", "dev", "test")
    return {p: {m: ev[(ev["period"] == p) & (ev["market"] == m)].reset_index(drop=True)
                for m in MARKETS} for p in periods}


def dev_phase():
    t0 = time.time()
    D = load("dev")
    dev_mae, fitted = {}, {}
    for rung in ["M0", "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9", "M10"]:
        dev_mae[rung], fitted[rung] = {}, {}
        for market in MARKETS:
            tr, dv = D["train"][market], D["dev"][market]
            F = fit_D_rung(tr, dv, market, rung)
            fitted[rung][market] = F
            ydv = dv["actual_yards"].to_numpy(float)
            dev_mae[rung][market] = {
                "n": len(dv), "D": mae(ydv, F["dev"]["pD"]),
                "A": mae(ydv, F["dev"]["pA"]), "B": mae(ydv, F["dev"]["pB"]),
                "C": mae(ydv, F["dev"]["pC"]),
                "a_alpha": F["a_alpha"], "b_params": F["b_params"]}
        line = " ".join(f"{m}={dev_mae[rung][m]['D']:.2f}" for m in MARKETS)
        print(f"[{rung}] dev D MAE: {line}", flush=True)

    # ---- M11 family selection (section 7 rule, dev only) ----
    # (family key, markets where tested, rung that tests it).
    # Qpos = position-specific quality (RQ/RUQ/QBE via M6); QB = full qb
    # family via M7. Mapped to M11 keys below.
    fam_tests = [
        ("B", MARKETS, "M1"), ("C", MARKETS, "M2"), ("D1", MARKETS, "M3"),
        ("E", MARKETS, "M4"), ("F", MARKETS, "M5"),
        ("RQ", ["receiving_yards"], "M6"), ("RUQ", ["rush_yards"], "M6"),
        ("QBE", ["pass_yards"], "M6"), ("QB", MARKETS, "M7"),
        ("J", MARKETS, "M8"), ("L", MARKETS, "M9"), ("D2", MARKETS, "M10"),
    ]
    m11_sel = {m: [] for m in MARKETS}
    for fam, mkts, rung in fam_tests:
        worst_reg = max(
            (dev_mae[rung][m]["D"] - dev_mae["M0"][m]["D"]) /
            dev_mae["M0"][m]["D"] for m in mkts)
        for m in mkts:
            imp = (dev_mae["M0"][m]["D"] - dev_mae[rung][m]["D"]) / \
                dev_mae["M0"][m]["D"]
            if imp >= 0.01 and worst_reg <= 0.01:
                key = "Qpos" if fam in ("RQ", "RUQ", "QBE") else fam
                if key not in m11_sel[m]:
                    m11_sel[m].append(key)
    print("M11 selection:", json.dumps(m11_sel), flush=True)
    dev_mae["M11"], fitted["M11"] = {}, {}
    for market in MARKETS:
        tr, dv = D["train"][market], D["dev"][market]
        F = fit_D_rung(tr, dv, market, "M11", m11_sel)
        fitted["M11"][market] = F
        ydv = dv["actual_yards"].to_numpy(float)
        dev_mae["M11"][market] = {"n": len(dv), "D": mae(ydv, F["dev"]["pD"]),
                                  "a_alpha": F["a_alpha"], "b_params": F["b_params"]}
    print(f"[M11] dev D MAE: " +
          " ".join(f"{m}={dev_mae['M11'][m]['D']:.2f}" for m in MARKETS), flush=True)

    # ---- M12 dev gate ----
    m12 = {}
    m12_dev = {}
    m12_gate = False
    for market in MARKETS:
        tr, dv = D["train"][market], D["dev"][market]
        F = fit_M12(tr, dv, market)
        m12[market] = F
        ydv = dv["actual_yards"].to_numpy(float)
        m12_dev[market] = {"n": len(dv), "pred": mae(ydv, F["dev_pred"]),
                           "b_params": F["b_params"]}
    imps = [(dev_mae["M0"][m]["D"] - m12_dev[m]["pred"]) / dev_mae["M0"][m]["D"]
            for m in MARKETS]
    regs = [(m12_dev[m]["pred"] - dev_mae["M0"][m]["D"]) / dev_mae["M0"][m]["D"]
            for m in MARKETS]
    m12_gate = (max(imps) >= 0.01) and (max(regs) <= 0.01)
    print(f"[M12] dev MAE: " +
          " ".join(f"{m}={m12_dev[m]['pred']:.2f}" for m in MARKETS) +
          f" | gate={'PASS' if m12_gate else 'FAIL'}", flush=True)

    # ---- uncertainty calibration on dev (protocol section 10, a-c) ----
    calib_dev = {}
    for rung in ["M0", "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9",
                 "M10", "M11"]:
        calib_dev[rung] = {}
        for market in MARKETS:
            dv = D["dev"][market]
            ydv = dv["actual_yards"].to_numpy(float)
            F = fitted[rung][market]
            calib_dev[rung][market] = calib_metrics(
                ydv, F["dev"]["p25"], F["dev"]["pC"], F["dev"]["p75"])
    out = {"dev_mae": dev_mae,
           "m11_selection": m11_sel,
           "calibration_dev": calib_dev,
           "m12_dev": {m: {k: v for k, v in m12_dev[m].items() if k != "pred"}
                       for m in MARKETS},
           "m12_gate": m12_gate,
           "elapsed_s": round(time.time() - t0, 1)}
    json.dump(out, open(f"{EXP}/data/experiment_002_dev.json", "w"), indent=1,
              default=str)
    print("DEV PHASE COMPLETE — test slice untouched.")


def calib_metrics(y, p25, p50, p75, dev_cutoffs=None):
    """Uncertainty calibration metrics (protocol section 10)."""
    rel_w = (p75 - p25) / np.maximum(p50, 1.0)
    ae = np.abs(y - p50)
    cov = float(np.mean((y >= p25) & (y <= p75)))
    out = {"coverage_p25_p75": cov, "n": len(y)}
    # (b) MAE by width tercile
    t1, t2 = np.percentile(rel_w, [100 / 3, 200 / 3])
    out["width_cutoffs"] = [float(t1), float(t2)]
    for i, (lo, hi) in enumerate([(-np.inf, t1), (t1, t2), (t2, np.inf)]):
        m = (rel_w > lo) & (rel_w <= hi)
        out[f"tercile{i + 1}_mae"] = float(np.mean(ae[m])) if m.sum() else None
        out[f"tercile{i + 1}_n"] = int(m.sum())
    # (c) production-rule labels from dev cutoffs
    if dev_cutoffs is not None:
        c33, c67 = dev_cutoffs
        lab = np.where(rel_w <= c33, "High", np.where(rel_w <= c67, "Medium", "Low"))
        per = {}
        for L in ("High", "Medium", "Low"):
            m = lab == L
            per[L] = {"mae": float(np.mean(ae[m])) if m.sum() else None,
                      "n": int(m.sum()),
                      "coverage": float(np.mean((y[m] >= p25[m]) & (y[m] <= p75[m])))
                      if m.sum() else None}
        out["labels"] = per
        mh, ml = per["High"]["mae"], per["Low"]["mae"]
        out["labels_meaningful"] = (
            mh is not None and ml is not None and ml > 0 and
            (ml - mh) / ml >= 0.10 and 0.40 <= cov <= 0.60)
    return out


def test_phase():
    assert os.path.exists(os.path.join(EXP, "PROTOCOL_FROZEN")), \
        "protocol not frozen — refusing test evaluation"
    dev_path = f"{EXP}/data/experiment_002_dev.json"
    assert os.path.exists(dev_path), "run --phase dev first"
    dev_out = json.load(open(dev_path))
    m11_sel = dev_out["m11_selection"]
    m12_gate = dev_out["m12_gate"]
    t0 = time.time()
    D = load("test")

    test_mae, test_rows, calib = {}, [], {}
    # refit every evaluated rung on train (dev selections frozen from dev phase)
    rungs_eval = ["M0", "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9",
                  "M10", "M11"] + (["M12"] if m12_gate else [])
    for rung in rungs_eval:
        test_mae[rung] = {}
        for market in MARKETS:
            tr, te = D["train"][market], D["test"][market]
            yte = te["actual_yards"].to_numpy(float)
            if rung == "M12":
                bp = dev_out["m12_dev"][market]["b_params"]
                F = fit_M12(tr, None, market, fixed_b_params=bp)
                pD = F["pred"](te)
                p25 = p75 = p50 = None
            else:
                dm = dev_out["dev_mae"][rung][market]
                F = fit_D_rung(tr, None, market, rung,
                               m11_sel if rung == "M11" else None,
                               fixed_alpha=dm["a_alpha"],
                               fixed_b_params=dm["b_params"])
                pA, pB = pred_A(F["A"], te), pred_B(F["B"], te)
                p50 = pred_C(F["C"], te)
                p25, p75 = pred_C(F["C"], te, 0.25), pred_C(F["C"], te, 0.75)
                pD = (pA + pB + p50) / 3.0
            r = {"n": len(te),
                 "n_2023": int((te["season"] == 2023).sum()),
                 "n_2024": int((te["season"] == 2024).sum()),
                 "D": mae(yte, pD)}
            # per-season MAE (win-bar condition 3)
            seas = {}
            for s in (2023, 2024):
                idx = (te["season"] == s).to_numpy()
                seas[str(s)] = {"D": mae(yte[idx], pD[idx]), "n": int(idx.sum())}
            r["by_season"] = seas
            # paired bootstrap CI of (M0 - rung) MAE difference
            if rung != "M0":
                m0d = test_mae["M0"][market]["_predD"]
                diff = np.abs(yte - m0d) - np.abs(yte - pD)
                bs = np.array([np.mean(RNG.choice(diff, size=len(diff), replace=True))
                               for _ in range(BOOT)])
                r["bootstrap_ci_M0_minus_rung"] = [
                    float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
            r["_predD"] = pD
            # experience / opportunity buckets
            exp_lab = np.where(te["exp_rookie"] == 1, "rookie",
                        np.where(te["exp_second_year"] == 1, "second_year", "veteran"))
            eb = {}
            for L in ("rookie", "second_year", "veteran"):
                m = exp_lab == L
                eb[L] = {"mae": float(np.mean(np.abs(yte[m] - pD[m]))) if m.sum() else None,
                         "n": int(m.sum())}
            r["by_experience"] = eb
            oc = te[MARKET_OPP_COL[market]].to_numpy(float)
            q1, q2 = np.percentile(oc, [100 / 3, 200 / 3])
            ob = {}
            for i, (lo, hi) in enumerate([(-np.inf, q1), (q1, q2), (q2, np.inf)]):
                m = (oc > lo) & (oc <= hi)
                ob[f"opp_tercile{i + 1}"] = {
                    "mae": float(np.mean(np.abs(yte[m] - pD[m]))) if m.sum() else None,
                    "n": int(m.sum())}
            r["by_opportunity"] = ob
            test_mae[rung][market] = r
            # calibration (needs quantiles; M12 excluded).
            # §10c: apply dev p33/p67 relative-width cutoffs to test.
            if rung != "M12":
                cutoffs = tuple(
                    dev_out["calibration_dev"][rung][market]["width_cutoffs"])
                calib.setdefault(rung, {})[market] = calib_metrics(
                    yte, p25, p50, p75, cutoffs)
            df = te[["player_name", "team", "opponent", "season", "week",
                     "position", "actual_yards"]].copy()
            df["market"] = market
            df["rung"] = rung
            df["pred_D"] = pD
            if rung != "M12":
                df["pred_p25"], df["pred_p75"] = p25, p75
            test_rows.append(df)
        line = " ".join(
            f"{m}={test_mae[rung][m]['D']:.2f}" for m in MARKETS)
        print(f"[{rung}] test D MAE: {line}", flush=True)

    # win-bar evaluation (section 9)
    verdict = {}
    for rung in rungs_eval:
        if rung == "M0":
            continue
        per_mkt = {}
        for m in MARKETS:
            b = test_mae["M0"][m]["D"]
            v = test_mae[rung][m]["D"]
            rel = (b - v) / b
            s23 = (test_mae["M0"][m]["by_season"]["2023"]["D"] -
                   test_mae[rung][m]["by_season"]["2023"]["D"]) / \
                test_mae["M0"][m]["by_season"]["2023"]["D"]
            s24 = (test_mae["M0"][m]["by_season"]["2024"]["D"] -
                   test_mae[rung][m]["by_season"]["2024"]["D"]) / \
                test_mae["M0"][m]["by_season"]["2024"]["D"]
            ci = test_mae[rung][m]["bootstrap_ci_M0_minus_rung"]
            per_mkt[m] = {"rel_improvement": rel, "s2023": s23, "s2024": s24,
                          "ci_excludes_zero": ci[0] > 0,
                          "n_ok": test_mae[rung][m]["n"] >= MIN_N[m]}
        winners = [m for m in MARKETS
                   if per_mkt[m]["rel_improvement"] >= 0.05
                   and per_mkt[m]["s2023"] >= 0.02
                   and per_mkt[m]["s2024"] >= 0.02
                   and per_mkt[m]["ci_excludes_zero"]
                   and per_mkt[m]["n_ok"]]
        no_big_reg = all(per_mkt[m]["rel_improvement"] >= -0.02 for m in MARKETS)
        verdict[rung] = {"per_market": per_mkt,
                         "clears_bar": len(winners) >= 2 and no_big_reg,
                         "winning_markets": winners}

    out = {"test_mae": test_mae, "calibration": calib, "win_bar": verdict,
           "m11_selection": m11_sel, "m12_gate": m12_gate,
           "elapsed_s": round(time.time() - t0, 1)}
    # strip bulky prediction arrays before JSON dump
    for rung in test_mae:
        for m in MARKETS:
            test_mae[rung][m].pop("_predD", None)
    json.dump(out, open(f"{EXP}/data/experiment_002_test.json", "w"), indent=1,
              default=str)
    pd.concat(test_rows, ignore_index=True).to_parquet(
        f"{EXP}/data/experiment_002_test_predictions.parquet", index=False)
    print("TEST EVALUATION COMPLETE (single pass).")
    for rung, v in verdict.items():
        print(f"[{rung}] clears_bar={v['clears_bar']} "
              f"winners={v['winning_markets']}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["dev", "test"], required=True)
    args = ap.parse_args()
    if args.phase == "dev":
        dev_phase()
    else:
        test_phase()


if __name__ == "__main__":
    main()
