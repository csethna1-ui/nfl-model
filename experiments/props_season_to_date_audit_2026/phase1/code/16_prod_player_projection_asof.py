#!/usr/bin/env python3
"""Player Projection v2 -- Experimental Production (weekly engine).

Productionizes the FROZEN Player Projection Experiment 001 models. This is
productionization, not new research: no model is fit here beyond reproducing
the experiment's exact fit procedure (train 2018-2020, select on dev
2021-2022). Nothing is ever fit on the 2023-2024 locked test.

Provenance:
  experiments/player_props_projection/PREREGISTRATION.md (approved+re-frozen)
  experiments/player_props_projection/RESULTS.md  (bar NOT cleared; pass-market
      gains real, mechanism supported; A ~= B; rush/receiving near-nulls)
  experiments/player_props_projection/scripts/run_experiment_001.py
      (fit/predict functions imported verbatim -- the identical procedure)

What runs each week (Friday, after the spread pipeline -- never blocking V1):
  1. --refresh : keyless nflverse refresh (2026 pbp slim + rich, aggregates,
     aux snap/injury/depth data best-effort).
  2. --fit     : reproduce the frozen fit (train/dev), verify dev MAE matches
     RESULTS.md exactly, calibrate uncertainty thresholds on dev, persist
     models to data/prod_player_models_v2.pkl. Run once; weekly runs load it.
  3. --season 2026 --week N [--market-json ...] : build feature rows for the
     week's games (Friday 18:00 America/Chicago cutoff), predict with
     Baseline / A / B / C / D, join market lines (projection -> line -> lean),
     write data/prop_v2_2026_wN.json.

Hard rules (from the authorization):
  - PFT/news = OFF. No news features anywhere.
  - No retraining on 2023-2024, no architecture changes from the results.
  - Do not touch V1, the spread pipeline, Experiment 006, or the PFT corpus.
  - Keyless data only. Weather excluded (game-time observations leak).

Usage:
  ./venv/bin/python scripts/16_prod_player_projection.py --fit
  ./venv/bin/python scripts/16_prod_player_projection.py --refresh
  ./venv/bin/python scripts/16_prod_player_projection.py --season 2026 --week 4 \
      --market-json data/market_props_2026_w4.json
"""
import argparse
import importlib.util
import json
import os
import pickle
import re
import subprocess
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = os.path.expanduser("~/workspace/nfl-model")
DATA = os.path.join(REPO, "data")
# AS-OF RECONSTRUCTION (Phase 1 props audit, 2026-10-01): --data-dir overrides
# DATA so weekly runs read truncated as-of caches. Applied in main(); the
# frozen original scripts/16_prod_player_projection.py is untouched.
_DATA_DIR_OVERRIDE = None
EXP = os.path.join(REPO, "experiments/player_props_projection")
EXP_DATA = os.path.join(EXP, "data")
EXP_SCRIPTS = os.path.join(EXP, "scripts")

CHI = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")

MODEL_PATH = os.path.join(DATA, "prod_player_models_v2.pkl")
META_PATH = os.path.join(DATA, "prod_player_models_v2_meta.json")

HALF_LIFE = 3.0
MAX_TRAIL = 16
MIN_GAMES = 3

MARKET_OF = {"QB": "pass_yards", "RB": "rush_yards", "WRTE": "receiving_yards"}
YCOL = {"pass_yards": "pass_yards", "rush_yards": "rush_yards",
        "receiving_yards": "receiving_yards"}
ATT_COL = {"pass_yards": "pass_att", "rush_yards": "rush_att",
           "receiving_yards": "targets"}
OPP_UNIT = {"pass_yards": "pass attempts", "rush_yards": "carries",
            "receiving_yards": "targets"}
EFF_UNIT = {"pass_yards": "yards/attempt", "rush_yards": "yards/carry",
            "receiving_yards": "yards/target"}
ROLE_NEED = {"pass_yards": 10, "rush_yards": 5, "receiving_yards": 5}

DISCLAIMER = ("Experimental NFL analytics / paper-tracking system. "
              "Player Projection v2 did not clear its preregistered "
              "improvement bar (see Experiment 001 results); it is a "
              "better-performing tested specification, not a validated "
              "best model. No verified betting edge. Not betting advice; "
              "no real-money recommendations.")
MODEL_LABEL = "Player Projection v2 \u2014 Experimental Production"


def _load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


print("loading frozen experiment modules...", flush=True)
X = _load_mod("exp001", os.path.join(EXP_SCRIPTS, "run_experiment_001.py"))
P10 = _load_mod("prop10", os.path.join(REPO, "scripts/10_prop_projector.py"))

MARKETS = X.MARKETS  # ["pass_yards", "rush_yards", "receiving_yards"]


def ewma(v):
    """Trailing EWMA, half-life 3, most-recent-first. (Same as experiment.)"""
    v = np.asarray(v, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return np.nan
    w = 0.5 ** (np.arange(len(v)) / HALF_LIFE)
    return float(np.sum(w * v) / np.sum(w))


def friday_timestamp(kickoffs):
    """Friday 18:00 America/Chicago of game week. (Same rule as experiment.)"""
    dates = sorted({k.date() for k in kickoffs})
    sundays = [d for d in dates if d.weekday() == 6]
    anchor = sundays[0] if sundays else min(dates)
    if anchor.weekday() == 6:
        friday = anchor - timedelta(days=2)
    else:
        friday = anchor - timedelta(days=(anchor.weekday() - 4) % 7)
    return datetime(friday.year, friday.month, friday.day, 18, 0, tzinfo=CHI)


# ------------------------------------------------------------------ refresh
RICH_WANT = ["game_id", "season", "week", "season_type", "posteam", "defteam",
             "play_type", "passer_player_name", "rusher_player_name",
             "receiver_player_name", "passing_yards", "rushing_yards",
             "receiving_yards", "air_yards", "yards_after_catch",
             "complete_pass", "yardline_100"]


def refresh_data(season=2026):
    """Keyless nflverse refresh for the weekly run. Idempotent.

    - slim pbp for `season` (via scripts/pull_pbp_players.py --refresh-season)
    - rich pbp for 2025 and `season` (experiment cache covers 2018-2024;
      production keeps its own 2025+ files, never touching experiment files)
    - rebuilds player_games.parquet + team_defense.parquet (build_aggregates
      from scripts/10_prop_projector.py -- same procedure as the old projector)
    - best-effort aux pulls: snap counts, injuries, depth charts (NOT model
      features; documented for context/future use only)
    """
    import nfl_data_py as nfl

    print(f"--- refresh: slim pbp {season} ---", flush=True)
    subprocess.run([sys.executable,
                    os.path.join(REPO, "scripts/pull_pbp_players.py"),
                    "--refresh-season", str(season)], check=True)

    print("--- refresh: rich pbp 2025+ (production cache) ---", flush=True)
    for s in (2025, season):
        out = os.path.join(DATA, f"prod_pbp_rich_{s}.parquet")
        if os.path.exists(out):
            print(f"  {s}: cached, skipping "
                  f"(delete {out} to force re-pull)", flush=True)
            continue
        print(f"  {s}: downloading...", flush=True)
        df = nfl.import_pbp_data([s])
        cols = [c for c in RICH_WANT if c in df.columns]
        missing = set(RICH_WANT) - set(df.columns)
        if missing:
            print(f"  WARNING missing cols: {missing}", flush=True)
        df = df[df["season_type"] == "REG"][cols].copy()
        df.to_parquet(out, index=False)
        print(f"  saved {out} ({len(df)} REG rows)", flush=True)
        del df

    print("--- rebuild player_games + team_defense aggregates ---", flush=True)
    P10.build_aggregates()

    print("--- aux pulls (best-effort, NOT model features) ---", flush=True)
    aux_report = {}
    aux_jobs = {
        "snap_counts": ("prod_aux_snap_counts.parquet",
                        lambda: nfl.import_snap_counts([season])),
        "injuries": ("prod_aux_injuries.parquet",
                     lambda: nfl.import_injuries([season])),
        "depth_charts": ("prod_aux_depth_charts.parquet",
                         lambda: nfl.import_depth_charts([season])),
    }
    for label, (fname, fn) in aux_jobs.items():
        out = os.path.join(DATA, fname)
        try:
            df = fn()
            df.to_parquet(out, index=False)
            aux_report[label] = {"status": "ok", "rows": int(len(df)),
                                 "file": fname}
            print(f"  {label}: ok ({len(df)} rows)", flush=True)
        except Exception as e:  # noqa: BLE001 -- best-effort by design
            aux_report[label] = {"status": "failed", "error": str(e)[:200]}
            print(f"  {label}: FAILED ({str(e)[:120]})", flush=True)
    with open(os.path.join(DATA, "prod_aux_report.json"), "w") as f:
        json.dump({"season": season, "pulled_at": datetime.now(CHI).isoformat(),
                   "aux": aux_report,
                   "note": "Aux data are context only; the frozen models use "
                           "exactly the 44 experiment columns."}, f, indent=1)
    print("refresh complete.", flush=True)
    return aux_report


# ------------------------------------------------- frozen fit reproduction
# Published dev-selection outcomes (RESULTS.md) -- the reproduction must
# recover these exactly, or abort. This is the proof the production models
# are the tested ones.
PUBLISHED_DEV_MAE = {
    "pass_yards": {"baseline": 65.75, "A": 58.69, "B": 58.52,
                   "C": 59.26, "D": 57.77},
    "rush_yards": {"baseline": 26.82, "A": 25.32, "B": 25.78,
                   "C": 25.37, "D": 25.15},
    "receiving_yards": {"baseline": 25.01, "A": 24.43, "B": 24.23,
                        "C": 23.98, "D": 23.98},
}
PUBLISHED_SELECTION = {
    "a_alpha": 10.0,
    "b_params": {"learning_rate": 0.05, "max_depth": 3, "max_iter": 200},
}


def fit_frozen_models():
    """Reproduce the Experiment 001 fit procedure EXACTLY.

    Fit on train (2018-2020) only; select on dev (2021-2022) only -- the same
    code path as scripts/run_experiment_001.py (functions imported verbatim).
    Never touches the 2023-2024 test slice.
    """
    D = X.load()  # evaluated rows only, per the experiment's own loader
    fitted, dev_mae = {}, {}
    for market in MARKETS:
        tr, dv = D["train"][market], D["dev"][market]
        ydv = dv["actual_yards"].to_numpy(float)

        # A: ridge alpha selected on dev
        a_cands = {}
        for a in X.A_ALPHAS:
            m = X.fit_A(tr, market, a)
            a_cands[a] = (m, X.mae(ydv, X.pred_A(m, dv)))
        a_alpha = min(a_cands, key=lambda a: a_cands[a][1])
        A = a_cands[a_alpha][0]

        # B: 8-combo grid selected on dev
        b_cands = {}
        for i, gp in enumerate(X.B_GRID):
            m = X.fit_B(tr, market, gp)
            b_cands[i] = (m, X.mae(ydv, X.pred_B(m, dv)), gp)
        b_key = min(b_cands, key=lambda i: b_cands[i][1])
        B, b_params = b_cands[b_key][0], b_cands[b_key][2]

        # C: fixed a priori (no selection)
        C = X.fit_C(tr, market)

        fitted[market] = {"A": A, "B": B, "C": C,
                          "a_alpha": a_alpha, "b_params": b_params}
        pA, pB, pC = X.pred_A(A, dv), X.pred_B(B, dv), X.pred_C(C, dv)
        dev_mae[market] = {
            "baseline": X.mae(ydv, X.baseline_pred(dv, market)),
            "A": X.mae(ydv, pA), "B": X.mae(ydv, pB),
            "C": X.mae(ydv, pC), "D": X.mae(ydv, (pA + pB + pC) / 3.0),
            "n": len(dv),
        }
        print(f"[{market}] reproduced dev MAE: " +
              " ".join(f"{k}={v:.2f}" for k, v in dev_mae[market].items()
                       if k != "n") +
              f" | a_alpha={a_alpha} b={b_params}", flush=True)
    return fitted, dev_mae, D


def calibrate_thresholds(fitted, D):
    """Uncertainty/confidence thresholds from DEV relative widths.

    rel_width = (p75 - p25) / max(median, 1). Dev is the legitimate selection
    ground; the locked test is never used for any production decision.
    """
    cal = {}
    for market in MARKETS:
        dv = D["dev"][market]
        C = fitted[market]["C"]
        p25 = X.pred_C(C, dv, 0.25)
        p50 = X.pred_C(C, dv, 0.5)
        p75 = X.pred_C(C, dv, 0.75)
        rw = (p75 - p25) / np.maximum(p50, 1.0)
        cal[market] = {
            "p33": float(np.percentile(rw, 33)),
            "p67": float(np.percentile(rw, 67)),
            "p90": float(np.percentile(rw, 90)),
            "n": int(len(dv)),
        }
        print(f"[{market}] dev rel-width pctls: " +
              " ".join(f"{k}={v:.3f}" for k, v in cal[market].items()
                       if k != "n"), flush=True)
    return cal


def do_fit():
    fitted, dev_mae, D = fit_frozen_models()

    # ---- verification: reproduction must match the published experiment ----
    for market in MARKETS:
        pub = PUBLISHED_DEV_MAE[market]
        for k in ("baseline", "A", "B", "C", "D"):
            got, want = dev_mae[market][k], pub[k]
            if abs(got - want) > 0.01:
                raise SystemExit(
                    f"REPRODUCTION MISMATCH [{market}] {k}: got {got:.4f}, "
                    f"published {want:.2f}. Aborting -- production models "
                    f"must be the tested ones.")
        if fitted[market]["a_alpha"] != PUBLISHED_SELECTION["a_alpha"]:
            raise SystemExit("A alpha selection mismatch -- aborting.")
        bp = fitted[market]["b_params"]
        want_bp = PUBLISHED_SELECTION["b_params"]
        if not (bp["learning_rate"] == want_bp["learning_rate"]
                and bp["max_depth"] == want_bp["max_depth"]
                and bp["max_iter"] == want_bp["max_iter"]):
            raise SystemExit("B grid selection mismatch -- aborting.")
    print("VERIFIED: reproduced dev MAE and selections match RESULTS.md.",
          flush=True)

    cal = calibrate_thresholds(fitted, D)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump({m: {"A": fitted[m]["A"], "B": fitted[m]["B"],
                       "C": fitted[m]["C"]} for m in MARKETS}, f)
    meta = {
        "model": MODEL_LABEL,
        "fit_procedure": "Experiment 001 reproduced exactly: fit on train "
                         "2018-2020, select on dev 2021-2022. Test slice "
                         "never touched.",
        "fit_at": datetime.now(CHI).isoformat(),
        "selection": {m: {"a_alpha": fitted[m]["a_alpha"],
                          "b_params": fitted[m]["b_params"]}
                      for m in MARKETS},
        "dev_mae_reproduced": dev_mae,
        "dev_mae_published": PUBLISHED_DEV_MAE,
        "uncertainty_calibration": {
            "rule": "uncertainty_flag = (p75-p25)/max(median,1) > "
                    "market p90 of dev relative widths; confidence = "
                    "High/Medium/Low by dev p33/p67 cutoffs.",
            "per_market": cal,
        },
        "provenance": "experiments/player_props_projection/PREREGISTRATION.md "
                      "+ RESULTS.md (frozen 2026-09-30)",
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=1)
    print(f"saved {MODEL_PATH} and {META_PATH}", flush=True)


# ------------------------------------------------------- weekly features
# Same per-game merge + trailing-EWMA procedure as
# experiments/player_props_projection/scripts/build_modeling_table.py,
# but emitting rows only for the target (season, week).
TRAIL_FEATS = ["pass_yards", "rush_yards", "receiving_yards",
               "pass_att", "rush_att", "targets", "air_yards", "yac",
               "rz_targets", "rz_carries", "completions",
               "target_share", "rush_share", "air_share",
               "ypt", "ypc", "ypa", "comp_rate", "yac_pt",
               "team_targets", "team_pass_att", "team_rush_att"]


def _rich_aggregates(rich):
    r = rich[rich["play_type"].isin(["pass", "run"])].copy()
    r["is_rz"] = r["yardline_100"] <= 20
    key = ["season", "week", "game_id"]

    recv = r[r["receiver_player_name"].notna()].copy()
    g = recv.groupby(["receiver_player_name", "posteam", "defteam"] + key,
                     dropna=False)
    prec = g.agg(targets_rich=("receiver_player_name", "size"),
                 air_yards=("air_yards", "sum"),
                 yac=("yards_after_catch", "sum"),
                 receptions=("complete_pass", "sum"),
                 rz_targets=("is_rz", "sum")).reset_index().rename(
        columns={"receiver_player_name": "player_name", "posteam": "team"})

    rush = r[r["rusher_player_name"].notna()].copy()
    g = rush.groupby(["rusher_player_name", "posteam", "defteam"] + key,
                     dropna=False)
    prush = g.agg(rz_carries=("is_rz", "sum")).reset_index().rename(
        columns={"rusher_player_name": "player_name", "posteam": "team"})

    pss = r[r["passer_player_name"].notna()].copy()
    g = pss.groupby(["passer_player_name", "posteam", "defteam"] + key,
                    dropna=False)
    ppass = g.agg(completions=("complete_pass", "sum")).reset_index().rename(
        columns={"passer_player_name": "player_name", "posteam": "team"})

    tg = r.groupby(["posteam", "season", "week", "game_id"], dropna=False)
    team_g = tg.agg(
        team_targets=("receiver_player_name", lambda s: s.notna().sum()),
        team_pass_att=("play_type", lambda s: (s == "pass").sum()),
        team_rush_att=("play_type", lambda s: (s == "run").sum()),
        team_air_yards=("air_yards", "sum")).reset_index().rename(
        columns={"posteam": "team"})
    return prec, prush, ppass, team_g


def build_week_frame(season, week, pred_ts_override=None):
    """One row per (player, market) for the upcoming week's games.

    Cutoff discipline: prediction timestamp = Friday 18:00 America/Chicago of
    game week; every trailing feature uses games strictly before
    (season, week); games kicking off at/before the timestamp are excluded.

    AS-OF RECONSTRUCTION: pred_ts_override (ISO string) replaces the
    Sunday-anchored friday_timestamp() computation, so the audit can pin the
    exact task-specified Friday 18:00 CT timestamps per week.
    """
    pg = pd.read_parquet(os.path.join(DATA, "player_games.parquet"))
    td = pd.read_parquet(os.path.join(DATA, "team_defense.parquet"))
    sched = pd.read_parquet(os.path.join(DATA, "schedules_2018_2025.parquet"))
    rich_parts = [pd.read_parquet(
        os.path.join(EXP_DATA, "pbp_rich_2018_2024.parquet"))]
    for s in (2025, season):
        p = os.path.join(DATA, f"prod_pbp_rich_{s}.parquet")
        if os.path.exists(p):
            rich_parts.append(pd.read_parquet(p))
    rich = pd.concat(rich_parts, ignore_index=True)
    print(f"caches: player_games {len(pg)}, team_defense {len(td)}, "
          f"rich pbp {len(rich)}", flush=True)

    # ---- schedules: kickoff, prediction timestamp, upcoming games ----
    sched = sched[(sched["game_type"] == "REG") &
                  (sched["season"] == season) & (sched["week"] == week)].copy()
    if sched.empty:
        raise SystemExit(f"no REG games found for {season} week {week}")
    sched["kickoff"] = (pd.to_datetime(sched["gameday"].astype(str) + " " +
                                       sched["gametime"].astype(str))
                        .dt.tz_localize(ET))
    if pred_ts_override is not None:
        # AS-OF RECONSTRUCTION: task-pinned Friday 18:00 CT timestamp.
        pred_ts = datetime.fromisoformat(pred_ts_override)
        if pred_ts.tzinfo is None:
            pred_ts = pred_ts.replace(tzinfo=CHI)
        print(f"prediction timestamp (OVERRIDE): {pred_ts.isoformat()}",
              flush=True)
    else:
        pred_ts = friday_timestamp(sched["kickoff"])
        print(f"prediction timestamp: {pred_ts.isoformat()}", flush=True)
    wk = sched[sched["kickoff"] > pred_ts.astimezone(ET)].copy()
    n_excl = len(sched) - len(wk)
    if n_excl:
        print(f"excluded {n_excl} game(s) kicking off at/before the "
              f"timestamp", flush=True)
    if wk["spread_line"].isna().any() or wk["total_line"].isna().any():
        print("WARNING: missing spread/total for some games -- those rows "
              "will be dropped (game-script features unknown pre-kickoff).",
              flush=True)
        wk = wk.dropna(subset=["spread_line", "total_line"])
    wk["imp_home"] = wk["total_line"] / 2 + wk["spread_line"] / 2

    game_of = {}   # team -> game row
    for _, g in wk.iterrows():
        game_of[g["home_team"]] = g
        game_of[g["away_team"]] = g

    # ---- merged per-game base (same recipe as the experiment) ----
    base = pg[pg["season"] <= season].copy()
    prec, prush, ppass, team_g = _rich_aggregates(rich)
    mkeys = ["player_name", "team", "season", "week", "game_id"]
    for df_ in (prec, prush, ppass):
        df_.drop(columns=["defteam"], inplace=True, errors="ignore")
    base = base.merge(prec, on=mkeys, how="left")
    base = base.merge(prush, on=mkeys, how="left")
    base = base.merge(ppass, on=mkeys, how="left")
    base = base.merge(team_g, on=["team", "season", "week", "game_id"],
                      how="left")
    for c in ["air_yards", "yac", "receptions", "rz_targets",
              "rz_carries", "completions"]:
        base[c] = base[c].fillna(0)
    base["target_share"] = (base["targets"] /
                            base["team_targets"].replace(0, np.nan))
    base["rush_share"] = (base["rush_att"] /
                          base["team_rush_att"].replace(0, np.nan))
    base["air_share"] = (base["air_yards"] /
                         base["team_air_yards"].replace(0, np.nan))
    base["ypt"] = base["receiving_yards"] / base["targets"].replace(0, np.nan)
    base["ypc"] = base["rush_yards"] / base["rush_att"].replace(0, np.nan)
    base["ypa"] = base["pass_yards"] / base["pass_att"].replace(0, np.nan)
    base["comp_rate"] = (base["completions"] /
                         base["pass_att"].replace(0, np.nan))
    base["yac_pt"] = base["yac"] / base["targets"].replace(0, np.nan)
    base = base.sort_values(["player_name", "season", "week"])

    # ---- opponent trailing defense (strictly prior weeks) ----
    td = td.sort_values(["team", "season", "week"]).reset_index(drop=True)
    td_hist = {}
    for team, g in td.groupby("team"):
        g = g.reset_index(drop=True)
        td_hist[team] = g
    lg_week = td.groupby(["season", "week"], as_index=False)[
        ["pass_allowed", "rush_allowed"]].mean()

    def opp_allowed(opp, stat):
        g = td_hist.get(opp)
        if g is None:
            return np.nan, np.nan
        m = (g["season"] < season) | ((g["season"] == season) &
                                     (g["week"] < week))
        hist = g[m].iloc[::-1].head(MAX_TRAIL)
        val = ewma(hist[stat].to_numpy()) if len(hist) else np.nan
        lg = lg_week[(lg_week["season"] == season) & (lg_week["week"] < week)]
        lg_avg = float(lg[stat].mean()) if len(lg) else np.nan
        return val, lg_avg

    # ---- player-team / position mapping ----
    # Most recent team; position from the most recent season with >=3 games
    # (documented early-season adaptation of the experiment's season touch-mix
    # rule, which is the full-season special case of this rule).
    pg_recent = pg[pg["season"] <= season].sort_values(
        ["player_name", "season", "week"])
    # Current-season eligibility -- AS-OF ADAPTATION for the W1-W3
    # reconstruction (documented in PHASE1_NOTES.md). The frozen script's
    # gate ("most recent cached game is in the current season") was added
    # 2026-09-30, after W1-W3; run against an as-of cache it would empty the
    # W1 universe entirely (no 2026 games exist as of Friday 9/4). As-of
    # reading of the gate's intent (exclude long-retired/inactive players
    # whose stale history passes the trailing guards): a player is eligible
    # iff they have >=1 game in the 2025 season OR >=1 game in `season` with
    # week < `week`. Both conditions are strictly as-of -- no W1-W3 outcomes
    # are used. The fitted models are untouched.
    eligible_players, n_inelig = set(), 0
    for p, g in pg_recent.groupby("player_name"):
        seasons = set(g["season"].unique())
        has_cur = bool(((g["season"] == season) & (g["week"] < week)).any())
        if has_cur or (2025 in seasons):
            eligible_players.add(p)
        else:
            n_inelig += 1
    print(f"eligibility (as-of): {len(eligible_players)} eligible players; "
          f"{n_inelig} retired/inactive players excluded", flush=True)
    player_team, player_pos = {}, {}
    for p, g in pg_recent.groupby("player_name"):
        if p not in eligible_players:
            continue  # retired/inactive: no game in the current season
        player_team[p] = g.iloc[-1]["team"]
        pos = None
        for s in sorted(g["season"].unique(), reverse=True):
            gs = g[g["season"] == s]
            if len(gs) >= MIN_GAMES:
                pos = gs.iloc[-1]["position"]
                break
        player_pos[p] = pos or g.iloc[-1]["position"]

    # league-average implied total for the week (team-environment note)
    wk = wk.copy()
    wk["imp_home"] = wk["total_line"] / 2 + wk["spread_line"] / 2
    wk["imp_away"] = wk["total_line"] / 2 - wk["spread_line"] / 2
    lg_imp_avg = float(pd.concat([wk["imp_home"], wk["imp_away"]]).mean())

    rows = []
    for p, g in base.groupby("player_name"):
        team = player_team.get(p)
        if team not in game_of:
            continue  # team not playing (or game excluded)
        gm = game_of[team]
        pos = player_pos.get(p)
        market = MARKET_OF.get(pos)
        if market is None:
            continue
        is_home = 1 if team == gm["home_team"] else 0
        opp = gm["away_team"] if is_home else gm["home_team"]

        hist = g[(g["season"] < season) |
                 ((g["season"] == season) & (g["week"] < week))]
        hist = hist.iloc[::-1].head(MAX_TRAIL)  # recent-first
        n = len(hist)
        if n < MIN_GAMES:
            continue
        att_col = ATT_COL[market]
        if float(hist[att_col].sum()) < ROLE_NEED[market]:
            continue  # trailing role guard (mirrors experiment)

        row = {"player_name": p, "team": team, "opponent": opp,
               "season": season, "week": week, "position": pos,
               "market": market, "trail_games": n,
               "prediction_timestamp": pred_ts.isoformat()}
        for c in TRAIL_FEATS:
            row["trail_" + c + "_ewma"] = (ewma(hist[c].to_numpy())
                                           if n else 0.0)
        # recent usage: last-3 mean opportunity vs trailing EWMA
        opp_hist = hist[att_col].to_numpy()[:3]
        trail_opp = row["trail_" + att_col + "_ewma"]
        row["_recent_opp_mean"] = float(np.mean(opp_hist)) if len(opp_hist) else 0.0
        row["_trail_opp_ewma"] = float(trail_opp) if trail_opp else 0.0

        stat = ("pass_allowed" if market in ("pass_yards", "receiving_yards")
                else "rush_allowed")
        # Both opponent-trailing columns are populated for every row, exactly
        # as in the experiment's table (B/C consume both features).
        o_pass, lg_pass = opp_allowed(opp, "pass_allowed")
        o_rush, lg_rush = opp_allowed(opp, "rush_allowed")
        row["opp_trail_pass_allowed_ewma"] = (float(o_pass)
                                             if not np.isnan(o_pass) else 0.0)
        row["opp_trail_rush_allowed_ewma"] = (float(o_rush)
                                             if not np.isnan(o_rush) else 0.0)
        o_val, o_lg = (o_pass, lg_pass) if stat == "pass_allowed" else (o_rush, lg_rush)
        row["_opp_allowed"] = float(o_val) if not np.isnan(o_val) else np.nan
        row["_opp_lg_avg"] = float(o_lg) if not np.isnan(o_lg) else np.nan

        spread = float(gm["spread_line"])
        total = float(gm["total_line"])
        team_spread = -spread if is_home else spread
        row["spread_line"] = spread
        row["total_line"] = total
        row["is_home"] = is_home
        row["team_spread"] = team_spread
        row["team_implied_total"] = total / 2 - team_spread / 2
        row["opp_implied_total"] = total / 2 + team_spread / 2
        row["_lg_imp_avg"] = lg_imp_avg
        rows.append(row)

    wf = pd.DataFrame(rows)
    if wf.empty:
        raise SystemExit("no eligible player-weeks built -- check caches")
    # NaN -> 0 for rate/share trailing features (same convention as experiment)
    feat_cols = [c for c in wf.columns
                 if c.startswith("trail_") or c.startswith("opp_")]
    wf[feat_cols] = wf[feat_cols].fillna(0)
    print(f"week frame: {len(wf)} eligible player-weeks "
          f"({wf['market'].value_counts().to_dict()})", flush=True)
    # AS-OF RECONSTRUCTION instrumentation: persist the feature frame so the
    # audit can compute trailing-opportunity and rich-pbp coverage diagnostics
    # without re-running feature construction. Additive only; predictions
    # below consume the identical `wf`.
    wf_path = os.path.join(DATA, f"week_frame_{season}_w{week}.parquet")
    wf.to_parquet(wf_path, index=False)
    print(f"week frame dumped: {wf_path}", flush=True)
    return wf, pred_ts


# --------------------------------------------- prediction + explanation
def prod_pred_A(model, df):
    """Model A point + stage outputs (same math as the experiment's pred_A)."""
    s1, r1, s2, r2 = model
    o = np.maximum(r1.predict(s1.transform(df[X.OPPORTUNITY_FEATS].to_numpy(float))), 0.0)
    e = r2.predict(s2.transform(df[X.EFFICIENCY_FEATS].to_numpy(float)))
    return np.maximum(o * e, 0.0), o, e


def why_block(r, opp_exp, eff_exp):
    """Rule-based 'why' from trailing/pre-kickoff data only. All cutoffs are
    fixed and documented; nothing here is fit or tuned."""
    why = {
        "expected_opportunities": round(float(opp_exp), 1),
        "opportunity_unit": OPP_UNIT[r["market"]],
        "expected_efficiency": round(float(eff_exp), 2),
        "efficiency_unit": EFF_UNIT[r["market"]],
    }
    # recent usage: last-3 mean opportunity vs trailing EWMA
    t, m3 = r["_trail_opp_ewma"], r["_recent_opp_mean"]
    if t > 0:
        ratio = m3 / t
        why["recent_usage_note"] = ("elevated" if ratio > 1.15 else
                                    "reduced" if ratio < 0.85 else "stable")
    else:
        why["recent_usage_note"] = "stable"
    # team environment: implied total vs the week's league average
    imp, lg = r["team_implied_total"], r["_lg_imp_avg"]
    why["team_environment"] = ("favorable" if imp >= lg + 2 else
                               "unfavorable" if imp <= lg - 2 else "neutral")
    # opponent: trailing allowed vs league average (market-relevant stat)
    oa, olg = r["_opp_allowed"], r["_opp_lg_avg"]
    if np.isnan(oa) or np.isnan(olg) or olg == 0:
        why["opponent_adjustment"] = "neutral"
    else:
        ratio = oa / olg
        why["opponent_adjustment"] = ("favorable" if ratio > 1.10 else
                                     "tough" if ratio < 0.90 else "neutral")
    return why


def uncertainty_assessment(p25, median, p75, cal, market,
                           opp_exp, trail_opp):
    """High-uncertainty flag + confidence from dev-calibrated range width.

    Rule (documented, fixed): relative width = (p75-p25)/max(median,1).
    uncertainty_flag = relative width above the market's dev 90th percentile
    (the model's own distribution puts this player-week in the widest decile
    of predicted ranges -- the operationalization of the Experiment 001
    big-miss finding). Confidence = High/Medium/Low by the dev 33rd/67th
    percentile cutoffs.
    """
    rw = (p75 - p25) / max(median, 1.0)
    c = cal[market]
    flag = bool(rw > c["p90"])
    conf = ("High" if rw <= c["p33"]
            else "Medium" if rw <= c["p67"] else "Low")
    note = None
    if flag:
        # primary uncertainty driver: role vs efficiency (heuristic, fixed)
        driver = ("player opportunity"
                  if trail_opp > 0 and opp_exp < 0.85 * trail_opp
                  else "production efficiency")
        note = (f"Wide predictive range (rel. width {rw:.2f} vs dev p90 "
                f"{c['p90']:.2f}). Primary uncertainty: {driver}.")
    return flag, conf, note, float(rw)


# ------------------------------------------------------- market join
def load_market_lines(path):
    """New market-line schema: player, market, line, source, captured_at.

    captured_at is the ISO timestamp of when the line was captured (recorded
    by the Friday researcher). Older files without source/captured_at are
    tolerated (source='unknown', captured_at=null) but all new captures must
    record them -- this fixes the historical timestamp gap going forward.
    """
    with open(path) as f:
        lines = json.load(f)
    for ln in lines:
        ln.setdefault("source", "unknown")
        ln.setdefault("captured_at", None)
        if ln["market"] not in MARKETS:
            raise SystemExit(f"unknown market in {path}: {ln['market']}")
    return lines


# ------------------------------------------------------- weekly run
def weekly_run(season, week, market_json=None, pred_ts_override=None):
    global DATA, MODEL_PATH, META_PATH
    if _DATA_DIR_OVERRIDE:
        DATA = _DATA_DIR_OVERRIDE
        MODEL_PATH = os.path.join(DATA, "prod_player_models_v2.pkl")
        META_PATH = os.path.join(DATA, "prod_player_models_v2_meta.json")
    if not os.path.exists(MODEL_PATH):
        raise SystemExit(f"fitted models not found at {MODEL_PATH}; "
                         f"run --fit first.")
    with open(MODEL_PATH, "rb") as f:
        models = pickle.load(f)
    with open(META_PATH) as f:
        cal = json.load(f)["uncertainty_calibration"]["per_market"]

    wf, pred_ts = build_week_frame(season, week,
                                     pred_ts_override=pred_ts_override)

    market_map = {}
    if market_json:
        index = P10.build_name_index(
            pd.read_parquet(os.path.join(DATA, "player_games.parquet")))
        for ln in load_market_lines(market_json):
            nv, note = P10.match_player(ln["player"], index)
            if nv is None:
                print(f"  market line unmatched, skipped: {ln['player']} "
                      f"({note})", flush=True)
                continue
            market_map.setdefault(nv, {})[ln["market"]] = ln
        print(f"market lines loaded: {sum(len(v) for v in market_map.values())} "
              f"matched", flush=True)

    out = []
    for _, r in wf.iterrows():
        market = r["market"]
        M = models[market]
        df1 = wf.iloc[[r.name]]

        base = float(X.baseline_pred(df1, market)[0])
        pA, oA, eA = prod_pred_A(M["A"], df1)
        pA, oA, eA = float(pA[0]), float(oA[0]), float(eA[0])
        pB = float(X.pred_B(M["B"], df1)[0])
        q25 = float(X.pred_C(M["C"], df1, 0.25)[0])
        q50 = float(X.pred_C(M["C"], df1, 0.5)[0])
        q75 = float(X.pred_C(M["C"], df1, 0.75)[0])
        # enforce quantile monotonicity (rare crossings)
        q25, q50, q75 = sorted([q25, q50, q75])
        proj = (pA + pB + q50) / 3.0  # Model D = equal-weight A/B/C

        flag, conf, note, rw = uncertainty_assessment(
            q25, q50, q75, cal, market, oA, r["_trail_opp_ewma"])

        mkt = None
        ln = market_map.get(r["player_name"], {}).get(market)
        if ln is not None:
            diff = proj - float(ln["line"])
            mkt = {"line": float(ln["line"]), "source": ln["source"],
                   "captured_at": ln["captured_at"],
                   "difference": round(diff, 1),
                   "lean": "over" if diff > 0 else "under"}

        out.append({
            "player": r["player_name"],
            "team": r["team"],
            "opp": r["opponent"],
            "market": market,
            "projection": round(proj, 1),
            "median": round(q50, 1),
            "p25": round(q25, 1),
            "p75": round(q75, 1),
            "confidence": conf,
            "why": why_block(r, oA, eA),
            "baseline_ewma": round(base, 1),
            "uncertainty_flag": flag,
            "uncertainty_note": note,
            "market_line": mkt,
            "prediction_timestamp": r["prediction_timestamp"],
            "trailing_games": int(r["trail_games"]),
        })

    obj = {
        "model": MODEL_LABEL,
        "season": season,
        "week": week,
        "prediction_timestamp": pred_ts.isoformat(),
        "generated_at": datetime.now(CHI).isoformat(),
        "disclaimer": DISCLAIMER,
        "experiment_provenance": {
            "experiment": "Player Projection Experiment 001",
            "preregistration": "experiments/player_props_projection/"
                               "PREREGISTRATION.md (approved+re-frozen "
                               "2026-09-30)",
            "results": "experiments/player_props_projection/RESULTS.md "
                       "(preregistered bar NOT cleared; pass-market gains "
                       "real; A~=B; rush/receiving near-nulls)",
            "models": "Baseline=EWMA; D=equal-weight(A,B,C); C ranges; "
                      "A why-decomposition. Fit on train 2018-2020, selected "
                      "on dev 2021-2022. Test slice never touched. "
                      "PFT/news OFF.",
        },
        "markets": MARKETS,
        "n_projections": len(out),
        "projections": sorted(out, key=lambda d: (d["market"], d["player"])),
    }
    opath = os.path.join(DATA, f"prop_v2_{season}_w{week}.json")
    with open(opath, "w") as f:
        json.dump(obj, f, indent=1)
    print(f"wrote {opath} ({len(out)} projections)", flush=True)

    counts = pd.Series([d["market"] for d in out]).value_counts().to_dict()
    n_lean = sum(1 for d in out if d["market_line"] is not None)
    n_flag = sum(1 for d in out if d["uncertainty_flag"])
    print(f"per-market: {counts} | with market line: {n_lean} | "
          f"high-uncertainty flags: {n_flag}", flush=True)
    return opath


# ------------------------------------------------------- schema validation
REQUIRED_TOP = {"model", "season", "week", "prediction_timestamp",
                "generated_at", "disclaimer", "experiment_provenance",
                "markets", "n_projections", "projections"}
REQUIRED_ROW = {"player", "team", "opp", "market", "projection", "median",
                "p25", "p75", "confidence", "why", "baseline_ewma",
                "uncertainty_flag", "uncertainty_note", "market_line",
                "prediction_timestamp", "trailing_games"}
REQUIRED_MKT = {"line", "source", "captured_at", "difference", "lean"}
REQUIRED_WHY = {"expected_opportunities", "opportunity_unit",
                "expected_efficiency", "efficiency_unit", "recent_usage_note",
                "team_environment", "opponent_adjustment"}


def validate_output(obj):
    errs = []
    if not REQUIRED_TOP <= set(obj):
        errs.append(f"top-level missing: {REQUIRED_TOP - set(obj)}")
    if obj.get("n_projections") != len(obj.get("projections", [])):
        errs.append("n_projections != len(projections)")
    for i, d in enumerate(obj.get("projections", [])):
        if not REQUIRED_ROW <= set(d):
            errs.append(f"row {i} missing: {REQUIRED_ROW - set(d)}")
            continue
        if d["market"] not in MARKETS:
            errs.append(f"row {i} bad market: {d['market']}")
        if not REQUIRED_WHY <= set(d["why"]):
            errs.append(f"row {i} why missing: "
                        f"{REQUIRED_WHY - set(d['why'])}")
        ml = d["market_line"]
        if ml is not None and not REQUIRED_MKT <= set(ml):
            errs.append(f"row {i} market_line missing: "
                        f"{REQUIRED_MKT - set(ml)}")
        if d["confidence"] not in ("High", "Medium", "Low"):
            errs.append(f"row {i} bad confidence: {d['confidence']}")
        if not (d["p25"] <= d["median"] <= d["p75"]):
            errs.append(f"row {i} quantiles not monotone")
        if ml is not None and ml["lean"] not in ("over", "under"):
            errs.append(f"row {i} bad lean")
    if errs:
        raise SystemExit("SCHEMA VALIDATION FAILED:\n" + "\n".join(errs[:20]))
    print(f"schema validation OK ({len(obj['projections'])} rows)", flush=True)


# ------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(
        description="Player Projection v2 -- Experimental Production")
    ap.add_argument("--fit", action="store_true",
                    help="reproduce the frozen Experiment 001 fit on "
                         "train/dev, verify vs RESULTS.md, persist models")
    ap.add_argument("--refresh", action="store_true",
                    help="keyless nflverse refresh for the weekly run")
    ap.add_argument("--season", type=int, help="season for the weekly run")
    ap.add_argument("--week", type=int, help="week for the weekly run")
    ap.add_argument("--market-json", default=None,
                    help="market lines JSON (new schema: player, market, "
                         "line, source, captured_at)")
    ap.add_argument("--data-dir", default=None,
                    help="AS-OF RECONSTRUCTION: override the data directory "
                         "(read truncated as-of caches; write outputs there)")
    ap.add_argument("--prediction-timestamp", default=None,
                    help="AS-OF RECONSTRUCTION: ISO timestamp overriding the "
                         "Sunday-anchored Friday 18:00 CT computation")
    ap.add_argument("--skip-validation", action="store_true")
    args = ap.parse_args()

    global _DATA_DIR_OVERRIDE
    _DATA_DIR_OVERRIDE = args.data_dir

    if args.fit:
        do_fit()
        return
    if args.refresh:
        season = args.season or 2026
        refresh_data(season)
        return
    if args.season and args.week:
        opath = weekly_run(args.season, args.week, args.market_json,
                           pred_ts_override=args.prediction_timestamp)
        if not args.skip_validation:
            with open(opath) as f:
                validate_output(json.load(f))
        return
    ap.print_help()
    raise SystemExit(1)


if __name__ == "__main__":
    main()
