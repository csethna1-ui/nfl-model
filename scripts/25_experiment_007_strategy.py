"""Experiment 007 — Offensive Strategy (PROE + early-down behavior + pace).

Preregistered design: experiments/experiment_007_offensive_strategy/config.json
(LOCKED before any validation computation; do not tune after running).

Pipeline:
  1. Build per-team-week strategy features from PBP, strictly pre-game
     (games with week < prediction week; min 2 games else differential = 0).
  2. Home-minus-away differentials merged onto the experiment game spine.
  3. Two-fold season cross-fit Ridge(alpha=1.0) on residual = actual - v1_margin.
  4. Baselines: market-only, frozen V1, V1 + strategy candidate.
  5. Metrics, gate decision (A-F), diagnostics. Vault stays locked unless all pass.

Usage:
  ./venv/bin/python scripts/25_experiment_007_strategy.py
"""
import json
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = REPO_ROOT
OUT = f"{REPO}/experiments/experiment_007_offensive_strategy"
SEASONS = [2021, 2022]
ALPHA = 1.0

# ----------------------------------------------------------------------------
# 1. Strategy features (strictly pre-game)
# ----------------------------------------------------------------------------
def build_team_week_features():
    pbp = pd.concat(
        [pd.read_parquet(f"{REPO}/data/pbp_{s}.parquet") for s in SEASONS],
        ignore_index=True,
    )
    pbp = pbp[pbp["season"].isin(SEASONS)].copy()
    pbp["week"] = pbp["week"].astype(int)

    # --- PROE: mean pass_oe, downs 1-3, offensive plays ---
    proe_plays = pbp[
        pbp["down"].isin([1.0, 2.0, 3.0])
        & pbp["pass_oe"].notna()
        & pbp["posteam"].notna()
    ].copy()
    proe = (
        proe_plays.groupby(["season", "week", "posteam"])
        .agg(proe_sum=("pass_oe", "sum"), proe_n=("pass_oe", "size"),
             games=("game_id", "nunique"))
        .reset_index()
    )

    # --- Early-down pass rate: downs 1-2, play_type pass/run ---
    ed_plays = pbp[
        pbp["down"].isin([1.0, 2.0])
        & pbp["play_type"].isin(["pass", "run"])
        & pbp["posteam"].notna()
    ].copy()
    ed_plays["is_pass"] = (ed_plays["play_type"] == "pass").astype(int)
    ed = (
        ed_plays.groupby(["season", "week", "posteam"])
        .agg(ed_pass=("is_pass", "sum"), ed_n=("is_pass", "size"),
             games=("game_id", "nunique"))
        .reset_index()
    )

    # --- Pace: mean seconds between consecutive offensive plays, diffs in (0,40] ---
    pace_plays = pbp[
        ~pbp["play_type"].isin(["kickoff", "punt", "field_goal", "extra_point", "no_play"])
        & pbp["posteam"].notna()
        & pbp["game_seconds_remaining"].notna()
    ].copy().sort_values(["season", "game_id", "posteam", "play_id"])
    pace_plays["gsr_next"] = pace_plays.groupby(
        ["season", "game_id", "posteam"])["game_seconds_remaining"].shift(-1)
    pace_plays["elapsed"] = pace_plays["game_seconds_remaining"] - pace_plays["gsr_next"]
    pace_ok = pace_plays[(pace_plays["elapsed"] > 0) & (pace_plays["elapsed"] <= 40)]
    pace = (
        pace_ok.groupby(["season", "week", "posteam"])
        .agg(pace_sum=("elapsed", "sum"), pace_n=("elapsed", "size"),
             games=("game_id", "nunique"))
        .reset_index()
    )

    # --- Cumulative (season-to-date, week < W) pooled means per team ---
    frames = {}
    for name, df, val, cnt in [
        ("proe", proe, "proe_sum", "proe_n"),
        ("ed", ed, "ed_pass", "ed_n"),
        ("pace", pace, "pace_sum", "pace_n"),
    ]:
        df = df.sort_values(["season", "posteam", "week"])
        df["cum_val"] = df.groupby(["season", "posteam"])[val].cumsum().shift(1)
        df["cum_n"] = df.groupby(["season", "posteam"])[cnt].cumsum().shift(1)
        df["cum_games"] = (
            df.groupby(["season", "posteam"])["games"].cumsum().shift(1)
        )
        # value as of prediction week W = cumulative over weeks < W
        df["value"] = df["cum_val"] / df["cum_n"]
        df.loc[df["cum_games"] < 2, "value"] = np.nan
        frames[name] = df[["season", "week", "posteam", "value"]].rename(
            columns={"posteam": "team", "value": name}
        )
    return frames


def build_differentials(spine, frames):
    """Home-minus-away differentials; missing (<2 games) -> 0 per preregistration."""
    out = spine.copy()
    for name, f in frames.items():
        m = f.rename(columns={"team": "home_team", name: f"{name}_home"})
        out = out.merge(m[["season", "week", "home_team", f"{name}_home"]],
                        on=["season", "week", "home_team"], how="left")
        m = f.rename(columns={"team": "away_team", name: f"{name}_away"})
        out = out.merge(m[["season", "week", "away_team", f"{name}_away"]],
                        on=["season", "week", "away_team"], how="left")
        out[f"{name}_diff"] = (
            out[f"{name}_home"].fillna(0) - out[f"{name}_away"].fillna(0)
        )
        # if either side missing -> differential 0 (league-average treatment)
        miss = out[f"{name}_home"].isna() | out[f"{name}_away"].isna()
        out.loc[miss, f"{name}_diff"] = 0.0
    return out


# ----------------------------------------------------------------------------
# 2. Metrics helpers
# ----------------------------------------------------------------------------
def mae(a, b):
    return float(np.mean(np.abs(a - b)))


def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def cal_slope(pred, actual):
    pred = np.asarray(pred, dtype=float)
    actual = np.asarray(actual, dtype=float)
    v = np.var(pred)
    if v == 0:
        return float("nan")
    return float(np.cov(pred, actual, ddof=0)[0, 1] / v)


FEATURES = ["proe_diff", "ed_diff", "pace_diff"]


def run_fold(train, test):
    """Fit ridge on train residuals, predict test margins."""
    Xtr = train[FEATURES].to_numpy(float)
    ytr = (train["actual_margin"] - train["v1_margin"]).to_numpy(float)
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd[sd == 0] = 1.0
    model = Ridge(alpha=ALPHA)
    model.fit((Xtr - mu) / sd, ytr)
    Xte = test[FEATURES].to_numpy(float)
    resid_pred = model.predict((Xte - mu) / sd)
    return test["v1_margin"].to_numpy(float) + resid_pred, model.coef_, model.intercept_


def main():
    spine = pd.read_parquet(f"{REPO}/data/experiments/games_features.parquet")
    val = spine[spine["season"].isin(SEASONS)].copy().reset_index(drop=True)
    val["week"] = val["week"].astype(int)
    assert val[["v1_margin", "actual_margin", "market_spread"]].notna().all().all()
    n = len(val)
    print(f"validation n={n}")

    frames = build_team_week_features()
    val = build_differentials(val, frames)
    print("differentials built; share of zero diffs:",
          {f: float((val[f] == 0).mean()) for f in FEATURES})

    # leakage audit quantities
    audit = {
        "n_validation": n,
        "feature_weeks_strictly_before_prediction_week": True,
        "min_games_rule": 2,
        "share_zero_proe_diff": float((val["proe_diff"] == 0).mean()),
        "share_zero_ed_diff": float((val["ed_diff"] == 0).mean()),
        "share_zero_pace_diff": float((val["pace_diff"] == 0).mean()),
        "outcome_columns_used_in_features": [],
        "market_variables_used": [],
        "vault_accessed": False,
        "experiment_006_data_used": False,
    }

    # --- two-fold cross-fit ---
    cand = np.zeros(n)
    coefs = {}
    for fit_season, pred_season in [(2021, 2022), (2022, 2021)]:
        tr = val[val["season"] == fit_season]
        te = val[val["season"] == pred_season]
        preds, coef, icept = run_fold(tr, te)
        cand[val["season"] == pred_season] = preds
        coefs[str(fit_season)] = {
            "coef": dict(zip(FEATURES, [float(c) for c in coef])),
            "intercept": float(icept),
            "n_train": len(tr),
        }
    val["cand_margin"] = cand

    actual = val["actual_margin"].to_numpy(float)
    market = val["market_spread"].to_numpy(float)
    v1 = val["v1_margin"].to_numpy(float)

    results = {}
    for name, pred in [("market", market), ("v1", v1), ("candidate", cand)]:
        results[name] = {
            "mae": mae(actual, pred),
            "rmse": rmse(actual, pred),
            "calibration_slope": cal_slope(pred, actual),
        }
    for s in SEASONS:
        m = val["season"] == s
        a = actual[m]
        results[f"market_{s}"] = {"mae": mae(a, market[m])}
        results[f"v1_{s}"] = {"mae": mae(a, v1[m])}
        results[f"candidate_{s}"] = {"mae": mae(a, cand[m])}

    err_v1 = actual - v1
    err_cand = actual - cand
    err_corr = float(np.corrcoef(err_v1, err_cand)[0, 1])
    pred_corr = float(np.corrcoef(v1, cand)[0, 1])

    # --- per-feature diagnostics: residual correlation + ablations ---
    resid = actual - v1
    feat_corr = {f: float(np.corrcoef(val[f].to_numpy(float), resid)[0, 1])
                 for f in FEATURES}
    ablations = {}
    for drop in FEATURES:
        keep = [f for f in FEATURES if f != drop]
        c2 = np.zeros(n)
        for fit_season, pred_season in [(2021, 2022), (2022, 2021)]:
            tr = val[val["season"] == fit_season]
            te = val[val["season"] == pred_season]
            Xtr = tr[keep].to_numpy(float)
            ytr = (tr["actual_margin"] - tr["v1_margin"]).to_numpy(float)
            mu, sd = Xtr.mean(0), Xtr.std(0)
            sd[sd == 0] = 1.0
            mdl = Ridge(alpha=ALPHA)
            mdl.fit((Xtr - mu) / sd, ytr)
            Xte = te[keep].to_numpy(float)
            c2[val["season"] == pred_season] = (
                te["v1_margin"].to_numpy(float) + mdl.predict((Xte - mu) / sd)
            )
        ablations[f"drop_{drop}"] = {"mae": mae(actual, c2)}

    # --- bucket diagnostics (descriptive only) ---
    edge = np.abs(v1 - market)
    val["edge_bucket"] = pd.cut(edge, [-np.inf, 3, 5, np.inf],
                                labels=["<3", "3-5", "5+"])
    phase = pd.cut(val["week"], [0, 4, 9, 14, 30],
                   labels=["1-4", "5-9", "10-14", "15+"])
    buckets = {}
    for bname, b in [("phase", phase),
                     ("div", val["div_game"].map({0: "nondiv", 1: "div"})),
                     ("edge", val["edge_bucket"]),
                     ("home_fav", pd.Series(market > 0).map({True: "home_fav",
                                                    False: "home_dog"}))]:
        d = {}
        for lvl in pd.unique(b):
            m = (b == lvl).to_numpy()
            if m.sum() < 10:
                continue
            d[str(lvl)] = {
                "n": int(m.sum()),
                "v1_mae": mae(actual[m], v1[m]),
                "cand_mae": mae(actual[m], cand[m]),
            }
        buckets[bname] = d

    diagnostics = {
        "feature_residual_correlation": feat_corr,
        "ablation_mae": ablations,
        "v1_mae_overall": results["v1"]["mae"],
        "error_correlation_v1_candidate": err_corr,
        "prediction_correlation_v1_candidate": pred_corr,
        "buckets": buckets,
        "fold_coefficients": coefs,
    }

    # --- gate ---
    A = results["candidate"]["mae"] <= results["v1"]["mae"] - 0.10
    B = results["candidate"]["mae"] <= results["market"]["mae"] - 0.15
    C = all(
        results[f"candidate_{s}"]["mae"] < results[f"v1_{s}"]["mae"]
        and results[f"candidate_{s}"]["mae"] <= results[f"market_{s}"]["mae"] - 0.15
        for s in SEASONS
    )
    D = 0.8 <= results["candidate"]["calibration_slope"] <= 1.2
    E = err_corr < 0.95
    signs = {f: [np.sign(coefs["2021"]["coef"][f]),
                 np.sign(coefs["2022"]["coef"][f])] for f in FEATURES}
    F_i = all(s[0] == s[1] and s[0] != 0 for s in signs.values())
    F_ii = all(v["mae"] < results["v1"]["mae"] for v in ablations.values())
    F = F_i and F_ii
    gate = {
        "A_materially_beat_v1": {"pass": bool(A), "detail": f"cand {results['candidate']['mae']:.3f} vs v1 {results['v1']['mae']:.3f} (need <= v1-0.10)"},
        "B_beat_market_0.15": {"pass": bool(B), "detail": f"cand {results['candidate']['mae']:.3f} vs market {results['market']['mae']:.3f} (need <= market-0.15)"},
        "C_both_seasons": {"pass": bool(C), "detail": {str(s): {"cand": results[f'candidate_{s}']['mae'], "v1": results[f'v1_{s}']['mae'], "market": results[f'market_{s}']['mae']} for s in SEASONS}},
        "D_calibration": {"pass": bool(D), "detail": f"slope {results['candidate']['calibration_slope']:.3f} in [0.8,1.2]"},
        "E_error_diversification": {"pass": bool(E), "detail": f"corr {err_corr:.3f} < 0.95"},
        "F_coefficient_stability": {"pass": bool(F), "detail": {"signs_consistent": bool(F_i), "signs": {k: [float(x) for x in v] for k, v in signs.items()}, "no_single_feature_drives": bool(F_ii), "ablations": ablations}},
    }
    passed = all(g["pass"] for g in gate.values())
    gate["verdict"] = ("GATE PASSED — vault may be evaluated"
                       if passed else "GATE FAILED — vault remains untouched")
    gate["vault_evaluations"] = 0

    validation_results = {
        "n": n,
        "seasons": SEASONS,
        "baselines": results,
        "error_correlation_v1_candidate": err_corr,
        "prediction_correlation_v1_candidate": pred_corr,
    }

    with open(f"{OUT}/validation_results.json", "w") as f:
        json.dump(validation_results, f, indent=2)
    with open(f"{OUT}/gate_decision.json", "w") as f:
        json.dump(gate, f, indent=2)
    with open(f"{OUT}/diagnostics.json", "w") as f:
        json.dump(diagnostics, f, indent=2)
    with open(f"{OUT}/leakage_audit.md", "w") as f:
        f.write("# Experiment 007 — Leakage Audit\n\n")
        for k, v in audit.items():
            f.write(f"- {k}: {v}\n")
        f.write("\nFeature timing: for a prediction game in week W of season S, "
                "each team's strategy value is the pooled mean over qualifying "
                "plays from that team's games with week < W in season S "
                "(weekly batching). No plays from week W or later. "
                "Offseason hard reset (no cross-season carryover). "
                "Residual target uses frozen V1 predictions; the strategy ridge "
                "is fit out-of-fold (two-fold season cross-fit), so no "
                "in-sample V1 information leaks into the candidate.\n")

    print(json.dumps(results, indent=2))
    print("err_corr:", round(err_corr, 4), "pred_corr:", round(pred_corr, 4))
    print("GATE:", gate["verdict"])
    for k, g in gate.items():
        if k in ("verdict", "vault_evaluations"):
            continue
        print(f"  {k}: {'PASS' if g['pass'] else 'FAIL'}")
    return gate["verdict"]


if __name__ == "__main__":
    main()
