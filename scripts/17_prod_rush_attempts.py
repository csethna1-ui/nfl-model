#!/usr/bin/env python3
"""003B rush-attempts head -- experimental production (additive).

Integrates the FROZEN Props Experiment 003B M2 rung as a NEW additive target
head in the props projection pipeline. The frozen fitted ensemble
models/M2_fitted.pkl is deployed DIRECTLY -- nothing here fits, selects, or
tunes anything. Existing passing/rushing/receiving-yards heads
(scripts/16_prod_player_projection.py) are untouched.

Frozen protocol:
  experiments/props_experiment_003_market_expansion/003B_rush_attempts/
    PREREGISTRATION.md (approved+frozen by Cale 2026-10-01 12:25 CDT)
    RESULTS.md (production gate, section 8)
    REPRODUCIBILITY.md
    scripts/build_003b_features.py  (trailing-window logic reproduced below)
    scripts/run_experiment_003b.py  (D-ensemble predict math reproduced below)

Research verdict (003B, locked 2023-2024 test, single evaluation): M2
(opportunity + trailing NGS rushing family) reduced carry-projection MAE by
29.76% pooled vs the frozen trailing-EWMA baseline. That establishes
projection quality only. This head is a research projection stream:
paper tracking, no betting-edge claim anywhere in this file or its outputs,
no V1 spread-model impact (separate system).

What runs each week (Friday, after the spread pipeline -- never blocking V1):
  1. --refresh : keyless pulls -- full 2026 pbp slim (for neutral rush rate
     and team-game pace, which need qtr/score_differential) and NGS rushing
     2024-2026 (for the trailing NGS family). Cached locally; never touches
     experiment files.
  2. --season 2026 --week N [--market-json ...] : build the 13 frozen M2
     features for eligible RBs in the week's games (Friday 18:00
     America/Chicago cutoff), predict with the frozen M2 D-ensemble, join
     rush-attempt market lines (projection -> line -> lean), write
     data/prop_v2_{season}_w{week}_rush_attempts.json.

Production gate behavior (RESULTS.md section 8), implemented verbatim:
  - As-of: Friday 18:00 CT. NGS trailing requires the prior week's NGS
    release; if the release is late, fall back to the previous trailing
    vector and set the stale flag.
  - Missing NGS feature -> 0 (research convention); full NGS pull failure
    degrades to the M1 rung (frozen M1_fitted.pkl) -- NEVER silently to M0.
  - week==0 season-total aggregate rows are excluded on every build
    (mandatory hygiene rule).

Usage:
  ./venv/bin/python scripts/17_prod_rush_attempts.py --refresh
  ./venv/bin/python scripts/17_prod_rush_attempts.py --season 2026 --week 4 \
      --market-json data/market_props_2026_w4.json
"""
import argparse
import importlib.util
import json
import os
import pickle
import re
import shutil
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = os.path.expanduser("~/workspace/nfl-model")
DATA = os.path.join(REPO, "data")
EXP3B = os.path.join(REPO, "experiments/props_experiment_003_market_expansion",
                     "003B_rush_attempts")
M2_PATH = os.path.join(EXP3B, "models/M2_fitted.pkl")
M1_PATH = os.path.join(EXP3B, "models/M1_fitted.pkl")

CHI = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")

HALF_LIFE = 3.0
MAX_TRAIL = 16
MIN_GAMES = 3
MIN_TRAIL_ATT_SUM = 5   # eligible_hist role analog: ELIGIBLE["rush_yards"]
MIN_TRAIL_ATT_EWMA = 5  # 003B clean-role cut (RESULTS.md population)

MODEL_VERSION_M2 = "003B-M2-frozen"
MODEL_VERSION_M1 = "003B-M1-degraded"

MARKET_KEY = "rush_attempts"
OPP_UNIT = "carries"

STATUS_EXPERIMENTAL = "experimental"
DISPLAY_NOTE = ("Experimental \u2014 NGS-enhanced projection. "
                "Research projection only. No verified betting edge "
                "established.")
DISCLAIMER = ("Experimental NFL analytics / paper-tracking system. The 003B "
              "rush-attempts head productionizes the frozen Experiment 003B "
              "M2 ensemble evaluated once on the locked 2023-2024 test "
              "(projection quality only). No verified betting edge. Not "
              "betting advice; no real-money recommendations.")

NGS_COLS = ["efficiency", "expected_rush_yards", "rush_yards_over_expected",
            "rush_pct_over_expected", "percent_attempts_gte_eight_defenders",
            "avg_time_to_los"]
NGS_OUT = {"efficiency": "ngs_eff",
           "expected_rush_yards": "ngs_xrush",
           "rush_yards_over_expected": "ngs_ryoe",
           "rush_pct_over_expected": "ngs_ryoe_pct",
           "percent_attempts_gte_eight_defenders": "ngs_8box",
           "avg_time_to_los": "ngs_ttl"}
M1_FEATS = ["pace_team_plays", "trail_rush_share_ewma", "opp2_snap_pct",
            "neut_rush_rate", "ctx_elo_adv", "trail_rz_carries_ewma",
            "trail_games"]

PBP_FULL_WANT = ["game_id", "season", "week", "season_type", "posteam",
                 "defteam", "play_type", "rusher_player_name", "yardline_100",
                 "qtr", "score_differential"]


def _load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


print("loading name-index module...", flush=True)
P10 = _load_mod("prop10", os.path.join(REPO, "scripts/10_prop_projector.py"))


def ewma(v, hl=HALF_LIFE):
    """Trailing EWMA, half-life 3, most-recent-first, max 16 games.
    (Identical to the experiment's build_003b_features.py.)"""
    v = np.asarray(v, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return np.nan
    w = 0.5 ** (np.arange(len(v)) / hl)
    return float(np.sum(w * v) / np.sum(w))


def ukey(name):
    """Name key used for the NGS join. (Verbatim from 003B build script.)"""
    s = str(name).lower().strip()
    s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)\.?$", "", s)
    s = re.sub(r"\.", " ", s)
    toks = [t for t in s.split() if t]
    if len(toks) < 2:
        return None
    return f"{toks[0][0]}.{toks[-1]}"


def friday_timestamp(kickoffs):
    """Friday 18:00 America/Chicago of game week. (Same rule as 16.)"""
    dates = sorted({k.date() for k in kickoffs})
    sundays = [d for d in dates if d.weekday() == 6]
    anchor = sundays[0] if sundays else min(dates)
    if anchor.weekday() == 6:
        friday = anchor - timedelta(days=2)
    else:
        friday = anchor - timedelta(days=(anchor.weekday() - 4) % 7)
    return datetime(friday.year, friday.month, friday.day, 18, 0, tzinfo=CHI)


# ------------------------------------------------------------------ refresh
def refresh_data(season=2026):
    """Keyless refresh for the 003B head. Idempotent; never touches
    experiment files.

    - full pbp for `season` (slim to PBP_FULL_WANT): neutral rush rate and
      team pace need qtr/score_differential, which the 16 rich pull omits.
    - NGS rushing for season-2..season: trailing family source.
    """
    import nfl_data_py as nfl

    print(f"--- 003B refresh: full pbp {season} (slim) ---", flush=True)
    out = os.path.join(DATA, f"prod_pbp_full_{season}.parquet")
    if os.path.exists(out):
        print(f"  cached, skipping (delete {out} to force re-pull)",
              flush=True)
    else:
        df = nfl.import_pbp_data([season])
        cols = [c for c in PBP_FULL_WANT if c in df.columns]
        missing = set(PBP_FULL_WANT) - set(df.columns)
        if missing:
            print(f"  WARNING missing cols: {missing}", flush=True)
        df = df[df["season_type"] == "REG"][cols].copy()
        df.to_parquet(out, index=False)
        print(f"  saved {out} ({len(df)} REG rows)", flush=True)
        del df

    print("--- 003B refresh: NGS rushing ---", flush=True)
    pull_ngs(season, force=True)
    print("refresh complete.", flush=True)


NGS_CACHE = os.path.join(DATA, "prod_ngs_rushing.parquet")
NGS_CACHE_PREV = os.path.join(DATA, "prod_ngs_rushing_prev.parquet")


def pull_ngs(season, force=False):
    """Keyless NGS rushing pull (seasons season-2..season), cached locally.

    Applies the mandatory hygiene rule: week==0 season-total aggregate rows
    are excluded on every build. Returns the frame and a pull timestamp.
    """
    import nfl_data_py as nfl

    if not force and os.path.exists(NGS_CACHE):
        ngs = pd.read_parquet(NGS_CACHE)
        print(f"  NGS: cached ({len(ngs)} rows)", flush=True)
        return ngs, None
    seasons = [season - 2, season - 1, season]
    df = nfl.import_ngs_data("rushing", seasons)
    df = df[df["season_type"] == "REG"].copy()
    n_w0 = int((df["week"] <= 0).sum())
    df = df[df["week"] > 0].copy()
    print(f"  NGS: excluded {n_w0} week<=0 season-aggregate rows", flush=True)
    missing = [c for c in NGS_COLS if c not in df.columns]
    if missing:
        raise SystemExit(f"NGS feed missing preregistered columns: {missing}")
    df["nplayer"] = df["player_display_name"].map(ukey)
    df = df.dropna(subset=["nplayer"])
    df = (df.sort_values("week")
          .drop_duplicates(["nplayer", "season", "week"], keep="last"))
    pulled_at = datetime.now(CHI).isoformat()
    if os.path.exists(NGS_CACHE):
        shutil.copy2(NGS_CACHE, NGS_CACHE_PREV)
    df.to_parquet(NGS_CACHE, index=False)
    print(f"  NGS: saved {NGS_CACHE} ({len(df)} rows, pulled {pulled_at})",
          flush=True)
    return df, pulled_at


def ngs_source(season, week):
    """Resolve the NGS trailing source honoring the as-of rule.

    The prior week's NGS release must be present before the Friday 18:00 CT
    cutoff. If the fresh pull is late (missing the required release week),
    fall back to the previous trailing vector and set the stale flag.
    A full pull failure degrades to the M1 rung (never silently to M0).

    Returns (ngs_frame, ngs_data_as_of, stale_ngs, rung) where rung is
    "M2" normally or "M1" on full-pull degradation.
    """
    req = (season, week - 1) if week > 1 else (season - 1, None)

    def covers(frame):
        f = frame[frame["season"] == req[0]]
        if req[1] is None:
            return len(f) > 0
        return bool((f["week"] >= req[1]).any())

    try:
        fresh, pulled_at = pull_ngs(season, force=True)
    except Exception as e:  # noqa: BLE001 -- failure path is specified
        print(f"  NGS pull FAILED ({str(e)[:120]}): degrading to M1 rung",
              flush=True)
        if not os.path.exists(NGS_CACHE):
            raise SystemExit("NGS pull failed and no cached NGS exists; "
                             "cannot build the head.")
        cached = pd.read_parquet(NGS_CACHE)
        as_of = {"pulled_at": "cache",
                 "latest_season_week": _ngs_latest(cached),
                 "required_release": [int(req[0]), req[1]],
                 "note": "NGS pull failed; degraded to M1 rung per RESULTS.md "
                         "production gate 8(f)."}
        return cached, as_of, False, "M1"

    if covers(fresh):
        as_of = {"pulled_at": pulled_at,
                 "latest_season_week": _ngs_latest(fresh),
                 "required_release": [int(req[0]), req[1]],
                 "note": "prior-week NGS release present before cutoff."}
        return fresh, as_of, False, "M2"

    # Late release: fall back to the previous trailing vector, flag it.
    print("  NGS release late (required release week missing): falling back "
          "to the previous trailing vector, stale flag set", flush=True)
    if not os.path.exists(NGS_CACHE_PREV):
        raise SystemExit("NGS release late and no previous pull cached; "
                         "refusing to fabricate trailing data.")
    prev = pd.read_parquet(NGS_CACHE_PREV)
    as_of = {"pulled_at": "previous-cache",
             "latest_season_week": _ngs_latest(prev),
             "required_release": [int(req[0]), req[1]],
             "note": "NGS release late; previous trailing vector used."}
    return prev, as_of, True, "M2"


def _ngs_latest(frame):
    s = int(frame["season"].max())
    w = int(frame.loc[frame["season"] == s, "week"].max())
    return [s, w]


# ------------------------------------------------------- feature build
def _team_game_tables(pbp_full):
    """Team-game pace tables from full REG pbp (002 section recipe).

    plays: all play types (002 Family E pace_team_plays source).
    neut_pr: pass rate on neutral plays (qtr 1-3, |score diff| <= 10).
    team_rush_att: (play_type == 'run') count on the pass/run subset
        (001 rush_share denominator).
    """
    r = pbp_full[pbp_full["season_type"] == "REG"].copy()
    tg = r.groupby(["posteam", "season", "week"], dropna=False)
    team_g = tg.agg(plays=("play_type", "size")).reset_index().rename(
        columns={"posteam": "team"})
    neut = r[r["qtr"].isin([1, 2, 3]) &
             (r["score_differential"].abs() <= 10)]
    ng = neut.groupby(["posteam", "season", "week"], dropna=False)
    neut_g = ng.agg(nplays=("play_type", "size"),
                    npass=("play_type", lambda s: (s == "pass").sum())
                    ).reset_index().rename(columns={"posteam": "team"})
    neut_g["neut_pr"] = (neut_g["npass"] /
                         neut_g["nplays"].replace(0, np.nan))
    team_g = team_g.merge(neut_g[["team", "season", "week", "neut_pr"]],
                          on=["team", "season", "week"], how="left")

    pr = r[r["play_type"].isin(["pass", "run"])].copy()
    tg2 = pr.groupby(["posteam", "season", "week"], dropna=False)
    rush_g = tg2.agg(
        team_rush_att=("play_type",
                       lambda s: (s == "run").sum())).reset_index().rename(
        columns={"posteam": "team"})
    team_g = team_g.merge(rush_g, on=["team", "season", "week"], how="left")

    # red-zone carries per player-game (001 rz_carries recipe)
    pr["is_rz"] = pr["yardline_100"] <= 20
    rush = pr[pr["rusher_player_name"].notna()].copy()
    g = rush.groupby(["rusher_player_name", "posteam", "season", "week"],
                     dropna=False)
    rz = g.agg(rz_carries=("is_rz", "sum")).reset_index().rename(
        columns={"rusher_player_name": "player_name", "posteam": "team"})
    return team_g, rz


def build_features(season, week):
    """Build the 13 frozen M2 feature rows for the week's eligible RBs.

    Trailing-window logic reproduces the experiment exactly: strictly-prior
    weeks, EWMA half-life 3, max 16 games, most-recent-first; week==0 NGS
    aggregate rows excluded; NaN -> 0 (research convention).
    """
    # ---- schedules: kickoff, prediction timestamp, upcoming games ----
    sched = pd.read_parquet(os.path.join(DATA, "schedules_2018_2025.parquet"))
    sched = sched[(sched["game_type"] == "REG") &
                  (sched["season"] == season) & (sched["week"] == week)].copy()
    if sched.empty:
        raise SystemExit(f"no REG games found for {season} week {week}")
    sched["kickoff"] = (pd.to_datetime(sched["gameday"].astype(str) + " " +
                                       sched["gametime"].astype(str))
                        .dt.tz_localize(ET))
    pred_ts = friday_timestamp(sched["kickoff"])
    print(f"prediction timestamp: {pred_ts.isoformat()}", flush=True)
    wk = sched[sched["kickoff"] > pred_ts.astimezone(ET)].copy()
    n_excl = len(sched) - len(wk)
    if n_excl:
        print(f"excluded {n_excl} game(s) kicking off at/before the "
              f"timestamp", flush=True)
    game_of = {}
    for _, g in wk.iterrows():
        game_of[g["home_team"]] = g
        game_of[g["away_team"]] = g

    # ---- pre-week ELO (walk-forward; same semantics as 002 ctx_elo_adv) ----
    rt_path = os.path.join(DATA, f"ratings_current_{season}_w{week}.parquet")
    if not os.path.exists(rt_path):
        raise SystemExit(
            f"pre-week ELO file missing: {rt_path}. Refusing to substitute a "
            f"stale rating file (as-of discipline).")
    elo = dict(pd.read_parquet(rt_path)[["team", "elo"]].itertuples(
        index=False, name=None))

    # ---- player spine: current-season RBs on playing teams ----
    pg = pd.read_parquet(os.path.join(DATA, "player_games.parquet"))
    pg = pg[pg["season"] <= season].copy()
    pg_recent = pg.sort_values(["player_name", "season", "week"])
    eligible_players = set()
    player_team, player_pos = {}, {}
    for p, g in pg_recent.groupby("player_name"):
        if g.iloc[-1]["season"] != season:
            continue  # retired/inactive: no game in the current season
        eligible_players.add(p)
        player_team[p] = g.iloc[-1]["team"]
        gs = g[g["season"] == season]
        player_pos[p] = gs.iloc[-1]["position"]

    # ---- team-game pace tables (full pbp 2018..season, slimmed) ----
    pbp_parts = [pd.read_parquet(os.path.join(DATA, f"pbp_{s}.parquet"),
                                  columns=PBP_FULL_WANT)
                 for s in range(2018, season)]
    pfull = os.path.join(DATA, f"prod_pbp_full_{season}.parquet")
    if not os.path.exists(pfull):
        raise SystemExit(f"full {season} pbp missing at {pfull}; "
                         f"run --refresh first.")
    pbp_parts.append(pd.read_parquet(pfull))
    pbp_full = pd.concat(pbp_parts, ignore_index=True)
    team_g, rz = _team_game_tables(pbp_full)
    print(f"team-game tables: {len(team_g)} team-games, "
          f"{len(rz)} player-game rz rows", flush=True)

    team_g = team_g.sort_values(["team", "season", "week"]).reset_index(
        drop=True)
    team_hist = {t: g.reset_index(drop=True)
                 for t, g in team_g.groupby("team")}

    def team_trail(team, col):
        g = team_hist.get(team)
        if g is None:
            return np.nan
        m = (g["season"] < season) | ((g["season"] == season) &
                                      (g["week"] < week))
        hist = g[m].iloc[::-1].head(MAX_TRAIL)
        return ewma(hist[col].to_numpy()) if len(hist) else np.nan

    # ---- player-game base: rush share + rz carries + team denominator ----
    base = pg[["player_name", "team", "season", "week", "rush_att"]].copy()
    share_den = team_g[["team", "season", "week", "team_rush_att"]]
    base = base.merge(share_den, on=["team", "season", "week"], how="left")
    base["rush_share"] = (base["rush_att"] /
                          base["team_rush_att"].replace(0, np.nan))
    base = base.merge(rz, on=["player_name", "team", "season", "week"],
                      how="left")
    base["rz_carries"] = base["rz_carries"].fillna(0)
    base = base.sort_values(["player_name", "season", "week"])

    # ---- snap counts -> opp2_snap_pct (002 Family F recipe) ----
    sn_parts = []
    for s in range(2018, season + 1):
        p = os.path.join(DATA, "v2", "raw", f"snap_counts_{s}.csv")
        if os.path.exists(p):
            sn_parts.append(pd.read_csv(p))
    sn = pd.concat(sn_parts, ignore_index=True)
    sn = sn[sn["game_type"] == "REG"].copy()
    sn["sukey"] = sn["player"].map(ukey) + "|" + sn["team"]
    sn = (sn.sort_values("offense_pct")
          .drop_duplicates(["sukey", "season", "week"], keep="last"))
    snp = sn[["sukey", "team", "season", "week", "offense_pct"]].copy()
    base["pukey"] = base["player_name"].map(ukey) + "|" + base["team"]
    base = base.merge(snp.rename(columns={"sukey": "pukey"}),
                      on=["pukey", "team", "season", "week"], how="left")
    print(f"snap merge rate on base: "
          f"{base['offense_pct'].notna().mean():.4f}", flush=True)

    # ---- NGS trailing source (as-of rule; may degrade to M1) ----
    ngs, ngs_as_of, stale_ngs, rung = ngs_source(season, week)
    print(f"NGS rung: {rung} | stale_ngs={stale_ngs} | "
          f"as_of={ngs_as_of}", flush=True)
    ngs = ngs.sort_values(["nplayer", "season", "week"]).reset_index(drop=True)
    ngs_trail = {}
    for pl, g in ngs.groupby("nplayer", sort=False):
        g = g.reset_index(drop=True)
        sw = list(zip(g["season"].astype(int), g["week"].astype(int)))
        vecs = {}
        for i in range(len(g)):
            if (g.loc[i, "season"], g.loc[i, "week"]) >= (season, week):
                continue  # strictly prior weeks only
            hist = g.iloc[max(0, i - MAX_TRAIL):i].iloc[::-1]
            vecs[(int(g.loc[i, "season"]), int(g.loc[i, "week"]))] = {
                NGS_OUT[c]: (ewma(hist[c].to_numpy()) if len(hist) else np.nan)
                for c in NGS_COLS}
            vecs[(int(g.loc[i, "season"]), int(g.loc[i, "week"]))][
                "ngs_trail_weeks"] = len(hist)
        ngs_trail[pl] = (sw, vecs)

    rows = []
    for p, g in base.groupby("player_name"):
        if p not in eligible_players:
            continue
        if player_pos.get(p) != "RB":
            continue  # 003B population: RB (market == rush_yards)
        team = player_team.get(p)
        if team not in game_of:
            continue  # team not playing (or game excluded)
        gm = game_of[team]
        is_home = 1 if team == gm["home_team"] else 0
        opp = gm["away_team"] if is_home else gm["home_team"]

        hist = g[(g["season"] < season) |
                 ((g["season"] == season) & (g["week"] < week))]
        hist = hist.iloc[::-1].head(MAX_TRAIL)  # recent-first
        n = len(hist)
        if n < MIN_GAMES:
            continue
        if float(hist["rush_att"].sum()) < MIN_TRAIL_ATT_SUM:
            continue  # eligible_hist role analog
        trail_att_ewma = ewma(hist["rush_att"].to_numpy())
        if not (trail_att_ewma and trail_att_ewma >= MIN_TRAIL_ATT_EWMA):
            continue  # 003B clean-role cut

        latest = hist.iloc[0]
        latest_game = f"{int(latest['season'])}-W{int(latest['week'])}"

        row = {"player_name": p, "team": team, "opponent": opp,
               "season": season, "week": week, "position": "RB",
               "market": MARKET_KEY, "trail_games": n,
               "prediction_timestamp": pred_ts.isoformat(),
               "latest_game_included": latest_game,
               "pace_team_plays": team_trail(team, "plays"),
               "trail_rush_share_ewma": ewma(hist["rush_share"].to_numpy()),
               "opp2_snap_pct": ewma(hist["offense_pct"].to_numpy()),
               "neut_rush_rate": 1.0 - team_trail(team, "neut_pr"),
               "ctx_elo_adv": (elo.get(team, np.nan) -
                               elo.get(opp, np.nan)),
               "trail_rz_carries_ewma": ewma(hist["rz_carries"].to_numpy())}
        for c in NGS_COLS:
            row[NGS_OUT[c]] = np.nan
        row["_ngs_trail_weeks"] = 0
        nk = ukey(p)
        if nk in ngs_trail:
            sw, vecs = ngs_trail[nk]
            # trailing vector for the week strictly before (season, week):
            # the latest NGS release week in the feed
            cand = [(s, w) for (s, w) in vecs if (s, w) < (season, week)]
            if cand:
                key = max(cand)
                v = vecs[key]
                for c in NGS_COLS:
                    row[NGS_OUT[c]] = v[NGS_OUT[c]]
                row["_ngs_trail_weeks"] = v["ngs_trail_weeks"]
        rows.append(row)

    wf = pd.DataFrame(rows)
    if wf.empty:
        raise SystemExit("no eligible RB player-weeks built -- check caches")
    # Missing feature -> 0 (research convention; matches the experiment's
    # NaN->0 table fill, which is what the frozen models were fit on).
    feat_all = M1_FEATS + list(NGS_OUT.values())
    wf[feat_all] = wf[feat_all].fillna(0)
    print(f"003B week frame: {len(wf)} eligible RB player-weeks; "
          f"median ngs trail weeks: "
          f"{wf['_ngs_trail_weeks'].median():.1f}", flush=True)
    return wf, pred_ts, ngs_as_of, stale_ngs, rung


# ------------------------------------------------------- prediction
def load_frozen(rung):
    path = M2_PATH if rung == "M2" else M1_PATH
    if not os.path.exists(path):
        raise SystemExit(f"frozen model missing: {path}")
    with open(path, "rb") as f:
        return pickle.load(f)


def pred_D(model):
    """D-ensemble point prediction: equal-weight mean of A/B/C, clipped >= 0.
    (Exact math from run_experiment_003b.py test phase.)"""
    def pred_A(m, X):
        s, r, feats = m
        return np.maximum(
            r.predict(s.transform(X[feats].to_numpy(float))), 0.0)

    def pred_B(m, X):
        r, feats = m
        return np.maximum(r.predict(X[feats].to_numpy(float)), 0.0)

    def pred_C(m, X):
        r, feats = m
        return np.maximum(r.predict(X[feats].to_numpy(float)), 0.0)

    def go(X):
        pA, pB, pC = pred_A(model["A"], X), pred_B(model["B"], X), \
            pred_C(model["C"], X)
        return (pA + pB + pC) / 3.0, pA, pB, pC
    return go


# ------------------------------------------------------- market join
def load_market_lines(path):
    """Same new market-line schema as 16: player, market, line, source,
    captured_at. Only MARKET_KEY lines are kept here."""
    with open(path) as f:
        lines = json.load(f)
    kept = []
    for ln in lines:
        if ln.get("market") != MARKET_KEY:
            continue
        ln.setdefault("source", "unknown")
        ln.setdefault("captured_at", None)
        kept.append(ln)
    return kept


# ------------------------------------------------------- weekly run
def weekly_run(season, week, market_json=None):
    wf, pred_ts, ngs_as_of, stale_ngs, rung = build_features(season, week)
    model = load_frozen(rung)
    model_version = MODEL_VERSION_M2 if rung == "M2" else MODEL_VERSION_M1
    feats = model["feats"]
    print(f"frozen model: {model_version} | feats={feats} | "
          f"fitted_on={model.get('fitted_on')}", flush=True)
    if rung == "M2" and feats != M1_FEATS + list(NGS_OUT.values()):
        raise SystemExit("M2 feature list mismatch vs frozen audit -- aborting.")
    if rung == "M1" and feats != M1_FEATS:
        raise SystemExit("M1 feature list mismatch vs frozen audit -- aborting.")

    predict = pred_D(model)
    pD, pA, pB, pC = predict(wf)
    wf = wf.copy()
    wf["_pD"], wf["_pA"], wf["_pB"], wf["_pC"] = pD, pA, pB, pC

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
        proj = float(r["_pD"])
        mkt = None
        ln = market_map.get(r["player_name"], {}).get(MARKET_KEY)
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
            "market": MARKET_KEY,
            "status": STATUS_EXPERIMENTAL,
            "display_note": DISPLAY_NOTE,
            "projection": round(proj, 1),
            "projection_components": {
                "A_ridge": round(float(r["_pA"]), 2),
                "B_gbm": round(float(r["_pB"]), 2),
                "C_quantile_median": round(float(r["_pC"]), 2),
                "D": "equal-weight mean of A/B/C, clipped >= 0",
            },
            # 003B has no calibrated uncertainty interval; the terminology
            # contract (High/Medium/Low Uncertainty, never "Confidence") is
            # honored with an explicit uncalibrated placeholder.
            "uncertainty": "Medium Uncertainty",
            "uncertainty_note": ("003B M2 ships a point projection only; no "
                                 "uncertainty interval was calibrated for "
                                 "this head. Label is a placeholder, not a "
                                 "calibrated assessment."),
            "market_line": mkt,
            "prediction_timestamp": r["prediction_timestamp"],
            "ngs_data_as_of": ngs_as_of,
            "latest_game_included": r["latest_game_included"],
            "feature_window": ("trailing 16 games max, EWMA half-life 3.0, "
                               "most-recent-first, strictly prior weeks; "
                               "week==0 NGS aggregate rows excluded"),
            "model_version": model_version,
            "stale_ngs_used": bool(stale_ngs),
            "fallback_to_M1": bool(rung == "M1"),
            "trailing_games": int(r["trail_games"]),
            "ngs_trail_weeks": int(r["_ngs_trail_weeks"]),
        })

    obj = {
        "model": "Props Experiment 003B \u2014 rush attempts "
                 "(experimental head)",
        "status": STATUS_EXPERIMENTAL,
        "display_note": DISPLAY_NOTE,
        "season": season,
        "week": week,
        "prediction_timestamp": pred_ts.isoformat(),
        "generated_at": datetime.now(CHI).isoformat(),
        "disclaimer": DISCLAIMER,
        "experiment_provenance": {
            "experiment": "Props Experiment 003B: Rush Attempts",
            "preregistration": "experiments/props_experiment_003_market_"
                               "expansion/003B_rush_attempts/"
                               "PREREGISTRATION.md (approved+frozen "
                               "2026-10-01 12:25 CDT)",
            "results": "experiments/props_experiment_003_market_expansion/"
                       "003B_rush_attempts/RESULTS.md (M2 MATERIAL WIN on "
                       "locked 2023-2024 test; projection quality only, no "
                       "market evaluation; paper tracking only)",
            "model_artifact": ("experiments/props_experiment_003_market_"
                               "expansion/003B_rush_attempts/models/"
                               "M2_fitted.pkl deployed directly, no "
                               "retraining"),
            "features": "13 frozen M2 features: 7 M1 opportunity "
                        "(pace_team_plays, trail_rush_share_ewma, "
                        "opp2_snap_pct, neut_rush_rate, ctx_elo_adv, "
                        "trail_rz_carries_ewma, trail_games) + 6 trailing "
                        "NGS rushing (ngs_eff, ngs_xrush, ngs_ryoe, "
                        "ngs_ryoe_pct, ngs_8box, ngs_ttl)",
            "as_of": "Friday 18:00 America/Chicago; strictly-prior-week "
                     "trailing; pre-week ELO",
        },
        "market": MARKET_KEY,
        "n_projections": len(out),
        "projections": sorted(out, key=lambda d: d["player"]),
    }
    opath = os.path.join(DATA, f"prop_v2_{season}_w{week}_rush_attempts.json")
    with open(opath, "w") as f:
        json.dump(obj, f, indent=1)
    print(f"wrote {opath} ({len(out)} projections)", flush=True)
    n_lean = sum(1 for d in out if d["market_line"] is not None)
    print(f"with market line: {n_lean} | stale_ngs: {stale_ngs} | "
          f"fallback_to_M1: {rung == 'M1'}", flush=True)
    return opath


# ------------------------------------------------------- schema validation
REQUIRED_TOP = {"model", "status", "display_note", "season", "week",
                "prediction_timestamp", "generated_at", "disclaimer",
                "experiment_provenance", "market", "n_projections",
                "projections"}
REQUIRED_ROW = {"player", "team", "opp", "market", "status", "display_note",
                "projection", "projection_components", "uncertainty",
                "uncertainty_note", "market_line", "prediction_timestamp",
                "ngs_data_as_of", "latest_game_included", "feature_window",
                "model_version", "stale_ngs_used", "fallback_to_M1",
                "trailing_games", "ngs_trail_weeks"}
REQUIRED_MKT = {"line", "source", "captured_at", "difference", "lean"}
REQUIRED_NGS_ASOF = {"pulled_at", "latest_season_week", "required_release",
                     "note"}


def validate_output(obj):
    errs = []
    if not REQUIRED_TOP <= set(obj):
        errs.append(f"top-level missing: {REQUIRED_TOP - set(obj)}")
    if obj.get("status") != STATUS_EXPERIMENTAL:
        errs.append("top-level status is not 'experimental'")
    if obj.get("display_note") != DISPLAY_NOTE:
        errs.append("display_note does not match the required text exactly")
    if obj.get("n_projections") != len(obj.get("projections", [])):
        errs.append("n_projections != len(projections)")
    for i, d in enumerate(obj.get("projections", [])):
        if not REQUIRED_ROW <= set(d):
            errs.append(f"row {i} missing: {REQUIRED_ROW - set(d)}")
            continue
        if d["market"] != MARKET_KEY:
            errs.append(f"row {i} bad market: {d['market']}")
        if d["status"] != STATUS_EXPERIMENTAL:
            errs.append(f"row {i} status not experimental")
        if d["display_note"] != DISPLAY_NOTE:
            errs.append(f"row {i} display_note mismatch")
        if d["uncertainty"] not in ("High Uncertainty", "Medium Uncertainty",
                                    "Low Uncertainty"):
            errs.append(f"row {i} bad uncertainty: {d['uncertainty']}")
        if "Confidence" in d["uncertainty"]:
            errs.append(f"row {i} uses forbidden 'Confidence' terminology")
        if d["model_version"] not in (MODEL_VERSION_M2, MODEL_VERSION_M1):
            errs.append(f"row {i} bad model_version: {d['model_version']}")
        if not REQUIRED_NGS_ASOF <= set(d["ngs_data_as_of"]):
            errs.append(f"row {i} ngs_data_as_of missing: "
                        f"{REQUIRED_NGS_ASOF - set(d['ngs_data_as_of'])}")
        if not d["latest_game_included"]:
            errs.append(f"row {i} missing latest_game_included")
        ml = d["market_line"]
        if ml is not None and not REQUIRED_MKT <= set(ml):
            errs.append(f"row {i} market_line missing: "
                        f"{REQUIRED_MKT - set(ml)}")
        if d["projection"] < 0:
            errs.append(f"row {i} negative projection")
    if errs:
        raise SystemExit("SCHEMA VALIDATION FAILED:\n" + "\n".join(errs[:20]))
    print(f"schema validation OK ({len(obj['projections'])} rows)", flush=True)


# ------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(
        description="003B rush-attempts head -- experimental production")
    ap.add_argument("--refresh", action="store_true",
                    help="keyless refresh: full pbp slim + NGS rushing pulls")
    ap.add_argument("--season", type=int, help="season for the weekly run")
    ap.add_argument("--week", type=int, help="week for the weekly run")
    ap.add_argument("--market-json", default=None,
                    help="market lines JSON (schema: player, market, line, "
                         "source, captured_at)")
    ap.add_argument("--skip-validation", action="store_true")
    args = ap.parse_args()

    if args.refresh:
        refresh_data(args.season or 2026)
        return
    if args.season and args.week:
        opath = weekly_run(args.season, args.week, args.market_json)
        if not args.skip_validation:
            with open(opath) as f:
                validate_output(json.load(f))
        return
    ap.print_help()
    raise SystemExit(1)


if __name__ == "__main__":
    main()
