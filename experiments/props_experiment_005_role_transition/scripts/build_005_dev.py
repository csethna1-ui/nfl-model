"""
Props Experiment 005 — DEV phase (frozen preregistration 2026-10-01).

DEV ONLY: fits candidates M1-M3 on 2021-2022. NO 2023-2024 data is loaded,
inspected, or summarized anywhere in this script (hard rule).

M0 = frozen Props Model D (Experiment 001), reproduced read-only by
re-executing the frozen 001 training procedure on train (2018-2020) with the
frozen dev-selected hyperparameters from dry_run_dev.json. No 001 pipeline
code or artifact is modified; reproduction is verified bit-identical against
the recorded 001 dev MAE before any candidate fitting.

Outputs (experiments/props_experiment_005_role_transition/):
  scripts/build_005_dev.py      (this file)
  data/dev_predictions.parquet  (M0 + M1/M2/M3 dev predictions, dev rows only)
  models/M{1,2,3}_{market}_fitted.pkl
  DEV_DIAGNOSTICS.md
  LOCKED_PARAMETERS.md
"""
import json, math, pickle, sys, time
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor

EXP = "/home/hatch/workspace/nfl-model/experiments/props_experiment_005_role_transition"
TABLE = "/home/hatch/workspace/nfl-model/experiments/player_props_projection/data/modeling_table.parquet"
SEL = "/home/hatch/workspace/nfl-model/experiments/player_props_projection/data/dry_run_dev.json"

SEED = 1337
RNG = np.random.default_rng(SEED)
HALF_LIFE = 3.0
MAX_TRAIL = 16

MARKETS = ["pass_yards", "rush_yards", "receiving_yards"]

# ---- frozen 001 feature lists (copied verbatim from run_experiment_001.py) ----
OPPORTUNITY_FEATS = [
    "trail_targets_ewma", "trail_rush_att_ewma", "trail_pass_att_ewma",
    "trail_target_share_ewma", "trail_rush_share_ewma", "trail_air_share_ewma",
    "trail_team_targets_ewma", "trail_team_pass_att_ewma", "trail_team_rush_att_ewma",
    "trail_rz_targets_ewma", "trail_rz_carries_ewma", "trail_air_yards_ewma",
    "trail_games",
]
EFFICIENCY_FEATS = [
    "trail_ypt_ewma", "trail_ypc_ewma", "trail_ypa_ewma",
    "trail_comp_rate_ewma", "trail_yac_pt_ewma",
]
YARDS_FEATS = ["trail_pass_yards_ewma", "trail_rush_yards_ewma", "trail_receiving_yards_ewma"]
OPP_FEATS = ["opp_trail_pass_allowed_ewma", "opp_trail_rush_allowed_ewma"]
ENV_FEATS = ["spread_line", "total_line", "is_home", "team_spread",
             "team_implied_total", "opp_implied_total"]
ALL_FEATS = OPPORTUNITY_FEATS + EFFICIENCY_FEATS + YARDS_FEATS + OPP_FEATS + ENV_FEATS
C_PARAMS = dict(loss="quantile", learning_rate=0.1, max_depth=3,
                max_iter=300, min_samples_leaf=20, random_state=7)
GBM_GRID = [{"learning_rate": lr, "max_depth": md, "max_iter": mi}
            for lr in (0.05, 0.1) for md in (3, 5) for mi in (200, 500)]
RIDGE_ALPHAS = [0.1, 1.0, 10.0, 100.0]

# ---- frozen 005 structural grids (prereg: grid-searched on dev only) ----
W_GRID = [0.0, 0.25, 0.5, 0.75, 1.0]
LAMBDA_GRID = [0.0, 0.25, 0.5, 1.0, 2.0]

EXPECTED_D_DEV_MAE = {"pass_yards": 57.774014152193786,
                      "rush_yards": 25.14778096197956,
                      "receiving_yards": 23.976700644236963}


def mae(y, p):
    return float(np.mean(np.abs(y - p)))


def ewma(v):
    """Frozen 001 convention: half-life 3, most-recent-first, NaN dropped."""
    v = np.asarray(v, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return np.nan
    w = 0.5 ** (np.arange(len(v)) / HALF_LIFE)
    return float(np.sum(w * v) / np.sum(w))


# ---------------- M0 reproduction (frozen 001 procedure, read-only) ----------------
def fit_A(train, alpha):
    X1 = train[OPPORTUNITY_FEATS].to_numpy(float)
    X2 = train[EFFICIENCY_FEATS].to_numpy(float)
    att = train["actual_att"].to_numpy(float)
    eff = train["actual_yards"].to_numpy(float) / np.maximum(att, 1e-6)
    s1, s2 = StandardScaler(), StandardScaler()
    r1 = Ridge(alpha=alpha).fit(s1.fit_transform(X1), att)
    r2 = Ridge(alpha=alpha).fit(s2.fit_transform(X2), eff)
    return (s1, r1, s2, r2)


def pred_A(model, df):
    s1, r1, s2, r2 = model
    o = np.maximum(r1.predict(s1.transform(df[OPPORTUNITY_FEATS].to_numpy(float))), 0.0)
    e = r2.predict(s2.transform(df[EFFICIENCY_FEATS].to_numpy(float)))
    return np.maximum(o * e, 0.0)


def fit_B(train, params):
    m = HistGradientBoostingRegressor(random_state=11, **params)
    return m.fit(train[ALL_FEATS].to_numpy(float), train["actual_yards"].to_numpy(float))


def pred_B(model, df):
    return np.maximum(model.predict(df[ALL_FEATS].to_numpy(float)), 0.0)


def fit_C(train):
    X = train[ALL_FEATS].to_numpy(float)
    y = train["actual_yards"].to_numpy(float)
    return {q: HistGradientBoostingRegressor(quantile=q, **C_PARAMS).fit(X, y)
            for q in (0.25, 0.5, 0.75)}


def pred_C(model, df, q=0.5):
    return np.maximum(model[q].predict(df[ALL_FEATS].to_numpy(float)), 0.0)

# ---------------- stint-aware trailing features (dev rows only) ----------------
def build_stint_features(dev):
    """
    For each dev row (player-game), compute from STRICTLY PRIOR games:
      stint_games  # prior games played with the current team
      transfer_ind # current stint began with a team change (player had a prior game)
      opp_cur      # EWMA of actual_att over prior in-stint games (recent-first, hl=3, max 16)
      opp_prior    # EWMA of actual_att over prior pre-stint games
      eff_cur      # EWMA of per-game yards/att over prior in-stint games
      eff_prior    # EWMA of per-game yards/att over prior pre-stint games
    A stint = maximal run of consecutive player-games with the same team.
    All inputs are completed-game records -> Friday 18:00 CT safe by construction.
    """
    dev = dev.sort_values(["player_name", "season", "week"]).reset_index(drop=True)
    # Name collisions: nflverse abbreviated player_name can collide across two
    # real players (e.g. A.Jones 2018 w14: DET 0 att + GB 17 att). The phantom
    # rows always carry ~zero opportunity; keep the max-actual_att row per
    # player-week so the stint walk sees one game per week. (The eligible dev
    # subsets used for fitting contain no such duplicates - asserted below.)
    ndup = int(dev.duplicated(["player_name", "season", "week"]).sum())
    if ndup:
        dev = (dev.sort_values("actual_att", ascending=False)
                  .drop_duplicates(["player_name", "season", "week"])
                  .sort_values(["player_name", "season", "week"]).reset_index(drop=True))
        print(f"  stint walk: dropped {ndup} phantom player-week rows (name collisions)", flush=True)
    dup = dev.duplicated(["player_name", "season", "week"]).sum()
    assert dup == 0, f"duplicate player-weeks in dev: {dup}"

    out = np.zeros((len(dev), 7))
    att = dev["actual_att"].to_numpy(float)
    yds = dev["actual_yards"].to_numpy(float)
    eff_game = np.where(att > 0, yds / np.maximum(att, 1e-9), np.nan)
    teams = dev["team"].to_numpy()

    idx = 0
    for player, grp in dev.groupby("player_name", sort=False):
        g = grp.sort_values(["season", "week"])
        pos = g.index.to_numpy()
        # walk games in time order, tracking current stint
        stint_start = 0  # position within this player's game list
        stint_is_transfer = False
        for j in range(len(g)):
            if j > 0 and teams[pos[j]] != teams[pos[j - 1]]:
                stint_start = j
                stint_is_transfer = True  # stint began with a team change (j>0: player had a prior game)
            # prior games: 0..j-1 ; in-stint priors: stint_start..j-1 ; pre-stint: 0..stint_start-1
            in_stint = pos[stint_start:j][::-1][:MAX_TRAIL]
            pre_stint = pos[:stint_start][::-1][:MAX_TRAIL]
            sg = j - stint_start
            # transfer_ind = 1 only on the stint's first game, when the stint
            # began with a team change (j==stint_start>0: player had a prior game)
            transfer = 1.0 if (j == stint_start and stint_start > 0) else 0.0
            out[pos[j], 0] = sg
            out[pos[j], 1] = transfer
            out[pos[j], 2] = ewma(att[in_stint]) if len(in_stint) else np.nan
            out[pos[j], 3] = ewma(att[pre_stint]) if len(pre_stint) else np.nan
            out[pos[j], 4] = ewma(eff_game[in_stint]) if len(in_stint) else np.nan
            out[pos[j], 5] = ewma(eff_game[pre_stint]) if len(pre_stint) else np.nan
            out[pos[j], 6] = 1.0 if stint_is_transfer else 0.0
        idx += 1

    cols = ["stint_games", "transfer_ind", "opp_cur", "opp_prior", "eff_cur", "eff_prior",
            "in_transfer_stint"]
    feat = pd.DataFrame(out, columns=cols, index=dev.index)
    # modeling-table convention: NaN -> 0 for rate/trailing features; stint_games kept
    for c in ["opp_cur", "opp_prior", "eff_cur", "eff_prior"]:
        feat[c] = feat[c].fillna(0.0)
    return pd.concat([dev.reset_index(drop=True), feat.reset_index(drop=True)], axis=1)


def blend_opp(df, w, lam=0.0):
    """M1/M2 opportunity blend. lam=0 reduces M2 to M1 exactly."""
    decay = np.exp(-lam * df["stint_games"].to_numpy(float))
    return w * df["opp_cur"].to_numpy(float) + (1.0 - w) * decay * df["opp_prior"].to_numpy(float)


def blend_eff(df, v):
    return v * df["eff_cur"].to_numpy(float) + (1.0 - v) * df["eff_prior"].to_numpy(float)


# ---------------- candidate fitting ----------------
def fit_ridge(X, y, alpha):
    s = StandardScaler()
    m = Ridge(alpha=alpha).fit(s.fit_transform(X), y)
    return (s, m)


def pred_ridge(model, X):
    s, m = model
    return m.predict(s.transform(X))


def rung_features(rung, df, m0, w=None, lam=0.0, v=None):
    base = {"m0": m0,
            "transfer_ind": df["transfer_ind"].to_numpy(float),
            "stint_games": df["stint_games"].to_numpy(float)}
    if rung == "M1":
        base["opp_blend"] = blend_opp(df, w)
        order = ["m0", "opp_blend", "transfer_ind", "stint_games"]
    elif rung == "M2":
        base["opp_blend"] = blend_opp(df, w, lam)
        order = ["m0", "opp_blend", "transfer_ind", "stint_games"]
    elif rung == "M3":
        ob = blend_opp(df, w)
        eb = blend_eff(df, v)
        base["opp_blend"] = ob
        base["eff_blend"] = eb
        base["opp_x_eff"] = ob * eb
        order = ["m0", "opp_blend", "eff_blend", "opp_x_eff", "transfer_ind", "stint_games"]
    return np.column_stack([base[k] for k in order]), order


def fit_rung(rung, df, m0, y):
    """
    Frozen selection procedure: grid over structural params x {Ridge alphas, GBM 8-combo},
    select by dev MAE (in-sample; the locked test is the honest evaluation).
    Returns (best structural dict, best model-class, best hyperparams, fitted model, feature order).
    """
    best = {"mae": np.inf}
    if rung == "M1":
        struct_grid = [{"w": w} for w in W_GRID]
    elif rung == "M2":
        struct_grid = [{"w": w, "lam": lam} for w in W_GRID for lam in LAMBDA_GRID]
    elif rung == "M3":
        struct_grid = [{"w": w, "v": v} for w in W_GRID for v in W_GRID]
    for sp in struct_grid:
        X, order = rung_features(rung, df, m0, **sp)
        for alpha in RIDGE_ALPHAS:
            mdl = fit_ridge(X, y, alpha)
            p = pred_ridge(mdl, X)
            m = mae(y, p)
            if m < best["mae"]:
                best = {"mae": m, "struct": sp, "class": "ridge",
                        "hyper": {"alpha": alpha}, "model": mdl, "order": order}
        for gp in GBM_GRID:
            mdl = HistGradientBoostingRegressor(random_state=11, **gp).fit(X, y)
            p = np.maximum(mdl.predict(X), 0.0)
            m = mae(y, p)
            if m < best["mae"]:
                best = {"mae": m, "struct": sp, "class": "gbm",
                        "hyper": dict(gp), "model": mdl, "order": order}
    return best

def cv_mae_diag(rung, df, m0, y, struct, cls, hyper, k=5, seed=1337):
    """
    Honesty diagnostic ONLY (does not affect selection): k-fold CV MAE on dev
    for the locked (struct, class, hyper). Selection itself stays in-sample
    per the frozen procedure; this reports how much of the dev gain is
    in-sample optimism. The locked test remains the honest evaluation.
    """
    rng = np.random.default_rng(seed)
    idx = np.arange(len(y))
    rng.shuffle(idx)
    folds = np.array_split(idx, k)
    maes = []
    for f in folds:
        tr_idx = np.concatenate([f_ for f_ in folds if f_ is not f])
        Xtr, _ = rung_features(rung, df.iloc[tr_idx], m0[tr_idx], **struct)
        Xte, _ = rung_features(rung, df.iloc[f], m0[f], **struct)
        if cls == "ridge":
            mdl = fit_ridge(Xtr, y[tr_idx], hyper["alpha"])
            p = pred_ridge(mdl, Xte)
        else:
            mdl = HistGradientBoostingRegressor(random_state=11, **hyper).fit(Xtr, y[tr_idx])
            p = np.maximum(mdl.predict(Xte), 0.0)
        maes.append(mae(y[f], p))
    return float(np.mean(maes))


# ---------------- main: DEV ONLY ----------------
def main():
    t0 = time.time()
    sel = json.load(open(SEL))["selection"]

    full = pd.read_parquet(TABLE)
    # HARD RULE: the locked test (2023-2024) is never loaded for this experiment.
    work = full[full["period"].isin(["train", "dev"])].copy()
    assert "test" not in work["period"].unique(), "locked-test rows present - ABORT"
    assert not ((work["season"] == 2023) | (work["season"] == 2024)).any(), "2023/2024 rows present - ABORT"
    assert not (work["season"] == 2025).any() and not (work["season"] == 2026).any()

    ev = work[(work["eligible_hist"] == 1) & (work["played_role"] == 1)].copy()
    train = {m: ev[(ev["period"] == "train") & (ev["market"] == m)].reset_index(drop=True)
             for m in MARKETS}
    # Stint history must include train-period games (and ineligible rows): build the
    # walk on ALL train+dev rows per market. Name collisions are resolved to the
    # max-actual_att row per player-week for the HISTORY chain only (documented
    # approximation; ~1% of rows). The EVALUATED dev set keeps every 001 row
    # (including same-week namesakes, which 001 evaluated separately); stint
    # features join onto evaluated rows m:1, so namesakes share the max-att
    # chain's features. M0 comparability is preserved exactly.
    FEAT_COLS = ["player_name", "season", "week", "stint_games", "transfer_ind",
                 "opp_cur", "opp_prior", "eff_cur", "eff_prior", "in_transfer_stint"]
    hist = {m: work[work["market"] == m].reset_index(drop=True) for m in MARKETS}
    dev = {}
    for m in MARKETS:
        hmf = build_stint_features(hist[m])
        direct = ev[(ev["period"] == "dev") & (ev["market"] == m)].reset_index(drop=True)
        dev[m] = direct.merge(hmf[FEAT_COLS], on=["player_name", "season", "week"],
                              how="left", validate="m:1")
        assert dev[m][FEAT_COLS[3:]].notna().all().all(), f"stint join produced NaNs for {m}"

    results, locked, pred_rows = {}, {}, []
    for market in MARKETS:
        tr, dv = train[market], dev[market]
        y = dv["actual_yards"].to_numpy(float)

        # ---- M0: reproduce frozen Model D read-only, verify bit-identical ----
        A = fit_A(tr, sel[market]["a_alpha"])
        B = fit_B(tr, sel[market]["b_params"])
        C = fit_C(tr)
        pA, pB, pC = pred_A(A, dv), pred_B(B, dv), pred_C(C, dv)
        m0 = (pA + pB + pC) / 3.0
        m0_mae = mae(y, m0)
        exp = EXPECTED_D_DEV_MAE[market]
        assert abs(m0_mae - exp) < 1e-6, (
            f"M0 reproduction mismatch for {market}: got {m0_mae}, frozen 001 recorded {exp}")
        print(f"[{market}] M0 reproduced bit-identical (dev MAE {m0_mae:.4f}), n={len(dv)}", flush=True)

        # ---- candidate fitting on the eligible dev rows (stint features built above) ----
        dvf = dev[market]

        # ---- fit rungs ----
        rung_best = {}
        for rung in ("M1", "M2", "M3"):
            b = fit_rung(rung, dvf, m0, y)
            rung_best[rung] = b
            X, _ = rung_features(rung, dvf, m0, **b["struct"])
            p = pred_ridge(b["model"], X) if b["class"] == "ridge" else np.maximum(b["model"].predict(X), 0.0)
            b["pred"] = p
            print(f"[{market}] {rung}: dev MAE {b['mae']:.4f} "
                  f"(M0 {m0_mae:.4f}) | struct={b['struct']} class={b['class']} hyper={b['hyper']}",
                  flush=True)
            # persist fitted model for the future locked-test run
            with open(f"{EXP}/models/{rung}_{market}_fitted.pkl", "wb") as f:
                pickle.dump({"struct": b["struct"], "class": b["class"],
                             "hyper": b["hyper"], "model": b["model"],
                             "order": b["order"]}, f)
            # honesty diagnostic: CV MAE for the locked config (reported only)
            b["cv_mae"] = cv_mae_diag(rung, dvf.reset_index(drop=True), m0, y,
                                      b["struct"], b["class"], b["hyper"])
            print(f"[{market}] {rung}: CV MAE {b['cv_mae']:.4f} (in-sample {b['mae']:.4f})",
                  flush=True)

        # ---- slice diagnostics ----
        in_ts = (dvf["in_transfer_stint"] == 1.0).to_numpy()
        sg = dvf["stint_games"].to_numpy()
        # stint_games = # PRIOR games in stint, so game number = stint_games+1:
        # games 1-3 -> sg 0..2 ; games 4-6 -> sg 3..5
        slices = {
            "overall": np.ones(len(dvf), bool),
            "transfer_stint": in_ts,
            "stint_1_3": in_ts & (sg <= 2),
            "stint_4_6": in_ts & (sg >= 3) & (sg <= 5),
            "non_transfer": ~in_ts,
        }
        diag = {"M0": {}, "M1": {}, "M2": {}, "M3": {}}
        preds = {"M0": m0, "M1": rung_best["M1"]["pred"],
                 "M2": rung_best["M2"]["pred"], "M3": rung_best["M3"]["pred"]}
        for sname, mask in slices.items():
            n = int(mask.sum())
            for rung in ("M0", "M1", "M2", "M3"):
                diag[rung][sname] = {"mae": mae(y[mask], preds[rung][mask]) if n else None, "n": n}
        results[market] = {"n": len(dv), "m0_mae": m0_mae, "diag": diag}
        locked[market] = {r: {"struct": rung_best[r]["struct"], "class": rung_best[r]["class"],
                              "hyper": rung_best[r]["hyper"], "order": rung_best[r]["order"],
                              "dev_mae_in_sample": rung_best[r]["mae"],
                              "dev_mae_cv5": rung_best[r]["cv_mae"]}
                          for r in ("M1", "M2", "M3")}

        pr = dvf[["player_name", "team", "opponent", "season", "week", "actual_yards",
                  "stint_games", "transfer_ind"]].copy()
        pr["market"] = market
        pr["pred_M0"] = m0
        for r in ("M1", "M2", "M3"):
            pr[f"pred_{r}"] = rung_best[r]["pred"]
        pred_rows.append(pr)

    import os
    os.makedirs(f"{EXP}/data", exist_ok=True)
    os.makedirs(f"{EXP}/models", exist_ok=True)
    pd.concat(pred_rows, ignore_index=True).to_parquet(f"{EXP}/data/dev_predictions.parquet", index=False)
    json.dump(locked, open(f"{EXP}/LOCKED_PARAMETERS.json", "w"), indent=1)
    print(f"dev predictions + locked params written ({time.time()-t0:.0f}s)", flush=True)
    return results, locked


if __name__ == "__main__":
    main()
