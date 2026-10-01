"""Build a shareable PDF of the 'How the NFL model works' report.

Output is written inside the repo tree (docs/) so the script works from any
checkout; previously it wrote to a personal workspace folder.
"""
import os

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                HRFlowable, KeepTogether)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "docs", "nfl-model-report.pdf")

styles = getSampleStyleSheet()
TEAL = HexColor("#1F4E5F")
RED = HexColor("#9C0006")

sTitle = ParagraphStyle("Title2", parent=styles["Title"], fontSize=22,
                       textColor=TEAL, spaceAfter=4)
sSub = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=10,
                     textColor=HexColor("#555555"), spaceAfter=14)
sH1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=15,
                    textColor=TEAL, spaceBefore=16, spaceAfter=6)
sH2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12,
                    textColor=TEAL, spaceBefore=10, spaceAfter=4)
sBody = ParagraphStyle("Body2", parent=styles["Normal"], fontSize=10.5,
                       leading=15, spaceAfter=7)
sBull = ParagraphStyle("Bull", parent=sBody, leftIndent=18, firstLineIndent=0,
                       bulletIndent=8, spaceAfter=5)
sHead = ParagraphStyle("Head", parent=sBody, textColor=RED, fontName="Helvetica-Bold",
                       borderPadding=(6, 6, 6), spaceAfter=10)

def H1(t): return Paragraph(t, sH1)
def H2(t): return Paragraph(t, sH2)
def P(t): return Paragraph(t, sBody)
def B(t): return Paragraph(t, sBull, bulletText="\u2022")

story = [
    Paragraph("How the NFL Model Works", sTitle),
    Paragraph("Spread picks &amp; prop projector &mdash; full methodology. Written September 2026.", sSub),
    HRFlowable(width="100%", thickness=1, color=TEAL),
    Paragraph("THE HONEST HEADLINE: The spread model has no verified edge. On a clean 2023&ndash;2025 "
              "holdout it went 140&ndash;125 ATS (52.8%, +0.9% ROI) &mdash; inside statistical noise, and the "
              "market out-predicts it. Everything below is real methodology; none of it is a proven winning system.",
              sHead),

    H1("1. Spread model"),
    H2("Data"),
    P("Every NFL game 2018&ndash;2025 from nflverse (2,229 games) &mdash; scores, lines, and full play-by-play."),

    H2("Ratings (the inputs)"),
    P("Two systems, both updated week by week with no lookahead:"),
    B("<b>Margin-aware ELO.</b> Every team starts at 1500. After each game, ratings move with K=20, scaled by a "
      "margin-of-victory multiplier (log-based, so a 28-point blowout counts more than a 3-point win but with "
      "diminishing returns), dampened when the result was expected. Each offseason every rating regresses one-third "
      "of the way back to 1500, because rosters turn over."),
    B("<b>EPA ratings.</b> From play-by-play: each team's offensive and defensive EPA per play, split into pass and "
      "rush, plus success rate &mdash; both sides of the ball. Updated with an exponentially weighted moving average "
      "(each new week gets 25% weight), regressed 35% toward league average every offseason."),

    H2("The three predictors"),
    P("Two are plain linear regressions fit on 2018&ndash;2020: one maps the ELO difference to expected margin, the "
      "other maps the EPA feature differences to expected margin. The third is a gradient-boosting regressor trained "
      "walk-forward &mdash; for each week of 2021 onward, it's trained only on games played before that week, then "
      "predicts that week. Features include the ELO/EPA diffs plus rest days, a divisional-game flag, and week number."),

    H2("The ensemble"),
    P("Final prediction = 0.4 &times; ELO-linear + 0.5 &times; EPA-linear + 0.1 &times; GBM. Those weights weren't "
      "guessed &mdash; they were picked on 2021&ndash;2022 validation data to minimize prediction error. Notably, the "
      "fancy ML model only earned a 0.1 weight: the simple linear models did nearly all the work. Useful lesson "
      "&mdash; complexity has to earn its place."),

    H2("The betting rule"),
    P("A pick fires only when the model's spread differs from the market spread by 3+ points. That threshold was "
      "tuned on validation (2021&ndash;2022: 103&ndash;88, 53.9%, +2.9% ROI at &ge;3.0). On the untouched 2023&ndash;2025 "
      "test: 140&ndash;125, 52.8%, +0.9% ROI over 265 plays. Standard error &asymp; &plusmn;3.1%, and breakeven at -110 "
      "odds is 52.4% &mdash; statistically indistinguishable from a coin flip with extra steps. The model's average "
      "miss (10.22 pts) is worse than the market's (9.79), and the size of the model's &ldquo;edge&rdquo; has "
      "essentially zero correlation (0.007) with whether the pick covers."),

    H2("Totals"),
    P("Tested at every threshold, lost money at all of them. The model never plays totals. (One real finding from the "
      "v2 work: wind lowers totals ~0.38 pts per mph, statistically significant &mdash; but unusable since we don't "
      "bet totals.)"),

    H2("The v2 attempt"),
    P("I added walk-forward QB ratings (EPA per play for each starting QB) and wind, then re-ran the full backtest. "
      "Result: worse &mdash; 50.9% / &minus;2.7% ROI on test. Why: the market prices QB news within minutes, so by "
      "Friday there's nothing left to exploit, and team passing efficiency already contains most of the QB's signal. "
      "The QB feature added noise, not information. v1 stays the default."),

    H2("Weekly operation"),
    P("Every Friday: re-pull 2026 data, roll ratings forward through games already played, refit the GBM on the "
      "expanded sample, predict the upcoming week against researched market lines. After the games, every pick is "
      "graded and appended to a permanent record &mdash; plus closing-line value (did our Friday number beat the "
      "closing line?), the stat I'm watching most closely going forward."),

    H1("2. Prop projector"),
    P("Different job: project individual player yardage (QB passing yards, RB rushing yards, WR/TE receiving yards) "
      "and compare to the sportsbook's line."),
    H2("How a projection is built"),
    B("Start from every play 2018&ndash;2026, aggregated to one row per player per game."),
    B("Baseline = the player's exponentially weighted trailing average (recent games count more, roughly a 3-game "
      "half-life), preferring same-season games, then last season. Small samples get shrunk hard toward the "
      "positional average &mdash; a rookie with two good games doesn't get projected like a star."),
    B("Matchup adjustment: fitted from historical data, not hand-tuned. A receiver facing a defense that's "
      "historically soft against the pass gets bumped; the size of the bump comes from a regression on past seasons."),
    B("Feed in the book's lines; output is projection minus line, sorted by biggest gap, with an over/under lean."),
    H2("Reality check (2025 holdout)"),
    P("It beats a naive &ldquo;average of last 3 games&rdquo; on all three markets &mdash; pass yards correlation 0.30 "
      "(MAE 63.1 vs naive 69.3), rush 0.37 (25.4 vs 27.3), receiving 0.44 (22.5 vs 24.3). But the gaps are small, "
      "because week-to-week yardage is mostly noise: last week's yards predict this week's at only ~0.2 correlation. "
      "The model extracts roughly as much signal as exists. Standing rules: gaps are paper-tracked only, never called "
      "+EV, and anything under ~half the typical error is treated as noise."),
    P("One structural caveat: historical player-prop lines don't exist anywhere, so unlike the spread model this one "
      "cannot be backtested at all. Every prop call is paper-tracked and judged on forward results."),

    H1("3. What I'd tell someone building their own"),
    B("Tune everything on one slice of history, judge on another you never touched. Validation&rarr;test decay bit us "
      "twice (spread threshold, v2)."),
    B("Simple beats complex until complexity proves itself on unseen data."),
    B("The market is the toughest baseline in sports. &ldquo;Beats a naive model&rdquo; &ne; &ldquo;beats the market.&rdquo;"),
    B("Track closing-line value from day one &mdash; it's the earliest signal of whether you have anything."),
    Spacer(1, 0.2 * inch),
    HRFlowable(width="100%", thickness=1, color=TEAL),
    Paragraph("Built by Scout for Cale &mdash; September 2026. Experimental outputs, honestly labeled. "
              "If you or someone you know has a gambling problem: 1-800-GAMBLER.", sSub),
]

doc = SimpleDocTemplate(OUT, pagesize=LETTER,
                        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
                        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                        title="How the NFL Model Works", author="Scout")
doc.build(story)
print("wrote", OUT)
