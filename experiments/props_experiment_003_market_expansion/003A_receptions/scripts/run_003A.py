#!/usr/bin/env python3
"""Experiment 003A runner: receptions, fixed ladder M0/M1/M2/M3, single locked-test eval.

Usage:
  run_003A.py --phase dev    # fit on train, select hyperparams on dev. Test untouched.
  run_003A.py --phase test   # requires PROTOCOL_FROZEN_003A + dev outputs; single eval.

Target: g_receptions (player-game receptions from pbp complete_pass).
Population: receiving market, eligible_hist=1 & played_role=1, evaluated rows
require trailing targets > 0 (trail_targets_ewma > 0; holds for 100% of the
eligible population) and a merged pbp actual.

Model D procedure mirrors experiments/props_experiment_002/scripts/
run_experiment_002.py (the frozen 001/002 procedure), adapted to the 003A
two-stage process model:
  A: two-stage Ridge — stage 1 predicts g_targets (opportunity),
     stage 2 predicts catch rate = g_receptions / max(g_targets, eps)
     (efficiency). pred = max(pred_targets * pred_catchrate, 0).
     alpha dev-selected from {0.1, 1, 10, 100}.
  B: HistGradientBoostingRegressor direct g_receptions, 8-combo grid
     dev-selected (lr in {0.05, 0.1} x depth in {3, 5} x iter in {200, 500}).
  C: quantile GBM P25/median/P75, fixed params (lr=0.1, max_depth=3,
     max_iter=300, min_samples_leaf=20, random_state=7).
  D = equal-weight mean of A/B/C point projections.

Ladder (003A preregistration section 4):
  M0  trailing receptions EWMA (frozen baseline, no fitting)
  M1  process model: S1 -> expected targets; S2 -> catch probability
  M2  M1 + NGS family (6 trailing NGS receiving fields)
  M3  M1 + team/matchup/game-context families (B, C, D1, D2, E, L)

Win bar (shared protocol section 5, single market): pooled 2023-2024
>=5% relative MAE reduction vs M0; >=2% in 2023 AND 2024 individually;
95% paired bootstrap CI (2000 resamples, seed 1337) excludes zero.

Seeds fixed (1337). Fit once. No production changes.
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
EXP = os.path.join(REPO, "experiments/props_experiment_003_market_expansion/003A_receptions")
TABLE = os.path.join(EXP, "data/features_003A_2018_2024.parquet")

RNG = np.random.default_rng(1337)
BOOT = 2000
A_ALPHAS = [0.1, 1.0, 10.0, 100.0]
B_GRID = [{"learning_rate": lr, "max_depth": md, "max_iter": mi}
          for lr in (0.05, 0.1) for md in (3, 5) for mi in (200, 500)]
C_PARAMS = dict(loss="quantile", learning_rate=0.1, max_depth=3,
                max_iter=300, min_samples_leaf=20, random_state=7)

# ---- M1 process-model feature sets (prereg section 4) ----
S1 = [  # expected targets: targets/target-share/snap-share/team-pass-rate/
        # expected-plays/opponent context
    "trail_targets_ewma", "trail_target_share_ewma",
    "opp2_snap_pct", "opp2_snap_trend",
    "pace_neutral_pass_rate", "pace_team_plays", "pace_combined",
    "oppd_def_pass_epa",
]
S2 = [  # catch probability: ADOT / separation-proxy (trailing pbp
        # catch-point quality) / QB context (002 Family I reconstruction)
    "rq_adot", "rq_yac_per_rec", "rq_drop_pct", "rq_broken_tackles",
    "qb_epa_trail", "qb_cpoe_trail", "qb_adot_trail",
    "qb_pressure_trail", "qb_changed",
]
NGS = [  # M2 family: trailing NGS receiving fields (trailing use only)
    "ngs_avg_separation_trail", "ngs_avg_cushion_trail",
    "ngs_avg_intended_air_yards_trail",
    "ngs_pct_share_intended_air_yards_trail",
    "ngs_avg_expected_yac_trail", "ngs_avg_yac_above_expectation_trail",
]
# M3 context families (verbatim from 002's FAM dict)
FAM_B = ["ctx_team_off_epa", "ctx_team_off_pass_epa", "ctx_team_off_rush_epa",
         "ctx_team_off_sr", "ctx_elo_adv"]
FAM_C = ["oppd_def_epa", "oppd_def_pass_epa", "oppd_def_rush_epa", "oppd_def_sr"]
FAM_D1 = ["envs_dome", "envs_team_pts_trail", "envs_opp_pts_allowed_trail"]
FAM_D2 = ["envf_days_rest", "envf_rest_diff", "envf_short_week",
          "envf_long_rest", "envf_div_game"]
FAM_E = ["pace_team_plays", "pace_combined", "pace_neutral_pass_rate"]
FAM_L = ["inj_player_status", "inj_team_out_share", "inj_ol_out"]
CTX = FAM_B + FAM_C + FAM_D1 + FAM_D2 + FAM_E + FAM_L

RUNGS = ["M0", "M1", "M2", "M3"]


def rung_features(rung):
    if rung == "M1":
        s1, s2, pool = S1, S2, S1 + S2
    elif rung == "M2":
        s1, s2, pool = S1 + NGS, S2 + NGS, S1 + S2 + NGS
    elif rung == "M3":
        s1, s2, pool = S1 + CTX, S2 + CTX, S1 + S2 + CTX
    else:
        raise ValueError(rung)
    return (list(dict.fromkeys(s1)), list(dict.fromkeys(s2)),
            list(dict.fromkeys(pool)))


def mae(y, p):
    return float(np.mean(np.abs(y - p)))


def X(df, cols):
    return np.nan_to_num(df[cols].to_numpy(float))


# ---- Model D components ----
def fit_A(tr, s1_feats, s2_feats, alpha):
    sc1, sc2 = StandardScaler(), StandardScaler()
    tgt = tr["tg_targets"].to_numpy(float)
    r1 = Ridge(alpha=alpha).fit(sc1.fit_transform(X(tr, s1_feats)), tgt)
    crate = (tr["g_receptions"].to_numpy(float) /
             np.maximum(tgt, 1e-6))
    r2 = Ridge(alpha=alpha).fit(sc2.fit_transform(X(tr, s2_feats)), crate)
    return (sc1, r1, sc2, r2, s1_feats, s2_feats)


def pred_A(model, df):
    sc1, r1, sc2, r2, f1, f2 = model
    o = np.maximum(r1.predict(sc1.transform(X(df, f1))), 0.0)
    e = r2.predict(sc2.transform(X(df, f2)))
    return np.maximum(o * e, 0.0)


def fit_B(tr, pool_feats, params):
    m = HistGradientBoostingRegressor(random_state=11, **params)
    return (m.fit(X(tr, pool_feats), tr["g_receptions"].to_numpy(float)),
            pool_feats)


def pred_B(model, df):
    m, pf = model
    return np.maximum(m.predict(X(df, pf)), 0.0)


def fit_C(tr, pool_feats):
    Xm = X(tr, pool_feats)
    y = tr["g_receptions"].to_numpy(float)
    return ({q: HistGradientBoostingRegressor(quantile=q, **C_PARAMS).fit(Xm, y)
             for q in (0.25, 0.5, 0.75)}, pool_feats)


def pred_C(model, df, q=0.5):
    ms, pf = model
    return np.maximum(ms[q].predict(X(df, pf)), 0.0)


def fit_D_rung(tr, dv, rung, fixed_alpha=None, fixed_b_params=None):
    s1, s2, pool = rung_features(rung)
    if fixed_alpha is not None:
        A, a_alpha = fit_A(tr, s1, s2, fixed_alpha), fixed_alpha
    else:
        ydv = dv["g_receptions"].to_numpy(float)
        cands = {}
        for a in A_ALPHAS:
            m = fit_A(tr, s1, s2, a)
            cands[a] = (m, mae(ydv, pred_A(m, dv)))
        a_alpha = min(cands, key=lambda a: cands[a][1])
        A = cands[a_alpha][0]
    if fixed_b_params is not None:
        B, b_params = fit_B(tr, pool, fixed_b_params), fixed_b_params
    else:
        ydv = dv["g_receptions"].to_numpy(float)
        cands = {}
        for i, gp in enumerate(B_GRID):
            m = fit_B(tr, pool, gp)
            cands[i] = (m, mae(ydv, pred_B(m, dv)), gp)
        k = min(cands, key=lambda i: cands[i][1])
        B, b_params = cands[k][0], cands[k][2]
    C = fit_C(tr, pool)
    dev = None
    if dv is not None:
        pA, pB, pC = pred_A(A, dv), pred_B(B, dv), pred_C(C, dv)
        dev = {"pA": pA, "pB": pB, "pC": pC, "pD": (pA + pB + pC) / 3.0,
               "p25": pred_C(C, dv, 0.25), "p75": pred_C(C, dv, 0.75)}
    return {"A": A, "B": B, "C": C, "a_alpha": a_alpha, "b_params": b_params,
            "feats": {"s1": s1, "s2": s2, "pool": pool}, "dev": dev}


def load(phase):
    t = pd.read_parquet(TABLE)
    ev = t[(t["eligible_hist"] == 1) & (t["played_role"] == 1) &
           (t["trail_targets_ewma"] > 0) &
           (t["g_receptions"].notna())].copy()
    periods = ("train", "dev") if phase == "dev" else ("train", "dev", "test")
    return {p: ev[ev["period"] == p].reset_index(drop=True) for p in periods}


def m0_pred(df):
    return np.nan_to_num(df["trail_receptions_ewma"].to_numpy(float))


def dev_phase():
    t0 = time.time()
    D = load("dev")
    assert D["train"].shape[0] > 0 and D["dev"].shape[0] > 0
    assert "test" not in D, "test slice loaded during dev -- aborting"
    dev_mae, dev_diag = {}, {}
    for rung in ["M1", "M2", "M3"]:
        tr, dv = D["train"], D["dev"]
        ytr, ydv = tr["g_receptions"].to_numpy(float), dv["g_receptions"].to_numpy(float)
        F = fit_D_rung(tr, dv, rung)
        dev_mae[rung] = {"n_train": len(tr), "n_dev": len(dv),
                         "A": mae(ydv, F["dev"]["pA"]),
                         "B": mae(ydv, F["dev"]["pB"]),
                         "C": mae(ydv, F["dev"]["pC"]),
                         "D": mae(ydv, F["dev"]["pD"]),
                         "a_alpha": F["a_alpha"], "b_params": F["b_params"]}
        # dev M0 reference + quantile coverage
        m0d = mae(ydv, m0_pred(dv))
        cov = float(np.mean((ydv >= F["dev"]["p25"]) & (ydv <= F["dev"]["p75"])))
        dev_diag[rung] = {"M0_dev_mae": m0d, "p25_p75_coverage": cov}
        print(f"[{rung}] dev D MAE={dev_mae[rung]['D']:.4f} "
              f"(M0={m0d:.4f}) alpha={F['a_alpha']} "
              f"b={F['b_params']}", flush=True)
    out = {"dev_mae": dev_mae, "dev_diag": dev_diag,
           "elapsed_s": round(time.time() - t0, 1)}
    json.dump(out, open(f"{EXP}/data/experiment_003A_dev.json", "w"), indent=1,
              default=str)
    print("DEV PHASE COMPLETE — test slice untouched.")


def test_phase():
    assert os.path.exists(os.path.join(EXP, "PROTOCOL_FROZEN_003A")), \
        "protocol not frozen — refusing test evaluation"
    dev_path = f"{EXP}/data/experiment_003A_dev.json"
    assert os.path.exists(dev_path), "run --phase dev first"
    dev_out = json.load(open(dev_path))
    t0 = time.time()
    D = load("test")
    tr, te = D["train"], D["test"]
    yte = te["g_receptions"].to_numpy(float)
    n2023, n2024 = int((te["season"] == 2023).sum()), int((te["season"] == 2024).sum())

    test_res, test_rows = {}, []
    m0d = m0_pred(te)
    test_res["M0"] = {"n": len(te), "n_2023": n2023, "n_2024": n2024,
                      "mae": mae(yte, m0d),
                      "rmse": float(np.sqrt(np.mean((yte - m0d) ** 2))),
                      "bias": float(np.mean(m0d - yte))}
    for s in (2023, 2024):
        idx = (te["season"] == s).to_numpy()
        test_res["M0"][f"mae_{s}"] = mae(yte[idx], m0d[idx])
    test_res["M0"]["_p"] = m0d

    for rung in ["M1", "M2", "M3"]:
        dm = dev_out["dev_mae"][rung]
        F = fit_D_rung(tr, None, rung, fixed_alpha=dm["a_alpha"],
                       fixed_b_params=dm["b_params"])
        pA, pB = pred_A(F["A"], te), pred_B(F["B"], te)
        p50 = pred_C(F["C"], te)
        p25, p75 = pred_C(F["C"], te, 0.25), pred_C(F["C"], te, 0.75)
        pD = (pA + pB + p50) / 3.0
        r = {"n": len(te), "n_2023": n2023, "n_2024": n2024,
             "A": mae(yte, pA), "B": mae(yte, pB), "C": mae(yte, p50),
             "D": mae(yte, pD),
             "rmse": float(np.sqrt(np.mean((yte - pD) ** 2))),
             "bias": float(np.mean(pD - yte)),
             "a_alpha": F["a_alpha"], "b_params": F["b_params"]}
        for s in (2023, 2024):
            idx = (te["season"] == s).to_numpy()
            r[f"mae_{s}"] = mae(yte[idx], pD[idx])
        # paired bootstrap CI of (M0 - rung) MAE difference
        diff = np.abs(yte - m0d) - np.abs(yte - pD)
        bs = np.array([np.mean(RNG.choice(diff, size=len(diff), replace=True))
                       for _ in range(BOOT)])
        r["bootstrap_ci_M0_minus_rung"] = [float(np.percentile(bs, 2.5)),
                                           float(np.percentile(bs, 97.5))]
        r["bootstrap_mean_diff"] = float(np.mean(diff))
        # quantile coverage on test
        r["p25_p75_coverage"] = float(np.mean((yte >= p25) & (yte <= p75)))
        test_res[rung] = r
        df = te[["player_name", "team", "opponent", "season", "week",
                 "position", "g_receptions", "tg_targets"]].copy()
        df["rung"] = rung
        df["pred_D"], df["pred_p25"], df["pred_p75"] = pD, p25, p75
        test_rows.append(df)
        print(f"[{rung}] test D MAE={r['D']:.4f} "
              f"(rel vs M0={(test_res['M0']['mae'] - r['D']) / test_res['M0']['mae']:+.3%})",
              flush=True)

    # ---- win-bar evaluation (shared protocol section 5) ----
    verdict = {}
    for rung in ["M1", "M2", "M3"]:
        b, v = test_res["M0"], test_res[rung]
        rel = (b["mae"] - v["D"]) / b["mae"]
        s23 = (b["mae_2023"] - v["mae_2023"]) / b["mae_2023"]
        s24 = (b["mae_2024"] - v["mae_2024"]) / b["mae_2024"]
        ci = v["bootstrap_ci_M0_minus_rung"]
        verdict[rung] = {"rel_improvement": rel, "s2023": s23, "s2024": s24,
                         "ci_lo": ci[0], "ci_hi": ci[1],
                         "ci_excludes_zero": ci[0] > 0,
                         "n_ok": v["n"] >= 2500,
                         "n_2023_ok": v["n_2023"] >= 150,
                         "n_2024_ok": v["n_2024"] >= 150,
                         "clears_bar": (rel >= 0.05 and s23 >= 0.02 and
                                        s24 >= 0.02 and ci[0] > 0 and
                                        v["n"] >= 2500)}

    out = {"test": {r: {k: v for k, v in test_res[r].items() if not k.startswith("_")}
                      for r in test_res},
           "win_bar": verdict, "elapsed_s": round(time.time() - t0, 1)}
    json.dump(out, open(f"{EXP}/data/experiment_003A_test.json", "w"), indent=1,
              default=str)
    m0df = te[["player_name", "team", "opponent", "season", "week",
               "position", "g_receptions", "tg_targets"]].copy()
    m0df["rung"] = "M0"
    m0df["pred_D"] = m0d
    pd.concat([m0df] + test_rows, ignore_index=True).to_parquet(
        f"{EXP}/data/experiment_003A_test_predictions.parquet", index=False)
    print("TEST EVALUATION COMPLETE (single pass).")
    for rung, v in verdict.items():
        print(f"[{rung}] clears_bar={v['clears_bar']} "
              f"rel={v['rel_improvement']:+.3%} s23={v['s2023']:+.3%} "
              f"s24={v['s2024']:+.3%} ci=[{v['ci_lo']:+.4f},{v['ci_hi']:+.4f}]",
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
