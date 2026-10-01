#!/usr/bin/env python3
"""
04_resolve_entities.py — Player entity resolution + event classification.

Inputs:
  data/pft_sitemap.db (articles table)
  data/rosters_2018_2022.parquet (season, full_name/team/position)

Method:
  1. Per-season name index from rosters: normalized full name -> [(team, position)].
     Normalization: lowercase, strip suffixes (jr/sr/ii/iii/iv/v), de-punctuate.
  2. One regex pass per article over headline+body with all season names
     (longest-first alternation), article season from date_published year.
  3. Disambiguation for multi-team names:
       a. parsely_tags team names ("Tennessee Titans" etc.) -> team abbr;
          if exactly one candidate team matches a tag -> resolved.
       b. else if one candidate -> resolved.
       c. else mark AMBIGUOUS (recorded, not guessed).
  4. Curated nickname map for common PFT nicknames (documented; residual = limitation).

Event class (headline+body keyword rules, heuristic — documented):
  ruled_out / expected_to_play / practice_participation / injury_report / transaction / other

Also flags qb_relevant (any resolved QB entity, or QB-position keyword + name hit).

Outputs: entities(article_url, player_name, team, position, resolution_method),
          articles.event_class, articles.qb_relevant, articles.n_entities
Rerunnable: rebuilds entities table from scratch.
"""
import json, re, sqlite3, unicodedata
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
DB = DATA / "pft_sitemap.db"
ROSTERS = DATA / "rosters_2018_2022.parquet"          # season-grain fallback
ROSTERS_WK = DATA / "rosters_weekly_2018_2022.parquet"  # week-grain primary

TEAM_NAMES = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Oakland Raiders": "OAK",
    "Los Angeles Chargers": "LAC", "San Diego Chargers": "SD",
    "Los Angeles Rams": "LAR", "St. Louis Rams": "STL",
    "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN", "New England Patriots": "NE",
    "New Orleans Saints": "NO", "New York Giants": "NYG", "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS", "Washington Football Team": "WAS",
    "Washington Redskins": "WAS",
}

# Curated PFT nicknames -> normalized full name. Documented; residual unmatched = limitation.
NICKNAMES = {
    "big ben": "ben roethlisberger",
    "matty ice": "matt ryan",
    "beek": None,  # placeholder guard — removed below
}

# remove guard
NICKNAMES.pop("beek", None)
NICKNAMES.update({
    "megatron": "calvin johnson",
    "beast mode": "marshawn lynch",
    "shady": "lesean mccoy",
    "primetime": "deion sanders",
    "danny dimes": "daniel jones",
    "baker": None,  # too ambiguous, skip
})
NICKNAMES.pop("baker", None)

SUFFIX_RE = re.compile(r"\s+(jr|sr|ii|iii|iv|v)\.?$")
PUNCT_RE = re.compile(r"[^a-z\s]")

def normalize(name):
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    n = n.lower().strip()
    n = SUFFIX_RE.sub("", n)
    n = PUNCT_RE.sub("", n)
    return re.sub(r"\s+", " ", n).strip()

EVENT_RULES = [
    ("ruled_out", [r"\bruled out\b", r"\bwill not play\b", r"\bwon'?t play\b", r"\bout for\b",
                   r"\bsidelined\b", r"\bscratched\b", r"\bplaced on (injured reserve|ir)\b",
                   r"\bto miss\b", r"\bwill miss\b"]),
    ("expected_to_play", [r"\bexpected to play\b", r"\bwill play\b", r"\bcleared\b",
                          r"\bgood to go\b", r"\bactive\b", r"\bwill start\b"]),
    ("practice_participation", [r"\bpractice\b", r"\blimited\b", r"\bdid not practice\b",
                                r"\bfull participant\b", r"\bdnp\b"]),
    ("injury_report", [r"\binjury report\b", r"\binjur\w*\b", r"\bhurt\b", r"\bsurgery\b",
                       r"\bconcussion\b"]),
    ("transaction", [r"\bsigned\b", r"\breleased\b", r"\btraded\b", r"\bwaived\b",
                     r"\bclaimed\b", r"\bactivated\b", r"\belevated\b"]),
]

def classify_event(text):
    t = text.lower()
    for cls, pats in EVENT_RULES:
        if any(re.search(p, t) for p in pats):
            return cls
    return "other"

def build_index(rosters):
    """(season, week) -> {norm_name: [(team, position)]} ; week=0 = season-grain fallback.
    Weekly rosters give the team as of that week (handles mid-season trades);
    preseason articles fall back to week 1, then season grain."""
    idx = {}
    wk = rosters.dropna(subset=["week"])
    for (season, week), g in wk.groupby(["season", "week"]):
        d = {}
        for _, r in g.iterrows():
            nm = normalize(str(r["full_name"]))
            if not nm:
                continue
            team = str(r["team"]); pos = str(r.get("position", ""))
            d.setdefault(nm, [])
            if (team, pos) not in d[nm]:
                d[nm].append((team, pos))
        idx[(int(season), int(week))] = d
    # season-grain fallback (week=0)
    for season, g in rosters.groupby("season"):
        d = {}
        for _, r in g.iterrows():
            nm = normalize(str(r["full_name"]))
            if not nm:
                continue
            team = str(r["team"]); pos = str(r.get("position", ""))
            d.setdefault(nm, [])
            if (team, pos) not in d[nm]:
                d[nm].append((team, pos))
        idx[(int(season), 0)] = d
    return idx

def week_windows():
    """(season) -> list of (win_start, win_end, week) Tue..Mon windows from schedules."""
    sched = pd.read_parquet(DATA / "schedules_2018_2022.parquet")
    sched = sched[sched.game_type == "REG"].copy()
    sched["gameday"] = pd.to_datetime(sched.gameday)
    out = {}
    for season, g in sched.groupby("season"):
        sun = (g[g.weekday == "Sunday"].groupby("week")["gameday"]
               .agg(lambda x: x.mode().iloc[0]))
        out[int(season)] = [(s - pd.Timedelta(days=5), s + pd.Timedelta(days=1), int(w))
                            for w, s in sun.items()]
    return out

def article_season_week(dp, lm, windows):
    for src in (dp, lm):
        m = re.search(r"(20\d\d)-(\d\d)-(\d\d)", str(src or ""))
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            import datetime
            dt = datetime.datetime(y, mo, d)
            season = y if mo >= 3 else y - 1
            for ws, we, w in windows.get(season, []):
                if ws.date() <= dt.date() <= we.date():
                    return season, w
            return season, 1  # preseason/offseason -> week 1 roster
    return None, None

def main(db_path=None):
    con = sqlite3.connect(db_path or DB)
    con.execute("PRAGMA busy_timeout=60000")
    # weekly rosters preferred; fall back to season grain if weekly file missing
    if ROSTERS_WK.exists():
        rosters = pd.read_parquet(ROSTERS_WK)
        print(f"weekly rosters: {len(rosters)} rows")
    else:
        rosters = pd.read_parquet(ROSTERS)
        print("WARNING: weekly rosters missing, using season grain")
    colmap = {}
    for c in rosters.columns:
        cl = c.lower()
        if cl in ("full_name", "player_name", "name"):
            colmap[c] = "full_name"
        elif cl in ("team", "recent_team", "club"):
            colmap[c] = "team"
        elif cl == "position":
            colmap[c] = "position"
        elif cl == "season":
            colmap[c] = "season"
        elif cl == "week":
            colmap[c] = "week"
    rosters = rosters.rename(columns=colmap)
    keep = ["season", "full_name", "team", "position"] + (["week"] if "week" in rosters.columns else [])
    rosters = rosters[keep].dropna(subset=["full_name", "team"])
    print(f"rosters: {len(rosters)} rows, seasons {sorted(rosters.season.unique())}")

    idx = build_index(rosters)
    windows = week_windows()
    # lazily compiled regexes per (season, week)
    regex_cache = {}
    def get_rx(season, week):
        for key in ((season, week), (season, 1), (season, 0)):
            if key in idx:
                if key not in regex_cache:
                    d = idx[key]
                    names = sorted(d.keys(), key=len, reverse=True)
                    regex_cache[key] = (re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b"), d)
                return regex_cache[key]
        return None, None
    nick_pat = re.compile(r"\b(" + "|".join(re.escape(k) for k in NICKNAMES) + r")\b")

    con.execute("DROP TABLE IF EXISTS entities")
    con.execute("""CREATE TABLE entities(
        article_url TEXT, player_name TEXT, team TEXT, position TEXT,
        resolution_method TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_ent_url ON entities(article_url)")
    for col in ("event_class", "qb_relevant", "n_entities"):
        try:
            con.execute(f"ALTER TABLE articles ADD COLUMN {col} {'TEXT' if col=='event_class' else 'INT'}")
        except sqlite3.OperationalError:
            pass

    rows = con.execute(
        """SELECT url, headline, body_text, parsely_tags, date_published, sitemap_lastmod
           FROM articles WHERE http_status=200 AND body_text IS NOT NULL""").fetchall()
    print(f"articles to resolve: {len(rows)}")
    n_ent = n_amb = n_qb = 0
    for i, (url, headline, body, tags_json, dp, lm) in enumerate(rows):
        text = f"{headline or ''}\n{body or ''}"
        season, week = article_season_week(dp, lm, windows)
        rx_d = get_rx(season, week) if season else (None, None)
        if rx_d[0] is None:
            continue
        rx, d = rx_d
        # normalize text the same way as names
        tnorm = normalize(text)
        found = {}
        for m in rx.finditer(tnorm):
            nm = m.group(1)
            found[nm] = found.get(nm, 0) + 1
        # nicknames
        for m in nick_pat.finditer(tnorm):
            target = NICKNAMES[m.group(1)]
            if target:
                found[target] = found.get(target, 0) + 1
        # tag teams
        tag_teams = set()
        try:
            for t in json.loads(tags_json or "[]"):
                if t in TEAM_NAMES:
                    tag_teams.add(TEAM_NAMES[t])
        except Exception:
            pass

        ents = []
        for nm in found:
            cands = d.get(nm)
            if not cands:
                continue
            teams = {t for t, _ in cands}
            if len(teams) == 1:
                team, pos = cands[0]; method = "unique"
            else:
                inter = tag_teams & teams
                if len(inter) == 1:
                    team = inter.pop()
                    pos = next(p for t, p in cands if t == team); method = "tag_disambiguated"
                else:
                    team, pos, method = None, cands[0][1], "ambiguous"
                    n_amb += 1
            ents.append((url, nm, team, pos, method))
            if pos == "QB":
                n_qb += 1
        for e in ents:
            con.execute("INSERT INTO entities VALUES(?,?,?,?,?)", e)
        n_ent += len(ents)
        text_l = text.lower()
        ev = classify_event(text_l)
        qb_rel = 1 if (any(e[3] == "QB" for e in ents) or
                       ("quarterback" in text_l and re.search(r"\bqb\b", text_l))) else 0
        con.execute("UPDATE articles SET event_class=?, qb_relevant=?, n_entities=? WHERE url=?",
                    (ev, qb_rel, len(ents), url))
        if (i + 1) % 2000 == 0:
            con.commit(); print(f"  {i+1}/{len(rows)} ents={n_ent} amb={n_amb}", flush=True)
    con.commit()
    print(f"done: articles={len(rows)} entities={n_ent} ambiguous={n_amb} qb_articles~{n_qb}")
    print("event class distribution:")
    for cls, c in con.execute("SELECT event_class, COUNT(*) FROM articles WHERE http_status=200 GROUP BY 1"):
        print(f"  {cls}: {c}")
    con.close()

if __name__ == "__main__":
    import sys
    db = sys.argv[sys.argv.index("--db") + 1] if "--db" in sys.argv else None
    main(db)
