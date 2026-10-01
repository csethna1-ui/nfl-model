#!/usr/bin/env python3
"""Step 24: Grade the information-timing study week (Experiment 006).

OBSERVATIONAL ONLY. Joins Tuesday + Friday snapshots with final scores and
CLV. No model fitting, no tuning, no inference.

Usage:
    ./venv/bin/python scripts/24_timing_grade.py --season 2026 --week 5

Reads:
    data/timing_study/tuesday_2026_w{N}.csv
    data/timing_study/friday_2026_w{N}.csv
    data/schedules_2018_2025.parquet   (final scores)
    data/clv_picks.csv                 (eventual CLV per graded pick)

Excludes: games already played at Friday capture (Thursday games), games
without final scores yet, and Friday rows missing model/market numbers.
Re-running replaces the week's rows (idempotent).

Appends: data/timing_study/graded.csv
Prints a small descriptive summary. Small samples: DO NOT INFER.
"""
import argparse
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
TS = f"{DATA}/timing_study"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    args = ap.parse_args()
    S, W = args.season, args.week

    tue_p = f"{TS}/tuesday_{S}_w{W}.csv"
    fri_p = f"{TS}/friday_{S}_w{W}.csv"
    for p in (tue_p, fri_p):
        if not os.path.exists(p):
            raise SystemExit(f"missing {p}: run the Tuesday/Friday snapshots first")

    tue = pd.read_csv(tue_p)
    fri = pd.read_csv(fri_p)
    sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    played = sched[(sched["season"] == S) & (sched["week"] == W)
                   & sched["home_score"].notna()][
        ["game_id", "home_score", "away_score"]].copy()
    if played.empty:
        raise SystemExit(f"no completed games yet for {S} week {W}")
    played["actual_margin"] = played["home_score"] - played["away_score"]

    clv = pd.read_csv(f"{DATA}/clv_picks.csv") if os.path.exists(
        f"{DATA}/clv_picks.csv") else pd.DataFrame()

    df = (tue.merge(fri, on=["game_id", "game", "season", "week"],
                    suffixes=("", "_f"), how="inner")
             .merge(played, on="game_id", how="inner"))
    df = df[df["already_played"] == 0].copy()  # Thursday games excluded
    if not clv.empty:
        c = clv[(clv["season"] == S) & (clv["week"] == W)][["game", "clv_pts"]]
        df = df.merge(c, on="game", how="left")

    def num(s):
        return pd.to_numeric(s, errors="coerce")

    df["tue_model_err"] = (num(df["model_spread_tue"]) - df["actual_margin"]).abs()
    df["fri_model_err"] = (num(df["model_spread_fri"]) - df["actual_margin"]).abs()
    df["tue_market_err"] = (num(df["market_spread_tue"]) - df["actual_margin"]).abs()
    df["fri_market_err"] = (num(df["market_spread_fri"]) - df["actual_margin"]).abs()
    df["model_move"] = num(df["model_spread_fri"]) - num(df["model_spread_tue"])
    df["market_move"] = num(df["market_spread_fri"]) - num(df["market_spread_tue"])
    df["graded_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    keep = ["season", "week", "game_id", "game", "kickoff_et", "actual_margin",
            "model_spread_tue", "model_spread_fri",
            "market_spread_tue", "market_spread_fri",
            "tue_model_err", "fri_model_err", "tue_market_err", "fri_market_err",
            "model_move", "market_move",
            "elo_diff_tue", "elo_diff_fri",
            "spread_pick_final", "void_reason", "qb_news_fri",
            "clv_pts", "timing_flag", "graded_at"]
    out = df[[c for c in keep if c in df.columns]].copy()

    gp = f"{TS}/graded.csv"
    if os.path.exists(gp):
        g = pd.read_csv(gp)
        g = g[~((g["season"] == S) & (g["week"] == W))]
        g = pd.concat([g, out], ignore_index=True)
    else:
        g = out
    g.to_csv(gp, index=False)

    # ---- descriptive summary only ----
    n = len(out)
    print(f"graded {S} week {W}: {n} games "
          f"({int(df['market_tue_missing'].sum())} missing Tuesday market)")
    for label, col in [("Tue model MAE", "tue_model_err"),
                       ("Fri model MAE", "fri_model_err"),
                       ("Tue market MAE", "tue_market_err"),
                       ("Fri market MAE", "fri_market_err")]:
        v = pd.to_numeric(out[col], errors="coerce").dropna()
        print(f"  {label}: {v.mean():.2f} (n={len(v)})" if len(v) else f"  {label}: n/a")
    mm = pd.to_numeric(out["model_move"], errors="coerce").dropna()
    km = pd.to_numeric(out["market_move"], errors="coerce").dropna()
    if len(mm):
        print(f"  mean |model Tue->Fri move|: {mm.abs().mean():.2f}")
    if len(km):
        print(f"  mean |market Tue->Fri move|: {km.abs().mean():.2f}")
    print("OBSERVATIONAL ONLY — do not infer from small samples.")


if __name__ == "__main__":
    main()
