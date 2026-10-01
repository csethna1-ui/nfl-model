#!/usr/bin/env python3
"""Step 21: Experiment 005 — non-QB player availability.

Implements the PREREGISTERED config in experiments/experiment_005_player_availability/config.json.
Frozen V1 + ridge-predicted residual from signed non-QB injury counts.
Training 2018-2020, validation 2021-2022. Vault (2023-2025) NEVER touched.
"""
import json
import os
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

warnings.filterwarnings("ignore")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = REPO_ROOT
EXP = f"{REPO}/experiments/experiment_005_player_availability"
GROUPS = {
    "OL": {"C", "G", "T"},
    "SKILL": {"RB", "WR", "TE", "FB"},  # FB added: appears in 2021-22 data (73 rows), absent 2018-20; natural skill-group member. Added before any validation evaluation.
    "FRONT7": {"DE", "DT", "LB"},
    "DB": {"CB", "S"},
    "ST": {"K", "P", "LS"},
}
DESIGNATIONS = ["Out", "Doubtful", "Questionable"]
ALPHA = 1.0  # preregistered
ET = "America/New_York"


def load_games():
    g = pd.read_parquet(f"{REPO}/data/experiments/games_features.parquet")
    g = g[g["season"] <= 2022].copy()  # vault never loaded
    assert g["season"].max() <= 2022, "VAULT LEAK: season > 2022 present"
    g["week"] = g["week"].astype(int)
    return g


def kickoff_map():
    s = pd.read_parquet(f"{REPO}/data/schedules_2018_2025.parquet")
    s = s[s["season"] <= 2022].copy()
    dt = pd.to_datetime(s["gameday"].dt.strftime("%Y-%m-%d") + " " + s["gametime"])
    s["kickoff"] = dt.dt.tz_localize(ET)
    # Friday 12:00 ET of game week
    fri = s["kickoff"] - pd.to_timedelta((s["kickoff"].dt.weekday - 4) % 7, unit="D")
    s["friday_noon"] = fri.dt.normalize() + pd.Timedelta(hours=12)
    s["T"] = s[["kickoff", "friday_noon"]].min(axis=1)
    return dict(zip(s["game_id"], s["T"]))


def load_injuries():
    import nfl_data_py as nfl

    frames = []
    for se in (2018, 2019, 2020, 2021, 2022):
        d = nfl.import_injuries([se])
        frames.append(d)
    inj = pd.concat(frames, ignore_index=True)
    inj = inj[inj["report_status"].isin(DESIGNATIONS)].copy()
    inj = inj[inj["position"] != "QB"].copy()  # non-QB only, preregistered
    inj["season"] = inj["season"].astype(int)
    inj["week"] = inj["week"].astype(int)
    inj["date_modified"] = pd.to_datetime(inj["date_modified"], utc=True)
    pos2grp = {p: grp for grp, ps in GROUPS.items() for p in ps}
    assert set(inj["position"].unique()) <= set(pos2grp) | {"QB"}, "unmapped position"
    inj["grp"] = inj["position"].map(pos2grp)
    return inj


def build_features(games, inj, tmap):
    feats = []
    matched = 0
    for _, r in games.iterrows():
        T = tmap[r["game_id"]]
        w = inj[(inj["season"] == r["season"]) & (inj["week"] == r["week"])]
        row = {"game_id": r["game_id"]}
        ok = True
        for team_col, sign in (("away_team", 1), ("home_team", -1)):
            tm = w[(w["team"] == r[team_col]) & (w["date_modified"] < T)]
            if len(tm):
                matched += 1
            for grp in GROUPS:
                for des in DESIGNATIONS:
                    c = int(((tm["grp"] == grp) & (tm["report_status"] == des)).sum())
                    row[f"{grp}_{des}"] = row.get(f"{grp}_{des}", 0) + sign * c
        feats.append(row)
    f = pd.DataFrame(feats)
    print(f"team-games with >=1 qualifying injury row: {matched}/{2*len(games)}")
    return f


def metrics(actual, pred):
    e = actual - pred
    slope = float(np.polyfit(pred, actual, 1)[0]) if len(actual) > 2 else float("nan")
    return {"n": int(len(actual)), "mae": round(float(np.abs(e).mean()), 3),
            "rmse": round(float(np.sqrt((e ** 2).mean())), 3),
            "calib_slope": round(slope, 3)}


def main():
    os.makedirs(EXP, exist_ok=True)
    games = load_games()
    print(f"games 2018-2022: {len(games)}")
    tmap = kickoff_map()
    assert set(games["game_id"]) <= set(tmap), "kickoff missing for some games"
    inj = load_injuries()
    print(f"injury rows (Out/Doubtful/Questionable, non-QB): {len(inj)}")

    feats = build_features(games, inj, tmap)
    feat_cols = [c for c in feats.columns if c != "game_id"]
    d = games.merge(feats, on="game_id", how="left")
    assert d[feat_cols].notna().all().all()

    d["resid_v1"] = d["actual_margin"] - d["v1_margin"]
    va = d[d["season"] >= 2021].copy()
    assert va["resid_v1"].notna().all(), "V1 residual undefined in validation window"
    print(f"validation n={len(va)}")

    # Two-fold season cross-fit (preregistration amendment 2026-09-29):
    # frozen-V1 margins do not exist pre-2021, so for each season fit the
    # injury ridge on the OTHER season's V1 residuals and predict this one.
    va["injury_adj"] = np.nan
    fold_coefs = {}
    for S in (2021, 2022):
        tr = va[va["season"] != S]
        te = va[va["season"] == S]
        model = Ridge(alpha=ALPHA, fit_intercept=True)
        model.fit(tr[feat_cols].values, tr["resid_v1"].values)
        va.loc[va["season"] == S, "injury_adj"] = model.predict(te[feat_cols].values)
        fold_coefs[S] = {"intercept": round(float(model.intercept_), 4),
                         "coefs": {f: round(float(c), 4) for f, c in zip(feat_cols, model.coef_)}}
    assert va["injury_adj"].notna().all()
    va["cand_margin"] = va["v1_margin"] + va["injury_adj"]

    out = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    comp = {}
    for name, pred in [("market_only", va["market_spread"]),
                       ("frozen_v1", va["v1_margin"]),
                       ("candidate", va["cand_margin"])]:
        comp[name] = metrics(va["actual_margin"].values, pred.values)
        for se in (2021, 2022):
            s = va[va["season"] == se]
            comp[name][f"season_{se}"] = metrics(s["actual_margin"].values, pred.loc[s.index].values)
    out["baseline_comparison"] = comp

    # error correlations
    e_mkt = va["actual_margin"] - va["market_spread"]
    e_v1 = va["actual_margin"] - va["v1_margin"]
    e_cand = va["actual_margin"] - va["cand_margin"]
    out["error_correlation"] = {
        "market_v1": round(float(np.corrcoef(e_mkt, e_v1)[0, 1]), 3),
        "market_candidate": round(float(np.corrcoef(e_mkt, e_cand)[0, 1]), 3),
        "v1_candidate": round(float(np.corrcoef(e_v1, e_cand)[0, 1]), 3),
    }
    out["fold_coefficients"] = fold_coefs

    # diagnostics (descriptive only)
    va["phase"] = pd.cut(va["week"], [0, 4, 9, 14, 22],
                         labels=["1-4", "5-9", "10-14", "15-18"])
    va["edge_bucket"] = pd.cut(va["resid_v1"].abs(), [0, 1, 2, 3, 4, 99],
                               labels=["0-1", "1-2", "2-3", "3-4", "4+"])
    diag = {}
    for col in ["phase", "div_game", "edge_bucket"]:
        dd = {}
        for key, s in va.groupby(col, observed=True):
            dd[str(key)] = {
                "n": int(len(s)),
                "v1_mae": round(float((s["actual_margin"] - s["v1_margin"]).abs().mean()), 3),
                "cand_mae": round(float((s["actual_margin"] - s["cand_margin"]).abs().mean()), 3),
                "mkt_mae": round(float((s["actual_margin"] - s["market_spread"]).abs().mean()), 3),
            }
        diag[col] = dd
    # position-group injury load diagnostic
    posload = {}
    for grp in GROUPS:
        cols = [c for c in feat_cols if c.startswith(grp + "_")]
        load = va[cols].abs().sum(axis=1)
        hi = va[load >= load.quantile(0.75)]
        posload[grp] = {"n_high_load": int(len(hi)),
                        "v1_mae_high": round(float((hi["actual_margin"] - hi["v1_margin"]).abs().mean()), 3) if len(hi) else None,
                        "cand_mae_high": round(float((hi["actual_margin"] - hi["cand_margin"]).abs().mean()), 3) if len(hi) else None}
    diag["position_group_load"] = posload
    out["diagnostics"] = diag

    # gate
    mkt, v1m, cand = comp["market_only"], comp["frozen_v1"], comp["candidate"]
    gate = {
        "A_beat_v1_materially": bool(cand["mae"] <= v1m["mae"] - 0.10),
        "B_beat_market_by_0.15": bool(cand["mae"] <= mkt["mae"] - 0.15),
        "C_holds_both_seasons": bool(cand["season_2021"]["mae"] < v1m["season_2021"]["mae"]
                                     and cand["season_2022"]["mae"] < v1m["season_2022"]["mae"]),
        "D_calibrated_0.8_1.2": bool(0.8 <= cand["calib_slope"] <= 1.2),
        "E_diversified_below_0.95": bool(out["error_correlation"]["v1_candidate"] < 0.95),
    }
    gate["ALL_PASS"] = bool(all(gate.values()))
    gate["vault"] = "UNTOUCHED — zero evaluations (gate failed)" if not gate["ALL_PASS"] else "MAY BE EVALUATED"
    out["gate_decision"] = gate

    with open(f"{EXP}/validation_results.json", "w") as f:
        json.dump({"generated_at": out["generated_at"],
                   "baseline_comparison": comp,
                   "fold_coefficients": out["fold_coefficients"]}, f, indent=1)
    with open(f"{EXP}/baseline_comparison.json", "w") as f:
        json.dump(comp, f, indent=1)
    with open(f"{EXP}/error_correlation.json", "w") as f:
        json.dump(out["error_correlation"], f, indent=1)
    with open(f"{EXP}/diagnostics.json", "w") as f:
        json.dump(diag, f, indent=1)
    with open(f"{EXP}/gate_decision.json", "w") as f:
        json.dump(gate, f, indent=1)

    print("\n=== BASELINES (2021-2022 validation) ===")
    for name in ("market_only", "frozen_v1", "candidate"):
        c = comp[name]
        print(f"{name:12s} MAE {c['mae']:.3f}  RMSE {c['rmse']:.3f}  calib {c['calib_slope']:.3f}  "
              f"2021 {c['season_2021']['mae']:.3f}  2022 {c['season_2022']['mae']:.3f}")
    print("error corr:", out["error_correlation"])
    print("gate:", {k: v for k, v in gate.items()})
    print("\nwrote", EXP)


if __name__ == "__main__":
    main()
