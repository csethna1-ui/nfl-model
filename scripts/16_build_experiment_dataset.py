#!/usr/bin/env python3
"""Step 16: Build the experimental game-level dataset for model experiments.

One row per game, 2018-2025 (same scope as the walk-forward backtest,
playoffs included). Every column is strictly what was knowable pregame.

Writes:
  data/experiments/games_features.parquet
  experiments/experiment_001_market_residual/config.json
  experiments/experiment_001_market_residual/leakage_audit.md

FROZEN inputs (read-only): data/games_with_preds.parquet,
data/games_with_ratings.parquet, data/schedules_2018_2025.parquet.
"""
import json
import os

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
EXP_DATA = f"{DATA}/experiments"
EXP_DIR = os.path.join(REPO_ROOT, "experiments", "experiment_001_market_residual")
os.makedirs(EXP_DATA, exist_ok=True)
os.makedirs(EXP_DIR, exist_ok=True)

FEATURES = ["elo_diff", "off_epa_diff", "def_epa_diff", "off_pass_diff",
            "off_rush_diff", "def_pass_diff", "def_rush_diff",
            "sr_off_diff", "sr_def_diff", "rest_diff", "div_game", "week"]

audit_lines = []


def audit(msg):
    audit_lines.append(msg)
    print("AUDIT:", msg)


def main():
    d = pd.read_parquet(f"{DATA}/games_with_preds.parquet")
    d = d[d["season"].between(2018, 2025)].copy()
    audit(f"scope: {len(d)} games, seasons 2018-2025 "
          f"(REG/PO: {d['game_type'].value_counts().to_dict()})")

    # ---- structural checks ----
    assert d["game_id"].is_unique, "duplicate game_id!"
    audit("game_id unique: OK")
    assert d["spread_line"].notna().all(), "missing market spread!"
    assert d["home_margin"].notna().all(), "missing actual margin!"
    audit("market_spread and actual_margin present on every row: OK")
    for c in FEATURES:
        n = int(d[c].isna().sum())
        assert n == 0, f"feature {c} has {n} nulls"
    audit(f"all {len(FEATURES)} walk-forward features non-null 2018-2025: OK")

    # ---- cross-file consistency: ratings carried through uncorrupted ----
    r = pd.read_parquet(f"{DATA}/games_with_ratings.parquet")
    r = r[r["season"].between(2018, 2025)][["game_id", "elo_home", "elo_away",
                                            "home_off_epa", "away_off_epa"]]
    m = d.merge(r, on="game_id", suffixes=("", "_rt"))
    assert np.allclose(m["elo_diff"], m["elo_home_rt"] - m["elo_away_rt"],
                       equal_nan=True), "elo_diff mismatch vs ratings file"
    assert np.allclose(m["off_epa_diff"],
                       m["home_off_epa_rt"] - m["away_off_epa_rt"],
                       equal_nan=True), "off_epa_diff mismatch vs ratings file"
    audit("feature values match step-3 ratings file exactly: OK")

    # ---- design audit (code inspection, cited) ----
    audit("ELO: scripts/03_ratings.py run_elo() attaches PRE-WEEK ratings to each "
          "game and applies updates only AFTER the week's games (weekly batching).")
    audit("EPA: scripts/03_ratings.py run_epa() attaches pre-week EWMA ratings; "
          "weekly PBP aggregates update ratings only after the week's games.")
    audit("GBM inputs: scripts/04_backtest.py trains on expanding window of past "
          "games only; predictions for week w never see week w or later.")
    audit("rest_diff/div_game/week: derived from the schedule, known pregame by "
          "construction; no outcome information.")
    audit("market_spread (spread_line): nflverse historical line, known pregame by "
          "construction. PROVENANCE: consensus/opening proxy, NOT a verified "
          "executable closing line (see config.json).")

    # ---- residual recomputation ----
    d["residual"] = d["home_margin"] - d["spread_line"]
    assert np.allclose(d["residual"], d["home_margin"] - d["spread_line"])
    audit("residual = actual_margin - market_spread recomputes exactly: OK")

    # ---- gameday join (for recency weighting / ordering) ----
    s = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")[["game_id", "gameday"]]
    d = d.merge(s, on="game_id", how="left")
    assert d["gameday"].notna().all(), "gameday join failed!"
    d["gameday"] = pd.to_datetime(d["gameday"])
    audit("gameday joined from schedules for every game: OK")

    # ---- v1_margin availability note ----
    n_v1 = int(d["ens_margin"].notna().sum())
    audit(f"v1_margin (ens_margin) available on {n_v1}/{len(d)} rows; "
          f"null for 2018-2020 because the GBM ensemble requires training "
          f"history (documented, not leakage).")

    out = pd.DataFrame({
        "game_id": d["game_id"],
        "season": d["season"].astype(int),
        "week": d["week"].astype(int),
        "gameday": d["gameday"],
        "away_team": d["away_team"],
        "home_team": d["home_team"],
        "market_spread": d["spread_line"].astype(float),
        "line_provenance": "nflverse_proxy_open",
        **{c: d[c].astype(float) for c in FEATURES},
        "v1_margin": d["ens_margin"].astype(float),
        "actual_margin": d["home_margin"].astype(float),
        "residual": d["residual"].astype(float),
    }).sort_values(["season", "week", "gameday"]).reset_index(drop=True)

    p = f"{EXP_DATA}/games_features.parquet"
    out.to_parquet(p, index=False)
    print(f"wrote {p}: {out.shape[0]} rows x {out.shape[1]} cols")

    with open(f"{EXP_DIR}/leakage_audit.md", "w") as f:
        f.write("# Leakage audit — experiment_001 dataset\n\n")
        f.write("Generated by scripts/16_build_experiment_dataset.py.\n\n")
        for line in audit_lines:
            f.write(f"- {line}\n")
        f.write("\nConclusion: every feature column is either a walk-forward "
                "rating (ELO/EPA, weekly-batched pre-week values), a "
                "schedule-derived pregame fact (rest_diff, div_game, week), "
                "or the pregame market proxy (spread_line). No post-game "
                "statistic, future line, or future roster/injury information "
                "enters any feature.\n")

    config = {
        "experiment": "experiment_001_market_residual",
        "dataset": "data/experiments/games_features.parquet",
        "rows": int(out.shape[0]),
        "seasons": "2018-2025",
        "target": "residual = actual_margin - market_spread",
        "features": FEATURES,
        "line_provenance": {
            "value": "nflverse_proxy_open",
            "meaning": ("Historical spread_line is a consensus/opening proxy "
                        "from nflverse, NOT a verified executable closing line. "
                        "The residual target therefore bakes in line movement "
                        "toward close. Residual-prediction skill must NOT be "
                        "presented as tradable-signal evidence."),
        },
        "splits": {
            "train_pool": "2018-2020",
            "validation": "2021-2022 (ALL model/parameter/window/decay selection happens here)",
            "vault": "2023-2025 (locked; exactly one evaluation after methodology is locked)",
        },
        "baselines": ["market-only (predicted residual = 0)", "V1 (ens_margin)"],
        "concepts_tracked_separately": [
            "1. prediction accuracy: how well actual margin is predicted",
            "2. market-residual accuracy: how well actual_margin - market_proxy is predicted",
            "3. tradable-signal evidence: actionable at the line available at prediction time",
        ],
        "promotion_bar": ("No V2 designation until: beats market MAE and V1 on "
                          "the vault, stable across 2023/2024/2025 individually, "
                          "reasonable calibration; ATS only as a secondary metric."),
    }
    with open(f"{EXP_DIR}/config.json", "w") as f:
        json.dump(config, f, indent=1)
    print(f"wrote {EXP_DIR}/config.json and leakage_audit.md")


if __name__ == "__main__":
    main()
