#!/usr/bin/env python3
"""31_pull_market_lines_hourly.py — hourly market-line capture for the NFL model.

Captures, every hour:
  - GAME lines (spread + total per game) from TWO keyless sources:
      * ESPN public scoreboard API (DraftKings odds; no key, no fingerprinting)
      * Bovada public coupon API (curl; throttles bursts)
    Both books' numbers are recorded separately per game: redundancy when one
    source throttles, plus a cross-book check.
  - PLAYER PROP lines from Bovada only (PrizePicks/Underdog/DraftKings block
    automated access; verified 2026-10-01). Beyond the original three yards
    markets, also captures Receptions, Rush Attempts, Pass Attempts,
    Completions, and Anytime TD when Bovada offers them. Markets not offered
    are recorded as absent — never fabricated.

Keyless sources only: no API key, no signup, no card. No retry storms: a
throttled/failed source is recorded in the snapshot and the run continues
with whatever sources succeeded.

Storage (append-only, never overwritten):
  data/market_hourly/game_lines/game_lines_{season}_w{week}_{utcstamp}.json
  data/market_hourly/prop_lines/prop_lines_{season}_w{week}_{utcstamp}.json
utcstamp = YYYYMMDDTHHMMSSZ (UTC). captured_at inside each file is local ISO
with offset. Files are never overwritten; a same-second collision gets a
numeric suffix.

Friday 18:00 CT evaluation cutoff: the hourly stream does NOT change the
cutoff rule. Use scripts/market_lines_latest.py::snapshot_at_or_before() to
select the newest successful snapshot at or before the cutoff. The stream
feeds line-movement / CLV tracking and live display lines.

No-op: exits 0 writing nothing when neither source returns a pregame event
(offseason / between slates). A throttled Bovada run still writes a snapshot
recording the throttle (auditable), but "latest" selectors skip
non-successful snapshots, so a throttled run never blanks live display lines.

Usage:
  ./venv/bin/python scripts/31_pull_market_lines_hourly.py [--season 2026] [--week 4]
Week auto-detects from data/games.csv (first week with a game on/after today).
"""

import argparse
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HOURLY_ROOT = os.path.join(DATA_ROOT, "market_hourly")
CT = ZoneInfo("America/Chicago")

COUPON_URL = ("https://www.bovada.lv/services/sports/event/coupon/events/A/"
              "description/football/nfl?preMatchOnly=true&lang=en")
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# ---------------------------------------------------------------------------
# team mappings
# ---------------------------------------------------------------------------
# ESPN abbreviations -> nflverse abbreviations (only the differences)
ESPN_ABBR_FIX = {"LAR": "LA", "WSH": "WAS"}

# Bovada full team names -> nflverse abbreviations
BOVADA_TEAM_MAP = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Los Angeles Chargers": "LAC", "Los Angeles Rams": "LA",
    "Las Vegas Raiders": "LV", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "Seattle Seahawks": "SEA", "San Francisco 49ers": "SF",
    "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
}

# ---------------------------------------------------------------------------
# prop market definitions: (our_key, keyword) in match order (specific first)
# ---------------------------------------------------------------------------
PROP_MARKETS = [
    ("pass_yards", "passing yards"),
    ("rush_yards", "rushing yards"),
    ("receiving_yards", "receiving yards"),
    ("receptions", "receptions"),
    ("rush_attempts", "rushing attempts"),
    ("pass_attempts", "passing attempts"),
    ("completions", "completions"),
    ("anytime_td", "anytime touchdown"),
]
PROP_KEY_SET = {k for k, _ in PROP_MARKETS}

TOTAL_DESC_RE = re.compile(r"^Total\s+(.+?)\s+-\s+(.+?)\s+\(([A-Z]{2,3})\)$")
ANYTIME_TD_RE = re.compile(r"^Anytime Touchdown(?: Scorer)?\s+-\s+(.+?)\s+\(([A-Z]{2,3})\)$")


def stat_phrase_to_market(phrase):
    p = phrase.lower()
    for key, kw in PROP_MARKETS:
        if kw in p:
            return key
    return None


# ---------------------------------------------------------------------------
# fetching (keyless only)
# ---------------------------------------------------------------------------
def curl_json(url, timeout=60):
    out = subprocess.run(["curl", "-s", "-m", str(timeout), url,
                          "-H", f"User-Agent: {UA}"],
                         capture_output=True, timeout=timeout + 30)
    return json.loads(out.stdout)


def fetch_bovada(retries=3, backoff_s=20):
    """Bovada coupon; throttles bursts with empty {} — back off, don't storm."""
    last_err = None
    for attempt in range(retries):
        try:
            data = curl_json(COUPON_URL)
            events = (data[0]["events"] if isinstance(data, list)
                      else data.get("events", []))
            if events:
                return data, None
            last_err = "empty events (throttled?)"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
        if attempt < retries - 1:
            time.sleep(backoff_s)
    return None, f"bovada fetch failed after {retries} tries: {last_err}"


def fetch_espn():
    try:
        data = curl_json(ESPN_URL)
        events = data.get("events", [])
        return data, None
    except Exception as e:  # noqa: BLE001
        return None, f"espn fetch failed: {e}"


# ---------------------------------------------------------------------------
# game lines
# ---------------------------------------------------------------------------
def parse_espn_games(scoreboard):
    """DraftKings odds via ESPN. Returns list of dicts; skips non-pregame."""
    games, notes = [], []
    for ev in scoreboard.get("events", []):
        try:
            comp = ev["competitions"][0]
            if comp.get("status", {}).get("type", {}).get("state") != "pre":
                continue  # already started/final: not a market line
            teams = {}
            for c in comp["competitors"]:
                abbr = c["team"]["abbreviation"]
                abbr = ESPN_ABBR_FIX.get(abbr, abbr)
                teams[c["homeAway"]] = abbr
            home, away = teams.get("home"), teams.get("away")
            if not home or not away:
                notes.append("espn event missing home/away"); continue
            odds = comp.get("odds") or []
            if not odds:
                notes.append(f"{away}@{home}: no odds"); continue
            o = odds[0]
            book = (o.get("provider", {}) or {}).get("name", "").lower().replace(" ", "")
            spread = o.get("spread")
            total = o.get("overUnder")
            hf = ((o.get("homeTeamOdds") or {}).get("favorite")) is True
            af = ((o.get("awayTeamOdds") or {}).get("favorite")) is True
            if spread is None or total is None:
                notes.append(f"{away}@{home}: odds missing spread/total"); continue
            spread_home = abs(float(spread)) if hf else (-abs(float(spread)) if af else 0.0)
            games.append({"away": away, "home": home,
                          "spread_home": round(spread_home, 1),
                          "total": round(float(total), 1),
                          "book": book or "draftkings",
                          "book_raw": o.get("provider", {}).get("name")})
        except Exception as e:  # noqa: BLE001
            notes.append(f"espn event parse error: {e}")
    return games, notes


def _bovada_events(coupon):
    if isinstance(coupon, list):
        return coupon[0]["events"]
    return coupon.get("events", [])


def parse_bovada_games(coupon):
    """Defensive parse of Bovada game lines.

    Structural assumptions (unverified against a live coupon in this session
    because Bovada throttled): events carry `competitors` with a `home` flag,
    a `displayGroups` entry named "Game Lines", and markets named
    "Point Spread" / "Total" whose outcomes carry team full names and
    price.handicap. Strict validation; anything unexpected -> the event is
    skipped and noted, never silently mis-parsed.
    """
    games, notes = [], []
    for ev in _bovada_events(coupon):
        try:
            comps = ev.get("competitors", [])
            home_c = next((c for c in comps if c.get("home")), None)
            away_c = next((c for c in comps if not c.get("home")), None)
            if not home_c or not away_c:
                notes.append("event missing home/away competitors"); continue
            home = BOVADA_TEAM_MAP.get(home_c.get("name"))
            away = BOVADA_TEAM_MAP.get(away_c.get("name"))
            if not home or not away:
                notes.append(f"unmapped teams: {away_c.get('name')} @ {home_c.get('name')}")
                continue
            gl = next((g for g in ev.get("displayGroups", [])
                       if g.get("description") == "Game Lines"), None)
            if gl is None:
                notes.append(f"{away}@{home}: no 'Game Lines' group"); continue
            spread_home = total = None
            for m in gl.get("markets", []):
                md = m.get("description") or ""
                if md == "Point Spread" and spread_home is None:
                    by_team = {}
                    for o in m.get("outcomes", []):
                        t = BOVADA_TEAM_MAP.get(o.get("description"))
                        try:
                            by_team[t] = float(o["price"]["handicap"])
                        except (KeyError, TypeError, ValueError):
                            pass
                    if home in by_team:
                        spread_home = -by_team[home]  # home-spread convention (+ = home favored)
                elif md == "Total" and total is None:
                    for o in m.get("outcomes", []):
                        if o.get("description") == "Over":
                            try:
                                total = float(o["price"]["handicap"])
                            except (KeyError, TypeError, ValueError):
                                pass
            if spread_home is None or total is None:
                notes.append(f"{away}@{home}: missing spread/total in Game Lines"); continue
            if not (-30 <= spread_home <= 30 and 20 <= total <= 80):
                notes.append(f"{away}@{home}: implausible s={spread_home} t={total}"); continue
            games.append({"away": away, "home": home,
                          "spread_home": round(spread_home, 1),
                          "total": round(total, 1), "book": "bovada"})
        except Exception as e:  # noqa: BLE001
            notes.append(f"bovada game parse error: {e}")
    return games, notes


# ---------------------------------------------------------------------------
# prop lines (Bovada only)
# ---------------------------------------------------------------------------
def parse_bovada_props(coupon):
    """Returns (lines, markets_offered, groups_seen).

    lines: [{bovada_player, team, market, line, line_type}] with line_type
    "handicap" (totals) or "odds" (anytime TD, American price on Yes).
    """
    lines, groups_seen = [], set()
    for ev in _bovada_events(coupon):
        for g in ev.get("displayGroups", []):
            gd = (g.get("description") or "")
            groups_seen.add(gd)
            for m in g.get("markets", []):
                md = (m.get("description") or "")
                if m.get("key") == "2W-OU":
                    mm = TOTAL_DESC_RE.match(md)
                    if not mm:
                        continue
                    market = stat_phrase_to_market(mm.group(1))
                    if not market or market == "anytime_td":
                        continue
                    overs = [o for o in m.get("outcomes", []) if o.get("description") == "Over"]
                    if not overs:
                        continue
                    try:
                        line = float(overs[0]["price"]["handicap"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    lines.append({"bovada_player": mm.group(2), "team": mm.group(3),
                                  "market": market, "line": line, "line_type": "handicap"})
                else:
                    mm = ANYTIME_TD_RE.match(md)
                    if not mm:
                        continue
                    yes = [o for o in m.get("outcomes", [])
                           if (o.get("description") or "").lower() == "yes"]
                    if not yes:
                        continue
                    try:
                        price = float(yes[0]["price"]["american"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    lines.append({"bovada_player": mm.group(1), "team": mm.group(2),
                                  "market": "anytime_td", "line": price,
                                  "line_type": "odds"})
    offered = set()
    for gd in groups_seen:
        mk = stat_phrase_to_market(gd)
        if mk:
            offered.add(mk)
    # a market can also be offered via a market description even if the group
    # name didn't match (e.g. group "Player Props" containing "Total Receptions")
    for ln in lines:
        offered.add(ln["market"])
    return lines, sorted(offered), sorted(groups_seen)


def our_last(player_id):
    return player_id.rsplit(".", 1)[-1].lower()


def our_first_initial(player_id):
    return player_id.split(".", 1)[0][0].lower()


def load_prop_rows(season, week):
    """Our projection rows per market for conservative name matching.

    Yards markets come from the v2 file; receptions/rush_attempts from the
    additive experimental heads. Markets without a projection file are still
    captured (player=null) — the line is real, we just have no row to match.
    """
    rows = {}
    v2_path = os.path.join(DATA_ROOT, f"prop_v2_{season}_w{week}.json")
    if os.path.exists(v2_path):
        with open(v2_path) as f:
            for r in json.load(f)["projections"]:
                rows.setdefault(r["market"], []).append(r)
    for market, fname in (("receptions", f"prop_v2_{season}_w{week}_receptions.json"),
                          ("rush_attempts", f"prop_v2_{season}_w{week}_rush_attempts.json")):
        p = os.path.join(DATA_ROOT, fname)
        if os.path.exists(p):
            with open(p) as f:
                rows.setdefault(market, []).extend(json.load(f)["projections"])
    return rows


def match_players(bovada_lines, rows_by_market):
    idx = {}
    for market, prows in rows_by_market.items():
        for r in prows:
            key = (r["team"], our_last(r["player"]), r["market"])
            idx.setdefault(key, []).append(r["player"])
    matched = []
    for ln in bovada_lines:
        last = ln["bovada_player"].rsplit(" ", 1)[-1].lower()
        cands = idx.get((ln["team"], last, ln["market"]), [])
        pid = None
        if len(cands) == 1:
            pid = cands[0]
        elif len(cands) > 1:
            first = ln["bovada_player"].split(" ")[0][0].lower()
            narrowed = [c for c in cands if our_first_initial(c) == first]
            if len(narrowed) == 1:
                pid = narrowed[0]
        # ambiguous -> null, never a guess
        matched.append({**ln, "player": pid})
    return matched


# ---------------------------------------------------------------------------
# week detection + snapshot writing
# ---------------------------------------------------------------------------
def detect_week(season):
    import pandas as pd
    sched = pd.read_csv(os.path.join(DATA_ROOT, "games.csv"))
    s = sched[sched["season"] == season]
    if "game_type" in s.columns:
        reg = s[s["game_type"] == "REG"]
        if len(reg):
            s = reg
    today = datetime.datetime.now(CT).date().isoformat()
    future = s[s["gameday"] >= today]
    if len(future):
        return season, int(future["week"].min())
    return season, int(s["week"].max())  # offseason: last week; expect no-op


def write_snapshot(kind, season, week, payload):
    d = os.path.join(HOURLY_ROOT, kind)
    os.makedirs(d, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = f"{kind}_{season}_w{week}_{stamp}"
    path = os.path.join(d, base + ".json")
    n = 1
    while os.path.exists(path):  # never overwrite; same-second rerun gets suffix
        n += 1
        path = os.path.join(d, f"{base}_{n}.json")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=1)
    os.replace(tmp, path)
    return path


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", type=int, default=None)
    args = ap.parse_args()

    season = args.season
    week = args.week if args.week else detect_week(season)[1]
    captured_at = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()
    print(f"capture {season} week {week} at {captured_at}")

    # ---- game lines: ESPN (DraftKings) + Bovada ----
    espn_data, espn_err = fetch_espn()
    espn_games, espn_notes = parse_espn_games(espn_data) if espn_data else ([], [])
    bovada_data, bovada_err = fetch_bovada()
    bov_games, bov_notes = parse_bovada_games(bovada_data) if bovada_data else ([], [])

    espn_status = "ok" if espn_data and not espn_err else "failed"
    if espn_data and not espn_games and not espn_err:
        espn_status = "no_pregame_events"
    bov_status = ("ok" if bovada_data and bov_games else
                  "throttled" if bovada_err and "throttled" in (bovada_err or "") else
                  ("parse_failed" if bovada_data else "failed"))

    by_game = {}
    for g in espn_games + bov_games:
        key = f"{g['away']}_{g['home']}"
        e = by_game.setdefault(key, {"away": g["away"], "home": g["home"],
                                     "game_key": key, "books": {}})
        e["books"][g["book"]] = {"spread_home": g["spread_home"], "total": g["total"]}

    game_status = "ok" if by_game else "no_pregame_events"
    if by_game:
        gp = {"season": season, "week": week, "captured_at": captured_at,
              "status": "ok",
              "sources": {
                  "espn_draftkings": {"status": espn_status,
                                      "n_games": len(espn_games),
                                      "error": espn_err, "notes": espn_notes[:10]},
                  "bovada": {"status": bov_status,
                             "n_games": len(bov_games),
                             "error": bovada_err, "notes": bov_notes[:10]},
              },
              "convention": "spread_home: + means home team favored (matches market_2026_wN.json)",
              "n_games": len(by_game),
              "games": [by_game[k] for k in sorted(by_game)]}
        p = write_snapshot("game_lines", season, week, gp)
        print(f"game lines: {len(by_game)} games "
              f"(draftkings {len(espn_games)}, bovada {len(bov_games)}) -> {p}")
    else:
        print("game lines: no pregame events from any source; no snapshot written")

    # ---- prop lines: Bovada only ----
    if bovada_data:
        raw_lines, offered, groups_seen = parse_bovada_props(bovada_data)
        rows_by_market = load_prop_rows(season, week)
        matched = match_players(raw_lines, rows_by_market)
        lines = [{**m, "source": "bovada", "captured_at": captured_at}
                 for m in matched]
        not_offered = sorted(PROP_KEY_SET - set(offered))
        pp = {"season": season, "week": week, "captured_at": captured_at,
              "status": "ok", "source": "bovada",
              "source_note": ("Bovada public unauthenticated JSON coupon API. Totals: main "
                              "Over/Under line only (2W-OU), alternates excluded. Anytime TD: "
                              "American price on Yes."),
              "markets_offered": offered,
              "markets_not_offered": not_offered,
              "groups_seen": groups_seen,
              "n_lines": len(lines),
              "n_matched": sum(1 for l in lines if l["player"]),
              "lines": lines}
        p = write_snapshot("prop_lines", season, week, pp)
        print(f"prop lines: {len(lines)} lines ({pp['n_matched']} matched), "
              f"offered={offered}, not_offered={not_offered} -> {p}")
    else:
        # Auditable record of the attempt; "latest" selectors skip non-ok
        # snapshots so this never blanks live display lines.
        pp = {"season": season, "week": week, "captured_at": captured_at,
              "status": "throttled", "source": "bovada",
              "error": bovada_err, "n_lines": 0, "n_matched": 0,
              "markets_offered": [], "markets_not_offered": sorted(PROP_KEY_SET),
              "lines": []}
        p = write_snapshot("prop_lines", season, week, pp)
        print(f"prop lines: bovada {bov_status} ({bovada_err}); "
              f"throttle recorded, no lines -> {p}")

    if game_status == "no_pregame_events" and not bovada_data:
        print("NO-OP: no pregame game lines and no Bovada coupon; nothing to capture.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
