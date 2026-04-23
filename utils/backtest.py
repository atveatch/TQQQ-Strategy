"""
utils/backtest.py — Daily backtest engine using real price data
"""

import pandas as pd
import numpy as np


REGIME_PRESETS = {
    "historical": {
        "label":       "Historical (actual data)",
        "color":       "#4488ff",
        "tqqq_boost":  0.0,
        "tlt_boost":   0.0,
        "cash_rate":   None,    # use SGOV actual
        "dd_note":     "Actual daily data — true peak-to-trough drawdowns.",
    },
    "rate_adj": {
        "label":       "Rate-Adjusted (strip Fed tailwind)",
        "color":       "#ffcc44",
        "tqqq_boost":  -0.00006,   # ~−1.5% annual / 252 days
        "tlt_boost":   -0.00008,
        "cash_rate":   None,
        "dd_note":     "Removes ~1.5%/yr Fed QE multiple expansion benefit from TQQQ.",
    },
    "forward": {
        "label":       "Forward Scenario (2025+)",
        "color":       "#ff6644",
        "tqqq_boost":  -0.0001,    # ~−2.5% annual
        "tlt_boost":   -0.00012,
        "cash_rate":   0.044 / 252,  # 4.4% annual floor
        "dd_note":     "Higher carry cost, 4.4% cash floor, muted multiple expansion.",
    },
}


def run_backtest(
    signals_df: pd.DataFrame,
    blend: dict,
    regime: str = "historical",
    start_date: str = None,
    end_date: str = None,
) -> dict:
    """
    Run daily backtest against real price data.

    blend: dict with keys btal/tlt/gold/sqqq/cash summing to 100
    regime: one of 'historical', 'rate_adj', 'forward'
    Returns dict with equity curves, stats, monthly returns.
    """
    cfg = REGIME_PRESETS[regime]
    w   = {k: v / 100.0 for k, v in blend.items()}

    df = signals_df.copy()
    if start_date:
        df = df[df.index >= start_date]
    if end_date:
        df = df[df.index <= end_date]

    df = df.dropna(subset=["SPY_SMA200", "TQQQ_ALLOC", "TQQQ", "SPY", "TLT", "GLD"])

    # Daily returns for each asset
    tqqq_ret  = df["TQQQ"].pct_change().fillna(0) + cfg["tqqq_boost"]
    spy_ret   = df["SPY"].pct_change().fillna(0)
    tlt_ret   = df["TLT"].pct_change().fillna(0) + cfg["tlt_boost"]
    gld_ret   = df["GLD"].pct_change().fillna(0)
    sqqq_ret  = df["SQQQ"].pct_change().fillna(0) if "SQQQ" in df.columns else -tqqq_ret
    btal_ret  = df["BTAL"].pct_change().fillna(0) if "BTAL" in df.columns else pd.Series(0.0, index=df.index)

    # Cash / T-bill rate
    if cfg["cash_rate"] is not None:
        cash_ret = pd.Series(cfg["cash_rate"], index=df.index)
    elif "SGOV" in df.columns:
        cash_ret = df["SGOV"].pct_change().fillna(0)
    else:
        cash_ret = pd.Series(0.0001, index=df.index)

    # Blend defensive return
    def_ret = (
        w["btal"] * btal_ret +
        w["tlt"]  * tlt_ret  +
        w["gold"] * gld_ret  +
        w["sqqq"] * sqqq_ret +
        w["cash"] * cash_ret
    )

    # Strategy daily return
    alloc       = df["TQQQ_ALLOC"]
    strat_ret   = alloc * tqqq_ret + (1 - alloc) * def_ret

    # Equity curves
    spy_curve   = (1 + spy_ret).cumprod() * 100
    tqqq_curve  = (1 + tqqq_ret).cumprod() * 100
    strat_curve = (1 + strat_ret).cumprod() * 100

    # Max drawdown (true daily peak-to-trough)
    def max_dd(curve):
        peak = curve.cummax()
        dd   = (curve - peak) / peak
        return dd.min() * 100  # negative number

    def rolling_dd(curve):
        peak = curve.cummax()
        return ((curve - peak) / peak * 100)

    spy_dd_series   = rolling_dd(spy_curve)
    tqqq_dd_series  = rolling_dd(tqqq_curve)
    strat_dd_series = rolling_dd(strat_curve)

    # Annualized stats
    n_years = len(df) / 252

    def cagr(curve):
        if curve.iloc[-1] <= 0 or n_years <= 0:
            return 0.0
        return (curve.iloc[-1] / 100) ** (1 / n_years) - 1

    def sharpe(rets, rf=0.04/252):
        excess = rets - rf
        return (excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0

    def calmar(c, mdd):
        return cagr(c) / abs(mdd / 100) if mdd != 0 else 0

    spy_mdd   = max_dd(spy_curve)
    tqqq_mdd  = max_dd(tqqq_curve)
    strat_mdd = max_dd(strat_curve)

    spy_cagr   = cagr(spy_curve)
    tqqq_cagr  = cagr(tqqq_curve)
    strat_cagr = cagr(strat_curve)

    # Monthly returns table
    monthly = pd.DataFrame({
        "SPY":      spy_ret,
        "TQQQ":     tqqq_ret,
        "Strategy": strat_ret,
        "Alloc":    alloc,
    })
    monthly_grp = monthly.resample("ME").apply(lambda x: (1 + x).prod() - 1) * 100
    monthly_grp.index = monthly_grp.index.to_period("M")

    # Annual returns
    annual = monthly.resample("YE").apply(lambda x: (1 + x).prod() - 1) * 100
    annual.index = annual.index.year

    # Equity curve DataFrame for plotting
    curve_df = pd.DataFrame({
        "SPY":      spy_curve,
        "TQQQ":     tqqq_curve,
        "Strategy": strat_curve,
        "SPY_DD":   spy_dd_series,
        "TQQQ_DD":  tqqq_dd_series,
        "Strat_DD": strat_dd_series,
        "Alloc":    alloc * 100,
    }, index=df.index)

    return {
        "curve_df":   curve_df,
        "monthly":    monthly_grp,
        "annual":     annual,
        "stats": {
            "spy": {
                "cagr":   spy_cagr,
                "maxdd":  spy_mdd,
                "sharpe": sharpe(spy_ret),
                "calmar": calmar(spy_curve, spy_mdd),
                "final":  spy_curve.iloc[-1],
            },
            "tqqq": {
                "cagr":   tqqq_cagr,
                "maxdd":  tqqq_mdd,
                "sharpe": sharpe(tqqq_ret),
                "calmar": calmar(tqqq_curve, tqqq_mdd),
                "final":  tqqq_curve.iloc[-1],
            },
            "strat": {
                "cagr":   strat_cagr,
                "maxdd":  strat_mdd,
                "sharpe": sharpe(strat_ret),
                "calmar": calmar(strat_curve, strat_mdd),
                "final":  strat_curve.iloc[-1],
            },
        },
        "regime_cfg": cfg,
    }


def sortino(returns: pd.Series, rf: float = 0.04/252) -> float:
    excess     = returns - rf
    downside   = excess[excess < 0].std() * np.sqrt(252)
    return (excess.mean() * 252) / downside if downside > 0 else 0


def win_rate(returns: pd.Series) -> float:
    return (returns > 0).sum() / len(returns) * 100


def avg_win_loss(returns: pd.Series) -> tuple:
    wins   = returns[returns > 0].mean() * 100
    losses = returns[returns < 0].mean() * 100
    return wins, losses


def underwater_periods(dd_series: pd.Series, threshold: float = -10) -> pd.DataFrame:
    """Find periods where drawdown exceeded threshold."""
    below     = dd_series < threshold
    periods   = []
    start     = None
    for date, val in below.items():
        if val and start is None:
            start = date
        elif not val and start is not None:
            periods.append({"start": start, "end": date,
                            "duration_days": (date - start).days,
                            "max_dd": dd_series[start:date].min()})
            start = None
    return pd.DataFrame(periods) if periods else pd.DataFrame()
