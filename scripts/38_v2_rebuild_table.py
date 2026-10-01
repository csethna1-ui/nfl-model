#!/usr/bin/env python3
"""Step 38: V2 modeling-table rebuild (leakage pre-modeling checklist).

Reads data/v2/team_features_pred.parquet (2,743 rows, team x season x pred_week)
and produces data/v2/team_features_pred_v2.parquet with three honest fixes.
NO model fitting. 2018-2022 only; vault (2023-2025), 2026, experiment 006,
and all V1 code untouched.

Fix 1 -- PFR one-week shift (timestamp_policy.md section 2):
    The 17 PFR-sourced columns were merged as expanding means through week W-1.
    PFR advanced stats do not fully update until Wednesday morning after the
    weekend's games, so at the Tuesday 08:00 ET snapshot week W-1 is incomplete.
    Rebuilt here as expanding means over weeks <= W-2 (all prior seasons kept
    whole; the lag applies within-season), from the single-week table
    data/v2/team_week_pfr.parquet, mirroring scripts/35's expanding-mean logic
    (per-column NaN-aware counts, MIN_GAMES=4 else NaN).

Fix 2 -- Injury row-level cutoff (injury_cutoff_policy.md section 8):
    include row  <=>  date_modified < min(prediction_cutoff, team_game_kickoff)
    with prediction_cutoff = 08:00 ET on the most recent Tuesday strictly
    before the team's kickoff. Aggregated from data/v2/raw/injuries_2018..2022.csv
    into avail_value_out (season snap-share weighted) / avail_n_out (count) at
    (team, season, pred_week) grain, then expanding-meaned mirroring scripts/35
    (each week's value computed under the same Tuesday cutoff type).
    The Tuesday set is empirically identically zero; that is the honest output
    of the rule, verified by counting surviving rows (not hardcoded).

Fix 3 -- QB merge:
    Left-join data/v2/qb_value_pred.parquet (qb_* historical columns) on
    (team, season, pred_week). qb_value_poll is quarantined and never merged
    or used.

Verification: every non-replaced column is byte-identical, row count and grain
unchanged (2,743 rows). A lag-0 rebuild of the PFR columns is checked against
the original columns to validate the expanding-mean reimplementation.
"""
import hashlib
import os

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
V2 = f"{DATA}/v2"
RAW = f"{V2}/raw"
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
MIN_GAMES = 4  # mirrors scripts/35

PFR_COLS = [
    "pressure_allowed_pct", "sacks_allowed", "hits_taken", "hurries_taken",
    "blitzed_taken", "pressures_taken", "drops", "bad_throw_pct",
    "def_blitzes", "def_hurries", "def_qb_hits", "def_sacks", "def_pressures",
    "def_missed_tackles", "def_adot_allowed", "def_ypt_allowed",
    "def_prating_allowed",
]

# ----------------------------------------------------------------------------
# Fix 1: PFR one-week shift
# ----------------------------------------------------------------------------
def rebuild_pfr(base, lag_weeks):
    """Expanding means of single-week PFR values over history through W-1-lag.

    lag_weeks=0 reproduces scripts/35 (weeks < W); lag_weeks=1 gives the
    Tuesday-honest weeks <= W-2. All prior seasons enter whole.
    """
    tw = pd.read_parquet(f"{V2}/team_week_pfr.parquet")
    missing = [c for c in PFR_COLS if c not in tw.columns]
    assert not missing, f"PFR single-week table missing cols: {missing}"
    tw = tw.sort_values(["team", "season", "week"]).reset_index(drop=True)
    out = base.copy()
    for c in PFR_COLS:
        out[c] = np.nan
    for team, g in tw.groupby("team", observed=True):
        g = g.sort_values(["season", "week"]).reset_index(drop=True)
        seasons = g["season"].to_numpy()
        weeks = g["week"].to_numpy()
        vals = {c: pd.to_numeric(g[c], errors="coerce").to_numpy() for c in PFR_COLS}
        bmask = (base["team"] == team)
        for idx in base.index[bmask]:
            S = int(base.at[idx, "season"])
            W = int(base.at[idx, "pred_week"])
            elig = (seasons < S) | ((seasons == S) & (weeks <= W - 1 - lag_weeks))
            for c in PFR_COLS:
                v = vals[c][elig]
                v = v[~np.isnan(v)]
                out.at[idx, c] = v.mean() if len(v) >= MIN_GAMES else np.nan
    return out


# ----------------------------------------------------------------------------
# Fix 2: injury row-level cutoff
# ----------------------------------------------------------------------------
def tuesday_cutoff_8am_et(kickoff_et):
    """08:00 ET on the most recent Tuesday strictly before kickoff."""
    d = kickoff_et - pd.Timedelta(days=1)
    days_back = (d.weekday() - 1) % 7  # Monday=0 .. Sunday=6; Tuesday=1
    t = (d - pd.Timedelta(days=int(days_back))).replace(
        hour=8, minute=0, second=0, microsecond=0)
    return t


def rebuild_availability(base):
    # --- kickoffs per (season, week, team) from data/games.csv (ET -> UTC) ---
    gc = pd.read_csv(f"{DATA}/games.csv",
                     usecols=["season", "game_type", "week", "gameday",
                              "gametime", "home_team", "away_team"])
    gc = gc[gc["season"].between(2018, 2022)]
    assert gc["gametime"].notna().all(), "games.csv gametime must be complete"
    gc["kickoff_et"] = pd.to_datetime(gc["gameday"] + " " + gc["gametime"]) \
        .dt.tz_localize(ET)
    home = gc[["season", "week", "home_team", "kickoff_et"]] \
        .rename(columns={"home_team": "team"})
    away = gc[["season", "week", "away_team", "kickoff_et"]] \
        .rename(columns={"away_team": "team"})
    ko = pd.concat([home, away], ignore_index=True)
    assert not ko.duplicated(["season", "week", "team"]).any()
    ko["kickoff_utc"] = ko["kickoff_et"].dt.tz_convert(UTC)
    ko["cutoff_utc"] = ko["kickoff_et"].apply(tuesday_cutoff_8am_et) \
        .dt.tz_convert(UTC)

    # --- injury rows 2018-2022 ---
    frames = []
    for y in range(2018, 2023):
        frames.append(pd.read_csv(f"{RAW}/injuries_{y}.csv",
                                  usecols=["season", "game_type", "week", "team",
                                           "full_name", "report_status",
                                           "date_modified"]))
    inj = pd.concat(frames, ignore_index=True)
    inj = inj[inj["report_status"].isin(["Out", "Doubtful"])].copy()
    inj["date_modified_utc"] = pd.to_datetime(inj["date_modified"], utc=True)
    assert inj["date_modified_utc"].notna().all(), \
        "date_modified must parse for 2018-2022"

    # --- season snap-share value proxy ---
    sframes = []
    for y in range(2018, 2023):
        sframes.append(pd.read_csv(f"{RAW}/snap_counts_{y}.csv",
                                    usecols=["season", "team", "player",
                                             "offense_snaps"]))
    sn = pd.concat(sframes, ignore_index=True)
    sn["pkey"] = sn["player"].str.lower().str.strip()
    team_tot = sn.groupby(["season", "team"], observed=True)["offense_snaps"] \
        .sum().rename("team_snaps")
    play = sn.groupby(["season", "team", "pkey"], observed=True)["offense_snaps"] \
        .sum().rename("player_snaps").reset_index()
    play = play.merge(team_tot, on=["season", "team"])
    play["snap_share"] = play["player_snaps"] / play["team_snaps"]
    share = play.set_index(["season", "team", "pkey"])["snap_share"]

    # --- row-level cutoff: date_modified < min(cutoff, kickoff) ---
    inj["pkey"] = inj["full_name"].str.lower().str.strip()
    inj = inj.merge(ko[["season", "week", "team", "kickoff_utc", "cutoff_utc"]],
                    on=["season", "week", "team"], how="left")
    n_no_ko = inj["kickoff_utc"].isna().sum()
    inj = inj[inj["kickoff_utc"].notna()]  # bye-week rows: no kickoff to anchor
    bound = inj[["cutoff_utc", "kickoff_utc"]].min(axis=1)
    inj["survives"] = inj["date_modified_utc"] < bound
    n_survive = int(inj["survives"].sum())
    inj["snap_share"] = inj.set_index(["season", "team", "pkey"]) \
        .index.map(share).fillna(0.0).to_numpy()
    n_unmatched = int(((inj["survives"]) & (inj["snap_share"] == 0)).sum())

    # --- per-week knowable values, then expanding means mirroring scripts/35 ---
    wk = inj[inj["survives"]].groupby(["team", "season", "week"], observed=True) \
        .agg(avail_value_out=("snap_share", "sum"),
             avail_n_out=("snap_share", "size")).reset_index()
    # weeks with no surviving rows -> honest zeros (present for every game)
    all_games = ko[["team", "season", "week"]].drop_duplicates()
    wk = all_games.merge(wk, on=["team", "season", "week"], how="left")
    wk[["avail_value_out", "avail_n_out"]] = \
        wk[["avail_value_out", "avail_n_out"]].fillna(0.0)
    wk = wk.sort_values(["team", "season", "week"]).reset_index(drop=True)

    out = base.copy()
    out["avail_value_out"] = np.nan
    out["avail_n_out"] = np.nan
    for team, g in wk.groupby("team", observed=True):
        g = g.sort_values(["season", "week"]).reset_index(drop=True)
        seasons = g["season"].to_numpy()
        weeks = g["week"].to_numpy()
        vv = g["avail_value_out"].to_numpy()
        nn = g["avail_n_out"].to_numpy()
        bmask = (base["team"] == team)
        for idx in base.index[bmask]:
            S = int(base.at[idx, "season"])
            W = int(base.at[idx, "pred_week"])
            elig = (seasons < S) | ((seasons == S) & (weeks < W))
            n = int(elig.sum())
            if n >= MIN_GAMES:
                out.at[idx, "avail_value_out"] = vv[elig].mean()
                out.at[idx, "avail_n_out"] = nn[elig].mean()
    print(f"injury rows Out/Doubtful 2018-2022: {len(inj)} "
          f"({n_no_ko} bye-week rows dropped, no kickoff anchor)")
    print(f"rows surviving date_modified < min(Tuesday 08:00 ET, kickoff): "
          f"{n_survive}")
    print(f"surviving rows with unmatched snap name (weight 0): {n_unmatched}")
    return out


# ----------------------------------------------------------------------------
# Fix 3: QB merge
# ----------------------------------------------------------------------------
def merge_qb(base):
    q = pd.read_parquet(f"{V2}/qb_value_pred.parquet")
    assert not q.duplicated(["team", "season", "pred_week"]).any()
    assert "qb_value_poll" not in q.columns, "poll must not come from qb table"
    qb_cols = [c for c in q.columns if c.startswith("qb_")]
    before = len(base)
    out = base.merge(q[["team", "season", "pred_week"] + qb_cols],
                     on=["team", "season", "pred_week"], how="left")
    assert len(out) == before, "QB merge changed row count"
    n_match = out["qb_sched"].notna().sum()
    print(f"QB merge: {n_match}/{before} rows matched "
          f"({before - n_match} without qb_value_pred row)")
    return out, qb_cols


def main():
    base = pd.read_parquet(f"{V2}/team_features_pred.parquet")
    print(f"base table: {base.shape}")
    assert len(base) == 2743
    assert not base.duplicated(["team", "season", "pred_week"]).any()
    orig = base.copy()

    # --- Fix 1: validate reimplementation at lag 0, then apply lag 1 ---
    lag0 = rebuild_pfr(base, lag_weeks=0)
    maxdiff = max(
        (lag0[c].fillna(-999) - orig[c].fillna(-999)).abs().max()
        for c in PFR_COLS)
    print(f"PFR lag-0 rebuild max abs diff vs original: {maxdiff:.3e}")
    assert maxdiff < 1e-9, "lag-0 rebuild does not reproduce scripts/35 logic"
    out = rebuild_pfr(base, lag_weeks=1)
    n_changed = sum(
        ((out[c].fillna(-999) != orig[c].fillna(-999))).sum() for c in PFR_COLS)
    print(f"PFR lag-1 rebuild applied ({len(PFR_COLS)} cols, "
          f"{n_changed} cell values differ from original)")

    # --- Fix 2 ---
    out = rebuild_availability(out)

    # --- Fix 3 ---
    out, qb_cols = merge_qb(out)

    # --- verification: nothing else changed ---
    untouched = [c for c in orig.columns
                 if c not in PFR_COLS + ["avail_value_out", "avail_n_out"]]
    for c in untouched:
        a, b = orig[c], out[c]
        if pd.api.types.is_numeric_dtype(a):
            assert ((a.fillna(-999) == b.fillna(-999)).all()), \
                f"column changed unexpectedly: {c}"
        else:
            assert a.equals(b), f"column changed unexpectedly: {c}"
    assert len(out) == 2743
    assert not out.duplicated(["team", "season", "pred_week"]).any()
    print(f"verified: {len(untouched)} non-rebuilt columns identical, "
          f"{len(out)} rows, grain unchanged")

    outp = f"{V2}/team_features_pred_v2.parquet"
    out.to_parquet(outp, index=False)
    print(f"wrote {outp}: {out.shape}")
    h = hashlib.sha256(open(outp, "rb").read()).hexdigest()[:16]
    print(f"sha256[:16] = {h}")


if __name__ == "__main__":
    main()
