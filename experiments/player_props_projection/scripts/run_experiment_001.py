"""
Player Projection Experiment 001 — modeling execution.

Binding spec: ../PREREGISTRATION.md (APPROVED AND RE-FROZEN 2026-09-30).
Discipline: fit on train (2018-2020) ONLY; select on dev (2021-2022) ONLY;
evaluate on locked test (2023-2024) ONCE at the end. No test iteration.

Models:
  Baseline: trail yards EWMA, no matchup adjustment (no fitting).
  A: two-stage opportunity x efficiency (Ridge stage1 on opportunity feats,
     Ridge stage2 on efficiency feats; alpha chosen on dev).
  B: HistGradientBoostingRegressor on all allowable features (small grid, dev-selected).
  C: quantile GBM (P25/median/P75), median graded; hyperparams fixed a priori.
  D: PRIMARY = equal-weight mean of A/B/C point projections.
  D-variant: NNLS weights fit on dev ONLY, frozen, reported separately.

Usage:
  python run_experiment_001.py --dry-run   # train/dev only, validates pipeline
  python run_experiment_001.py             # full run incl. single test evaluation
"""
import argparse, json, sys, time
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from scipy.optimize import nnls

RNG = np.random.default_rng(1337)
BOOT = 2000

EXP = "/home/hatch/workspace/nfl-model/experiments/player_props_projection"
TABLE = f"{EXP}/data/modeling_table.parquet"

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
MARKETS = ["pass_yards", "rush_yards", "receiving_yards"]
MARKET_YARDS_COL = {"pass_yards": "trail_pass_yards_ewma",
                    "rush_yards": "trail_rush_yards_ewma",
                    "receiving_yards": "trail_receiving_yards_ewma"}

A_ALPHAS = [0.1, 1.0, 10.0, 100.0]
B_GRID = [{"learning_rate": lr, "max_depth": md, "max_iter": mi}
          for lr in (0.05, 0.1) for md in (3, 5) for mi in (200, 500)]
C_PARAMS = dict(loss="quantile", learning_rate=0.1, max_depth=3,
                max_iter=300, min_samples_leaf=20, random_state=7)


def mae(y, p):
    return float(np.mean(np.abs(y - p)))


def load():
    t = pd.read_parquet(TABLE)
    ev = t[(t["eligible_hist"] == 1) & (t["played_role"] == 1)].copy()
    return {p: {m: ev[(ev["period"] == p) & (ev["market"] == m)].reset_index(drop=True)
                for m in MARKETS} for p in ("train", "dev", "test")}


def baseline_pred(df, market):
    return df[MARKET_YARDS_COL[market]].to_numpy(dtype=float)


def fit_A(train, market, alpha):
    """Two-stage: Ridge(actual_att ~ opp feats) x Ridge(yards/att ~ eff feats)."""
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


def fit_B(train, market, params):
    X = train[ALL_FEATS].to_numpy(float)
    y = train["actual_yards"].to_numpy(float)
    m = HistGradientBoostingRegressor(random_state=11, **params)
    return m.fit(X, y)


def pred_B(model, df):
    return np.maximum(model.predict(df[ALL_FEATS].to_numpy(float)), 0.0)


def fit_C(train, market):
    X = train[ALL_FEATS].to_numpy(float)
    y = train["actual_yards"].to_numpy(float)
    out = {}
    for q in (0.25, 0.5, 0.75):
        out[q] = HistGradientBoostingRegressor(quantile=q, **C_PARAMS).fit(X, y)
    return out


def pred_C(model, df, q=0.5):
    return np.maximum(model[q].predict(df[ALL_FEATS].to_numpy(float)), 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    D = load()

    # ---- fit on train, select on dev ----
    fitted = {}   # fitted[market] = dict of models + chosen params
    dev_mae = {}
    for market in MARKETS:
        tr, dv = D["train"][market], D["dev"][market]
        ytr, ydv = tr["actual_yards"].to_numpy(float), dv["actual_yards"].to_numpy(float)

        # A: alpha on dev
        a_cands = {}
        for a in A_ALPHAS:
            m = fit_A(tr, market, a)
            a_cands[a] = (m, mae(ydv, pred_A(m, dv)))
        a_alpha = min(a_cands, key=lambda a: a_cands[a][1])
        A = a_cands[a_alpha][0]

        # B: grid on dev
        b_cands = {}
        for i, gp in enumerate(B_GRID):
            m = fit_B(tr, market, gp)
            b_cands[i] = (m, mae(ydv, pred_B(m, dv)), gp)
        b_key = min(b_cands, key=lambda i: b_cands[i][1])
        B, b_params = b_cands[b_key][0], b_cands[b_key][2]

        # C: fixed params
        C = fit_C(tr, market)

        fitted[market] = {"A": A, "B": B, "C": C,
                          "a_alpha": a_alpha, "b_params": b_params}

        pA, pB, pC = pred_A(A, dv), pred_B(B, dv), pred_C(C, dv)
        pD = (pA + pB + pC) / 3.0
        # D-variant: NNLS weights on dev
        w, _ = nnls(np.column_stack([pA, pB, pC]), ydv)
        w = w / w.sum() if w.sum() > 0 else np.full(3, 1 / 3)
        pDv = w[0] * pA + w[1] * pB + w[2] * pC
        fitted[market]["d_weights"] = w
        dev_mae[market] = {
            "baseline": mae(ydv, baseline_pred(dv, market)),
            "A": mae(ydv, pA), "B": mae(ydv, pB), "C": mae(ydv, pC),
            "D": mae(ydv, pD), "D_variant": mae(ydv, pDv),
            "n": len(dv),
        }
        print(f"[{market}] dev MAE " +
              " ".join(f"{k}={v:.2f}" for k, v in dev_mae[market].items() if k != "n"),
              f"| a_alpha={a_alpha} b={b_params} d_w={np.round(w,3)}", flush=True)

    out = {"dev_mae": dev_mae,
           "selection": {m: {"a_alpha": fitted[m]["a_alpha"],
                             "b_params": fitted[m]["b_params"],
                             "d_weights": fitted[m]["d_weights"].tolist()}
                         for m in MARKETS}}
    if args.dry_run:
        print("DRY RUN OK — test slice untouched.")
        json.dump(out, open(f"{EXP}/data/dry_run_dev.json", "w"), indent=1)
        return

    # ---- SINGLE locked-test evaluation ----
    test_rows = []
    test_mae = {}
    for market in MARKETS:
        te = D["test"][market]
        yte = te["actual_yards"].to_numpy(float)
        F = fitted[market]
        preds = {
            "baseline": baseline_pred(te, market),
            "A": pred_A(F["A"], te), "B": pred_B(F["B"], te),
            "C": pred_C(F["C"], te),
        }
        preds["D"] = (preds["A"] + preds["B"] + preds["C"]) / 3.0
        w = F["d_weights"]
        preds["D_variant"] = w[0] * preds["A"] + w[1] * preds["B"] + w[2] * preds["C"]
        preds["C_p25"] = pred_C(F["C"], te, 0.25)
        preds["C_p75"] = pred_C(F["C"], te, 0.75)
        test_mae[market] = {k: mae(yte, v) for k, v in preds.items()
                            if k in ("baseline", "A", "B", "C", "D", "D_variant")}
        test_mae[market]["n"] = len(te)
        test_mae[market]["n_2023"] = int((te["season"] == 2023).sum())
        test_mae[market]["n_2024"] = int((te["season"] == 2024).sum())

        # per-season MAE for the consistency condition
        seas = {}
        for s in (2023, 2024):
            idx = (te["season"] == s).to_numpy()
            seas[str(s)] = {k: mae(yte[idx], v[idx]) for k, v in preds.items()
                            if k in ("baseline", "A", "B", "C", "D", "D_variant")}
            seas[str(s)]["n"] = int(idx.sum())
        test_mae[market]["by_season"] = seas

        # paired bootstrap CI of (baseline - model) MAE difference, per market/model
        base_ae = np.abs(yte - preds["baseline"])
        boot = {}
        for k in ("A", "B", "C", "D", "D_variant"):
            diff = base_ae - np.abs(yte - preds[k])
            bs = np.array([np.mean(RNG.choice(diff, size=len(diff), replace=True))
                           for _ in range(BOOT)])
            boot[k] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
        test_mae[market]["bootstrap_ci"] = boot

        # secondary: top decile of baseline absolute errors
        thr = np.percentile(base_ae, 90)
        top = base_ae >= thr
        rest = ~top
        sec = {"threshold": float(thr), "n_top": int(top.sum())}
        for k in ("baseline", "A", "B", "C", "D"):
            sec[k + "_top_mae"] = mae(yte[top], preds[k][top])
            sec[k + "_rest_mae"] = mae(yte[rest], preds[k][rest])
        test_mae[market]["secondary_topdecile"] = sec

        df = te[["player_name", "team", "opponent", "season", "week",
                 "position", "actual_yards"]].copy()
        df["market"] = market
        for k, v in preds.items():
            df["pred_" + k] = v
        test_rows.append(df)

    out["test_mae"] = test_mae
    out["elapsed_s"] = round(time.time() - t0, 1)
    json.dump(out, open(f"{EXP}/data/experiment_001_results.json", "w"), indent=1)
    pd.concat(test_rows, ignore_index=True).to_parquet(
        f"{EXP}/data/experiment_001_test_predictions.parquet", index=False)
    print("TEST EVALUATION COMPLETE (single pass).")
    for market in MARKETS:
        r = test_mae[market]
        b = r["baseline"]
        line = " ".join(
            f"{k}={v:.2f}({(b-v)/b*100:+.1f}%)" for k, v in r.items()
            if k in ("A", "B", "C", "D", "D_variant"))
        print(f"[{market}] baseline={b:.2f} n={r['n']} | {line}", flush=True)


if __name__ == "__main__":
    main()
