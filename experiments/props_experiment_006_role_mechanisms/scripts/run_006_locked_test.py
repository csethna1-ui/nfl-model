"""
Props Experiment 006 — LOCKED TEST (single evaluation, frozen prereg 2026-10-01).

ONE evaluation on 2023-2024. NO fitting, NO parameter tuning, NO model
selection. Locked parameters from LOCKED_PARAMETERS.json are asserted equal
to the fitted artifacts at eval time; any mismatch aborts.

M0 = frozen Props Model D, reproduced read-only by re-executing the frozen
001 training procedure on train (2018-2020) with the frozen dev-selected
hyperparameters from dry_run_dev.json. Verified bit-identical against the
stored 001 test predictions (experiment_001_test_predictions.parquet, pred_D)
BEFORE any candidate runs.

M1: locked Ridge (scaler + alpha from models/M1_{market}_fitted.pkl).
M2: locked Kalman (q_share, q_eff, r + priors); filter state walked over each
    player's full 2018-2024 history; one-step-ahead predictions at test rows.

Outputs (experiments/props_experiment_006_role_mechanisms/):
  scripts/run_006_locked_test.py
  data/test_predictions.parquet  (M0/M1/M2 predictions on evaluated test rows)
  data/test_results.json          (machine-readable adjudication inputs)
"""
import json
import math
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

EXP = "/home/hatch/workspace/nfl-model/experiments/props_experiment_006_role_mechanisms"
sys.path.insert(0, os.path.join(EXP, "scripts"))
from build_006_dev import (
    fit_A, pred_A, fit_B, pred_B, fit_C, pred_C,
    add_stints, add_contrast_features, kalman_run,
    ukey, mae, MKT_DEF, TEAM_VOL_COL, CONTRAST_MAG, M1_ORDER,
    V0_SHARE, V0_EFF, MAX_TRAIL,
)

TABLE = "/home/hatch/workspace/nfl-model/experiments/player_props_projection/data/modeling_table.parquet"
SEL = "/home/hatch/workspace/nfl-model/experiments/player_props_projection/data/dry_run_dev.json"
P001 = "/home/hatch/workspace/nfl-model/experiments/player_props_projection/data/experiment_001_test_predictions.parquet"
PG = "/home/hatch/workspace/nfl-model/data/player_games.parquet"
SNAP_DIR = "/home/hatch/workspace/nfl-model/data/v2/raw"

SEED = 1337
rng = np.random.default_rng(SEED)
np.random.seed(SEED)
MARKETS = ["pass_yards", "rush_yards", "receiving_yards"]
TEST_SEASONS = (2023, 2024)
N_BOOT = 2000


def build_history_full():
    """One row per player-week (2018-2024). Completed-game records only."""
    import re
    pg = pd.read_parquet(PG)
    pg = pg[pg["season"].between(2018, 2024)].copy()
    assert pg["season"].max() <= 2024 and pg["season"].min() >= 2018

    tm = (pg.groupby(["game_id", "team"], as_index=False)[["rush_att", "targets", "pass_att"]]
            .sum().rename(columns={"rush_att": "team_rush", "targets": "team_targets",
                                    "pass_att": "team_pass"}))
    pg = pg.merge(tm, on=["game_id", "team"], how="left")
    pg["rush_share_g"] = pg["rush_att"] / pg["team_rush"].replace(0, np.nan)
    pg["target_share_g"] = pg["targets"] / pg["team_targets"].replace(0, np.nan)
    pg["pass_share_g"] = pg["pass_att"] / pg["team_pass"].replace(0, np.nan)
    for c in ("rush_share_g", "target_share_g", "pass_share_g"):
        pg[c] = pg[c].fillna(0.0)

    def _ukey(name):
        s = str(name).lower().strip()
        s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)\.?$", "", s)
        s = re.sub(r"\.", " ", s)
        toks = [t for t in s.split() if t]
        if len(toks) < 2:
            return None
        return f"{toks[0][0]}.{toks[-1]}"

    sn_parts = [pd.read_csv(os.path.join(SNAP_DIR, f"snap_counts_{s}.csv"))
                for s in range(2018, 2025)]
    sn = pd.concat(sn_parts, ignore_index=True)
    sn = sn[sn["game_type"] == "REG"].copy()
    sn["sukey"] = sn["player"].map(_ukey) + "|" + sn["team"]
    sn = (sn.sort_values("offense_pct")
            .drop_duplicates(["sukey", "season", "week"], keep="last"))
    pg["sukey"] = pg["player_name"].map(_ukey) + "|" + pg["team"]
    pg = pg.merge(sn[["sukey", "season", "week", "offense_pct"]],
                  on=["sukey", "season", "week"], how="left")
    print(f"  snap merge rate: {pg['offense_pct'].notna().mean():.4f}", flush=True)
    pg["snap_g"] = pg["offense_pct"].fillna(0.0)

    ndup = int(pg.duplicated(["player_name", "season", "week"]).sum())
    if ndup:
        pg = (pg.sort_values("touches", ascending=False)
                .drop_duplicates(["player_name", "season", "week"])
                .reset_index(drop=True))
        print(f"  history: dropped {ndup} phantom player-week rows (name collisions)", flush=True)
    assert pg.duplicated(["player_name", "season", "week"]).sum() == 0
    return pg.sort_values(["player_name", "season", "week"]).reset_index(drop=True)


def build_test_bundles(hist, ev, market, locked_m2):
    """Per-player bundles walked over full 2018-2024 history; is_eval = test rows."""
    d = MKT_DEF[market]
    evm = ev[(ev["market"] == market) & (ev["period"] == "test")].reset_index(drop=True)
    keys = set(zip(evm["player_name"], evm["season"], evm["week"]))
    evm_lookup = (evm.drop_duplicates(["player_name", "season", "week"])
                     .set_index(["player_name", "season", "week"]))
    sub = hist[hist["player_name"].isin(evm["player_name"].unique())].copy()
    sub = sub.sort_values(["player_name", "season", "week"]).reset_index(drop=True)
    sub["is_eval"] = [k in keys for k in
                      zip(sub["player_name"], sub["season"], sub["week"])]
    sub["team_vol"] = np.nan
    sub["actual"] = np.nan
    has = sub["is_eval"].to_numpy()
    idx_keys = list(zip(sub.loc[has, "player_name"], sub.loc[has, "season"], sub.loc[has, "week"]))
    sub.loc[has, "team_vol"] = [evm_lookup.loc[k, TEAM_VOL_COL[market]] for k in idx_keys]
    sub.loc[has, "actual"] = [evm_lookup.loc[k, "actual_yards"] for k in idx_keys]
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


def boot_ci(y, p0, p1, n_boot=N_BOOT, seed=SEED):
    """Paired bootstrap CI of (M0 - rung) MAE. Positive = rung better."""
    r = np.random.default_rng(seed)
    d = np.abs(y - p0) - np.abs(y - p1)
    n = len(d)
    means = np.empty(n_boot)
    for b in range(n_boot):
        idx = r.integers(0, n, n)
        means[b] = d[idx].mean()
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(d.mean()), float(lo), float(hi)


def main():
    t0 = time.time()
    sel = json.load(open(SEL))["selection"]
    locked = json.load(open(f"{EXP}/LOCKED_PARAMETERS.json"))
    os.makedirs(f"{EXP}/data", exist_ok=True)

    full = pd.read_parquet(TABLE)
    ev = full[(full["eligible_hist"] == 1) & (full["played_role"] == 1)].copy()
    train = {m: ev[(ev["period"] == "train") & (ev["market"] == m)].reset_index(drop=True)
             for m in MARKETS}
    test_all = {m: ev[(ev["period"] == "test") & (ev["market"] == m)].reset_index(drop=True)
                for m in MARKETS}
    for m in MARKETS:
        assert set(test_all[m]["season"].unique()) <= set(TEST_SEASONS)

    # ---- M0: reproduce frozen Model D read-only (train only) ----
    m0_test = {}
    for market in MARKETS:
        tr, te = train[market], test_all[market]
        A = fit_A(tr, sel[market]["a_alpha"])
        B = fit_B(tr, sel[market]["b_params"])
        C = fit_C(tr)
        m0_test[market] = (pred_A(A, te) + pred_B(B, te) + pred_C(C, te)) / 3.0
    print("M0 reproduced read-only (train fit only)", flush=True)

    # ---- M0 bit-identical verification BEFORE any candidate runs ----
    p001 = pd.read_parquet(P001)
    for market in MARKETS:
        te = test_all[market]
        mine = pd.DataFrame({
            "player_name": te["player_name"], "team": te["team"],
            "opponent": te["opponent"], "season": te["season"],
            "week": te["week"], "market": te["market"], "m0_mine": m0_test[market]})
        mg = mine.merge(p001[["player_name", "team", "opponent", "season",
                              "week", "market", "pred_D"]],
                        on=["player_name", "team", "opponent", "season", "week", "market"],
                        how="inner", validate="m:1")
        assert len(mg) == len(mine), f"M0 verify join incomplete for {market}"
        maxdiff = float(np.max(np.abs(mg["m0_mine"] - mg["pred_D"])))
        assert maxdiff == 0.0, f"M0 NOT bit-identical for {market}: max diff {maxdiff}"
        print(f"[{market}] M0 bit-identical vs 001 test predictions "
              f"(max diff {maxdiff:.2e}, n={len(mg)})", flush=True)

    # ---- assert locked configs equal frozen parameters (no silent drift) ----
    m1_models, m2_params = {}, {}
    for market in MARKETS:
        with open(f"{EXP}/models/M1_{market}_fitted.pkl", "rb") as f:
            m1 = pickle.load(f)
        assert m1["alpha"] == locked[market]["M1"]["alpha"], "M1 alpha drift!"
        assert m1["order"] == locked[market]["M1"]["order"], "M1 order drift!"
        m1_models[market] = m1
        with open(f"{EXP}/models/M2_{market}_params.json") as f:
            m2 = json.load(f)
        for k in ("q_share", "q_eff", "r", "prior_share", "prior_eff"):
            assert m2[k] == locked[market]["M2"][k], f"M2 {k} drift for {market}!"
        m2_params[market] = m2
    print("LOCKED CONFIGS VERIFIED: all artifacts equal LOCKED_PARAMETERS.json", flush=True)

    # ---- per-game history 2018-2024, stints, contrasts ----
    print("building per-game history (2018-2024)...", flush=True)
    hist = build_history_full()
    hist = add_stints(hist)
    print("computing contrast features...", flush=True)
    hist = add_contrast_features(hist)

    FEAT_COLS = ["player_name", "season", "week"] + M1_ORDER[1:] + ["in_transfer_stint"]
    results, pred_rows = {}, {}
    for market in MARKETS:
        te = test_all[market]
        mg = te.merge(hist[FEAT_COLS].drop_duplicates(["player_name", "season", "week"]),
                      on=["player_name", "season", "week"], how="left",
                      validate="m:1", indicator=True)
        rate = (mg["_merge"] == "both").mean()
        print(f"[{market}] feature join rate: {rate:.4f} (n={len(te)})", flush=True)
        assert rate >= 0.99, f"feature join rate too low for {market}"
        dv = mg[mg["_merge"] == "both"].reset_index(drop=True)
        y = dv["actual_yards"].to_numpy(float)
        # m0 on the joined rows via index alignment (same rows all rungs use)
        keep = (mg["_merge"] == "both").to_numpy()
        m0 = m0_test[market][keep]
        print(f"[{market}] evaluated n={len(dv)}", flush=True)

        # ---- M1: locked Ridge, predict only ----
        s, mdl = m1_models[market]["model"]
        X1 = np.column_stack([m0, dv[M1_ORDER[1:]].to_numpy(float)])
        m1_pred = mdl.predict(s.transform(X1))

        # ---- M2: locked Kalman, predict only ----
        mp = m2_params[market]
        bundles = build_test_bundles(hist, ev, market, mp)
        print(f"[{market}] walking {len(bundles)} players (locked Kalman)...", flush=True)
        _, m2_pu, _ = kalman_run(bundles, mp["q_share"], mp["q_eff"], mp["r"],
                                 mp["prior_share"], mp["prior_eff"])
        key2pred = {}
        i = 0
        for b in bundles:
            for k in b["keys"]:
                key2pred[k] = m2_pu[i]
                i += 1
        dv_keys = list(zip(dv["player_name"], dv["season"], dv["week"]))
        m2_pred = np.array([key2pred[k] for k in dv_keys])
        assert len(m2_pred) == len(dv)

        preds = {"M0": m0, "M1": m1_pred, "M2": m2_pred}

        # ---- slices ----
        in_ts = (dv["in_transfer_stint"] == 1.0).to_numpy()
        sg = dv["stint_games"].to_numpy()
        season = dv["season"].to_numpy()
        mag = np.abs(dv[CONTRAST_MAG[market]].to_numpy(float))
        hi_thr = float(np.quantile(mag, 0.9))
        slices = {
            "overall": np.ones(len(dv), bool),
            "transfer_stint": in_ts,
            "stint_1_3": in_ts & (sg <= 2),
            "stint_4_6": in_ts & (sg >= 3) & (sg <= 5),
            "high_contrast": mag >= hi_thr,
            "non_transfer": ~in_ts,
            "y2023": season == 2023,
            "y2024": season == 2024,
        }
        out = {"n": len(dv), "rungs": {}, "slices": {}, "bootstrap": {}}
        for rung in ("M0", "M1", "M2"):
            p = preds[rung]
            err = np.abs(y - p)
            out["rungs"][rung] = {
                "mae": float(err.mean()),
                "rmse": float(np.sqrt(np.mean((y - p) ** 2))),
                "bias": float(np.mean(p - y)),
            }
            out["slices"][rung] = {}
            for sname, mask in slices.items():
                n = int(mask.sum())
                out["slices"][rung][sname] = {
                    "n": n,
                    "mae": float(np.mean(np.abs(y[mask] - p[mask]))) if n else None,
                }
        m0_mae = out["rungs"]["M0"]["mae"]
        for rung in ("M1", "M2"):
            out["bootstrap"][rung] = {}
            for sname in ("overall", "transfer_stint"):
                mask = slices[sname]
                mean_d, lo, hi = boot_ci(y[mask], preds["M0"][mask], preds[rung][mask])
                out["bootstrap"][rung][sname] = {"mean_diff": mean_d, "lo": lo, "hi": hi,
                                                "n": int(mask.sum())}
        # relative changes vs M0
        out["rel"] = {}
        for rung in ("M1", "M2"):
            out["rel"][rung] = {}
            for sname in slices:
                a = out["slices"]["M0"][sname]["mae"]
                b = out["slices"][rung][sname]["mae"]
                out["rel"][rung][sname] = (None if (a is None or b is None or a == 0)
                                           else float((a - b) / a))

        # ---- win-bar adjudication (prereg §5) ----
        bar = {}
        for rung in ("M1", "M2"):
            r = out["rel"][rung]
            c_ov = out["bootstrap"][rung]["overall"]
            c_ts = out["bootstrap"][rung]["transfer_stint"]
            cond1 = (r["overall"] is not None and r["overall"] >= 0.05
                     and r["transfer_stint"] is not None and r["transfer_stint"] >= 0.05)
            cond2 = (r["y2023"] is not None and r["y2023"] >= 0.02
                     and r["y2024"] is not None and r["y2024"] >= 0.02)
            cond3 = (c_ov["lo"] > 0) and (c_ts["lo"] > 0)
            cond4 = (r["non_transfer"] is not None and r["non_transfer"] >= -0.01)
            passed = cond1 and cond2 and cond3 and cond4
            # PARTIAL-SIGNAL: CI excludes zero in the right direction but sub-bar
            partial = (not passed) and (c_ov["lo"] > 0 or c_ts["lo"] > 0)
            bar[rung] = {
                "cond1_pooled5pct": bool(cond1),
                "cond2_peryear2pct": bool(cond2),
                "cond3_ci_excludes_zero": bool(cond3),
                "cond4_regression_guard": bool(cond4),
                "verdict": ("MATERIAL WIN" if passed
                            else ("PARTIAL-SIGNAL" if partial else "NULL")),
            }
        out["win_bar"] = bar
        results[market] = out

        pr = dv[["player_name", "team", "opponent", "season", "week",
                 "actual_yards", "in_transfer_stint"] + M1_ORDER[1:]].copy()
        pr["market"] = market
        pr["pred_M0"] = m0
        pr["pred_M1"] = m1_pred
        pr["pred_M2"] = m2_pred
        pred_rows[market] = pr
        print(f"[{market}] M0 {m0_mae:.4f} | "
              f"M1 {out['rungs']['M1']['mae']:.4f} ({out['rel']['M1']['overall']:+.2%}) | "
              f"M2 {out['rungs']['M2']['mae']:.4f} ({out['rel']['M2']['overall']:+.2%})",
              flush=True)

    pd.concat(pred_rows, ignore_index=True).to_parquet(
        f"{EXP}/data/test_predictions.parquet", index=False)
    with open(f"{EXP}/data/test_results.json", "w") as f:
        json.dump(results, f, indent=1)
    print(f"\nlocked test complete ({time.time()-t0:.0f}s). "
          f"NO fitting was performed.", flush=True)
    return results


if __name__ == "__main__":
    main()
