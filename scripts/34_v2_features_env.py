#!/usr/bin/env python3
"""Step 34: V2 environment features (game grain, walk-forward SAFE).

From nflverse schedules (all strictly pregame fields):
  - rest_diff: home_rest - away_rest (days)
  - short_week_home/away: rest <= 6 days (Thu-game followups)
  - off_bye_home/away: rest >= 13
  - travel_miles_away: great-circle distance, away team city -> game stadium
    (hardcoded stadium coordinates below; neutral-site aware)
  - altitude_game: stadium elevation >= 4000 ft (DEN; Mexico City neutral)
  - dome_game / closed_roof: roof in {dome, closed}
  - grass_game: surface == grass
  - temp_game / wind_game: forecast temp (F), wind (mph) at kickoff
    (margin use only; prior work: wind affects totals, totals never bet)
  - primetime: gametime >= 20:00 ET or Monday night (gameday weekday)
  - div_game: divisional (already in V1; kept for reference, flagged overlap)
  - month: seasonal scoring environment proxy

Grain: one row per game (2018+). All inputs known before kickoff.
NO model fitting. Feature architecture only.
"""
import math
import os

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
OUT = f"{DATA}/v2/game_env.parquet"

# Stadium coordinates (lat, lon) -- public facts, hardcoded for offline use.
STADIUM_COORDS = {
    "ARI": (33.5277, -112.2626), "ATL": (33.7554, -84.4008),
    "BAL": (39.2780, -76.6227), "BUF": (42.7738, -78.7870),
    "CAR": (35.2258, -80.8529), "CHI": (41.8623, -87.6167),
    "CIN": (39.0954, -84.5160), "CLE": (41.5061, -81.6995),
    "DAL": (32.7473, -97.0945), "DEN": (39.7439, -105.0201),
    "DET": (42.3400, -83.0456), "GB": (44.5013, -88.0622),
    "HOU": (29.6847, -95.4107), "IND": (39.7601, -86.1639),
    "JAX": (30.3239, -81.6373), "KC": (39.0489, -94.4839),
    "LV": (36.0908, -115.1839), "LAC": (33.9535, -118.3392),
    "LAR": (33.9535, -118.3392), "MIA": (25.9580, -80.2389),
    "MIN": (44.9739, -93.2575), "NE": (42.0909, -71.2643),
    "NO": (29.9511, -90.0812), "NYG": (40.8135, -74.0745),
    "NYJ": (40.8135, -74.0745), "PHI": (39.9008, -75.1675),
    "PIT": (40.4468, -79.9921), "SF": (37.4030, -121.9700),
    "SEA": (47.5952, -122.3316), "TB": (27.9742, -82.5033),
    "TEN": (36.1665, -86.7713), "WAS": (38.9076, -76.8645),
}
ALTITUDE_FT = {"DEN": 5280}


def haversine_miles(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 3958.8 * math.asin(math.sqrt(h))


def main():
    os.makedirs(f"{DATA}/v2", exist_ok=True)
    s = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    s = s[(s["week"] <= 22) & s["home_score"].notna()].copy()
    s = s[(s["season"] >= 2018) & (s["season"] <= 2022)]  # vault/2026 excluded
    s["gameday"] = pd.to_datetime(s["gameday"])

    out = pd.DataFrame({
        "game_id": s["game_id"], "season": s["season"], "week": s["week"],
        "home_team": s["home_team"], "away_team": s["away_team"],
        "rest_diff": s["home_rest"] - s["away_rest"],
        "short_week_home": (s["home_rest"] <= 6).astype(int),
        "short_week_away": (s["away_rest"] <= 6).astype(int),
        "off_bye_home": (s["home_rest"] >= 13).astype(int),
        "off_bye_away": (s["away_rest"] >= 13).astype(int),
        "dome_game": s["roof"].isin(["dome", "closed"]).astype(int),
        "grass_game": (s["surface"] == "grass").astype(int),
        "temp_game": pd.to_numeric(s["temp"], errors="coerce"),
        "wind_game": pd.to_numeric(s["wind"], errors="coerce"),
        "div_game": s["div_game"].astype(int),
        "month": s["gameday"].dt.month,
    })
    # primetime: late kickoff or Monday
    gt = pd.to_datetime(s["gametime"], format="%H:%M", errors="coerce")
    out["primetime"] = ((gt.dt.hour >= 20)
                        | (s["gameday"].dt.dayofweek == 0)).astype(int)
    # travel: away city -> stadium (home city, or neutral site)
    def travel(row):
        a = STADIUM_COORDS.get(row["away_team"])
        h = STADIUM_COORDS.get(row["home_team"])
        if a is None or h is None:
            return np.nan
        return haversine_miles(a, h)

    out["travel_miles_away"] = s.apply(travel, axis=1)
    out["altitude_game"] = s["home_team"].map(
        lambda t: 1 if ALTITUDE_FT.get(t, 0) >= 4000 else 0).astype(int)
    out.to_parquet(OUT, index=False)
    print(f"wrote {OUT}: {out.shape}")
    print("seasons:", sorted(out["season"].unique()))


if __name__ == "__main__":
    main()
