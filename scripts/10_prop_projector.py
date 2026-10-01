#!/usr/bin/env python3
"""v1 data-backed NFL player prop projector.

Projection = trailing exponentially-weighted per-game yards (half-life 3 games,
same season first then prior season, min ~3 games else shrink toward positional
mean) + matchup adjustment (opponent's trailing defensive yards allowed vs
league average, coefficient FIT by OLS on 2018-2024 residuals -- not hand-picked).

This is NOT a betting backtest: no historical prop lines exist, so no edge can
be validated. Outputs are projections to paper-track; diagnostics report
projection accuracy (correlation/MAE), never ROI.

Usage:
  # one-time / occasional rebuild of aggregates from the pbp cache
  ./venv/bin/python scripts/10_prop_projector.py --rebuild
  # fit matchup coefficients on 2018-2024 (cached to data/prop_matchup_betas.json)
  ./venv/bin/python scripts/10_prop_projector.py --fit-betas
  # holdout diagnostics on 2025
  ./venv/bin/python scripts/10_prop_projector.py --diagnose
  # weekly run: compare projections vs sportsbook lines
  ./venv/bin/python scripts/10_prop_projector.py --season 2026 --week 2 \
      --market-json data/market_props_2026_w2.json

Market JSON: [{"player": "Josh Allen", "market": "pass_yards"|"rush_yards"|"receiving_yards",
               "line": 245.5}, ...]
Weekly output: data/prop_gaps_<season>_w<week>.csv sorted by |projection - line|.

FRIDAY WORKER refresh sequence (2026 in progress):
  ./venv/bin/python scripts/pull_pbp_players.py --refresh-season 2026
  ./venv/bin/python scripts/10_prop_projector.py --rebuild   # rebuild aggregates
  ./venv/bin/python scripts/10_prop_projector.py --season 2026 --week N \
      --market-json data/market_props_2026_wN.json
Betas are cached (data/prop_matchup_betas.json); refit only if method changes.
"""
import argparse
import json
import os
import re
import sys

import numpy as np
import pandas as pd

DATA = os.path.expanduser("~/workspace/nfl-model/data")
PG_PATH = f"{DATA}/player_games.parquet"
TD_PATH = f"{DATA}/team_defense.parquet"
BETA_PATH = f"{DATA}/prop_matchup_betas.json"
SCHED_PATH = f"{DATA}/schedules_2018_2025.parquet"

HALF_LIFE = 3.0
MAX_TRAIL = 16
MIN_GAMES = 3
FIT_SEASONS = (2018, 2024)

MARKETS = ["pass_yards", "rush_yards", "receiving_yards"]
# which defensive stat prices each market
MATCHUP_STAT = {"pass_yards": "pass_allowed",
                "rush_yards": "rush_allowed",
                "receiving_yards": "pass_allowed"}
# which position group supplies the shrinkage mean, by (market, player position)
SHRINK_POS = {
    "pass_yards": {"QB": "QB", "RB": "QB", "WRTE": "QB"},
    "rush_yards": {"QB": "QB", "RB": "RB", "WRTE": "RB"},
    "receiving_yards": {"QB": "WRTE", "RB": "WRTE", "WRTE": "WRTE"},
}
YCOL = {"pass_yards": "pass_yards", "rush_yards": "rush_yards",
        "receiving_yards": "receiving_yards"}
# role-relevance guard: only evaluate/fit on players who actually play the role
ELIGIBLE = {"pass_yards": lambda h: h["pass_att"].sum() >= 10,
            "rush_yards": lambda h: h["rush_att"].sum() >= 5,
            "receiving_yards": lambda h: h["targets"].sum() >= 5}
# for diagnostics: only grade games where the player actually played the role
# (a benched QB's 0 yards says nothing about the projection; books void those props)
ACTUAL_MIN = {"pass_yards": ("pass_att", 10),
              "rush_yards": ("rush_att", 5),
              "receiving_yards": ("targets", 3)}


# ---------------------------------------------------------------- data build
def build_aggregates():
    """player_games.parquet + team_defense.parquet from the pbp player cache."""
    src = f"{DATA}/pbp_players_2018_2026.parquet"
    if os.path.exists(src):
        pbp = pd.read_parquet(src)
    else:
        parts = []
        for s in range(2018, 2027):
            p = f"{DATA}/pbp_players_{s}.parquet"
            if os.path.exists(p):
                parts.append(pd.read_parquet(p))
        if not parts:
            sys.exit("no pbp player cache found; run scripts/pull_pbp_players.py first")
        pbp = pd.concat(parts, ignore_index=True)
    print(f"pbp rows: {len(pbp)}", flush=True)
    pbp = pbp[pbp["play_type"].isin(["pass", "run"])].copy()

    frames = []
    spec = [("passer_player_name", "passing_yards", "pass_yards", "pass_att"),
            ("rusher_player_name", "rushing_yards", "rush_yards", "rush_att"),
            ("receiver_player_name", "receiving_yards", "receiving_yards", "targets")]
    keys = ["player_name", "team", "opponent", "season", "week", "game_id"]
    for name_col, y_col, out_y, out_n in spec:
        m = pbp[name_col].notna()
        g = pbp[m].groupby([name_col, "posteam", "defteam", "season", "week",
                            "game_id"], dropna=False)
        d = g.agg(**{out_y: (y_col, "sum"), out_n: (y_col, "size")}).reset_index()
        d = d.rename(columns={name_col: "player_name", "posteam": "team",
                              "defteam": "opponent"})
        frames.append(d)
    pg = frames[0]
    for f in frames[1:]:
        pg = pg.merge(f, on=keys, how="outer")
    for c in ["pass_yards", "rush_yards", "receiving_yards",
              "pass_att", "rush_att", "targets"]:
        pg[c] = pg[c].fillna(0)
    pg["touches"] = pg["pass_att"] + pg["rush_att"] + pg["targets"]
    pg = pg[pg["touches"] > 0].copy()

    mix = pg.groupby(["player_name", "season"]).agg(
        pa=("pass_att", "sum"), ra=("rush_att", "sum"), tg=("targets", "sum"))

    def pos(r):
        if r["pa"] >= 10 and r["pa"] >= r["ra"] and r["pa"] >= r["tg"]:
            return "QB"
        return "RB" if r["ra"] >= r["tg"] else "WRTE"

    mix["position"] = mix.apply(pos, axis=1)
    pg = pg.merge(mix[["position"]], on=["player_name", "season"], how="left")
    pg = pg.sort_values(["player_name", "season", "week"]).reset_index(drop=True)
    pg.to_parquet(PG_PATH, index=False)
    print(f"player_games: {len(pg)} rows, {pg['player_name'].nunique()} players",
          flush=True)

    # team defensive yards allowed per game
    off = pbp[pbp["posteam"].notna()].groupby(
        ["game_id", "season", "week", "posteam"], as_index=False).agg(
        off_pass=("passing_yards", "sum"), off_rush=("rushing_yards", "sum"))
    rows = []
    for gid, grp in off.groupby("game_id"):
        if len(grp) != 2:
            continue
        a, b = grp.iloc[0], grp.iloc[1]
        rows.append({"game_id": gid, "season": int(a["season"]),
                     "week": int(a["week"]), "team": a["posteam"],
                     "pass_allowed": float(b["off_pass"]),
                     "rush_allowed": float(b["off_rush"])})
        rows.append({"game_id": gid, "season": int(b["season"]),
                     "week": int(b["week"]), "team": b["posteam"],
                     "pass_allowed": float(a["off_pass"]),
                     "rush_allowed": float(a["off_rush"])})
    td = pd.DataFrame(rows).sort_values(["team", "season", "week"]).reset_index(drop=True)
    td.to_parquet(TD_PATH, index=False)
    print(f"team_defense: {len(td)} rows", flush=True)
    return pg, td


# ------------------------------------------------------------------ helpers
def ewma_mean(vals):
    vals = np.asarray(vals, dtype=float)
    w = 0.5 ** (np.arange(len(vals)) / HALF_LIFE)
    return float(np.sum(w * vals) / np.sum(w))


def trailing(df, season, week, max_n=MAX_TRAIL):
    """Rows strictly before (season, week), most-recent-first, capped."""
    m = (df["season"] < season) | ((df["season"] == season) & (df["week"] < week))
    d = df[m].sort_values(["season", "week"], ascending=False)
    return d.head(max_n)


def positional_means(pg):
    """Mean per-game yards by (season, position), averaged over players (min 3 games)."""
    g = pg.groupby(["player_name", "season", "position"], as_index=False).agg(
        n=("game_id", "count"), py=("pass_yards", "mean"),
        ry=("rush_yards", "mean"), cy=("receiving_yards", "mean"))
    g = g[g["n"] >= MIN_GAMES]
    m = g.groupby(["season", "position"])[["py", "ry", "cy"]].mean()
    return m


def pos_mean_lookup(pmeans, season, position, market):
    col = {"pass_yards": "py", "rush_yards": "ry", "receiving_yards": "cy"}[market]
    grp = SHRINK_POS[market][position]
    for s in (season, season - 1):
        try:
            return float(pmeans.loc[(s, grp), col])
        except KeyError:
            continue
    return 0.0


def league_avg_lookup(lg_week, lg_season, season, week, stat):
    """League-average allowed per game: season-to-date, else prior full season."""
    std = lg_week[(lg_week["season"] == season) & (lg_week["week"] < week)]
    if len(std):
        return float(std[stat].mean())
    return float(lg_season.get(season - 1, {}).get(stat, 0.0))


def base_projection(hist, market, pmean):
    """Trailing EWMA; shrink toward positional mean when < MIN_GAMES."""
    n = len(hist)
    if n == 0:
        return pmean, 0
    wmean = ewma_mean(hist[YCOL[market]].to_numpy())
    if n >= MIN_GAMES:
        return wmean, n
    return (n / MIN_GAMES) * wmean + ((MIN_GAMES - n) / MIN_GAMES) * pmean, n


def full_projection(pg_p, td_teams, pmeans, lg_week, lg_season, betas,
                    season, week, market, opp_team):
    pos = pg_p["position"].iloc[-1]
    pmean = pos_mean_lookup(pmeans, season, pos, market)
    hist = trailing(pg_p, season, week)
    base, n = base_projection(hist, market, pmean)
    stat = MATCHUP_STAT[market]
    tdf = td_teams.get(opp_team)
    th = trailing(tdf, season, week) if tdf is not None else None
    if th is not None and len(th) and betas:
        diff = ewma_mean(th[stat].to_numpy()) - league_avg_lookup(
            lg_week, lg_season, season, week, stat)
        b = betas[market]
        adj = b["intercept"] + b["beta"] * diff
    else:
        adj = 0.0
    return base + adj, n, base


# ------------------------------------------------------------ beta fitting
def fit_betas(pg, td_teams, pmeans, lg_week, lg_season):
    """OLS of (actual - base projection) on matchup differential, 2018-2024."""
    betas = {}
    sub = pg[(pg["season"] >= FIT_SEASONS[0]) & (pg["season"] <= FIT_SEASONS[1])]
    for market in MARKETS:
        resids, diffs = [], []
        stat = MATCHUP_STAT[market]
        for (player, season), grp in sub.groupby(["player_name", "season"]):
            grp = grp.sort_values("week")
            pos = grp["position"].iloc[0]
            pmean = pos_mean_lookup(pmeans, season, pos, market)
            for _, row in grp.iterrows():
                hist = trailing(grp[grp["week"] < row["week"]], season,
                                row["week"])
                if len(hist) < MIN_GAMES or not ELIGIBLE[market](hist):
                    continue
                base, _ = base_projection(hist, market, pmean)
                tdf = td_teams.get(row["opponent"])
                th = trailing(tdf, season, row["week"]) if tdf is not None else None
                if th is None or not len(th):
                    continue
                diff = (ewma_mean(th[stat].to_numpy()) - league_avg_lookup(
                    lg_week, lg_season, season, row["week"], stat))
                resids.append(row[YCOL[market]] - base)
                diffs.append(diff)
        X = np.column_stack([np.ones(len(diffs)), np.array(diffs)])
        y = np.array(resids)
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        pred = X @ coef
        ss_res = np.sum((y - pred) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        betas[market] = {"intercept": float(coef[0]), "beta": float(coef[1]),
                         "n": int(len(y)),
                         "r2": float(1 - ss_res / ss_tot) if ss_tot else 0.0}
        print(f"  {market}: intercept={coef[0]:.3f} beta={coef[1]:.4f} "
              f"n={len(y)} R^2={betas[market]['r2']:.4f}", flush=True)
    with open(BETA_PATH, "w") as f:
        json.dump({"fit_seasons": list(FIT_SEASONS), "markets": betas}, f, indent=2)
    print(f"saved {BETA_PATH}")
    return betas


# ------------------------------------------------------------- diagnostics
def diagnose(pg, td_teams, pmeans, lg_week, lg_season, betas, season=2025):
    print(f"Holdout diagnostics on {season} (betas fit on "
          f"{FIT_SEASONS[0]}-{FIT_SEASONS[1]}):", flush=True)
    sub = pg[pg["season"] == season]
    out = {}
    for market in MARKETS:
        preds, acts, naive = [], [], []
        # full player history (all seasons <= target): matches production use.
        # trailing() enforces the no-lookahead cutoff per game.
        for player, phist_all in pg[pg["season"] <= season].groupby("player_name"):
            phist_all = phist_all.sort_values(["season", "week"]).reset_index(drop=True)
            g25 = phist_all[phist_all["season"] == season]
            if g25.empty:
                continue
            pos_by_season = dict(zip(phist_all["season"], phist_all["position"]))
            for _, row in g25.iterrows():
                wk = int(row["week"])
                hist = trailing(phist_all, season, wk)
                if len(hist) < MIN_GAMES or not ELIGIBLE[market](hist):
                    continue
                acol, amin = ACTUAL_MIN[market]
                if row[acol] < amin:
                    continue
                pos = pos_by_season.get(season, phist_all["position"].iloc[-1])
                pmean = pos_mean_lookup(pmeans, season, pos, market)
                base, _ = base_projection(hist, market, pmean)
                stat = MATCHUP_STAT[market]
                tdf = td_teams.get(row["opponent"])
                th = trailing(tdf, season, wk) if tdf is not None else None
                if th is not None and len(th) and betas:
                    diff = (ewma_mean(th[stat].to_numpy()) - league_avg_lookup(
                        lg_week, lg_season, season, wk, stat))
                    b = betas[market]
                    proj = base + b["intercept"] + b["beta"] * diff
                else:
                    proj = base
                preds.append(proj)
                acts.append(row[YCOL[market]])
                naive.append(float(np.mean(hist[YCOL[market]].to_numpy()[:3])))
        preds, acts, naive = map(np.array, (preds, acts, naive))
        mae = float(np.mean(np.abs(preds - acts)))
        mae_naive = float(np.mean(np.abs(naive - acts)))
        corr = float(np.corrcoef(preds, acts)[0, 1]) if len(preds) > 2 else 0.0
        out[market] = {"n": int(len(preds)), "corr": round(corr, 3),
                       "mae": round(mae, 1),
                       "mae_naive_last3": round(mae_naive, 1)}
        print(f"  {market:15s} n={len(preds):5d}  corr={corr:.3f}  "
              f"MAE={mae:.1f}  (naive last-3 avg MAE={mae_naive:.1f})", flush=True)
    return out


# ------------------------------------------------------------ name matching
def normalize_book(name):
    name = name.lower()
    name = re.sub(r"[^a-z ]", "", name)  # strip punctuation: . ' - ! etc.
    name = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", name)
    return re.sub(r"\s+", " ", name).strip()


def nflverse_key(nv_name):
    """'J.Allen' -> ('allen','j')."""
    nv = nv_name.lower()
    if "." in nv:
        first, rest = nv.split(".", 1)
        last = rest.split(".")[-1]
    else:
        parts = nv.split()
        first, last = parts[0], parts[-1]
    last = re.sub(r"[^a-z]", "", last)
    last = re.sub(r"(jr|sr|ii|iii|iv|v)$", "", last)
    first = re.sub(r"[^a-z]", "", first)
    return last, first[0] if first else ""


def build_name_index(pg):
    idx = {}
    touches = pg.groupby("player_name")["touches"].sum()
    for nv in pg["player_name"].unique():
        key = nflverse_key(nv)
        idx.setdefault(key, []).append(nv)
    # most-touched candidate first for ambiguous keys
    for k in idx:
        idx[k].sort(key=lambda n: touches.get(n, 0), reverse=True)
    return idx


def match_player(book_name, index):
    norm = normalize_book(book_name)
    toks = norm.split()
    if len(toks) < 2:
        return None, "unparseable name"
    key = (toks[-1], toks[0][0])
    cands = index.get(key, [])
    if not cands:
        return None, "no match"
    if len(cands) > 1:
        return cands[0], f"ambiguous {len(cands)} -> picked {cands[0]}"
    return cands[0], ""


# ------------------------------------------------------------------ weekly
def weekly_run(pg, td_teams, pmeans, lg_week, lg_season, betas, index,
               season, week, market_path):
    with open(market_path) as f:
        lines = json.load(f)
    sched = pd.read_parquet(SCHED_PATH)
    wk = sched[(sched["season"] == season) & (sched["week"] == week)]

    def opponent_of(team):
        g = wk[(wk["home_team"] == team) | (wk["away_team"] == team)]
        if g.empty:
            return None
        g = g.iloc[0]
        return g["away_team"] if g["home_team"] == team else g["home_team"]

    rows, unmatched = [], []
    for ln in lines:
        market = ln["market"]
        if market not in MARKETS:
            unmatched.append((ln["player"], f"unknown market {market}"))
            continue
        nv, note = match_player(ln["player"], index)
        if nv is None:
            unmatched.append((ln["player"], note))
            continue
        pg_p = pg[pg["player_name"] == nv].sort_values(["season", "week"])
        # Optional "team" override in the market JSON (handles offseason
        # team changes: trailing data reflects the player's old team).
        team = ln.get("team") or pg_p.iloc[-1]["team"]
        opp = opponent_of(team)
        if opp is None:
            unmatched.append((ln["player"], f"{team} not scheduled week {week}"))
            continue
        proj, n, base = full_projection(pg_p, td_teams, pmeans, lg_week,
                                        lg_season, betas, season, week,
                                        market, opp)
        gap = proj - ln["line"]
        rows.append({"player": ln["player"], "matched_as": nv,
                     "team": team, "opp": opp, "market": market,
                     "line": ln["line"], "projection": round(proj, 1),
                     "gap": round(gap, 1),
                     "lean": "over" if gap > 0 else "under",
                     "trailing_games": n, "match_note": note})
    out = pd.DataFrame(rows)
    if len(out):
        out["abs_gap"] = out["gap"].abs()
        out = out.sort_values("abs_gap", ascending=False).drop(columns="abs_gap")
    csv_path = f"{DATA}/prop_gaps_{season}_w{week}.csv"
    out.to_csv(csv_path, index=False)
    print(out.to_string(index=False))
    print(f"\nsaved {csv_path}")
    if unmatched:
        print("\nUNMATCHED LINES (no projection made):")
        for name, why in unmatched:
            print(f"  {name}: {why}")


# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--fit-betas", action="store_true")
    ap.add_argument("--diagnose", action="store_true")
    ap.add_argument("--season", type=int)
    ap.add_argument("--week", type=int)
    ap.add_argument("--market-json")
    args = ap.parse_args()

    if args.rebuild or not (os.path.exists(PG_PATH) and os.path.exists(TD_PATH)):
        pg, td = build_aggregates()
    else:
        pg = pd.read_parquet(PG_PATH)
        td = pd.read_parquet(TD_PATH)
        print(f"loaded player_games ({len(pg)} rows), "
              f"team_defense ({len(td)} rows)", flush=True)

    td_teams = {t: d.sort_values(["season", "week"]).reset_index(drop=True)
                for t, d in td.groupby("team")}
    pmeans = positional_means(pg)
    lg_week = td.groupby(["season", "week"], as_index=False)[
        ["pass_allowed", "rush_allowed"]].mean()
    lg_season = td.groupby("season")[["pass_allowed", "rush_allowed"]].mean().to_dict(
        orient="index")

    betas = None
    if args.fit_betas or (not os.path.exists(BETA_PATH)
                          and (args.diagnose or args.market_json)):
        print(f"Fitting matchup betas on {FIT_SEASONS[0]}-{FIT_SEASONS[1]}...",
              flush=True)
        betas = fit_betas(pg, td_teams, pmeans, lg_week, lg_season)
    elif os.path.exists(BETA_PATH):
        with open(BETA_PATH) as f:
            betas = json.load(f)["markets"]

    if args.diagnose:
        diagnose(pg, td_teams, pmeans, lg_week, lg_season, betas)

    if args.market_json:
        if args.season is None or args.week is None:
            sys.exit("--season and --week required with --market-json")
        index = build_name_index(pg)
        weekly_run(pg, td_teams, pmeans, lg_week, lg_season, betas, index,
                   args.season, args.week, args.market_json)


if __name__ == "__main__":
    main()
