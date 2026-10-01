#!/usr/bin/env python3
"""Step 36: V2 research inventory + documentation (NO model fitting).

Reads the built V2 feature tables and writes, to v2_research/:
  - feature_inventory.json : every feature with full tags
      (name, family, definition, source, seasons, timestamp availability,
       leakage status, min sample, info family, overlaps V1?,
       genuinely new per the uncorrelated-with-ELO/EPA filter?, complexity)
  - data_availability.json : source-by-source coverage
  - leakage_audit.md       : per-family leakage + timestamp assessment
  - architecture.md        : the Component + Matchup design
  - REPORT.md              : build summary

NO model fitting. NO validation evaluation. Architecture only.
"""
import json
import os

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
V2 = f"{DATA}/v2"
R = f"{DATA}/../v2_research"
os.makedirs(R, exist_ok=True)

# ---------------------------------------------------------------- family tags
FAMILIES = {
    "possession": {
        "source": "nflverse PBP (local parquets), drive-level via fixed_drive",
        "seasons": "1999+ (built 2018-2026)",
        "timestamp_availability": "play timestamps; week grain; nightly in-season",
        "leakage_status": "SAFE -- strictly games with week < W; drive points from in-game score deltas only",
        "min_sample": "4 prior games (expanding all-history)",
        "info_family": "possession structure / scoring-opportunity generation",
        "overlaps_v1": "PARTIAL -- EPA/play adjacent but drive structure (counts, sequencing, field position) is new",
        "genuinely_new": "LIKELY -- drive counts, 3-and-outs, start field position are weakly correlated with EPA/play efficiency",
        "genuinely_new_rationale": "Two teams can share EPA/play via very different possession structures; audit filter: possession counts are process variables, not efficiency ratings",
        "complexity": "low",
    },
    "explosiveness": {
        "source": "nflverse PBP (local parquets)",
        "seasons": "1999+ (built 2018-2026)",
        "timestamp_availability": "play timestamps; week grain; nightly in-season",
        "leakage_status": "SAFE -- strictly games with week < W",
        "min_sample": "4 prior games (expanding all-history)",
        "info_family": "outcome distribution shape / volatility",
        "overlaps_v1": "PARTIAL -- V1 has EPA means and success rate; V1 has NO tails, variance, or verticality",
        "genuinely_new": "LIKELY -- EPA variance/tails/aDOT describe distribution shape, which mean-EPA discards by construction",
        "genuinely_new_rationale": "Audit: V1 sees means and thresholds, not tails. Volatility is mathematically orthogonal-ish to the mean level",
        "complexity": "low",
    },
    "pressure_pbp": {
        "source": "nflverse PBP flags (sack, qb_hit, qb_dropback)",
        "seasons": "1999+ (built 2018-2026)",
        "timestamp_availability": "play timestamps; week grain",
        "leakage_status": "SAFE -- strictly games with week < W",
        "min_sample": "4 prior games",
        "info_family": "trench process (outcome-flavored)",
        "overlaps_v1": "LOW -- V1 has no sack/hit rates",
        "genuinely_new": "MAYBE -- sack rate is partly an outcome of the same pass game EPA measures",
        "genuinely_new_rationale": "Sacks are EPA events, so some correlation with pass EPA expected; rate form adds process info",
        "complexity": "low",
    },
    "pressure_pfr": {
        "source": "nflverse pfr_advstats weekly (player-grain, aggregated to team-week)",
        "seasons": "2018+ (release tag pfr_advstats; 2026 in-season updating)",
        "timestamp_availability": "week grain; daily cadence in-season; PFR box-score lag ~1 day post-game",
        "leakage_status": "SAFE with lag caveat -- weekly files can lag the weekend; Tuesday-batch consumption recommended (documented)",
        "min_sample": "4 prior games",
        "info_family": "trench process (pressure allowed / generated)",
        "overlaps_v1": "LOW -- V1 has no pressure concept at all",
        "genuinely_new": "LIKELY -- pressure rate is a process signal (how often hurried) vs EPA outcome (how well plays worked)",
        "genuinely_new_rationale": "Feature-discovery audit Tier 1. Caveat: primary-passer proxy (max times_pressured) since attempts unpublished; team sums for defense",
        "complexity": "medium (external pull + player->team aggregation)",
    },
    "special_teams": {
        "source": "nflverse PBP (punt/kickoff/FG/XP plays)",
        "seasons": "1999+ (built 2018-2026)",
        "timestamp_availability": "play timestamps; week grain",
        "leakage_status": "SAFE -- strictly games with week < W",
        "min_sample": "4 prior games (noisy: few ST plays/week -- flagged)",
        "info_family": "third phase (kicking/punting/returns)",
        "overlaps_v1": "NONE -- V1 has zero special-teams representation",
        "genuinely_new": "YES by construction -- but LOW SIGNAL: few plays, high variance; kickoff rules changed 2023/2024/2025 (structural breaks)",
        "genuinely_new_rationale": "Genuinely absent from V1; feasibility limited by sample size and rule breaks",
        "complexity": "low",
    },
    "player_qb": {
        "source": "schedules (home/away_qb_name) + PBP passer + data/qb_point_values.json (2026 poll)",
        "seasons": "QB names 1999+; qb_value_poll 2026-ANCHORED (historical limitation)",
        "timestamp_availability": "schedules name QBs pregame; PBP primary known post-game (used for backup detection with 1-week lag discipline)",
        "leakage_status": "MIXED -- qb_sched is pregame-safe; qb_backup_flag uses played-week PBP (safe at played grain; current-week value is pregame-known via injury report, documented)",
        "min_sample": "n/a (identity features)",
        "info_family": "player-level value (starter vs replacement)",
        "overlaps_v1": "NONE in features (V1 has no QB identity); injury-adjust script 11 is post-processing, not a feature",
        "genuinely_new": "LIKELY for backup flag -- starter/backup is discrete information EPA averages over",
        "genuinely_new_rationale": "Exp 005 tested raw injury COUNTS (failed); this is identity x value, a different representation. qb_value_poll is 2026-anchored: Tier 2 until per-season QB values sourced",
        "complexity": "medium",
    },
    "player_continuity": {
        "source": "nflverse snap_counts release (2012+)",
        "seasons": "2012+ (2026 in-season updating)",
        "timestamp_availability": "week grain; weekly cadence",
        "leakage_status": "SAFE -- prior-season roster from prior-season snaps; current-week shares from games with week < W",
        "min_sample": "4 prior games; needs prior season (2018 pred_weeks use 2017 rosters -- available)",
        "info_family": "roster stability / unit familiarity",
        "overlaps_v1": "NONE",
        "genuinely_new": "MAYBE -- continuity likely correlates with team quality (good teams keep players); needs the uncorrelated filter at modeling stage",
        "genuinely_new_rationale": "New information family, but confounded with strength; treat as Tier 2",
        "complexity": "medium",
    },
    "player_availability": {
        "source": "nflverse injuries release (report_status, date_modified) x snap-count value proxy",
        "seasons": "2009+ (built 2018-2026; 2026 verify on pull)",
        "timestamp_availability": "date_modified per row; week grain with pre-kickoff discipline",
        "leakage_status": "NEEDS DISCIPLINE -- date_modified must be strictly pre-kickoff; week-grain fallback risks using post-game updates. Documented as the highest leakage risk in the build",
        "min_sample": "n/a",
        "info_family": "player value x absence (NOT raw counts)",
        "overlaps_v1": "NONE as a feature",
        "genuinely_new": "MAYBE -- value-weighting is new vs Exp 005 counts, but availability news is fast-priced by the market",
        "genuinely_new_rationale": "Different representation from the failed 005; market-pricing caveat keeps it Tier 2",
        "complexity": "high (name matching snap<->injury is fuzzy; timing discipline required)",
    },
    "matchup": {
        "source": "derived from component features (no new raw data)",
        "seasons": "inherits component coverage (2018+ binding = PFR)",
        "timestamp_availability": "inherits components",
        "leakage_status": "SAFE -- pure function of walk-forward-safe components",
        "min_sample": "inherits components",
        "info_family": "unit-vs-unit interaction structure",
        "overlaps_v1": "NONE -- V1 collapses everything to team differentials before any interaction",
        "genuinely_new": "LIKELY -- this is representation, not just information: A-protection x B-rush cannot be expressed as (A-B) differentials",
        "genuinely_new_rationale": "The architecture audit's structural point: V1's scalar collapse destroys interaction structure. Products/cross-differentials preserve it",
        "complexity": "low (derived)",
    },
    "environment": {
        "source": "nflverse schedules (rest, roof, surface, temp, wind, gametime, div_game) + hardcoded stadium coords",
        "seasons": "1999+",
        "timestamp_availability": "known pregame (weather = forecast at pull time; use Tuesday-pull discipline)",
        "leakage_status": "SAFE except weather -- forecasts update; freeze at prediction time (documented)",
        "min_sample": "n/a",
        "info_family": "game context",
        "overlaps_v1": "PARTIAL -- rest/div_game already in V1 (flagged); travel/altitude/dome/primetime new",
        "genuinely_new": "MIXED -- travel/time-zone previously null (wadefuller 0/4); rest already in V1",
        "genuinely_new_rationale": "Keep for architecture completeness; prior evidence weak for spreads",
        "complexity": "low",
    },
}

FEATURE_DEFS = {
    # possession offense
    "drives": "drives per game (offense)", "points_per_drive": "points per offensive drive (score-delta method)",
    "epa_per_drive": "mean EPA per offensive drive", "start_y100": "mean drive start (yards from own goal: 100 - yardline_100)",
    "three_and_out_rate": "share of drives: <=3 plays ending in punt", "scoring_drive_rate": "share of drives ending TD/FG",
    "rz_trip_rate": "share of drives reaching inside-20", "gtg_td_rate": "TD rate on drives reaching goal-to-go",
    "plays_per_drive": "mean plays per drive", "drive_to_rate": "share of drives ending in turnover",
    # possession defense
    "points_per_drive_allowed": "opp points per drive", "epa_per_drive_allowed": "opp EPA per drive",
    "start_y100_allowed": "mean opp drive start", "three_and_out_forced": "share of opp drives forced 3-and-out",
    "scoring_drive_allowed": "share of opp drives scoring", "rz_trip_allowed": "share of opp drives reaching RZ",
    "drive_to_forced": "share of opp drives ending in turnover",
    # explosiveness
    "expl_pass_rate": "pass plays gaining >=16 yds", "expl_rush_rate": "rush plays gaining >=10 yds",
    "big20_rate": "scrimmage plays gaining >=20 yds", "big40_rate": "scrimmage plays gaining >=40 yds",
    "epa_std": "std of EPA/play (volatility)", "epa_median": "median EPA/play",
    "epa_p10": "10th pct EPA/play (floor)", "epa_p90": "90th pct EPA/play (ceiling)",
    "air_per_att": "mean air yards per pass attempt", "adot": "average depth of target",
    "expl_pass_allowed": "opp explosive pass rate allowed", "expl_rush_allowed": "opp explosive rush rate allowed",
    "big20_allowed": "opp 20+ rate allowed", "big40_allowed": "opp 40+ rate allowed",
    "epa_std_allowed": "opp EPA/play std allowed",
    # pressure pbp
    "sack_rate": "sacks per dropback (offense)", "qb_hit_rate": "QB hits per dropback (offense)",
    "sack_rate_made": "sacks per opp dropback (defense)",
    # pressure pfr
    "pressure_allowed_pct": "primary passer times_pressured_pct (PFR)",
    "sacks_allowed": "team sacks allowed (PFR sum)", "hits_taken": "team QB hits taken",
    "hurries_taken": "team hurries taken", "blitzed_taken": "team times blitzed",
    "pressures_taken": "team times pressured", "drops": "team passing drops",
    "bad_throw_pct": "primary passer bad-throw pct",
    "def_blitzes": "defense blitzes (PFR sum)", "def_hurries": "defense hurries",
    "def_qb_hits": "defense QB hits", "def_sacks": "defense sacks",
    "def_pressures": "defense pressures", "def_missed_tackles": "defense missed tackles",
    "def_adot_allowed": "defense aDOT allowed", "def_ypt_allowed": "defense yards/target allowed",
    "def_prating_allowed": "defense passer rating allowed",
    # special teams
    "st_epa": "total ST EPA (punt+kickoff+FG+XP)", "st_epa_per_play": "ST EPA per ST play",
    "punt_epa": "punt-play EPA", "kick_epa": "FG+XP EPA", "kickoff_epa": "kickoff EPA",
    "fg_make_rate": "field-goal make rate",
    # player
    "qb_backup_flag": "1 if PBP primary passer != scheduled starter",
    "qb_nonqb1_share": "share of dropbacks by non-primary passer (season)",
    "qb_value_poll": "2026-poll starter-minus-backup value (HISTORICAL LIMITATION)",
    "snap_continuity_off": "share of off snaps by prior-season roster players",
    "ol_continuity": "same for T/G/C", "skill_continuity": "same for RB/WR/TE",
    "avail_value_out": "sum of snap-shares of Out/Doubtful players (value-weighted)",
    "avail_n_out": "raw Out/Doubtful count (comparison only)",
    # environment
    "rest_diff": "home_rest - away_rest (days)", "travel_miles_away": "away-city to stadium miles",
    "altitude_game": "stadium >=4000ft", "dome_game": "roof dome/closed",
    "grass_game": "surface grass", "temp_game": "kickoff temp F", "wind_game": "kickoff wind mph",
    "primetime": "late/Monday kickoff", "month": "calendar month",
    "short_week_home": "home rest<=6", "short_week_away": "away rest<=6",
    "off_bye_home": "home rest>=13", "off_bye_away": "away rest>=13",
}

FAMILY_OF = {}
for f in ["drives", "points_per_drive", "epa_per_drive", "start_y100",
          "three_and_out_rate", "scoring_drive_rate", "rz_trip_rate",
          "gtg_td_rate", "plays_per_drive", "drive_to_rate",
          "points_per_drive_allowed", "epa_per_drive_allowed",
          "start_y100_allowed", "three_and_out_forced", "scoring_drive_allowed",
          "rz_trip_allowed", "drive_to_forced"]:
    FAMILY_OF[f] = "possession"
for f in ["expl_pass_rate", "expl_rush_rate", "big20_rate", "big40_rate",
          "epa_std", "epa_median", "epa_p10", "epa_p90", "air_per_att", "adot",
          "expl_pass_allowed", "expl_rush_allowed", "big20_allowed",
          "big40_allowed", "epa_std_allowed"]:
    FAMILY_OF[f] = "explosiveness"
for f in ["sack_rate", "qb_hit_rate", "sack_rate_made", "dropbacks", "sacks",
          "qb_hits", "sacks_made", "qb_hits_made", "dropbacks_faced"]:
    FAMILY_OF[f] = "pressure_pbp"
for f in ["pressure_allowed_pct", "sacks_allowed", "hits_taken",
          "hurries_taken", "blitzed_taken", "pressures_taken", "drops",
          "bad_throw_pct", "def_blitzes", "def_hurries", "def_qb_hits",
          "def_sacks", "def_pressures", "def_missed_tackles",
          "def_adot_allowed", "def_ypt_allowed", "def_prating_allowed"]:
    FAMILY_OF[f] = "pressure_pfr"
for f in ["st_epa", "st_epa_per_play", "punt_epa", "kick_epa", "kickoff_epa",
          "fg_make_rate", "st_plays", "fg_att", "fg_made"]:
    FAMILY_OF[f] = "special_teams"
for f in ["qb_backup_flag", "qb_nonqb1_share", "qb_value_poll",
          "qb1_dropbacks", "qb_dropback"]:
    FAMILY_OF[f] = "player_qb"
for f in ["snap_continuity_off", "ol_continuity", "skill_continuity"]:
    FAMILY_OF[f] = "player_continuity"
for f in ["avail_value_out", "avail_n_out"]:
    FAMILY_OF[f] = "player_availability"
for f in ["rest_diff", "travel_miles_away", "altitude_game", "dome_game",
          "grass_game", "temp_game", "wind_game", "primetime", "month",
          "short_week_home", "short_week_away", "off_bye_home",
          "off_bye_away"]:
    FAMILY_OF[f] = "environment"


def main():
    team = pd.read_parquet(f"{V2}/team_features_pred.parquet")
    games = pd.read_parquet(f"{V2}/games_v2_features.parquet")

    base_cols = [c for c in team.columns
                 if c not in ("team", "season", "pred_week", "hist_games")]
    mx_cols = [c for c in games.columns if c.startswith("mx_")]
    env_cols = [c for c in games.columns if not c.startswith(
        ("game_", "season", "week", "home_", "away_", "mx_"))]

    inventory = []
    for c in base_cols:
        fam = FAMILY_OF.get(c, "unclassified")
        ft = FAMILIES.get(fam, {})
        inventory.append({
            "feature": c, "family": fam,
            "definition": FEATURE_DEFS.get(c, ""),
            "source": ft.get("source", ""),
            "seasons": ft.get("seasons", ""),
            "timestamp_availability": ft.get("timestamp_availability", ""),
            "leakage_status": ft.get("leakage_status", ""),
            "min_sample": ft.get("min_sample", ""),
            "info_family": ft.get("info_family", ""),
            "overlaps_v1": ft.get("overlaps_v1", ""),
            "genuinely_new": ft.get("genuinely_new", ""),
            "genuinely_new_rationale": ft.get("genuinely_new_rationale", ""),
            "complexity": ft.get("complexity", ""),
            "grain": "team x pred_week (expanding mean, min 4 games)",
        })
    for c in mx_cols:
        ft = FAMILIES["matchup"]
        inventory.append({
            "feature": c, "family": "matchup",
            "definition": f"interaction: {'product' if '_x_' in c else 'cross-differential'} of components",
            "source": ft["source"], "seasons": ft["seasons"],
            "timestamp_availability": ft["timestamp_availability"],
            "leakage_status": ft["leakage_status"],
            "min_sample": ft["min_sample"], "info_family": ft["info_family"],
            "overlaps_v1": ft["overlaps_v1"],
            "genuinely_new": ft["genuinely_new"],
            "genuinely_new_rationale": ft["genuinely_new_rationale"],
            "complexity": ft["complexity"],
            "grain": "game (home/away components x matchup pair)",
        })
    for c in env_cols:
        fam = FAMILY_OF.get(c, "environment")
        ft = FAMILIES.get(fam, FAMILIES["environment"])
        inventory.append({
            "feature": c, "family": "environment",
            "definition": FEATURE_DEFS.get(c, ""),
            "source": ft["source"], "seasons": ft["seasons"],
            "timestamp_availability": ft["timestamp_availability"],
            "leakage_status": ft["leakage_status"],
            "min_sample": ft["min_sample"], "info_family": ft["info_family"],
            "overlaps_v1": ft["overlaps_v1"],
            "genuinely_new": ft["genuinely_new"],
            "genuinely_new_rationale": ft["genuinely_new_rationale"],
            "complexity": ft["complexity"], "grain": "game",
        })

    # QB identity columns (game grain, pregame-known with documented caveat)
    qb_id_cols = [c for c in games.columns
                  if c.startswith(("home_qb_", "away_qb_"))]
    QB_ID_TAGS = {
        "home_qb_sched": ("scheduled home starter (pregame-safe)",
                          "SAFE -- schedule fact, known pregame"),
        "away_qb_sched": ("scheduled away starter (pregame-safe)",
                          "SAFE -- schedule fact, known pregame"),
        "home_qb_primary": ("PBP primary passer, current week -- POST-GAME known; "
                            "modeling must substitute pregame injury-report value",
                            "LEAK RISK if used as-is -- replace with pregame source at modeling stage"),
        "away_qb_primary": ("PBP primary passer, current week -- POST-GAME known; "
                            "modeling must substitute pregame injury-report value",
                            "LEAK RISK if used as-is -- replace with pregame source at modeling stage"),
        "home_qb_backup_flag": ("1 if backup started (pregame-known via injury report)",
                                "SAFE when sourced pregame; current-week PBP value is post-game"),
        "away_qb_backup_flag": ("1 if backup started (pregame-known via injury report)",
                                "SAFE when sourced pregame; current-week PBP value is post-game"),
    }
    for c in qb_id_cols:
        defin, leak = QB_ID_TAGS.get(c, ("", ""))
        ft = FAMILIES["player_qb"]
        inventory.append({
            "feature": c, "family": "player_qb", "definition": defin,
            "source": ft["source"], "seasons": ft["seasons"],
            "timestamp_availability": ft["timestamp_availability"],
            "leakage_status": leak,
            "min_sample": ft["min_sample"], "info_family": ft["info_family"],
            "overlaps_v1": ft["overlaps_v1"],
            "genuinely_new": ft["genuinely_new"],
            "genuinely_new_rationale": ft["genuinely_new_rationale"],
            "complexity": ft["complexity"], "grain": "game (current week)",
        })

    json.dump(inventory, open(f"{R}/feature_inventory.json", "w"), indent=1)

    counts = {}
    for it in inventory:
        counts[it["family"]] = counts.get(it["family"], 0) + 1

    # ---------------- data_availability.json ----------------
    avail = {
        "note": "All sources free/keyless. PFR data via nflverse nflverse-data releases (MIT). FTN not used.",
        "sources": [
            {"source": "nflverse PBP (local parquets 2018-2026)",
             "seasons": "1999+ (built 2018-2026)", "cadence": "nightly in-season",
             "families": ["possession", "explosiveness", "pressure_pbp", "special_teams"],
             "status": "FULLY FEASIBLE -- local, 372 cols verified"},
            {"source": "nflverse pfr_advstats (weekly, player-grain)",
             "seasons": "2018+", "cadence": "daily in-season (box-score lag ~1d)",
             "families": ["pressure_pfr"],
             "status": "FEASIBLE -- pulled 2018-2026 to data/v2/raw/; binding constraint on history (2018+)"},
            {"source": "nflverse snap_counts",
             "seasons": "2012+", "cadence": "weekly in-season",
             "families": ["player_continuity", "player_availability(value proxy)"],
             "status": "FEASIBLE -- pulled 2018-2026"},
            {"source": "nflverse schedules",
             "seasons": "1999+", "cadence": "live in-season",
             "families": ["player_qb (names)", "environment"],
             "status": "FEASIBLE"},
            {"source": "nflverse injuries",
             "seasons": "2009+ (2026 verify on pull)", "cadence": "weekly",
             "families": ["player_availability"],
             "status": "PARTIAL -- pulled 2018-2026; name-matching fuzzy; date_modified discipline required (highest leakage risk)"},
            {"source": "data/qb_point_values.json (2026 oddsmaker poll)",
             "seasons": "2026-anchored", "cadence": "static",
             "families": ["player_qb (qb_value_poll)"],
             "status": "LIMITED -- anachronistic for 2018-2025; structural placeholder only; per-season QB values unsourced"},
        ],
    }
    json.dump(avail, open(f"{R}/data_availability.json", "w"), indent=1)

    # ---------------- leakage_audit.md ----------------
    leakage = """# V2 Research -- Leakage & Timestamp Audit

Walk-forward rule (enforced in scripts/35): every team feature for prediction
week W uses only games with week < W (all prior seasons + current season).
MIN_GAMES = 4 prior games else NaN. No offseason mean reset (expanding
all-history); recency weighting is a modeling-stage decision.

## Per-family assessment

### possession / explosiveness / pressure_pbp / special_teams -- SAFE
PBP aggregates over completed games only. Drive points use in-game score
deltas (no future scores). Explosive thresholds (>=16 pass / >=10 rush,
20+/40+) are fixed constants, not tuned.

### pressure_pfr -- SAFE WITH LAG CAVEAT
PFR weekly files can lag the weekend box scores by ~1 day (known nflverse
issue). Consume in the Tuesday batch, not Monday. Primary-passer proxy:
`times_pressured_pct` taken from the max-`times_pressured` player because
attempts are not published in this file -- documented approximation.
Defense sums are exact team sums.

### player_qb -- MIXED
- `qb_sched` (scheduled starter): pregame-safe.
- `qb_backup_flag` at played-week grain: uses played-week PBP -- safe in the
  source table. The CURRENT-week flag for prediction week W must come from the
  pregame injury report, not PBP -- enforced at modeling stage.
- `qb_value_poll`: 2026-anchored, anachronistic for 2018-2025. Labeled
  limitation; do not interpret historically.

### player_continuity -- SAFE
Prior-season roster from prior-season snap counts; current shares from
completed games only.

### player_availability -- HIGHEST RISK, NEEDS DISCIPLINE
`date_modified` must be strictly before the week's first kickoff. The
week-grain fallback (any Out/Doubtful row that week) can include post-game
updates. Modeling stage must enforce the timestamp filter; the source table
retains `date_modified` for this. Name matching (snap `player` vs injury
`full_name`, lowercased/strip) is fuzzy -- unmatched injuries contribute 0
(conservative).

### matchup -- SAFE
Pure functions of walk-forward-safe components. No new raw data.

### environment -- SAFE EXCEPT WEATHER
Rest/roof/surface/division/gametime are schedule facts. `temp_game`/`wind_game`
are forecasts at pull time -- freeze at prediction time (Tuesday pull
discipline, same as Experiment 006). Travel uses hardcoded stadium coords.

## Timestamp summary for the 2026 timing study
All PBP/PFR/snap features are week-grain and timestampable to the Tuesday
batch. Injury features require row-level `date_modified` discipline. Nothing
in this build consumes Experiment 006 observations.
"""
    open(f"{R}/leakage_audit.md", "w").write(leakage)

    # ---------------- architecture.md ----------------
    arch = """# V2 -- Component + Matchup Model: Research Architecture

## Design principle
NOT V1 + residual correction. V2 builds the game prediction from separate
component ratings so unit-vs-unit interactions are visible BEFORE anything is
collapsed to a scalar.

## Component layers (per team, prediction-week grain)
1. **V1 layer (benchmark, frozen):** ELO + EPA + GBM ensemble, HFA, rest,
   division/week -- unchanged, kept as the comparison baseline.
2. **Possession:** points/drive, EPA/drive, drives, start field position,
   3-and-out / scoring-drive / RZ-trip / goal-to-go rates, drive TO rate
   (offense + allowed).
3. **Explosiveness:** explosive pass/rush rates, 20+/40+ rates, EPA/play
   volatility (std, p10, p90, median), air yards, aDOT (offense + allowed).
4. **Trench pressure:** PFR pressure allowed/generated, sacks, hits, hurries,
   blitzes, drops, bad throws, coverage allowed (aDOT/ypT/PRating).
5. **Player:** QB starter identity, backup flag, QB value (2026-poll,
   limited), OL/skill continuity, value-weighted availability.
6. **Special teams:** ST EPA split (punt/kick/kickoff), FG make rate.
7. **Environment:** rest diff, travel, altitude, dome/grass, temp/wind,
   primetime, month.

## Matchup layer (game grain)
Explicit interaction structures, e.g.:
- home pass-protection x away pass-rush (product + cross-differential)
- home explosive pass rate x away explosive pass allowed
- home EPA/drive x away EPA/drive allowed
- home aDOT x away aDOT allowed
- home RZ-trip rate x away RZ-trip allowed
- home start field position x away start field position allowed
- home pressure allowed x away defensive pressures
- home sack rate x away sacks made
- home points/drive x away points/drive allowed
Raw scale in the research tables; standardization is a modeling-stage choice.

## Game model (to be designed at modeling stage -- NOT built here)
Components + matchups + environment -> expected_home_margin.
Planned controlled comparisons (require separate authorization):
- V2-A: component architecture only (no matchup interactions)
- V2-B: + matchup interactions
- V2-C: + player/QB layer
- V2-D: + pressure/explosiveness/possession layers
- V2-E: full V2
Same walk-forward protocol, same validation, vault untouched until gates pass.

## Variance target (future -- NOT built here)
Second target: Var(margin) / margin distribution, so the model can express
"expected +4 but highly volatile" vs "expected +4 and stable". PFR's
win-probability methodology treats margin as a distribution with ~13-14 pts
SD -- the scalar point estimate is the binding constraint the audit found.
The research tables already carry volatility features (epa_std, epa_p10/p90,
explosive rates) that feed this target later.

## What this architecture changes vs V1
V1: team ratings -> scalar differential -> margin.
V2: unit ratings -> unit-vs-unit matchups -> margin (+ variance later).
Information the scalar collapse destroys (protection-vs-rush, explosiveness
shape, possession structure) is preserved until the game model.
"""
    open(f"{R}/architecture.md", "w").write(arch)

    # ---------------- REPORT.md ----------------
    n_feat = len(inventory)
    lines = [f"# V2 Research Architecture -- Build Report",
             "",
             "READ-ONLY research build. No models trained, no validation evaluated,",
             "no 2026 Experiment-006 data used, 2023-2025 vault untouched, V1 untouched.",
             "",
             "## What was built",
             f"- **{n_feat} features** inventoried across {len(counts)} families",
             "- Build scripts: `scripts/30_v2_pull_sources.py` (acquisition),",
             "  `scripts/31_v2_features_pbp.py` (possession/explosiveness/PBP-pressure/ST),",
             "  `scripts/32_v2_features_pfr.py` (PFR pressure),",
             "  `scripts/33_v2_features_player.py` (QB/continuity/availability),",
             "  `scripts/34_v2_features_env.py` (environment),",
             "  `scripts/35_v2_assemble.py` (walk-forward assembler),",
             "  `scripts/36_v2_inventory.py` (this inventory).",
             "- Data tables: `data/v2/team_week_*.parquet` (played-week source),",
             "  `data/v2/team_features_pred.parquet` (pred-week grain),",
             "  `data/v2/games_v2_features.parquet` (game grain, 2018-2022 only).",
             "- Docs: `v2_research/{architecture.md, feature_inventory.json,",
             "  data_availability.json, leakage_audit.md, REPORT.md}`.",
             "",
             "## Features per family"]
    for fam in sorted(counts):
        lines.append(f"- {fam}: {counts[fam]}")
    lines += ["",
              "## Feasibility summary",
              "- FULLY FEASIBLE: possession, explosiveness, PBP pressure proxies, special teams (PBP local);",
              "  PFR pressure (pulled 2018-2026); snap-count continuity; schedules env; QB identity.",
              "- PARTIAL / NEEDS DISCIPLINE: value-weighted availability (fuzzy name match, date_modified",
              "  discipline required -- highest leakage risk); weather (freeze-at-prediction-time).",
              "- LIMITED: `qb_value_poll` is 2026-anchored (anachronistic pre-2026); per-season QB values",
              "  unsourced. Special teams: few plays/week (noisy) + kickoff rule breaks 2023/2024/2025.",
              "- HISTORY BOUND: PFR pressure starts 2018 (matches train window); FTN/participation excluded",
              "  (2022+/post-season-only -- incompatible with walk-forward).",
              "",
              "## Genuinely new vs V1 (audit's uncorrelated-with-ELO/EPA filter)",
              "- LIKELY NEW: possession structure, explosiveness shape, PFR pressure process, matchup",
              "  interactions (representation, not just information), QB backup identity.",
              "- MAYBE (needs the filter at modeling stage): PBP sack rates, continuity (confounded with",
              "  strength), value-weighted availability (market prices news fast).",
              "- WEAK PRIORS: travel/time-zone, special teams (noisy).",
              "",
              "## What must be resolved before V2-A..E comparisons",
              "1. Per-season QB value sourcing (or drop `qb_value_poll` from historical modeling).",
              "2. Injury timestamp discipline enforced in the modeling pipeline (date_modified < kickoff).",
              "3. PFR lag discipline: consume in Tuesday batch, not Monday.",
              "4. Cold-start policy for pred_weeks 1-4 (MIN_GAMES=4 -> NaN; modeling must define fallback).",
              "5. Matchup standardization choice (raw products now; z-score at modeling stage).",
              "6. Human authorization of the V2-A..E comparison protocol (gates, metrics, baselines).",
              "",
              "V2-A through V2-E are NOT authorized by this build."]
    open(f"{R}/REPORT.md", "w").write("\n".join(lines) + "\n")
    print(f"wrote inventory: {n_feat} features")
    for fam in sorted(counts):
        print(f"  {fam}: {counts[fam]}")


if __name__ == "__main__":
    main()
