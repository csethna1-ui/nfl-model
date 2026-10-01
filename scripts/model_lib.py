"""Shared feature engineering + GBM factory for the NFL model."""
import numpy as np
import pandas as pd

try:
    from xgboost import XGBRegressor
    GBM_BACKEND = "xgboost"
except ImportError:
    from sklearn.ensemble import HistGradientBoostingRegressor
    GBM_BACKEND = "sklearn-hgbr"

MARGIN_FEATS = ["elo_diff",
    "off_epa_diff", "def_epa_diff", "off_pass_diff", "off_rush_diff",
    "def_pass_diff", "def_rush_diff", "sr_off_diff", "sr_def_diff",
    "rest_diff", "div_game", "week"]
TOTAL_FEATS = ["off_epa_sum", "def_epa_sum", "off_pass_sum", "off_rush_sum",
    "def_pass_sum", "def_rush_sum", "sr_off_sum", "sr_def_sum",
    "rest_diff", "div_game", "week"]
EPA_M_FEATS = ["off_epa_diff", "def_epa_diff", "off_pass_diff", "off_rush_diff",
               "def_pass_diff", "def_rush_diff", "sr_off_diff", "sr_def_diff"]
EPA_T_FEATS = ["off_epa_sum", "def_epa_sum", "off_pass_sum", "off_rush_sum",
               "def_pass_sum", "def_rush_sum"]

def add_features(d):
    d = d.copy()
    d["off_epa_diff"] = d["home_off_epa"] - d["away_off_epa"]
    d["def_epa_diff"] = d["home_def_epa"] - d["away_def_epa"]
    d["off_pass_diff"] = d["home_off_pass_epa"] - d["away_off_pass_epa"]
    d["off_rush_diff"] = d["home_off_rush_epa"] - d["away_off_rush_epa"]
    d["def_pass_diff"] = d["home_def_pass_epa"] - d["away_def_pass_epa"]
    d["def_rush_diff"] = d["home_def_rush_epa"] - d["away_def_rush_epa"]
    d["sr_off_diff"] = d["home_off_sr"] - d["away_off_sr"]
    d["sr_def_diff"] = d["home_def_sr"] - d["away_def_sr"]
    d["off_epa_sum"] = d["home_off_epa"] + d["away_off_epa"]
    d["def_epa_sum"] = d["home_def_epa"] + d["away_def_epa"]
    d["off_pass_sum"] = d["home_off_pass_epa"] + d["away_off_pass_epa"]
    d["off_rush_sum"] = d["home_off_rush_epa"] + d["away_off_rush_epa"]
    d["def_pass_sum"] = d["home_def_pass_epa"] + d["away_def_pass_epa"]
    d["def_rush_sum"] = d["home_def_rush_epa"] + d["away_def_rush_epa"]
    d["sr_off_sum"] = d["home_off_sr"] + d["away_off_sr"]
    d["sr_def_sum"] = d["home_def_sr"] + d["away_def_sr"]
    d["rest_diff"] = d["home_rest"] - d["away_rest"]
    return d

def make_gbm():
    if GBM_BACKEND == "xgboost":
        return XGBRegressor(n_estimators=200, max_depth=3, learning_rate=0.05,
                            subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
                            random_state=42, n_jobs=4)
    return HistGradientBoostingRegressor(max_iter=200, max_depth=3,
                            learning_rate=0.05, l2_regularization=1.0, random_state=42)


# ---------------- v2 additions (QB + weather). v1 lists above are untouched. --
V2_MARGIN_EXTRA = ["qb_epa_diff", "wind_eff"]
V2_TOTAL_EXTRA = ["wind_eff"]
MARGIN_FEATS_V2 = MARGIN_FEATS + V2_MARGIN_EXTRA
TOTAL_FEATS_V2 = TOTAL_FEATS + V2_TOTAL_EXTRA
EPA_M_FEATS_V2 = EPA_M_FEATS + ["qb_epa_diff", "wind_eff"]
EPA_T_FEATS_V2 = EPA_T_FEATS + ["wind_eff"]

OUTDOOR_MEDIAN_WIND = 8.0

def add_wind(d):
    """wind_eff: effective wind in mph. Domes / closed roofs -> 0.
    Outdoors/open with missing wind -> outdoor median (8 mph)."""
    d = d.copy()
    if "roof" in d.columns:
        calm = d["roof"].fillna("outdoors").isin(["dome", "closed"])
    else:
        calm = pd.Series(False, index=d.index)
    wind = d["wind"] if "wind" in d.columns else np.nan
    d["wind_eff"] = np.where(calm, 0.0, pd.to_numeric(wind, errors="coerce")).astype(float)
    d["wind_eff"] = d["wind_eff"].fillna(OUTDOOR_MEDIAN_WIND)
    return d
