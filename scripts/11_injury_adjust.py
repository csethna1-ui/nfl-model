#!/usr/bin/env python3
"""Step 11: QB availability overlay — "show adjusted, don't void".

Policy (2026-10-01, Cale's call): the pipeline no longer auto-voids picks
when a starting QB is out. Instead it SHOWS the backup-adjusted prediction
alongside the frozen V1 number, so the QB overlay explains the prediction
rather than rewriting the model's historical output. This keeps later
backtesting clean: raw vs adjusted are recorded separately, so we can test
whether the adjustment adds information instead of inadvertently changing
the frozen V1 dataset.

Pipeline stages per game:
    V1 raw (frozen, never altered)
      -> Expected QB (current availability state)
      -> QB adjustment (experimental overlay, market-implied point value)
      -> Adjusted prediction (derived, labeled experimental)
      -> Market (current line)
      -> Raw edge vs Adjusted edge
      -> Final status (PICK / NO PLAY / VETOED)

Decision logic:
  * No QB change: final = raw V1 decision (|raw_edge| >= thresh -> PICK).
  * QB change, raw pick NOT on the downgraded team (or no raw pick): the
    overlay is shown but changes nothing. The delta can only REMOVE picks,
    never create or flip them.
  * QB change, raw pick ON the downgraded team: apply the STALE-QB VETO
    check. If the market confirms the QB-adjusted number
    (|adj_spread - market| <= veto_band), the raw "edge" was stale QB news
    (V1's rating was built on the starter; the market priced the backup) and
    the pick is vetoed to "no play" — transparently, with every number shown.
    If the market does NOT confirm it, the disagreement is about team
    strength, not the QB: the raw pick stands, flagged.

QB_ADJUSTMENT_DOUBLE_COUNT_RISK: TRUE when the replacement QB has already
started a game for this team in the sample feeding V1's current ratings
(PBP-derived). The backup's performance is then already in the team rating,
so the mechanical full-value shift double-counts — treat the adjusted number
as the conservative bound and the raw number as the aggressive bound.

QB-state precedence per (game, side): manual qb_news > expected-QB recorder
(29, v2 rule) > frozen injury-state auto entries. Manual always wins; the
feed lags breaking news.

Usage:
    ./venv/bin/python scripts/11_injury_adjust.py --season 2026 --week 4 \
        --predictions-csv data/predictions_2026_w4.csv \
        --market-json data/market_2026_w4.json \
        --injury-state data/injuries/availability_friday_2026_w4.json \
        --expected-qb data/qb_expectations/qb_expected_2026_w4.parquet

Updates the predictions CSV in place, adding: expected_qb_home,
expected_qb_away, qb_change_side, qb_change_note, qb_shift_pts,
qb_double_count_risk, qb_news, model_spread_adj, edge_adj, stale_qb_veto,
spread_pick_final, void_reason. Every disposition is appended to
data/injuries/logs/void_disposition.jsonl with action in
{keep, vetoed, noted}.
"""
import argparse
import json
import os
import sys

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
from injury_lib import append_log, resolve_backup_qb

DATA = os.path.join(REPO_ROOT, "data")
TRIGGER = {"out", "doubtful"}
MARKET_CONFIRM_BAND = 1.0  # judgment parameter: |adj - market| <= band means
                           # the market confirms the QB-adjusted number


def load_qb_values():
    with open(f"{DATA}/qb_point_values.json") as f:
        raw = json.load(f)
    meta = raw["_meta"]
    vals = {}
    for team, d in raw["teams"].items():
        v = float(d["value"])
        v = max(meta["floor"], min(meta["cap"], v))
        vals[team] = {"qb1": d["qb1"], "value": v, "source": d["source"]}
    return vals, meta


def last_name(name):
    return str(name).replace(".", " ").split()[-1].lower() if str(name).strip() else ""


def feed_out_from_availability(avail):
    """{team: [(name, report_status), ...]} for starting QBs Out/Doubtful."""
    out = {}
    for e in avail.get("starting_qb_flags", []):
        st = str(e.get("report_status") or "").lower()
        if st in TRIGGER and e.get("triggers_void"):
            out.setdefault(e["team"], []).append((e["player"], e["report_status"]))
    return out


def cross_check_injuries(season, week, qb_news, avail=None):
    """Compare manual qb_news against the nflverse injury feed. Manual news
    always wins; the feed lags breaking news."""
    warns = []
    if avail is not None:
        feed_out = feed_out_from_availability(avail)
    else:
        try:
            import nfl_data_py as nfl
            inj = nfl.import_injuries([season])
        except Exception as e:
            return [f"injury feed unavailable ({e}); relying on manual qb_news only"]
        wk = inj[(inj["week"] == week) & (inj["position"] == "QB")]
        feed_out = {}
        for _, r in wk.iterrows():
            st = str(r.get("report_status", "")).lower()
            if st in TRIGGER:
                feed_out.setdefault(r["team"], []).append(
                    (r["full_name"], r["report_status"]))
    news_teams = set()
    for key, sides in qb_news.items():
        a, h = key.split("_")
        for side, team in (("away", a), ("home", h)):
            if side in sides and str(sides[side].get("status", "")).lower() in TRIGGER:
                news_teams.add(team)
    for team, lst in sorted(feed_out.items()):
        if team not in news_teams:
            names = ", ".join(f"{n} ({s})" for n, s in lst)
            warns.append(f"FEED: {team} QB {names} Out/Doubtful but not in "
                         f"qb_news — check this game before publishing")
    for team in sorted(news_teams):
        if team not in feed_out:
            warns.append(f"NEWS: {team} QB change in qb_news but not yet on the "
                         f"official report — breaking news, feed lags (expected)")
    return warns


def build_auto_qb_news(avail, team_side, week):
    """qb_news-shaped entries from the automated availability state (legacy
    fallback; the expected-QB recorder is now the primary automated source)."""
    auto = {}
    as_of = avail.get("as_of", "?")
    for e in avail.get("starting_qb_flags", []):
        if int(e.get("week", -1)) != week:
            continue
        st = str(e.get("report_status") or "").lower()
        if st not in TRIGGER and st != "questionable":
            continue
        team = e["team"]
        if team not in team_side:
            continue
        key, side = team_side[team]
        backup = resolve_backup_qb(team, e["player"])
        entry = {"status": st, "starter": e["player"], "backup": backup,
                 "note": (f"auto from nflverse snapshot as_of {as_of}; "
                          f"{e.get('primary_injury') or 'no injury listed'}"),
                 "_source": "auto"}
        auto.setdefault(key, {})[side] = entry
    return auto


def build_recorder_qb_news(qb_df, team_side, week):
    """qb_news-shaped entries from the expected-QB recorder (29, v2 rule).
    A team whose expected QB is a backup yields a trigger entry; a
    questionable QB1 yields a note-only entry."""
    rec = {}
    wk = qb_df[qb_df["week"] == week]
    for _, r in wk.iterrows():
        team = r["team"]
        if team not in team_side:
            continue
        key, side = team_side[team]
        if r["starter_or_backup"] == "backup":
            st = str(r["qb1_report_status"] or "out").lower()
            entry = {"status": st if st in TRIGGER else "out",
                     "starter": r["qb1_name"],
                     "backup": r["expected_qb_name"],
                     "starter_gsis": r.get("qb1_gsis_id"),
                     "note": (f"expected-QB recorder v2: {r['qb1_name']} "
                              f"({r['qb1_report_status'] or 'unavailable'}, "
                              f"report week {r['qb_status_week']}) -> "
                              f"{r['expected_qb_name']}"),
                     "_source": "recorder"}
            rec.setdefault(key, {})[side] = entry
        elif str(r["qb1_report_status"]).lower() == "questionable":
            entry = {"status": "questionable", "starter": r["qb1_name"],
                     "backup": r["expected_qb_name"],
                     "note": "expected-QB recorder v2: QB1 questionable "
                             "(no action — plays through tag most weeks)",
                     "_source": "recorder"}
            rec.setdefault(key, {})[side] = entry
    return rec


def merge_qb_news(manual, recorder, auto):
    """Precedence per (game_key, side): manual > recorder > auto."""
    merged = {}
    for key, sides in auto.items():
        merged[key] = {s: dict(v) for s, v in sides.items()}
    for key, sides in recorder.items():
        for side, info in sides.items():
            merged.setdefault(key, {})[side] = dict(info)
    for key, sides in manual.items():
        for side, info in sides.items():
            info = dict(info)
            info["_source"] = "manual"
            merged.setdefault(key, {})[side] = info
    return merged


def load_weekly_starters(season, week):
    """{(team, week): passer name} for played weeks < `week`, derived from
    the PBP cache: the passer with the most pass plays per team-week. This
    is the same game sample feeding V1's current ratings (07 refreshes the
    cache before this step runs)."""
    import pandas as pd
    cols = ["season", "week", "posteam", "passer_player_name", "play_type"]
    p = pd.read_parquet(f"{DATA}/pbp_players_2018_2026.parquet", columns=cols)
    p = p[(p["season"] == season) & (p["week"] < week)
          & p["passer_player_name"].notna()
          & (p["play_type"] == "pass")]
    if p.empty:
        return {}
    s = (p.groupby(["posteam", "week", "passer_player_name"]).size()
           .reset_index(name="n")
           .sort_values(["posteam", "week", "n"], ascending=[True, True, False]))
    return {(r["posteam"], int(r["week"])): r["passer_player_name"]
            for _, r in s.groupby(["posteam", "week"]).first().reset_index()
            .iterrows()}


def double_count_risk(team, backup_name, starters, season, week):
    """QB_ADJUSTMENT_DOUBLE_COUNT_RISK: TRUE when the replacement QB has
    already started a game for this team in the sample feeding V1's current
    ratings (played weeks < `week`, PBP-derived). The backup's performance is
    then already inside the team rating, so the mechanical full-value shift
    double-counts: the adjusted number is the conservative bound, raw V1 the
    aggressive bound."""
    bn = last_name(backup_name)
    if not bn:
        return False
    for w in range(1, week):
        if last_name(starters.get((team, w), "")) == bn:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--predictions-csv", required=True)
    ap.add_argument("--market-json", required=True)
    ap.add_argument("--injury-state", default=None,
                    help="frozen availability JSON (legacy automated source)")
    ap.add_argument("--expected-qb", default=None,
                    help="expected-QB recorder parquet (29); primary "
                         "automated QB-state source")
    ap.add_argument("--veto-band", type=float, default=MARKET_CONFIRM_BAND,
                    help="|adj_spread - market| <= band means the market "
                         "confirms the QB-adjusted number (stale-QB veto)")
    args = ap.parse_args()

    with open(f"{DATA}/ensemble_params.json") as f:
        thresh = float(json.load(f)["op_spread_thresh"])
    qb_vals, _ = load_qb_values()

    pred = pd.read_csv(args.predictions_csv)
    with open(args.market_json) as f:
        market = json.load(f)
    manual_news = market.get("qb_news", {})

    avail = None
    if args.injury_state and os.path.exists(args.injury_state):
        with open(args.injury_state) as f:
            avail = json.load(f)

    qb_df = None
    if args.expected_qb and os.path.exists(args.expected_qb):
        qb_df = pd.read_parquet(args.expected_qb)

    starters = load_weekly_starters(args.season, args.week)

    def key_of(game):
        a, h = [t.strip() for t in game.split("@")]
        return f"{a}_{h}"

    pred["_key"] = pred["game"].map(key_of)
    by_key = {k: i for i, k in enumerate(pred["_key"])}
    team_side = {}
    for k in by_key:
        a, h = k.split("_")
        team_side[a] = (k, "away")
        team_side[h] = (k, "home")

    auto_news = build_auto_qb_news(avail, team_side, args.week) if avail else {}
    rec_news = build_recorder_qb_news(qb_df, team_side, args.week) \
        if qb_df is not None else {}
    qb_news = merge_qb_news(manual_news, rec_news, auto_news)

    # expected QB per team for display (all 32, from the recorder when given)
    exp_qb = {}
    if qb_df is not None:
        for _, r in qb_df[qb_df["week"] == args.week].iterrows():
            exp_qb[r["team"]] = r["expected_qb_name"]

    warns = cross_check_injuries(args.season, args.week, qb_news, avail=avail)
    n_rec = sum(1 for s in qb_news.values() for v in s.values()
                if v.get("_source") == "recorder")
    n_auto = sum(1 for s in qb_news.values() for v in s.values()
                 if v.get("_source") == "auto")
    if args.expected_qb:
        warns.append(f"RECORDER: {n_rec} QB entries from expected-QB v2 "
                     f"({args.expected_qb}); manual qb_news wins on conflict")
    if args.injury_state:
        warns.append(f"AUTO: {n_auto} entries from frozen injury state "
                     f"(fallback only)")

    # ---- fresh overlay columns (reset every run; V1 raw untouched) ----
    for col, default in [("expected_qb_home", ""), ("expected_qb_away", ""),
                         ("qb_change_side", ""), ("qb_change_note", ""),
                         ("qb_shift_pts", 0.0), ("qb_double_count_risk", False),
                         ("qb_news", ""), ("model_spread_adj", None),
                         ("edge_adj", None), ("stale_qb_veto", False),
                         ("spread_pick_final", None), ("void_reason", "")]:
        pred[col] = default
    pred["model_spread_adj"] = pred["model_spread"]
    pred["edge_adj"] = pred["edge"]
    pred["spread_pick_final"] = pred["spread_pick"]

    report = []
    for key, sides in qb_news.items():
        if key not in by_key:
            report.append(f"{key}: qb_news entry but no such game in predictions — skipped")
            continue
        i = by_key[key]
        away, home = key.split("_")
        row = pred.iloc[i]
        v1 = float(row["model_spread"])
        mkt = float(row["market_spread"]) if pd.notna(row["market_spread"]) else None
        raw_edge = float(row["edge"]) if pd.notna(row["edge"]) else 0.0
        raw_pick = str(row["spread_pick"])

        pred.at[i, "expected_qb_home"] = exp_qb.get(home, "")
        pred.at[i, "expected_qb_away"] = exp_qb.get(away, "")

        notes, events = [], []
        shift = 0.0
        changed_sides = []
        for side, team in (("away", away), ("home", home)):
            info = sides.get(side)
            if not info:
                continue
            status = str(info.get("status", "")).lower()
            starter = info.get("starter", "?")
            backup = info.get("backup", "?")
            src = info.get("_source", "manual")
            s_sign = 1 if side == "home" else -1  # home-spread space
            if status in TRIGGER:
                val = qb_vals.get(team, {"value": 4.0, "source": "default"})["value"]
                shift += -s_sign * val
                dcr = double_count_risk(team, backup, starters,
                                        args.season, args.week)
                events.append({"side": side, "team": team, "s_sign": s_sign,
                               "starter": starter, "backup": backup,
                               "status": status,
                               "value": val, "source": src,
                               "double_count_risk": dcr})
                changed_sides.append(side)
                # The expected QB for a changed side is the backup: manual
                # qb_news (breaking news the recorder hasn't seen) wins over
                # the recorder's expectation for display, not just for the
                # shift math.
                pred.at[i, f"expected_qb_{side}"] = backup
                notes.append(f"{team} {side} QB {status.upper()}: {starter} -> "
                             f"{backup} (shift {val:.1f} pts) [{src}]"
                             + (" DOUBLE-COUNT RISK" if dcr else ""))
            elif status == "questionable":
                notes.append(f"{team} {side} QB QUESTIONABLE: {starter} "
                             f"(no action) [{src}]")
            else:
                notes.append(f"{team} {side} QB note: {starter} ({status}) [{src}]")

        adj = round(v1 + shift, 1)
        pred.at[i, "qb_news"] = "; ".join(notes)
        pred.at[i, "model_spread_adj"] = adj
        if mkt is not None:
            pred.at[i, "edge_adj"] = round(adj - mkt, 1)
        if changed_sides:
            pred.at[i, "qb_change_side"] = "+".join(changed_sides)
            pred.at[i, "qb_change_note"] = "; ".join(notes)
            pred.at[i, "qb_shift_pts"] = round(shift, 1)
            pred.at[i, "qb_double_count_risk"] = any(
                e["double_count_risk"] for e in events)

        # ---- stale-QB veto (replaces the old auto-void) ----
        vetoed = False
        adj_edge = (adj - mkt) if mkt is not None else None
        if events and raw_pick != "no play" and mkt is not None:
            pick_on_downgraded = any(
                e["s_sign"] * raw_edge >= thresh for e in events)
            market_confirms = abs(adj - mkt) <= args.veto_band
            if pick_on_downgraded and market_confirms:
                vetoed = True
                pred.at[i, "stale_qb_veto"] = True
                pred.at[i, "spread_pick_final"] = "no play"
                rsn = "; ".join(f"{e['team']} {e['starter']} -> {e['backup']}"
                                for e in events)
                pred.at[i, "void_reason"] = (
                    f"VETOED — market confirms QB-adjusted number "
                    f"(|{adj:.1f} - ({mkt:+.1f})| <= {args.veto_band}); "
                    f"raw edge {raw_edge:+.1f} was stale QB news: {rsn}")
                report.append(f"{key}: VETOED {raw_pick} "
                              f"(raw edge {raw_edge:+.1f} -> adj "
                              f"{adj_edge:+.1f}; market {mkt:+.1f} confirms adj)")
        if events and not vetoed:
            action = "keep" if raw_pick != "no play" else "noted"
            ae = f"{adj_edge:+.1f}" if adj_edge is not None else "n/a"
            if raw_pick != "no play":
                dcr_note = (" [DOUBLE-COUNT RISK: adj understates]"
                            if pred.at[i, "qb_double_count_risk"] else "")
                report.append(f"{key}: KEEP {raw_pick} "
                              f"(raw edge {raw_edge:+.1f}, adj edge {ae})"
                              f"{dcr_note}")
            else:
                report.append(f"{key}: no raw pick; QB overlay shown only "
                              f"(raw edge {raw_edge:+.1f}, adj {ae})")
        for e in events:
            append_log("void_disposition",
                       {"season": args.season, "week": args.week, "game": key,
                        "side": e["side"], "team": e["team"],
                        "player": e["starter"], "status": e["status"],
                        "backup": e["backup"], "source": e["source"],
                        "action": ("vetoed" if vetoed
                                   else ("keep" if raw_pick != "no play"
                                         else "noted")),
                        "v1_spread": round(v1, 1),
                        "qb_shift_pts": round(shift, 1),
                        "adj_spread": adj,
                        "market_spread": mkt,
                        "edge_before": round(raw_edge, 1),
                        "edge_after": (round(adj_edge, 1)
                                       if adj_edge is not None else None),
                        "double_count_risk": bool(e["double_count_risk"]),
                        "stale_qb_veto": bool(vetoed)})

    # games with no QB news still get expected QBs for display
    for k, i in by_key.items():
        a, h = k.split("_")
        if not pred.at[i, "expected_qb_home"]:
            pred.at[i, "expected_qb_home"] = exp_qb.get(h, "")
        if not pred.at[i, "expected_qb_away"]:
            pred.at[i, "expected_qb_away"] = exp_qb.get(a, "")

    pred = pred.drop(columns=["_key"])
    pred.to_csv(args.predictions_csv, index=False)

    print("=" * 64)
    print(f"QB AVAILABILITY OVERLAY — {args.season} week {args.week} "
          f"(threshold {thresh:.1f}, veto band {args.veto_band})")
    print("show adjusted, don't void: V1 raw frozen; overlay is experimental")
    print("=" * 64)
    if warns:
        print("\n-- cross-check warnings --")
        for w in warns:
            print("  !", w)
    else:
        print("\n-- cross-check: sources agree --")
    print("\n-- dispositions --")
    if report:
        for r in report:
            print("  *", r)
    else:
        print("  * no QB changes affecting games")
    n_veto = int(pred["stale_qb_veto"].sum())
    n_picks = int((pred["spread_pick_final"] != "no play").sum())
    n_dcr = int(pred["qb_double_count_risk"].sum())
    print(f"\nresult: {n_picks} live picks, {n_veto} vetoed (stale QB), "
          f"{n_dcr} games with double-count risk flagged")
    print(f"updated {args.predictions_csv}")


if __name__ == "__main__":
    main()
