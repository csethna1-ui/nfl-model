"""V2 Phase 5 evaluation — RUN ONCE per the frozen protocol.

Reads pred_v2{abcd}.parquet (2021–2022), joins labels + V1 baseline, computes
the 14 protocol metrics and gates G1–G3/G5 per candidate. G4 (leakage code
audit) and G6 (timestamp defensibility) are recorded from the manifests'
checklists. No ATS/ROI anywhere. Writes validation_results.json +
validation_report.md. Run once; failed gates stay failed.
"""
import json
import numpy as np
import pandas as pd

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = REPO_ROOT
CANDS = ["a", "b", "c", "d"]
N_BOOT = 10000
SEED = 20260929

def calib_intercept_slope(y, p):
    X = np.column_stack([np.ones_like(p), p])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(coef[0]), float(coef[1])

def main():
    vp = pd.read_parquet(f"{REPO}/data/games_with_preds.parquet")
    vp = vp[(vp.season.isin([2021, 2022])) & (vp.game_type == "REG")]
    base = vp[["game_id", "season", "week", "home_team", "away_team",
               "home_margin", "ens_margin", "spread_line"]].copy()
    base = base.rename(columns={"ens_margin": "v1_pred"})
    base["v1_err"] = base["home_margin"] - base["v1_pred"]
    base["v1_ae"] = base["v1_err"].abs()

    rng = np.random.default_rng(SEED)
    results = {"scope": "2021–2022 REG, V2-defined games only (fallback excluded); one run",
               "n_bootstrap": N_BOOT, "candidates": {}}

    for c in CANDS:
        pred = pd.read_parquet(f"{REPO}/data/v2/pred_v2{c}.parquet")
        man = json.load(open(f"{REPO}/data/v2/manifest_v2{c}.json"))
        df = base.merge(pred[["game_id", "pred_margin", "fallback_flag"]],
                        on="game_id", how="inner")
        n_all = len(df)
        df = df[~df["fallback_flag"]].reset_index(drop=True)
        df["pred"] = df["pred_margin"]
        df["err"] = df["home_margin"] - df["pred"]
        df["ae"] = df["err"].abs()
        y, p = df["home_margin"].to_numpy(), df["pred"].to_numpy()

        mae = float(df["ae"].mean())
        v1_mae = float(df["v1_ae"].mean())
        # G1: paired bootstrap on (ae_v1 - ae_v2)
        diff = (df["v1_ae"] - df["ae"]).to_numpy()
        boots = np.array([rng.choice(diff, size=len(diff), replace=True).mean()
                          for _ in range(N_BOOT)])
        p_val = float(2 * min((boots <= 0).mean(), (boots >= 0).mean()))
        ci_lo, ci_hi = float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))

        a_int, a_slope = calib_intercept_slope(y, p)
        by_season = {str(s): {"mae": float(g["ae"].mean()),
                              "v1_mae": float(g["v1_ae"].mean()), "n": int(len(g))}
                     for s, g in df.groupby("season")}
        buckets = {}
        for lo, hi, name in [(0, 3, "0-3"), (3, 7, "3-7"), (7, 14, "7-14"), (14, 99, "14+")]:
            g = df[(df["pred"].abs() >= lo) & (df["pred"].abs() < hi)]
            if len(g):
                buckets[name] = {"mae": float(g["ae"].mean()),
                                 "v1_mae": float(g["v1_ae"].mean()), "n": int(len(g))}
        err_corr_v1 = float(df["err"].corr(df["v1_err"]))
        miss = float(df["pred"].isna().mean())

        g1 = mae < v1_mae and p_val < 0.05
        g2 = all(v["mae"] < v["v1_mae"] for v in by_season.values())
        bias = float(df["err"].mean())
        g3 = abs(bias) < 1.0 and 0.8 <= a_slope <= 1.2
        g5 = err_corr_v1 < 0.98
        # G4/G6 from manifest checklists (code audit recorded at build).
        # Values may carry annotations, e.g. "PASS (detail)" — accept any
        # value whose stripped form starts with "PASS".
        lc = man.get("leakage_checklist", {})
        g4 = bool(lc) and all(str(v).strip().startswith("PASS") for v in lc.values())
        g6 = bool(man.get("timestamp_policy_attestation"))

        results["candidates"][f"V2-{c.upper()}"] = {
            "n_games_all": n_all, "n_v2_defined": int(len(df)),
            "n_fallback": int(n_all - len(df)),
            "frozen_alpha": man.get("frozen_alpha"),
            "mae": round(mae, 4), "v1_mae": round(v1_mae, 4),
            "mae_diff_v1_minus_v2": round(v1_mae - mae, 4),
            "bootstrap_ci_95": [round(ci_lo, 4), round(ci_hi, 4)],
            "bootstrap_p": round(p_val, 4),
            "rmse": round(float(np.sqrt((df["err"] ** 2).mean())), 4),
            "signed_bias": round(bias, 4),
            "calibration_intercept": round(a_int, 4),
            "calibration_slope": round(a_slope, 4),
            "error_sd": round(float(df["err"].std()), 4),
            "pred_actual_corr": round(float(df["home_margin"].corr(df["pred"])), 4),
            "error_corr_v1": round(err_corr_v1, 4),
            "by_season": {k: {"mae": round(v["mae"], 4), "v1_mae": round(v["v1_mae"], 4), "n": v["n"]}
                          for k, v in by_season.items()},
            "by_pred_magnitude": {k: {"mae": round(v["mae"], 3), "v1_mae": round(v["v1_mae"], 3), "n": v["n"]}
                                  for k, v in buckets.items()},
            "missing_pred_frac": miss,
            "gates": {"G1_paired_improvement": bool(g1), "G2_both_seasons": bool(g2),
                      "G3_calibration": bool(g3), "G4_leakage_audit": bool(g4),
                      "G5_not_twin": bool(g5), "G6_timestamps": bool(g6)},
            "all_gates_pass": bool(g1 and g2 and g3 and g4 and g5 and g6),
        }

    json.dump(results, open(f"{REPO}/v2_research/validation_results.json", "w"), indent=1)

    lines = ["# V2 Validation Results — 2021–2022 (one run, frozen protocol)", "",
             "Primary comparison on V2-defined games only (fallback games excluded).",
             "Gates: G1 paired bootstrap p<0.05 & MAE<V1; G2 better both seasons; "
             "G3 |bias|<1.0 & slope∈[0.8,1.2]; G4 leakage audit; G5 err-corr<0.98; "
             "G6 timestamps. No ATS/ROI.", ""]
    for cand, r in results["candidates"].items():
        lines += [f"## {cand} (alpha={r['frozen_alpha']}, n={r['n_v2_defined']}, "
                  f"fallback={r['n_fallback']})",
                  f"- MAE: {r['mae']} vs V1 {r['v1_mae']} "
                  f"(diff {r['mae_diff_v1_minus_v2']:+.4f}, 95% CI "
                  f"[{r['bootstrap_ci_95'][0]:+.4f}, {r['bootstrap_ci_95'][1]:+.4f}], p={r['bootstrap_p']})",
                  f"- RMSE {r['rmse']}, bias {r['signed_bias']:+.4f}, "
                  f"calib a={r['calibration_intercept']:+.4f} b={r['calibration_slope']:.4f}, "
                  f"err_sd {r['error_sd']}, pred-corr {r['pred_actual_corr']}, "
                  f"err-corr-v1 {r['error_corr_v1']}",
                  f"- by season: " + "; ".join(
                      f"{s}: {v['mae']} vs V1 {v['v1_mae']} (n={v['n']})"
                      for s, v in r["by_season"].items()),
                  f"- gates: " + ", ".join(
                      f"{k}={'PASS' if v else 'FAIL'}" for k, v in r["gates"].items()),
                  f"- **{'ALL GATES PASS' if r['all_gates_pass'] else 'GATES FAILED'}**", ""]
    open(f"{REPO}/v2_research/validation_report.md", "w").write("\n".join(lines))
    print("wrote validation_results.json + validation_report.md")

if __name__ == "__main__":
    main()
