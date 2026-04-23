"""
utils/data.py — Market data fetching via yfinance with Streamlit caching
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import streamlit as st


TICKERS = {
    "TQQQ": "TQQQ",
    "SPY":  "SPY",
    "QQQ":  "QQQ",
    "HYG":  "HYG",
    "TLT":  "TLT",
    "IEF":  "IEF",
    "GLD":  "GLD",
    "BTAL": "BTAL",
    "GOVZ": "GOVZ",
    "EDV":  "EDV",
    "SGOV": "SGOV",
    "VIX":  "^VIX",
    "SQQQ": "SQQQ",
}

START_DATE = "2010-01-01"


@st.cache_data(ttl=3600)  # cache 1 hour
def fetch_prices(tickers: list[str] = None, start: str = START_DATE) -> pd.DataFrame:
    """Download adjusted close prices for all tickers."""
    if tickers is None:
        tickers = list(TICKERS.values())
    raw = yf.download(tickers, start=start, auto_adjust=True, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"]
    else:
        prices = raw[["Close"]].rename(columns={"Close": tickers[0]})
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    prices.ffill(inplace=True)
    return prices


@st.cache_data(ttl=3600)
def fetch_all() -> dict:
    """Fetch all tickers and return as a dict of Series."""
    df = fetch_prices(list(TICKERS.values()))
    rename = {v: k for k, v in TICKERS.items()}
    df.rename(columns=rename, inplace=True)
    # VIX column rename
    if "^VIX" in df.columns:
        df.rename(columns={"^VIX": "VIX"}, inplace=True)
    return df


def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all strategy indicators on daily data.
    Returns enriched DataFrame with signal columns.
    """
    out = df.copy()

    # ── SPY SMA200 & Band ────────────────────────────────────────────────────
    out["SPY_SMA200"]    = out["SPY"].rolling(200).mean()
    out["SPY_UPPER"]     = out["SPY_SMA200"] * 1.03
    out["SPY_LOWER"]     = out["SPY_SMA200"] * 0.97
    out["SPY_BAND_PCT"]  = (out["SPY"] - out["SPY_SMA200"]) / out["SPY_SMA200"] * 100

    # ── RVOL: 20-day avg volume via separate download ────────────────────────
    # (volume not in price df — approximate with price-range proxy)
    out["SPY_SMA50"]     = out["SPY"].rolling(50).mean()
    out["SPY_SMA20"]     = out["SPY"].rolling(20).mean()

    # ── HYG credit health ────────────────────────────────────────────────────
    out["HYG_SMA50"]     = out["HYG"].rolling(50).mean()
    out["HYG_SMA200"]    = out["HYG"].rolling(200).mean()
    out["HYG_VS_SMA50"]  = out["HYG"] > out["HYG_SMA50"]
    out["HYG_SMA50_VS_200"] = out["HYG_SMA50"] > out["HYG_SMA200"]

    # ── TLT trend ────────────────────────────────────────────────────────────
    out["TLT_SMA50"]     = out["TLT"].rolling(50).mean()
    out["TLT_SMA200"]    = out["TLT"].rolling(200).mean()
    out["TLT_TREND"]     = (out["TLT"] > out["TLT_SMA50"]).astype(int)

    # ── RSI (14) on SPY ──────────────────────────────────────────────────────
    delta = out["SPY"].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    out["RSI14"] = 100 - (100 / (1 + rs))

    # ── TQQQ-specific drawdown from rolling peak ─────────────────────────────
    out["TQQQ_PEAK"]     = out["TQQQ"].cummax()
    out["TQQQ_DD_PCT"]   = (out["TQQQ"] - out["TQQQ_PEAK"]) / out["TQQQ_PEAK"] * 100

    # ── Daily returns ────────────────────────────────────────────────────────
    for ticker in ["TQQQ", "SPY", "QQQ", "TLT", "IEF", "GLD", "HYG", "GOVZ", "EDV", "BTAL"]:
        if ticker in out.columns:
            out[f"{ticker}_RET"] = out[ticker].pct_change()

    # ── Regime classification ────────────────────────────────────────────────
    out["SPY_REGIME"] = pd.cut(
        out["SPY_BAND_PCT"],
        bins=[-np.inf, -3, 0, 3, np.inf],
        labels=["BEAR", "CAUTION", "NEUTRAL", "BULL"]
    )

    # HYG health score: 2=healthy, 1=warning, 0=danger
    out["HYG_SCORE"] = (
        out["HYG_VS_SMA50"].astype(int) +
        out["HYG_SMA50_VS_200"].astype(int)
    )

    # VIX regime
    out["VIX_REGIME"] = pd.cut(
        out["VIX"],
        bins=[0, 15, 20, 25, 30, np.inf],
        labels=["CALM", "LOW", "ELEVATED", "HIGH", "EXTREME"]
    )

    # ── Composite signal score (0-100) ───────────────────────────────────────
    def spy_score(band_pct):
        if band_pct > 3:   return min(100, 80 + (band_pct - 3) * 5)
        elif band_pct > 0: return 60 + (band_pct / 3) * 20
        elif band_pct > -3:return 35 - ((band_pct + 3) / 3) * 25
        else:              return max(0, 10 + band_pct * 2)

    out["SCORE_SPY"]  = out["SPY_BAND_PCT"].apply(spy_score)
    out["SCORE_HYG"]  = out["HYG_SCORE"].map({2: 85, 1: 50, 0: 15})
    out["SCORE_VIX"]  = out["VIX"].apply(lambda v:
        90 if v < 15 else 75 if v < 20 else 55 if v < 25 else 30 if v < 30 else 10)
    out["SCORE_RSI"]  = out["RSI14"].apply(lambda r:
        60 if r > 70 else 85 if r > 55 else 70 if r > 45 else 40 if r > 30 else 20
        if not np.isnan(r) else 50)

    out["COMPOSITE"]  = (
        out["SCORE_SPY"] * 0.40 +
        out["SCORE_HYG"] * 0.25 +
        out["SCORE_VIX"] * 0.20 +
        out["SCORE_RSI"] * 0.15
    )

    # ── TQQQ allocation signal ────────────────────────────────────────────────
    def tqqq_alloc(row):
        hyg_bad  = row["HYG_SCORE"] == 0
        hyg_warn = row["HYG_SCORE"] == 1
        vix_bad  = row["VIX"] >= 28 if not np.isnan(row["VIX"]) else False
        vix_warn = 20 <= row["VIX"] < 28 if not np.isnan(row["VIX"]) else False
        comp     = row["COMPOSITE"]
        if hyg_bad or vix_bad:          return 0.0
        elif hyg_warn and vix_warn:     return 0.15
        elif hyg_warn or vix_warn:      return 0.35
        elif comp >= 70:                return 1.0
        elif comp >= 55:                return 0.75
        elif comp >= 42:                return 0.50
        else:                           return 0.25

    out["TQQQ_ALLOC"] = out.apply(tqqq_alloc, axis=1)
    out["DEF_ALLOC"]  = 1 - out["TQQQ_ALLOC"]

    return out


def get_current_signals(df: pd.DataFrame) -> dict:
    """Extract today's (latest) signal values."""
    latest = df.dropna(subset=["SPY_SMA200", "COMPOSITE"]).iloc[-1]
    prev   = df.dropna(subset=["SPY_SMA200", "COMPOSITE"]).iloc[-2]
    return {
        "date":         latest.name.strftime("%Y-%m-%d"),
        "spy":          latest["SPY"],
        "spy_sma200":   latest["SPY_SMA200"],
        "spy_upper":    latest["SPY_UPPER"],
        "spy_lower":    latest["SPY_LOWER"],
        "spy_band_pct": latest["SPY_BAND_PCT"],
        "hyg":          latest["HYG"],
        "hyg_sma50":    latest["HYG_SMA50"],
        "hyg_sma200":   latest["HYG_SMA200"],
        "hyg_score":    int(latest["HYG_SCORE"]),
        "vix":          latest["VIX"],
        "rsi":          latest["RSI14"],
        "tlt":          latest["TLT"],
        "tlt_trend":    int(latest["TLT_TREND"]),
        "composite":    latest["COMPOSITE"],
        "tqqq_alloc":   latest["TQQQ_ALLOC"],
        "tqqq":         latest["TQQQ"],
        "tqqq_dd":      latest["TQQQ_DD_PCT"],
        "regime":       str(latest["SPY_REGIME"]),
        "vix_regime":   str(latest["VIX_REGIME"]),
        "prev_alloc":   prev["TQQQ_ALLOC"],
    }


def compute_rvol(ticker: str = "SPY", window: int = 20) -> float:
    """Compute relative volume vs N-day average using intraday data."""
    try:
        data = yf.download(ticker, period="30d", interval="1d", progress=False, auto_adjust=True)
        if "Volume" in data.columns and len(data) >= window:
            avg_vol = data["Volume"].iloc[-window:-1].mean()
            today_vol = data["Volume"].iloc[-1]
            return round(today_vol / avg_vol, 2) if avg_vol > 0 else 1.0
    except Exception:
        pass
    return 1.0
