"""
TQQQ Regime Strategy — Live Dashboard
Run with:  streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="TQQQ Regime Strategy",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;900&display=swap');
  html, body, [class*="css"] { font-family: 'JetBrains Mono', monospace !important; }
  .stMetric { background:#0f0f1c; border:1px solid #ffffff12; border-radius:8px; padding:12px 16px; }
  .stMetric label { font-size:10px !important; letter-spacing:0.15em; color:#ffffff55 !important; }
  .stMetric [data-testid="stMetricValue"] { font-size:20px !important; font-weight:900 !important; }
  h1, h2, h3 { font-family:'JetBrains Mono',monospace !important; letter-spacing:0.04em; }
  div[data-testid="stSidebarContent"] { background:#0a0a16; }
</style>
""", unsafe_allow_html=True)

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pages.live_signal        as live_signal
import pages.backtest           as backtest_page
import pages.enhanced_backtest  as enhanced_backtest
import pages.blend_builder      as blend_builder
import pages.guide              as guide_page

st.sidebar.markdown("## 📈 TQQQ STRATEGY")
st.sidebar.markdown("---")

PAGE_MAP = {
    "📡  Live Signal":        live_signal,
    "📊  Backtest":           backtest_page,
    "🚀  Enhanced Strategy":  enhanced_backtest,
    "🔧  Blend Builder":      blend_builder,
    "📋  Strategy Guide":     guide_page,
}

page_name = st.sidebar.radio(
    "Navigation", list(PAGE_MAP.keys()), label_visibility="collapsed"
)
st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="font-size:9px; color:#ffffff33; line-height:1.8">
Data: yfinance (1hr cache)<br>
Tickers: TQQQ SPY HYG TLT GLD BTAL SQQQ SGOV ^VIX<br><br>
⚠ Not financial advice.<br>
Past performance ≠ future results.
</div>
""", unsafe_allow_html=True)

PAGE_MAP[page_name].render()
