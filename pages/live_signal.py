"""
pages/live_signal.py — Real-time regime dashboard
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.data import fetch_all, compute_signals, get_current_signals, compute_rvol


REGIME_COLORS = {
    "BULL":    "#00ff88",
    "NEUTRAL": "#ffcc44",
    "CAUTION": "#ff8844",
    "BEAR":    "#ff3355",
}

ALLOC_LABELS = {
    (0.9, 1.01): ("FULL TQQQ",   "#00ff88", "100% TQQQ — Maximum exposure"),
    (0.6, 0.9):  ("PARTIAL",     "#66ffbb", "60–80% TQQQ — Trend intact, reduce on weakness"),
    (0.3, 0.6):  ("MIXED",       "#ffcc44", "30–50% TQQQ — Cautious, watch HYG & VIX"),
    (0.1, 0.3):  ("DEFENSIVE",   "#ff8844", "10–25% TQQQ — Mostly defensive"),
    (-0.1, 0.1): ("CASH/HEDGE",  "#ff3355", "0% TQQQ — Defensive assets only"),
}


def alloc_info(alloc: float):
    for (lo, hi), info in ALLOC_LABELS.items():
        if lo <= alloc < hi:
            return info
    return ("UNKNOWN", "#888888", "")


def render():
    st.markdown("# 📡 LIVE SIGNAL")
    st.markdown("---")

    # ── Fetch & compute ──────────────────────────────────────────────────────
    with st.spinner("Fetching market data…"):
        try:
            df_raw  = fetch_all()
            df      = compute_signals(df_raw)
            signals = get_current_signals(df)
            rvol    = compute_rvol("SPY")
        except Exception as e:
            st.error(f"Data fetch error: {e}")
            st.info("Check your internet connection. yfinance may be rate-limited — try again in 60s.")
            return

    sig = signals
    alloc_label, alloc_color, alloc_desc = alloc_info(sig["tqqq_alloc"])
    regime_color = REGIME_COLORS.get(sig["regime"], "#888888")

    # ── TOP SIGNAL BOX ───────────────────────────────────────────────────────
    col_sig, col_score, col_alloc = st.columns([2, 1, 2])

    with col_sig:
        st.markdown(f"""
        <div style="background:{regime_color}11; border:2px solid {regime_color}55;
             border-radius:10px; padding:20px 24px; text-align:center;">
          <div style="font-size:11px; color:#ffffff55; letter-spacing:0.2em; margin-bottom:8px">
            MARKET REGIME · {sig['date']}
          </div>
          <div style="font-size:38px; font-weight:900; color:{regime_color}; letter-spacing:0.08em">
            {sig['regime']}
          </div>
          <div style="font-size:11px; color:{regime_color}; margin-top:6px; opacity:0.8">
            SPY {sig['spy_band_pct']:+.2f}% vs SMA200
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col_score:
        score = sig["composite"]
        score_color = "#00ff88" if score >= 65 else "#ffcc44" if score >= 42 else "#ff3355"
        st.markdown(f"""
        <div style="background:#0f0f1c; border:1px solid {score_color}33;
             border-radius:10px; padding:20px 16px; text-align:center; height:100%">
          <div style="font-size:10px; color:#ffffff44; letter-spacing:0.18em; margin-bottom:8px">
            COMPOSITE
          </div>
          <div style="font-size:44px; font-weight:900; color:{score_color}">{score:.0f}</div>
          <div style="font-size:9px; color:#ffffff33; margin-top:4px">/ 100</div>
        </div>
        """, unsafe_allow_html=True)

    with col_alloc:
        prev_change = sig["tqqq_alloc"] - sig["prev_alloc"]
        arrow = "▲" if prev_change > 0.05 else "▼" if prev_change < -0.05 else "◆"
        st.markdown(f"""
        <div style="background:{alloc_color}11; border:2px solid {alloc_color}55;
             border-radius:10px; padding:20px 24px; text-align:center;">
          <div style="font-size:10px; color:#ffffff55; letter-spacing:0.18em; margin-bottom:8px">
            TQQQ ALLOCATION SIGNAL
          </div>
          <div style="font-size:34px; font-weight:900; color:{alloc_color}">
            {sig['tqqq_alloc']*100:.0f}% {arrow}
          </div>
          <div style="font-size:10px; color:{alloc_color}; margin-top:6px; opacity:0.8">
            {alloc_label} — {alloc_desc}
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── INDICATOR GRID ───────────────────────────────────────────────────────
    st.markdown("##### INDICATOR BREAKDOWN")

    c1, c2, c3, c4, c5 = st.columns(5)

    def ind_card(col, label, value, sub, ok: bool | None = None, score=None):
        color = "#00ff88" if ok is True else "#ff3355" if ok is False else "#ffcc44"
        if score is not None:
            s_color = "#00ff88" if score >= 65 else "#ffcc44" if score >= 42 else "#ff3355"
        else:
            s_color = color
        col.markdown(f"""
        <div style="background:#0f0f1c; border:1px solid {color}22; border-radius:8px;
             padding:12px; text-align:center; margin-bottom:8px">
          <div style="font-size:9px; color:#ffffff44; letter-spacing:0.15em; margin-bottom:6px">{label}</div>
          <div style="font-size:20px; font-weight:900; color:{s_color or color}">{value}</div>
          <div style="font-size:9px; color:{color}; margin-top:4px">{sub}</div>
        </div>
        """, unsafe_allow_html=True)

    ind_card(c1, "SPY SMA200 BAND",
             f"{sig['spy_band_pct']:+.1f}%",
             f"${sig['spy']:.1f} / ${sig['spy_sma200']:.1f}",
             ok=sig["spy_band_pct"] > 0,
             score=sig["composite"])

    hyg_ok = sig["hyg_score"] == 2
    hyg_warn = sig["hyg_score"] == 1
    ind_card(c2, "HYG CREDIT",
             ["DANGER","WARNING","HEALTHY"][sig["hyg_score"]],
             f"${sig['hyg']:.1f} / SMA50 ${sig['hyg_sma50']:.1f}",
             ok=hyg_ok if not hyg_warn else None)

    ind_card(c3, "VIX",
             f"{sig['vix']:.1f}",
             sig["vix_regime"],
             ok=sig["vix"] < 20,
             score=None)

    ind_card(c4, "RSI (14)",
             f"{sig['rsi']:.1f}",
             "Overbought" if sig["rsi"] > 70 else "Oversold" if sig["rsi"] < 30 else "Normal",
             ok=30 < sig["rsi"] < 70)

    ind_card(c5, "RVOL",
             f"{rvol:.2f}×",
             "Above avg" if rvol >= 1.0 else "Below avg",
             ok=rvol >= 1.0)

    # ── SPY SMA200 BAND CHART (90 days) ─────────────────────────────────────
    st.markdown("##### SPY vs SMA200 ±3% BAND — LAST 252 DAYS")

    recent = df.dropna(subset=["SPY_SMA200"]).tail(252)
    fig_band = go.Figure()
    fig_band.add_trace(go.Scatter(
        x=recent.index, y=recent["SPY_UPPER"],
        name="+3% Band", line=dict(color="#00ff8844", width=1, dash="dot"),
        fill=None))
    fig_band.add_trace(go.Scatter(
        x=recent.index, y=recent["SPY_LOWER"],
        name="−3% Band", line=dict(color="#ff335544", width=1, dash="dot"),
        fill="tonexty", fillcolor="rgba(255,255,255,0.02)"))
    fig_band.add_trace(go.Scatter(
        x=recent.index, y=recent["SPY_SMA200"],
        name="SMA200", line=dict(color="#ffcc44", width=1.5)))
    fig_band.add_trace(go.Scatter(
        x=recent.index, y=recent["SPY"],
        name="SPY", line=dict(color="#4488ff", width=2)))
    fig_band.update_layout(
        height=280, template="plotly_dark",
        paper_bgcolor="#0f0f1c", plot_bgcolor="#0f0f1c",
        font=dict(family="JetBrains Mono, monospace", size=10, color="#ffffff88"),
        legend=dict(orientation="h", y=-0.15, font_size=10),
        margin=dict(l=50, r=20, t=10, b=40),
        xaxis=dict(gridcolor="#ffffff08"), yaxis=dict(gridcolor="#ffffff08"))
    st.plotly_chart(fig_band, use_container_width=True)

    # ── HYG & TQQQ ALLOCATION ────────────────────────────────────────────────
    col_hyg, col_alloc_chart = st.columns(2)

    with col_hyg:
        st.markdown("##### HYG CREDIT HEALTH")
        hyg_data = df.dropna(subset=["HYG_SMA50", "HYG_SMA200"]).tail(252)
        fig_hyg = go.Figure()
        fig_hyg.add_trace(go.Scatter(x=hyg_data.index, y=hyg_data["HYG_SMA200"],
            name="SMA200", line=dict(color="#ff3355", width=1, dash="dot")))
        fig_hyg.add_trace(go.Scatter(x=hyg_data.index, y=hyg_data["HYG_SMA50"],
            name="SMA50", line=dict(color="#ffcc44", width=1, dash="dash")))
        fig_hyg.add_trace(go.Scatter(x=hyg_data.index, y=hyg_data["HYG"],
            name="HYG", line=dict(color="#44ffcc", width=2)))
        fig_hyg.update_layout(height=220, template="plotly_dark",
            paper_bgcolor="#0f0f1c", plot_bgcolor="#0f0f1c",
            font=dict(family="JetBrains Mono, monospace", size=9),
            legend=dict(orientation="h", y=-0.2, font_size=9),
            margin=dict(l=45, r=10, t=10, b=35),
            xaxis=dict(gridcolor="#ffffff06"), yaxis=dict(gridcolor="#ffffff06"))
        st.plotly_chart(fig_hyg, use_container_width=True)

    with col_alloc_chart:
        st.markdown("##### TQQQ ALLOCATION SIGNAL — LAST 252 DAYS")
        alloc_data = df.dropna(subset=["TQQQ_ALLOC"]).tail(252)
        fig_alloc = go.Figure()
        fig_alloc.add_trace(go.Scatter(
            x=alloc_data.index, y=alloc_data["TQQQ_ALLOC"] * 100,
            fill="tozeroy", fillcolor="rgba(0,255,136,0.1)",
            line=dict(color="#00ff88", width=2), name="TQQQ %"))
        fig_alloc.update_layout(height=220, template="plotly_dark",
            paper_bgcolor="#0f0f1c", plot_bgcolor="#0f0f1c",
            font=dict(family="JetBrains Mono, monospace", size=9),
            yaxis=dict(range=[0, 105], ticksuffix="%", gridcolor="#ffffff06"),
            xaxis=dict(gridcolor="#ffffff06"),
            margin=dict(l=45, r=10, t=10, b=35), showlegend=False)
        st.plotly_chart(fig_alloc, use_container_width=True)

    # ── CHECKLIST ────────────────────────────────────────────────────────────
    st.markdown("##### SIGNAL CHECKLIST")
    checks = [
        ("SPY > SMA200",               sig["spy"] > sig["spy_sma200"]),
        ("SPY above upper band (+3%)",  sig["spy"] > sig["spy_upper"]),
        ("HYG > SMA50",                sig["hyg"] > sig["hyg_sma50"]),
        ("HYG SMA50 > SMA200",         sig["hyg_sma50"] > sig["hyg_sma200"]),
        ("VIX < 20",                   sig["vix"] < 20),
        ("VIX < 25",                   sig["vix"] < 25),
        ("RSI between 40–70",          40 < sig["rsi"] < 70),
        ("RVOL ≥ 1.0",                 rvol >= 1.0),
        ("TLT in uptrend (>SMA50)",    sig["tlt_trend"] == 1),
        ("TQQQ not in >20% drawdown",  sig["tqqq_dd"] > -20),
    ]
    cols = st.columns(2)
    for i, (label, passed) in enumerate(checks):
        icon  = "✅" if passed else "❌"
        color = "#00ff88" if passed else "#ff3355"
        cols[i % 2].markdown(
            f'<span style="font-size:11px; color:{color};">{icon} {label}</span>',
            unsafe_allow_html=True)

    st.markdown(f"""
    <br>
    <div style="font-size:9px; color:#ffffff22; text-align:center; letter-spacing:0.08em">
    Data via yfinance · Refreshes every hour · Last update: {sig['date']} · NOT FINANCIAL ADVICE
    </div>
    """, unsafe_allow_html=True)
