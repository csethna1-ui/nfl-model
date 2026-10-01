#!/usr/bin/env python3
"""Step 15: Export UI JSON snapshots for the NFL Model Dashboard.

Reads the model's canonical outputs (no recomputation of picks) and writes
small, UI-ready JSON files to data/ui_json/. Re-run every Friday after the
weekly pipeline so the dashboard stays current; the web artifact embeds these
files at build/edit time.

Outputs:
  meta.json, predictions.json, record.json, clv.json,
  backtest.json, teams.json, props.json, injuries.json, model_facts.json

EXPORTER CONTRACT (architectural rule, 2026-09-30):
  The exporter is the final gatekeeper for dashboard data. Pipeline is
  Model -> calculations -> export normalization -> schema validation
  -> JSON -> dashboard. The model may legitimately produce missing
  values; the exporter converts every non-finite numeric (NaN, Infinity,
  -Infinity) to JSON-safe null BEFORE serialization:
      finite number -> number
      missing/non-finite -> null
  No imputation, no manufactured values; legitimate zeroes and valid
  numerics pass through untouched. Serialization uses allow_nan=False,
  so any non-finite value that survives normalization FAILS THE EXPORT
  loudly instead of leaking invalid JSON to the dashboard.
"""
import argparse
import glob
import json
import math
import os
import pickle
from datetime import datetime, timezone

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
UI_ROOT = f"{DATA}/ui_json"
THRESH = 3.0

# Frozen V1 component definitions (copied from saved model files at export
# time — never refit here). Used only to *display* per-game component
# margins; the predictions themselves are read from the canonical CSV.
RATING_COLS = ["off_epa", "off_pass_epa", "off_rush_epa", "off_sr",
               "def_epa", "def_pass_epa", "def_rush_epa", "def_sr"]
# Maps lr_epa_m's training feature names -> ratings-parquet columns.
# ORDER MATTERS: coef_[i] multiplies the i-th feature in epa_m_feats order.
FEAT_TO_COL = {"off_epa_diff": "off_epa", "def_epa_diff": "def_epa",
               "off_pass_diff": "off_pass_epa", "off_rush_diff": "off_rush_epa",
               "def_pass_diff": "def_pass_epa", "def_rush_diff": "def_rush_epa",
               "sr_off_diff": "off_sr", "sr_def_diff": "def_sr"}

# Registry of model versions with genuine canonical source data.
# Only versions listed here can be exported. This prevents silently
# relabeling one model's outputs under another version's name.
# A future V2 gets an entry here only after it clears the promotion bar,
# pointing at its own genuine canonical data directory.
KNOWN_VERSION_SOURCES = {
    "V1": DATA,
}


def parse_args():
    p = argparse.ArgumentParser(description="Export UI JSON snapshots (versioned).")
    p.add_argument("--model-version", default="V1",
                   help="Model version label, e.g. V1, V2, V3 (default V1)")
    p.add_argument("--week", type=int, default=None,
                   help="Season week to export (default: auto-detect latest "
                        "predictions_2026_w*.csv in the data root)")
    return p.parse_args()


def _detect_latest_week(data_root):
    """Auto-detect the latest week from predictions_2026_w*.csv files."""
    cands = []
    for f in glob.glob(f"{data_root}/predictions_2026_w*.csv"):
        stem = os.path.basename(f)[len("predictions_2026_w"):-len(".csv")]
        if stem.isdigit():
            cands.append(int(stem))
    if not cands:
        raise SystemExit(
            f"ERROR: no predictions_2026_w*.csv found in {data_root}; "
            "pass --week explicitly.")
    return max(cands)


def version_dir(label):
    return f"{UI_ROOT}/{label.lower()}"


def _json_safe(obj):
    """Recursively normalize an export payload to strict-JSON-safe values.

    Contract: finite number -> number; missing/non-finite -> null.
    Converts NaN / Infinity / -Infinity (float or numpy scalar) to None,
    and numpy scalars to their Python equivalents. Everything else
    (strings, bools, None, zero, valid numerics) passes through unchanged.
    """
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (float, np.floating)) and not isinstance(obj, bool):
        f = float(obj)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(obj, (np.integer,)) and not isinstance(obj, bool):
        return int(obj)
    return obj


def w(out_dir, obj, name):
    p = f"{out_dir}/{name}"
    obj = _json_safe(obj)
    with open(p, "w") as f:
        # allow_nan=False is the fail-loud validation: any non-finite
        # value that survived normalization raises here instead of
        # emitting invalid JSON to the dashboard.
        json.dump(obj, f, indent=1, allow_nan=False)
    print(f"wrote {p} ({os.path.getsize(p)//1024} KB)")


def load_component_models(data_root):
    """Load the frozen V1 component regressions (display only, never refit).

    Returns (lr_elo, lr_epa_m, ensemble_weights). The GBM is refit per run
    by 07 and is NOT a saved regression, so its per-game margin is backed
    out of the blend instead of recomputed.
    """
    with open(f"{data_root}/linear_models.pkl", "rb") as f:
        lin = pickle.load(f)
    with open(f"{data_root}/ensemble_params.json") as f:
        ens = json.load(f)
    return lin["lr_elo"], lin["lr_epa_m"], ens


def game_components(away, home, ratings, lr_elo, lr_epa_m, ens, model_spread_full):
    """Per-game V1 component margins from the frozen ratings + regressions.

    elo_margin / epa_margin are recomputed exactly as 07 does (verified:
    ratings_current_2026_w4.parquet is byte-identical to 07's in-memory
    ELO/EPA state; the computation reproduces the audit's Friday trace to
    display rounding). gbm_margin is backed out of the blend — it is the
    implied GBM component, not a recomputation, because the GBM is refit
    per run and has no saved regression. Raises ValueError if the blend
    does not reproduce model_spread within 1e-6 (fail loud, never ship
    inconsistent numbers).
    """
    rh, ra = ratings.loc[home], ratings.loc[away]
    elo_diff = float(rh["elo"] - ra["elo"])
    elo_margin = float(lr_elo.predict(np.array([[elo_diff]]))[0])
    # Feature order MUST match the training column order in epa_m_feats;
    # coef_[i] belongs to epa_m_feats[i]. (A wrong order here once shipped
    # silently because the blend check can't catch it — the backed-out GBM
    # absorbs the error. Verified against an independent GBM refit.)
    epa_feats = list(lr_epa_m.feature_names_in_)
    if set(epa_feats) != set(FEAT_TO_COL):
        raise ValueError(f"lr_epa_m features changed: {epa_feats}")
    diffs = [float(rh[FEAT_TO_COL[f]] - ra[FEAT_TO_COL[f]]) for f in epa_feats]
    epa_margin = float(lr_epa_m.predict(np.array([diffs]))[0])
    gbm_margin = (model_spread_full
                  - ens["w_elo"] * elo_margin
                  - ens["w_epa"] * epa_margin) / ens["w_gbm"]
    recon = (ens["w_elo"] * elo_margin + ens["w_epa"] * epa_margin
             + ens["w_gbm"] * gbm_margin)
    if abs(recon - model_spread_full) > 1e-6:
        raise ValueError(
            f"component blend mismatch for {away} @ {home}: "
            f"blend={recon:.6f} vs model_spread={model_spread_full:.6f}")
    return {
        "elo_diff": round(elo_diff, 2),
        "elo_margin": round(elo_margin, 2),
        "epa_margin": round(epa_margin, 2),
        "gbm_margin": round(gbm_margin, 2),
    }


def model_math_block(lr_elo, lr_epa_m, ens):
    """Top-level frozen-math reference for the 'show me the math' UI level.

    Every number copied from saved model files or the rating scripts —
    nothing refit, nothing invented.
    """
    feat_names = ["off_epa", "def_epa", "off_pass_epa", "off_rush_epa",
                  "def_pass_epa", "def_rush_epa", "off_sr", "def_sr"]
    return {
        "note": ("Frozen V1 component math, copied from saved model files. "
                 "Per-game components in games[].components are display-only; "
                 "predictions always come from the canonical CSV."),
        "lr_elo": {
            "feature": "elo_diff (home ELO minus away ELO, home-field already in ratings via HFA)",
            "coef": [round(float(c), 8) for c in np.atleast_1d(lr_elo.coef_)],
            "intercept": round(float(lr_elo.intercept_), 8),
        },
        "lr_epa_margin": {
            "features": [f + "_diff (home minus away)" for f in feat_names],
            "coef": [round(float(c), 8) for c in np.atleast_1d(lr_epa_m.coef_)],
            "intercept": round(float(lr_epa_m.intercept_), 8),
        },
        "ensemble_weights": {k: ens[k] for k in ("w_elo", "w_epa", "w_gbm")},
        "elo_params": {"K": 20.0, "home_field_advantage_elo": 55.0,
                       "offseason_regression": "1/3 toward 1500 at each week 1",
                       "update": "weekly batching; margin-of-victory multiplier",
                       "source": "scripts/03_ratings.py"},
        "epa_params": {"weekly_ewma_alpha": 0.25,
                       "offseason_prior_weight": 0.35,
                       "offseason_prior_value": 0.0,
                       "plays": "nflverse pbp pass/run plays with non-null EPA",
                       "source": "scripts/07_update_weekly.py run_epa_current"},
        "gbm": {
            "note": ("Refit per run on the expanding window of played games; "
                     "no saved regression exists, so per-game gbm_margin is "
                     "the implied component backed out of the blend."),
            "backend": "sklearn-hgbr (HistGradientBoostingRegressor)",
            "hyperparameters": {"max_iter": 200, "max_depth": 3,
                                "learning_rate": 0.05, "l2_regularization": 1.0,
                                "random_state": 42},
            "features": ["elo_diff", "off_epa_diff", "def_epa_diff",
                         "off_pass_diff", "off_rush_diff", "def_pass_diff",
                         "def_rush_diff", "sr_off_diff", "sr_def_diff",
                         "rest_diff", "div_game", "week"],
            "source": "scripts/model_lib.py make_gbm",
        },
        "pick_threshold": THRESH,
        "win_probability": {
            "note": ("Separate derived layer, not part of V1. P(home win) = "
                     "sigmoid(a * model_spread + b); cannot change any "
                     "spread, pick, or edge."),
            "calibration_file": "data/calibration/winprob_v1.json",
            "a": 0.12274, "b": 0.09099,
            "validated": "Brier 0.21908 vs naive 0.24758 on locked 2023-2025",
        },
    }


def main():
    args = parse_args()
    ver = args.model_version.strip().upper()
    if ver not in KNOWN_VERSION_SOURCES:
        raise SystemExit(
            f"ERROR: refusing to export version '{ver}'. No canonical source "
            f"data is registered for '{ver}' (known: {sorted(KNOWN_VERSION_SOURCES)}). "
            f"Register genuine {ver} model outputs in KNOWN_VERSION_SOURCES before "
            f"exporting — V1 data will not be relabeled."
        )
    data_root = KNOWN_VERSION_SOURCES[ver]
    out_dir = version_dir(ver)
    os.makedirs(out_dir, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    wk = args.week if args.week is not None else _detect_latest_week(data_root)

    # ---- meta ----
    w(out_dir, {
        "model_version": ver,
        "ensemble": "0.4 * ELO + 0.5 * EPA-linear + 0.1 * GBM",
        "threshold": THRESH,
        "season": 2026,
        "latest_week": wk,
        "generated_at": now,
        "lines_note": ("Weekly picks use Friday researched lines; "
                       "CLV is measured vs the nflverse close proxy."),
        "disclaimer": ("Experimental NFL analytics / paper-tracking system. "
                       "No verified betting edge. Not betting advice; no "
                       "real-money recommendations."),
    }, "meta.json")

    # ---- predictions (latest week) ----
    preds = pd.read_csv(f"{data_root}/predictions_2026_w{wk}.csv")
    sched = pd.read_parquet(f"{data_root}/schedules_2018_2025.parquet")
    s4 = sched[(sched["season"] == 2026) & (sched["week"] == wk)]
    # Frozen V1 component regressions + the exact rating snapshot 07 used
    # (verified byte-identical to 07's in-memory ELO/EPA state).
    lr_elo, lr_epa_m, ens = load_component_models(data_root)
    # Win-probability calibration (derived layer, validated 2026-09-30).
    # P(home win) = sigmoid(a * model_spread + b) with frozen coefficients
    # from data/calibration/winprob_v1.json. Applied to the full-precision
    # model_spread; does not change any prediction, pick, or edge.
    # market_win_prob is intentionally absent: no moneyline data exists in
    # the market JSONs, and it is never approximated.
    with open(f"{data_root}/calibration/winprob_v1.json") as f:
        wp = json.load(f)["mapping"]
    wp_a, wp_b = float(wp["a"]), float(wp["b"])
    ratings = pd.read_parquet(
        f"{data_root}/ratings_current_2026_w{wk}.parquet").set_index("team")
    games = []
    def _s(v):
        return "" if pd.isna(v) else str(v)
    def _n(v):
        return None if pd.isna(v) else round(float(v), 1)
    def _b(v):
        return str(v).lower() == "true"
    for _, r in preds.iterrows():
        away, home = r["game"].split(" @ ")
        g = s4[(s4["away_team"] == away) & (s4["home_team"] == home)]
        kick = ""
        if len(g):
            g = g.iloc[0]
            try:
                day = pd.to_datetime(g["gameday"]).strftime("%a %b %-d")
            except Exception:
                day = str(g["gameday"])
            tm = str(g["gametime"]).strip()
            try:
                tm = datetime.strptime(tm, "%H:%M").strftime("%-I:%M %p")
            except Exception:
                pass
            kick = f"{day}, {tm} ET"
        comp = game_components(away, home, ratings, lr_elo, lr_epa_m, ens,
                               float(r["model_spread"]))
        ms_full = float(r["model_spread"])
        model_win_prob = round(
            1.0 / (1.0 + math.exp(-(wp_a * ms_full + wp_b))), 3)
        # QB-adjusted win prob: same frozen calibration applied to the
        # adjusted margin. Displayed as a raw -> adjusted range on QB-change
        # games (raw = aggressive bound, adjusted = conservative bound when
        # double-count risk is flagged).
        ms_adj_full = float(r["model_spread_adj"])
        model_win_prob_adj = round(
            1.0 / (1.0 + math.exp(-(wp_a * ms_adj_full + wp_b))), 3)
        veto = _b(r.get("stale_qb_veto", False))
        pick_final = r["spread_pick_final"]
        if veto:
            final_status = "VETOED"
        elif pick_final != "no play":
            final_status = "PICK"
        else:
            final_status = "NO PLAY"
        change_side = _s(r.get("qb_change_side", "")) or None
        games.append({
            "game": r["game"], "away": away, "home": home, "kickoff": kick,
            "model_spread": round(float(r["model_spread"]), 1),
            "market_spread": round(float(r["market_spread"]), 1),
            "edge": round(float(r["edge"]), 1),
            "model_win_prob": model_win_prob,
            "components": {"elo_margin": comp["elo_margin"],
                           "epa_margin": comp["epa_margin"],
                           "gbm_margin": comp["gbm_margin"]},
            "elo_diff": comp["elo_diff"],
            "spread_pick": r["spread_pick"],
            "spread_pick_final": pick_final,
            "void_reason": _s(r["void_reason"]),
            "qb_news": _s(r["qb_news"]),
            "is_pick": pick_final != "no play",
            # QB availability overlay (2026-10-01): V1 raw is never
            # rewritten; the adjusted prediction is an experimental derived
            # overlay shown alongside the frozen V1 number.
            "qb_overlay": {
                "expected_qb_away": _s(r.get("expected_qb_away", "")) or None,
                "expected_qb_home": _s(r.get("expected_qb_home", "")) or None,
                "qb_change_side": change_side,
                "qb_change_note": _s(r.get("qb_change_note", "")) or None,
                "qb_shift_pts": _n(r.get("qb_shift_pts")) if change_side else None,
                "qb_double_count_risk": _b(r.get("qb_double_count_risk", False)),
                "model_spread_adj": _n(r.get("model_spread_adj")),
                "edge_adj": _n(r.get("edge_adj")),
                "model_win_prob_adj": (model_win_prob_adj
                                       if change_side else None),
                "stale_qb_veto": veto,
                "final_status": final_status,
                "overlay_note": ("Adjusted prediction is an experimental "
                                 "derived overlay, not a V1 rerun. When "
                                 "double-count risk is flagged, the backup "
                                 "already started games in V1's rating sample: "
                                 "treat raw as the aggressive bound and "
                                 "adjusted as the conservative bound."),
            },
        })
    # Provenance sidecar written by 07 (additive; missing = pre-audit run).
    prov = {}
    prov_path = f"{data_root}/predictions_2026_w{wk}.provenance.json"
    if os.path.exists(prov_path):
        with open(prov_path) as f:
            prov = json.load(f)
    else:
        prov = {"note": "provenance sidecar not written for this run "
                        "(pre-2026-09-30 audit)"}
    # ---- live game lines (display only; Friday evaluation numbers untouched) ----
    # Hourly snapshots record both books per game. Display prefers DraftKings
    # (via ESPN, verified working) and falls back to Bovada. market_spread /
    # edge / market_total below stay pinned to the Friday researched line from
    # predictions_2026_w4.csv; the _live fields show the latest captured line.
    gl_snap = None
    try:
        from market_lines_latest import latest_snapshot as _mls2
        gl_snap = _mls2("game_lines", 2026, 4)
    except Exception:  # helper missing/broken -> no live fields
        gl_snap = None
    gl_ts, gl_books = None, {}
    if gl_snap:
        gl_ts = gl_snap.get("captured_at")
        for gg in gl_snap.get("games", []):
            gl_books[gg["game_key"]] = gg.get("books", {})
    for g in games:
        books = gl_books.get(f"{g['away']}_{g['home']}", {})
        dk, bov = books.get("draftkings"), books.get("bovada")
        pref = dk or bov
        g["market_spread_live"] = pref["spread_home"] if pref else None
        g["market_total_live"] = pref["total"] if pref else None
        g["market_live_book"] = ("draftkings" if dk else "bovada") if pref else None
        g["market_live_books"] = {k: v for k, v in
                                  (("draftkings", dk), ("bovada", bov)) if v}
    w(out_dir, {"model_version": ver, "week": wk, "season": 2026,
                "games": games, "provenance": prov,
                "market_lines_captured_at": gl_ts,
                "market_lines_note": ("Latest successfully captured game lines "
                                      "(display only). Picks/edges remain pinned "
                                      "to the Friday researched line."),
                "model_math": model_math_block(lr_elo, lr_epa_m, ens)},
      "predictions.json")

    # ---- model_facts: static methodology facts for the "show me the math"
    # UI level. Every number sourced from repo docs/saved files; nothing
    # invented, nothing refit. Updated only when the research record changes.
    w(out_dir, {
        "model_version": ver,
        "note": ("Static methodology facts for the dashboard's 'how it works' "
                 "levels. Sourced from backtest_report.md and saved model "
                 "files; see sources per section."),
        "identity": {
            "name": "V1",
            "built": "2026-09-11",
            "data": "nflverse 2018-2025 (2,229 games)",
            "method": "walk-forward, no lookahead",
            "source": "backtest_report.md",
        },
        "architecture": {
            "description": ("Ensemble of three margin components predicting "
                            "home-team margin."),
            "components": [
                {"name": "ELO", "weight": 0.4,
                 "what": ("Strength rating from game results; beating stronger "
                          "opponents moves it more. Linear regression maps "
                          "ELO differential to margin.")},
                {"name": "EPA-linear", "weight": 0.5,
                 "what": ("Linear regression on 8 EPA/success-rate "
                          "differentials (offense, defense, pass/rush splits).")},
                {"name": "GBM", "weight": 0.1,
                 "what": ("Gradient boosting on ELO diff, EPA differentials, "
                          "rest-day differential, division-game flag, week; "
                          "captures nonlinear matchup patterns. Refit weekly "
                          "on the expanding window.")},
            ],
            "weights_selected": "tuned by MAE on the 2021-2022 validation window",
            "pick_rule": "paper pick when |predicted margin - market spread| >= 3.0",
            "source": "backtest_report.md",
        },
        "training_periods": {
            "linear_components": "fit 2018-2020",
            "ensemble_weights_and_threshold": "tuned on 2021-2022 validation",
            "gbm": "walk-forward, retrained weekly on expanding window (each prediction used only games already played)",
            "locked_test": "2023-2025 (never used for any selection decision)",
            "source": "backtest_report.md",
        },
        "features": {
            "elo_diff": "home ELO minus away ELO",
            "epa_differentials": [
                "off_epa_diff: offensive EPA/play, home minus away",
                "def_epa_diff: defensive EPA/play allowed, home minus away",
                "off_pass_diff / off_rush_diff: pass/rush EPA/play splits",
                "def_pass_diff / def_rush_diff: pass/rush EPA allowed splits",
                "sr_off_diff / sr_def_diff: offensive/defensive success-rate differential",
            ],
            "gbm_extra": ["rest_diff: rest-day differential",
                          "div_game: division-game flag",
                          "week: week number"],
            "source": "scripts/model_lib.py",
        },
        "elo_methodology": {
            "K": 20.0, "home_field_advantage_elo": 55.0,
            "offseason_regression": "1/3 toward 1500 at each week 1",
            "update": ("weekly batching (all games in a week use pre-week "
                       "ratings); win/loss outcome scaled by a "
                       "margin-of-victory multiplier"),
            "source": "scripts/03_ratings.py",
        },
        "epa_methodology": {
            "plays": "nflverse play-by-play, pass/run plays with non-null EPA",
            "weekly_update": "EWMA with alpha=0.25 on the new week's per-team means",
            "offseason": "35% regression toward league average (0.0) at week 1",
            "metrics": ["off_epa", "off_pass_epa", "off_rush_epa", "off_sr",
                        "def_epa", "def_pass_epa", "def_rush_epa", "def_sr"],
            "source": "scripts/07_update_weekly.py run_epa_current",
        },
        "validation": {
            "method": ("walk-forward: linears fit 2018-2020, GBM retrained "
                       "weekly, weights/threshold tuned on 2021-2022 "
                       "validation, final verdict on locked 2023-2025 test"),
            "locked_test_2023_2025": {
                "ats_record": "140-125 (52.8%, n=265)",
                "roi": "+0.9% at -110 (inside statistical noise; breakeven 52.4% within +/-3.1pp SE)",
                "mae_model": 10.22, "mae_market": 9.79,
                "totals": "not bettable: negative ROI at every threshold",
            },
            "honest_verdict": ("No verified edge. The market's spread predicts "
                               "final margins better than the model (9.79 vs "
                               "10.22 MAE). V1 is the ceiling given this "
                               "information set."),
            "research_status": "frozen 2026-09-29 (RESEARCH_PROGRAM_FREEZE.md)",
            "source": "backtest_report.md",
        },
    }, "model_facts.json")

    # ---- record ----
    rec = pd.read_csv(f"{data_root}/record.csv")
    rows = rec.to_dict("records")
    tw, tl = int(rec["w"].sum()), int(rec["l"].sum())
    clv_rows = rec.dropna(subset=["clv_avg_pts"])
    wsum = float((clv_rows["clv_n"] * clv_rows["clv_avg_pts"]).sum()) if len(clv_rows) else 0.0
    nsum = float(clv_rows["clv_n"].sum()) if len(clv_rows) else 0.0
    w(out_dir, {"model_version": ver, "weeks": rows, "season": {
        "w": tw, "l": tl,
        "win_pct": round(tw / (tw + tl), 3) if tw + tl else None,
        "avg_clv_pts": round(wsum / nsum, 2) if nsum else None,
        "clv_n": int(nsum),
    },
    # Per-pick results ledger (written by 08_grade_week.py): every graded
    # paper pick plus voided picks. NaN -> null via _json_safe.
    "picks": (pd.read_csv(f"{data_root}/pick_results.csv")
              .sort_values(["season", "week", "game"]).to_dict("records")
              if os.path.exists(f"{data_root}/pick_results.csv") else [])}, "record.json")

    # ---- clv ----
    log = pd.read_csv(f"{data_root}/clv_picks.csv") if os.path.exists(f"{data_root}/clv_picks.csv") else pd.DataFrame()
    if len(log):
        d = log[log["result"].isin(["win", "loss"])].copy()
        agg = {"n": int(len(d)),
               "avg_clv_pts": round(float(d["clv_pts"].mean()), 2),
               "hit_rate": round(float((d["clv_pts"] > 0).mean()), 3)}
    else:
        d, agg = log, {"n": 0, "avg_clv_pts": None, "hit_rate": None}
    w(out_dir, {"model_version": ver, "aggregate": agg,
              "picks": log.to_dict("records")}, "clv.json")

    # ---- backtest (recomputed from the parquet; thresholds + seasons) ----
    d = pd.read_parquet(f"{data_root}/games_with_preds.parquet")
    d = d.dropna(subset=["ens_margin", "spread_line", "home_margin"]).copy()
    d["edge"] = d["ens_margin"] - d["spread_line"]

    def ats(frame, t):
        f = frame[frame["edge"].abs() >= t].copy()
        f["bet_home"] = f["edge"] > 0
        f["win"] = np.where(f["bet_home"],
                            f["home_margin"] > f["spread_line"],
                            f["home_margin"] < f["spread_line"])
        f = f[f["home_margin"] != f["spread_line"]]  # drop pushes
        n = len(f)
        w_ = int(f["win"].sum())
        return {"n": n, "w": w_, "l": n - w_,
                "win_pct": round(w_ / n, 3) if n else None,
                "roi": round((w_ * 100 / 110 - (n - w_)) / n, 3) if n else None}

    val = d[d["season"].between(2021, 2022)]
    tst = d[d["season"].between(2023, 2025)]
    by_thresh = {str(t): {"validation_2021_22": ats(val, t),
                          "test_2023_25": ats(tst, t)}
                 for t in [1.5, 2.0, 2.5, 3.0]}

    # cumulative test W-L by week @3.0 (for charts), per-season splits
    t3 = tst[tst["edge"].abs() >= THRESH].copy()
    t3["bet_home"] = t3["edge"] > 0
    t3["win"] = np.where(t3["bet_home"],
                         t3["home_margin"] > t3["spread_line"],
                         t3["home_margin"] < t3["spread_line"])
    t3 = t3[t3["home_margin"] != t3["spread_line"]].sort_values(["season", "week"])
    cum, cw, cl = [], 0, 0
    for _, r in t3.iterrows():
        if r["win"]:
            cw += 1
        else:
            cl += 1
        cum.append({"season": int(r["season"]), "week": int(r["week"]),
                    "w": cw, "l": cl})
    by_season = {str(s): ats(tst[tst["season"] == s], THRESH) for s in [2023, 2024, 2025]}

    mae_model = float((tst["ens_margin"] - tst["home_margin"]).abs().mean())
    mae_mkt = float((tst["spread_line"] - tst["home_margin"]).abs().mean())
    signed_edge = t3["edge"] * np.where(t3["bet_home"], 1, -1)
    edge_cover_corr = float(np.corrcoef(signed_edge, t3["win"].astype(int))[0, 1])

    w(out_dir, {
        "model_version": ver,
        "method": "walk-forward; linears fit 2018-2020, weights/threshold on 2021-2022 validation, reported on 2023-2025 test",
        "by_threshold": by_thresh,
        "test_by_season_at_3": by_season,
        "test_cumulative_at_3": cum,
        "test_mae": {"model": round(mae_model, 2), "market": round(mae_mkt, 2)},
        "test_edge_cover_corr": round(edge_cover_corr, 3),
        "breakeven_at_minus110": 0.524,
    }, "backtest.json")

    # ---- teams: CURRENT ratings first (what V1 actually used) ----
    # Primary: the exact production-state ratings snapshot that generated the
    # Week 4 V1 predictions (reconstructed Sep-25 data state: 2026 W1-W2 +
    # Thursday W3; verified by exact 16/16 reproduction in the provenance
    # audit). Secondary: 2025 final pre-game ratings kept as REFERENCE ONLY.
    cur = pd.read_parquet(f"{data_root}/ratings_current_2026_w{wk}.parquet")
    with open(f"{data_root}/ratings_current_2026_w{wk}.provenance.json") as f:
        cur_prov = json.load(f)
    # 32 current-season teams (drop historical residues like OAK from 2018-19)
    cur32 = sorted(set(sched[sched["season"] == 2026]["home_team"]) |
                   set(sched[sched["season"] == 2026]["away_team"]))
    cur = cur[cur["team"].isin(cur32)]

    def _trow(r):
        get = lambda c: (round(float(r[c]), 3)
                         if pd.notna(r.get(c)) else None)
        return {"team": r["team"], "elo": get("elo"),
                "off_epa": get("off_epa"), "def_epa": get("def_epa"),
                "off_sr": get("off_sr"), "def_sr": get("def_sr"),
                "off_pass_epa": get("off_pass_epa"),
                "off_rush_epa": get("off_rush_epa"),
                "def_pass_epa": get("def_pass_epa"),
                "def_rush_epa": get("def_rush_epa")}
    current_teams = sorted([_trow(r) for _, r in cur.iterrows()],
                           key=lambda x: x["team"])

    # Preseason baseline (reference only): 2025 final pre-game ratings.
    r18 = pd.read_parquet(f"{data_root}/games_with_ratings.parquet")
    r18 = r18[(r18["season"] == 2025) & (r18["week"] == 18)]
    # Per-team provenance: these are PRE-GAME week-18 ratings, so each team's
    # latest included game is its last scored 2025 game before week 18.
    s25 = sched[(sched["season"] == 2025) & (sched["week"] < 18) &
                sched["home_score"].notna()].copy()
    last_gm = {}
    for _, g in s25.iterrows():
        for t in (g["home_team"], g["away_team"]):
            last_gm[t] = g["game_id"]  # iterated in week order; last wins
    base_teams = {}
    for _, r in r18.iterrows():
        for side in ("home", "away"):
            t = r[f"{side}_team"]
            get = lambda c: (round(float(r[c]), 3)
                             if pd.notna(r.get(c)) else None)
            elo_col = "elo_home" if side == "home" else "elo_away"
            base_teams[t] = {
                "team": t,
                "elo": get(elo_col),
                "off_epa": get(f"{side}_off_epa"),
                "def_epa": get(f"{side}_def_epa"),
                "off_sr": get(f"{side}_off_sr"),
                "def_sr": get(f"{side}_def_sr"),
                "off_pass_epa": get(f"{side}_off_pass_epa"),
                "off_rush_epa": get(f"{side}_off_rush_epa"),
                "def_pass_epa": get(f"{side}_def_pass_epa"),
                "def_rush_epa": get(f"{side}_def_rush_epa"),
            }
    w(out_dir, {
        "model_version": ver,
        "label": f"Current Ratings — Pre-Game Week {wk}",
        "season": 2026, "week": wk,
        "data_through": cur_prov["data_through"],
        "data_as_of": cur_prov["data_as_of"],
        "latest_game_included": cur_prov["latest_game_included"],
        "snapshot_generated_at": cur_prov["snapshot_generated_at"],
        "note": ("What V1 actually used for this week's predictions. Ratings "
                 "incorporate completed games through the prediction cutoff; "
                 "Week 4 future games are excluded. Same rating snapshot that "
                 "generated the Week 4 V1 predictions — verified by exact "
                 "16/16 reproduction (see predictions.json provenance)."),
        "teams": current_teams,
        "preseason_baseline": {
            "label": "Preseason Baseline — 2026",
            "season": 2025, "week": 18,
            "data_as_of": str(s25["gameday"].max()),
            "note": ("Reference only — opening 2026 ratings (2025 final "
                     "pre-game ratings). NOT the ratings driving current "
                     "predictions."),
            "teams": sorted(base_teams.values(), key=lambda x: x["team"]),
        }}, "teams.json")

    # ---- props (latest available week) ----
    # Player Projection v2 (new): data/prop_v2_2026_w*.json written by
    # scripts/16_prod_player_projection.py. Falls back to the legacy
    # prop_gaps CSV only if no v2 file exists yet.
    import glob, re
    # Main v2 yards file only: exclude suffixed experimental variants
    # (prop_v2_2026_w4_receptions.json / _rush_attempts.json) so the
    # alphabetical-last pick can't silently swap the whole props export.
    v2files = sorted(f for f in glob.glob(f"{data_root}/prop_v2_2026_w*.json")
                     if re.fullmatch(r"prop_v2_2026_w\d+\.json", f.split("/")[-1]))
    if v2files:
        with open(v2files[-1]) as f:
            v2 = json.load(f)
        pw, props = v2["week"], v2["projections"]
        v2model, v2ts, v2discl = v2["model"], v2["prediction_timestamp"], v2["disclaimer"]
    else:
        pfiles = sorted(glob.glob(f"{data_root}/prop_gaps_2026_w*.csv"))
        if pfiles:
            pf = pfiles[-1]
            pw = int(pf.split("_w")[-1].split(".")[0])
            props = pd.read_csv(pf).to_dict("records")
        else:
            pw, props = None, []
        v2model, v2ts, v2discl = ("Prop projector v1 (EWMA)", None,
                                  "paper tracking only")
    w(out_dir, {"model_version": ver, "week": pw, "season": 2026,
       "model": v2model, "prediction_timestamp": v2ts,
       "disclaimer": v2discl,
       "note": "paper tracking only; no verified edge is claimed",
       "props": props}, "props.json")
    # ---- prop market lines (join; never impute) ----
    # Hourly snapshots (scripts/31_pull_market_lines_hourly.py) via
    # scripts/market_lines_latest.py (newest *successful* snapshot, so a
    # throttled hour never blanks display lines); falls back to the legacy
    # Friday file data/market_props/market_props_{season}_w{week}.json from 30.
    # market_line populates only where a real captured line exists; else null.
    if pw is not None:
        mp, mp_from = None, None
        try:
            from market_lines_latest import latest_snapshot as _mls
            mp = _mls("prop_lines", 2026, pw)
            if mp is not None:
                mp_from = "hourly snapshot"
        except Exception:  # helper missing/broken -> legacy path
            mp = None
        if mp is None:
            mp_path = f"{data_root}/market_props/market_props_2026_w{pw}.json"
            if os.path.exists(mp_path):
                with open(mp_path) as f:
                    mp = json.load(f)
                mp_from = mp_path
        if mp is not None:
            line_lu = {(l["player"], l["team"], l["market"]): l["line"]
                       for l in mp["lines"] if l["player"]}
            n_filled = 0
            for r in props:
                hit = line_lu.get((r.get("player"), r.get("team"), r.get("market")))
                r["market_line"] = float(hit) if hit is not None else None
                if hit is not None:
                    n_filled += 1
            # re-write with lines joined (props.json was just written above)
            pj = json.load(open(f"{out_dir}/props.json"))
            pj["props"] = props
            pj["market_lines_source"] = mp["source"]
            pj["market_lines_captured_at"] = mp["captured_at"]
            w(out_dir, pj, "props.json")
            print(f"props market_line: {n_filled}/{len(props)} filled from {mp_from}")

    # ---- injuries (current availability from the Phase-1 injury pipeline) ----
    # Dedicated block: as-of timestamp, status counts, starting-QB flags,
    # and the most recent diff. The Friday prediction uses the frozen file;
    # this block always reflects the LATEST snapshot (live view).
    inj_block = {"available": False}
    cur_path = f"{data_root}/injuries/availability_current.json"
    if os.path.exists(cur_path):
        with open(cur_path) as f:
            cur = json.load(f)
        last_diff = None
        dlog = f"{data_root}/injuries/logs/diff_log.jsonl"
        if os.path.exists(dlog):
            with open(dlog) as f:
                lines = [ln for ln in f if ln.strip()]
            if lines:
                last_diff = json.loads(lines[-1])
        friday_files = sorted(
            f for f in os.listdir(f"{data_root}/injuries")
            if f.startswith("availability_friday_") and f.endswith(".json"))
        inj_block = {
            "available": True,
            "as_of": cur.get("as_of"),
            "snapshot_rows": cur.get("snapshot_rows"),
            "status_counts": cur.get("status_counts", {}),
            "starting_qb_flags": cur.get("starting_qb_flags", []),
            "n_notable_injuries": len(cur.get("notable_injuries", [])),
            "notable_injuries": cur.get("notable_injuries", [])[:50],
            "latest_diff": last_diff,
            "friday_frozen_files": friday_files,
            "note": cur.get("note", ""),
        }
    w(out_dir, {"model_version": ver, "season": 2026, **inj_block}, "injuries.json")

    print("done.")


def write_manifest():
    """Regenerate data/ui_json/versions.json: which model versions have
    exported data. The frontend builds its version selector from this file."""
    versions = []
    if os.path.isdir(UI_ROOT):
        for entry in sorted(os.listdir(UI_ROOT)):
            d = os.path.join(UI_ROOT, entry)
            meta = os.path.join(d, "meta.json")
            if os.path.isdir(d) and os.path.isfile(meta):
                try:
                    m = json.load(open(meta))
                    versions.append({
                        "version": m.get("model_version", entry.upper()),
                        "dir": entry,
                        "status": ("production" if m.get("model_version", "").upper() == "V1"
                                   else "experimental"),
                        "generated_at": m.get("generated_at", ""),
                        "season": m.get("season"),
                        "latest_week": m.get("latest_week"),
                    })
                except Exception:
                    continue
    manifest = {"default": "V1", "versions": versions}
    p = os.path.join(UI_ROOT, "versions.json")
    with open(p, "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"wrote {p}: {[v['version'] for v in versions]}")


if __name__ == "__main__":
    main()
    write_manifest()
