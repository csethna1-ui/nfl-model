# PREREGISTRATION — Experiment 010: Historical Inactives (Information-Timing Measurement)

**Status: FROZEN — APPROVED by Cale 2026-10-01 11:20 CDT.** Both judgment calls
approved as written: (1) no dev gate — the 2021–2022 coefficient is estimated
mechanically and frozen, the test runs once regardless; (2) market-gap
attribution stays secondary and caveated — no tradable-market claim; the
primary result is strictly inactive burden → V1 prediction error. Three
missing team-games excluded, no imputation. V1 untouched. The 2023–2025 locked
test may be touched exactly once, for this protocol only.

## 1. Research question (binding)

> How much incremental predictive information does the final historical
> inactive information contain relative to the information available at our
> existing V1 freeze?

NOT: "can we improve V1 by throwing every injury variable into it." This is a
measurement of timing information, not a model-fitting exercise. It does not
prove PFT or inactives improve predictions — it quantifies the information
content of the T-90 inactive list against a fixed baseline.

## 2. Why this experiment is allowed

- **Phase 2 (injury adjustment, NULL 2026-09-30) is untouched.** Phase 2 asked
  whether Friday-cutoff injury-report formulations improve V1's prediction and
  answered null for its five prespecified families. Cale's 2026-09-30 decision
  ("do not fit additional injury specifications, tune thresholds, or search
  for alternative injury formulations after seeing these development results")
  prohibits *searching for a better injury model*. This experiment does not
  search: it specifies **one** frozen burden variable, estimates **one**
  prespecified coefficient, reports it with uncertainty, and stops. No
  candidate set, no selection, no threshold tuning, no retry-if-null.
- **The data is new relative to V1's freeze.** V1's walk-forward features use
  only data through the prior week — zero current-week injury information of
  any kind (confirmed in `scripts/04_backtest.py`). The T-90 inactive list is
  strictly post-cutoff information by the institutional fact (released 90
  minutes before kickoff, always after Friday 18:00 CT). Game-mapping suffices
  for the timing claim; no per-row timestamp is needed.
- **The research freeze (2026-09-29)** closed better math on the same free
  pregame information. Gameday inactive lists are a *new information source*
  not present in V1's feature set, same standing as Phase 2's justification.
- **PFT combination is explicitly out of scope** ("eventually," per Cale
  2026-10-01). This experiment measures the inactive list alone.

## 3. Data (all reconstructable, keyless — probe 2026-10-01)

| Element | Source | Verdict |
|---|---|---|
| Gameday inactive lists, 2021–2025 REG | nflverse weekly rosters, `status == 'INA'` | RECONSTRUCTABLE — 99.9% team-game coverage; 3/3 games validated name-for-name vs 4for4's independent gameday lists |
| Friday injury-report baseline (`report_status`, `date_modified`) | nflverse `import_injuries` | RECONSTRUCTABLE — 11,269 rows (21–22) + 17,882 rows (23–25) |
| Frozen V1 walk-forward margins | `data/games_with_preds.parquet` | In repo |
| Snap shares (burden weights) | nflverse snap counts, season-to-date through prior week | Build asserts ≥99% coverage on dev, else STOP and return to Cale (data-availability gate, not an outcome gate) |
| Timestamped intraday historical lines | — | NOT RECONSTRUCTABLE — only undated `spread_line` snapshots; Exp 006 backfill found zero A-class Friday lines |

**Exclusions (prespecified):** the 3 team-games missing INA rows (2021 W16 LAC,
2025 W1 NYG, 2025 W1 WAS) are excluded entirely — no imputation. Postseason
excluded. Tie games handled by the MAE metric naturally (no special-casing).

## 4. Primary specification (frozen, one variable)

For each team-game, the **inactive burden**:

```
burden_team = Σ snap_share_i  over players with status == 'INA'
```

- `snap_share_i` = the player's offensive/defensive snap share over the
  trailing 4 weeks through the prior week (frozen; playing time, not an
  outcome; no current-week information).
- Signed from the home perspective: `BURDEN = away_burden − home_burden`
  (positive = away team more depleted → favors home margin), matching the
  lab's sign convention.
- One variable. One coefficient. No position groups in the primary spec, no
  transformations, no interactions.

**Estimation (dev 2021–2022, frozen before test):** OLS of the V1 residual
`r = actual_margin − v1_margin` on `BURDEN` with intercept. The slope β̂ is the
measuring instrument. Applied frozen to the locked test:
`adj_margin = v1_margin + β̂·BURDEN`.

**No dev gate is proposed.** The dev fit is mechanical (it produces the frozen
coefficient), not a selection step — the test runs once regardless of the dev
outcome, because "no detectable information on fresh data" is itself the
answer to the research question. (Rationale: a dev-outcome gate would be
selection; the 2023–2025 window was already opened once under 009's own
preregistration, so the marginal vault cost of one prespecified measurement
is low.)

## 5. Primary metric, bar, decision rule

- **Metric:** ΔMAE = MAE(V1) − MAE(V1 + β̂·BURDEN) on the 2023–2025 locked test
  (n≈816 REG games), with a 95% paired CI (paired by game).
- **Bar (material):** ΔMAE ≥ 0.15 (the lab's standard bar, same as Phase 2)
  **and** the 95% paired CI excludes zero.
- **Reading the outcome:**
  - Pass → the T-90 inactive list carries material incremental information vs
    the V1 freeze; proceed to the timing-chain decomposition (PFT × inactives
    × market) as a follow-up design.
  - Null → the inactive list, as of the final T-90 announcement, contains no
    material incremental information beyond V1's freeze. Narrow claim only:
    it does not rule out finer formulations, and it does not claim "injuries
    don't matter."

## 6. Secondary analyses (preregistered, not gated)

- **S1 — known-vs-new decomposition.** Split BURDEN into players already
  listed Out on the final Friday injury report vs players newly inactive after
  Friday (Questionable/Doubtful→INA, or never on the report). Report each
  component's association with the V1 residual (descriptive; speaks to
  Cale's known-injury → official-inactive link).
- **S2 — base rates.** Fraction of gameday inactives already Out on Friday;
  distribution of BURDEN; how often the surprise component is nonzero.
- **S3 — by position group** (QB, OL, SKILL, FRONT7, DB, ST — Phase 2's locked
  groups), descriptive only. No selection, no "best group" claim.
- **S4 — market-gap exploratory (heavily caveated).** Compare MAE(V1),
  MAE(V1+β̂·BURDEN), MAE(undated `spread_line`) on the locked test. IF the
  inactive adjustment narrows the V1-vs-market gap, timing *plausibly*
  explains up to that share of the gap — but the undated-line caveat (Exp 004,
  carried through 009) forbids a clean attribution. Reported as
  suggestive-only, never as tradable edge.

## 7. What this experiment will not claim

- It will not claim the inactive list (or any adjustment) is a tradable edge.
- It will not re-litigate Phase 2's null or search its neighborhood.
- It will not combine with PFT (reserved for a follow-up design).
- The market-reaction leg of the timing chain (official inactive info →
  market reaction) is documented as **inaccessible-only** for the historical
  window: timestamped intraday lines are not reconstructable. The 2026 Friday
  prospective stream (measurement only) is the future route to that leg.

## 8. Approval gate

Cale's approval of this document freezes: the BURDEN definition (§4), the
dev-fit-once procedure, the ΔMAE ≥ 0.15 + CI-excludes-zero bar (§5), the
secondary set (§6), and the no-dev-gate discipline. After freezing, the build
script asserts data availability on dev, fits the single coefficient, applies
it once to the locked test, and reports. Any deviation returns to Cale before
the test is touched.
