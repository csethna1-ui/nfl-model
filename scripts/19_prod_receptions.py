#!/usr/bin/env python3
"""003A receptions head -- experimental production (additive).

Integrates the VERIFIED Props Experiment 003A M2 rung as a NEW additive
target head in the props projection pipeline. The verified fitted ensemble
models/M2_verified_deployed.pkl is deployed DIRECTLY -- nothing here fits,
selects, or tunes anything. The deployment reproduces the frozen
experiment_003A_test_predictions.parquet bit-for-bit
(DEPLOYMENT_VERIFICATION.md). Existing passing/rushing/receiving-yards
heads (scripts/16_prod_player_projection.py) are untouched.

Frozen protocol:
  experiments/props_experiment_003_market_expansion/003A_receptions/
    PREREGISTRATION.md (approved+frozen by Cale 2026-10-01 12:25 CDT)
    RESULTS.md (production package, section 5; judgment calls, section 7)
    scripts/run_003A.py      (model math + feature sets, imported verbatim)
    scripts/build_003A_features.py (trailing-window logic reproduced below)

Research verdict (003A, locked 2023-2024 test, single evaluation): M2
(process + trailing NGS receiving family) reduced reception-projection MAE
by 19.51% pooled vs the frozen trailing-EWMA baseline. That establishes
projection quality only. This head is a research projection stream:
paper tracking, no betting-edge claim anywhere in this file or its
outputs, no V1 spread-model impact (separate system).

What runs each week (Friday, after the spread pipeline -- never blocking V1):
  1. --refresh : keyless pulls -- NGS receiving 2024-2026 (trailing family).
     Cached locally; never touches experiment files.
  2. --season 2026 --week N [--market-json ...] : build the 23 frozen M2
     features for eligible WRTE in the week's games (Friday 18:00
     America/Chicago cutoff), predict with the verified M2 D-ensemble, join
     reception market lines (projection -> line -> lean), write
     data/prop_v2_{season}_w{week}_receptions.json.

Production gate behavior (RESULTS.md section 5), implemented verbatim:
  - As-of: Friday 18:00 CT. NGS trailing requires the prior week's NGS
    release; if the release is late, fall back to the previous trailing
    vector and set the stale flag.
  - Missing NGS feature -> 0 (research convention); full NGS pull failure
    degrades to the M1 rung (verified M1 artifact) -- NEVER silently to M0.
  - Frozen proxies only: snap share + NGS air-yard share. NO route
    reconstruction (Cale freeze note 2026-10-01).
  - Name-collision trailing convention: trailing groups by player_name,
    exactly as in 001/002 (RESULTS.md section 7.2).

Usage:
  ./venv/bin/python scripts/19_prod_receptions.py --refresh
  ./venv/bin/python scripts/19_prod_receptions.py --season 2026 --week 4 \
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

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root, location-independent
DATA = os.path.join(REPO, "data")
EXP3A = os.path.join(REPO, "experiments/props_experiment_003_market_expansion",
                     "003A_receptions")
M2_PATH = os.path.join(EXP3A, "models/M2_verified_deployed.pkl")
M1_PATH = os.path.join(EXP3A, "models/M1_verified_deployed.pkl")

CHI = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")

HALF_LIFE = 3.0
MAX_TRAIL = 16
MIN_GAMES = 3

MODEL_VERSION_M2 = "003A-M2-verified"
MODEL_VERSION_M1 = "003A-M1-degraded"

MARKET_KEY = "receptions"

STATUS_EXPERIMENTAL = "experimental"
DISPLAY_NOTE = ("Experimental \u2014 NGS-enhanced projection. "
                "Research projection only. No verified betting edge "
                "established.")
DISCLAIMER = ("Experimental NFL analytics / paper-tracking system. The 003A "
              "receptions head productionizes the verified Experiment 003A "
              "M2 ensemble (bit-for-bit deployment verification in "
              "DEPLOYMENT_VERIFICATION.md; projection quality only). No "
              "verified betting edge. Not betting advice; no real-money "
              "recommendations.")

# Frozen M2 feature sets (run_003A.py rung_features("M2"), verbatim).
S1 = ["trail_targets_ewma", "trail_target_share_ewma",
      "opp2_snap_pct", "opp2_snap_trend",
      "pace_neutral_pass_rate", "pace_team_plays", "pace_combined",
      "oppd_def_pass_epa"]
S2 = ["rq_adot", "rq_yac_per_rec", "rq_drop_pct", "rq_broken_tackles",
      "qb_epa_trail", "qb_cpoe_trail", "qb_adot_trail",
      "qb_pressure_trail", "qb_changed"]
NGS_FEATS = ["ngs_avg_separation_trail", "ngs_avg_cushion_trail",
             "ngs_avg_intended_air_yards_trail",
             "ngs_pct_share_intended_air_yards_trail",
             "ngs_avg_expected_yac_trail",
             "ngs_avg_yac_above_expectation_trail"]
NGS_COLS = ["avg_separation", "avg_cushion", "avg_intended_air_yards",
            "percent_share_of_intended_air_yards", "avg_expected_yac",
            "avg_yac_above_expectation"]

PBP_WANT = ["game_id", "season", "week", "season_type", "posteam", "defteam",
            "play_type", "receiver_player_name", "passer_player_name",
            "air_yards", "yards_after_catch", "complete_pass", "pass_attempt",
            "epa", "cpoe", "qtr", "score_differential", "sack"]


def _load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


print("loading verified model math module...", flush=True)
R3A = _load_mod("run_003A", os.path.join(EXP3A, "scripts/run_003A.py"))


def ewma(v, hl=HALF_LIFE):
    """Trailing EWMA, half-life 3, most-recent-first, max 16 games.
    (Identical to the experiment's build scripts.)"""
    v = np.asarray(v, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return np.nan
    w = 0.5 ** (np.arange(len(v)) / hl)
    return float(np.sum(w * v) / np.sum(w))


def ukey(name):
    """Name key used for the NGS/snap/advstats joins. (Verbatim.)"""
    s = str(name).lower().strip()
    s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)\.?$", "", s)
    s = re.sub(r"\.", " ", s)
    toks = [t for t in s.split() if t]
    if len(toks) < 2:
        return None
    return f"{toks[0][0]}.{toks[-1]}"


def friday_timestamp(kickoffs):
    """Friday 18:00 America/Chicago of game week. (Same rule as 16/17.)"""
    dates = sorted({k.date() for k in kickoffs})
    sundays = [d for d in dates if d.weekday() == 6]
    anchor = sundays[0] if sundays else min(dates)
    if anchor.weekday() == 6:
        friday = anchor - timedelta(days=2)
    else:
        friday = anchor - timedelta(days=(anchor.weekday() - 4) % 7)
    return datetime(friday.year, friday.month, friday.day, 18, 0, tzinfo=CHI)


# ------------------------------------------------------------------ refresh
NGS_CACHE = os.path.join(DATA, "prod_ngs_receiving.parquet")
NGS_CACHE_PREV = os.path.join(DATA, "prod_ngs_receiving_prev.parquet")


def pull_ngs(season, force=False):
    """Keyless NGS receiving pull (seasons season-2..season), cached locally.

    Applies the mandatory hygiene rule: week==0 season-total aggregate rows
    are excluded on every build. Returns the frame and a pull timestamp.
    """
    import nfl_data_py as nfl

    if not force and os.path.exists(NGS_CACHE):
        ngs = pd.read_parquet(NGS_CACHE)
        print(f"  NGS receiving: cached ({len(ngs)} rows)", flush=True)
        return ngs, None
    seasons = [season - 2, season - 1, season]
    df = nfl.import_ngs_data("receiving", seasons)
    df = df[df["season_type"] == "REG"].copy()
    n_w0 = int((df["week"] <= 0).sum())
    df = df[df["week"] > 0].copy()
    print(f"  NGS receiving: excluded {n_w0} week<=0 aggregate rows",
          flush=True)
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
    print(f"  NGS receiving: saved {NGS_CACHE} ({len(df)} rows, "
          f"pulled {pulled_at})", flush=True)
    return df, pulled_at


def _ngs_latest(frame):
    s = int(frame["season"].max())
    w = int(frame.loc[frame["season"] == s, "week"].max())
    return [s, w]


def ngs_source(season, week):
    """Resolve the NGS trailing source honoring the as-of rule.

    The prior week's NGS release must be present before the Friday 18:00 CT
    cutoff. Late release -> previous trailing vector + stale flag. Full
    pull failure -> degrade to the M1 rung (never silently to M0).

    Returns (ngs_frame, ngs_data_as_of, stale_ngs, rung).
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
                 "note": "NGS pull failed; degraded to M1 rung per "
                         "RESULTS.md production gate 5(f)."}
        return cached, as_of, False, "M1"

    if covers(fresh):
        as_of = {"pulled_at": pulled_at,
                 "latest_season_week": _ngs_latest(fresh),
                 "required_release": [int(req[0]), req[1]],
                 "note": "prior-week NGS release present before cutoff."}
        return fresh, as_of, False, "M2"

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


def refresh_data(season=2026):
    """Keyless refresh for the 003A head. Idempotent; never touches
    experiment files. NGS receiving for season-2..season."""
    print("--- 003A refresh: NGS receiving ---", flush=True)
    pull_ngs(season, force=True)
    print("refresh complete.", flush=True)

# ------------------------------------------------------- predictable-game filter
# The experiment's player trailing iterates over BASE rows, which are
# predictable games only: the 001 base joins player-games to schedules on
# game_id with an inner join after filtering to games kicking off AFTER the
# Friday 18:00 CT prediction timestamp of their week. Thursday (and other
# pre-Friday) games are therefore EXCLUDED from the player trailing history
# -- this is the frozen definition, replicated here exactly. (Team pace
# trailing and QB trailing use ALL games; NGS trailing uses all NGS weeks.)
#
# The base rows come from player_games.parquet (nflverse player_stats),
# which INCLUDES 0-target games (a player active but not targeted). Building
# the history from pbp receivers only would drop those games and skew the
# trails. pbp is used only for the receiving splits (receptions, air, yac).
def predictable_game_ids(season_max):
    """Set of game_id for predictable REG games, 2018..season_max.

    A game is predictable iff its kickoff is strictly after the Friday
    18:00 America/Chicago timestamp computed from that week's kickoffs
    (001 build_modeling_table.py week_timestamp logic).
    """
    sched = pd.read_parquet(os.path.join(DATA, "schedules_2018_2025.parquet"))
    sched = sched[(sched["game_type"] == "REG") &
                  (sched["season"] >= 2018) &
                  (sched["season"] <= season_max)].copy()
    sched["kickoff"] = (pd.to_datetime(sched["gameday"].astype(str) + " " +
                                       sched["gametime"].astype(str))
                        .dt.tz_localize(ET))

    def week_timestamp(kicks):
        dates = sorted({k.date() for k in kicks})
        sundays = [d for d in dates if d.weekday() == 6]
        anchor = sundays[0] if sundays else min(dates)
        if anchor.weekday() == 6:
            friday = anchor - timedelta(days=2)
        else:
            friday = anchor - timedelta(days=(anchor.weekday() - 4) % 7)
        return datetime(friday.year, friday.month, friday.day, 18, 0,
                        tzinfo=CHI)

    pred = set()
    for (s, w), g in sched.groupby(["season", "week"]):
        ts = week_timestamp(g["kickoff"])
        for _, r in g.iterrows():
            if r["kickoff"] > ts.astimezone(ET):
                pred.add(r["game_id"])
    print(f"  predictable REG games 2018..{season_max}: {len(pred)}",
          flush=True)
    return pred


def predictable_team_games(season_max):
    """Set of (season, week, team) for predictable REG games (convenience)."""
    sched = pd.read_parquet(os.path.join(DATA, "schedules_2018_2025.parquet"))
    sched = sched[(sched["game_type"] == "REG") &
                  (sched["season"] >= 2018) &
                  (sched["season"] <= season_max)].copy()
    gids = predictable_game_ids(season_max)
    sched = sched[sched["game_id"].isin(gids)]
    out = set()
    for _, r in sched.iterrows():
        out.add((int(r["season"]), int(r["week"]), r["home_team"]))
        out.add((int(r["season"]), int(r["week"]), r["away_team"]))
    return out


# ------------------------------------------------------- player history
def build_player_history(season, pred_gids=None):
    """Per-player-game receiving history, 2018..season (predictable REG only).

    Base rows from data/player_games.parquet (nflverse player_stats),
    inner-joined to predictable game_ids -- exactly the 001 base
    construction, including 0-target games. pbp supplies the receiving
    splits (receptions, air yards, yac); snap counts and PFR advstats merge
    on ukey|team as in 002.

    Returns a frame with one row per (player_name, team, season, week).
    """
    print("--- building per-player-game receiving history 2018.."
          f"{season} ---", flush=True)
    if pred_gids is None:
        pred_gids = predictable_game_ids(season)

    pg = pd.read_parquet(os.path.join(DATA, "player_games.parquet"))
    pg = pg[(pg["season"] >= 2018) & (pg["season"] <= season)].copy()
    n0 = len(pg)
    pg = pg[pg["game_id"].isin(pred_gids)].reset_index(drop=True)
    print(f"  player_games 2018..{season}: {n0} -> {len(pg)} predictable REG",
          flush=True)
    pg = pg.rename(columns={"targets": "targets"})
    # pbp receiving splits (receptions, air, yac); 0-target games have no
    # pbp receiver rows -> NaN -> 0 after the merge.
    parts = []
    for s in range(2018, season + 1):
        p = os.path.join(DATA, f"pbp_{s}.parquet")
        if not os.path.exists(p):
            continue
        df = pd.read_parquet(p, columns=PBP_WANT)
        parts.append(df[df["season_type"] == "REG"])
    pbp = pd.concat(parts, ignore_index=True)
    recv = pbp[pbp["receiver_player_name"].notna()].copy()
    g = recv.groupby(["receiver_player_name", "posteam", "season", "week"],
                     dropna=False)
    pr = g.agg(receptions=("complete_pass", "sum"),
               air=("air_yards", "sum"),
               yac=("yards_after_catch", "sum")).reset_index().rename(
        columns={"receiver_player_name": "player_name", "posteam": "team"})
    pr["adot_g"] = pr["air"] / pr["receptions"].replace(0, np.nan)
    # note: adot uses targets as denominator in 002 (rair/rtargets); the
    # 003A rq_adot is the 002 value, so recompute below after the merge.
    pr["yacrec_g"] = pr["yac"] / pr["receptions"].replace(0, np.nan)
    pg = pg.merge(pr, on=["player_name", "team", "season", "week"],
                  how="left")
    # team targets (for target_share) from pbp
    tt = (recv.groupby(["posteam", "season", "week"], dropna=False)
          .size().reset_index(name="team_targets")
          .rename(columns={"posteam": "team"}))
    pg = pg.merge(tt, on=["team", "season", "week"], how="left")
    pg["target_share"] = pg["targets"] / pg["team_targets"].replace(0, np.nan)
    # 002 adot definition: rair / rtargets (not receptions)
    pg["adot_g"] = pg["air"] / pg["targets"].replace(0, np.nan)
    pg["yacrec_g"] = pg["yac"] / pg["receptions"].replace(0, np.nan)

    # snap counts -> offense_pct (002 recipe: ukey|team, max offense_pct)
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
    pg["sukey"] = pg["player_name"].map(ukey) + "|" + pg["team"]
    pg = pg.merge(sn[["sukey", "season", "week", "offense_pct"]],
                  on=["sukey", "season", "week"], how="left")
    print(f"  snap merge rate: {pg['offense_pct'].notna().mean():.4f}",
          flush=True)

    # PFR advstats -> drop_pct_g, rec_bt_g (002 recipe)
    ar_parts = []
    for s in range(2018, season + 1):
        p = os.path.join(DATA, "v2", "raw",
                         f"advstats_week_rec_{s}.parquet")
        if os.path.exists(p):
            ar_parts.append(pd.read_parquet(p))
    ar = pd.concat(ar_parts, ignore_index=True)
    ar = ar[ar["game_type"] == "REG"].copy()
    ar["aukey"] = ar["pfr_player_name"].map(ukey) + "|" + ar["team"]
    ar = (ar.sort_values("week")
          .drop_duplicates(["aukey", "season", "week"], keep="last"))
    pg = pg.merge(
        ar[["aukey", "season", "week", "receiving_drop_pct",
            "receiving_broken_tackles"]].rename(
            columns={"aukey": "sukey",
                     "receiving_drop_pct": "drop_pct_g",
                     "receiving_broken_tackles": "rec_bt_g"}),
        on=["sukey", "season", "week"], how="left")
    print(f"  advstats merge rate: {pg['drop_pct_g'].notna().mean():.4f}",
          flush=True)
    return pg.drop(columns=["sukey"])


def player_trailing(pg, season, week):
    """Trailing player features for the target week.

    Groups by player_name (the documented 001/002/003A name-collision
    convention: first-initial.last collisions mix in the trail). Strictly
    prior (season, week); EWMA hl=3, max 16, most-recent-first. NaN -> 0
    matches the experiment's table fill.

    Note on the 002 row_id convention: the frozen 002 features use
    "strictly prior by row_id" which, for same-week name-collision
    duplicates, includes the earlier duplicate in the later duplicate's
    trail. For a PRODUCTION target week this is moot -- all history rows
    are strictly prior weeks, so the row set and ordering are identical.
    The historical check script documents the residual max diffs, which
    come only from this same-week-duplicate ordering nuance.

    Returns dict player_name -> feature dict (for the target week only).
    """
    out = {}
    for pn, grp in pg.groupby("player_name", sort=False):
        grp = grp.sort_values(["season", "week"]).reset_index(drop=True)
        m = (grp["season"] < season) | ((grp["season"] == season) &
                                        (grp["week"] < week))
        hist = grp[m].iloc[::-1].head(MAX_TRAIL)  # recent-first
        n = len(hist)
        if n < MIN_GAMES:
            continue
        t_ewma = ewma(hist["targets"].to_numpy())
        if not (t_ewma and t_ewma > 0):
            continue  # eval population requires trail_targets_ewma > 0
        v_snap = hist["offense_pct"].to_numpy(dtype=float)
        v_snap = v_snap[~np.isnan(v_snap)]
        last3 = v_snap[:3].mean() if len(v_snap) else np.nan
        e16 = ewma(v_snap) if len(v_snap) else np.nan
        snap_trend = (last3 - e16 if not np.isnan(last3) and
                      not np.isnan(e16) else np.nan)
        latest = hist.iloc[0]
        out[pn] = {
            "trail_targets_ewma": t_ewma,
            "trail_target_share_ewma": ewma(hist["target_share"].to_numpy()),
            "opp2_snap_pct": ewma(hist["offense_pct"].to_numpy()),
            "opp2_snap_trend": snap_trend,
            "rq_adot": ewma(hist["adot_g"].to_numpy()),
            "rq_yac_per_rec": ewma(hist["yacrec_g"].to_numpy()),
            "rq_drop_pct": ewma(hist["drop_pct_g"].to_numpy()),
            "rq_broken_tackles": ewma(hist["rec_bt_g"].to_numpy()),
            "trail_receptions_ewma": ewma(hist["receptions"].to_numpy()),
            "trail_games": n,
            "latest_game_included":
                f"{int(latest['season'])}-W{int(latest['week'])}",
            "team": grp.iloc[-1]["team"],
        }
    # NaN -> 0 (research convention; matches the experiment's table fill,
    # which is what the verified models were fit on).
    feats = ["trail_targets_ewma", "trail_target_share_ewma",
             "opp2_snap_pct", "opp2_snap_trend",
             "rq_adot", "rq_yac_per_rec", "rq_drop_pct", "rq_broken_tackles"]
    for pn in out:
        for c in feats:
            v = out[pn][c]
            out[pn][c] = 0.0 if (v is None or np.isnan(v)) else float(v)
    print(f"  player trailing: {len(out)} eligible player-weeks", flush=True)
    return out


# ------------------------------------------------------- team trailing
def team_game_tables(season):
    """Team-game pace tables from REG pbp 2018..season (002 recipe).

    plays: all play types. neut_pr: pass rate on neutral plays
    (qtr 1-3, |score diff| <= 10). dplays: defensive plays faced.
    Trailing EWMAs are strictly prior team-games.
    """
    parts = []
    for s in range(2018, season + 1):
        p = os.path.join(DATA, f"pbp_{s}.parquet")
        if not os.path.exists(p):
            continue
        parts.append(pd.read_parquet(
            p, columns=["season", "week", "season_type", "posteam",
                        "defteam", "play_type", "qtr", "score_differential"]))
    pbp = pd.concat(parts, ignore_index=True)
    pbp = pbp[pbp["season_type"] == "REG"].copy()
    tg = pbp.groupby(["posteam", "season", "week"], dropna=False)
    team_g = tg.agg(plays=("play_type", "size")).reset_index().rename(
        columns={"posteam": "team"})
    neut = pbp[pbp["qtr"].isin([1, 2, 3]) &
               (pbp["score_differential"].abs() <= 10)]
    ng = neut.groupby(["posteam", "season", "week"], dropna=False)
    neut_g = ng.agg(nplays=("play_type", "size"),
                    npass=("play_type",
                           lambda s: (s == "pass").sum())).reset_index().rename(
        columns={"posteam": "team"})
    neut_g["neut_pr"] = (neut_g["npass"] /
                         neut_g["nplays"].replace(0, np.nan))
    team_g = team_g.merge(neut_g[["team", "season", "week", "neut_pr"]],
                          on=["team", "season", "week"], how="left")
    dg = pbp.groupby(["defteam", "season", "week"], dropna=False)
    def_g = dg.agg(dplays=("play_type", "size")).reset_index().rename(
        columns={"defteam": "team"})
    team_g = team_g.merge(def_g, on=["team", "season", "week"], how="left")
    team_g = team_g.sort_values(["team", "season", "week"]).reset_index(
        drop=True)
    return team_g


def team_trail(team_g, team, col, season, week):
    """Trailing EWMA of a team-game column, strictly prior (season, week)."""
    g = team_g[team_g["team"] == team]
    m = (g["season"] < season) | ((g["season"] == season) &
                                  (g["week"] < week))
    hist = g[m].iloc[::-1].head(MAX_TRAIL)
    return ewma(hist[col].to_numpy()) if len(hist) else np.nan

# ------------------------------------------------------- QB expected starter
def qb_features_for_week(season, week, pred_ts, team_list):
    """002 Family I expected-starter reconstruction for the target week.

    For each team: prior-4 team-games' QB attempt leader is the default;
    the expected starter is the first QB in attempt-ranked order whose
    as-of injury status is not Out/Doubtful. Trailing QB stats are EWMAs
    over the chosen QB's own prior games (min-50-attempt blend with the
    league mean for EPA). Pressure from PFR pass advstats.

    As-of note: injuries_2026.csv carries no date_modified timestamps, so
    the experiment's dm <= pred_ts filter cannot be applied; the target
    week's report rows are the production analog (pre-game injury
    information). Documented here, not hidden.
    """
    print("--- QB expected-starter reconstruction ---", flush=True)
    parts = []
    for s in range(2018, season + 1):
        p = os.path.join(DATA, f"pbp_{s}.parquet")
        if not os.path.exists(p):
            continue
        parts.append(pd.read_parquet(p, columns=[
            "season", "week", "season_type", "posteam", "passer_player_name",
            "pass_attempt", "epa", "cpoe", "air_yards"]))
    pbp = pd.concat(parts, ignore_index=True)
    pbp = pbp[pbp["season_type"] == "REG"].copy()

    pss = pbp[pbp["passer_player_name"].notna()].copy()
    qatt = (pss.groupby(["posteam", "season", "week", "passer_player_name"],
                        dropna=False)["pass_attempt"].sum().reset_index()
            .rename(columns={"posteam": "team",
                             "passer_player_name": "qb_name",
                             "pass_attempt": "att"}))
    qatt["qb_ukey"] = qatt["qb_name"].map(ukey) + "|" + qatt["team"] + "|QB"

    # per-QB-game stats for trailing
    g = pss.groupby(["passer_player_name", "posteam", "season", "week"],
                    dropna=False)
    qb_game = g.agg(att=("pass_attempt", "sum"),
                    epa_sum=("epa", "sum"),
                    cpoe_mean=("cpoe", "mean"),
                    pair=("air_yards", "sum")).reset_index().rename(
        columns={"passer_player_name": "player_name", "posteam": "team"})
    qb_game["q_epa_g"] = qb_game["epa_sum"] / qb_game["att"].replace(0, np.nan)
    qb_game["q_adot_g"] = qb_game["pair"] / qb_game["att"].replace(0, np.nan)
    qb_game["qb_ukey"] = (qb_game["player_name"].map(ukey) + "|" +
                          qb_game["team"] + "|QB")
    qb_game = qb_game.sort_values(["qb_ukey", "season", "week"])
    qb_game["qrow"] = np.arange(len(qb_game))

    def _trail(gg, cols):
        gg = gg.sort_values("qrow").reset_index(drop=True)
        out = []
        for i in range(len(gg)):
            hist = gg.iloc[max(0, i - MAX_TRAIL):i].iloc[::-1]
            d = {"qrow": int(gg.loc[i, "qrow"])}
            for c in cols:
                d[f"trail_{c}"] = (ewma(hist[c].to_numpy())
                                   if len(hist) else np.nan)
            out.append(d)
        return pd.DataFrame(out)

    qtr = (qb_game.groupby("qb_ukey", group_keys=False)
           .apply(lambda gg: _trail(gg, ["att", "q_epa_g", "cpoe_mean",
                                         "q_adot_g"]),
                  include_groups=False).reset_index(drop=True))
    qb_game = qb_game.merge(qtr, on="qrow", how="left")
    lg = qb_game.groupby("season").apply(
        lambda gg: np.average(gg["q_epa_g"].fillna(0),
                              weights=gg["att"].fillna(0) + 1e-9),
        include_groups=False).to_dict()

    # PFR pressure per QB-game
    pr_parts = []
    for s in range(2018, season + 1):
        p = os.path.join(DATA, "v2", "raw", f"advstats_week_pass_{s}.parquet")
        if os.path.exists(p):
            pr_parts.append(pd.read_parquet(p))
    ap = pd.concat(pr_parts, ignore_index=True)
    ap = ap[ap["game_type"] == "REG"].copy()
    ap["aukey"] = ap["pfr_player_name"].map(ukey) + "|" + ap["team"] + "|QB"

    # injury lookup: target-week report rows (no date_modified in 2026 file)
    inj = pd.read_csv(os.path.join(DATA, "v2", "raw",
                                   f"injuries_{season}.csv"))
    inj = inj[inj["week"] == week].copy()
    inj["iukey"] = (inj["full_name"].map(ukey) + "|" + inj["team"] + "|QB")
    stat_map = {"Questionable": 1, "Doubtful": 2, "Out": 3}
    inj["status_num"] = inj["report_status"].map(stat_map).fillna(0).astype(int)
    inj = inj.sort_values("report_status").drop_duplicates("iukey",
                                                           keep="last")
    stat_lookup = dict(zip(inj["iukey"], inj["status_num"]))
    print(f"  injury report rows (week {week}): {len(inj)}", flush=True)

    # team-game weeks for the prior-4 lookup
    sched = pd.read_parquet(os.path.join(DATA, "schedules_2018_2025.parquet"))
    sched = sched[(sched["game_type"] == "REG")].copy()
    tw = pd.concat([
        sched[["season", "week", "home_team"]].rename(
            columns={"home_team": "team"}),
        sched[["season", "week", "away_team"]].rename(
            columns={"away_team": "team"})], ignore_index=True)

    out = {}
    for tm in team_list:
        prior = tw[(tw["team"] == tm) &
                   ((tw["season"] < season) |
                    ((tw["season"] == season) & (tw["week"] < week))
                    )].tail(4)
        pw = set(zip(prior["season"].astype(int), prior["week"].astype(int)))
        qa = qatt[(qatt["team"] == tm) &
                  qatt.set_index(["season", "week"]).index.isin(pw)]
        if len(qa) == 0:
            continue
        ranked = (qa.groupby(["qb_name", "qb_ukey"])["att"].sum()
                  .sort_values(ascending=False))
        leader = ranked.index[0]
        chosen, changed = leader, 0
        for qb_name, qb_uk in ranked.index:
            st = stat_lookup.get(qb_uk, 0)
            if st < 2:  # not Out/Doubtful
                chosen = (qb_name, qb_uk)
                changed = int(chosen != leader)
                break
        qb_name, qb_uk = chosen
        qh = qb_game[(qb_game["qb_ukey"] == qb_uk) &
                     ((qb_game["season"] < season) |
                      ((qb_game["season"] == season) &
                       (qb_game["week"] < week)))]
        qh = qh.tail(MAX_TRAIL)
        att_total = float(qh["att"].sum()) if len(qh) else 0.0
        lam = min(1.0, att_total / 50.0)
        qh = qh.iloc[::-1]
        epa_t = (qh["trail_q_epa_g"].iloc[-1] if len(qh) else np.nan)
        epa_t = 0.0 if np.isnan(epa_t) else epa_t
        cpoe_t = (qh["trail_cpoe_mean"].iloc[-1] if len(qh) else np.nan)
        cpoe_t = 0.0 if np.isnan(cpoe_t) else cpoe_t
        adot_t = (qh["trail_q_adot_g"].iloc[-1] if len(qh) else np.nan)
        adot_t = 0.0 if np.isnan(adot_t) else adot_t
        pr = ap[(ap["aukey"] == qb_uk) &
                ((ap["season"] < season) |
                 ((ap["season"] == season) & (ap["week"] < week))
                 )].tail(MAX_TRAIL)
        press_t = (ewma(pr["times_pressured_pct"].to_numpy())
                   if len(pr) else 0.0)
        press_t = 0.0 if np.isnan(press_t) else press_t
        out[tm] = {"qb_epa_trail": lam * epa_t + (1 - lam) * lg.get(season, 0.0),
                   "qb_cpoe_trail": cpoe_t,
                   "qb_adot_trail": adot_t,
                   "qb_pressure_trail": press_t,
                   "qb_changed": changed,
                   "qb_name": qb_name}
    print(f"  QB features built for {len(out)} teams", flush=True)
    return out


# ------------------------------------------------------- NGS trailing
def ngs_trailing(ngs, season, week):
    """Trailing EWMAs of the six NGS receiving fields, per player ukey,
    strictly prior NGS weeks (hl=3, max 16). Matches build_003A_features.py.
    Returns dict nplayer -> {feat: value, 'ngs_trail_weeks': n}."""
    ngs = ngs.sort_values(["nplayer", "season", "week"]).reset_index(drop=True)
    out = {}
    for nk, grp in ngs.groupby("nplayer", sort=False):
        grp = grp.sort_values(["season", "week"]).reset_index(drop=True)
        m = (grp["season"] < season) | ((grp["season"] == season) &
                                        (grp["week"] < week))
        hist = grp[m].iloc[::-1].head(MAX_TRAIL)  # recent-first
        n = len(hist)
        d = {"ngs_trail_weeks": n}
        for i, c in enumerate(NGS_COLS):
            v = ewma(hist[c].to_numpy()) if n else np.nan
            d[NGS_FEATS[i]] = 0.0 if np.isnan(v) else float(v)
        out[nk] = d
    return out

# ------------------------------------------------------- feature assembly
def build_features(season, week):
    """Build the 23 frozen M2 feature rows for the week's eligible WRTE.

    Trailing-window logic reproduces the experiment exactly: strictly-prior
    weeks, EWMA half-life 3, max 16 games, most-recent-first; player
    trailing grouped by player_name (collision convention); NaN -> 0
    (research convention).
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

    # ---- pre-week ratings (002 analog for 2026): oppd_def_pass_epa ----
    rt_path = os.path.join(DATA, f"ratings_current_{season}_w{week}.parquet")
    if not os.path.exists(rt_path):
        raise SystemExit(
            f"pre-week ratings file missing: {rt_path}. Refusing to "
            f"substitute stale ratings (as-of discipline).")
    rtg = pd.read_parquet(rt_path).set_index("team")
    if "def_pass_epa" not in rtg.columns:
        raise SystemExit("ratings file lacks def_pass_epa -- aborting.")

    # ---- player trailing (2018..season history) ----
    pg = build_player_history(season)
    ptrail = player_trailing(pg, season, week)

    # ---- team trailing (pace) ----
    team_g = team_game_tables(season)

    # ---- QB expected-starter features ----
    qb = qb_features_for_week(season, week, pred_ts, list(game_of))

    # ---- NGS trailing source (as-of rule; may degrade to M1) ----
    ngs, ngs_as_of, stale_ngs, rung = ngs_source(season, week)
    print(f"NGS rung: {rung} | stale_ngs={stale_ngs}", flush=True)
    ntrail = ngs_trailing(ngs, season, week) if rung == "M2" else {}

    # ---- current-team + position spine (2026) ----
    spine = pg[pg["season"] == season].copy()
    spine = spine.sort_values(["player_name", "week"]).drop_duplicates(
        "player_name", keep="last")
    cur_team = dict(zip(spine["player_name"], spine["team"]))
    pg26 = pd.read_parquet(os.path.join(DATA, "player_games.parquet"))
    pg26 = pg26[pg26["season"] == season].copy()
    pg26 = pg26.sort_values(["player_name", "week"]).drop_duplicates(
        "player_name", keep="last")
    cur_pos = dict(zip(pg26["player_name"], pg26["position"]))

    rows = []
    for pn, f in ptrail.items():
        if cur_pos.get(pn) != "WRTE":
            continue  # 003A population: receiving market (WRTE)
        team = cur_team.get(pn, f["team"])
        if team not in game_of:
            continue
        gm = game_of[team]
        is_home = 1 if team == gm["home_team"] else 0
        opp = gm["away_team"] if is_home else gm["home_team"]
        qbf = qb.get(team, {})
        row = {"player_name": pn, "team": team, "opponent": opp,
               "season": season, "week": week, "position": "WRTE",
               "market": MARKET_KEY,
               "prediction_timestamp": pred_ts.isoformat(),
               "latest_game_included": f["latest_game_included"],
               "trail_games": f["trail_games"],
               "trail_targets_ewma": f["trail_targets_ewma"],
               "trail_target_share_ewma": f["trail_target_share_ewma"],
               "opp2_snap_pct": f["opp2_snap_pct"],
               "opp2_snap_trend": f["opp2_snap_trend"],
               "pace_neutral_pass_rate": team_trail(team_g, team, "neut_pr",
                                                   season, week),
               "pace_team_plays": team_trail(team_g, team, "plays",
                                             season, week),
               "pace_combined": (lambda a, b: (a + b) / 2 if not
                                 (np.isnan(a) or np.isnan(b)) else np.nan)(
                   team_trail(team_g, team, "plays", season, week),
                   team_trail(team_g, team, "dplays", season, week)),
               "oppd_def_pass_epa": (rtg.loc[opp, "def_pass_epa"]
                                     if opp in rtg.index else np.nan),
               "rq_adot": f["rq_adot"],
               "rq_yac_per_rec": f["rq_yac_per_rec"],
               "rq_drop_pct": f["rq_drop_pct"],
               "rq_broken_tackles": f["rq_broken_tackles"],
               "qb_epa_trail": qbf.get("qb_epa_trail", np.nan),
               "qb_cpoe_trail": qbf.get("qb_cpoe_trail", np.nan),
               "qb_adot_trail": qbf.get("qb_adot_trail", np.nan),
               "qb_pressure_trail": qbf.get("qb_pressure_trail", np.nan),
               "qb_changed": qbf.get("qb_changed", 0)}
        nk = ukey(pn)
        nt = ntrail.get(nk, {})
        for c in NGS_FEATS:
            row[c] = nt.get(c, 0.0)  # missing NGS -> 0 (research convention)
        row["_ngs_trail_weeks"] = nt.get("ngs_trail_weeks", 0)
        rows.append(row)

    wf = pd.DataFrame(rows)
    if wf.empty:
        raise SystemExit("no eligible WRTE player-weeks built -- check caches")
    feat_all = S1 + S2 + NGS_FEATS
    wf[feat_all] = wf[feat_all].fillna(0)
    print(f"003A week frame: {len(wf)} eligible WRTE player-weeks; "
          f"median ngs trail weeks: "
          f"{wf['_ngs_trail_weeks'].median():.1f}", flush=True)
    return wf, pred_ts, ngs_as_of, stale_ngs, rung


# ------------------------------------------------------- prediction
def load_verified(rung):
    path = M2_PATH if rung == "M2" else M1_PATH
    if not os.path.exists(path):
        raise SystemExit(f"verified model missing: {path}")
    with open(path, "rb") as f:
        return pickle.load(f)


def predict_D(model, wf):
    """D-ensemble point prediction + quantiles, verbatim model math."""
    pA = R3A.pred_A(model["A"], wf)
    pB = R3A.pred_B(model["B"], wf)
    p50 = R3A.pred_C(model["C"], wf, 0.5)
    p25 = R3A.pred_C(model["C"], wf, 0.25)
    p75 = R3A.pred_C(model["C"], wf, 0.75)
    return (pA + pB + p50) / 3.0, pA, pB, p50, p25, p75


# ------------------------------------------------------- market join
def load_market_lines(path):
    """Same market-line schema as 16/17: player, market, line, source,
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
    model = load_verified(rung)
    model_version = MODEL_VERSION_M2 if rung == "M2" else MODEL_VERSION_M1
    feats = model["feats"]["pool"]
    print(f"verified model: {model_version} | {len(feats)} feats | "
          f"{model.get('fitted_on')}", flush=True)
    expect = (S1 + S2 + NGS_FEATS) if rung == "M2" else (S1 + S2)
    expect = list(dict.fromkeys(expect))
    if feats != expect:
        raise SystemExit("feature list mismatch vs verified audit -- aborting.")

    pD, pA, pB, p50, p25, p75 = predict_D(model, wf)
    wf = wf.copy()
    wf["_pD"], wf["_pA"], wf["_pB"], wf["_p50"] = pD, pA, pB, p50
    wf["_p25"], wf["_p75"] = p25, p75

    market_map = {}
    if market_json:
        P10 = _load_mod("prop10", os.path.join(REPO, "scripts/10_prop_projector.py"))
        index = P10.build_name_index(
            pd.read_parquet(os.path.join(DATA, "player_games.parquet")))
        for ln in load_market_lines(market_json):
            nv, note = P10.match_player(ln["player"], index)
            if nv is None:
                print(f"  market line unmatched, skipped: {ln['player']} "
                      f"({note})", flush=True)
                continue
            market_map.setdefault(nv, {})[ln["market"]] = ln
        print(f"market lines loaded: "
              f"{sum(len(v) for v in market_map.values())} matched",
              flush=True)

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
                "A_two_stage_ridge": round(float(r["_pA"]), 2),
                "B_gbm": round(float(r["_pB"]), 2),
                "C_quantile_median": round(float(r["_p50"]), 2),
                "D": "equal-weight mean of A/B/C, clipped >= 0",
            },
            "uncertainty": "Medium Uncertainty",
            "uncertainty_note": ("003A M2 ships calibrated P25/P75 intervals "
                                 "from the quantile GBM; the interval width "
                                 "is shown per player. Label uses the "
                                 "corrected uncertainty terminology."),
            "interval_p25": round(float(r["_p25"]), 1),
            "interval_p75": round(float(r["_p75"]), 1),
            "market_line": mkt,
            "prediction_timestamp": r["prediction_timestamp"],
            "ngs_data_as_of": ngs_as_of,
            "latest_game_included": r["latest_game_included"],
            "feature_window": ("trailing 16 games max, EWMA half-life 3.0, "
                               "most-recent-first, strictly prior weeks; "
                               "player trailing grouped by player_name "
                               "(001/002 collision convention)"),
            "model_version": model_version,
            "stale_ngs_used": bool(stale_ngs),
            "fallback_to_M1": bool(rung == "M1"),
            "trailing_games": int(r["trail_games"]),
            "ngs_trail_weeks": int(r["_ngs_trail_weeks"]),
        })

    obj = {
        "model": "Props Experiment 003A \u2014 receptions (experimental head)",
        "status": STATUS_EXPERIMENTAL,
        "display_note": DISPLAY_NOTE,
        "season": season,
        "week": week,
        "prediction_timestamp": pred_ts.isoformat(),
        "generated_at": datetime.now(CHI).isoformat(),
        "disclaimer": DISCLAIMER,
        "experiment_provenance": {
            "experiment": "Props Experiment 003A: Receptions",
            "preregistration": "experiments/props_experiment_003_market_"
                               "expansion/003A_receptions/PREREGISTRATION.md "
                               "(approved+frozen 2026-10-01 12:25 CDT)",
            "results": "experiments/props_experiment_003_market_expansion/"
                       "003A_receptions/RESULTS.md (M2 MATERIAL WIN on "
                       "locked 2023-2024 test; projection quality only, no "
                       "market evaluation; paper tracking only)",
            "model_artifact": ("experiments/props_experiment_003_market_"
                               "expansion/003A_receptions/models/"
                               "M2_verified_deployed.pkl -- verified "
                               "procedure, bit-for-bit deployment "
                               "verification in DEPLOYMENT_VERIFICATION.md, "
                               "no retraining"),
            "features": ("23 frozen M2 features: 8 S1 opportunity "
                         "(trail_targets_ewma, trail_target_share_ewma, "
                         "opp2_snap_pct, opp2_snap_trend, "
                         "pace_neutral_pass_rate, pace_team_plays, "
                         "pace_combined, oppd_def_pass_epa) + 9 S2 catch-point "
                         "(rq_adot, rq_yac_per_rec, rq_drop_pct, "
                         "rq_broken_tackles, qb_epa_trail, qb_cpoe_trail, "
                         "qb_adot_trail, qb_pressure_trail, qb_changed) + 6 "
                         "trailing NGS receiving"),
            "as_of": "Friday 18:00 America/Chicago; strictly-prior-week "
                     "trailing; pre-week ratings; frozen proxies only "
                     "(snap share + NGS air-yard share, no route "
                     "reconstruction)",
        },
        "market": MARKET_KEY,
        "n_projections": len(out),
        "projections": sorted(out, key=lambda d: d["player"]),
    }
    opath = os.path.join(DATA, f"prop_v2_{season}_w{week}_receptions.json")
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
                "uncertainty_note", "interval_p25", "interval_p75",
                "market_line", "prediction_timestamp",
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
        if not d["interval_p25"] <= d["interval_p75"]:
            errs.append(f"row {i} inverted interval")
    if errs:
        raise SystemExit("SCHEMA VALIDATION FAILED:\n" + "\n".join(errs[:20]))
    print(f"schema validation OK ({len(obj['projections'])} rows)", flush=True)


# ------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(
        description="003A receptions head -- experimental production")
    ap.add_argument("--refresh", action="store_true",
                    help="keyless refresh: NGS receiving pull")
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
