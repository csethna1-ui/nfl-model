# RECONSTRUCTABILITY AUDIT — Props Experiment 005: Player Role Transition

**Status: COMPLETE — verified read-only 2026-10-01. No fitting, no model changes, no locked-test computation.**
**Purpose:** Before designing the Experiment 005 candidate list, verify which role/opportunity signals can actually be reconstructed historically at Friday 18:00 CT prediction timing for the dev (2021–2022) and locked-test (2023–2024) periods. "As-of OK" = the value reflects only information knowable at the cutoff.

## Verdict summary

| Signal | Reconstructable historically? | Source | As-of OK? |
|---|---|---|---|
| Team per player-week / team changes | **YES** | `data/player_games.parquet` (2018–2026), `team` column | Yes — trailing completed games only |
| Games played with current team | **YES** | Derived from team stints in `player_games.parquet` | Yes |
| Current-team carries / targets / touches | **YES** | `player_games.parquet` (attempts, targets, touches columns) | Yes |
| Current-team efficiency (ypc, ypt, catch rate) | **YES** | Derived from the above | Yes |
| Snap counts / snap share | **YES** | `data/v2/raw/snap_counts_<season>.csv`, 2018–2026 (`offense_snaps`, `offense_pct`) | Yes — post-game release, trailing only |
| Red-zone usage (rush att / targets inside 20) | **YES** | Derivable from `data/pbp_<season>.parquet` (2018–2025) | Yes — trailing only |
| Routes / route participation | **NO** | — | — |
| Depth-chart position (RB1/2/3, WR1/2/3/4) | **NO (historical) / YES (2026 only)** | `data/prod_aux_depth_charts.parquet` covers **2026 only** (208 snapshot timestamps, all Aug–Sep 2026) | N/A historically |
| Market line as feature | **EXCLUDED** | Leakage rule (003 §2 precedent) | — |

## Detail

### Team changes — YES
`player_games.parquet` carries `team` per player-week for 2018–2026. Team stints are derived by comparing each game to the player's most recent prior game (`new_stint = team != prev_team`). All values are completed-game records, so trailing use at the Friday cutoff is timestamp-safe. No intraday timing problem exists here — unlike depth charts, there is no "as-of Friday" ambiguity for completed games.

### Current-team opportunity — YES
Carries (`rushing_attempts`-family columns), targets, touches are all present per player-week in the same table. Current-team trailing aggregates (EWMA over games within the current stint) are computable for every prediction week. Efficiency (yards per carry, yards per target) likewise.

### Snap counts / snap share — YES
`data/v2/raw/snap_counts_2018.csv` … `snap_counts_2026.csv` provide per-player-game `offense_snaps` and `offense_pct` (share of team offensive snaps). Weekly releases are post-game, so strictly-prior-week trailing values are Friday-cutoff safe (same convention as the 003A audit).

### Red-zone usage — YES
`data/pbp_2018.parquet` … `pbp_2025.parquet` support deriving carries and targets inside the 20 (and inside the 10) per player-week. Standard derivation; no new data needed.

### Routes — NO (confirmed, not re-litigated)
The 003A preregistration freeze note stands: no keyless source for route participation. Snap share + NGS intended-air-yard share remain the documented proxies. 005 does not reopen this.

### Depth charts — NO for the locked test (the finding this audit was ordered to produce)
`data/prod_aux_depth_charts.parquet` contains 585,690 rows across 208 distinct snapshot timestamps — **all in 2026** (2026-08-19 through 2026-09-30). There are **no historical depth-chart snapshots** for 2021–2024, and no keyless nflverse depth-chart history exists locally. The `pos_rank` field (1, 2, 3…) does give RB1/RB2/RB3-style ordering within formation groups — but only for the 2026 season.

**Design consequence (binding):** any candidate that requires historical depth-chart position (Cale's candidate C as originally sketched — "explicit depth-chart/current-role signal") **cannot be evaluated on the locked test** and is therefore **excluded from the frozen 005 ladder**. It is retained as a 2026-prospective-only research candidate: depth charts exist for the live season, so role-rank signals can be built into the 2026 monitoring stream and evaluated prospectively — but they cannot be part of a preregistered historical experiment without inventing history.

This is exactly the trap the audit was ordered to avoid: 2026 role reconstruction is beautiful; historical role reconstruction via depth charts does not exist.

### As-of timing notes
- All "YES" signals above are trailing completed-game values → no Friday-cutoff leakage by construction.
- Injury-role states (returning from injury, etc.) can use the 002 Family L as-of convention (`date_modified <= Friday 18:00 CT`), which measures feed-available injury information. Available if a candidate needs it; not required for the core ladder.
- The market line is **never a feature** (leakage rule). The Rodriguez 39.7-yard gap is the motivating diagnostic, not an input.

## Transfer population sizing (locked test 2023–2024, RB/WR/TE)

Derived from `player_games.parquet` team stints (audit-order estimates; exact evaluated n comes from the frozen pipeline's eligibility rules):

| Slice | Player-games |
|---|---|
| All skill player-games (RB/WR/TE) | ~2,832* |
| In transfer stints (player changed teams) | 566 |
| Transfer stint, games 1–3 with new team | 287 |
| Transfer stint, games 4–6 with new team | 86 |
| Transfer stint, games 7+ | 193 |
| Unique transferring players | 222 |

\* `player_games.parquet` coverage is a subset of all NFL player-games; the frozen pipeline's eligible population will differ. These are order-of-magnitude checks, not the preregistered n.

**Power implications for the preregistration:**
- Overall population: well-powered for the standard bar.
- Transfer-stint population (566 pooled, ~283/season): adequate for a co-primary bar.
- Stint games 1–3 (287 pooled, ~143/season): per-season slices borderline — pooled inference is fine, per-season reported as exploratory if <150.
- Stint games 4–6 (86 pooled): **underpowered** — diagnostic only, never a win/loss slice.
- QB team changes are rare; the passing-yards transfer slice will likely be underpowered — reported as such, not forced.

## What this audit does not do
No features were constructed, no parameters estimated, no 2023–2024 outcomes touched. The next step is the draft preregistration, whose candidate list is constrained to the "YES" rows above.
