#!/usr/bin/env python3
"""Step 28: persistent per-week injury/QB-overlay audit table.

Answers: "What exactly did the system know, and what did the QB overlay do?"
Runs in the Friday flow AFTER the overlay layer (11_injury_adjust.py).

Reads:
  - data/injuries/availability_friday_{season}_w{week}.json  (frozen cutoff
    state; required on Fridays, see --no-freeze for mid-week re-runs)
  - data/market_{season}_w{week}.json                         (qb_news manual state)
  - data/qb_expectations/qb_expected_{season}_w{week}.parquet (recorder v2)
  - data/injuries/logs/void_disposition.jsonl                (overlay dispositions;
    legacy pre-2026-10-01 void/survive records are excluded)

Writes:
  - data/injuries/audit/audit_{season}_w{week}.parquet       (refuses to overwrite)

QB-state precedence per (game, side) — identical to the overlay layer:
manual qb_news > expected-QB recorder (29, v2) > frozen feed auto entries.

Columns:
  game_id | player | team | role | automated_status | recorder_status |
  manual_status | final_status | expected_qb | first_seen_at |
  recorder_captured_at | prediction_cutoff | overlay_action | void_triggered |
  override_used | source | qb_shift_pts | adj_spread | edge_before |
  edge_after | double_count_risk | stale_qb_veto

Definitions:
  role: expected_starter | backup | other. From the frozen availability's
    is_expected_starter flag; manual/recorder/dispo-only rows cross-check the
    named starter against the qb1 list (expected_starter on last-name match,
    else backup — an auditable discrepancy, never a reason to hide the row).
  overlay_action: the disposition the overlay layer logged for this
    game/team/player: keep | vetoed | noted (None when the overlay logged
    nothing — e.g. a feed-only questionable note).
  void_triggered: legacy name kept for cross-week continuity. TRUE when
    final_status is in the trigger set (OUT/DOUBTFUL) AND overlay_action is
    "vetoed" — i.e. the stale-QB veto removed a live pick. (Before 2026-10-01
    this meant the old auto-void's action=void.)
  override_used: True when the winning source's status differs from a
    lower-precedence source's status (a genuine conflict the precedence rule
    resolved). A higher source filling a lower source's gap is not an
    override.
  source: "+"-joined contributing sources among auto/recorder/manual, e.g.
    "manual", "recorder", "manual+recorder".
  first_seen_at: provenance for OUR feed snapshots only — earliest snapshot
    pulled_at whose row for this player-week carried automated_status. NOT
    when the market learned it (that's the PFT branch's job). Null for
    manual/recorder-only rows.
  Numeric overlay columns (qb_shift_pts, adj_spread, edge_before, edge_after,
    double_count_risk, stale_qb_veto) come from the disposition log; null
    when the overlay logged nothing for the row.

Usage:
    ./venv/bin/python scripts/28_injury_audit.py --season 2026 --week 5
    # mid-week re-run without a Friday freeze (cutoff recorded honestly):
    ./venv/bin/python scripts/28_injury_audit.py --season 2026 --week 4 --no-freeze
"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
from injury_lib import (ensure_dirs, friday_path, append_log, norm_status,
                        load_qb1)

DATA = os.path.join(REPO_ROOT, "data")
INJ_DIR = f"{DATA}/injuries"
AUDIT_DIR = f"{INJ_DIR}/audit"
TRIGGER = {"OUT", "DOUBTFUL"}

COLUMNS = ["game_id", "player", "team", "role", "automated_status",
           "recorder_status", "manual_status", "final_status", "expected_qb",
           "first_seen_at", "recorder_captured_at", "prediction_cutoff",
           "overlay_action", "void_triggered", "override_used", "source",
           "qb_shift_pts", "adj_spread", "edge_before", "edge_after",
           "double_count_risk", "stale_qb_veto"]


def last_name(name):
    parts = re.sub(r"[^A-Za-z ]", " ", str(name)).split()
    return parts[-1].lower() if parts else ""


def up(s):
    s = norm_status(s)
    return s.upper() if s else None


def load_snapshots_index():
    """[(day, pulled_at, df), ...] sorted by day. df is None if unloadable."""
    import pandas as pd
    out = []
    for p in sorted(glob.glob(f"{INJ_DIR}/snapshots/injuries_*.parquet")):
        day = os.path.basename(p)[len("injuries_"):-len(".parquet")]
        if day.endswith("-repull"):
            day = day[:-len("-repull")]
        try:
            df = pd.read_parquet(p)
            pulled = str(df["pulled_at"].iloc[0]) if "pulled_at" in df.columns and len(df) else None
            out.append((day, pulled or day, df))
        except Exception:
            out.append((day, day, None))
    return out


def first_seen_at(snaps, team, week, lname, status):
    """Earliest snapshot pulled_at where this player-week row carried `status`."""
    for _day, pulled_at, df in snaps:
        if df is None:
            continue
        wk = df[df["week"] == week]
        wk = wk[wk["team"] == team]
        if wk.empty:
            continue
        hit = wk[(wk["full_name"].map(last_name) == lname)
                 & (wk["report_status"].map(norm_status) == status.lower())]
        if not hit.empty:
            return pulled_at
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--freeze-path", default=None,
                    help="explicit frozen availability file (for smoke tests); "
                         "defaults to the production Friday freeze")
    ap.add_argument("--out", default=None,
                    help="explicit output path (for smoke tests); defaults to "
                         "data/injuries/audit/audit_{season}_w{week}.parquet")
    ap.add_argument("--expected-qb", default=None,
                    help="expected-QB recorder parquet; defaults to "
                         "data/qb_expectations/qb_expected_{season}_w{week}.parquet")
    ap.add_argument("--no-freeze", action="store_true",
                    help="mid-week re-run: proceed without a Friday freeze; "
                         "the cutoff is recorded as the run time, honestly "
                         "labeled. Never use this in the Friday flow.")
    args = ap.parse_args()
    ensure_dirs()
    os.makedirs(AUDIT_DIR, exist_ok=True)

    freeze = args.freeze_path or friday_path(args.season, args.week)
    avail = None
    if os.path.exists(freeze):
        with open(freeze) as f:
            avail = json.load(f)
        frozen_meta = avail.get("frozen_for_prediction", {})
        prediction_cutoff = frozen_meta.get("frozen_at") or avail.get("as_of")
        cutoff_note = "friday-freeze"
    elif args.no_freeze:
        prediction_cutoff = datetime.now(timezone.utc).isoformat()
        cutoff_note = "mid-week re-run, NO Friday freeze"
    else:
        raise SystemExit(f"frozen availability not found: {freeze} "
                         "(run 27_injury_diff.py --freeze-friday first, "
                         "or pass --no-freeze for a mid-week re-run)")

    market_path = f"{DATA}/market_{args.season}_w{args.week}.json"
    if not os.path.exists(market_path):
        raise SystemExit(f"market JSON not found: {market_path}")
    with open(market_path) as f:
        market = json.load(f)
    manual_news = market.get("qb_news", {})

    # team -> game_id from the market JSON (skip the qb_news key itself)
    team_game = {}
    for key in market:
        if key == "qb_news" or "_" not in key:
            continue
        a, h = key.split("_", 1)
        team_game[a] = key
        team_game[h] = key

    # ---- automated rows from the frozen state (this week only) ----
    auto = {}  # (game_id, team, lname) -> dict
    if avail:
        flags = [e for e in avail.get("starting_qb_flags", [])
                 if int(e.get("week", -1)) == args.week]
        for e in flags:
            team = e["team"]
            game = team_game.get(team)
            if not game:
                continue
            lname = last_name(e["player"])
            role = ("expected_starter" if e.get("is_expected_starter")
                    else ("backup" if e.get("position") == "QB" else "other"))
            auto[(game, team, lname)] = {
                "player": e["player"], "team": team, "role": role,
                "automated_status": up(e.get("report_status")),
            }
        for e in avail.get("notable_injuries", []):
            if int(e.get("week", -1)) != args.week:
                continue
            team = e["team"]
            game = team_game.get(team)
            if not game:
                continue
            lname = last_name(e["player"])
            key = (game, team, lname)
            if key in auto:
                continue
            auto[key] = {
                "player": e["player"], "team": team,
                "role": "backup" if e.get("position") == "QB" else "other",
                "automated_status": up(e.get("report_status")),
            }

    # ---- recorder rows: expected-QB v2 (primary automated QB source) ----
    import pandas as pd
    rec_path = (args.expected_qb or
                f"{DATA}/qb_expectations/qb_expected_{args.season}_w{args.week}.parquet")
    rec = {}       # (game_id, team, qb1_lname) -> dict
    exp_qb = {}    # team -> expected QB name (all 32)
    if os.path.exists(rec_path):
        qd = pd.read_parquet(rec_path)
        qd = qd[qd["week"] == args.week]
        for _, r in qd.iterrows():
            team = r["team"]
            exp_qb[team] = r["expected_qb_name"]
            game = team_game.get(team)
            if not game or r["starter_or_backup"] != "backup":
                continue
            st = up(r["qb1_report_status"]) or "OUT"
            rec[(game, team, last_name(r["qb1_name"]))] = {
                "player": r["qb1_name"], "team": team,
                "recorder_status": st,
                "recorder_captured_at": str(r.get("captured_at") or
                                           r.get("qb_status_as_of") or ""),
                "expected_qb": r["expected_qb_name"],
            }

    # ---- manual rows from qb_news ----
    manual = {}  # (game_id, team, lname) -> dict
    for key, sides in manual_news.items():
        if "_" not in key:
            continue
        a, h = key.split("_", 1)
        for side, team in (("away", a), ("home", h)):
            info = (sides or {}).get(side)
            if not info or not info.get("starter"):
                continue
            lname = last_name(info["starter"])
            manual[(key, team, lname)] = {
                "player": info["starter"],
                "manual_status": up(info.get("status")),
                "manual_note": str(info.get("note", ""))[:200],
            }

    # ---- overlay dispositions: latest record per (game, team, lname) ----
    # Only overlay-era records (those carrying the new schema's
    # "stale_qb_veto" key). Legacy pre-2026-10-01 actions ("void"/"survive")
    # stay in the JSONL for archaeology but are not overlay dispositions.
    dispo = {}
    dlog = f"{INJ_DIR}/logs/void_disposition.jsonl"
    if os.path.exists(dlog):
        with open(dlog) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("season") != args.season or r.get("week") != args.week:
                    continue
                if "stale_qb_veto" not in r:
                    continue  # legacy pre-overlay record
                k = (r.get("game"), r.get("team"), last_name(r.get("player", "")))
                prev = dispo.get(k)
                if prev is None or str(r.get("ts", "")) >= str(prev.get("ts", "")):
                    dispo[k] = r

    # ---- provenance index over snapshots ----
    snaps = load_snapshots_index()

    # ---- merge: manual > recorder > auto ----
    qb1 = load_qb1()
    rows = []
    for key in sorted(set(auto) | set(rec) | set(manual) | set(dispo)):
        game_id, team, lname = key
        a = auto.get(key, {})
        rc = rec.get(key, {})
        m = manual.get(key, {})
        d = dispo.get(key, {})
        automated_status = a.get("automated_status")
        recorder_status = rc.get("recorder_status")
        manual_status = m.get("manual_status")
        # precedence: manual > recorder > auto
        final_status = manual_status or recorder_status or automated_status
        if a:
            role = a["role"]
        else:
            role = ("expected_starter"
                    if lname == last_name(qb1.get(team, "")) else "backup")
        contributing = [s for s, v in (("auto", automated_status),
                                       ("recorder", recorder_status),
                                       ("manual", manual_status)) if v]
        # override: the winning source's status differs from a
        # lower-precedence source's status (a genuine conflict the
        # precedence rule resolved; filling a gap is not an override)
        statuses = {"manual": manual_status, "recorder": recorder_status,
                    "auto": automated_status}
        present = [(s, statuses[s]) for s in ("manual", "recorder", "auto")
                   if statuses[s]]
        override_used = bool(present and
                             any(v != present[0][1] for _, v in present[1:]))
        overlay_action = d.get("action")
        void_triggered = bool(final_status in TRIGGER
                              and overlay_action == "vetoed")
        fsa = None
        if automated_status:
            fsa = first_seen_at(snaps, team, args.week, lname,
                                automated_status.lower())
        rows.append({
            "game_id": game_id,
            "player": m.get("player") or rc.get("player") or a.get("player")
                      or d.get("player"),
            "team": team,
            "role": role,
            "automated_status": automated_status,
            "recorder_status": recorder_status,
            "manual_status": manual_status,
            "final_status": final_status,
            "expected_qb": exp_qb.get(team) or rc.get("expected_qb"),
            "first_seen_at": fsa,
            "recorder_captured_at": rc.get("recorder_captured_at"),
            "prediction_cutoff": prediction_cutoff,
            "overlay_action": overlay_action,
            "void_triggered": void_triggered,
            "override_used": override_used,
            "source": "+".join(contributing) if contributing else None,
            "qb_shift_pts": d.get("qb_shift_pts"),
            "adj_spread": d.get("adj_spread"),
            "edge_before": d.get("edge_before"),
            "edge_after": d.get("edge_after"),
            "double_count_risk": d.get("double_count_risk"),
            "stale_qb_veto": d.get("stale_qb_veto"),
        })

    df = pd.DataFrame(rows, columns=COLUMNS)

    out = args.out or f"{AUDIT_DIR}/audit_{args.season}_w{args.week}.parquet"
    if os.path.exists(out):
        raise SystemExit(f"refusing to overwrite existing audit table {out}")
    df.to_parquet(out, index=False)

    n_override = int(df["override_used"].sum())
    n_veto = int(df["void_triggered"].sum())
    append_log("audit_log", {"event": "audit", "season": args.season,
                             "week": args.week, "rows": len(df),
                             "void_triggered": n_veto,
                             "overrides": n_override, "out": out,
                             "freeze": freeze if avail else None,
                             "cutoff": prediction_cutoff,
                             "cutoff_note": cutoff_note})

    print("=" * 64)
    print(f"INJURY AUDIT — {args.season} week {args.week} -> {out}")
    print("=" * 64)
    print(f"rows: {len(df)}  |  cutoff: {prediction_cutoff} ({cutoff_note})")
    print(f"void_triggered (stale-QB vetoes): {n_veto}  |  overrides: {n_override}")
    if not df.empty:
        show = df[["game_id", "player", "role", "automated_status",
                   "recorder_status", "manual_status", "final_status",
                   "expected_qb", "overlay_action", "void_triggered",
                   "override_used", "source"]]
        print(show.to_string(index=False))


if __name__ == "__main__":
    main()
