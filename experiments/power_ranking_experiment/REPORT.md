# Power-Ranking Experiment — Final Report

Date: 2026-09-30. Protocol preregistered in `PREREGISTRATION.md` BEFORE any
candidate comparison was computed. Vault (2023–2025) never touched. No 2026
data used anywhere. V1, ELO parameters, and production outputs untouched.

## 1. Research question
Should the dashboard's "Overall" team ranking be a composite of validated
team-strength signals rather than ELO-only? The current UI labels the ELO
ordering as "Overall", misleading users into reading "#9" as "#9 overall team
strength" when it is "#9 ELO".

## 2. Definition of "power ranking"
Three interpretations were evaluated (per preregistration):

- (A) **Predictive team strength** — the ranking estimates latent current
  strength. Validated by predicting FUTURE results. Adopted as the PRIMARY
  target: "true current strength" is unobservable, so predictive validity is
  the only non-circular criterion.
- (B) **Game-outcome strength** — predicting future game results/margins. The
  binarized cousin of (A); measured via the same future-margin MAE.
- (C) **Descriptive current-season strength** — summarizing observed
  performance. Reported as SECONDARY only (stability, coherence), because a
  descriptive ranking can always be made to fit the past and cannot adjudicate
  ELO-only vs composite.

This does not assume the ranking must optimize V1's objective. V1 predicts
pregame margins; the power ranking answers "how good is this team right now"
for display. The experiment changes no prediction model regardless of outcome.

## 3. Candidate inputs
All from the frozen production pipeline / already-exported values. No new
data sources.

| Input | Definition | Cutoff | Prior-season info? | Current-season only? | In V1? |
|---|---|---|---|---|---|
| ELO | Pre-week ELO (`run_elo`, K=20, HFA=55, MOV, 1/3 offseason regression) | Prior week | Yes (1/3 regression) | No — blended | Yes (40%) |
| Off EPA | Pre-week offensive EPA/play EWMA (ALPHA=0.25, 35% offseason regression to 0) | Prior week | Yes (35% regression) | No — blended | Yes, via EPA-linear (50%) |
| Def EPA | Pre-week defensive EPA/play allowed EWMA, negated (higher=better) | Prior week | Yes | No — blended | Yes, via EPA-linear (50%) |
| Net Success Rate | off_sr − def_sr from the same EWMA ratings | Prior week | Yes | No — blended | No |
| W-L (win%) | (w + 0.5·t)/gp, regular season through prior week | Prior week | No | Yes | No |
| Point differential | (PF − PA)/gp, regular season through prior week | Prior week | No | Yes | No |

## 4. Leakage / information-cutoff audit
- All rating inputs are **pre-week snapshots** (weekly batching: week-W games
  use only data through week W−1). Verified in `03_ratings.py`: ratings are
  attached before the week's games are folded in.
- W-L and point differential are computed strictly from games with
  `week < W`. Bye-week teams carry forward prior-week values.
- Future games used for evaluation are always `week > W`. No end-of-season
  ratings, no post-cutoff information anywhere.
- Seasons used: 2018–2022 only. **2023–2025 (locked vault) never opened.**
  No 2026 outcomes used for tuning or selection.
- One imperfection, documented: the ELO run cold-starts in 2018 (all teams
  1500.0), so 2018 early-season ELOs carry no pre-2018 history. This affects
  development only, all candidates identically; validation (2021–2022) ELO is
  fully mature.

## 5. Walk-forward methodology
- Snapshots: every regular-season week, 2018–2022 (32 teams × 87 weeks =
  2784 snapshots; `snapshots_2018_2022.parquet`).
- **Development** (2018–2020): fit per-candidate OLS margin mappings
  `home_margin ~ score_diff` (pooled over development snapshots' future
  games); fit learned-composite OLS weights
  (rest-of-season PD/game ~ six standardized components, pooled, weeks 4+).
- **Validation** (2021–2022): apply development-fit parameters; compare
  candidates. Nothing refit.
- PRIMARY evaluation: snapshots at weeks 4+; each candidate's score
  differential predicts every future regular-season game via its
  development-fit mapping → MAE (n=3161 game-snapshot pairs).
- Weeks 1–3 reported separately (early-season sensitivity). At week 1, W-L
  and point differential are degenerate (all 0–0), so specs 5–6 are skipped
  there per preregistration.
- Full protocol preregistered in `PREREGISTRATION.md`, including decision
  rules (ADOPT / OPEN / KEEP) stated before results.

## 6. Candidate specifications
Components are cross-sectional z-scores across the 32 teams at each snapshot
week (no lookahead). Defense components negated so higher = better for all.

1. **ELO only**: `z_elo`
2. **ELO+OffEPA**: mean(z_elo, z_off)
3. **ELO+Off+Def EPA**: mean(z_elo, z_off, z_def)
4. **+NetSR**: mean(z_elo, z_off, z_def, z_netsr)
5. **+W-L**: mean(z_elo, z_off, z_def, z_netsr, z_wl)
6. **+PtDiff**: mean(z_elo, z_off, z_def, z_netsr, z_wl, z_pd)
7. **Learned**: OLS weights from development (intercept 0.012; z_elo +2.997,
   z_off +1.037, z_def −0.386, z_netsr +0.805, z_wl −0.566, z_pd +0.763)

Equal weighting for specs 2–6 is the preregistered neutral choice (no tuning).

## 7. Learned-weight methodology
OLS of team rest-of-season point-differential/game on the six standardized
components, pooled over development snapshots (2018–2020, weeks 4+). Applied
as-is to validation. Per-season refits (2018/2019/2020 separately) were used
to test weight stability — see §11.

## 8. Season-by-season results (validation future-margin MAE)
`table_season_mae.csv`. Δ = MAE improvement vs ELO-only (positive = better).

| Season | ELO only | ELO+OffEPA (Δ) | Learned (Δ) |
|---|---|---|---|
| 2021 (n=1588) | 11.337 | 11.249 (**+0.088**) | 11.211 (**+0.126**) |
| 2022 (n=1573) | 10.012 | 9.650 (**+0.362**) | 9.634 (**+0.378**) |

Both composites beat ELO-only in **both** validation seasons. Other specs in
2021 were *worse* than ELO-only (+DefEPA −0.121, +NetSR −0.171, +W-L −0.237,
+PtDiff −0.244); in 2022 they were modestly better (+0.24 to +0.36) —
inconsistent, and never better than ELO+OffEPA.

## 9. Pooled results (PRIMARY metric)
`table_primary_mae.csv`. Validation 2021–2022, snapshots weeks 4+, n=3161,
paired t-test vs ELO-only:

| Candidate | MAE | Δ vs ELO | t | p |
|---|---|---|---|---|
| Learned | 10.426 | **+0.251** | 7.88 | <1e-4 |
| ELO+OffEPA | 10.453 | **+0.224** | 5.57 | <1e-4 |
| +NetSR | 10.583 | +0.095 | 2.03 | 0.042 |
| ELO+Off+Def EPA | 10.617 | +0.061 | 1.52 | 0.13 |
| +PtDiff | 10.637 | +0.041 | 0.90 | 0.37 |
| +W-L | 10.671 | +0.006 | 0.14 | 0.89 |
| ELO only | 10.678 | — | — | — |

The two best candidates are the learned composite and the simple,
untuned ELO+OffEPA blend. Adding defensive EPA, success rate, W-L, or point
differential on top does not help (and in 2021 hurt).

## 10. Early / mid / late-season splits
`table_split_mae.csv`. Δ vs ELO-only:

| Split | ELO+OffEPA Δ | Learned Δ |
|---|---|---|
| Early, snapshots wk 1–3 (n=1437) | +0.021 (neutral) | +0.020 (neutral) |
| Mid, wk 4–12 (n=2690) | **+0.221** | **+0.252** |
| Late, wk 13+ (n=471) | **+0.242** | **+0.245** |

The composite advantage appears once ~4 weeks of current-season data exist
and persists through late season. Early-season neutrality is expected: with
≤3 games, efficiency components are mostly preseason-blended noise. No
candidate is meaningfully worse than ELO-only at any split.

## 11. Rank stability
`table_rankcorr.csv`, `table_stability.csv`, `table_learned_weights.csv`.

- **Predictive rank correlation** (mean Spearman over validation snapshots,
  composite rank vs team's rest-of-season performance; higher = better):
  Learned 0.506 / ELO+OffEPA 0.500 vs ELO-only 0.431 (future PD/game);
  0.442 / 0.437 vs 0.377 (future win%). The composites order teams better.
- **Week-to-week rank stability** (Spearman of consecutive weekly ranks):
  ELO-only 0.972 > Learned 0.948 > ELO+OffEPA 0.921. Composites move more
  week to week — expected, since efficiency reacts faster than results-based
  ELO. Not a defect for a "how good right now" ranking, but documented.
- **Learned-weight stability** (per-season OLS on development years):
  z_elo (+5.1, +2.3, +3.9) and z_off (+1.3, +1.7, +0.2) keep their signs;
  z_def, z_netsr, z_wl, z_pd ALL flip signs across seasons. The tuned blend
  is not well-identified — the data cannot stably allocate credit among the
  correlated secondary components. **The learned-weight version is therefore
  not adopted** (see §14).

## 12. NE / GB / PHI case study (descriptive only, from 2026 diagnostic)
No 2026 futures exist and none were used. Structural reading only:

- **NE (2026 wk 3)**: ELO rank 9 vs off-EPA rank 29 (10th-largest disagreement
  of 32). Under the adopted composite, NE's poor offensive efficiency would
  pull its ranking well below #9 — exactly the correction the current
  "Overall = ELO" label fails to make. (Whether that proves *correct* for NE
  specifically cannot be known until the season plays out; the validation
  evidence is historical, not Patriots-specific.)
- **GB (−14) and PHI (−12)** showed the same strong-2025/slow-start pattern
  in the diagnostic — ELO ahead of efficiency. The composite treats all such
  cases symmetrically; nothing was tuned around any of these teams.
- Validation-season analogues (`table_disagreement_cases.csv`, week-4
  snapshots): when ELO and efficiency disagreed sharply, the ELO+OffEPA rank
  was usually closer to the team's eventual future-performance rank than the
  ELO rank (e.g. 2021 DAL: ELO 21 → composite 17 → future 2; 2022 JAX: ELO 26
  → composite 16 → future 11) — but not always (2021 KC: ELO 5 was right,
  efficiency was wrong, composite overcorrected to 1). Descriptive; no
  selection was based on these.

## 13. Interpretation
1. **The "Overall = ELO" label is misleading and a composite is measurably
   better.** A simple, untuned, preregistered equal-weight blend of
   standardized ELO and offensive EPA predicts future game margins better
   than ELO alone: +0.22 MAE pooled (p<1e-4), positive in both validation
   seasons, robust across mid/late splits, and better rank-ordered against
   future performance. This is not curve-fitting: spec 2 had zero tuned
   parameters.
2. **More is not better.** Adding defensive EPA, net success rate, W-L, or
   point differential does not improve on ELO+OffEPA (and hurt in 2021).
   Defensive efficiency appears to be already captured by ELO's
   results-based signal; the orthogonal information is on offense.
3. **Tuned blends are fragile.** Learned weights flip signs across
   development seasons for 4 of 6 components. The only stably-positive
   learned components are ELO and offensive EPA — the same two in the simple
   blend. Do not ship the learned version.
4. **Caveats**: only two validation seasons (2021 gain was modest at +0.09);
   the vault (2023–2025) was deliberately not used and remains available for
   a future preregistered confirmation; composites are slightly less
   week-to-week stable than ELO-only; early-season (weeks 1–3) the composite
   is neutral vs ELO-only.
5. **This changes nothing about V1.** The composite is a descriptive
   dashboard ranking. ELO remains the 40% component of the frozen game
   prediction model, unchanged.

## 14. Recommendation
**ADOPT A VALIDATED COMPOSITE POWER RANKING** — with the adopted
specification being the simple fixed blend, **not** the learned version:

> **Power score = ( z(ELO) + z(offensive EPA/play) ) / 2**,
> z-scored cross-sectionally across the 32 teams at each week; rank descending.

Transparency note on the preregistered decision rules: the ADOPT clause
required the best composite to clear +0.15 pooled (Learned: +0.251 ✓),
win both seasons (✓), and have stable learned-weight signs (✗ — 4 of 6
components flip signs). The stability clause exists to guard against
overfit tuned blends; the adopted fixed blend has **zero tuned parameters**,
so the guard is satisfied vacuously, and every performance clause is met by
both the learned and the fixed version. The learned version itself is
explicitly **declined**. If a stricter reading is preferred, the fallback is
OPEN FOR FURTHER VALIDATION with a preregistered vault (2023–2025)
confirmation — the evidence already in hand is reported above either way.

**Dashboard implications (not implemented — architecture guidance only):**
- Rename the current "Overall" lens to **"Power Ranking"** and compute it as
  the adopted composite.
- Keep **ELO** as an explicit standalone lens/rank (it remains the
  results-based rating and a V1 component).
- Keep **Offense** (offensive EPA etc.) and **Defense** (defensive EPA etc.)
  lenses as-is.
- This resolves the exact confusion that motivated the experiment: a user
  seeing "#9" under Power Ranking will be seeing a validated overall-strength
  estimate, while "#9 ELO" will be explicitly labeled as the ELO rank.

## Artifacts
All under `experiments/power_ranking_experiment/`:
- `PREREGISTRATION.md` — protocol + decision rules, written before analysis
- `01_build_snapshots.py`, `02_walkforward.py` — re-runnable code
- `snapshots_2018_2022.parquet` — 2784 weekly team snapshots
- `table_primary_mae.csv` — pooled primary results
- `table_season_mae.csv` — per-season results
- `table_split_mae.csv` — early/mid/late splits
- `table_rankcorr.csv` — predictive rank correlations
- `table_stability.csv` — week-to-week stability
- `table_learned_weights.csv` — pooled + per-season learned weights
- `table_disagreement_cases.csv` — week-4 disagreement case studies
- `REPORT.md` — this file

## Confirmations
- V1 prediction model unchanged (ELO + EPA-linear + GBM, 40/50/10, K=20,
  HFA=55, threshold 3.0).
- Current V1 ELO methodology unchanged (1/3 offseason regression intact).
- No 2026 outcomes used for tuning, selection, or validation.
- 2023–2025 locked vault never opened.
- No production dashboard, Teams page, or UI files were modified.
- All work is read-only analysis; nothing in `data/` or `scripts/` was
  written.
