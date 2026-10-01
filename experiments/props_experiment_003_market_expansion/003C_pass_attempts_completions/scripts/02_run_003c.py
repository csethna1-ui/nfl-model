#!/usr/bin/env python3
"""Props Experiment 003C runner: pass attempts ladder M0-M3 + hierarchical
completions leg (C0 vs C1).

Usage:
  02_run_003c.py --phase dev    # fit on train, select hyperparams on dev. Test untouched.
  02_run_003c.py --phase test   # requires frozen prereg + dev outputs; single eval.

Binding discipline (frozen prereg 2026-10-01, shared protocol):
  - Splits: train 2018-2020 / dev 2021-2022 / locked test 2023-2024.
  - Fixed ladder, no family selection, fit ONCE.
  - spread/total/implied features EXCLUDED everywhere.
  - Completions evaluated ONLY downstream of attempts (C1 vs C0), never standalone.
  - Win bar (count targets): >=5% pooled relative MAE reduction vs baseline,
    >=2% in 2023 AND in 2024 individually, 95% paired bootstrap CI excludes zero.
    For C1, the "baseline" is C0 (the naive downstream).

Model procedure per rung (shared protocol 002 section 7 hyperparameter
procedure): Ridge (alpha in {0.1, 1, 10, 100}, dev-selected) +
HistGradientBoostingRegressor (8-combo grid, dev-selected); rung point
projection = equal-weight mean of the two. Seeds: 1337 (bootstrap),
GBM random_state=11 (002 precedent).

Rung feature sets (frozen prereg section 4):
  M0: trailing attempts EWMA (trail_pass_att_ewma), NaN->0.
  M1 (volume model): expected plays x pass rate x ELO-diff script x
      QB-identity/role context.
  M2: M1 + NGS passing family (trailing only).
  M3: M1 + team/matchup/game-context families (B, C, D1, D2, E, L) +
      QB efficiency trails.

Completions leg (frozen prereg section 4):
  feeder: M1's attempts projection (predetermined, same for C0 and C1).
  C0: feeder x trailing completion% (trail_comp_rate_ewma).
  C1: feeder x modeled completion probability, features =
      [ngs_xcomp_trail, ngs_cpoe_trail, ngs_aggro_trail, qb_adot_trail,
       qb_pressure_trail]; target = actual_comp / actual_att with
      sample_weight = actual_att; output clipped to [0.05, 0.98].
"""
import argparse
import json
import os
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingRegressor

REPO = os.path.expanduser("~/workspace/nfl-model")
EXP = os.path.join(REPO, "experiments/props_experiment_003_market_expansion/"
                          "003C_pass_attempts_completions")
TABLE = os.path.join(EXP, "data/table_003c.parquet")

RNG = np.random.default_rng(1337)
BOOT = 2000
A_ALPHAS = [0.1, 1.0, 10.0, 100.0]
B_GRID = [{"learning_rate": lr, "max_depth": md, "max_iter": mi}
          for lr in (0.05, 0.1) for md in (3, 5) for mi in (200, 500)]
MIN_N = 700

NGS_FAM = ["ngs_ttt_trail", "ngs_aggro_trail", "ngs_iay_trail",
           "ngs_ayts_trail", "ngs_xcomp_trail", "ngs_cpoe_trail"]

M1_FEATS = ["pace_team_plays", "pace_combined", "pace_neutral_pass_rate",
            "ctx_elo_adv", "trail_pass_att_ewma",
            "qb_changed", "exp_rookie", "exp_second_year",
            "exp_career_games", "trail_games"]
M3_ADD = ["ctx_team_off_epa", "ctx_team_off_pass_epa", "ctx_team_off_rush_epa",
          "ctx_team_off_sr",
          "oppd_def_epa", "oppd_def_pass_epa", "oppd_def_rush_epa",
          "oppd_def_sr",
          "envs_dome", "envs_team_pts_trail", "envs_opp_pts_allowed_trail",
          "envf_days_rest", "envf_rest_diff", "envf_short_week",
          "envf_long_rest", "envf_div_game",
          "inj_player_status", "inj_team_out_share", "inj_ol_out",
          "qb_epa_trail", "qb_cpoe_trail", "qb_adot_trail",
          "qb_pressure_trail"]
RUNG_FEATS = {
    "M1": M1_FEATS,
    "M2": list(dict.fromkeys(M1_FEATS + NGS_FAM)),
    "M3": list(dict.fromkeys(M1_FEATS + M3_ADD)),
}

C1_FEATS = ["ngs_xcomp_trail", "ngs_cpoe_trail", "ngs_aggro_trail",
            "qb_adot_trail", "qb_pressure_trail"]


def mae(y, p):
    return float(np.mean(np.abs(y - p)))


def select_hyperparams(Xtr, ytr, Xdv, ydv, feats, wtr=None, wdv=None):
    Xtrn, Xd = Xtr[feats].to_numpy(float), Xdv[feats].to_numpy(float)
    ytrn, ydvn = np.asarray(ytr, float), np.asarray(ydv, float)
    wtrn = None if wtr is None else np.asarray(wtr, float)
    wdvn = None if wdv is None else np.asarray(wdv, float)

    def wmae(y, p, w):
        e = np.abs(y - p)
        return float(np.sum(w * e) / np.sum(w)) if w is not None else float(np.mean(e))

    s = StandardScaler()
    Xs = s.fit_transform(Xtrn)
    Xds = s.transform(Xd)
    best_a, best_a_s = None, np.inf
    for a in A_ALPHAS:
        r = Ridge(alpha=a).fit(Xs, ytrn, sample_weight=wtrn)
        sc = wmae(ydvn, r.predict(Xds), wdvn)
        if sc < best_a_s:
            best_a, best_a_s = a, sc
    best_b, best_b_s = None, np.inf
    for gp in B_GRID:
        g = HistGradientBoostingRegressor(
            random_state=11, **gp).fit(Xtrn, ytrn, sample_weight=wtrn)
        sc = wmae(ydvn, np.maximum(g.predict(Xd), 0.0), wdvn)
        if sc < best_b_s:
            best_b, best_b_s = gp, sc
    return best_a, best_b


def fit_final(Xtr, ytr, feats, alpha, b_params, wtr=None, floor=0.0):
    X = Xtr[feats].to_numpy(float)
    y = np.asarray(ytr, float)
    w = None if wtr is None else np.asarray(wtr, float)
    s = StandardScaler()
    r = Ridge(alpha=alpha).fit(s.fit_transform(X), y, sample_weight=w)
    g = HistGradientBoostingRegressor(
        random_state=11, **b_params).fit(X, y, sample_weight=w)

    def pred(df):
        pr = r.predict(s.transform(df[feats].to_numpy(float)))
        pg = np.maximum(g.predict(df[feats].to_numpy(float)), floor)
        return (pr + pg) / 2.0
    return pred


def load(phase):
    t = pd.read_parquet(TABLE)
    periods = ("train", "dev") if phase == "dev" else ("train", "dev", "test")
    return {p: t[t["period"] == p].reset_index(drop=True) for p in periods}


def bootstrap_ci(y, p_base, p_new, n=BOOT):
    diff = np.abs(np.asarray(y, float) - np.asarray(p_base, float)) - \
        np.abs(np.asarray(y, float) - np.asarray(p_new, float))
    bs = np.array([np.mean(RNG.choice(diff, size=len(diff), replace=True))
                   for _ in range(n)])
    return [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def season_metrics(y, p, season):
    out = {}
    for s in (2023, 2024):
        m = (np.asarray(season) == s)
        out[str(s)] = {"mae": mae(np.asarray(y)[m], np.asarray(p)[m]),
                       "n": int(m.sum())}
    return out


def dev_phase():
    t0 = time.time()
    D = load("dev")
    tr, dv = D["train"], D["dev"]
    ytr, ydv = tr["actual_att"].to_numpy(float), dv["actual_att"].to_numpy(float)

    dev = {"n_train": len(tr), "n_dev": len(dv)}
    # ---- M0 ----
    m0_tr = tr["trail_pass_att_ewma"].fillna(0).to_numpy(float)
    m0_dv = dv["trail_pass_att_ewma"].fillna(0).to_numpy(float)
    dev["M0"] = {"mae": mae(ydv, m0_dv)}
    print(f"[M0] dev MAE: {dev['M0']['mae']:.3f}", flush=True)

    fitted = {}
    for rung in ("M1", "M2", "M3"):
        feats = RUNG_FEATS[rung]
        a, b = select_hyperparams(tr, ytr, dv, ydv, feats)
        pred = fit_final(tr, ytr, feats, a, b)
        pdv = pred(dv)
        dev[rung] = {"mae": mae(ydv, pdv), "a_alpha": a, "b_params": b,
                     "feats": feats}
        fitted[rung] = (pred, feats, a, b)
        print(f"[{rung}] dev MAE: {dev[rung]['mae']:.3f} "
              f"alpha={a} b={b}", flush=True)

    # ---- completions leg on dev (feeder: M1 dev projection) ----
    m1_dv = fit_final(tr, ytr, RUNG_FEATS["M1"],
                      dev["M1"]["a_alpha"], dev["M1"]["b_params"])(dv)
    comp_tr = tr["actual_comp"].to_numpy(float)
    rate_tr = comp_tr / np.maximum(ytr, 1e-9)
    comp_dv = dv["actual_comp"].to_numpy(float)
    rate_dv = comp_dv / np.maximum(ydv, 1e-9)
    c0_dv = m1_dv * np.clip(dv["trail_comp_rate_ewma"].fillna(0).to_numpy(float),
                             0.0, 1.0)
    a, b = select_hyperparams(tr, rate_tr, dv, rate_dv, C1_FEATS,
                              wtr=ytr, wdv=ydv)
    cpred = fit_final(tr, rate_tr, C1_FEATS, a, b, wtr=ytr)
    cprob_dv = np.clip(cpred(dv), 0.05, 0.98)
    c1_dv = m1_dv * cprob_dv
    dev["C0"] = {"mae": mae(comp_dv, c0_dv)}
    dev["C1"] = {"mae": mae(comp_dv, c1_dv), "a_alpha": a, "b_params": b,
                 "feats": C1_FEATS}
    print(f"[C0] dev completions MAE: {dev['C0']['mae']:.3f} | "
          f"[C1] dev completions MAE: {dev['C1']['mae']:.3f}", flush=True)

    dev["elapsed_s"] = round(time.time() - t0, 1)
    json.dump(dev, open(f"{EXP}/data/experiment_003C_dev.json", "w"),
              indent=1, default=str)
    print("DEV PHASE COMPLETE — test slice untouched.", flush=True)


def test_phase():
    dev_path = f"{EXP}/data/experiment_003C_dev.json"
    assert os.path.exists(dev_path), "run --phase dev first"
    dev_out = json.load(open(dev_path))
    t0 = time.time()
    D = load("test")
    tr, te = D["train"], D["test"]
    ytr, yte = tr["actual_att"].to_numpy(float), te["actual_att"].to_numpy(float)
    season = te["season"].to_numpy()

    res = {"n_train": len(tr), "n_test": len(te),
           "n_2023": int((te["season"] == 2023).sum()),
           "n_2024": int((te["season"] == 2024).sum())}
    assert res["n_test"] >= MIN_N, "minimum-sample rule"

    # ---- M0 ----
    m0_te = te["trail_pass_att_ewma"].fillna(0).to_numpy(float)
    res["M0"] = {"mae": mae(yte, m0_te), "by_season": season_metrics(yte, m0_te, season)}

    preds = {}
    for rung in ("M1", "M2", "M3"):
        d = dev_out[rung]
        pred = fit_final(tr, ytr, d["feats"], d["a_alpha"], d["b_params"])
        p = pred(te)
        preds[rung] = p
        ci = bootstrap_ci(yte, m0_te, p)
        r = {"mae": mae(yte, p),
             "by_season": season_metrics(yte, p, season),
             "bootstrap_ci_M0_minus_rung": ci,
             "a_alpha": d["a_alpha"], "b_params": d["b_params"]}
        res[rung] = r
        print(f"[{rung}] test MAE: {r['mae']:.3f} (M0 {res['M0']['mae']:.3f})",
              flush=True)

    # ---- completions leg (feeder: M1 test projection, predetermined) ----
    m1_te = preds["M1"]
    comp_te = te["actual_comp"].to_numpy(float)
    c0_te = m1_te * np.clip(te["trail_comp_rate_ewma"].fillna(0).to_numpy(float),
                            0.0, 1.0)
    d = dev_out["C1"]
    rate_tr = tr["actual_comp"].to_numpy(float) / np.maximum(ytr, 1e-9)
    cpred = fit_final(tr, rate_tr, d["feats"], d["a_alpha"], d["b_params"],
                      wtr=ytr)
    cprob_te = np.clip(cpred(te), 0.05, 0.98)
    c1_te = m1_te * cprob_te
    ci_c = bootstrap_ci(comp_te, c0_te, c1_te)
    res["C0"] = {"mae": mae(comp_te, c0_te),
                 "by_season": season_metrics(comp_te, c0_te, season)}
    res["C1"] = {"mae": mae(comp_te, c1_te),
                 "by_season": season_metrics(comp_te, c1_te, season),
                 "bootstrap_ci_C0_minus_C1": ci_c,
                 "a_alpha": d["a_alpha"], "b_params": d["b_params"]}

    # ---- win-bar evaluation ----
    def clears(bar_base_mae, bar_base_seas, cand_mae, cand_seas, ci):
        rel = (bar_base_mae - cand_mae) / bar_base_mae
        s23 = (bar_base_seas["2023"]["mae"] - cand_seas["2023"]["mae"]) / \
            bar_base_seas["2023"]["mae"]
        s24 = (bar_base_seas["2024"]["mae"] - cand_seas["2024"]["mae"]) / \
            bar_base_seas["2024"]["mae"]
        return {"rel_improvement": rel, "s2023": s23, "s2024": s24,
                "ci_excludes_zero": ci[0] > 0,
                "clears": rel >= 0.05 and s23 >= 0.02 and s24 >= 0.02 and ci[0] > 0}

    verdict = {}
    for rung in ("M1", "M2", "M3"):
        verdict[rung] = clears(res["M0"]["mae"], res["M0"]["by_season"],
                              res[rung]["mae"], res[rung]["by_season"],
                              res[rung]["bootstrap_ci_M0_minus_rung"])
    verdict["C1_vs_C0"] = clears(res["C0"]["mae"], res["C0"]["by_season"],
                                 res["C1"]["mae"], res["C1"]["by_season"],
                                 res["C1"]["bootstrap_ci_C0_minus_C1"])
    res["win_bar"] = verdict

    for k in ("M1", "M2", "M3"):
        v = verdict[k]
        print(f"[{k}] rel_imp={v['rel_improvement']:+.3%} s23={v['s2023']:+.3%} "
              f"s24={v['s2024']:+.3%} ci0={v['ci_excludes_zero']} "
              f"clears={v['clears']}", flush=True)
    v = verdict["C1_vs_C0"]
    print(f"[C1 vs C0] rel_imp={v['rel_improvement']:+.3%} s23={v['s2023']:+.3%} "
          f"s24={v['s2024']:+.3%} ci0={v['ci_excludes_zero']} "
          f"clears={v['clears']}", flush=True)

    res["elapsed_s"] = round(time.time() - t0, 1)
    json.dump(res, open(f"{EXP}/data/experiment_003C_test.json", "w"),
              indent=1, default=str)

    df = te[["player_name", "team", "opponent", "season", "week", "position",
             "actual_att", "actual_comp"]].copy()
    df["pred_M0"] = m0_te
    for rung in ("M1", "M2", "M3"):
        df[f"pred_{rung}"] = preds[rung]
    df["pred_C0"] = c0_te
    df["pred_C1"] = c1_te
    df.to_parquet(f"{EXP}/data/experiment_003C_test_predictions.parquet",
                  index=False)
    print("TEST EVALUATION COMPLETE (single pass).", flush=True)


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
