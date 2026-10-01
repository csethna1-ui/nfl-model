# V2 -- Component + Matchup Model: Research Architecture

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

## Data flow (scripts 30–36, all under scripts/)
- `30_v2_pull_sources.py` — downloads 45 PFR advstats + snap-count + injury raw files
  (2018–2026) to `data/v2/raw/`. Source availability only; no evaluation.
- `31_v2_features_pbp.py` — drive-level PBP aggregation → `data/v2/team_week_pbp.parquet`
  (2744 × 53, 2018–2022). Verified: 3-and-out 19.6%, ST EPA attribution, pts/drive 1.93.
- `32_v2_features_pfr.py` — PFR weekly advstats → `data/v2/team_week_pfr.parquet`
  (2018–2022). Pressure allowed 22% median. Binding history constraint: PFR series starts 2018.
- `33_v2_features_player.py` — QB identity/backup, snap continuity, value-weighted
  availability → `data/v2/team_week_player.parquet` (2018–2022). 2025/2026 injury files lack
  `date_modified` (schema change, documented).
- `34_v2_features_env.py` — rest/travel/weather/context → `data/v2/game_env.parquet`
  (1372 × 19, 2018–2022). Neutral-site travel uses home-stadium coords (limitation).
- `35_v2_assemble.py` — walk-forward expanding means (min 4 games) →
  `team_features_pred.parquet` (team pred-week grain) and
  `games_v2_features.parquet` (1372 games × 223 cols, 2018–2022).
- `36_v2_inventory.py` — writes `v2_research/feature_inventory.json` (144 features),
  `data_availability.json`, `architecture.md`, `leakage_audit.md`.

## Feature count by family (144 total, 0 unclassified)
| family | n | status |
|---|---|---|
| matchup (interactions) | 32 | fully feasible, structurally new |
| player_qb | 26 | feasible; current-week identity needs pregame substitution |
| pressure_pfr | 17 | fully feasible |
| possession | 17 | fully feasible |
| explosiveness | 15 | fully feasible |
| environment | 14 | feasible; weather 36.8% missing, neutral-site coords limited |
| pressure_pbp | 9 | fully feasible |
| special_teams | 9 | fully feasible |
| player_continuity | 3 | fully feasible |
| player_availability | 2 | LIMITED — needs pregame-cutoff injury pipeline |

## Families most likely independent of ELO/EPA (per V1 architecture audit)
The audit found V1's components are three views of one latent team-strength axis
(error corr ~0.95) and V1 errors correlate 0.967 with market errors — only information
uncorrelated with ELO/EPA can move the residual. Ranked by likely independence:
1. **Matchup interactions** — unit-vs-unit structure (protection×rush, explosiveness×coverage)
   is destroyed by V1's scalar collapse; structurally new even though inputs are derived.
2. **Possession/drive structure** — V1 knows EPA/play outcomes, not how drives are built
   (3-and-outs, RZ trips, start field position, scoring-drive conversion).
3. **Explosiveness distribution shape** — volatility (epa_std, p10/p90, big-play rates) is
   orthogonal to mean EPA by construction; also feeds the future variance target.
(Honorable mention: trench pressure from PFR — process-flavored, but correlated with EPA outcomes.)
