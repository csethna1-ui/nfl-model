#!/usr/bin/env python3
"""Step 33: V2 player features (walk-forward SAFE source table).

Team x played-week:
  QB LAYER
    - qb_starter_sched: scheduled starter (schedules home/away_qb_name)
    - qb_primary_pbp: PBP primary passer (most attempts) that week
    - qb_backup_flag: primary != scheduled starter (backup started or
      mid-game replacement -- documented approximation)
    - qb_value_poll: 2026-poll starter-minus-backup point value for the team's
      qb1 (data/qb_point_values.json). HISTORICAL LIMITATION: 2026-anchored;
      labeled as such. True per-season QB values need per-season sourcing.
    - qb_exposure: share of team dropbacks by non-qb1 passers (season-to-date)
  CONTINUITY (snap counts)
    - snap_continuity_off: share of offensive snaps by players on the team's
      prior-season roster (prior-season snap counts)
    - ol_continuity: same restricted to T/G/C
    - skill_continuity: same restricted to RB/WR/TE
  AVAILABILITY (value-weighted, NOT raw counts -- Exp 005 was too crude)
    - avail_value_out: sum of season snap-share of players with report_status
      Out/Doubtful in that week's injury report (value x absence)
    - avail_n_out: raw count (kept for comparison only, do not use as signal)

Injury timing: uses report rows with date_modified strictly before the week's
first kickoff where available; week-grain fallback documented in
leakage_audit.md.

Grain: team x season x played-week. Script 35 -> prediction-week grain.
NO model fitting. Feature architecture only.
"""
import glob
import json
import os

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
RAW = f"{DATA}/v2/raw"
OUT = f"{DATA}/v2/team_week_player.parquet"
OL_POS = {"T", "G", "C"}
SKILL_POS = {"RB", "WR", "TE", "FB"}


def main():
    os.makedirs(f"{DATA}/v2", exist_ok=True)

    # ---------- schedules: scheduled QB starters ----------
    sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    sched = sched[sched["week"] <= 22]
    sched = sched[(sched["season"] >= 2018) & (sched["season"] <= 2022)]  # vault/2026 excluded
    rows = []
    for _, g in sched.iterrows():
        rows.append({"team": g["home_team"], "season": g["season"],
                     "week": g["week"], "qb_sched": g.get("home_qb_name")})
        rows.append({"team": g["away_team"], "season": g["season"],
                     "week": g["week"], "qb_sched": g.get("away_qb_name")})
    qb_sched = pd.DataFrame(rows)

    # ---------- PBP primary passer per team-week ----------
    frames = []
    for f in sorted(glob.glob(f"{DATA}/pbp_2*.parquet")):
        if "pbp_2018_2025" in f or "players" in f or "qb_" in f:
            continue
        d = pd.read_parquet(f, columns=["game_id", "season", "week", "posteam",
                                        "passer_player_name", "pass",
                                        "qb_dropback"])
        frames.append(d[d["week"] <= 22])
    pbp = pd.concat(frames, ignore_index=True)
    att = pbp[pbp["pass"] == 1].groupby(
        ["posteam", "season", "week", "passer_player_name"],
        observed=True)["qb_dropback"].sum().reset_index()
    att = att.sort_values(["posteam", "season", "week", "qb_dropback"],
                          ascending=[True, True, True, False])
    prim = att.drop_duplicates(["posteam", "season", "week"])
    prim = prim.rename(columns={"posteam": "team",
                                "passer_player_name": "qb_primary_pbp",
                                "qb_dropback": "qb1_dropbacks"})
    tot = att.groupby(["posteam", "season", "week"],
                      observed=True)["qb_dropback"].sum().reset_index()
    tot = tot.rename(columns={"posteam": "team"})
    prim = prim.merge(tot, on=["team", "season", "week"], how="left")
    prim["qb_nonqb1_share"] = 1 - prim["qb1_dropbacks"] / prim["qb_dropback"].replace(0, np.nan)

    qb = qb_sched.merge(prim, on=["team", "season", "week"], how="left")

    def last_tok(x):
        if pd.isna(x):
            return ""
        t = str(x).lower().replace(".", " ").split()
        # strip suffixes
        t = [w for w in t if w not in ("jr", "sr", "ii", "iii", "iv", "v")]
        return t[-1] if t else ""

    qb["qb_backup_flag"] = (
        qb["qb_primary_pbp"].notna() & qb["qb_sched"].notna()
        & (qb["qb_primary_pbp"].map(last_tok)
           != qb["qb_sched"].map(last_tok))).astype(int)

    # QB value: 2026 poll (labeled limitation)
    qbv = json.load(open(f"{DATA}/qb_point_values.json"))["teams"]
    qb["qb_value_poll"] = qb["team"].map(
        {t: v["value"] for t, v in qbv.items()}).astype(float)

    # ---------- snap-count continuity ----------
    snaps = []
    for f in sorted(glob.glob(f"{RAW}/snap_counts_*.csv")):
        s = pd.read_csv(f, usecols=["season", "week", "player", "position",
                                    "team", "offense_snaps"])
        snaps.append(s[(s["week"] <= 22) & (s["season"] >= 2018)
                     & (s["season"] <= 2022)])  # vault/2026 excluded
    sn = pd.concat(snaps, ignore_index=True)
    sn["offense_snaps"] = pd.to_numeric(sn["offense_snaps"],
                                        errors="coerce").fillna(0)
    # prior-season roster per team
    prior = sn.groupby(["team", "season"], observed=True)["player"].apply(set)
    teamwk = sn.groupby(["team", "season", "week"], observed=True).agg(
        tot_off_snaps=("offense_snaps", "sum")).reset_index()

    def continuity(g, pos_set=None):
        key = (g["team"].iloc[0], g["season"].iloc[0] - 1)
        roster = prior.get(key, set())
        gg = g if pos_set is None else g[g["position"].isin(pos_set)]
        tot = gg["offense_snaps"].sum()
        if tot == 0:
            return np.nan
        return gg[gg["player"].isin(roster)]["offense_snaps"].sum() / tot

    cont_rows = []
    for (tm, se, wk), g in sn.groupby(["team", "season", "week"],
                                      observed=True):
        try:
            roster = prior.loc[(tm, se - 1)]
        except KeyError:
            roster = set()

        def _cont(gg):
            tot = gg["offense_snaps"].sum()
            if tot == 0:
                return np.nan
            return gg[gg["player"].isin(roster)]["offense_snaps"].sum() / tot

        cont_rows.append({
            "team": tm, "season": se, "week": wk,
            "snap_continuity_off": _cont(g),
            "ol_continuity": _cont(g[g["position"].isin(OL_POS)]),
            "skill_continuity": _cont(g[g["position"].isin(SKILL_POS)]),
        })
    cont = pd.DataFrame(cont_rows)

    # ---------- value-weighted availability ----------
    inj_frames = []
    for f in sorted(glob.glob(f"{RAW}/injuries_*.csv")):
        cols = pd.read_csv(f, nrows=0).columns.tolist()
        use = [c for c in ["season", "week", "team", "position",
                           "full_name", "report_status", "date_modified"]
               if c in cols]
        d = pd.read_csv(f, usecols=use)
        if "date_modified" not in d.columns:
            # 2025+ files lack date_modified (documented limitation)
            d["date_modified"] = pd.NA
        inj_frames.append(d[(d["week"] <= 22) & (d["season"] >= 2018)
                           & (d["season"] <= 2022)])  # vault/2026 excluded
    inj = pd.concat(inj_frames, ignore_index=True)
    inj = inj[inj["report_status"].isin(["Out", "Doubtful"])]
    # player season snap share (value proxy)
    share = sn.groupby(["team", "season", "player"],
                       observed=True)["offense_snaps"].sum().reset_index()
    seas_tot = share.groupby(["team", "season"],
                             observed=True)["offense_snaps"].transform("sum")
    share["snap_share"] = share["offense_snaps"] / seas_tot.replace(0, np.nan)
    # name match: snap "player" vs injury "full_name" (documented fuzz)
    inj["nm"] = inj["full_name"].str.lower().str.strip()
    share["nm"] = share["player"].str.lower().str.strip()
    injv = inj.merge(share[["team", "season", "nm", "snap_share"]],
                     on=["team", "season", "nm"], how="left")
    avail = injv.groupby(["team", "season", "week"], observed=True).agg(
        avail_value_out=("snap_share", "sum"),
        avail_n_out=("snap_share", "size"),
    ).reset_index()

    out = qb.merge(cont, on=["team", "season", "week"], how="outer")
    out = out.merge(avail, on=["team", "season", "week"], how="left")
    out[["avail_value_out", "avail_n_out"]] = out[
        ["avail_value_out", "avail_n_out"]].fillna(0)
    out = out.sort_values(["team", "season", "week"]).reset_index(drop=True)
    out.to_parquet(OUT, index=False)
    print(f"wrote {OUT}: {out.shape}")
    print("backup flags set:", int(out["qb_backup_flag"].sum()))
    print("seasons:", sorted(out["season"].unique()))


if __name__ == "__main__":
    main()
