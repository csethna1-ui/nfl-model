#!/usr/bin/env python3
"""Step 20: Experiment 003 — dynamic offensive/defensive team-strength ratings.

Preregistered design in experiments/experiment_003_dynamic_strength/config.json
(read BEFORE any validation evaluation). This script:
  1. loads the preregistered config,
  2. computes frozen training statistics (L, Hf) on 2018-2020,
  3. selects K on 2019-2020 (2018 = burn-in) by preregistered grid rule,
  4. records frozen_params.json,
  5. runs walk-forward dynamic ratings 2018->2025 (weekly batches),
  6. evaluates 2021-2022 validation ONLY vs market-only and frozen V1,
  7. applies the preregistered gate; vault (2023+) is never touched.

Strictly pregame. No market features. No validation-derived features.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = REPO_ROOT
EXP = f"{REPO}/experiments/experiment_003_dynamic_strength"
VAULT_START = 2023
VAL_SEASONS = (2021, 2022)
TRAIN_SEASONS = (2018, 2019, 2020)
K_GRID = [0.03, 0.05, 0.08, 0.12, 0.18]
OFFSEASON_R = 1.0 / 3.0


def load_games():
    g = pd.read_parquet(f"{REPO}/data/experiments/games_features.parquet")
    s = pd.read_parquet(f"{REPO}/data/schedules_2018_2025.parquet")
    keep = ["game_id", "home_score", "away_score"]
    m = g.merge(s[keep], on="game_id", how="left", validate="one_to_one")
    assert m["home_score"].notna().all(), "missing scores after merge"
    m = m.sort_values(["season", "week", "gameday"]).reset_index(drop=True)
    return m


def run_ratings(games, K, L, Hf, r):
    """Walk-forward dynamic off/def ratings. Returns per-game candidate margin.
    Weekly batching: week W predicted with pre-W ratings, updates applied after."""
    teams = pd.unique(games[["home_team", "away_team"]].values.ravel())
    off = {t: 0.0 for t in teams}
    deff = {t: 0.0 for t in teams}
    cand = np.full(len(games), np.nan)
    prev_season = None
    # process in (season, week) batches
    for (season, week), idx in games.groupby(["season", "week"]).groups.items():
        if season != prev_season:
            if prev_season is not None:  # offseason regression before each new season
                for t in teams:
                    off[t] *= (1 - r)
                    deff[t] *= (1 - r)
            prev_season = season
        rows = games.loc[idx]
        ph = L + rows["home_team"].map(off) + rows["away_team"].map(deff) + Hf / 2.0
        pa = L + rows["away_team"].map(off) + rows["home_team"].map(deff) - Hf / 2.0
        cand[idx] = (ph - pa).values
        eh = (rows["home_score"] - ph).values
        ea = (rows["away_score"] - pa).values
        ht = rows["home_team"].values
        at = rows["away_team"].values
        for h, a, ehh, eaa in zip(ht, at, eh, ea):
            off[h] += K * ehh
            deff[a] += K * ehh
            off[a] += K * eaa
            deff[h] += K * eaa
    return cand


def mae(a, b):
    return float(np.abs(a - b).mean())


def rmse(a, b):
    return float(np.sqrt(((a - b) ** 2).mean()))


def calib_slope(actual, pred):
    x = np.asarray(pred, dtype=float)
    y = np.asarray(actual, dtype=float)
    b = float(np.cov(x, y, bias=True)[0, 1] / np.var(x))
    return b


def main():
    cfg = json.load(open(f"{EXP}/config.json"))
    assert cfg["status"].startswith("PREREGISTERED")
    games = load_games()
    assert (games["season"] < VAULT_START + 3).all()  # data file ends 2025; we simply never evaluate >=2023
    train = games[games["season"].isin(TRAIN_SEASONS)].copy()

    # --- frozen training statistics (2018-2020 only) ---
    L = float((train["home_score"] + train["away_score"]).mean() / 2.0)
    Hf = float((train["home_score"] - train["away_score"]).mean())
    print(f"frozen training stats: L={L:.3f} pts/team-game, Hf={Hf:.3f} pts home edge (2018-2020, n={len(train)})")

    # --- K selection on 2019-2020 (2018 burn-in), preregistered grid rule ---
    sel = train[train["season"].isin([2019, 2020])]
    k_mae = {}
    for K in K_GRID:
        cand = run_ratings(games, K, L, Hf, OFFSEASON_R)
        k_mae[K] = mae(sel["actual_margin"].values, cand[sel.index.values])
        print(f"  K={K}: 2019-2020 MAE={k_mae[K]:.4f}")
    best_mae = min(k_mae.values())
    K_star = min(k for k, v in k_mae.items() if abs(v - best_mae) < 1e-12)  # ties -> smaller K
    print(f"selected K={K_star} (2019-2020 MAE={best_mae:.4f})")

    frozen = {
        "L_league_avg_pts_per_team_game": round(L, 4),
        "Hf_home_field_pts": round(Hf, 4),
        "K_update_rate": K_star,
        "K_grid_mae_2019_2020": {str(k): round(v, 4) for k, v in k_mae.items()},
        "offseason_regression_r": round(OFFSEASON_R, 4),
        "selected_on": "2019-2020 training only; 2018 burn-in; frozen BEFORE validation evaluation",
    }
    json.dump(frozen, open(f"{EXP}/frozen_params.json", "w"), indent=1)
    print(f"wrote {EXP}/frozen_params.json")

    # --- final walk-forward with frozen params; predictions for all games ---
    cand = run_ratings(games, K_star, L, Hf, OFFSEASON_R)
    games["candidate_margin"] = cand
    assert games["candidate_margin"].notna().all()

    # --- leakage audit ---
    audit = []
    audit.append(f"rows: {len(games)}; seasons {games.season.min()}-{games.season.max()}")
    audit.append("weekly batching: week W predictions use only pre-week-W ratings (verified in run_ratings: predictions computed before updates within each (season, week) group)")
    audit.append(f"offseason regression r=1/3 applied at every season boundary 2019-2025 before week 1")
    audit.append(f"frozen params (L, Hf, K) derived from 2018-2020 only; K selected on 2019-2020")
    audit.append("no market spread, closing line, future result, postgame, or injury inputs used")
    audit.append("no validation-derived (2021-2022) quantities used anywhere in ratings or params")
    audit.append(f"vault seasons >= {VAULT_START}: never used for fitting, selection, or evaluation in this script")
    # chronological sanity: first prediction of each season uses only regressed prior ratings
    open(f"{EXP}/leakage_audit.md", "w").write("# Experiment 003 — leakage audit\n\n" + "\n".join(f"- {a}" for a in audit) + "\n")
    print("wrote leakage_audit.md")

    # --- validation evaluation: 2021-2022 ONLY ---
    val = games[games["season"].isin(VAL_SEASONS)].copy()
    assert (val["season"] < VAULT_START).all()
    y = val["actual_margin"].values
    preds = {
        "market_only": val["market_spread"].values,
        "v1": val["v1_margin"].values,
        "candidate": val["candidate_margin"].values,
    }
    metrics = {}
    for name, p in preds.items():
        metrics[name] = {
            "n": int(len(val)),
            "mae": round(mae(y, p), 4),
            "rmse": round(rmse(y, p), 4),
            "calib_slope": round(calib_slope(y, p), 4),
        }
        for s in VAL_SEASONS:
            m = val["season"] == s
            metrics[name][f"mae_{s}"] = round(mae(y[m], p[m]), 4)
    json.dump(metrics, open(f"{EXP}/validation_metrics.json", "w"), indent=1)

    # --- error correlations ---
    errs = {n: y - p for n, p in preds.items()}
    ec = {}
    names = list(errs.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            ec[f"{a}_vs_{b}"] = round(float(np.corrcoef(errs[a], errs[b])[0, 1]), 4)
    json.dump(ec, open(f"{EXP}/error_correlation.json", "w"), indent=1)

    # --- secondary diagnostics (diagnostics only) ---
    def bucket(s):
        return s
    val["phase"] = pd.cut(val["week"], [0, 4, 9, 14, 30], labels=["1-4", "5-9", "10-14", "15+"])
    val["edge_bucket"] = pd.cut(val["v1_margin"].sub(val["market_spread"]).abs(), [0, 1, 2, 3, 4, 99], labels=["0-1", "1-2", "2-3", "3-4", "4+"])
    diag = {}
    for col, lab in [("phase", "phase"), ("div_game", "div"), ("edge_bucket", "edge")]:
        d = {}
        for key, grp in val.groupby(col, observed=True):
            ii = grp.index
            d[str(key)] = {
                "n": int(len(grp)),
                "v1_minus_market_mae": round(mae(y[val.index.isin(ii)], preds["v1"][val.index.isin(ii)]) - mae(y[val.index.isin(ii)], preds["market_only"][val.index.isin(ii)]), 4),
                "cand_minus_market_mae": round(mae(y[val.index.isin(ii)], preds["candidate"][val.index.isin(ii)]) - mae(y[val.index.isin(ii)], preds["market_only"][val.index.isin(ii)]), 4),
            }
        diag[lab] = d
    # home/away from V1 bet direction
    val["bet_home"] = (val["v1_margin"] - val["market_spread"]) > 0
    d = {}
    for key, grp in val.groupby("bet_home"):
        ii = grp.index
        mask = val.index.isin(ii)
        d["home" if key else "away"] = {
            "n": int(len(grp)),
            "v1_minus_market_mae": round(mae(y[mask], preds["v1"][mask]) - mae(y[mask], preds["market_only"][mask]), 4),
            "cand_minus_market_mae": round(mae(y[mask], preds["candidate"][mask]) - mae(y[mask], preds["market_only"][mask]), 4),
        }
    diag["bet_direction"] = d
    json.dump(diag, open(f"{EXP}/diagnostics.json", "w"), indent=1)
    print("wrote validation_metrics.json, error_correlation.json, diagnostics.json")

    # --- preregistered gate ---
    m = metrics
    gate = {
        "A_material_v1_improvement": bool(m["candidate"]["mae"] < m["v1"]["mae"] - 0.05),
        "B_market_bar_minus_0_15": bool(m["candidate"]["mae"] <= m["market_only"]["mae"] - 0.15),
        "C_both_seasons": bool(m["candidate"]["mae_2021"] < m["market_only"]["mae_2021"] and m["candidate"]["mae_2022"] < m["market_only"]["mae_2022"]),
        "D_calibrated_0_8_1_2": bool(0.8 <= m["candidate"]["calib_slope"] <= 1.2),
        "E_diversified_from_v1": bool(ec["v1_vs_candidate"] < 0.95),
        "detail": {
            "candidate_mae": m["candidate"]["mae"], "v1_mae": m["v1"]["mae"], "market_mae": m["market_only"]["mae"],
            "candidate_mae_2021": m["candidate"]["mae_2021"], "market_mae_2021": m["market_only"]["mae_2021"],
            "candidate_mae_2022": m["candidate"]["mae_2022"], "market_mae_2022": m["market_only"]["mae_2022"],
            "candidate_calib_slope": m["candidate"]["calib_slope"],
            "v1_vs_candidate_err_corr": ec["v1_vs_candidate"],
        },
    }
    gate["ALL_PASS"] = all([gate["A_material_v1_improvement"], gate["B_market_bar_minus_0_15"], gate["C_both_seasons"], gate["D_calibrated_0_8_1_2"], gate["E_diversified_from_v1"]])
    gate["vault"] = "MAY_BE_EVALUATED" if gate["ALL_PASS"] else "UNTOUCHED"
    json.dump(gate, open(f"{EXP}/gate_decision.json", "w"), indent=1)
    print("gate:", json.dumps({k: v for k, v in gate.items() if k != "detail"}, indent=1))
    print("VAULT:", gate["vault"])
    return 0 if not gate["ALL_PASS"] else 0


if __name__ == "__main__":
    sys.exit(main())
