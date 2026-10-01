#!/usr/bin/env python3
"""Build the extended feature table for Experiment 002.

DATA PREP ONLY. No model fitting of any kind.

Base: experiments/player_props_projection/data/modeling_table.parquet
(frozen Experiment 001 table, 2018-2024). This script ADDS the Family B-Q
features specified in experiment_002_protocol.md section 5.

Conventions (mirror build_modeling_table.py):
- Trailing EWMA, half-life 3, max 16 games, most-recent-first, strictly
  prior (season, week). rec2_* use half-life 1/8 as specified.
- NaN -> 0 for undefined rates/shares; trail_games preserved.
- Player-level trailing iterates over base rows (predictable games only),
  exactly like 001. Team-level trailing uses ALL completed REG games
  (all are strictly pre-cutoff information).
- Prediction timestamp Friday 18:00 America/Chicago; injury features use
  explicit date_modified <= cutoff as-of filtering.
- Name matching via ukey (first-initial.last|team), suffix-stripped.

Output: experiments/props_experiment_002/data/extended_features_2018_2024.parquet

Validation checks run on TRAIN+DEV ONLY. Test slice built blind.
"""
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = os.path.expanduser("~/workspace/nfl-model")
EXP = os.path.join(REPO, "experiments/props_experiment_002")
DATA = os.path.join(EXP, "data")
E01 = os.path.join(REPO, "experiments/player_props_projection")
CHI = ZoneInfo("America/Chicago")

HALF_LIFE = 3.0
MAX_TRAIL = 16


def ukey(name):
    s = str(name).lower().strip()
    s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)\.?$", "", s)
    s = re.sub(r"\.", " ", s)
    toks = [t for t in s.split() if t]
    if len(toks) < 2:
        return None
    return f"{toks[0][0]}.{toks[-1]}"


def ewma(v, hl=HALF_LIFE):
    v = np.asarray(v, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return np.nan
    w = 0.5 ** (np.arange(len(v)) / hl)  # v most-recent-first
    return float(np.sum(w * v) / np.sum(w))


def trail_frame_player(grp, stats, hl=HALF_LIFE, prefix="trail_",
                       suffix="_ewma"):
    """Per-player trailing EWMAs over base rows (strictly prior row_id)."""
    grp = grp.sort_values("row_id").reset_index(drop=True)
    out = []
    for i in range(len(grp)):
        hist = grp.iloc[max(0, i - MAX_TRAIL):i].iloc[::-1]
        # NOTE: no trail_games here -- base already carries the 001 version;
        # emitting it would create trail_games_x/_y on merge.
        d = {"row_id": int(grp.loc[i, "row_id"])}
        for c in stats:
            d[f"{prefix}{c}{suffix}"] = (ewma(hist[c].to_numpy(), hl)
                                         if len(hist) else np.nan)
        out.append(d)
    return pd.DataFrame(out)


def add_team_trail(tg, stats, hl=HALF_LIFE):
    """Per-team trailing EWMAs. tg sorted by (team, season, week).
    Returns tg with t_<stat>_ewma columns (strictly prior team games)."""
    tg = tg.sort_values(["team", "season", "week"]).reset_index(drop=True)
    tg["_trow"] = np.arange(len(tg))
    parts = []
    for _tm, g in tg.groupby("team", sort=False):
        g = g.sort_values("_trow").reset_index(drop=True)
        out = []
        for i in range(len(g)):
            hist = g.iloc[max(0, i - MAX_TRAIL):i].iloc[::-1]
            d = {"_trow": int(g.loc[i, "_trow"])}
            for c in stats:
                d[f"t_{c}_ewma"] = (ewma(hist[c].to_numpy(), hl)
                                   if len(hist) else np.nan)
            out.append(d)
        parts.append(pd.DataFrame(out))
    res = pd.concat(parts, ignore_index=True)
    return tg.merge(res, on="_trow", how="left").drop(columns=["_trow"])


def trail_frame_team(tg, stats, hl=HALF_LIFE, prefix="t_"):
    raise NotImplementedError("use add_team_trail")


def main():
    base = pd.read_parquet(
        f"{E01}/data/modeling_table.parquet")
    print(f"base: {base.shape}", flush=True)
    base = base.sort_values(["player_name", "season", "week"]).reset_index(drop=True)
    base["row_id"] = np.arange(len(base))
    base["pred_ts"] = pd.to_datetime(base["prediction_timestamp"], utc=True).dt.tz_convert(CHI)
    base["pukey"] = base["player_name"].map(ukey) + "|" + base["team"]

    # ================= pbp 2018-2024 (REG) =================
    pbp = pd.concat(
        [pd.read_parquet(f"{REPO}/data/pbp_{s}.parquet") for s in range(2018, 2025)],
        ignore_index=True)
    pbp = pbp[pbp["season_type"] == "REG"].copy()
    print(f"pbp REG 2018-2024: {len(pbp)}", flush=True)

    is_pass = pbp["play_type"] == "pass"
    is_run = pbp["play_type"] == "run"

    # ---- per-player-game pbp stats ----
    recv = pbp[pbp["receiver_player_name"].notna()].copy()
    g = recv.groupby(["receiver_player_name", "posteam", "season", "week"],
                     dropna=False)
    pg_recv = g.agg(rtargets=("receiver_player_name", "size"),
                    rair=("air_yards", "sum"),
                    ryac=("yards_after_catch", "sum"),
                    rrec=("complete_pass", "sum"),
                    rxyac=("xyac_mean_yardage", "sum")).reset_index().rename(
        columns={"receiver_player_name": "player_name", "posteam": "team"})

    rus = pbp[pbp["rusher_player_name"].notna()].copy()
    g = rus.groupby(["rusher_player_name", "posteam", "season", "week"],
                    dropna=False)
    pg_rush = g.agg(carries=("rusher_player_name", "size"),
                    y10=("yards_gained", lambda s: (s >= 10).sum()),
                    y1=("yards_gained", lambda s: (s <= 1).sum()),
                    gl=("yardline_100", lambda s: (s <= 5).sum())).reset_index().rename(
        columns={"rusher_player_name": "player_name", "posteam": "team"})

    pss = pbp[pbp["passer_player_name"].notna()].copy()
    g = pss.groupby(["passer_player_name", "posteam", "season", "week"],
                    dropna=False)
    pg_pass = g.agg(att=("pass_attempt", "sum"),
                    epa_sum=("epa", "sum"),
                    cpoe_mean=("cpoe", "mean"),
                    pair=("air_yards", "sum")).reset_index().rename(
        columns={"passer_player_name": "player_name", "posteam": "team"})

    pg_pbp = (pg_recv.merge(pg_rush, on=["player_name", "team", "season", "week"],
                            how="outer")
              .merge(pg_pass, on=["player_name", "team", "season", "week"],
                     how="outer"))
    pg_pbp["adot_g"] = pg_pbp["rair"] / pg_pbp["rtargets"].replace(0, np.nan)
    pg_pbp["yacrec_g"] = pg_pbp["ryac"] / pg_pbp["rrec"].replace(0, np.nan)
    pg_pbp["xypt_g"] = (pg_pbp["rair"] + pg_pbp["rxyac"]) / pg_pbp["rtargets"].replace(0, np.nan)
    pg_pbp["expl_g"] = pg_pbp["y10"] / pg_pbp["carries"].replace(0, np.nan)
    pg_pbp["stuff_g"] = pg_pbp["y1"] / pg_pbp["carries"].replace(0, np.nan)
    pg_pbp["q_epa_g"] = pg_pbp["epa_sum"] / pg_pbp["att"].replace(0, np.nan)
    pg_pbp["q_adot_g"] = pg_pbp["pair"] / pg_pbp["att"].replace(0, np.nan)
    keep_pbp = ["player_name", "team", "season", "week",
                "adot_g", "yacrec_g", "xypt_g", "expl_g", "stuff_g",
                "gl", "att", "q_epa_g", "cpoe_mean", "q_adot_g"]
    base = base.merge(pg_pbp[keep_pbp],
                      on=["player_name", "team", "season", "week"], how="left")
    print("pbp player-game merged", flush=True)

    # ---- per-team-game pbp stats ----
    tg = pbp.groupby(["posteam", "season", "week"], dropna=False)
    team_g = tg.agg(
        plays=("play_type", "size"),
        sacks_faced=("sack", "sum"),
        att_faced=("play_type", lambda s: (s == "pass").sum()),
        epa_pp=("epa", "mean")).reset_index().rename(columns={"posteam": "team"})
    neut = pbp[pbp["qtr"].isin([1, 2, 3]) &
               (pbp["score_differential"].abs() <= 10)]
    ng = neut.groupby(["posteam", "season", "week"], dropna=False)
    neut_g = ng.agg(nplays=("play_type", "size"),
                    npass=("play_type", lambda s: (s == "pass").sum())
                    ).reset_index().rename(columns={"posteam": "team"})
    neut_g["neut_pr"] = neut_g["npass"] / neut_g["nplays"].replace(0, np.nan)
    team_g = team_g.merge(neut_g[["team", "season", "week", "neut_pr"]],
                          on=["team", "season", "week"], how="left")
    # defensive view: plays/sacks allowed by defense
    dg = pbp.groupby(["defteam", "season", "week"], dropna=False)
    def_g = dg.agg(dplays=("play_type", "size"),
                   dsacks=("sack", "sum"),
                   datt=("play_type", lambda s: (s == "pass").sum())
                   ).reset_index().rename(columns={"defteam": "team"})

    # ================= schedules: dome / rest / points =================
    sched = pd.read_parquet(f"{REPO}/data/schedules_2018_2025.parquet")
    sched = sched[(sched["game_type"] == "REG") &
                  (sched["season"] >= 2018) & (sched["season"] <= 2024)].copy()
    sched["gameday"] = pd.to_datetime(sched["gameday"])
    sched["dome"] = sched["roof"].isin(["dome", "closed"]).astype(int)
    # long form: one row per team-game (ALL games incl. Thursday)
    home = sched[["season", "week", "gameday", "home_team", "home_score",
                  "away_score", "div_game", "dome"]].copy()
    home.columns = ["season", "week", "gameday", "team", "pts_for",
                    "pts_against", "div_game", "dome"]
    away = sched[["season", "week", "gameday", "away_team", "away_score",
                  "home_score", "div_game", "dome"]].copy()
    away.columns = ["season", "week", "gameday", "team", "pts_for",
                    "pts_against", "div_game", "dome"]
    tgl = pd.concat([home, away], ignore_index=True).sort_values(
        ["team", "season", "week"]).reset_index(drop=True)
    tgl["prev_gameday"] = tgl.groupby("team")["gameday"].shift(1)
    tgl["days_rest"] = ((tgl["gameday"] - tgl["prev_gameday"]).dt.days
                        .clip(upper=28).fillna(28))
    tgl["short_week"] = (tgl["days_rest"] <= 5).astype(int)
    tgl["long_rest"] = (tgl["days_rest"] >= 10).astype(int)
    # trailing points (strictly prior team games)
    tgl = add_team_trail(tgl, ["pts_for", "pts_against"])
    tgl = tgl.merge(team_g, on=["team", "season", "week"], how="left")
    tgl = tgl.merge(def_g, on=["team", "season", "week"], how="left")
    tgl = add_team_trail(tgl, ["plays", "neut_pr"])
    # opponent defensive trailing: sacks + plays allowed
    tgl = add_team_trail(tgl, ["dsacks", "datt", "dplays"])
    tgl["t_dsack_rate_ewma"] = (tgl["t_dsacks_ewma"] /
                                tgl["t_datt_ewma"].replace(0, np.nan))
    tgl["pace_comb"] = (tgl["t_plays_ewma"] + tgl["t_dplays_ewma"]) / 2

    gm = tgl[["team", "season", "week", "dome", "days_rest", "short_week",
              "long_rest", "div_game",
              "t_pts_for_ewma", "t_pts_against_ewma",
              "t_plays_ewma", "t_neut_pr_ewma", "pace_comb",
              "t_dsack_rate_ewma"]].copy()
    gm.columns = ["team", "season", "week", "envs_dome", "envf_days_rest",
                  "envf_short_week", "envf_long_rest", "envf_div_game",
                  "envs_team_pts_trail", "_opp_pts_allowed_trail",
                  "pace_team_plays", "pace_neutral_pass_rate", "pace_combined",
                  "def_sack_rate_trail"]
    base = base.merge(gm, on=["team", "season", "week"], how="left")
    oppm = gm[["team", "season", "week", "_opp_pts_allowed_trail",
               "def_sack_rate_trail"]].rename(
        columns={"team": "opponent",
                 "_opp_pts_allowed_trail": "envs_opp_pts_allowed_trail",
                 "def_sack_rate_trail": "ol_opp_sack_rate"})
    base = base.merge(oppm, on=["opponent", "season", "week"], how="left")
    print("schedules/pbp team-game merged", flush=True)

    # ================= pre-week ratings -> ctx / oppd =================
    rt = pd.read_parquet(f"{REPO}/data/games_with_ratings.parquet")
    rt = rt[(rt["game_type"] == "REG") & (rt["season"] >= 2018)
            & (rt["season"] <= 2024)].copy()
    rh = rt[["season", "week", "home_team", "home_off_epa",
              "home_off_pass_epa", "home_off_rush_epa", "home_off_sr",
              "elo_home", "home_def_epa", "home_def_pass_epa",
              "home_def_rush_epa", "home_def_sr"]].copy()
    rh.columns = ["season", "week", "team", "off_epa", "off_pass_epa",
                  "off_rush_epa", "off_sr", "elo",
                  "def_epa", "def_pass_epa", "def_rush_epa", "def_sr"]
    ra = rt[["season", "week", "away_team", "away_off_epa",
              "away_off_pass_epa", "away_off_rush_epa", "away_off_sr",
              "elo_away", "away_def_epa", "away_def_pass_epa",
              "away_def_rush_epa", "away_def_sr"]].copy()
    ra.columns = rh.columns
    rtg = pd.concat([rh, ra], ignore_index=True)
    base = base.merge(
        rtg[["team", "season", "week", "off_epa", "off_pass_epa",
             "off_rush_epa", "off_sr", "elo"]].rename(columns={
                 "off_epa": "ctx_team_off_epa",
                 "off_pass_epa": "ctx_team_off_pass_epa",
                 "off_rush_epa": "ctx_team_off_rush_epa",
                 "off_sr": "ctx_team_off_sr", "elo": "_elo"}),
        on=["team", "season", "week"], how="left")
    base = base.merge(
        rtg[["team", "season", "week", "elo"]].rename(
            columns={"team": "opponent", "elo": "_opp_elo"}),
        on=["opponent", "season", "week"], how="left")
    base["ctx_elo_adv"] = base["_elo"] - base["_opp_elo"]
    base = base.merge(
        rtg[["team", "season", "week", "def_epa", "def_pass_epa",
             "def_rush_epa", "def_sr"]].rename(columns={
                 "team": "opponent", "def_epa": "oppd_def_epa",
                 "def_pass_epa": "oppd_def_pass_epa",
                 "def_rush_epa": "oppd_def_rush_epa",
                 "def_sr": "oppd_def_sr"}),
        on=["opponent", "season", "week"], how="left")
    base = base.drop(columns=["_elo", "_opp_elo"])
    print("ratings merged", flush=True)

    # ================= snap counts -> opp2_* =================
    sn = pd.concat(
        [pd.read_csv(f"{REPO}/data/v2/raw/snap_counts_{s}.csv")
         for s in range(2018, 2025)], ignore_index=True)
    sn = sn[sn["game_type"] == "REG"].copy()
    sn["sukey"] = sn["player"].map(ukey) + "|" + sn["team"]
    # collapse rare same (ukey,team,season,week) dupes: keep max offense_pct
    sn = (sn.sort_values("offense_pct")
          .drop_duplicates(["sukey", "season", "week"], keep="last"))
    snp = sn[["sukey", "team", "season", "week", "offense_pct",
              "offense_snaps"]].copy()
    base = base.merge(snp.rename(columns={"sukey": "pukey"}),
                      on=["pukey", "team", "season", "week"], how="left")
    print(f"snap merge rate: {base['offense_pct'].notna().mean():.4f}",
          flush=True)

    # ================= PFR advstats =================
    def load_adv(kind):
        return pd.concat(
            [pd.read_parquet(f"{REPO}/data/v2/raw/advstats_week_{kind}_{s}.parquet")
             for s in range(2018, 2025)], ignore_index=True)
    ar = load_adv("rec")
    ar = ar[ar["game_type"] == "REG"].copy()
    ar["aukey"] = ar["pfr_player_name"].map(ukey) + "|" + ar["team"]
    ar = (ar.sort_values("week")
          .drop_duplicates(["aukey", "season", "week"], keep="last"))
    base = base.merge(
        ar[["aukey", "season", "week", "receiving_drop_pct",
            "receiving_broken_tackles"]].rename(
            columns={"aukey": "pukey",
                     "receiving_drop_pct": "drop_pct_g",
                     "receiving_broken_tackles": "rec_bt_g"}),
        on=["pukey", "season", "week"], how="left")
    au = load_adv("rush")
    au = au[au["game_type"] == "REG"].copy()
    au["aukey"] = au["pfr_player_name"].map(ukey) + "|" + au["team"]
    au = (au.sort_values("week")
          .drop_duplicates(["aukey", "season", "week"], keep="last"))
    base = base.merge(
        au[["aukey", "season", "week", "rushing_yards_before_contact_avg",
            "rushing_yards_after_contact_avg",
            "rushing_broken_tackles"]].rename(
            columns={"aukey": "pukey",
                     "rushing_yards_before_contact_avg": "ybc_g",
                     "rushing_yards_after_contact_avg": "yacatt_g",
                     "rushing_broken_tackles": "rush_bt_g"}),
        on=["pukey", "season", "week"], how="left")
    ap = load_adv("pass")
    ap = ap[ap["game_type"] == "REG"].copy()
    ap["aukey"] = ap["pfr_player_name"].map(ukey) + "|" + ap["team"]
    ap = (ap.sort_values("week")
          .drop_duplicates(["aukey", "season", "week"], keep="last"))
    base = base.merge(
        ap[["aukey", "season", "week", "times_pressured",
            "times_pressured_pct"]].rename(
            columns={"aukey": "pukey",
                     "times_pressured": "pressured_g",
                     "times_pressured_pct": "pressure_pct_g"}),
        on=["pukey", "season", "week"], how="left")
    # team pressure allowed: sum pressured over team QBs per game
    tp = (ap.groupby(["team", "season", "week"], dropna=False)
          .agg(team_pressured=("times_pressured", "sum")).reset_index())
    tp = tp.merge(team_g[["team", "season", "week", "att_faced"]],
                  on=["team", "season", "week"], how="left")
    # NOTE: att_faced in team_g is offensive plays where play_type=='pass'
    # for posteam==team -> team pass attempts. Correct denominator.
    tp["press_rate_g"] = tp["team_pressured"] / tp["att_faced"].replace(0, np.nan)
    tp = add_team_trail(tp.sort_values(["team", "season", "week"]),
                        ["press_rate_g"])
    base = base.merge(tp[["team", "season", "week", "t_press_rate_g_ewma"]].rename(
        columns={"t_press_rate_g_ewma": "ol_team_pressure_allowed"}),
        on=["team", "season", "week"], how="left")
    print("PFR merged", flush=True)

    # ================= NGS =================
    ngs = pd.read_parquet(f"{DATA}/ngs_receiving_2018_2024.parquet")
    ngs = ngs[ngs["season_type"] == "REG"].copy()
    ngs["nukey"] = (ngs["player_display_name"].map(ukey) + "|" +
                    ngs["team_abbr"])
    ngs = (ngs.sort_values("week")
           .drop_duplicates(["nukey", "season", "week"], keep="last"))
    base = base.merge(
        ngs[["nukey", "season", "week", "avg_separation",
             "avg_expected_yac"]].rename(
            columns={"nukey": "pukey", "avg_separation": "sep_g",
                     "avg_expected_yac": "xyac_g"}),
        on=["pukey", "season", "week"], how="left")
    print(f"NGS merge rate: {base['sep_g'].notna().mean():.4f}", flush=True)

    # ================= injuries (as-of Friday 18:00 CT) =================
    inj = pd.concat(
        [pd.read_csv(f"{REPO}/data/v2/raw/injuries_{s}.csv")
         for s in range(2018, 2025)], ignore_index=True)
    inj["dm"] = pd.to_datetime(inj["date_modified"], utc=True).dt.tz_convert(CHI)
    ts_map = (base[["season", "week", "pred_ts"]]
              .drop_duplicates().set_index(["season", "week"])["pred_ts"])
    inj["pred_ts"] = inj.set_index(["season", "week"]).index.map(ts_map)
    inj = inj[inj["dm"] <= inj["pred_ts"]].copy()
    inj = inj.sort_values("dm")
    # collision resolution per protocol: ukey|team|posg
    POSG_INJ = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WRTE",
                "TE": "WRTE", "T": "OL", "G": "OL", "C": "OL", "LS": "OL"}
    inj["posg"] = inj["position"].map(POSG_INJ).fillna("OTHER")
    inj["iukey"] = (inj["full_name"].map(ukey) + "|" + inj["team"] + "|" +
                    inj["posg"])
    # residual collisions: same ukey|team|posg but different players ->
    # drop from feature per protocol (counted in missingness)
    nunq = inj.groupby(["iukey", "season", "week"])["full_name"].nunique()
    resid_keys = set(nunq[nunq > 1].index)
    n_resid = len(resid_keys)
    if n_resid:
        key = inj.set_index(["iukey", "season", "week"]).index
        inj = inj[~key.isin(resid_keys)].copy()
    print(f"injury residual collisions dropped: {n_resid}", flush=True)
    inj = inj.sort_values("dm").drop_duplicates(
        ["iukey", "season", "week"], keep="last")
    stat_map = {"Questionable": 1, "Doubtful": 2, "Out": 3}
    inj["status_num"] = inj["report_status"].map(stat_map).fillna(0).astype(int)
    base["pukey_posg"] = base["pukey"] + "|" + base["position"]
    base = base.merge(
        inj[["iukey", "season", "week", "status_num"]].rename(
            columns={"iukey": "pukey_posg", "status_num": "inj_player_status"}),
        on=["pukey_posg", "season", "week"], how="left",
        validate="many_to_one")
    base["inj_player_status"] = base["inj_player_status"].fillna(0).astype(int)
    print(f"injury merge rate (listed): "
          f"{(base['inj_player_status'] > 0).mean():.4f}", flush=True)
    # team out share: trailing-4-game snaps from as-of Out/Doubtful players
    out_set = set(inj[inj["status_num"] >= 2]
                  .apply(lambda r: (r["iukey"], int(r["season"]), int(r["week"])),
                         axis=1))
    sn["sposg"] = sn["position"].map(POSG_INJ).fillna("OTHER")
    sn["sukey_posg"] = sn["sukey"] + "|" + sn["sposg"]
    sn["is_out"] = sn.apply(
        lambda r: (r["sukey_posg"], int(r["season"]), int(r["week"])) in out_set,
        axis=1)
    sn["sw"] = list(zip(sn["season"].astype(int), sn["week"].astype(int)))
    team_weeks = base[["team", "season", "week"]].drop_duplicates()
    tw = tgl[["team", "season", "week"]].copy()  # all team-games incl Thursday
    out_rows, ol_rows = [], []
    for (tm, s, w), _ in team_weeks.groupby(["team", "season", "week"]):
        prior = tw[(tw["team"] == tm) &
                   ((tw["season"] < s) | ((tw["season"] == s) & (tw["week"] < w)))
                   ].tail(4)
        if len(prior) == 0:
            out_rows.append({"team": tm, "season": s, "week": w,
                             "inj_team_out_share": 0.0})
            ol_rows.append({"team": tm, "season": s, "week": w,
                            "inj_ol_out": 0})
            continue
        pw = [(int(r.season), int(r.week)) for r in prior.itertuples()]
        s4 = sn[(sn["team"] == tm) & (sn["sw"].isin(pw))]
        tot = s4["offense_snaps"].sum()
        out_sn = s4[s4["is_out"]]["offense_snaps"].sum()
        out_rows.append({"team": tm, "season": s, "week": w,
                         "inj_team_out_share": (out_sn / tot if tot > 0 else 0.0)})
        olw = inj[(inj["team"] == tm) & (inj["season"] == s) &
                  (inj["week"] == w) & (inj["status_num"] >= 2) &
                  (inj["position"].isin(["T", "G", "C"]))]
        ol_rows.append({"team": tm, "season": s, "week": w,
                        "inj_ol_out": int(olw["full_name"].nunique())})
    base = base.merge(pd.DataFrame(out_rows),
                      on=["team", "season", "week"], how="left")
    base = base.merge(pd.DataFrame(ol_rows),
                      on=["team", "season", "week"], how="left")
    print("injuries done", flush=True)

    # ================= QB expected starter =================
    # team-game QB attempts (all completed games)
    qatt = (pss.groupby(["posteam", "season", "week", "passer_player_name"],
                        dropna=False)["pass_attempt"].sum().reset_index()
            .rename(columns={"posteam": "team",
                             "passer_player_name": "qb_name",
                             "pass_attempt": "att"}))
    qatt["qb_ukey"] = qatt["qb_name"].map(ukey) + "|" + qatt["team"] + "|QB"
    # as-of status lookup per (qb_ukey|QB, season, week)
    stat_lookup = {(r.iukey, int(r.season), int(r.week)): r.status_num
                   for r in inj.itertuples()}
    # per-QB-game stats for trailing
    qb_game = pg_pbp[["player_name", "team", "season", "week", "att",
                      "q_epa_g", "cpoe_mean", "q_adot_g"]].copy()
    qb_game["qb_ukey"] = (qb_game["player_name"].map(ukey) + "|" +
                          qb_game["team"] + "|QB")
    qb_game = qb_game.sort_values(["qb_ukey", "season", "week"])
    # trailing per-QB EWMAs (over QB's own prior games)
    qb_game["qrow"] = np.arange(len(qb_game))
    qtr = (qb_game.groupby("qb_ukey", group_keys=False)
           .apply(lambda g: trail_frame_player(
               g.rename(columns={"qrow": "row_id"}),
               ["att", "q_epa_g", "cpoe_mean", "q_adot_g"]),
               include_groups=False).reset_index(drop=True))
    qb_game = qb_game.merge(qtr, left_on="qrow", right_on="row_id", how="left")
    # league-mean EPA/play per season (for low-attempt blend)
    lg = qb_game.groupby("season").apply(
        lambda g: np.average(g["q_epa_g"].fillna(0), weights=g["att"].fillna(0) + 1e-9),
        include_groups=False).to_dict()
    # PFR pressure per QB-game (pass advstats are passer-centric: assume QB)
    qb_press = ap[["aukey", "season", "week", "times_pressured_pct"]].copy()
    qb_press["aukey"] = qb_press["aukey"] + "|QB"
    qb_press = qb_press.rename(columns={"times_pressured_pct": "pressure_pct_g"})

    exp_rows = []
    for (tm, s, w), _ in team_weeks.groupby(["team", "season", "week"]):
        prior = tw[(tw["team"] == tm) &
                   ((tw["season"] < s) | ((tw["season"] == s) & (tw["week"] < w))
                    )].tail(4)
        pw = [(int(r.season), int(r.week)) for r in prior.itertuples()]
        qa = qatt[(qatt["team"] == tm) &
                  qatt.set_index(["season", "week"]).index.isin(pw)]
        if len(qa) == 0:
            continue
        ranked = (qa.groupby(["qb_name", "qb_ukey"])["att"].sum()
                  .sort_values(ascending=False))
        leader = ranked.index[0]
        chosen, changed = leader, 0
        for qb_name, qb_uk in ranked.index:
            st = stat_lookup.get((qb_uk, s, w), 0)
            if st < 2:  # not Out/Doubtful
                chosen = (qb_name, qb_uk)
                changed = int(chosen != leader)
                break
        qb_name, qb_uk = chosen
        qh = qb_game[(qb_game["qb_ukey"] == qb_uk) &
                     ((qb_game["season"] < s) |
                      ((qb_game["season"] == s) & (qb_game["week"] < w)))]
        qh = qh.tail(MAX_TRAIL)
        # protocol: min 50 trailing attempts, else 50/50 blend with league mean
        att_total = float(qh["att"].sum()) if len(qh) else 0.0
        lam = min(1.0, att_total / 50.0)
        qh = qh.iloc[::-1]  # recent-first (trail cols already reflect full history)
        epa_t = (qh["trail_q_epa_g_ewma"].iloc[-1] if len(qh) else np.nan)
        epa_t = 0.0 if np.isnan(epa_t) else epa_t
        cpoe_t = (qh["trail_cpoe_mean_ewma"].iloc[-1] if len(qh) else np.nan)
        cpoe_t = 0.0 if np.isnan(cpoe_t) else cpoe_t
        adot_t = (qh["trail_q_adot_g_ewma"].iloc[-1] if len(qh) else np.nan)
        adot_t = 0.0 if np.isnan(adot_t) else adot_t
        pr = qb_press[(qb_press["aukey"] == qb_uk) &
                      ((qb_press["season"] < s) |
                       ((qb_press["season"] == s) & (qb_press["week"] < w))
                       )].tail(MAX_TRAIL)
        press_t = (ewma(pr["pressure_pct_g"].to_numpy()) if len(pr) else 0.0)
        press_t = 0.0 if np.isnan(press_t) else press_t
        exp_rows.append({
            "team": tm, "season": s, "week": w,
            "qb_epa_trail": lam * epa_t + (1 - lam) * lg.get(s, 0.0),
            "qb_cpoe_trail": cpoe_t,
            "qb_adot_trail": adot_t,
            "qb_pressure_trail": press_t,
            "qb_changed": changed})
    base = base.merge(pd.DataFrame(exp_rows),
                      on=["team", "season", "week"], how="left")
    print("QB expected starter done", flush=True)

    # ================= experience =================
    pg_all = pd.read_parquet(f"{REPO}/data/player_games.parquet")
    pg_all = pg_all[(pg_all["season"] >= 2018) & (pg_all["season"] <= 2024)].copy()
    pg_all = pg_all.drop_duplicates(["player_name", "season", "week"])
    first_season = pg_all.groupby("player_name")["season"].min().to_dict()
    # career games strictly prior: order within player
    pg_all = pg_all.sort_values(["player_name", "season", "week"])
    pg_all["career_g"] = pg_all.groupby("player_name").cumcount()
    expm = pg_all[["player_name", "team", "season", "week",
                   "career_g"]].drop_duplicates()
    expm["exp_career_games"] = expm["career_g"]
    expm["exp_rookie"] = (expm["season"] ==
                          expm["player_name"].map(first_season)).astype(int)
    expm["exp_second_year"] = (expm["season"] ==
                               expm["player_name"].map(first_season) + 1).astype(int)
    base = base.merge(expm[["player_name", "team", "season", "week",
                            "exp_career_games", "exp_rookie",
                            "exp_second_year"]],
                      on=["player_name", "team", "season", "week"], how="left")
    # raw opportunity for rec2_opp_hl1
    raw = pg_all[["player_name", "team", "season", "week",
                  "pass_att", "rush_att", "targets"]].drop_duplicates()
    base = base.merge(raw, on=["player_name", "team", "season", "week"],
                      how="left")
    base["opp_g"] = np.where(base["market"] == "pass_yards", base["pass_att"],
                     np.where(base["market"] == "rush_yards", base["rush_att"],
                              base["targets"]))
    print("experience merged", flush=True)

    # ================= player-level trailing loops =================
    P1 = ["offense_pct", "adot_g", "yacrec_g", "xypt_g", "expl_g", "stuff_g",
          "gl", "drop_pct_g", "rec_bt_g", "ybc_g", "yacatt_g", "rush_bt_g",
          "sep_g", "xyac_g"]
    t1 = (base.groupby("player_name", group_keys=False)
          .apply(lambda g: trail_frame_player(g, P1), include_groups=False)
          .reset_index(drop=True))
    base = base.merge(t1, on="row_id", how="left", validate="one_to_one")
    rename1 = {"trail_offense_pct_ewma": "opp2_snap_pct",
               "trail_adot_g_ewma": "rq_adot",
               "trail_yacrec_g_ewma": "rq_yac_per_rec",
               "trail_xypt_g_ewma": "xq_xYpt",
               "trail_expl_g_ewma": "ruq_explosive_rate",
               "trail_stuff_g_ewma": "ruq_stuff_rate",
               "trail_gl_ewma": "ruq_goal_line_carries",
               "trail_drop_pct_g_ewma": "rq_drop_pct",
               "trail_rec_bt_g_ewma": "rq_broken_tackles",
               "trail_ybc_g_ewma": "ruq_ybc_per_att",
               "trail_yacatt_g_ewma": "ruq_yac_per_att",
               "trail_rush_bt_g_ewma": "ruq_broken_tackles",
               "trail_sep_g_ewma": "rq_ngs_separation",
               "trail_xyac_g_ewma": "rq_ngs_xYAC"}
    base = base.rename(columns=rename1)

    # snap trend: mean(last 3) - ewma16
    def snap_trend(grp):
        grp = grp.sort_values("row_id").reset_index(drop=True)
        out = []
        for i in range(len(grp)):
            hist = grp.iloc[max(0, i - MAX_TRAIL):i].iloc[::-1]
            v = hist["offense_pct"].to_numpy(dtype=float)
            v = v[~np.isnan(v)]
            last3 = v[:3].mean() if len(v) else np.nan
            e16 = ewma(v) if len(v) else np.nan
            out.append({"row_id": int(grp.loc[i, "row_id"]),
                        "opp2_snap_trend": (last3 - e16
                                           if not np.isnan(last3) and
                                           not np.isnan(e16) else np.nan)})
        return pd.DataFrame(out)
    st = (base.groupby("player_name", group_keys=False)
          .apply(snap_trend, include_groups=False).reset_index(drop=True))
    base = base.merge(st, on="row_id", how="left", validate="one_to_one")

    # rec2: different half-lives
    for hl, suf in [(1.0, "hl1"), (8.0, "hl8")]:
        ty = (base.groupby("player_name", group_keys=False)
              .apply(lambda g: trail_frame_player(g, ["actual_yards"],
                                                  hl=hl, prefix="ry_"),
                     include_groups=False).reset_index(drop=True))
        base = base.merge(ty.rename(
            columns={"ry_actual_yards_ewma": f"rec2_yards_{suf}"}),
            on="row_id", how="left", validate="one_to_one")
    to = (base.groupby("player_name", group_keys=False)
          .apply(lambda g: trail_frame_player(g, ["opp_g"], hl=1.0,
                                              prefix="ro_"),
                 include_groups=False).reset_index(drop=True))
    base = base.merge(to.rename(columns={"ro_opp_g_ewma": "rec2_opp_hl1"}),
                      on="row_id", how="left", validate="one_to_one")
    print("trailing loops done", flush=True)

    # ================= finalize =================
    NEW = ["ctx_team_off_epa", "ctx_team_off_pass_epa",
           "ctx_team_off_rush_epa", "ctx_team_off_sr", "ctx_elo_adv",
           "oppd_def_epa", "oppd_def_pass_epa", "oppd_def_rush_epa",
           "oppd_def_sr", "envs_dome", "envs_team_pts_trail",
           "envs_opp_pts_allowed_trail", "envf_days_rest", "envf_rest_diff",
           "envf_short_week", "envf_long_rest", "envf_div_game",
           "pace_team_plays", "pace_combined", "pace_neutral_pass_rate",
           "ol_team_pressure_allowed", "ol_opp_sack_rate",
           "inj_player_status", "inj_team_out_share", "inj_ol_out",
           "exp_career_games", "exp_rookie", "exp_second_year",
           "opp2_snap_pct", "opp2_snap_trend",
           "rq_adot", "rq_yac_per_rec", "rq_drop_pct", "rq_broken_tackles",
           "rq_ngs_separation", "rq_ngs_xYAC",
           "ruq_ybc_per_att", "ruq_yac_per_att", "ruq_broken_tackles",
           "ruq_explosive_rate", "ruq_stuff_rate", "ruq_goal_line_carries",
           "qb_epa_trail", "qb_cpoe_trail", "qb_adot_trail",
           "qb_pressure_trail", "qb_changed",
           "rec2_yards_hl1", "rec2_yards_hl8", "rec2_opp_hl1", "xq_xYpt"]
    base["envf_rest_diff"] = np.nan  # filled below via opponent join
    od = (base[["team", "season", "week", "envf_days_rest"]]
          .drop_duplicates()
          .rename(columns={"team": "opponent", "envf_days_rest": "_orest"}))
    base = base.merge(od, on=["opponent", "season", "week"], how="left",
                      validate="many_to_one")
    base["envf_rest_diff"] = base["envf_days_rest"] - base["_orest"]
    base = base.drop(columns=["_orest"])
    # xq_xYpt is receiving-market only per protocol
    base.loc[base["market"] != "receiving_yards", "xq_xYpt"] = 0.0

    missing = [c for c in NEW if c not in base.columns]
    assert not missing, f"missing new cols: {missing}"
    base[NEW] = base[NEW].fillna(0)
    # drop scratch columns
    drop = [c for c in base.columns
            if c.endswith("_g") or c in ("pukey", "pukey_posg", "pred_ts",
                                         "row_id", "offense_pct",
                                         "offense_snaps", "pass_att",
                                         "rush_att", "targets", "opp_g",
                                         "_opp_pts_allowed_trail",
                                         "def_sack_rate_trail")]
    base = base.drop(columns=[c for c in drop if c in base.columns])

    out = f"{DATA}/extended_features_2018_2024.parquet"
    base.to_parquet(out, index=False)
    print(f"wrote {out}: {base.shape}", flush=True)

    # ---- validation on TRAIN+DEV ONLY ----
    chk = base[base["period"].isin(["train", "dev"])]
    print("--- validation (train+dev only) ---")
    print("rows:", len(chk))
    print("nulls in NEW cols:", int(chk[NEW].isna().sum().sum()))
    print("merge/availability (nonzero or defined) rates:")
    for c in NEW:
        nz = float((chk[c] != 0).mean())
        print(f"  {c}: nonzero={nz:.3f}")
    print("period counts:")
    print(base["period"].value_counts().to_string())
    print("eligible+played by period/market:")
    print(base[base["eligible_hist"] & base["played_role"]]
          .groupby(["period", "market"]).size().to_string())


if __name__ == "__main__":
    main()
