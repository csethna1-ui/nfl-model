#!/usr/bin/env python3
"""003C data prep: population table + NGS passing trailing + actual completions.

DATA PREP ONLY. No model fitting of any kind.

Inputs (read-only):
  - experiments/props_experiment_002/data/extended_features_2018_2024.parquet
    (frozen 002 table: population, as-of features, splits)
  - keyless nflverse NGS passing (import_ngs_data('passing'), 2016-2024)
  - local plain pbp 2018-2024 (for actual completions, same definition as
    001's completions = sum(complete_pass) for passer_player_name)

Conventions (mirror 002 build):
  - Population: market == 'pass_yards', eligible_hist == 1, played_role == 1
    (all QBs by construction).
  - Trailing EWMA, half-life 3, max 16 rows, most-recent-first, STRICTLY
    prior rows (per player over population rows sorted by (season, week)).
    NGS trailing is timestamp-safe: NGS releases are post-game, so only
    strictly-prior-week values are used (002 precedent).
  - NaN -> 0 for trailing NGS features (undefined = no history).
  - Name matching via ukey (first-initial.last|team), suffix-stripped
    (002 convention).
  - actual_comp from pbp, same source family as 001's completions column.

Validation prints run on TRAIN+DEV slices only. The test slice is built
blind (same code path, no outcome inspection).

Outputs:
  data/ngs_passing_2016_2024.parquet   (raw NGS pull, provenance)
  data/table_003c.parquet              (population + new 003C columns)
"""
import os
import re

import numpy as np
import pandas as pd

REPO = os.path.expanduser("~/workspace/nfl-model")
EXP = os.path.join(
    REPO, "experiments/props_experiment_003_market_expansion/003C_pass_attempts_completions")
DATA = os.path.join(EXP, "data")
os.makedirs(DATA, exist_ok=True)
EXT = os.path.join(REPO, "experiments/props_experiment_002/data",
                   "extended_features_2018_2024.parquet")

HALF_LIFE = 3.0
MAX_TRAIL = 16

NGS_RAW_COLS = ["avg_time_to_throw", "aggressiveness", "avg_intended_air_yards",
                "avg_air_yards_to_sticks", "expected_completion_percentage",
                "completion_percentage_above_expectation"]
NGS_OUT = ["ngs_ttt_trail", "ngs_aggro_trail", "ngs_iay_trail",
           "ngs_ayts_trail", "ngs_xcomp_trail", "ngs_cpoe_trail"]


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
    w = 0.5 ** (np.arange(len(v)) / hl)
    return float(np.sum(w * v) / np.sum(w))


def main():
    # ---------- 1. population ----------
    t = pd.read_parquet(EXT)
    pop = t[(t["market"] == "pass_yards") & (t["eligible_hist"] == 1) &
             (t["played_role"] == 1)].copy()
    pop = pop.sort_values(["player_name", "season", "week"]).reset_index(drop=True)
    pop["row_id"] = np.arange(len(pop))
    pop["pukey"] = pop["player_name"].map(ukey) + "|" + pop["team"]
    print(f"population: {len(pop)} "
          f"(train {(pop['period']=='train').sum()} / "
          f"dev {(pop['period']=='dev').sum()} / "
          f"test {(pop['period']=='test').sum()})", flush=True)
    assert (pop["position"] == "QB").all()

    # ---------- 2. NGS passing (keyless) ----------
    import nfl_data_py as nfl
    ngs = nfl.import_ngs_data("passing", list(range(2016, 2025)))
    ngs = ngs[ngs["season_type"] == "REG"].copy()
    ngs["nukey"] = ngs["player_display_name"].map(ukey) + "|" + ngs["team_abbr"]
    ngs = (ngs.sort_values("week")
           .drop_duplicates(["nukey", "season", "week"], keep="last"))
    ngs.to_parquet(os.path.join(DATA, "ngs_passing_2016_2024.parquet"),
                   index=False)
    print(f"NGS passing REG rows 2016-2024: {len(ngs)}", flush=True)

    pop = pop.merge(
        ngs[["nukey", "season", "week"] + NGS_RAW_COLS]
        .rename(columns={"nukey": "pukey",
                         **{c: c + "_g" for c in NGS_RAW_COLS}}),
        on=["pukey", "season", "week"], how="left")
    print(f"NGS weekly merge rate on population: "
          f"{pop['avg_time_to_throw_g'].notna().mean():.4f}", flush=True)

    # ---------- 3. trailing NGS features (strictly prior rows) ----------
    gcols = [c + "_g" for c in NGS_RAW_COLS]

    def trail_grp(g):
        g = g.sort_values("row_id").reset_index(drop=True)
        out = []
        for i in range(len(g)):
            hist = g.iloc[max(0, i - MAX_TRAIL):i].iloc[::-1]
            d = {"row_id": int(g.loc[i, "row_id"])}
            for c, o in zip(gcols, NGS_OUT):
                d[o] = (ewma(hist[c].to_numpy()) if len(hist) else np.nan)
            out.append(d)
        return pd.DataFrame(out)

    tr = (pop.groupby("pukey", group_keys=False)
          .apply(trail_grp, include_groups=False).reset_index(drop=True))
    pop = pop.merge(tr, on="row_id", how="left", validate="one_to_one")
    pop[NGS_OUT] = pop[NGS_OUT].fillna(0.0)
    print(f"NGS trailing NaN->0 rate (no history): "
          f"{(pop[NGS_OUT] == 0).all(axis=1).mean():.4f}", flush=True)

    # ---------- 4. actual completions (pbp, 001 definition) ----------
    pbp = pd.concat(
        [pd.read_parquet(f"{REPO}/data/pbp_{s}.parquet") for s in range(2018, 2025)],
        ignore_index=True)
    pbp = pbp[(pbp["season_type"] == "REG") &
              pbp["passer_player_name"].notna()].copy()
    g = pbp.groupby(["passer_player_name", "posteam", "season", "week"],
                    dropna=False)
    pg = g.agg(actual_comp=("complete_pass", "sum"),
               att_chk=("pass_attempt", "sum")).reset_index().rename(
        columns={"passer_player_name": "player_name", "posteam": "team"})
    pop = pop.merge(pg[["player_name", "team", "season", "week",
                        "actual_comp", "att_chk"]],
                    on=["player_name", "team", "season", "week"], how="left")
    print(f"completions merge rate: {pop['actual_comp'].notna().mean():.4f}",
          flush=True)
    pop["actual_comp"] = pop["actual_comp"].fillna(0).astype(int)
    cr = pop["actual_comp"] / pop["actual_att"].replace(0, np.nan)
    print(f"completion rate sanity: min {cr.min():.3f} max {cr.max():.3f} "
          f"mean {cr.mean():.3f}", flush=True)
    print(f"rows with comp > att: {(pop['actual_comp'] > pop['actual_att']).sum()}",
          flush=True)

    # ---------- 5. train+dev-only validation ----------
    td = pop[pop["period"].isin(["train", "dev"])].copy()
    assert td["actual_comp"].notna().all()
    assert (td["actual_att"] > 0).all()
    assert (td["actual_comp"] <= td["actual_att"]).all(), \
        "comp > att on train/dev"
    print(f"train+dev rows: {len(td)}, comp<=att holds everywhere", flush=True)

    pop.to_parquet(os.path.join(DATA, "table_003c.parquet"), index=False)
    print(f"WROTE {os.path.join(DATA, 'table_003c.parquet')} shape={pop.shape}",
          flush=True)


if __name__ == "__main__":
    main()
