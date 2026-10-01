#!/usr/bin/env python3
"""Step 5: Ensemble tuning (weights by 2021-2022 validation MAE), threshold selection
by validation ROI, honest reporting on 2023-2025 test."""
import itertools
import numpy as np
import pandas as pd

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
THRESHOLDS = [1.5, 2.0, 2.5, 3.0]

def ats_metrics(df, pred_col, line_col="spread_line", side="spread"):
    """Returns dict of metrics per threshold. Bet home if pred>line (spread) etc.
    spread_line>0 = home favored; home covers iff home_margin > spread_line.
    Pushes (==) excluded."""
    out = {}
    df = df.dropna(subset=[pred_col]).copy()
    for t in THRESHOLDS:
        edge = df[pred_col] - df[line_col]
        if side == "spread":
            bet_home = edge >= t
            bet_away = edge <= -t
            plays = df[bet_home | bet_away].copy()
            plays["win"] = np.where(
                bet_home[bet_home | bet_away],
                plays["home_margin"] > plays["spread_line"],
                plays["home_margin"] < plays["spread_line"])
            plays = plays[plays["home_margin"] != plays["spread_line"]]  # drop pushes
        else:
            bet_over = edge >= t
            bet_under = edge <= -t
            plays = df[bet_over | bet_under].copy()
            plays["win"] = np.where(
                bet_over[bet_over | bet_under],
                plays["total_pts"] > plays["total_line"],
                plays["total_pts"] < plays["total_line"])
            plays = plays[plays["total_pts"] != plays["total_line"]]
        n = len(plays)
        w = int(plays["win"].sum()) if n else 0
        l = n - w
        profit = w * 1.0 - l * 1.1
        roi = profit / (n * 1.1) if n else 0.0
        out[t] = {"n": n, "w": w, "l": l, "win_rate": w / n if n else 0,
                  "profit_units": round(profit, 1), "roi": round(roi, 4)}
    return out

def main():
    d = pd.read_parquet(f"{DATA}/games_with_preds.parquet")
    tmp = d.dropna(subset=["pred_gbm_m"])
    val = tmp[tmp["season"].isin([2021, 2022])].copy()
    test = tmp[tmp["season"].isin([2023, 2024, 2025])].copy()
    print(f"val games: {len(val)}, test games: {len(test)}", flush=True)

    # --- tune ensemble weights on validation MAE ---
    best, best_mae = None, 1e9
    for w1, w2 in itertools.product(np.arange(0, 1.01, 0.1), repeat=2):
        w3 = round(1 - w1 - w2, 10)
        if w3 < -1e-9:
            continue
        pred = w1 * val["pred_elo"] + w2 * val["pred_epa_m"] + w3 * val["pred_gbm_m"]
        mae = np.abs(pred - val["home_margin"]).mean()
        if mae < best_mae:
            best_mae, best = mae, (round(w1,2), round(w2,2), round(w3,2))
    w_elo, w_epa, w_gbm = best
    print(f"margin ensemble weights (val MAE {best_mae:.2f}): elo={w_elo} epa={w_epa} gbm={w_gbm}")

    best, best_mae = None, 1e9
    for w1 in np.arange(0, 1.01, 0.1):
        w2 = round(1 - w1, 10)
        pred = w1 * val["pred_epa_t"] + w2 * val["pred_gbm_t"]
        mae = np.abs(pred - val["total_pts"]).mean()
        if mae < best_mae:
            best_mae, best = mae, (round(w1,2), round(w2,2))
    w_epa_t, w_gbm_t = best
    print(f"total ensemble weights (val MAE {best_mae:.2f}): epa={w_epa_t} gbm={w_gbm_t}")

    for df_ in (d, val, test):
        df_["ens_margin"] = w_elo*df_["pred_elo"] + w_epa*df_["pred_epa_m"] + w_gbm*df_["pred_gbm_m"]
        df_["ens_total"] = w_epa_t*df_["pred_epa_t"] + w_gbm_t*df_["pred_gbm_t"]

    # individual-component MAE on validation for the report
    print("\nValidation MAE by component (margin):")
    for c in ["pred_elo", "pred_epa_m", "pred_gbm_m", "ens_margin"]:
        print(f"  {c}: {np.abs(val[c]-val['home_margin']).mean():.2f}")
    print("Validation MAE by component (total):")
    for c in ["pred_epa_t", "pred_gbm_t", "ens_total"]:
        print(f"  {c}: {np.abs(val[c]-val['total_pts']).mean():.2f}")

    # --- threshold selection on validation ROI ---
    print("\n== SPREADS: validation (2021-2022) ==")
    vm = ats_metrics(val, "ens_margin", side="spread")
    for t, m in vm.items():
        print(f"  edge>={t}: n={m['n']} {m['w']}-{m['l']} wr={m['win_rate']:.3f} roi={m['roi']:.3f}")
    # choose threshold: max ROI with n>=40 on validation
    cand = [(t, m) for t, m in vm.items() if m["n"] >= 40]
    op_t = max(cand, key=lambda kv: kv[1]["roi"])[0] if cand else None
    print("operating spread threshold:", op_t)

    print("\n== TOTALS: validation (2021-2022) ==")
    vmt = ats_metrics(val, "ens_total", line_col="total_line", side="total")
    for t, m in vmt.items():
        print(f"  edge>={t}: n={m['n']} {m['w']}-{m['l']} wr={m['win_rate']:.3f} roi={m['roi']:.3f}")
    cand = [(t, m) for t, m in vmt.items() if m["n"] >= 40]
    op_tt = max(cand, key=lambda kv: kv[1]["roi"])[0] if cand else None
    print("operating total threshold:", op_tt)

    print("\n== SPREADS: test (2023-2025) ==")
    tm = ats_metrics(test, "ens_margin", side="spread")
    for t, m in tm.items():
        print(f"  edge>={t}: n={m['n']} {m['w']}-{m['l']} wr={m['win_rate']:.3f} roi={m['roi']:.3f}")
    print("\n== TOTALS: test (2023-2025) ==")
    tmt = ats_metrics(test, "ens_total", line_col="total_line", side="total")
    for t, m in tmt.items():
        print(f"  edge>={t}: n={m['n']} {m['w']}-{m['l']} wr={m['win_rate']:.3f} roi={m['roi']:.3f}")

    # save params
    import json
    with open(f"{DATA}/ensemble_params.json", "w") as f:
        json.dump({"w_elo": w_elo, "w_epa": w_epa, "w_gbm": w_gbm,
                   "w_epa_t": w_epa_t, "w_gbm_t": w_gbm_t,
                   "op_spread_thresh": op_t, "op_total_thresh": op_tt}, f, indent=2)
    d.to_parquet(f"{DATA}/games_with_preds.parquet", index=False)
    print("\nsaved ensemble_params.json")

if __name__ == "__main__":
    main()
