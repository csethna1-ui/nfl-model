# Experiment 009 — NFL Information Frontier & Market-Residual Audit: REPORT

**Status: COMPLETE. Vault touched exactly once, for the preregistered §5G diagnostic only.
V1 unchanged. No production or dashboard changes. No auto-deploy.**
**Protocol frozen 2026-09-30 before any locked-test computation; all numbers below
reproduced from canonical artifacts.**
**Independent research agent (not the original modeler); Exp 004 inventory and prior
experiment findings accepted as evidence, not re-derived.**

---

## §1. Baseline reconciliation

Reproduced from `data/games_with_preds.parquet` (canonical backtest artifact):

| Set | n | V1 MAE | Market MAE | Gap |
|---|---|---|---|---|
| Validation 2021–22 (REG) | 569 | 10.0425 | 9.7267 | 0.3158 |
| Locked 2023–25 (REG only) | 816 | 10.1867 | 9.7445 | 0.4422 |
| Locked 2023–25 (all, incl. playoffs) | 857 | 10.2285 | 9.7905 | 0.4380 |

The brief's figures (~10.19 / ~9.75 / ~0.44) reconcile to the REG-only locked set
(10.1867 / 9.7445 / 0.4422); the backtest_report's 10.22/9.79 reconciles to the all-games
locked set (10.2285 / 9.7905). **Data note:** the parquet contains 2 2026 Week 1 games
(2026_01_NE_SEA, 2026_01_SF_LA); they were excluded from the locked set per protocol
(2026 = monitoring only). This explains the 816 vs 818 discrepancy in the brief's draft.

ELO–EPA structure on validation: prediction correlation 0.763, **error correlation 0.949**
— confirms the v1_architecture_audit finding (error corr ~0.95): the components are
three views of one latent team-strength axis.

---

## §2. Information-frontier audit (Part 1)

Full table: `frontier_table.csv` (38 rows). Summary by status:

**Tested, null — do not re-run (16 families):** QB EPA/play and QB-form features (4
independent external nulls + v2); historical QB value (V2-C); non-QB availability
(Exp 005); full-roster injury adjustment (Phase 2); opponent-adjusted EPA (Exp 002);
dynamic strength (Exp 003); offensive strategy incl. pace (Exp 007); pressure/
explosiveness/possession (V2-D); matchup features (V2-B); wind on spreads (totals-only);
market-residual linear modeling (Exp 001); distributional/variance modeling (Exp 008);
luck-stripping (external, n=2,761); PFR advanced (V2 feature set).

**Tested in this experiment (3):** market anchoring (§3 — null); training windows
(§5 — null); home-bias correction (§5 — real but immaterial).

**Hypothesized-reconstructable, untested (5):** PFT news-arrival timing (pending
separate track, verdict 2026-10-01); Sunday-morning QB news (PFT subset); confirmed
inactives (nflverse INA, ~1 day effort); roster transactions (PFR wire, medium leakage
care); weather forecast vintages (weak margin mechanism); officiating (not assessed).

**Hypothesized-inaccessible (6):** public ticket splits, money splits (proxy only,
never "sharp money"), line movement/open-to-close (SBR died Sep 2026 — archives
perishable), true sharp money, X/Twitter full archive ($5k–42k/mo), premium grades.

**Dead (4, verified in audit):** practice participation, beat-reporter reconstruction,
ESPN/Sleeper/FantasyPros historical APIs, special-teams EPA edge (rule breaks 2023–25).

**Untested, weak mechanism or redundant (4):** time-varying HFA, NGS separation/
coverage, drive/field-position detail, OL/skill continuity.

The disciplined conclusion: the tested-but-null column is long and convergent
(internal experiments + independent public models + external researchers all land on
the same null). The remaining hypothesized-reconstructable column is short, and the
hypothesized-inaccessible column contains the most mechanically plausible explanations
(line movement, money flow, fast news wires).

---

## §3. Market-anchoring (Parts 3 + 9)

Validation (2021–22, n=569). Grid w ∈ [0,1] step 0.05 on `w·V1 + (1−w)·market`:

| | MAE |
|---|---|
| A: V1 | 10.0425 |
| B: market-only | 9.7267 |
| **C: blend, w\*=0.15** | **9.7107** |

- Blend vs V1: +0.3317, 95% paired bootstrap CI (0.0983, 0.5403) — excludes zero, ≥0.15
  bar. This is the market's edge, not V1's contribution.
- **Blend vs market: +0.0160, CI (−0.0255, 0.0577) — includes zero, far below the 0.15
  bar.** Per-season (w\*=0.15): 2021 — V1 11.082 / market 10.667 / blend 10.670;
  2022 — V1 8.999 / market 8.783 / blend 8.748. Grid is flat near the minimum
  (w=0.10: 9.7150, w=0.15: 9.7107, w=0.20: 9.7113). Optimal weight on V1 is only 0.15.

**§5G locked-test confirmation (the single vault touch, 2023–25 REG, n=816,
fixed w\*=0.15):** V1 10.1867, market 9.7445, **blend 9.7583**.
- Blend vs V1: +0.4283, CI (0.2607, 0.5941) — excludes zero.
- **Blend vs market: −0.0138, CI (−0.0465, 0.0183) — includes zero.**
- Per-season: 2023 10.573/9.901/9.950; 2024 9.893/9.610/9.584; 2025 10.094/9.722/9.741.
  The blend ≈ market-only in all three seasons.

**Verdict:** CONFIRMED on locked data — frozen V1 carries no validated incremental
information beyond the pregame market snapshot. This is the diagnostic's clean answer
to "what does the market know that V1 doesn't": within this blend framework,
effectively everything the market knows is absent from V1, and V1 adds ~0.016 MAE
(validation) / −0.014 MAE (locked) — statistically and practically zero.
(Part 3D: skipped — no surviving feature families after Exp 001's null. Part 3E:
cited — Exp 001 found market-only beats all market-residual variants.)

---

## §4. One-family-at-a-time component tests (Part 4)

**Skipped by preregistered design.** The premise of Part 4 was surviving families from
Experiments 001/002/003/005/007 — there are none (all null). Re-running them would
violate the "do not re-run convergent nulls" rule and the research freeze.
Candidate incremental values against frozen V1 on validation:

| Experiment | Family | Best candidate vs V1 | Result |
|---|---|---|---|
| 002 | Opponent-adjusted EPA | failed gate | null |
| 003 | Dynamic strength | err corr 0.985 | null |
| 005 | Non-QB availability | 10.077 vs 10.042 (worse) | null |
| 007 | Strategy/pace | 10.157 vs 10.042 (worse) | null |
| V2-A–D | Components/matchups/QB/pressure | all significantly worse | null |

Jointly with §3: V1 ≈ ELO ≈ EPA ≈ market-residual-zero all live on one latent axis;
no tested family separates from it.

---

## §5. Training-window audit + spec synthesis (Parts 5 + 6)

Frozen linear components refit on windows W0–W4 (same 8 EPA/SR features, same
ELO feature, GBM and 40/50/10 weights frozen), evaluated on 2021–22:

| Window | Train seasons (S=2021 / 2022) | Validation MAE | Δ vs W0 | 95% CI |
|---|---|---|---|---|
| W0 frozen 2018–2020 | — | 10.0425 | — | — |
| W1 rolling-2 | 19–20 / 20–21 | 10.0599 | −0.0174 | (−0.0721, 0.0363) |
| W2 rolling-1 | 2020 / 2021 | 10.0834 | −0.0409 | (−0.1349, 0.0552) |
| W3 expanding | ≤2020 / ≤2021 | 10.0267 | +0.0158 | (−0.0040, 0.0352) |
| W4 drop-2018 | 19–20 / 19–20 | 10.1217 | −0.0792 | (−0.1449, −0.0142) |

**Verdict:** performance is insensitive to training window. The largest move (W4,
−0.079) is below the 0.15 materiality bar. The 2018–2020 window is not restrictive;
recency-weighting is not a lever. (Note: for S=2022, W1/W2/W3 legitimately include
validation year 2021 in training — strict walk-forward, no future leakage for 2022
predictions; disclosed in preregistration.)

**Home-bias diagnostic (post-hoc, from the architecture audit's open question):**
train-set bias (actual − predicted) is +1.19 (fit 2021) / +1.30 (fit 2022) — real and
stable. But correcting it cross-season buys only +0.045 MAE (2022) and −0.010 in
reverse — immaterial. The drift is second-order on ~13pt residual noise, not the gap.

**Spec synthesis (read-only):** V1's construction is honest and leak-free
(walk-forward linears + GBM, frozen weights). The binding constraint is the scalar
point-estimate target and the pregame information set, not the architecture:
error corr V1–market 0.967 (both fail the same games the same way); ELO–EPA error
corr 0.949; the blend grid is flat; the weight surface is flat (weight diagnostic).
"Better math on the same data" is exhausted — consistent with the research freeze.

---

## §6. Segment analysis (Part 7)

Validation 2021–22 MAE (V1 vs market; + = market better):

| Segment | n | V1 | Market | Δ |
|---|---|---|---|---|
| Weeks 1–4 | 128 | 9.490 | 9.207 | +0.283 |
| Weeks 5–9 | 144 | 10.086 | 10.354 | −0.268 |
| Weeks 10–18 | 297 | 10.259 | 9.646 | +0.613 |
| Home favored (≡ road underdog) | 352 | 9.908 | 9.659 | +0.249 |
| Home underdog (≡ road favorite) | 217 | 10.261 | 9.836 | +0.425 |
| Spread < 3 | 130 | 9.536 | 9.423 | +0.112 |
| Spread 3–7 | 286 | 9.734 | 9.456 | +0.278 |
| Spread 7+ | 153 | 11.050 | 10.490 | +0.560 |
| Division games | 199 | 10.663 | 10.043 | +0.621 |
| Non-division | 370 | 9.708 | 9.557 | +0.152 |
| 2021 | 285 | 11.082 | 10.667 | +0.416 |
| 2022 | 284 | 8.999 | 8.783 | +0.216 |

(Note: with a single spread number, home-favorite ≡ road-underdog — reported once.)
Largest gaps: division games (+0.621), weeks 10–18 (+0.613), large spreads (+0.560) —
where within-week news, familiarity, and motivation information concentrate, and where
the market's richer information set has the most room to win. V1's only winning
segment is weeks 5–9 (−0.268), consistent with early-season ratings settling.

---

## §7. Edge buckets (Part 8)

Validation 2021–22, ATS by |edge| = |V1 margin − market spread|:

| Bucket | n | W–L–Push | Win% | Mean |V1 err| |
|---|---|---|---|---|
| [0,1) | 117 | 55–61–1 | 0.474 | 10.759 |
| [1,2) | 137 | 70–63–4 | 0.526 | 10.133 |
| [2,3) | 119 | 57–58–4 | 0.496 | 10.330 |
| [3,4) | 76 | 39–36–1 | 0.520 | 8.576 |
| [4,∞) | 120 | 64–52–4 | 0.552 | 9.885 |
| **Operating \|edge\|≥3.0** | **196** | **103–88–5** | **0.539** | — |

- The backtest_report's 103–88 reproduces exactly (196 games − 5 pushes = 191 decided).
- Larger disagreement does not monotonically mean larger model edge: the [0,1) bucket
  is sub-coin-flip (0.474), [2,3) is 0.496, and the best bucket ([4,∞), 0.552) is noisy
  at n=120. Mean model error does not decrease with edge.
- Betting-relevant read: the operating threshold reproduces, but §3 shows the edge
  the model *thinks* it has is not information the market lacks — the blend result
  implies market prices already subsume V1's signal. Paper-track only; no +EV claim.

---

## §8. CLV (Part 9)

Historical CLV not reconstructable (timestamp-unknown market snapshot — Exp 004).
2026 live: n=14, +0.32 (reported per protocol; monitoring only, no conclusions at n=14).

---

## §9. Recommendations (ranked)

**The single most important finding:** the market-anchoring diagnostic (§3) plus the
Exp 004 timestamp-gap finding jointly reframe the gap. V1 adds nothing to the market
snapshot — the residual gap is an **information-timing gap**, not a modeling gap.
Nothing in Parts 4–6 contradicts this. The research program freeze stands: no more
"better math on the same data."

Ranked missing-but-reconstructable information (research priority):

1. **PFT news-arrival timing** — pending separate track (verdict 2026-10-01). If the
   corpus is a real timing layer, the next experiment is preregistered: a news-timing
   feature tested on validation, locked test only if it passes gates. If it fails,
   it is an archive, not a timing layer — say so.
2. **Confirmed inactives** (nflverse INA < kickoff−90min) — the cleanest untested
   reconstructable candidate (~1 day effort). Preregistered validation test; do not
   touch 2023+ until gates pass.
3. **Roster transactions** (PFR wire) — if (2) is null, test wire-derived
   availability deltas with day-level leakage rules.
4. **Betting-splits / line-movement feasibility audit** — already queued as a separate
   track; starts only after the PFT verdict AND Cale's authorization. Of the three,
   open-to-close movement is the most mechanically plausible; splits are proxies.
5. **Live 2026 Friday stream as prospective arbiter** — accumulate timestamp-aligned
   weeks (spread at research time + Friday freeze + inactives); re-examine the gap
   with n≥100 aligned observations. This is the only path that removes the Exp 004
   caveat.

**Do not authorize:** any re-run of the 16 tested-null families; any weight/training
change (Parts 5–6 are null); any V1 change on the basis of the blend (the blend is
not deployable — it uses the market as input); any betting-splits modeling before the
PFT verdict; X/Twitter or premium-data routes (inaccessible).

**"Nothing we can validate" remains the legitimate outcome** if (1)–(4) come back
null — the gap would then be documented as inaccessible-only explanations
(fast wires, true sharp flow), stated as hypothesis, never finding.

## Leakage audit: `leakage_audit.md` — 7/7 PASS (1 with disclosed timestamp caveat).

## Reproducibility

- `PREREGISTRATION.md` — frozen 2026-09-30 before any locked computation.
- `01_validation_analyses.py` — Parts A/B/D/E + ELO–EPA corr; seed 42; 2000-iteration
  paired bootstrap. Reads only `data/games_with_preds.parquet`.
- `results_validation.json`, `results_locked.json` — all reported numbers.
- `frontier_table.csv` — Part 1 (38 rows).
- `leakage_audit.md` — Part 10.
- Locked test touched exactly once (§5G, fixed w\*=0.15 blend). 2026 excluded.
- No PFT corpus use, no Exp 006 use, no production/dashboard/V1 changes.
