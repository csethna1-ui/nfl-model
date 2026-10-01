# V2 Feature-Family Overlap Matrix

DIAGNOSTIC ONLY — 2021–2022, n=569 games. No predictive evaluation, no model comparison, no gate pass/fail on any model.

Family score = mean of z-scored (home − away) differentials across the family's numeric features (matchup uses game-level mx_* interactions). Z-scores computed across the 2021–2022 sample as a descriptive summary.

## Core correlation matrix

| | V1 | ELO | EPA | Matchup | Possession | Explosive | Pressure | QB |
|---|---|---|---|---|---|---|---|---|
| V1 | 1.000 | 0.932 | 0.942 | 0.514 | 0.438 | 0.423 | -0.096 | 0.064 |
| ELO | 0.932 | 1.000 | 0.763 | 0.550 | 0.487 | 0.454 | -0.094 | 0.045 |
| EPA | 0.942 | 0.763 | 1.000 | 0.413 | 0.337 | 0.337 | -0.094 | 0.069 |
| Matchup | 0.514 | 0.550 | 0.413 | 1.000 | 0.625 | 0.796 | -0.106 | -0.085 |
| Possession | 0.438 | 0.487 | 0.337 | 0.625 | 1.000 | 0.731 | -0.055 | 0.129 |
| Explosive | 0.423 | 0.454 | 0.337 | 0.796 | 0.731 | 1.000 | 0.035 | -0.017 |
| Pressure | -0.096 | -0.094 | -0.094 | -0.106 | -0.055 | 0.035 | 1.000 | 0.081 |
| QB | 0.064 | 0.045 | 0.069 | -0.085 | 0.129 | -0.017 | 0.081 | 1.000 |

## Correlation of each family score with V1 / ELO / EPA

| family | r(V1) | r(ELO) | r(EPA) |
|---|---|---|---|
| environment | -0.056 | -0.045 | -0.063 |
| explosiveness | 0.423 | 0.454 | 0.337 |
| matchup | 0.514 | 0.55 | 0.413 |
| player_availability | -0.118 | -0.145 | -0.076 |
| player_continuity | 0.376 | 0.462 | 0.249 |
| player_qb | 0.064 | 0.045 | 0.069 |
| possession | 0.438 | 0.487 | 0.337 |
| pressure | -0.096 | -0.094 | -0.094 |
| pressure_pbp | -0.061 | -0.029 | -0.089 |
| pressure_pfr | -0.124 | -0.163 | -0.08 |
| special_teams | 0.031 | 0.037 | 0.022 |

## Coverage

| family | features used / total | median non-NaN frac |
|---|---|---|
| environment | 14/14 | 1.0 |
| explosiveness | 15/15 | 1.0 |
| matchup | 32/32 | 1.0 |
| player_availability | 2/2 | 1.0 |
| player_continuity | 3/3 | 1.0 |
| player_qb | 18/26 | 1.0 |
| possession | 17/17 | 1.0 |
| pressure_pbp | 9/9 | 1.0 |
| pressure_pfr | 17/17 | 1.0 |
| special_teams | 9/9 | 1.0 |

## Interpretation

**The families are not one latent variable.** V1/ELO/EPA form the familiar
tight cluster (V1–ELO 0.932, V1–EPA 0.942, ELO–EPA 0.763), but the new
families spread across the full range:

- **Pressure (−0.10 with V1) and QB (0.06 with V1) are essentially orthogonal
  to the latent team-strength axis.** These are the two families most likely
  to carry information V1 cannot represent. (Caveat: the QB family score is
  built from the current inventory's QB features — scheduled identity,
  backup flags, hit rates, and the quarantined poll — not from the historical
  QB value of blocker 1, which does not exist yet. The score's near-zero
  correlation partly reflects that these are identity/availability markers,
  not quality ratings. Recompute after blocker 1 lands.)
- **Matchup / Possession / Explosive form a correlated cluster**
  (Matchup–Explosive 0.80, Matchup–Possession 0.63, Possession–Explosive 0.73;
  each correlates 0.42–0.51 with V1). This is expected, not a flaw: the
  matchup interactions are constructed *from* the possession/explosiveness/
  pressure team features, so they share inputs. The structural claim of the
  matchup family was never "independent inputs" — it is "interaction structure
  V1's scalar collapse destroys." The matrix cannot confirm or deny that
  claim; only the V2-B experiment can. Per Cale's refined filter, their
  correlation with the strength axis is a prioritization note, not a reason
  to drop them.
- **Continuity (0.38 with V1) and special teams (0.03), environment (−0.06),
  availability (−0.12)** sit in between: weakly related to the strength axis.
- **A methodological note on the matchup score:** the mx_* features are
  side-specific (`_homeoff` favors home, `_awayoff` favors away); the score
  flips `_awayoff` variants to home-margin perspective before averaging.
  An earlier unflipped version produced a spurious ~0.00 correlation — a
  reminder that family-level aggregates need sign discipline, which is now
  documented in the script.

**Priority ranking for orthogonal information (priority, not exclusion):**
1. Pressure, 2. QB (pending blocker 1's historical value), 3. Special teams /
   availability / environment (weakly correlated), 4. Matchup / possession /
   explosiveness (correlated cluster — test is whether interaction structure
   adds information *conditional* on the strength axis, i.e. V2-B/D).
