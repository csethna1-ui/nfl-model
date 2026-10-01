"""V2 blocker gate: feature-family overlap matrix (DIAGNOSTIC ONLY).

Descriptive family-level correlation matrix on 2021-2022. Shows whether the
feature families are distinct information sources or several names for one
latent variable. NO predictive evaluation, NO model comparison.

Family score construction (transparent, unfitted):
- team-level features (home_/away_ columns): game score = mean of z-scored
  (home - away) differentials across the family's numeric features.
- matchup mx_* features: already game-level interactions; score = mean of
  z-scored raw values.
- z-scores computed across the 2021-2022 descriptive sample only. This is a
  descriptive summary of the observed sample, not a predictive transform, so
  no future-information concern applies to the z-scoring itself.
- V1 margin and ELO/EPA/GBM components joined from data/games_with_preds.parquet.
"""
import json
import numpy as np
import pandas as pd

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = REPO_ROOT
OUT_JSON = f"{REPO}/v2_research/overlap_matrix.json"
OUT_MD = f"{REPO}/v2_research/overlap_matrix.md"

def main():
    g = pd.read_parquet(f"{REPO}/data/v2/games_v2_features.parquet")
    g = g[g.season.isin([2021, 2022])].reset_index(drop=True)
    inv = json.load(open(f"{REPO}/v2_research/feature_inventory.json"))
    fams = {}
    for x in inv:
        fams.setdefault(x["family"], []).append(x["feature"])

    cols = set(g.columns)
    scores = pd.DataFrame({"game_id": g.game_id, "season": g.season, "week": g.week})

    coverage = {}
    for fam, feats in sorted(fams.items()):
        zs = []
        used = 0
        for f in feats:
            hc, ac = "home_" + f, "away_" + f
            if hc in cols and ac in cols:
                v = pd.to_numeric(g[hc], errors="coerce") - pd.to_numeric(g[ac], errors="coerce")
            elif f in cols:
                v = pd.to_numeric(g[f], errors="coerce")
                # matchup interactions are game-level but side-specific:
                # _awayoff variants favor the away team; flip to home-margin perspective
                if fam == "matchup" and f.endswith("_awayoff"):
                    v = -v
            else:
                continue
            if v.notna().sum() < 50 or v.std(skipna=True) == 0:
                continue
            z = (v - v.mean(skipna=True)) / v.std(skipna=True)
            zs.append(z)
            used += 1
        if zs:
            mat = pd.concat(zs, axis=1)
            scores[fam] = mat.mean(axis=1, skipna=True)
            coverage[fam] = {"features_used": used, "features_total": len(feats),
                             "median_nonan_frac": round(float(mat.notna().mean(axis=1).median()), 3)}
        else:
            scores[fam] = np.nan
            coverage[fam] = {"features_used": 0, "features_total": len(feats),
                             "median_nonan_frac": 0.0}

    # V1 components (research artifact, 2021-2022)
    vp = pd.read_parquet(f"{REPO}/data/games_with_preds.parquet")
    vp = vp[vp.season.isin([2021, 2022])][["game_id", "pred_elo", "pred_epa_m",
                                           "pred_gbm_m", "ens_margin"]]
    scores = scores.merge(vp, on="game_id", how="left")

    # Pressure: combine PBP + PFR sub-families for the core matrix
    scores["pressure"] = scores[["pressure_pbp", "pressure_pfr"]].mean(axis=1, skipna=True)

    core = ["ens_margin", "pred_elo", "pred_epa_m",
            "matchup", "possession", "explosiveness", "pressure", "player_qb"]
    core_labels = {"ens_margin": "V1", "pred_elo": "ELO", "pred_epa_m": "EPA",
                   "matchup": "Matchup", "possession": "Possession",
                   "explosiveness": "Explosive", "pressure": "Pressure",
                   "player_qb": "QB"}
    corr = scores[core].corr(method="pearson").round(3)

    # per-family correlation with V1 / ELO / EPA
    fam_corr = {}
    for fam in sorted(fams) + ["pressure"]:
        row = {}
        for t in ["ens_margin", "pred_elo", "pred_epa_m"]:
            if fam in scores and t in scores:
                row[t] = round(float(scores[fam].corr(scores[t])), 3)
        fam_corr[fam] = row

    result = {
        "scope": "descriptive only; 2021-2022, n=%d games; no predictive evaluation" % len(g),
        "family_score_method": ("mean of z-scored (home-away) differentials per family; "
                                "matchup uses game-level mx_* interactions; z-scored across "
                                "the 2021-2022 sample (descriptive, not predictive)"),
        "core_columns": core,
        "core_labels": core_labels,
        "correlation_matrix": {core_labels[c]: {core_labels[r]: float(corr.loc[r, c])
                                                for r in core} for c in core},
        "family_corr_with_v1_elo_epa": fam_corr,
        "coverage": coverage,
        "n_games": int(len(g)),
    }
    json.dump(result, open(OUT_JSON, "w"), indent=1)

    # markdown
    lines = ["# V2 Feature-Family Overlap Matrix", "",
             "DIAGNOSTIC ONLY — 2021–2022, n=%d games. No predictive evaluation, "
             "no model comparison, no gate pass/fail on any model." % len(g), "",
             "Family score = mean of z-scored (home − away) differentials across the "
             "family's numeric features (matchup uses game-level mx_* interactions). "
             "Z-scores computed across the 2021–2022 sample as a descriptive summary.", "",
             "## Core correlation matrix", "",
             "| | " + " | ".join(core_labels[c] for c in core) + " |",
             "|" + "---|" * (len(core) + 1)]
    for c in core:
        lines.append("| " + core_labels[c] + " | " +
                     " | ".join(f"{corr.loc[c, r]:.3f}" for r in core) + " |")
    lines += ["", "## Correlation of each family score with V1 / ELO / EPA", "",
              "| family | r(V1) | r(ELO) | r(EPA) |", "|---|---|---|---|"]
    for fam in sorted(fam_corr):
        r = fam_corr[fam]
        lines.append(f"| {fam} | {r.get('ens_margin','')} | {r.get('pred_elo','')} | {r.get('pred_epa_m','')} |")
    lines += ["", "## Coverage", "",
              "| family | features used / total | median non-NaN frac |",
              "|---|---|---|"]
    for fam, cov in coverage.items():
        lines.append(f"| {fam} | {cov['features_used']}/{cov['features_total']} | {cov['median_nonan_frac']} |")
    lines += ["", "## Interpretation",
              "See REPORT.md for the plain-language reading. Key questions this answers: "
              "(a) are the families distinct information sources or one latent variable; "
              "(b) which families track the V1/ELO/EPA latent strength axis most closely; "
              "(c) which families are the strongest candidates for orthogonal information "
              "(priority criterion, not exclusion — per Cale's refined filter)."]
    open(OUT_MD, "w").write("\n".join(lines) + "\n")
    print("wrote", OUT_JSON, "and", OUT_MD)
    print(corr)

if __name__ == "__main__":
    main()
