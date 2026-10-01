#!/usr/bin/env python3
"""Build the modeling table for Player Projection Experiment 001.

DATA PREP ONLY. No model fitting of any kind.

Grain: one row per (player, season, week, market) for the player's primary
role-market pair: QB -> pass_yards, RB -> rush_yards, WR/TE -> receiving_yards.
Regular season only. Games kicking off at/before the prediction timestamp are
excluded (Thursday games, rescheduled odd-weekday games).

Prediction timestamp: Friday 18:00 America/Chicago of game week, matching the
Friday production flow. All trailing features use games strictly before
(season, week) -- no within-week information, no lookahead.

Trailing aggregation: EWMA, half-life 3 games, max 16 games, most-recent-first
(same weighting as the current EWMA projector for comparability).

Inputs:
  ~/workspace/nfl-model/data/player_games.parquet
  ~/workspace/nfl-model/data/team_defense.parquet
  ~/workspace/nfl-model/data/schedules_2018_2025.parquet
  experiments/player_props_projection/data/pbp_rich_2018_2024.parquet
Output:
  experiments/player_props_projection/data/modeling_table.parquet

Validation checks (nulls, ranges, merge rates) are run on TRAIN+DEV ONLY.
The test slice (2023-2024) is built by identical code, blind.
"""
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = os.path.expanduser("~/workspace/nfl-model")
EXP = os.path.join(REPO, "experiments/player_props_projection")
DATA = os.path.join(EXP, "data")

CHI = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")

HALF_LIFE = 3.0
MAX_TRAIL = 16
MIN_GAMES = 3

MARKET_OF = {"QB": "pass_yards", "RB": "rush_yards", "WRTE": "receiving_yards"}
YCOL = {"pass_yards": "pass_yards", "rush_yards": "rush_yards",
        "receiving_yards": "receiving_yards"}
# role guards mirrored from scripts/10_prop_projector.py
ELIGIBLE = {"pass_yards": ("pass_att", 10),
            "rush_yards": ("rush_att", 5),
            "receiving_yards": ("targets", 5)}
ACTUAL_MIN = {"pass_yards": ("pass_att", 10),
              "rush_yards": ("rush_att", 5),
              "receiving_yards": ("targets", 3)}


def ewma(v):
    v = np.asarray(v, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return np.nan
    w = 0.5 ** (np.arange(len(v)) / HALF_LIFE)  # v most-recent-first
    return float(np.sum(w * v) / np.sum(w))


def main():
    pg = pd.read_parquet(f"{REPO}/data/player_games.parquet")
    td = pd.read_parquet(f"{REPO}/data/team_defense.parquet")
    sched = pd.read_parquet(f"{REPO}/data/schedules_2018_2025.parquet")
    rich = pd.read_parquet(f"{DATA}/pbp_rich_2018_2024.parquet")
    print(f"loaded: player_games {len(pg)}, team_defense {len(td)}, "
          f"schedules {len(sched)}, rich pbp {len(rich)}", flush=True)

    # ---- schedules: kickoff + prediction timestamp per (season, week) ----
    sched = sched[(sched["game_type"] == "REG") &
                  (sched["season"] >= 2018) & (sched["season"] <= 2024)].copy()
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

    ts_map = {}
    for (s, w), g in sched.groupby(["season", "week"]):
        ts_map[(s, w)] = week_timestamp(g["kickoff"])
    sched["pred_ts"] = sched.apply(lambda r: ts_map[(r["season"], r["week"])],
                                   axis=1)
    sched["predictable"] = sched["kickoff"] > sched["pred_ts"].apply(
        lambda t: t.astimezone(ET))
    n_sched, n_pred = len(sched), int(sched["predictable"].sum())
    print(f"schedules: {n_sched} REG games 2018-2024, {n_pred} kick off after "
          f"Friday 18:00 CT ({n_sched - n_pred} excluded: Thursday/early games)",
          flush=True)
    sched = sched[sched["predictable"]].copy()

    # ---- base player-game rows ----
    base = pg[(pg["season"] >= 2018) & (pg["season"] <= 2024)].copy()
    n0 = len(base)
    gid_info = sched[["game_id", "spread_line", "total_line", "home_team",
                      "away_team", "kickoff", "pred_ts"]].copy()
    base = base.merge(gid_info, on="game_id", how="inner")
    print(f"base rows: {n0} -> {len(base)} after REG+predictable game join "
          f"(merge rate {len(base)/n0:.3f})", flush=True)
    base["is_home"] = (base["team"] == base["home_team"]).astype(int)
    # spread_line > 0 means home favored (verified on 2024 W1 games)
    base["team_spread"] = np.where(base["is_home"] == 1,
                                   -base["spread_line"], base["spread_line"])
    base["team_implied_total"] = base["total_line"] / 2 - base["team_spread"] / 2
    base["opp_implied_total"] = base["total_line"] / 2 + base["team_spread"] / 2
    base["market"] = base["position"].map(MARKET_OF)
    base = base[base["market"].notna()].copy()

    # ---- rich pbp: player-game opportunity depth ----
    r = rich[rich["play_type"].isin(["pass", "run"])].copy()
    r["is_rz"] = r["yardline_100"] <= 20
    key = ["season", "week", "game_id"]

    recv = r[r["receiver_player_name"].notna()].copy()
    g = recv.groupby(["receiver_player_name", "posteam", "defteam"] + key,
                     dropna=False)
    prec = g.agg(targets=("receiver_player_name", "size"),
                 air_yards=("air_yards", "sum"),
                 yac=("yards_after_catch", "sum"),
                 receptions=("complete_pass", "sum"),
                 rz_targets=("is_rz", "sum")).reset_index().rename(
        columns={"receiver_player_name": "player_name", "posteam": "team",
                 "defteam": "opponent"})

    rush = r[r["rusher_player_name"].notna()].copy()
    g = rush.groupby(["rusher_player_name", "posteam", "defteam"] + key,
                     dropna=False)
    prush = g.agg(rz_carries=("is_rz", "sum")).reset_index().rename(
        columns={"rusher_player_name": "player_name", "posteam": "team",
                 "defteam": "opponent"})

    pss = r[r["passer_player_name"].notna()].copy()
    g = pss.groupby(["passer_player_name", "posteam", "defteam"] + key,
                    dropna=False)
    ppass = g.agg(completions=("complete_pass", "sum")).reset_index().rename(
        columns={"passer_player_name": "player_name", "posteam": "team",
                 "defteam": "opponent"})

    # team-game opportunity totals (share denominators)
    tg = r.groupby(["posteam", "season", "week", "game_id"], dropna=False)
    team_g = tg.agg(
        team_targets=("receiver_player_name",
                      lambda s: s.notna().sum()),
        team_pass_att=("play_type", lambda s: (s == "pass").sum()),
        team_rush_att=("play_type", lambda s: (s == "run").sum()),
        team_air_yards=("air_yards", "sum")).reset_index().rename(
        columns={"posteam": "team"})

    mkeys = ["player_name", "team", "season", "week", "game_id"]
    # 'opponent' also appears in the rich aggregates; base's copy (from the
    # same pbp posteam/defteam) is authoritative -- drop the duplicates.
    for df_ in (prec, prush, ppass):
        df_.drop(columns=["opponent"], inplace=True)
    # 'targets' exists in both base and prec (same pbp definition) -- keep
    # base's copy, but verify the rich re-derivation agrees.
    prec = prec.rename(columns={"targets": "targets_rich"})
    base = base.merge(prec, on=mkeys, how="left")
    base = base.merge(prush, on=mkeys, how="left")
    base = base.merge(ppass, on=mkeys, how="left")
    base = base.merge(team_g, on=["team", "season", "week", "game_id"],
                      how="left")
    for c in ["air_yards", "yac", "receptions", "rz_targets",
              "rz_carries", "completions"]:
        base[c] = base[c].fillna(0)
    # verify the rich re-derivation of targets matches player_games
    chk_t = base["targets_rich"].notna()
    assert (base.loc[chk_t, "targets"] ==
            base.loc[chk_t, "targets_rich"]).all(), \
        "targets definition mismatch between caches"
    base = base.drop(columns=["targets_rich"])

    # per-game shares and efficiency (NaN where undefined -> 0 later)
    base["target_share"] = base["targets"] / base["team_targets"].replace(0, np.nan)
    base["rush_share"] = base["rush_att"] / base["team_rush_att"].replace(0, np.nan)
    base["air_share"] = base["air_yards"] / base["team_air_yards"].replace(0, np.nan)
    base["ypt"] = base["receiving_yards"] / base["targets"].replace(0, np.nan)
    base["ypc"] = base["rush_yards"] / base["rush_att"].replace(0, np.nan)
    base["ypa"] = base["pass_yards"] / base["pass_att"].replace(0, np.nan)
    base["comp_rate"] = base["completions"] / base["pass_att"].replace(0, np.nan)
    base["yac_pt"] = base["yac"] / base["targets"].replace(0, np.nan)

    # ---- trailing features per player (strictly prior season/week) ----
    base = base.sort_values(["player_name", "season", "week"]).reset_index(drop=True)
    base["row_id"] = np.arange(len(base))

    FEATS = ["pass_yards", "rush_yards", "receiving_yards",
             "pass_att", "rush_att", "targets", "air_yards", "yac",
             "rz_targets", "rz_carries", "completions",
             "target_share", "rush_share", "air_share",
             "ypt", "ypc", "ypa", "comp_rate", "yac_pt",
             "team_targets", "team_pass_att", "team_rush_att"]

    def trail_frame(grp):
        grp = grp.sort_values("row_id").reset_index(drop=True)
        out = []
        for i in range(len(grp)):
            hist = grp.iloc[max(0, i - MAX_TRAIL):i].iloc[::-1]  # recent-first
            d = {"row_id": int(grp.loc[i, "row_id"]),
                 "trail_games": len(hist)}
            for c in FEATS:
                d["trail_" + c + "_ewma"] = (ewma(hist[c].to_numpy())
                                            if len(hist) else np.nan)
            # role-eligibility on trailing sums (mirrors current projector)
            d["trail_pass_att_sum"] = float(hist["pass_att"].sum())
            d["trail_rush_att_sum"] = float(hist["rush_att"].sum())
            d["trail_targets_sum"] = float(hist["targets"].sum())
            out.append(d)
        return pd.DataFrame(out)

    trail = (base.groupby("player_name", group_keys=False)
             .apply(trail_frame, include_groups=False))
    trail = trail.reset_index(drop=True)
    base = base.merge(trail, on="row_id", how="left", validate="one_to_one")
    base = base.drop(columns=["row_id"])

    # ---- opponent trailing defense ----
    td = td.sort_values(["team", "season", "week"]).reset_index(drop=True)
    td["trow_id"] = np.arange(len(td))

    def trail_opp(g):
        g = g.sort_values("trow_id").reset_index(drop=True)
        rows = []
        for i in range(len(g)):
            hist = g.iloc[max(0, i - MAX_TRAIL):i].iloc[::-1]
            rows.append({
                "trow_id": int(g.loc[i, "trow_id"]),
                "opp_trail_pass_allowed_ewma": (ewma(hist["pass_allowed"].to_numpy())
                                               if len(hist) else np.nan),
                "opp_trail_rush_allowed_ewma": (ewma(hist["rush_allowed"].to_numpy())
                                               if len(hist) else np.nan),
            })
        return pd.DataFrame(rows)

    td_t = (td.groupby("team", group_keys=False)
            .apply(trail_opp, include_groups=False).reset_index(drop=True))
    td = td.merge(td_t, on="trow_id", how="left", validate="one_to_one")
    td = td.drop(columns=["trow_id"])
    base = base.merge(
        td[["team", "season", "week", "opp_trail_pass_allowed_ewma",
            "opp_trail_rush_allowed_ewma"]].rename(
            columns={"team": "opponent"}),
        on=["opponent", "season", "week"], how="left")

    # ---- flags, target, period ----
    def elig(r):
        col, need = ELIGIBLE[r["market"]]
        return (r["trail_games"] >= MIN_GAMES) and (r["trail_" + col + "_sum"] >= need)

    def played(r):
        col, need = ACTUAL_MIN[r["market"]]
        return r[col] >= need

    base["eligible_hist"] = base.apply(elig, axis=1)
    base["played_role"] = base.apply(played, axis=1)
    base["actual_yards"] = base.apply(lambda r: r[YCOL[r["market"]]], axis=1)
    base["actual_att"] = base.apply(lambda r: r[ACTUAL_MIN[r["market"]][0]], axis=1)
    base["period"] = pd.cut(base["season"], bins=[2017, 2020, 2022, 2024],
                            labels=["train", "dev", "test"])

    base["kickoff_et"] = base["kickoff"].dt.tz_convert(ET).astype(str)
    base["prediction_timestamp"] = base["pred_ts"].astype(str)

    keep = ["player_name", "team", "opponent", "season", "week", "game_id",
            "position", "market", "kickoff_et", "prediction_timestamp",
            "period", "eligible_hist", "played_role",
            "actual_yards", "actual_att", "trail_games",
            # opportunity (stage 1)
            "trail_targets_ewma", "trail_rush_att_ewma", "trail_pass_att_ewma",
            "trail_target_share_ewma", "trail_rush_share_ewma",
            "trail_air_share_ewma",
            "trail_team_targets_ewma", "trail_team_pass_att_ewma",
            "trail_team_rush_att_ewma",
            "trail_rz_targets_ewma", "trail_rz_carries_ewma",
            "trail_air_yards_ewma",
            # efficiency (stage 2)
            "trail_ypt_ewma", "trail_ypc_ewma", "trail_ypa_ewma",
            "trail_comp_rate_ewma", "trail_yac_pt_ewma",
            "trail_pass_yards_ewma", "trail_rush_yards_ewma",
            "trail_receiving_yards_ewma",
            # opponent
            "opp_trail_pass_allowed_ewma", "opp_trail_rush_allowed_ewma",
            # game environment (pre-kickoff known)
            "spread_line", "total_line", "is_home", "team_spread",
            "team_implied_total", "opp_implied_total"]
    tbl = base[keep].copy()
    # NaN -> 0 for rate/share features (undefined = no opportunity); trail_games
    # preserves how much history existed. Documented in DATA_DICTIONARY.md.
    feat_cols = [c for c in keep if c.startswith("trail_") or c.startswith("opp_")]
    tbl[feat_cols] = tbl[feat_cols].fillna(0)

    out_path = f"{DATA}/modeling_table.parquet"
    tbl.to_parquet(out_path, index=False)
    print(f"wrote {out_path}: {tbl.shape}", flush=True)

    # ---- validation on TRAIN+DEV ONLY (test stays blind) ----
    chk = tbl[tbl["period"].isin(["train", "dev"])]
    print("--- validation (train+dev only) ---")
    print(f"rows: {len(chk)}, players: {chk['player_name'].nunique()}")
    print("nulls in feat cols:", int(chk[feat_cols].isna().sum().sum()))
    print("actual_yards range:", float(chk['actual_yards'].min()),
          float(chk['actual_yards'].max()))
    print("eligible_hist rate:", float(chk['eligible_hist'].mean()))
    print("played_role rate:", float(chk['played_role'].mean()))
    print("share bounds ok:",
          bool(((chk['trail_target_share_ewma'] >= 0) &
                (chk['trail_target_share_ewma'] <= 1)).all()),
          bool(((chk['trail_rush_share_ewma'] >= 0) &
                (chk['trail_rush_share_ewma'] <= 1)).all()))
    print("period counts:")
    print(tbl["period"].value_counts().to_string())
    print("eligible+played by period/market:")
    print(tbl[tbl["eligible_hist"] & tbl["played_role"]]
          .groupby(["period", "market"]).size().to_string())


if __name__ == "__main__":
    main()
