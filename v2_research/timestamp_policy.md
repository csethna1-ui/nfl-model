# V2 Timestamp Policy

Date: 2026-09-29. Frozen for the research protocol. This is the single
authoritative statement of what "available at prediction time" means for V2.

## 1. The prediction information set

V2's research information set is the **Tuesday-AM set**, matching the
standing `22_tuesday_snapshot` / `nfl-timing-tuesday-snapshot` convention:

- **Prediction cutoff (Tuesday):** `08:00 ET on the most recent Tuesday
  strictly before the team's kickoff.`
  - Sunday game → cutoff is 5 days prior. Thursday game → 2 days prior.
    Monday game → 6 days prior.
- **Prediction cutoff (Friday, where an experiment type requires it):**
  `23:59:59 ET on the most recent Friday strictly before kickoff`, for games
  not yet played Friday evening.

Every feature, scaler, imputation statistic, and prior used for a prediction
must be computed exclusively from information with timestamps strictly before
the applicable cutoff.

## 2. Per-source timestamp rules

| Source | Rule |
|---|---|
| nflverse PBP (drives, EPA, explosiveness, pressure proxies, ST) | Play timestamps; week grain. PBP for week W−1 games is complete well before the Tuesday snapshot (games finished Sunday/Monday night). Usable through week W−1. |
| PFR advanced stats (all 17 `pressure_pfr` features) | **Lag one week.** PFR's advanced stats do not fully update until the Wednesday morning after the weekend's games (PFR's own statement). At the Tuesday 08:00 ET snapshot, week W−1 is incomplete. Usable only through week W−2. The stored `team_week_pfr.parquet` was built from complete files and must be shifted (week W ← rows ≤ W−2) before any walk-forward use. |
| Injury reports (`avail_*`) | Row-level rule: `date_modified < min(prediction_cutoff, team_game_kickoff)`. 2018–2024 files carry `date_modified`; 2025/26 files do not, and are unusable for availability features. Empirical consequence: at the Tuesday cutoff, 0% of 2021–2022 Out/Doubtful rows are knowable (report cycle starts Wednesday) — Tuesday-set availability is identically zero. |
| QB identity (`qb_sched`) | Schedules name QBs pregame — pregame-safe. Mid-week changes are handled downstream by the script-11 stale-news filter convention, not by the research features. |
| QB value (`qb_value_historical`) | Built only from games strictly before the prediction week (script 37). The `qb_pressured_pct_rw` component inherits the PFR one-week lag (Friday-safe only). |
| Schedules / rest / environment | Schedule facts (dates, rest days, stadium, roof/surface) are known far in advance — pregame-safe. Weather: 36.8% missing; no imputation policy frozen (documented limitation). |
| Snap counts / continuity | Prior-week snap counts publish before the Tuesday snapshot — usable through week W−1. |

## 3. The "knowable" doctrine

"Eventually known before kickoff" ≠ "knowable at prediction time." The
policy enforces the latter:

- A player ruled Out on Friday was eventually known before Sunday's kickoff
  but is **excluded** from the Tuesday set (correctly).
- A Saturday downgrade (e.g. Minkah Fitzpatrick, PIT 2022 W10, Out stamped
  Sat 16:50 ET) is known ~20h before kickoff but **excluded** from both the
  Tuesday and Friday sets (correctly).
- Never substitute "the weekly file was eventually updated" for "the row's
  timestamp precedes the cutoff." The 2025/26 injury files (no timestamps)
  are therefore unusable — there is no honest fallback.

## 4. Scaling / imputation / prior timestamps

Per `standardization_spec.md`: scaling parameters μ,σ are estimated over
S(W) = league games with kickoff strictly before the Tuesday prediction-date
batch (expanding, |S(W)| ≥ 30, plus the ≥4-prior-games component gate).
Imputation uses walk-forward medians over the same set. No full-sample
statistic may enter any prediction.

## 5. What this policy does not cover

- Totals/clock/projection markets: out of scope (V2 predicts margin only).
- The live 2026 Friday stream (Experiment 006): separate prospective
  protocol; its observations are never training/selection inputs.
- Vault-phase (2023–2025) feature construction: same frozen rules, applied
  at the single locked evaluation — no inspection of vault outcomes before
  or during construction.
