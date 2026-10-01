"""
Props Experiment 005 — SINGLE locked-test evaluation (frozen preregistration 2026-10-01).

AUTHORIZED SEQUENCE: FREEZE -> DEV (done) -> LOCK PARAMETERS (done) -> THIS.
This script runs EXACTLY ONCE. No refitting, no parameter tuning, no model
selection. A null is a legitimate preregistered outcome.

- M0 = frozen Props Model D (Experiment 001 procedure, fit on train ONLY with
  frozen dev-selected hyperparameters; verified bit-identical vs stored 001
  test predictions before any candidate evaluation).
- M1/M2/M3 = fitted models in models/ (fit on dev), applied to test rows with
  the EXACT locked structural parameters in LOCKED_PARAMETERS.json. Values are
  read from the pickle files; this script asserts they match the JSON.
- Test population: period == 'test' (2023-2024), eligible_hist==1 & played_role==1.
- Stint features: built on ALL rows per market (train+dev+test walk, strictly
  prior games only -> Friday 18:00 CT safe), merged m:1 onto eligible test rows
  (same name-collision convention as dev).
- Market line is never a feature.

Outputs:
  data/test_predictions.parquet   (M0 + M1/M2/M3 test predictions, test rows only)
  data/locked_test_metrics.json   (all metrics, slices, bootstrap CIs)
"""
import json, pickle, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/hatch/workspace/nfl-model/experiments/props_experiment_005_role_transition/scripts")
import build_005_dev as D  # reuse frozen dev helpers (feature builders, M0 fitters)

EXP = "/home/hatch/workspace/nfl-model/experiments/props_experiment_005_role_transition"
TABLE = "/home/hatch/workspace/nfl-model/experiments/player_props_projection/data/modeling_table.parquet"
SEL = "/home/hatch/workspace/nfl-model/experiments/player_props_projection/data/dry_run_dev.json"
STORED_001 = "/home/hatch/workspace/nfl-model/experiments/player_props_projection/data/experiment_001_test_predictions.parquet"

MARKETS = ["pass_yards", "rush_yards", "receiving_yards"]
SEED = 1337
BOOT = 2000
FEAT_COLS = ["player_name", "season", "week", "stint_games", "transfer_ind",
             "opp_cur", "opp_prior", "eff_cur", "eff_prior", "in_transfer_stint"]


def mae(y, p):
    return float(np.mean(np.abs(y - p)))


def paired_bootstrap_ci(y, p0, p1, n_boot=BOOT, seed=SEED):
    """95% CI of mean(|y-p0| - |y-p1|); positive favors p1 (challenger)."""
    rng = np.random.default_rng(seed)
    diff = np.abs(y - p0) - np.abs(y - p1)
    n = len(diff)
    bs = np.empty(n_boot)
    for i in range(n_boot):
        bs[i] = np.mean(diff[rng.integers(0, n, n)])
    return float(np.mean(diff)), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def main():
    t0 = time.time()
    locked = json.load(open(f"{EXP}/LOCKED_PARAMETERS.json"))
    sel = json.load(open(SEL))["selection"]
    stored = pd.read_parquet(STORED_001)

    full = pd.read_parquet(TABLE)
    ev = full[(full["eligible_hist"] == 1) & (full["played_role"] == 1)].copy()

    all_metrics, pred_rows = {}, []
    for market in MARKETS:
        tr = ev[(ev["period"] == "train") & (ev["market"] == market)].reset_index(drop=True)

        # ---- stint features: walk on ALL rows (train+dev+test), strictly-prior games ----
        hist = full[full["market"] == market].reset_index(drop=True)
        hmf = D.build_stint_features(hist)
        direct = ev[(ev["period"] == "test") & (ev["market"] == market)].reset_index(drop=True)
        te = direct.merge(hmf[FEAT_COLS], on=["player_name", "season", "week"],
                          how="left", validate="m:1")
        assert te[FEAT_COLS[3:]].notna().all().all(), f"stint join NaNs for {market}"
        y = te["actual_yards"].to_numpy(float)

        # ---- M0: frozen 001 procedure on train, predict test ----
        A = D.fit_A(tr, sel[market]["a_alpha"])
        B = D.fit_B(tr, sel[market]["b_params"])
        C = D.fit_C(tr)
        m0 = (D.pred_A(A, te) + D.pred_B(B, te) + D.pred_C(C, te)) / 3.0

        # bit-identical verification vs stored 001 test predictions (read-only)
        st = stored[stored["market"] == market].sort_values(
            ["player_name", "season", "week"]).reset_index(drop=True)
        te_s = te.sort_values(["player_name", "season", "week"]).reset_index(drop=True)
        assert (st["player_name"].to_numpy() == te_s["player_name"].to_numpy()).all()
        assert (st["season"].to_numpy() == te_s["season"].to_numpy()).all()
        assert (st["week"].to_numpy() == te_s["week"].to_numpy()).all()
        m0_s = m0[te.sort_values(["player_name", "season", "week"]).index.to_numpy()]
        maxdiff = float(np.max(np.abs(m0_s - st["pred_D"].to_numpy(float))))
        assert maxdiff < 1e-9, f"M0 mismatch vs stored 001 test preds: {maxdiff}"
        print(f"[{market}] M0 bit-identical vs stored 001 test preds (max diff {maxdiff:.2e}), n={len(te)}", flush=True)

        # ---- candidates: exact locked models + locked structural params ----
        preds = {"M0": m0}
        for rung in ("M1", "M2", "M3"):
            with open(f"{EXP}/models/{rung}_{market}_fitted.pkl", "rb") as f:
                saved = pickle.load(f)
            lj = locked[market][rung]
            assert saved["struct"] == lj["struct"], f"struct mismatch {rung}/{market}"
            assert saved["class"] == lj["class"] and saved["hyper"] == lj["hyper"]
            assert saved["order"] == lj["order"]
            X, order = D.rung_features(rung, te, m0, **saved["struct"])
            assert order == saved["order"]
            mdl = saved["model"]
            if saved["class"] == "ridge":
                p = D.pred_ridge(mdl, X)
            else:
                p = np.maximum(mdl.predict(X), 0.0)
            preds[rung] = p
            print(f"[{market}] {rung}: test MAE {mae(y, p):.4f} (M0 {mae(y, m0):.4f})", flush=True)

        # ---- slices ----
        in_ts = (te["in_transfer_stint"] == 1.0).to_numpy()
        sg = te["stint_games"].to_numpy()
        seas = te["season"].to_numpy()
        slices = {
            "overall": np.ones(len(te), bool),
            "transfer_stint": in_ts,
            "stint_1_3": in_ts & (sg <= 2),
            "stint_4_6": in_ts & (sg >= 3) & (sg <= 5),
            "stint_7p": in_ts & (sg >= 6),
            "non_transfer": ~in_ts,
            "y2023": seas == 2023,
            "y2024": seas == 2024,
            "transfer_y2023": in_ts & (seas == 2023),
            "transfer_y2024": in_ts & (seas == 2024),
        }
        m = {"n": len(te), "slices": {}, "bootstrap": {}, "secondary": {}}
        m0_mae = mae(y, m0)
        for sname, mask in slices.items():
            n = int(mask.sum())
            row = {"n": n}
            for rung in ("M0", "M1", "M2", "M3"):
                if n:
                    pm = preds[rung][mask]
                    row[rung] = {
                        "mae": mae(y[mask], pm),
                        "rmse": float(np.sqrt(np.mean((y[mask] - pm) ** 2))),
                        "bias": float(np.mean(pm - y[mask])),
                    }
                else:
                    row[rung] = None
            m["slices"][sname] = row
        # paired bootstrap CIs: overall and transfer_stint, per rung
        for sname in ("overall", "transfer_stint"):
            mask = slices[sname]
            m["bootstrap"][sname] = {}
            for rung in ("M1", "M2", "M3"):
                md, lo, hi = paired_bootstrap_ci(y[mask], m0[mask], preds[rung][mask])
                m["bootstrap"][sname][rung] = {
                    "mean_diff": md, "ci_lo": lo, "ci_hi": hi,
                    "rel_reduction": md / mae(y[mask], m0[mask]),
                }
        all_metrics[market] = m

        pr = te[["player_name", "team", "opponent", "season", "week", "position",
                 "actual_yards", "stint_games", "transfer_ind", "in_transfer_stint"]].copy()
        pr["market"] = market
        for r in ("M0", "M1", "M2", "M3"):
            pr["pred_" + r] = preds[r]
        pred_rows.append(pr)

    pd.concat(pred_rows, ignore_index=True).to_parquet(
        f"{EXP}/data/test_predictions.parquet", index=False)
    json.dump(all_metrics, open(f"{EXP}/data/locked_test_metrics.json", "w"), indent=1)
    print(f"LOCKED-TEST EVALUATION COMPLETE (single pass, {time.time()-t0:.0f}s).", flush=True)


if __name__ == "__main__":
    main()
