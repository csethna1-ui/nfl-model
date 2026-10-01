#!/usr/bin/env python3
"""18_export_experimental_markets.py — export experimental props markets for the dashboard.

Reads the additive experimental heads (003B rush attempts live; 003A receptions
live) and writes data/ui_json/v1/experimental_markets.json.

Gatekeeper rule (AGENTS.md): the export layer is the final gatekeeper. Any
non-finite value fails the export loudly — never literal NaN in JSON.
Existing Props v2 output is untouched by this script.
"""
import argparse
import glob
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "data" / "ui_json" / "v1" / "experimental_markets.json"


def _detect_latest_week():
    """Auto-detect the latest week from prop_v2_2026_w*_rush_attempts.json files."""
    cands = []
    for f in glob.glob(str(ROOT / "data" / "prop_v2_2026_w*_rush_attempts.json")):
        stem = Path(f).name[len("prop_v2_2026_w"):-len("_rush_attempts.json")]
        if stem.isdigit():
            cands.append(int(stem))
    if not cands:
        raise SystemExit(
            "ERROR: no prop_v2_2026_w*_rush_attempts.json found in data/; "
            "pass --week explicitly.")
    return max(cands)

DISCLAIMER = (
    "Experimental NFL analytics / paper-tracking system. Experimental markets "
    "are research projections only. No verified betting edge has been established; "
    "projection accuracy alone does not imply the market is beatable."
)


def _json_safe(obj):
    """Recursively convert non-finite floats to None; raise on unexpected types."""
    if isinstance(obj, float):
        if math.isfinite(obj):
            return obj
        return None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def main():
    p = argparse.ArgumentParser(description="Export experimental props markets.")
    p.add_argument("--week", type=int, default=None,
                   help="Week to export (default: auto-detect latest "
                        "prop_v2_2026_w*_rush_attempts.json)")
    args = p.parse_args()
    wk = args.week if args.week is not None else _detect_latest_week()
    rush_src = ROOT / "data" / f"prop_v2_2026_w{wk}_rush_attempts.json"
    rec_src = ROOT / "data" / f"prop_v2_2026_w{wk}_receptions.json"
    print(f"exporting experimental markets for week {wk}")
    src = json.loads(rush_src.read_text())
    rush_rows = _json_safe(src.get("projections", []))
    for r in rush_rows:
        # Enforce experimental labeling contract on every row.
        assert r.get("status") == "experimental", f"row missing experimental status: {r.get('player')}"
        assert "No verified betting edge" in r.get("display_note", ""), f"row missing edge disclaimer: {r.get('player')}"

    rsrc = json.loads(rec_src.read_text())
    rec_rows = _json_safe(rsrc.get("projections", []))
    for r in rec_rows:
        assert r.get("status") == "experimental", f"row missing experimental status: {r.get('player')}"
        assert "No verified betting edge" in r.get("display_note", ""), f"row missing edge disclaimer: {r.get('player')}"
        assert r.get("market") == "receptions", f"row wrong market: {r.get('player')}"

    # ---- live market lines (hourly snapshots; display only) ----
    # Refreshes market_line from the newest *successful* hourly prop snapshot
    # when one exists; otherwise rows keep their projection-time market_line.
    # Never imputed: no snapshot -> null stays null.
    ml_ts, ml_src, ml_n = None, None, 0
    try:
        from market_lines_latest import latest_snapshot
        snap = latest_snapshot("prop_lines", int(src.get("season", 2026)),
                               int(src.get("week", 4)))
    except Exception:  # helper missing/broken -> keep projection-time lines
        snap = None
    if snap:
        lu = {(l["player"], l["team"], l["market"]): l["line"]
              for l in snap.get("lines", []) if l.get("player")}
        for r in rush_rows + rec_rows:
            hit = lu.get((r.get("player"), r.get("team"), r.get("market")))
            if hit is not None:
                r["market_line"] = float(hit)
                ml_n += 1
        ml_ts, ml_src = snap.get("captured_at"), snap.get("source")
        print(f"experimental market_line: {ml_n} rows refreshed "
              f"from hourly snapshot @{ml_ts}")

    payload = {
        "season": int(src.get("season", 2026)),
        "week": int(src.get("week", 4)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": DISCLAIMER,
        "market_lines_source": ml_src,
        "market_lines_captured_at": ml_ts,
        "markets": [
            {
                "market": "rush_attempts",
                "title": "Rush Attempts",
                "status": "experimental",
                "display_note": src.get("display_note", ""),
                "model_version": "003B-M2-frozen",
                "n_projections": len(rush_rows),
                "prediction_timestamp": src.get("prediction_timestamp"),
                "projections": rush_rows,
            },
            {
                "market": "receptions",
                "title": "Receptions",
                "status": "experimental",
                "display_note": rsrc.get("display_note", ""),
                "model_version": "003A-M2-verified",
                "n_projections": len(rec_rows),
                "prediction_timestamp": rsrc.get("prediction_timestamp"),
                "projections": rec_rows,
            },
        ],
    }

    text = json.dumps(payload, indent=1, allow_nan=False)  # fail loudly on non-finite
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT} ({len(rush_rows)} rush-attempt rows, {len(rec_rows)} reception rows)")


if __name__ == "__main__":
    sys.exit(main())
