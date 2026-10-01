#!/usr/bin/env python3
"""Experiment 003B runner: rush attempts. Fixed ladder M0/M1/M2/M3.

Usage:
  run_experiment_003b.py --phase dev    # fit on train, select on dev. Test untouched.
  run_experiment_003b.py --phase test   # requires PROTOCOL_FROZEN + dev outputs; single eval.

Prereg (frozen 2026-10-01): props_experiment_003_market_expansion/
003B_rush_attempts/PREREGISTRATION.md. Shared discipline:
MARKET_EXPANSION_PROTOCOL.md.

Population: market=='rush_yards' (all RB), eligible_hist==1, played_role==1,
trail_rush_att_ewma >= 5. Target: actual_att (carries). Primary metric:
walk-forward MAE vs M0.

Model procedure (shared protocol section 4: follows 002 section 7). Because
the target is pure opportunity (attempts, no efficiency stage), the 002
two-stage A degenerates to a single-stage Ridge on the rung's opportunity
features; B = GBM direct; C = quantile-GBM median (fixed a priori);
D = equal-weight mean of A/B/C point projections, clipped >= 0.
  M0: trailing carries EWMA (trail_rush_att_ewma), frozen. NaN->0.
  M1: opportunity set = pace_team_plays, trail_rush_share_ewma,
      opp2_snap_pct, neut_rush_rate, ctx_elo_adv, trail_rz_carries_ewma,
      trail_games (weight input, shared protocol section 3).
  M2: M1 + NGS rushing family (trailing only): ngs_eff, ngs_xrush,
      ngs_ryoe, ngs_ryoe_pct, ngs_8box, ngs_ttl.
  M3: M1 + team/matchup/game-context families (002 Families B, C, D1, D2, E, L):
      ctx_team_off_epa, ctx_team_off_pass_epa, ctx_team_off_rush_epa,
      ctx_team_off_sr, oppd_def_rush_epa, envs_dome, envs_team_pts_trail,
      envs_opp_pts_allowed_trail, envf_days_rest, envf_rest_diff,
      envf_short_week, envf_long_rest, envf_div_game, pace_combined,
      pace_neutral_pass_rate.
spread/total/implied lines EXCLUDED everywhere (002 leakage rule).

Hyperparameters: Ridge alpha grid {0.1,1,10,100} re-selected on dev per rung;
GBM 8-combo grid re-selected on dev per rung; quantile hyperparams fixed a
priori. Seeds fixed (1337 bootstrap; GBM random_state=11; quantile 7).

Win bar (shared protocol section 5, 003A-003C):
  1. pooled 2023-2024: >=5% relative MAE reduction vs M0;
  2. >=2% relative reduction in 2023 AND in 2024 individually;
  3. 95% paired bootstrap CI of the MAE difference excludes zero.
Verdict: MATERIAL WIN / NULL / PARTIAL-SIGNAL (significant but sub-bar).
"""
import argparse
import json
import os
import pickle
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingRegressor

REPO = os.path.expanduser("~/workspace/nfl-model")
EXP = os.path.join(REPO, "experiments/props_experiment_003_market_expansion",
                   "003B_rush_attempts")
TABLE = os.path.join(EXP, "data/features_003b_2018_2024.parquet")

RNG = np.random.default_rng(1337)
BOOT = 2000
A_ALPHAS = [0.1, 1.0, 10.0, 100.0]
B_GRID = [{"learning_rate": lr, "max_depth": md, "max_iter": mi}
          for lr in (0.05, 0.1) for md in (3, 5) for mi in (200, 500)]
C_PARAMS = dict(loss="quantile", learning_rate=0.1, max_depth=3,
                max_iter=300, min_samples_leaf=20, random_state=7)
RUNGS = ["M0", "M1", "M2", "M3"]
MIN_N = 1000  # shared protocol section 6: rush attempts pooled >= 1000

M1_FEATS = ["pace_team_plays", "trail_rush_share_ewma", "opp2_snap_pct",
            "neut_rush_rate", "ctx_elo_adv", "trail_rz_carries_ewma",
            "trail_games"]
NGS_FEATS = ["ngs_eff", "ngs_xrush", "ngs_ryoe", "ngs_ryoe_pct",
             "ngs_8box", "ngs_ttl"]
CTX_FEATS = ["ctx_team_off_epa", "ctx_team_off_pass_epa",
             "ctx_team_off_rush_epa", "ctx_team_off_sr", "oppd_def_rush_epa",
             "envs_dome", "envs_team_pts_trail", "envs_opp_pts_allowed_trail",
             "envf_days_rest", "envf_rest_diff", "envf_short_week",
             "envf_long_rest", "envf_div_game", "pace_combined",
             "pace_neutral_pass_rate"]


def rung_features(rung):
    if rung == "M1":
        return list(M1_FEATS)
    if rung == "M2":
        return list(dict.fromkeys(M1_FEATS + NGS_FEATS))
    if rung == "M3":
        return list(dict.fromkeys(M1_FEATS + CTX_FEATS))
    raise ValueError(rung)


def mae(y, p):
    return float(np.mean(np.abs(y - p)))


def fit_A(tr, feats, alpha):
    s = StandardScaler()
    m = Ridge(alpha=alpha).fit(s.fit_transform(tr[feats].to_numpy(float)),
                               tr["actual_att"].to_numpy(float))
    return (s, m, feats)


def pred_A(model, df):
    s, m, feats = model
    return np.maximum(m.predict(s.transform(df[feats].to_numpy(float))), 0.0)


def fit_B(tr, feats, params):
    m = HistGradientBoostingRegressor(random_state=11, **params)
    return (m.fit(tr[feats].to_numpy(float),
                  tr["actual_att"].to_numpy(float)), feats)


def pred_B(model, df):
    m, feats = model
    return np.maximum(m.predict(df[feats].to_numpy(float)), 0.0)


def fit_C(tr, feats):
    X = tr[feats].to_numpy(float)
    y = tr["actual_att"].to_numpy(float)
    return (HistGradientBoostingRegressor(quantile=0.5, **C_PARAMS).fit(X, y),
            feats)


def pred_C(model, df):
    m, feats = model
    return np.maximum(m.predict(df[feats].to_numpy(float)), 0.0)


def fit_D_rung(tr, dv, rung, fixed_alpha=None, fixed_b_params=None):
    """Fit A/B/C for one rung on train; dev-select alpha and B params unless
    fixed_* are given (test phase: use dev-selected hyperparams)."""
    feats = rung_features(rung)
    if fixed_alpha is not None:
        A = fit_A(tr, feats, fixed_alpha)
        a_alpha = fixed_alpha
    else:
        ydv = dv["actual_att"].to_numpy(float)
        cands = {a: (fit_A(tr, feats, a), None) for a in A_ALPHAS}
        scored = {a: mae(ydv, pred_A(cands[a][0], dv)) for a in A_ALPHAS}
        a_alpha = min(scored, key=scored.get)
        A = cands[a_alpha][0]
    if fixed_b_params is not None:
        B = fit_B(tr, feats, fixed_b_params)
        b_params = fixed_b_params
    else:
        ydv = dv["actual_att"].to_numpy(float)
        scored = {}
        bmods = {}
        for i, gp in enumerate(B_GRID):
            m = fit_B(tr, feats, gp)
            bmods[i] = m
            scored[i] = mae(ydv, pred_B(m, dv))
        b_key = min(scored, key=scored.get)
        B, b_params = bmods[b_key], B_GRID[b_key]
    C = fit_C(tr, feats)
    dev = None
    if dv is not None:
        pA, pB, pC = pred_A(A, dv), pred_B(B, dv), pred_C(C, dv)
        dev = {"pA": pA, "pB": pB, "pC": pC, "pD": (pA + pB + pC) / 3.0}
    return {"A": A, "B": B, "C": C, "a_alpha": a_alpha, "b_params": b_params,
            "feats": feats, "dev": dev}


def load(phase):
    t = pd.read_parquet(TABLE)
    ev = t[(t["market"] == "rush_yards") &
           (t["eligible_hist"] == 1) & (t["played_role"] == 1) &
           (t["trail_rush_att_ewma"] >= 5)].copy()
    ev["m0_pred"] = ev["trail_rush_att_ewma"].fillna(0)
    periods = ("train", "dev") if phase == "dev" else ("train", "dev", "test")
    return {p: ev[ev["period"] == p].reset_index(drop=True) for p in periods}


def dev_phase():
    t0 = time.time()
    D = load("dev")
    dev_out, fitted = {}, {}
    print("population n by period:",
          {p: len(D[p]) for p in ("train", "dev")}, flush=True)
    for rung in ["M1", "M2", "M3"]:
        tr, dv = D["train"], D["dev"]
        F = fit_D_rung(tr, dv, rung)
        fitted[rung] = F
        ydv = dv["actual_att"].to_numpy(float)
        ytr = tr["actual_att"].to_numpy(float)
        m0d = mae(ydv, dv["m0_pred"].to_numpy(float))
        m0t = mae(ytr, tr["m0_pred"].to_numpy(float))
        dev_out[rung] = {
            "n_train": len(tr), "n_dev": len(dv),
            "train_M0_MAE": m0t,
            "dev_M0_MAE": m0d,
            "dev_A": mae(ydv, F["dev"]["pA"]),
            "dev_B": mae(ydv, F["dev"]["pB"]),
            "dev_C": mae(ydv, F["dev"]["pC"]),
            "dev_D": mae(ydv, F["dev"]["pD"]),
            "dev_D_rel_vs_M0": (m0d - mae(ydv, F["dev"]["pD"])) / m0d,
            "a_alpha": F["a_alpha"], "b_params": F["b_params"],
            "n_feats": len(F["feats"])}
        print(f"[{rung}] train n={len(tr)} dev n={len(dv)} | "
              f"dev M0={m0d:.3f} A={dev_out[rung]['dev_A']:.3f} "
              f"B={dev_out[rung]['dev_B']:.3f} C={dev_out[rung]['dev_C']:.3f} "
              f"D={dev_out[rung]['dev_D']:.3f} "
              f"(rel {dev_out[rung]['dev_D_rel_vs_M0']:+.1%}) | "
              f"alpha={F['a_alpha']} b={F['b_params']}", flush=True)
    out = {"dev": dev_out, "rung_features": {r: rung_features(r)
                                             for r in ("M1", "M2", "M3")},
           "elapsed_s": round(time.time() - t0, 1)}
    json.dump(out, open(f"{EXP}/data/experiment_003b_dev.json", "w"), indent=1,
              default=str)
    print("DEV PHASE COMPLETE - test slice untouched.")


def test_phase():
    assert os.path.exists(os.path.join(EXP, "PROTOCOL_FROZEN")), \
        "protocol not frozen - refusing test evaluation"
    dev_path = f"{EXP}/data/experiment_003b_dev.json"
    assert os.path.exists(dev_path), "run --phase dev first"
    dev_out = json.load(open(dev_path))
    t0 = time.time()
    D = load("test")
    tr, te = D["train"], D["test"]
    yte = te["actual_att"].to_numpy(float)
    m0 = te["m0_pred"].to_numpy(float)

    res, rows = {}, []
    preds = {"M0": m0}
    # M0 metrics
    r0 = {"n": len(te), "n_2023": int((te["season"] == 2023).sum()),
          "n_2024": int((te["season"] == 2024).sum()),
          "MAE": mae(yte, m0), "RMSE": float(np.sqrt(np.mean((yte - m0) ** 2))),
          "bias": float(np.mean(m0 - yte))}
    seas0 = {}
    for s in (2023, 2024):
        idx = (te["season"] == s).to_numpy()
        seas0[str(s)] = {"MAE": mae(yte[idx], m0[idx]), "n": int(idx.sum())}
    r0["by_season"] = seas0
    res["M0"] = r0

    for rung in ("M1", "M2", "M3"):
        dm = dev_out["dev"][rung]
        F = fit_D_rung(tr, None, rung, fixed_alpha=dm["a_alpha"],
                       fixed_b_params=dm["b_params"])
        pA, pB, pC = pred_A(F["A"], te), pred_B(F["B"], te), pred_C(F["C"], te)
        pD = (pA + pB + pC) / 3.0
        preds[rung] = pD
        r = {"n": len(te), "n_2023": r0["n_2023"], "n_2024": r0["n_2024"],
             "MAE": mae(yte, pD),
             "RMSE": float(np.sqrt(np.mean((yte - pD) ** 2))),
             "bias": float(np.mean(pD - yte)),
             "A_MAE": mae(yte, pA), "B_MAE": mae(yte, pB),
             "C_MAE": mae(yte, pC),
             "a_alpha": dm["a_alpha"], "b_params": dm["b_params"]}
        seas = {}
        for s in (2023, 2024):
            idx = (te["season"] == s).to_numpy()
            seas[str(s)] = {"MAE": mae(yte[idx], pD[idx]),
                            "n": int(idx.sum())}
        r["by_season"] = seas
        # paired bootstrap CI of (M0 - rung) MAE difference, pooled test
        diff = np.abs(yte - m0) - np.abs(yte - pD)
        bs = np.array([np.mean(RNG.choice(diff, size=len(diff), replace=True))
                       for _ in range(BOOT)])
        r["bootstrap_ci_M0_minus_rung"] = [
            float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
        r["bootstrap_mean_diff"] = float(bs.mean())
        res[rung] = r
        # frozen artifacts: the exact fitted models evaluated on test
        with open(f"{EXP}/models/{rung}_fitted.pkl", "wb") as f:
            pickle.dump({"A": F["A"], "B": F["B"], "C": F["C"],
                         "feats": F["feats"], "a_alpha": F["a_alpha"],
                         "b_params": F["b_params"],
                         "fitted_on": "train 2018-2020",
                         "dev_selected": True}, f)
        df = te[["player_name", "team", "opponent", "season", "week",
                 "position", "actual_att"]].copy()
        df["rung"] = rung
        df["pred_D"] = pD
        df["pred_A"], df["pred_B"], df["pred_C"] = pA, pB, pC
        rows.append(df)
        print(f"[{rung}] test MAE={r['MAE']:.3f} vs M0={r0['MAE']:.3f} "
              f"(rel {(r0['MAE'] - r['MAE']) / r0['MAE']:+.2%})", flush=True)

    # win-bar evaluation (shared protocol section 5)
    verdict = {}
    for rung in ("M1", "M2", "M3"):
        b, v = r0["MAE"], res[rung]["MAE"]
        rel = (b - v) / b
        s23 = (r0["by_season"]["2023"]["MAE"] -
               res[rung]["by_season"]["2023"]["MAE"]) / r0["by_season"]["2023"]["MAE"]
        s24 = (r0["by_season"]["2024"]["MAE"] -
               res[rung]["by_season"]["2024"]["MAE"]) / r0["by_season"]["2024"]["MAE"]
        ci = res[rung]["bootstrap_ci_M0_minus_rung"]
        cond = {"pooled_rel_ge_5pct": bool(rel >= 0.05),
                "s2023_rel_ge_2pct": bool(s23 >= 0.02),
                "s2024_rel_ge_2pct": bool(s24 >= 0.02),
                "ci_excludes_zero": bool(ci[0] > 0),
                "n_ok": bool(res[rung]["n"] >= MIN_N)}
        clears = all(cond.values())
        partial = (not clears) and cond["ci_excludes_zero"]
        verdict[rung] = {
            "rel_improvement": rel, "s2023": s23, "s2024": s24,
            "conditions": cond,
            "verdict": ("MATERIAL WIN" if clears
                        else "PARTIAL/SIGNAL" if partial else "NULL")}

    out = {"test": res, "win_bar": verdict,
           "rung_features": dev_out["rung_features"],
           "bootstrap": {"n_resamples": BOOT, "seed": 1337, "paired": True,
                         "stat": "mean(M0_abs_err - rung_abs_err), pooled test"},
           "elapsed_s": round(time.time() - t0, 1)}
    json.dump(out, open(f"{EXP}/data/experiment_003b_test.json", "w"), indent=1,
              default=str)
    pd.concat(rows, ignore_index=True).to_parquet(
        f"{EXP}/data/experiment_003b_test_predictions.parquet", index=False)
    print("TEST EVALUATION COMPLETE (single pass).")
    for rung in ("M1", "M2", "M3"):
        print(f"[{rung}] {verdict[rung]['verdict']} "
              f"rel={verdict[rung]['rel_improvement']:+.2%} "
              f"s23={verdict[rung]['s2023']:+.2%} s24={verdict[rung]['s2024']:+.2%} "
              f"ci_excl0={verdict[rung]['conditions']['ci_excludes_zero']}",
              flush=True)


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
