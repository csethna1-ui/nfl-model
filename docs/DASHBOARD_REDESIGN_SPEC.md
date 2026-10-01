# NFL Model Dashboard — Major Redesign Spec (frozen 2026-09-30)

Binding product-design brief from Cale. Front-end/product design ONLY. Do NOT
change: model logic, predictions, backtests, weights, thresholds, research
protocol, data-generation methodology, void logic, or model-version stamping.

## Aesthetic

- Premium dark-first sports analytics aesthetic: deep navy/charcoal, slightly
  lighter cards, restrained gradients/raised surfaces, high-contrast
  typography, primary model accent, secondary market/reference color.
- Green ONLY for positive/confirmed states, amber for uncertainty/warnings,
  red ONLY for voids/errors.
- Avoid: excessive teal, spreadsheet-style white tables, generic
  corporate-dashboard styling, clutter, excessive borders/shadows/rounding,
  tiny dense text.

## Product hierarchy (in order)

1. Visual signal
2. Model vs market
3. Plain-English reasoning
4. Supporting data
5. Deep analytics

## Navigation

- Primary: Home, Games, Props, Teams, Performance
- Utility: Model, CLV, Data Health, About
- Compact week and model-version selectors.
- "Production" means production specification, never profitability.
- Keep "No verified betting edge" visible but unobtrusive.

## Home / Games / Picks

- Heading: "WEEK 4 MODEL BOARD".
- Premium game cards: real team logos/fallbacks, kickoff, market spread,
  model spread, model gap, decision, uncertainty, QB/injury warning.
- Subtle market→model visual.
- Filters: All / Paper Plays / No Play / Voided, plus gap thresholds.
- Paper plays, no plays, and voids visually distinct.
- Voids show: raw model signal, QB status/reason, final void disposition.

## Reasoning (hard rule)

- Natural language generated ONLY from facts in the current data.
- NEVER invent: injuries, weather, matchups, schemes, player form, betting
  information, feature importance, statistical drivers.
- If game-level contributions are unavailable, state they are not included
  and cannot be attributed to a specific factor.

## Props

- Premium player cards, NOT a spreadsheet.
- Each card: headshot with initials fallback, team logo, player/team/position,
  matchup, market, line, Model D projection, gap, lean, P25/median/P75,
  supported uncertainty level.
- Detail view shows the actual opportunity × efficiency decomposition when
  present.
- Projection, line, and lean remain separate; no line = projection-only, no
  lean.
- Never invent calibrated probabilities.
- Label remains: "Player Projection v2 — Experimental Production."

## Teams

- Visual power board using ONLY available ELO, Off EPA, Def EPA, Success
  Rate.
- Sortable compact ranking bars + team detail views.

## Performance

- Research-center presentation: locked-test MAE, market comparison, ATS
  history, thresholds, season splits.
- Explicitly state the market has lower locked-test MAE.
- No flashy profit framing.

## CLV

- Keep "nflverse close proxy — not a verified close." Prominently labeled
  as a proxy.

## Data Health

- Statuses come from ACTUAL validation; never manufacture "healthy."

## Model page

- Visual ELO/EPA/GBM ensemble diagram: 40% ELO / 50% EPA / 10% GBM.
- Train 2018–2020, validation 2021–2022, locked test 2023–2025.
- Use: "Current best validated specification under the frozen information
  set."
- Do NOT use "the ceiling" in the UI.

## About

- Sections: what it does, validation, what was tested, what it does not
  claim, limitations.

## Responsive

- Purpose-built desktop, laptop, tablet, and iPhone layouts. Mobile must NOT
  merely stack desktop.

## Required microcopy (exact)

- "How far the model is from the market"
- "Model gap"
- "No paper play"
- "Not included in this snapshot"
- "Where the projection differs from the line"
- "Research model · paper tracking only"

## Preserved guardrails

- No verified edge; paper tracking; locked test; model vs market MAE;
  CLV proxy disclaimer; experimental prop disclaimer; voids; versioning;
  data-health validation; historical test periods; uncertainty flags.

## Final verification (required before handoff)

- Every page works; V1 loads; filters/sorting work; game and prop detail
  navigation works; logo/headshot fallbacks work; mobile works; no model
  calculations changed; disclaimers remain; no unsupported reasoning; UI is
  substantially different from the old spreadsheet-style build.

## Publication

- Do NOT publish. The public URL keeps serving the current build until Cale
  approves the final look.
