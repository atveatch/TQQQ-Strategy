"""
pages/blend_builder.py — Interactive defensive blend optimizer
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.data import fetch_all, compute_signals
from utils.backtest import run_backtest, REGIME_PRESETS

PRESETS = {
    "All Cash":          {"btal":0,  "tlt":0,  "gold":0,  "sqqq":0,  "cash":100},
    "BTAL Heavy":        {"btal":60, "tlt":20, "gold":10, "sqqq":0,  "cash":10},
    "Crisis Alpha":      {"btal":30, "tlt":35, "gold":25, "sqqq":0,  "cash":10},
    "TLT + Gold":        {"btal":0,  "tlt":50, "gold":30, "sqqq":0,  "cash":20},
    "BTAL + TLT":        {"btal":45, "tlt":40, "gold":5,  "sqqq":0,  "cash":10},
    "Aggressive Hedge":  {"btal":20, "tlt":20, "gold":20, "sqqq":20, "cash":20},
}

ASSET_COLORS = {
    "btal": "#44ffcc", "tlt": "#4488ff",
    "gold": "#ffcc44", "sqqq": "#ff6644", "cash": "#888888"
}


def render():
    st.markdown("# 🔧 BLEND BUILDER")
    st.markdown("---")
    st.markdown("Dial in your defensive allocation and compare results side-by-side against saved blends.")

    with st.spinner("Loading data…"):
        try:
            df_raw = fetch_all()
            df     = compute_signals(df_raw)
        except Exception as e:
            st.error(f"Data error: {e}")
            return

    # ── Preset selector ───────────────────────────────────────────────────
    preset_cols = st.columns(len(PRESETS))
    selected_preset = None
    for col, (name, weights) in zip(preset_cols, PRESETS.items()):
        if col.button(name, use_container_width=True):
            selected_preset = weights

    # ── Blend sliders ──────────────────────────────────────────────────────
    st.markdown("### Defensive Blend Weights")
    if selected_preset:
        defaults = selected_preset
    else:
        defaults = {"btal":40,"tlt":30,"gold":15,"sqqq":0,"cash":15}

    col_sliders, col_results = st.columns([1, 2])

    with col_sliders:
        b_btal = st.slider("BTAL — Anti-Beta",   0, 100,
                           st.session_state.get("b_btal", defaults["btal"]), 5, key="b_btal")
        b_tlt  = st.slider("TLT — Long Bonds",   0, 100,
                           st.session_state.get("b_tlt",  defaults["tlt"]),  5, key="b_tlt")
        b_gold = st.slider("GLD — Gold",          0, 100,
                           st.session_state.get("b_gold", defaults["gold"]), 5, key="b_gold")
        b_sqqq = st.slider("SQQQ — 3× Inverse",  0, 100,
                           st.session_state.get("b_sqqq", defaults["sqqq"]), 5, key="b_sqqq")
        b_cash = st.slider("Cash — T-Bills",      0, 100,
                           st.session_state.get("b_cash", defaults["cash"]), 5, key="b_cash")

        total = b_btal + b_tlt + b_gold + b_sqqq + b_cash
        if total != 100:
            st.error(f"Must sum to 100% — currently {total}%")
        else:
            st.success("✓ Valid blend")

        # Stacked bar
        fig_pie = go.Figure(go.Bar(
            x=[b_btal, b_tlt, b_gold, b_sqqq, b_cash],
            y=[""] * 5,
            orientation="h",
            marker_color=[ASSET_COLORS[k] for k in ["btal","tlt","gold","sqqq","cash"]],
            text=[f"{v}%" if v > 0 else "" for v in [b_btal,b_tlt,b_gold,b_sqqq,b_cash]],
            textposition="inside",
        ))
        fig_pie.update_layout(
            height=60, barmode="stack", showlegend=False,
            template="plotly_dark", paper_bgcolor="#0f0f1c",
            plot_bgcolor="#0f0f1c", margin=dict(l=0,r=0,t=5,b=5),
            xaxis=dict(visible=False), yaxis=dict(visible=False))
        st.plotly_chart(fig_pie, use_container_width=True)

        regime = st.selectbox("Rate Regime", list(REGIME_PRESETS.keys()),
                              format_func=lambda k: REGIME_PRESETS[k]["label"])

        save_blend = st.button("💾 Save & Compare", use_container_width=True,
                               disabled=(total != 100))

    blend = {"btal":b_btal,"tlt":b_tlt,"gold":b_gold,"sqqq":b_sqqq,"cash":b_cash}

    # ── Saved blends store ────────────────────────────────────────────────
    if "saved_blends" not in st.session_state:
        st.session_state.saved_blends = []

    SAVED_COLORS = ["#00ff88","#ff88cc","#88ccff","#ffaa44","#cc88ff"]

    if save_blend and total == 100:
        idx   = len(st.session_state.saved_blends)
        label = f"Blend {idx+1}"
        color = SAVED_COLORS[idx % len(SAVED_COLORS)]
        res   = run_backtest(df, blend, regime=regime)
        st.session_state.saved_blends.append({
            "label": label, "blend": dict(blend),
            "regime": regime, "result": res, "color": color
        })

    # Run current blend
    if total == 100:
        current_result = run_backtest(df, blend, regime=regime)
        c_stats = current_result["stats"]["strat"]

        with col_results:
            # Current stats
            st.markdown("### Current Blend")
            m1,m2,m3,m4 = st.columns(4)
            m1.metric("Final Value",  f"${c_stats['final']:,.0f}")
            m2.metric("CAGR",         f"{c_stats['cagr']*100:.1f}%")
            m3.metric("Max Drawdown", f"{c_stats['maxdd']:.1f}%")
            m4.metric("Sharpe",       f"{c_stats['sharpe']:.2f}")

            # Equity curve with saved blends
            fig_eq = go.Figure()
            curve = current_result["curve_df"]
            fig_eq.add_trace(go.Scatter(
                x=curve.index, y=curve["Strategy"],
                name="Current", line=dict(color="#00ff88", width=2.5)))
            fig_eq.add_trace(go.Scatter(
                x=curve.index, y=curve["SPY"],
                name="SPY", line=dict(color="#4488ff55", width=1.2)))
            fig_eq.add_trace(go.Scatter(
                x=curve.index, y=curve["TQQQ"],
                name="TQQQ B&H", line=dict(color="#ff664455", width=1.2)))
            for saved in st.session_state.saved_blends:
                sc = saved["result"]["curve_df"]
                fig_eq.add_trace(go.Scatter(
                    x=sc.index, y=sc["Strategy"],
                    name=saved["label"],
                    line=dict(color=saved["color"], width=1.5, dash="dash")))
            fig_eq.update_layout(
                height=340, template="plotly_dark",
                paper_bgcolor="#0f0f1c", plot_bgcolor="#0f0f1c",
                yaxis_type="log", yaxis_title="Value ($, log scale)",
                font=dict(family="JetBrains Mono, monospace", size=10),
                legend=dict(orientation="h", y=-0.15, font_size=9),
                margin=dict(l=60,r=20,t=20,b=50),
                xaxis=dict(gridcolor="#ffffff08"),
                yaxis=dict(gridcolor="#ffffff08"))
            st.plotly_chart(fig_eq, use_container_width=True)

    # ── Comparison table ──────────────────────────────────────────────────
    if st.session_state.saved_blends:
        st.markdown("### Saved Blend Comparison")
        rows = []
        for saved in st.session_state.saved_blends:
            s = saved["result"]["stats"]["strat"]
            rows.append({
                "Label":   saved["label"],
                "BTAL%":   saved["blend"]["btal"],
                "TLT%":    saved["blend"]["tlt"],
                "GLD%":    saved["blend"]["gold"],
                "SQQQ%":   saved["blend"]["sqqq"],
                "Cash%":   saved["blend"]["cash"],
                "Regime":  REGIME_PRESETS[saved["regime"]]["label"],
                "CAGR":    f"{s['cagr']*100:.1f}%",
                "Max DD":  f"{s['maxdd']:.1f}%",
                "Sharpe":  f"{s['sharpe']:.2f}",
                "Calmar":  f"{s['calmar']:.2f}",
                "Final $": f"${s['final']:,.0f}",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if st.button("🗑 Clear saved blends"):
            st.session_state.saved_blends = []
            st.rerun()
