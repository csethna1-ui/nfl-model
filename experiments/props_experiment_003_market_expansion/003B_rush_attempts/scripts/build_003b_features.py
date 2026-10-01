#!/usr/bin/env python3
"""Build the 003B (rush attempts) feature table.

DATA PREP ONLY. No model fitting of any kind.

Base: experiments/props_experiment_002/data/extended_features_2018_2024.parquet
(frozen 002 table: 001 modeling rows + Family B-Q features, as-of-safe).

This script ADDS for 003B:
  - ngs_* : trailing (strictly prior weeks, half-life 3, max 16 games,
    most-recent-first) EWMAs of the NGS rushing family, computed on the NGS
    weekly frame (ALL player REG weeks 2018-2024, not just base rows), per
    player (name-key), then joined back to base rows by (player, season, week).
    NGS weekly releases are post-game, so strictly-prior-week trailing is
    the timestamp-safe rule (002 precedent for rq_ngs_separation).
  - neut_rush_rate = 1 - pace_neutral_pass_rate (prereg M1 component).

Population/target selection happens in run_experiment_003b.py, not here.

Output: experiments/props_experiment_003_market_expansion/003B_rush_attempts/
        data/features_003b_2018_2024.parquet

Validation checks run on TRAIN+DEV ONLY. Test slice built blind.
"""
import os
import re

import numpy as np
import pandas as pd

REPO = os.path.expanduser("~/workspace/nfl-model")
EXP = os.path.join(REPO, "experiments/props_experiment_003_market_expansion",
                   "003B_rush_attempts")
DATA = os.path.join(EXP, "data")
EXT = os.path.join(REPO, "experiments/props_experiment_002",
                   "data/extended_features_2018_2024.parquet")

HALF_LIFE = 3.0
MAX_TRAIL = 16

NGS_COLS = ["efficiency", "expected_rush_yards", "rush_yards_over_expected",
            "rush_pct_over_expected", "percent_attempts_gte_eight_defenders",
            "avg_time_to_los"]
NGS_OUT = {"efficiency": "ngs_eff",
           "expected_rush_yards": "ngs_xrush",
           "rush_yards_over_expected": "ngs_ryoe",
           "rush_pct_over_expected": "ngs_ryoe_pct",
           "percent_attempts_gte_eight_defenders": "ngs_8box",
           "avg_time_to_los": "ngs_ttl"}


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


def main():
    os.makedirs(DATA, exist_ok=True)
    base = pd.read_parquet(EXT)
    print(f"base (frozen 002 extended table): {base.shape}", flush=True)

    # ================= NGS rushing 2018-2024 (raw, weekly) =================
    ngs = pd.read_parquet(os.path.join(DATA, "ngs_rushing_2018_2024.parquet"))
    ngs = ngs[ngs["season_type"] == "REG"].copy()
    # DATA HYGIENE (verified 2026-10-01): the feed carries week==0
    # SEASON-TOTAL aggregate rows (354 rows; e.g. D.Henry 2022: 349 att /
    # 1538 yds = full-season totals). These are not weekly observations and
    # contain the target week's own game plus future games of that season,
    # so they are NOT valid strictly-prior-week trailing inputs under the
    # prereg's NGS trailing-only rule. Excluded here.
    n_w0 = int((ngs["week"] <= 0).sum())
    ngs = ngs[ngs["week"] > 0].copy()
    print(f"excluded {n_w0} week<=0 season-aggregate rows", flush=True)
    missing = [c for c in NGS_COLS if c not in ngs.columns]
    assert not missing, f"NGS feed missing prereg columns: {missing}"
    ngs["nplayer"] = ngs["player_display_name"].map(ukey)
    ngs = ngs.dropna(subset=["nplayer"])
    ngs = (ngs.sort_values("week")
           .drop_duplicates(["nplayer", "season", "week"], keep="last"))
    print(f"NGS REG player-weeks: {len(ngs)}", flush=True)

    # trailing per player over strictly prior weeks
    ngs = ngs.sort_values(["nplayer", "season", "week"]).reset_index(drop=True)
    trail_rows = []
    for pl, g in ngs.groupby("nplayer", sort=False):
        g = g.reset_index(drop=True)
        sw = list(zip(g["season"].astype(int), g["week"].astype(int)))
        for i in range(len(g)):
            hist = g.iloc[max(0, i - MAX_TRAIL):i].iloc[::-1]
            d = {"nplayer": pl, "season": int(g.loc[i, "season"]),
                 "week": int(g.loc[i, "week"]),
                 "ngs_trail_weeks": len(hist)}
            for c in NGS_COLS:
                d[NGS_OUT[c]] = (ewma(hist[c].to_numpy()) if len(hist) else np.nan)
            trail_rows.append(d)
    ngt = pd.DataFrame(trail_rows)

    base["nplayer"] = base["player_name"].map(ukey)
    base = base.merge(ngt, on=["nplayer", "season", "week"], how="left")
    base = base.drop(columns=["nplayer"])
    print(f"NGS trailing merge rate (any ngs col non-null): "
          f"{base[list(NGS_OUT.values())].notna().any(axis=1).mean():.4f}",
          flush=True)

    # ================= derived M1 component =================
    base["neut_rush_rate"] = 1.0 - base["pace_neutral_pass_rate"]

    # fill trailing-style NaNs -> 0 (002 precedent for NEW cols; matches
    # shared-protocol M0 NaN->0 convention)
    new_cols = list(NGS_OUT.values()) + ["neut_rush_rate"]
    base[new_cols] = base[new_cols].fillna(0)

    out = os.path.join(DATA, "features_003b_2018_2024.parquet")
    base.to_parquet(out, index=False)
    print(f"wrote {out}: {base.shape}", flush=True)

    # ---- validation on TRAIN+DEV ONLY (no locked-test inspection) ----
    chk = base[base["period"].isin(["train", "dev"])]
    rb = chk[(chk["market"] == "rush_yards") & (chk["eligible_hist"] == 1) &
             (chk["played_role"] == 1) & (chk["trail_rush_att_ewma"] >= 5)]
    print("--- validation (train+dev only) ---")
    print("003B population rows (train+dev):", len(rb))
    print("nulls in new cols:", int(chk[new_cols].isna().sum().sum()))
    print("ngs merge rate on 003B population:",
          float(rb[list(NGS_OUT.values())].notna().any(axis=1).mean()))
    print("ngs_trail_weeks median on 003B population:",
          float(rb["ngs_trail_weeks"].median()))
    print("target actual_att describe (003B pop, train+dev):")
    print(rb["actual_att"].describe().to_string())
    print("M0 (trail_rush_att_ewma) MAE on 003B pop train+dev:",
          float(np.abs(rb["actual_att"] - rb["trail_rush_att_ewma"]).mean()))


if __name__ == "__main__":
    main()
