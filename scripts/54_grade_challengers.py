#!/usr/bin/env python3
"""Step 54: Grade champion + live challengers for a completed week.

Usage:
    ./venv/bin/python scripts/54_grade_challengers.py --season 2026 --week 4

Grades every model with a prediction file for the week — the champion
(data/predictions_<S>_w<W>.csv, RAW model_spread, no QB overlay) and each
live challenger (data/challengers/<name>/predictions_<S>_w<W>.csv) — on
identical rules: SU winner, ATS vs the same market lines, and margin MAE.
Appends one row per model to data/challenger_ledger.csv (idempotent per
week) and prints the head-to-head vs the champion plus cumulative standings.

The promotion bar in docs/CHALLENGER_CHARTER.md is PROPOSED until Cale
ratifies it; this script reports standings against it but changes nothing.
"""
import argparse
import json
import os

import pandas as pd

DATA = "/home/hatch/workspace/nfl-model/data"
REGISTRY = "/home/hatch/workspace/nfl-model/challengers/registry.json"
LEDGER = f"{DATA}/challenger_ledger.csv"


def grade(pred_path, finals, week):
    preds = pd.read_csv(pred_path)
    su_w = su_l = ats_w = ats_l = ats_p = 0
    errs = []
    n = 0
    for _, p in preds.iterrows():
        if pd.isna(p["model_spread"]):
            continue
        away, home = p["game"].split(" @ ")
        g = finals[(finals["week"] == week) & (finals["away_team"] == away)
                   & (finals["home_team"] == home)]
        if g.empty:
            continue
        g = g.iloc[0]
        am = float(g["away_score"]) - float(g["home_score"])
        m = float(p["model_spread"])
        n += 1
        errs.append(abs(-m - am))
        pw = home if m > 0 else away
        if pw == (away if am > 0 else home):
            su_w += 1
        else:
            su_l += 1
        if pd.notna(p["market_spread"]):
            L = float(p["market_spread"])
            s = am + L
            edge = m - L
            if edge == 0 or s == 0:
                ats_p += 1
            elif (edge < 0 and s > 0) or (edge > 0 and s < 0):
                ats_w += 1
            else:
                ats_l += 1
    return {"n": n, "su_w": su_w, "su_l": su_l, "ats_w": ats_w,
            "ats_l": ats_l, "ats_push": ats_p,
            "mae": round(float(pd.Series(errs).mean()), 3) if errs else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    args = ap.parse_args()
    S, W = args.season, args.week

    sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    finals = sched[(sched["season"] == S) & (sched["week"] == W)
                   & sched["home_score"].notna()].copy()
    if finals.empty:
        print(f"no completed games yet for {S} week {W}")
        return

    with open(REGISTRY) as f:
        registry = json.load(f)
    models = [("champion_v1", f"{DATA}/predictions_{S}_w{W}.csv")]
    for name, cfg in registry.items():
        if cfg["status"] == "live":
            p = f"{DATA}/challengers/{name}/predictions_{S}_w{W}.csv"
            if os.path.exists(p):
                models.append((name, p))
            else:
                print(f"note: {name} has no prediction file for w{W}, skipped")

    rows = []
    for name, path in models:
        g = grade(path, finals, W)
        rows.append({"season": S, "week": W, "model": name, **g})
    week_df = pd.DataFrame(rows)
    print(week_df.to_string(index=False))

    ledger = pd.read_csv(LEDGER) if os.path.exists(LEDGER) else pd.DataFrame()
    if len(ledger):
        ledger = ledger[~((ledger["season"] == S) & (ledger["week"] == W))]
    ledger = pd.concat([ledger, week_df], ignore_index=True)
    ledger.to_csv(LEDGER, index=False)

    # cumulative standings vs champion + ratified promotion-bar check
    print("\nCumulative (all graded weeks):")
    cum = ledger.groupby("model").agg(
        n=("n", "sum"), su_w=("su_w", "sum"), su_l=("su_l", "sum"),
        ats_w=("ats_w", "sum"), ats_l=("ats_l", "sum"))
    cum["mae"] = ledger.groupby("model").apply(
        lambda d: round((d["mae"] * d["n"]).sum() / d["n"].sum(), 3),
        include_groups=False)
    champ = cum.loc["champion_v1"]
    c_su = champ["su_w"] / max(champ["su_w"] + champ["su_l"], 1)
    c_ats = champ["ats_w"] / max(champ["ats_w"] + champ["ats_l"], 1)
    cleared = []
    for name in cum.index:
        r = cum.loc[name]
        flag = " [CHAMPION]" if name == "champion_v1" else ""
        d_mae = r["mae"] - champ["mae"]
        line = (f"  {name}{flag}: n={int(r['n'])} "
                f"SU {int(r['su_w'])}-{int(r['su_l'])} "
                f"ATS {int(r['ats_w'])}-{int(r['ats_l'])} "
                f"MAE {r['mae']:.3f} (Δ {d_mae:+.3f} vs champ)")
        if name != "champion_v1":
            n = int(r["n"])
            s_su = r["su_w"] / max(r["su_w"] + r["su_l"], 1)
            s_ats = r["ats_w"] / max(r["ats_w"] + r["ats_l"], 1)
            bar = (n >= 100 and (champ["mae"] - r["mae"]) >= 0.30
                   and s_ats > c_ats and s_su >= c_su)
            line += (f"  << PROMOTION BAR CLEARED — needs Cale's tap to crown >>"
                     if bar else f"  (bar: {n}/100 games"
                     f"{'' if n >= 100 else ', not eligible'}"
                     f"{'; MAE edge too small' if n >= 100 and (champ['mae'] - r['mae']) < 0.30 else ''}"
                     f"{'; ATS not better' if n >= 100 and not s_ats > c_ats else ''}"
                     f"{'; SU worse' if n >= 100 and not s_su >= c_su else ''})")
            if bar:
                cleared.append(name)
        print(line)
    print("\nPromotion bar: RATIFIED 2026-10-01 (docs/CHALLENGER_CHARTER.md).")
    if cleared:
        print(f"*** {', '.join(cleared)} CLEARED THE BAR — report to Cale; "
              "title change needs his explicit tap, never auto-promote. ***")
    print(f"saved {LEDGER}")


if __name__ == "__main__":
    main()
