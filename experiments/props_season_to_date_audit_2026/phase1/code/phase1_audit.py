#!/usr/bin/env python3
"""Phase 1: Prospective Season-to-Date Props Audit (2026 W1-W3) -- error table.

MONITORING ONLY. No retraining, no refitting, no threshold changes, no tuning.
W1-W3 are strictly prospective out-of-sample.

Reads the as-of Model D projection sets regenerated under phase1/inputs/,
joins nflverse 2026 weekly player actuals (local player_games.parquet --
the canonical nflverse weekly player-stats file 404s for 2026, see notes),
and writes the per-row error table + aggregate JSON.

Writes (all under experiments/props_season_to_date_audit_2026/phase1/):
  outputs/phase1_errors_2026_w1w3.parquet   -- one row per scored player-week-market
  outputs/phase1_aggregates.json            -- MAE/RMSE/bias per market x week + diagnostics
"""
import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.expanduser("~/workspace/nfl-model")
PHASE1 = os.path.join(REPO, "experiments/props_season_to_date_audit_2026/phase1")
IN = os.path.join(PHASE1, "inputs")
OUT = os.path.join(PHASE1, "outputs")
os.makedirs(OUT, exist_ok=True)

WEEKS = (1, 2, 3)
MARKETS = ["pass_yards", "rush_yards", "receiving_yards"]
YCOL = {"pass_yards": "pass_yards", "rush_yards": "rush_yards",
        "receiving_yards": "receiving_yards"}
OPP_COL = {"pass_yards": "trail_pass_att_ewma", "rush_yards": "trail_rush_att_ewma",
           "receiving_yards": "trail_targets_ewma"}
# dashboard contract: script emits "confidence" (High = narrow range);
# audit reports it as uncertainty with inverted labels.
CONF2UNC = {"High": "Low", "Medium": "Medium", "Low": "High"}
MAX_TRAIL = 16


def _load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


print("loading full player_games (actuals source)...", flush=True)
pg_full = pd.read_parquet(os.path.join(REPO, "data/player_games.parquet"))
pg26 = pg_full[pg_full["season"] == 2026].copy()
print(f"  2026 rows: {len(pg26)}, weeks: {sorted(pg26['week'].unique())}", flush=True)

# rookie flag: no player_games rows before 2026 (first NFL season in 2026)
pre26 = set(pg_full[pg_full["season"] < 2026]["player_name"].unique())

# as-of script copy (for _rich_aggregates only -- no predictions re-run here)
ASOF = _load_mod(
    "asof16",
    os.path.join(PHASE1, "code/16_prod_player_projection_asof.py"))
EXP_DATA = os.path.join(REPO, "experiments/player_props_projection/data")


def rich_coverage_for_week(w):
    """Fraction of each projected player's trailing games present in the
    rich-pbp aggregates (the source of air_yards/yac/rz/completions trailing
    features; missing -> zero-filled fallback in the pipeline)."""
    parts = [pd.read_parquet(os.path.join(EXP_DATA, "pbp_rich_2018_2024.parquet")),
             pd.read_parquet(os.path.join(IN, f"asof_w{w}/prod_pbp_rich_2025.parquet")),
             pd.read_parquet(os.path.join(IN, f"asof_w{w}/prod_pbp_rich_2026.parquet"))]
    rich = pd.concat(parts, ignore_index=True)
    prec, prush, ppass, _ = ASOF._rich_aggregates(rich)
    agg_of = {"pass_yards": ppass, "rush_yards": prush, "receiving_yards": prec}
    pg_a = pd.read_parquet(os.path.join(IN, f"asof_w{w}/player_games.parquet"))
    keys = ["player_name", "team", "season", "week", "game_id"]
    cov = {}
    for m in MARKETS:
        agg = agg_of[m][keys].copy()
        for c in ("season", "week"):
            agg[c] = agg[c].astype(int)
        trail = pg_a[keys].copy()
        for c in ("season", "week"):
            trail[c] = trail[c].astype(int)
        trail = trail.sort_values(["player_name", "season", "week"],
                                  ascending=[True, False, False])
        trail = trail.groupby("player_name", as_index=False).head(MAX_TRAIL)
        mg = trail.merge(agg.assign(_hit=1), on=keys, how="left")
        cov[m] = mg.groupby("player_name")["_hit"].mean().to_dict()
    return cov


def tertile_labels(s):
    q = s.quantile([1 / 3, 2 / 3])
    return pd.cut(s, [-np.inf, q.iloc[0], q.iloc[1], np.inf],
                  labels=["low", "med", "high"]), (float(q.iloc[0]), float(q.iloc[1]))


rows, unscored = [], []
data_quality = {}
for w in WEEKS:
    with open(os.path.join(IN, f"asof_w{w}/prop_v2_2026_w{w}.json")) as f:
        obj = json.load(f)
    wf = pd.read_parquet(os.path.join(IN, f"asof_w{w}/week_frame_2026_w{w}.parquet"))
    wf_idx = wf.set_index(["player_name", "market"])
    cov = rich_coverage_for_week(w)
    act_w = pg26[pg26["week"] == w]
    n_proj = len(obj["projections"])
    n_score = 0
    for p in obj["projections"]:
        player, market = p["player"], p["market"]
        a = act_w[act_w["player_name"] == player]
        if a.empty:
            unscored.append({"player": player, "week": w, "market": market,
                             "team_proj": p["team"], "reason": "no_actual_row"})
            continue
        dup_teams = len(a) > 1
        if dup_teams:
            # data artifact: same abbreviated name on 2+ teams in one week.
            # Attribute the actual to the team the projection was made for;
            # unscorable if no row matches that team.
            mrow = a[a["team"] == p["team"]]
            if len(mrow) != 1:
                unscored.append({"player": player, "week": w, "market": market,
                                 "team_proj": p["team"],
                                 "reason": "ambiguous_actual_no_team_match"})
                continue
            a = mrow
        a = a.iloc[0]
        n_score += 1
        dup_flag = bool(dup_teams)
        actual = float(a[YCOL[market]])
        proj = float(p["projection"])
        ml = p["market_line"]
        wfr = wf_idx.loc[(player, market)]
        trail_opp = float(wfr["_trail_opp_ewma"])
        coverage = float(cov[market].get(player, 0.0))
        rows.append({
            "player": player, "week": w, "market": market,
            "position": str(wfr["position"]),
            "team_proj": p["team"], "opp_proj": p["opp"],
            "team_actual": str(a["team"]),
            "team_mismatch": bool(p["team"] != a["team"]),
            "dup_actual_teams": dup_flag,
            "projection": proj, "p25": float(p["p25"]),
            "median": float(p["median"]), "p75": float(p["p75"]),
            "confidence": p["confidence"],
            "uncertainty": CONF2UNC[p["confidence"]],
            "uncertainty_flag": bool(p["uncertainty_flag"]),
            "baseline_ewma": float(p["baseline_ewma"]),
            "trailing_games": int(p["trailing_games"]),
            "trail_opp_ewma": trail_opp,
            "actual": actual,
            "abs_error": abs(proj - actual),
            "signed_error": proj - actual,  # >0: model high
            "line": float(ml["line"]) if ml else np.nan,
            "model_minus_market": (proj - float(ml["line"])) if ml else np.nan,
            "lean": ml["lean"] if ml else None,
            "line_source": ml["source"] if ml else None,
            "rookie": bool(player not in pre26),
            "rich_coverage": coverage,
            "prediction_timestamp": p["prediction_timestamp"],
        })
    data_quality[f"w{w}"] = {"n_projected": n_proj, "n_scored": n_score,
                             "n_unscored": n_proj - n_score}
    print(f"w{w}: {n_score}/{n_proj} scored", flush=True)

err = pd.DataFrame(rows)
print(f"total scored rows: {len(err)}", flush=True)

# ---- buckets (cutoffs fit on the scored sample only; documented, not tuned)
err["rich_coverage_bucket"] = pd.cut(
    err["rich_coverage"], [-0.01, 0.0, 0.9999, 1.01],
    labels=["fallback", "partial", "full"])
cutoffs = {}
for m in MARKETS:
    sub = err[err["market"] == m]
    lab, (c1, c2) = tertile_labels(sub["trail_opp_ewma"])
    err.loc[sub.index, "opp_volume_bucket"] = lab.astype(str).values
    cutoffs[f"{m}.trail_opp_ewma_tertiles"] = [c1, c2]
    lab, (c1, c2) = tertile_labels(sub["projection"])
    err.loc[sub.index, "proj_size_bucket"] = lab.astype(str).values
    cutoffs[f"{m}.projection_tertiles"] = [c1, c2]
err["gap_bucket"] = pd.cut(err["model_minus_market"],
                            [-np.inf, -5, 5, np.inf],
                            labels=["model_low", "close", "model_high"])


def agg(g):
    n = len(g)
    if n == 0:
        return {"n": 0, "mae": None, "rmse": None, "bias": None}
    ae, se = g["abs_error"].to_numpy(float), g["signed_error"].to_numpy(float)
    return {"n": int(n), "mae": round(float(np.mean(ae)), 2),
            "rmse": round(float(np.sqrt(np.mean(se ** 2))), 2),
            "bias": round(float(np.mean(se)), 2)}


aggregates = {"per_market_week": {}, "pooled": {}, "diagnostics": {},
              "data_quality": data_quality, "bucket_cutoffs": cutoffs,
              "signed_error_convention": "projection - actual (>0 means model projected high)",
              "uncertainty_convention": "uncertainty = inverted pipeline 'confidence' "
                                        "(High confidence -> Low uncertainty), per dashboard contract"}
un = pd.DataFrame(unscored)
for m in MARKETS:
    aggregates["per_market_week"][m] = {}
    for w in WEEKS:
        sub = err[(err["market"] == m) & (err["week"] == w)]
        d = agg(sub)
        n_un = int(((un["market"] == m) & (un["week"] == w)).sum()) if len(un) else 0
        d["n_unscored"] = n_un
        d["n_projected"] = d["n"] + n_un
        aggregates["per_market_week"][m][f"w{w}"] = d
    aggregates["pooled"][m] = agg(err[err["market"] == m])

diag_dims = {
    "opp_volume_bucket": "opp_volume_bucket",
    "proj_size_bucket": "proj_size_bucket",
    "uncertainty": "uncertainty",
    "gap_bucket": "gap_bucket",
    "position": "position",
    "week": "week",
    "rookie": "rookie",
    "rich_coverage_bucket": "rich_coverage_bucket",
}
for label, col in diag_dims.items():
    block = {}
    for m in MARKETS:
        sub = err[err["market"] == m]
        bm = {}
        for val, g in sub.groupby(col, observed=True):
            bm[str(val)] = agg(g)
        block[m] = bm
    aggregates["diagnostics"][label] = block

# team-mismatch diagnostic (offseason-trade staleness in W1 team assignment)
mm = err[err["team_mismatch"]]
aggregates["team_mismatch"] = {
    "n": int(len(mm)),
    "by_week": {f"w{w}": int((mm["week"] == w).sum()) for w in WEEKS},
    "mae_all_scored": round(float(err["abs_error"].mean()), 2),
    "mae_mismatched": round(float(mm["abs_error"].mean()), 2) if len(mm) else None,
}

# duplicate-actual-teams artifact accounting
dup_rows = err[err["dup_actual_teams"]]
aggregates["duplicate_actual_teams"] = {
    "n_scored_with_dup_actual": int(len(dup_rows)),
    "rule": "actual attributed to the row whose team == projection team; "
            "unscorable when no row matches (counted in unscored reasons)",
    "unscored_ambiguous": sum(1 for u in unscored
                              if u["reason"] == "ambiguous_actual_no_team_match"),
}

err_path = os.path.join(OUT, "phase1_errors_2026_w1w3.parquet")
err.to_parquet(err_path, index=False)
agg_path = os.path.join(OUT, "phase1_aggregates.json")
with open(agg_path, "w") as f:
    json.dump(aggregates, f, indent=1)
print(f"wrote {err_path} ({len(err)} rows)", flush=True)
print(f"wrote {agg_path}", flush=True)
