#!/usr/bin/env python3
"""Pull NFL player-prop market lines (pass/rush/receiving yards) from a free,
keyless source and write a versioned, timestamped market file.

Source: Bovada's unauthenticated public JSON API
  (https://www.bovada.lv/services/sports/event/coupon/events/A/description/football/nfl).
No signup, no API key, no card. If Bovada changes or blocks this endpoint,
this script fails loudly rather than fabricating lines.

Output: data/market_props/market_props_{season}_w{week}.json (never overwritten).
Each line records exactly: {player, market, line, source, captured_at},
where player is the prop-export player id (e.g. "J.Allen") when the Bovada
player matches one of our projection rows, else null.

Matching: Bovada names ("Josh Allen (BUF)") are matched to our prop ids
("J.Allen") on (team, last_name, market); first-initial disambiguation when
several players share a last name on a team; ambiguous -> no match (null),
never a guess.

Usage:
  ./venv/bin/python scripts/30_pull_prop_lines.py --season 2026 --week 4
Friday cron order: 16 (projections) -> 30 (this script) -> 15 (export).
"""

import argparse, datetime, json, os, re, sys, urllib.request

DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
COUPON_URL = ("https://www.bovada.lv/services/sports/event/coupon/events/A/"
              "description/football/nfl?preMatchOnly=true&lang=en")
SOURCE = "bovada"
GROUP_TO_MARKET = {
    "Passing Yards": "pass_yards",
    "Rushing Yards": "rush_yards",
    "Receiving Yards": "receiving_yards",
}
MAIN_LINE_RE = re.compile(r"Total (Passing|Rushing|Receiving) Yards - (.+) \(([A-Z]{2,3})\)")


def fetch_coupon(retries=4, backoff_s=60):
    # NOTE: plain urllib gets an empty {} from this endpoint (edge
    # fingerprinting); curl works reliably, so we shell out to it.
    # The endpoint also throttles bursts with empty {} responses, hence retries.
    import subprocess, time
    last_err = None
    for attempt in range(retries):
        out = subprocess.run(
            ["curl", "-s", "-m", "60", COUPON_URL,
             "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)"],
            capture_output=True, timeout=90)
        try:
            data = json.loads(out.stdout)
            events = (data[0]["events"] if isinstance(data, list)
                      else data.get("events", []))
            if events:
                return data
            last_err = "empty events"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
        if attempt < retries - 1:
            time.sleep(backoff_s)
    raise RuntimeError(f"Bovada coupon fetch failed after {retries} tries: {last_err}")


def _events(coupon):
    if isinstance(coupon, list):
        return coupon[0]["events"]
    return coupon.get("events", [])


def parse_lines(coupon):
    """Return list of (game_desc, market, bovada_name, team, line)."""
    out = []
    for ev in _events(coupon):
        for g in ev.get("displayGroups", []):
            market = GROUP_TO_MARKET.get(g.get("description"))
            if not market:
                continue
            for m in g["markets"]:
                if m.get("key") != "2W-OU":  # main total only, not alternates
                    continue
                mm = MAIN_LINE_RE.match(m.get("description") or "")
                if not mm:
                    continue
                _, name, team = mm.groups()
                overs = [o for o in m["outcomes"] if o.get("description") == "Over"]
                if not overs:
                    continue
                line = float(overs[0]["price"]["handicap"])
                out.append((ev["description"], market, name, team, line))
    return out


def our_last(player_id):
    # "J.Allen" / "Ji.Horn" / "Bri.Thomas" -> last name
    return player_id.rsplit(".", 1)[-1].lower()


def our_first_initial(player_id):
    return player_id.split(".", 1)[0][0].lower()


def match_players(bovada_lines, prop_rows):
    """Map each Bovada line to our player id, or None when ambiguous."""
    # index our props by (team, last_name, market)
    idx = {}
    for r in prop_rows:
        key = (r["team"], our_last(r["player"]), r["market"])
        idx.setdefault(key, []).append(r["player"])
    matched = []
    for game, market, name, team, line in bovada_lines:
        last = name.rsplit(" ", 1)[-1].lower()
        cands = idx.get((team, last, market), [])
        pid = None
        if len(cands) == 1:
            pid = cands[0]
        elif len(cands) > 1:
            # disambiguate by first initial, e.g. "D.Johnson" vs "T.Johnson"
            first = name.split(" ")[0][0].lower()
            narrowed = [c for c in cands if our_first_initial(c) == first]
            if len(narrowed) == 1:
                pid = narrowed[0]
        matched.append((game, market, name, team, line, pid))
    return matched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", type=int, required=True)
    args = ap.parse_args()

    out_dir = os.path.join(DATA_ROOT, "market_props")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"market_props_{args.season}_w{args.week}.json")
    if os.path.exists(out_path):
        sys.exit(f"REFUSING TO OVERWRITE existing {out_path}")

    # our projection rows for identity matching
    v2_path = os.path.join(DATA_ROOT, f"prop_v2_{args.season}_w{args.week}.json")
    if not os.path.exists(v2_path):
        sys.exit(f"projection file not found: {v2_path} (run 16 first)")
    with open(v2_path) as f:
        prop_rows = json.load(f)["projections"]

    captured_at = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()
    coupon = fetch_coupon()
    bovada_lines = parse_lines(coupon)
    matched = match_players(bovada_lines, prop_rows)

    lines = [{
        "player": pid,                 # our prop-export id, or null if no unambiguous match
        "bovada_player": name,
        "team": team,
        "market": market,
        "line": line,
        "source": SOURCE,
        "captured_at": captured_at,
    } for game, market, name, team, line, pid in matched]

    payload = {
        "season": args.season,
        "week": args.week,
        "source": SOURCE,
        "source_note": ("Bovada public unauthenticated JSON coupon API; main "
                        "Over/Under total only (2W-OU), alternates excluded."),
        "captured_at": captured_at,
        "n_bovada_lines": len(lines),
        "n_matched": sum(1 for l in lines if l["player"]),
        "lines": lines,
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=1)
    print(f"wrote {out_path}: {len(lines)} lines, "
          f"{payload['n_matched']} matched to prop rows")


if __name__ == "__main__":
    main()
