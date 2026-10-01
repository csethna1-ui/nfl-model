#!/usr/bin/env python3
"""Experiment 003D runner: anytime-TD binary-event protocol.

Usage:
  run_experiment_003d.py --phase dev    # fit on train, select on dev. Test untouched.
  run_experiment_003d.py --phase test   # single locked-test evaluation.

FROZEN per PREREGISTRATION.md (approved 2026-10-01 12:25 CDT):
  Target: td_binary = 1{rushing_tds + receiving_tds > 0}, population
    WR/TE/RB with eligible_hist=1 & played_role=1.
  M0: trailing TD-rate EWMA with shrinkage toward position base rate
      (deterministic; k=4 pseudo-games; position base rates from train).
  M1 (opportunity model): red-zone/goal-line/inside-10/end-zone usage +
      target/carry share + snap share + team scoring environment +
      opponent red-zone defense + expected game script (pre-week ELO) +
      is_RB + trail_games (mechanical pooled-model terms, documented).
  M2: M1 + NGS family (trailing only).
  M3: M1 + team/matchup/game-context families (002 B/C/D1/D2/E/J/L + QB I).
  Per rung: LogisticRegression (C dev-selected from {10,1,0.1,0.01} --
      binary analog of 002's Ridge alpha grid {0.1,1,10,100}) and
      HistGradientBoostingClassifier log_loss (8-combo grid dev-selected,
      same grid as 002); rung prediction = equal-weight mean of the two
      probabilities (mirrors 002's D = equal-weight mean of components).
  Metrics: Brier (primary), log loss, calibration (10 equal-width buckets;
      slope via logistic regression of y on logit(p)), ROC-AUC / PR-AUC
      (diagnostics), event rate vs mean predicted probability.
  Win bar (all must hold): >=5% pooled Brier reduction vs M0; >=2% in 2023
      AND 2024 individually; calibration (no n>=100 bucket deviates >0.06
      abs from diagonal; slope in [0.85,1.15]); 95% paired bootstrap CI of
      the Brier difference excludes zero (2000 resamples, seed 1337).
  spread/total/implied scoring EXCLUDED everywhere (002 leakage rule).
  Seeds: bootstrap RNG 1337; GBM random_state=11 (002 precedent).
"""
import argparse
import json
import os
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import log_loss, roc_auc_score, average_precision_score

REPO = os.path.expanduser("~/workspace/nfl-model")
EXP = os.path.join(REPO,
                   "experiments/props_experiment_003_market_expansion/003D_anytime_td")
TABLE = os.path.join(EXP, "data/003d_features_2018_2024.parquet")

RNG = np.random.default_rng(1337)
BOOT = 2000
C_GRID = [10.0, 1.0, 0.1, 0.01]  # binary analog of Ridge alphas {0.1,1,10,100}
GBM_GRID = [{"learning_rate": lr, "max_depth": md, "max_iter": mi}
            for lr in (0.05, 0.1) for md in (3, 5) for mi in (200, 500)]
RUNGS = ["M0", "M1", "M2", "M3"]

M1_FEATS = [
    "trail_rz_targets_ewma", "trail_rz_carries_ewma", "ruq_goal_line_carries",
    "trail_inside10_carries_ewma", "trail_inside10_targets_ewma",
    "trail_endzone_targets_ewma",
    "trail_target_share_ewma", "trail_rush_share_ewma", "trail_air_share_ewma",
    "opp2_snap_pct",
    "envs_team_pts_trail", "envs_opp_pts_allowed_trail",
    "opp_rz_td_rate_allowed_trail", "ctx_elo_adv",
    "is_RB", "trail_games",
]
M2_ADD = ["rq_ngs_separation", "rq_ngs_cushion", "rq_ngs_intended_air_yards",
          "ruq_ngs_efficiency", "ruq_ngs_ryoe_per_att"]
M3_ADD = ["ctx_team_off_epa", "ctx_team_off_pass_epa", "ctx_team_off_rush_epa",
          "ctx_team_off_sr",
          "oppd_def_epa", "oppd_def_pass_epa", "oppd_def_rush_epa", "oppd_def_sr",
          "envs_dome",
          "envf_days_rest", "envf_rest_diff", "envf_short_week",
          "envf_long_rest", "envf_div_game",
          "pace_team_plays", "pace_combined", "pace_neutral_pass_rate",
          "ol_team_pressure_allowed", "ol_opp_sack_rate",
          "inj_player_status", "inj_team_out_share", "inj_ol_out",
          "qb_epa_trail", "qb_cpoe_trail", "qb_adot_trail",
          "qb_pressure_trail", "qb_changed"]
RUNG_FEATS = {"M1": M1_FEATS,
              "M2": M1_FEATS + M2_ADD,
              "M3": list(dict.fromkeys(M1_FEATS + M3_ADD))}


def brier(y, p):
    return float(np.mean((p - y) ** 2))


def calib_metrics(y, p):
    """Calibration: 10 equal-width buckets; slope via y ~ logit(p)."""
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    y = np.asarray(y, dtype=float)
    edges = np.linspace(0, 1, 11)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, 9)
    buckets = []
    for b in range(10):
        m = idx == b
        n = int(m.sum())
        if n == 0:
            buckets.append({"n": 0})
            continue
        mp, er = float(p[m].mean()), float(y[m].mean())
        buckets.append({"n": n, "mean_pred": mp, "event_rate": er,
                        "abs_dev": abs(mp - er)})
    with np.errstate(divide="ignore", invalid="ignore"):
        lp = np.log(p / (1 - p))
    lp = np.clip(lp, -6.9, 6.9)  # logit(clip p to [1e-3, 1-1e-3])
    lr = LogisticRegression().fit(lp.reshape(-1, 1), y)
    slope = float(lr.coef_[0][0])
    big = [bk for bk in buckets if bk["n"] >= 100]
    return {"buckets": buckets,
            "max_abs_dev_n100": max((bk["abs_dev"] for bk in big), default=None),
            "n_buckets_n100": len(big),
            "slope": slope,
            "event_rate": float(y.mean()),
            "mean_pred": float(p.mean())}


def full_metrics(y, p):
    pc = np.clip(np.asarray(p, dtype=float), 1e-15, 1 - 1e-15)
    return {"brier": brier(y, p),
            "log_loss": float(log_loss(y, pc)),
            "roc_auc": float(roc_auc_score(y, pc)),
            "pr_auc": float(average_precision_score(y, pc)),
            "calibration": calib_metrics(y, p)}


def fit_logistic(tr, feats, C):
    X = tr[feats].to_numpy(float)
    X = np.nan_to_num(X, nan=0.0)
    s = StandardScaler()
    m = LogisticRegression(C=C, max_iter=2000, random_state=1337)
    m.fit(s.fit_transform(X), tr["td_binary"].to_numpy(int))
    return s, m


def pred_logistic(model, df, feats):
    s, m = model
    X = np.nan_to_num(df[feats].to_numpy(float), nan=0.0)
    return m.predict_proba(s.transform(X))[:, 1]


def fit_gbm(tr, feats, params):
    X = np.nan_to_num(tr[feats].to_numpy(float), nan=0.0)
    m = HistGradientBoostingClassifier(loss="log_loss", random_state=11,
                                       **params)
    return m.fit(X, tr["td_binary"].to_numpy(int)), feats


def pred_gbm(model, df):
    m, feats = model
    X = np.nan_to_num(df[feats].to_numpy(float), nan=0.0)
    return m.predict_proba(X)[:, 1]


def fit_rung(tr, dv, rung, fixed_C=None, fixed_gbm=None):
    """Fit logistic + GBM for one rung on train; dev-select hyperparams
    unless fixed_* given (test phase). Rung prob = mean of the two."""
    feats = RUNG_FEATS[rung]
    ydv = dv["td_binary"].to_numpy(int) if dv is not None else None
    if fixed_C is not None:
        L, C = fit_logistic(tr, feats, fixed_C), fixed_C
    else:
        cands = {}
        for C in C_GRID:
            Lm = fit_logistic(tr, feats, C)
            cands[C] = (Lm, brier(ydv, pred_logistic(Lm, dv, feats)))
        C = min(cands, key=lambda c: cands[c][1])
        L = cands[C][0]
    if fixed_gbm is not None:
        G, gp = fit_gbm(tr, feats, fixed_gbm), fixed_gbm
    else:
        cands = {}
        for i, prm in enumerate(GBM_GRID):
            Gm = fit_gbm(tr, feats, prm)
            cands[i] = (Gm, brier(ydv, pred_gbm(Gm, dv)), prm)
        k = min(cands, key=lambda i: cands[i][1])
        G, gp = cands[k][0], cands[k][2]

    def pred(df):
        return (pred_logistic(L, df, feats) + pred_gbm(G, df)) / 2.0

    dev_pred = pred(dv) if dv is not None else None
    return {"pred": pred, "C": C, "gbm_params": gp, "feats": feats,
            "dev_pred": dev_pred}


def load(phase):
    t = pd.read_parquet(TABLE)
    t["is_RB"] = (t["position"] == "RB").astype(int)
    ev = t[(t["eligible_hist"] == 1) & (t["played_role"] == 1)].copy()
    periods = ("train", "dev") if phase == "dev" else ("train", "dev", "test")
    return {p: ev[ev["period"] == p].reset_index(drop=True) for p in periods}


def dev_phase():
    t0 = time.time()
    D = load("dev")
    tr, dv = D["train"], D["dev"]
    ydv = dv["td_binary"].to_numpy(int)
    out = {"n_train": len(tr), "n_dev": len(dv),
           "dev_event_rate": float(ydv.mean()), "rungs": {}}
    for rung in RUNGS:
        if rung == "M0":
            p = dv["m0_prob"].to_numpy(float)
            out["rungs"][rung] = {"metrics": full_metrics(ydv, p),
                                  "n": len(dv)}
        else:
            F = fit_rung(tr, dv, rung)
            out["rungs"][rung] = {"metrics": full_metrics(ydv, F["dev_pred"]),
                                  "C": F["C"], "gbm_params": F["gbm_params"],
                                  "n": len(dv), "n_feats": len(F["feats"])}
        m = out["rungs"][rung]["metrics"]
        print(f"[{rung}] dev Brier={m['brier']:.5f} logloss={m['log_loss']:.5f} "
              f"AUC={m['roc_auc']:.4f} slope={m['calibration']['slope']:.3f}",
              flush=True)
    json.dump(out, open(f"{EXP}/data/experiment_003d_dev.json", "w"), indent=1,
              default=str)
    print("DEV PHASE COMPLETE — test slice untouched.")


def test_phase():
    dev_path = f"{EXP}/data/experiment_003d_dev.json"
    assert os.path.exists(dev_path), "run --phase dev first"
    dev_out = json.load(open(dev_path))
    t0 = time.time()
    D = load("test")
    tr, te = D["train"], D["test"]
    yte = te["td_binary"].to_numpy(int)
    print(f"test: n={len(te)} events={int(yte.sum())} "
          f"rate={yte.mean():.4f}", flush=True)

    res, rows = {}, []
    p0 = te["m0_prob"].to_numpy(float)
    res["M0"] = {"metrics": full_metrics(yte, p0), "n": len(te),
                 "n_2023": int((te["season"] == 2023).sum()),
                 "n_2024": int((te["season"] == 2024).sum()),
                 "events": int(yte.sum())}
    res["M0"]["_p"] = p0
    for rung in ["M1", "M2", "M3"]:
        dm = dev_out["rungs"][rung]
        F = fit_rung(tr, None, rung, fixed_C=dm["C"],
                     fixed_gbm=dm["gbm_params"])
        p = F["pred"](te)
        r = {"metrics": full_metrics(yte, p), "n": len(te),
             "n_2023": int((te["season"] == 2023).sum()),
             "n_2024": int((te["season"] == 2024).sum()),
             "events": int(yte.sum()),
             "C": dm["C"], "gbm_params": dm["gbm_params"]}
        # per-season Brier (win-bar condition 2)
        seas = {}
        for s in (2023, 2024):
            idx = (te["season"] == s).to_numpy()
            seas[str(s)] = {"brier": brier(yte[idx], p[idx]),
                            "brier_M0": brier(yte[idx], p0[idx]),
                            "n": int(idx.sum()),
                            "events": int(yte[idx].sum())}
        r["by_season"] = seas
        # paired bootstrap CI of (M0 - rung) Brier difference
        diff = (p0 - yte) ** 2 - (p - yte) ** 2
        bs = np.array([np.mean(RNG.choice(diff, size=len(diff), replace=True))
                       for _ in range(BOOT)])
        r["bootstrap_ci_M0_minus_rung"] = [float(np.percentile(bs, 2.5)),
                                           float(np.percentile(bs, 97.5))]
        r["_p"] = p
        res[rung] = r
        print(f"[{rung}] test Brier={r['metrics']['brier']:.5f} "
              f"vs M0 {res['M0']['metrics']['brier']:.5f} | "
              f"slope={r['metrics']['calibration']['slope']:.3f}",
              flush=True)
        df = te[["player_name", "team", "opponent", "season", "week",
                 "position", "td_binary", "rush_tds", "rec_tds"]].copy()
        df["rung"] = rung
        df["pred_prob"] = p
        rows.append(df)

    # ---- win-bar evaluation ----
    b0 = res["M0"]["metrics"]["brier"]
    verdict = {}
    for rung in ["M1", "M2", "M3"]:
        r = res[rung]
        b = r["metrics"]["brier"]
        rel = (b0 - b) / b0
        s23 = (r["by_season"]["2023"]["brier_M0"] -
               r["by_season"]["2023"]["brier"]) / \
            r["by_season"]["2023"]["brier_M0"]
        s24 = (r["by_season"]["2024"]["brier_M0"] -
               r["by_season"]["2024"]["brier"]) / \
            r["by_season"]["2024"]["brier_M0"]
        ci = r["bootstrap_ci_M0_minus_rung"]
        cal = r["metrics"]["calibration"]
        cal_ok = (cal["max_abs_dev_n100"] is not None and
                  cal["max_abs_dev_n100"] <= 0.06 and
                  0.85 <= cal["slope"] <= 1.15)
        verdict[rung] = {
            "rel_brier_reduction_pooled": rel,
            "s2023": s23, "s2024": s24,
            "ci_excludes_zero": ci[0] > 0,
            "calibration_ok": cal_ok,
            "clears_bar": (rel >= 0.05 and s23 >= 0.02 and s24 >= 0.02 and
                           ci[0] > 0 and cal_ok)}

    out = {"test": {r: {k: v for k, v in res[r].items()
                        if not k.startswith("_")} for r in res},
           "win_bar": verdict,
           "elapsed_s": round(time.time() - t0, 1)}
    json.dump(out, open(f"{EXP}/data/experiment_003d_test.json", "w"), indent=1,
              default=str)
    allp = pd.DataFrame({"player_name": te["player_name"], "team": te["team"],
                         "opponent": te["opponent"], "season": te["season"],
                         "week": te["week"], "position": te["position"],
                         "td_binary": yte, "pred_M0": res["M0"].pop("_p"),
                         "pred_M1": res["M1"].pop("_p"),
                         "pred_M2": res["M2"].pop("_p"),
                         "pred_M3": res["M3"].pop("_p")})
    allp.to_parquet(f"{EXP}/data/experiment_003d_test_predictions.parquet",
                    index=False)
    print("TEST EVALUATION COMPLETE (single pass).")
    for rung, v in verdict.items():
        print(f"[{rung}] clears_bar={v['clears_bar']} "
              f"rel={v['rel_brier_reduction_pooled']:.4f} "
              f"s23={v['s2023']:.4f} s24={v['s2024']:.4f} "
              f"ci0>{0}={v['ci_excludes_zero']} cal_ok={v['calibration_ok']}",
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
