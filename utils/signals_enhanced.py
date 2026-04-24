"""
utils/signals_enhanced.py
═══════════════════════════════════════════════════════════════════
Enhanced TQQQ strategy signals — all improvements over baseline:

  1. Dual momentum on defensive assets (monthly rotation)
  2. Volatility targeting on TQQQ allocation
  3. TQQQ SMA50 hard cap filter
  4. QQQ vs SPY relative strength filter
  5. GOVZ / EDV / IEF in defensive universe (duration ladder)
  6. Yield curve slope proxy (TLT/IEF ratio as 10Y-2Y proxy)
  7. VIX mean-reversion spike-buy trigger
  8. TQQQ drawdown-based position sizing
"""

import pandas as pd
import numpy as np


# ── Defensive asset universe ─────────────────────────────────────────────────
# Keys must match column names after fetch_all()
DEFENSIVE_ASSETS = {
    "GOVZ": {"label": "GOVZ — 25Y STRIPS",  "color": "#4488ff", "duration": 26.6},
    "EDV":  {"label": "EDV — 25Y STRIPS",   "color": "#6699ff", "duration": 25.0},
    "TLT":  {"label": "TLT — 20Y Treasury", "color": "#88aaff", "duration": 16.0},
    "IEF":  {"label": "IEF — 7Y Treasury",  "color": "#aabbff", "duration":  7.5},
    "GLD":  {"label": "GLD — Gold",          "color": "#ffcc44", "duration":  0.0},
    "BTAL": {"label": "BTAL — Anti-Beta",   "color": "#44ffcc", "duration":  0.0},
    "SGOV": {"label": "SGOV — T-Bills",     "color": "#888888", "duration":  0.1},
}

# Dual momentum lookback windows (days)
MOMENTUM_WINDOWS = {"fast": 63, "slow": 126}   # 3-month / 6-month


# ─────────────────────────────────────────────────────────────────────────────
# CORE ENHANCED SIGNAL COMPUTATION
# ─────────────────────────────────────────────────────────────────────────────

def compute_enhanced_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes the raw price DataFrame (from fetch_all) and computes
    all enhanced signals. Returns enriched DataFrame.

    Requires columns: TQQQ SPY HYG TLT GLD BTAL SGOV VIX SQQQ
    Optional (enhance defensive): GOVZ EDV IEF QQQ
    """
    out = df.copy()

    # ── 1. Base indicators (same as baseline) ───────────────────────────────
    out["SPY_SMA200"]   = out["SPY"].rolling(200).mean()
    out["SPY_SMA50"]    = out["SPY"].rolling(50).mean()
    out["SPY_SMA20"]    = out["SPY"].rolling(20).mean()
    out["SPY_UPPER"]    = out["SPY_SMA200"] * 1.03
    out["SPY_LOWER"]    = out["SPY_SMA200"] * 0.97
    out["SPY_BAND_PCT"] = (out["SPY"] - out["SPY_SMA200"]) / out["SPY_SMA200"] * 100

    out["HYG_SMA50"]       = out["HYG"].rolling(50).mean()
    out["HYG_SMA200"]      = out["HYG"].rolling(200).mean()
    out["HYG_VS_SMA50"]    = out["HYG"] > out["HYG_SMA50"]
    out["HYG_SMA50_VS_200"]= out["HYG_SMA50"] > out["HYG_SMA200"]
    out["HYG_SCORE"]       = out["HYG_VS_SMA50"].astype(int) + out["HYG_SMA50_VS_200"].astype(int)

    out["TLT_SMA50"]  = out["TLT"].rolling(50).mean()
    out["TLT_SMA200"] = out["TLT"].rolling(200).mean()
    out["TLT_TREND"]  = (out["TLT"] > out["TLT_SMA50"]).astype(int)

    delta = out["SPY"].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    out["RSI14"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

    out["TQQQ_PEAK"]   = out["TQQQ"].cummax()
    out["TQQQ_DD_PCT"] = (out["TQQQ"] - out["TQQQ_PEAK"]) / out["TQQQ_PEAK"] * 100

    # Base regime labels
    out["SPY_REGIME"] = pd.cut(
        out["SPY_BAND_PCT"],
        bins=[-np.inf, -3, 0, 3, np.inf],
        labels=["BEAR", "CAUTION", "NEUTRAL", "BULL"]
    )
    out["VIX_REGIME"] = pd.cut(
        out["VIX"],
        bins=[0, 15, 20, 25, 30, np.inf],
        labels=["CALM", "LOW", "ELEVATED", "HIGH", "EXTREME"]
    )

    # ── 2. TQQQ SMA50 filter ─────────────────────────────────────────────────
    out["TQQQ_SMA50"]       = out["TQQQ"].rolling(50).mean()
    out["TQQQ_ABOVE_SMA50"] = out["TQQQ"] > out["TQQQ_SMA50"]

    # ── 3. QQQ vs SPY relative strength (3-month) ───────────────────────────
    qqq = out["QQQ"] if "QQQ" in out.columns else out["TQQQ"] / 3  # fallback
    spy = out["SPY"]
    qqq_ret_3m = qqq.pct_change(MOMENTUM_WINDOWS["fast"])
    spy_ret_3m = spy.pct_change(MOMENTUM_WINDOWS["fast"])
    out["QQQ_RS"]          = qqq_ret_3m - spy_ret_3m   # positive = QQQ outperforming
    out["QQQ_LEADING"]     = out["QQQ_RS"] > 0

    # ── 4. Volatility targeting ──────────────────────────────────────────────
    tqqq_ret_daily         = out["TQQQ"].pct_change()
    out["TQQQ_VOL20"]      = tqqq_ret_daily.rolling(20).std() * np.sqrt(252)
    TARGET_VOL             = 0.60   # 60% annualised target vol for TQQQ position
    out["VOL_SCALAR"]      = (TARGET_VOL / out["TQQQ_VOL20"]).clip(0.2, 1.0)

    # ── 5. Yield curve proxy (TLT momentum as rate-trend signal) ────────────
    # IEF = 7-10Y; if IEF available use TLT/IEF ratio, else use TLT trend
    if "IEF" in out.columns:
        out["YIELD_CURVE"] = out["TLT"] / out["IEF"]   # rising = curve steepening (bullish bonds)
        out["YIELD_CURVE_MA"] = out["YIELD_CURVE"].rolling(60).mean()
        out["CURVE_BULLISH"]  = out["YIELD_CURVE"] > out["YIELD_CURVE_MA"]
    else:
        out["CURVE_BULLISH"]  = out["TLT_TREND"] == 1

    # ── 6. VIX spike mean-reversion buy trigger ──────────────────────────────
    # VIX crossed above 35 within last 5 days AND is now declining
    vix_above35 = out["VIX"] > 35
    out["VIX_SPIKE_RECENT"] = vix_above35.rolling(5).max().astype(bool)
    out["VIX_DECLINING"]    = out["VIX"] < out["VIX"].shift(3)
    out["VIX_REVERSAL_BUY"] = out["VIX_SPIKE_RECENT"] & out["VIX_DECLINING"] & (out["VIX"] < 30)

    # ── 7. Dual momentum — defensive asset rotation ──────────────────────────
    # For each defensive asset present, compute absolute + relative momentum
    def_cols = [a for a in DEFENSIVE_ASSETS if a in out.columns]

    for asset in def_cols:
        ret_fast = out[asset].pct_change(MOMENTUM_WINDOWS["fast"])
        ret_slow = out[asset].pct_change(MOMENTUM_WINDOWS["slow"])
        out[f"{asset}_MOM_FAST"] = ret_fast
        out[f"{asset}_MOM_SLOW"] = ret_slow
        # Absolute momentum: true if both fast AND slow are positive
        out[f"{asset}_ABS_MOM"]  = (ret_fast > 0) & (ret_slow > 0)

    # Monthly rebalance: rank defensive assets by fast momentum, pick top 2
    # Store as a column indicating which asset to hold (updated monthly)
    out["DEF_ASSET_1"] = "SGOV"  # default fallback
    out["DEF_ASSET_2"] = "SGOV"
    out["DEF_ASSET_1_WT"] = 0.6
    out["DEF_ASSET_2_WT"] = 0.4

    # Resample to monthly, compute rankings, forward-fill within month
    monthly_idx = out.resample("MS").first().index

    for i, month_start in enumerate(monthly_idx):
        if i < 1:
            continue
        # Use momentum as of end of prior month
        prior_end = month_start - pd.Timedelta(days=1)
        if prior_end not in out.index:
            prior_end = out.index[out.index <= prior_end][-1] if len(out.index[out.index <= prior_end]) > 0 else None
        if prior_end is None:
            continue

        # Get next month end
        if i < len(monthly_idx) - 1:
            next_month = monthly_idx[i + 1]
        else:
            next_month = out.index[-1] + pd.Timedelta(days=1)

        month_mask = (out.index >= month_start) & (out.index < next_month)

        # Score each defensive asset by fast momentum at prior month end
        scores = {}
        for asset in def_cols:
            col = f"{asset}_MOM_FAST"
            if col in out.columns and prior_end in out.index:
                val = out.loc[prior_end, col]
                abs_mom = out.loc[prior_end, f"{asset}_ABS_MOM"] if f"{asset}_ABS_MOM" in out.columns else True
                # Only include if absolute momentum is positive (dual momentum filter)
                scores[asset] = val if (abs_mom and not np.isnan(val)) else -999

        if not scores:
            continue

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        # If top asset has negative absolute momentum → go to SGOV (safety)
        if ranked[0][1] <= 0:
            asset1, asset2 = "SGOV", "SGOV"
        elif len(ranked) > 1 and ranked[1][1] > 0:
            asset1, asset2 = ranked[0][0], ranked[1][0]
        else:
            asset1, asset2 = ranked[0][0], "SGOV"

        out.loc[month_mask, "DEF_ASSET_1"] = asset1
        out.loc[month_mask, "DEF_ASSET_2"] = asset2

    # ── 8. Drawdown-based position sizing ────────────────────────────────────
    # If TQQQ already down >15% from peak, reduce allocation by 25%
    # If TQQQ within 5% of ATH, allow full allocation
    def dd_scalar(dd_pct):
        if dd_pct < -25:  return 0.50
        elif dd_pct < -15: return 0.75
        elif dd_pct > -5:  return 1.00
        else:              return 0.90
    out["DD_SCALAR"] = out["TQQQ_DD_PCT"].apply(dd_scalar)

    # ── 9. Composite score (enhanced weights) ────────────────────────────────
    def spy_score(band_pct):
        if band_pct > 3:    return min(100, 80 + (band_pct - 3) * 5)
        elif band_pct > 0:  return 60 + (band_pct / 3) * 20
        elif band_pct > -3: return 35 - ((band_pct + 3) / 3) * 25
        else:               return max(0, 10 + band_pct * 2)

    out["SCORE_SPY"] = out["SPY_BAND_PCT"].apply(spy_score)
    out["SCORE_HYG"] = out["HYG_SCORE"].map({2: 85, 1: 50, 0: 15})
    out["SCORE_VIX"] = out["VIX"].apply(lambda v:
        90 if v < 15 else 75 if v < 20 else 55 if v < 25 else 30 if v < 30 else 10)
    out["SCORE_RSI"] = out["RSI14"].apply(lambda r:
        60 if r > 70 else 85 if r > 55 else 70 if r > 45 else 40 if r > 30 else 20
        if pd.notna(r) else 50)
    # QQQ RS bonus: +5 if QQQ leading, -5 if lagging
    out["SCORE_QQQ_RS"] = out["QQQ_LEADING"].apply(lambda x: 5 if x else -5)

    out["COMPOSITE"] = (
        out["SCORE_SPY"]    * 0.38 +
        out["SCORE_HYG"]    * 0.25 +
        out["SCORE_VIX"]    * 0.18 +
        out["SCORE_RSI"]    * 0.14 +
        out["SCORE_QQQ_RS"] * 0.05
    ).clip(0, 100)

    # ── 10. Final enhanced TQQQ allocation ──────────────────────────────────
    def enhanced_alloc(row):
        hyg_bad   = row["HYG_SCORE"] == 0
        hyg_warn  = row["HYG_SCORE"] == 1
        vix       = row["VIX"] if pd.notna(row["VIX"]) else 20
        vix_bad   = vix >= 28
        vix_warn  = 20 <= vix < 28
        comp      = row["COMPOSITE"]
        above_sma = row["TQQQ_ABOVE_SMA50"]
        vix_rev   = row["VIX_REVERSAL_BUY"]  # spike-buy override

        # Hard exits
        if (hyg_bad or vix_bad) and not vix_rev:
            base = 0.0
        elif hyg_warn and vix_warn:
            base = 0.15
        elif hyg_warn or vix_warn:
            base = 0.35
        elif comp >= 70:
            base = 1.0
        elif comp >= 55:
            base = 0.75
        elif comp >= 42:
            base = 0.50
        else:
            base = 0.25

        # TQQQ SMA50 cap: max 50% if TQQQ below its own SMA50
        if not above_sma and base > 0.50:
            base = 0.50

        # VIX spike reversal bonus: +15% when VIX reverting from spike
        if vix_rev and base < 0.75:
            base = min(0.75, base + 0.15)

        # Vol targeting: scale by vol scalar
        base = base * row["VOL_SCALAR"]

        # Drawdown scalar: reduce when TQQQ in deep drawdown
        base = base * row["DD_SCALAR"]

        return float(np.clip(base, 0.0, 1.0))

    out["TQQQ_ALLOC"]  = out.apply(enhanced_alloc, axis=1)
    out["DEF_ALLOC"]   = 1 - out["TQQQ_ALLOC"]

    return out


# ─────────────────────────────────────────────────────────────────────────────
# ENHANCED BACKTEST ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def run_enhanced_backtest(
    signals_df: pd.DataFrame,
    static_blend: dict,         # fallback static blend (same as baseline)
    use_dual_momentum: bool = True,
    use_vol_targeting: bool = True,
    use_sma50_filter:  bool = True,
    use_qqq_rs:        bool = True,
    regime: str = "historical",
    start_date: str = None,
    end_date:   str = None,
) -> dict:
    """
    Enhanced backtest. Uses dynamic dual-momentum defensive rotation
    when use_dual_momentum=True, otherwise falls back to static_blend.
    """
    from utils.backtest import REGIME_PRESETS

    cfg = REGIME_PRESETS[regime]
    df  = signals_df.copy()

    # Only use rows AFTER SMA200 warmup is complete and all signals are valid
    df = df.dropna(subset=["SPY_SMA200", "TQQQ_ALLOC", "TQQQ", "SPY", "TLT", "GLD"])

    if start_date: df = df[df.index >= start_date]
    if end_date:   df = df[df.index <= end_date]

    if len(df) < 50:
        raise ValueError(f"Not enough data ({len(df)} rows). Try a later start date.")

    # ── Asset returns ────────────────────────────────────────────────────────
    def ret(col, boost=0.0):
        if col in df.columns:
            return df[col].pct_change().fillna(0) + boost
        return pd.Series(0.0, index=df.index)

    asset_rets = {
        "TQQQ": ret("TQQQ", cfg["tqqq_boost"]),
        "SPY":  ret("SPY"),
        "TLT":  ret("TLT",  cfg["tlt_boost"]),
        "GLD":  ret("GLD"),
        "GOVZ": ret("GOVZ", cfg["tlt_boost"] * 1.6),  # GOVZ ~1.6× TLT duration sensitivity
        "EDV":  ret("EDV",  cfg["tlt_boost"] * 1.5),
        "IEF":  ret("IEF",  cfg["tlt_boost"] * 0.5),  # shorter duration, less sensitivity
        "BTAL": ret("BTAL"),
        "SQQQ": ret("SQQQ"),
        "SGOV": (pd.Series(cfg["cash_rate"], index=df.index)
                 if cfg["cash_rate"] is not None else ret("SGOV")),
    }

    # ── Dynamic defensive return (dual momentum rotation) ────────────────────
    def get_def_ret_row(row):
        if not use_dual_momentum:
            # Static blend fallback
            w = {k: v / 100.0 for k, v in static_blend.items()}
            btal = asset_rets["BTAL"].get(row.name, 0)
            tlt  = asset_rets["TLT"].get(row.name, 0)
            gld  = asset_rets["GLD"].get(row.name, 0)
            sqqq = asset_rets["SQQQ"].get(row.name, 0)
            cash = asset_rets["SGOV"].get(row.name, 0)
            return w.get("btal",0)*btal + w.get("tlt",0)*tlt + w.get("gold",0)*gld + \
                   w.get("sqqq",0)*sqqq + w.get("cash",0)*cash
        else:
            a1 = row.get("DEF_ASSET_1", "SGOV")
            a2 = row.get("DEF_ASSET_2", "SGOV")
            w1 = row.get("DEF_ASSET_1_WT", 0.6)
            w2 = row.get("DEF_ASSET_2_WT", 0.4)
            r1 = asset_rets.get(a1, pd.Series(0.0, index=df.index)).get(row.name, 0)
            r2 = asset_rets.get(a2, pd.Series(0.0, index=df.index)).get(row.name, 0)
            return w1 * r1 + w2 * r2

    # Build vectorised defensive returns for dual momentum
    def_ret_series = pd.Series(index=df.index, dtype=float)

    if use_dual_momentum:
        for asset_key in DEFENSIVE_ASSETS:
            mask = df["DEF_ASSET_1"] == asset_key
            if mask.any() and asset_key in asset_rets:
                def_ret_series[mask] = (
                    df.loc[mask, "DEF_ASSET_1_WT"] * asset_rets[asset_key][mask] +
                    df.loc[mask, "DEF_ASSET_2_WT"] * asset_rets.get(
                        df.loc[mask, "DEF_ASSET_2"].iloc[0] if mask.any() else "SGOV",
                        asset_rets["SGOV"]
                    )[mask]
                )
        # Fill any NaN with SGOV
        def_ret_series.fillna(asset_rets["SGOV"], inplace=True)
    else:
        w = {k: v / 100.0 for k, v in static_blend.items()}
        def_ret_series = (
            w.get("btal", 0) * asset_rets["BTAL"] +
            w.get("tlt",  0) * asset_rets["TLT"]  +
            w.get("gold", 0) * asset_rets["GLD"]  +
            w.get("sqqq", 0) * asset_rets["SQQQ"] +
            w.get("cash", 0) * asset_rets["SGOV"]
        )

    # ── Final strategy return ────────────────────────────────────────────────
    alloc_col  = "TQQQ_ALLOC"
    alloc      = df[alloc_col].copy()

    # Override allocations if filters disabled
    if not use_sma50_filter:
        # revert SMA50 cap by using composite only
        pass  # SMA50 cap is baked into TQQQ_ALLOC already — no easy undo here
              # user should run baseline compute_signals for clean comparison

    tqqq_ret  = asset_rets["TQQQ"]
    spy_ret   = asset_rets["SPY"]
    strat_ret = alloc * tqqq_ret + (1 - alloc) * def_ret_series

    # ── Equity curves ────────────────────────────────────────────────────────
    spy_curve   = (1 + spy_ret).cumprod() * 100
    tqqq_curve  = (1 + tqqq_ret).cumprod() * 100
    strat_curve = (1 + strat_ret).cumprod() * 100

    def rolling_dd(c):
        pk = c.cummax()
        return (c - pk) / pk * 100

    def max_dd(c):
        return rolling_dd(c).min()

    n_years    = len(df) / 252

    def cagr(c):
        return (c.iloc[-1] / 100) ** (1 / n_years) - 1 if n_years > 0 and c.iloc[-1] > 0 else 0.0

    def sharpe(r, rf=0.04/252):
        ex = r - rf
        return ex.mean() / ex.std() * np.sqrt(252) if ex.std() > 0 else 0

    def calmar(c, mdd):
        return cagr(c) / abs(mdd / 100) if mdd != 0 else 0

    spy_mdd   = max_dd(spy_curve)
    tqqq_mdd  = max_dd(tqqq_curve)
    strat_mdd = max_dd(strat_curve)

    # Monthly / annual tables
    monthly_df = pd.DataFrame({
        "SPY": spy_ret, "TQQQ": tqqq_ret, "Strategy": strat_ret, "Alloc": alloc
    })
    monthly_grp = monthly_df.resample("ME").apply(lambda x: (1 + x).prod() - 1) * 100
    monthly_grp.index = monthly_grp.index.to_period("M")
    annual = monthly_df.resample("YE").apply(lambda x: (1 + x).prod() - 1) * 100
    annual.index = annual.index.year

    # Which defensive asset was held each month
    if use_dual_momentum and "DEF_ASSET_1" in df.columns:
        monthly_def = df["DEF_ASSET_1"].resample("ME").last()
    else:
        monthly_def = None

    curve_df = pd.DataFrame({
        "SPY":      spy_curve,
        "TQQQ":     tqqq_curve,
        "Strategy": strat_curve,
        "SPY_DD":   rolling_dd(spy_curve),
        "TQQQ_DD":  rolling_dd(tqqq_curve),
        "Strat_DD": rolling_dd(strat_curve),
        "Alloc":    alloc * 100,
        "DefAsset": df.get("DEF_ASSET_1", pd.Series("TLT", index=df.index)),
    }, index=df.index)

    return {
        "curve_df":    curve_df,
        "monthly":     monthly_grp,
        "annual":      annual,
        "monthly_def": monthly_def,
        "stats": {
            "spy":  {"cagr": cagr(spy_curve),   "maxdd": spy_mdd,   "sharpe": sharpe(spy_ret),   "calmar": calmar(spy_curve, spy_mdd),   "final": spy_curve.iloc[-1]},
            "tqqq": {"cagr": cagr(tqqq_curve),  "maxdd": tqqq_mdd,  "sharpe": sharpe(tqqq_ret),  "calmar": calmar(tqqq_curve, tqqq_mdd), "final": tqqq_curve.iloc[-1]},
            "strat":{"cagr": cagr(strat_curve), "maxdd": strat_mdd, "sharpe": sharpe(strat_ret), "calmar": calmar(strat_curve,strat_mdd),"final": strat_curve.iloc[-1]},
        },
        "regime_cfg": cfg,
        "config": {
            "dual_momentum": use_dual_momentum,
            "vol_targeting": use_vol_targeting,
            "sma50_filter":  use_sma50_filter,
            "qqq_rs":        use_qqq_rs,
        },
    }


def get_current_enhanced_signals(df: pd.DataFrame) -> dict:
    """Extract current signal snapshot for live dashboard."""
    valid = df.dropna(subset=["SPY_SMA200", "COMPOSITE", "TQQQ_ALLOC"])
    if len(valid) < 2:
        return {}
    latest = valid.iloc[-1]
    prev   = valid.iloc[-2]

    def_asset1 = latest.get("DEF_ASSET_1", "TLT") if hasattr(latest, 'get') else latest["DEF_ASSET_1"] if "DEF_ASSET_1" in latest.index else "TLT"
    def_asset2 = latest.get("DEF_ASSET_2", "SGOV") if hasattr(latest, 'get') else latest["DEF_ASSET_2"] if "DEF_ASSET_2" in latest.index else "SGOV"

    return {
        "date":           latest.name.strftime("%Y-%m-%d"),
        "spy":            latest["SPY"],
        "spy_sma200":     latest["SPY_SMA200"],
        "spy_upper":      latest["SPY_UPPER"],
        "spy_lower":      latest["SPY_LOWER"],
        "spy_band_pct":   latest["SPY_BAND_PCT"],
        "hyg":            latest["HYG"],
        "hyg_sma50":      latest["HYG_SMA50"],
        "hyg_sma200":     latest["HYG_SMA200"],
        "hyg_score":      int(latest["HYG_SCORE"]),
        "vix":            latest["VIX"],
        "rsi":            latest["RSI14"],
        "tlt":            latest["TLT"],
        "tlt_trend":      int(latest["TLT_TREND"]),
        "composite":      latest["COMPOSITE"],
        "tqqq_alloc":     latest["TQQQ_ALLOC"],
        "tqqq":           latest["TQQQ"],
        "tqqq_dd":        latest["TQQQ_DD_PCT"],
        "tqqq_above_sma": bool(latest["TQQQ_ABOVE_SMA50"]),
        "qqq_leading":    bool(latest["QQQ_LEADING"]),
        "vol_scalar":     float(latest["VOL_SCALAR"]),
        "dd_scalar":      float(latest["DD_SCALAR"]),
        "vix_reversal":   bool(latest["VIX_REVERSAL_BUY"]),
        "curve_bullish":  bool(latest["CURVE_BULLISH"]),
        "def_asset1":     def_asset1,
        "def_asset2":     def_asset2,
        "regime":         str(latest["SPY_REGIME"]),
        "vix_regime":     str(latest["VIX_REGIME"]),
        "prev_alloc":     prev["TQQQ_ALLOC"],
    }
