"""
pages/backtest.py — Real-data backtest with regime comparison
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.data import fetch_all, compute_signals
from utils.backtest import (
    run_backtest, REGIME_PRESETS, sortino, win_rate,
    avg_win_loss, underwater_periods
)

DEFAULT_BLEND = {"btal": 40, "tlt": 30, "gold": 15, "sqqq": 0, "cash": 15}


def render():
    st.markdown("# 📊 BACKTEST")
    st.markdown("---")

    # ── Sidebar controls ──────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### Backtest Settings")
        regime = st.radio(
            "Rate Regime",
            options=list(REGIME_PRESETS.keys()),
            format_func=lambda k: REGIME_PRESETS[k]["label"],
            index=0,
        )
        st.markdown("**Defensive Blend**")
        b_btal = st.slider("BTAL %",  0, 100, DEFAULT_BLEND["btal"], 5)
        b_tlt  = st.slider("TLT %",   0, 100, DEFAULT_BLEND["tlt"],  5)
        b_gold = st.slider("GLD %",   0, 100, DEFAULT_BLEND["gold"], 5)
        b_sqqq = st.slider("SQQQ %",  0, 100, DEFAULT_BLEND["sqqq"], 5)
        b_cash = st.slider("Cash %",  0, 100, DEFAULT_BLEND["cash"], 5)
        total  = b_btal + b_tlt + b_gold + b_sqqq + b_cash
        color  = "green" if total == 100 else "red"
        st.markdown(f"**Total: :{color}[{total}%]**")
        start_yr = st.slider("Start Year", 2013, 2022, 2013)
        overlay  = st.checkbox("Overlay all 3 regimes", False)

    blend = {"btal": b_btal, "tlt": b_tlt, "gold": b_gold,
             "sqqq": b_sqqq, "cash": b_cash}

    if total != 100:
        st.warning(f"Defensive blend must sum to 100% (currently {total}%)")
        return

    # ── Fetch & compute ───────────────────────────────────────────────────
    with st.spinner("Loading data…"):
        try:
            df_raw = fetch_all()
            df     = compute_signals(df_raw)
        except Exception as e:
            st.error(f"Data error: {e}")
            return

    cfg      = REGIME_PRESETS[regime]
    start_dt = f"{start_yr}-01-01"
    result   = run_backtest(df, blend, regime=regime, start_date=start_dt)
    stats    = result["stats"]
    curve    = result["curve_df"]

    # ── Warning banner ───────────────────────────────────────────────────
    st.info(f"⚠ {cfg['dd_note']}")

    # ── Key stats ─────────────────────────────────────────────────────────
    col_labels = ["SPY B&H", "TQQQ B&H", "Strategy"]
    row1 = st.columns(3)
    for i, (key, label) in enumerate(zip(["spy","tqqq","strat"], col_labels)):
        s = stats[key]
        cagr_pct = s["cagr"] * 100
        mdd_pct  = s["maxdd"]
        row1[i].metric(
            label=f"**{label}** — Final Value",
            value=f"${s['final']:,.0f}",
            delta=f"CAGR {cagr_pct:.1f}%",
        )

    row2 = st.columns(6)
    metrics = [
        ("SPY Max DD",      f"{stats['spy']['maxdd']:.1f}%",   None),
        ("TQQQ Max DD",     f"{stats['tqqq']['maxdd']:.1f}%",  None),
        ("Strat Max DD",    f"{stats['strat']['maxdd']:.1f}%", None),
        ("Strat Sharpe",    f"{stats['strat']['sharpe']:.2f}", None),
        ("Strat Calmar",    f"{stats['strat']['calmar']:.2f}", None),
        ("Strat Sortino",   f"{sortino(df['TQQQ'].pct_change().fillna(0) * df['TQQQ_ALLOC']):.2f}", None),
    ]
    for col, (lbl, val, delta) in zip(row2, metrics):
        col.metric(lbl, val, delta)

    st.markdown("---")

    # ── Equity curve ──────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Equity Curve", "📉 Drawdown", "📅 Annual Returns", "🔀 Allocation"
    ])

    with tab1:
        if overlay:
            res_h = run_backtest(df, blend, "historical", start_dt)
            res_a = run_backtest(df, blend, "rate_adj",   start_dt)
            res_f = run_backtest(df, blend, "forward",    start_dt)
            fig = go.Figure()
            for r, lbl, col in [
                (res_h, "Historical",    "#4488ff"),
                (res_a, "Rate-Adjusted", "#ffcc44"),
                (res_f, "Forward",       "#ff6644"),
            ]:
                fig.add_trace(go.Scatter(
                    x=r["curve_df"].index, y=r["curve_df"]["Strategy"],
                    name=lbl, line=dict(color=col, width=2)))
        else:
            fig = go.Figure()
            colors = {"SPY": "rgba(68,136,255,0.33)", "TQQQ": "rgba(255,102,68,0.33)",
                      "Strategy": cfg["color"]}
            widths = {"SPY": 1.2, "TQQQ": 1.2, "Strategy": 2.5}
            for col_name in ["SPY", "TQQQ", "Strategy"]:
                fig.add_trace(go.Scatter(
                    x=curve.index, y=curve[col_name],
                    name=col_name,
                    line=dict(color=colors[col_name], width=widths[col_name])))

        fig.update_layout(
            height=400, template="plotly_dark",
            paper_bgcolor="#0f0f1c", plot_bgcolor="#0f0f1c",
            yaxis_type="log", yaxis_title="Portfolio Value ($, log)",
            font=dict(family="JetBrains Mono, monospace", size=10),
            legend=dict(orientation="h", y=-0.12),
            margin=dict(l=60, r=20, t=20, b=50),
            xaxis=dict(gridcolor="rgba(255,255,255,0.03)"), yaxis=dict(gridcolor="rgba(255,255,255,0.03)"))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig_dd = go.Figure()
        dd_cols = {
            "SPY_DD":   ("SPY B&H",   "#4488ff", 1),
            "TQQQ_DD":  ("TQQQ B&H",  "#ff6644", 1),
            "Strat_DD": ("Strategy",  cfg["color"], 2),
        }
        for col_name, (lbl, color, width) in dd_cols.items():
            fig_dd.add_trace(go.Scatter(
                x=curve.index, y=curve[col_name],
                name=lbl, fill="tozeroy",
                fillcolor=color.replace("#", "rgba(").rstrip(")") + ",0.08)",
                line=dict(color=color, width=width)))
        fig_dd.add_hline(y=-50, line_dash="dot", line_color="rgba(255,0,0,0.33)",
                         annotation_text="-50% threshold")
        fig_dd.update_layout(
            height=380, template="plotly_dark",
            paper_bgcolor="#0f0f1c", plot_bgcolor="#0f0f1c",
            yaxis_title="Drawdown from Peak (%)",
            font=dict(family="JetBrains Mono, monospace", size=10),
            legend=dict(orientation="h", y=-0.12),
            margin=dict(l=60, r=20, t=20, b=50),
            xaxis=dict(gridcolor="rgba(255,255,255,0.03)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.03)", ticksuffix="%"))
        st.plotly_chart(fig_dd, use_container_width=True)

        # Worst drawdown periods
        ud = underwater_periods(curve["Strat_DD"], threshold=-15)
        if not ud.empty:
            st.markdown("**Strategy drawdown periods >15%**")
            ud["max_dd"] = ud["max_dd"].apply(lambda x: f"{x:.1f}%")
            st.dataframe(ud.rename(columns={
                "start": "Start", "end": "End",
                "duration_days": "Days", "max_dd": "Max DD"
            }), use_container_width=True, hide_index=True)

    with tab3:
        annual = result["annual"]
        fig_ann = go.Figure()
        for col_name, color in [("SPY","#4488ff"),("TQQQ","#ff6644"),("Strategy",cfg["color"])]:
            if col_name in annual.columns:
                vals = annual[col_name]
                fig_ann.add_trace(go.Bar(
                    name=col_name, x=annual.index.astype(str), y=vals,
                    marker_color=[color if v >= 0 else "rgba(255,51,51,0.53)" for v in vals],
                    opacity=0.85))
        fig_ann.add_hline(y=0, line_color="rgba(255,255,255,0.20)")
        fig_ann.update_layout(
            height=380, barmode="group", template="plotly_dark",
            paper_bgcolor="#0f0f1c", plot_bgcolor="#0f0f1c",
            yaxis_title="Annual Return (%)", yaxis_ticksuffix="%",
            font=dict(family="JetBrains Mono, monospace", size=10),
            legend=dict(orientation="h", y=-0.12),
            margin=dict(l=60, r=20, t=20, b=50),
            xaxis=dict(gridcolor="rgba(255,255,255,0.03)"), yaxis=dict(gridcolor="rgba(255,255,255,0.03)"))
        st.plotly_chart(fig_ann, use_container_width=True)

        # Monthly heatmap for strategy
        st.markdown("**Strategy Monthly Returns (%)**")
        monthly = result["monthly"]
        if "Strategy" in monthly.columns:
            pivot = monthly["Strategy"].unstack(level=0)
            pivot.columns = [str(c) for c in pivot.columns]
            pivot.index   = [str(i) for i in pivot.index]
            import plotly.figure_factory as ff
            fig_heat = go.Figure(go.Heatmap(
                z=pivot.values.tolist(),
                x=pivot.columns.tolist(),
                y=pivot.index.tolist(),
                colorscale=[[0,"#ff3355"],[0.5,"#0f0f1c"],[1,"#00ff88"]],
                zmid=0,
                text=[[f"{v:.1f}%" if not np.isnan(v) else "" for v in row]
                      for row in pivot.values],
                texttemplate="%{text}",
                textfont=dict(size=8),
                showscale=False,
            ))
            fig_heat.update_layout(
                height=300, template="plotly_dark",
                paper_bgcolor="#0f0f1c", plot_bgcolor="#0f0f1c",
                font=dict(family="JetBrains Mono, monospace", size=9),
                margin=dict(l=60, r=20, t=10, b=40))
            st.plotly_chart(fig_heat, use_container_width=True)

    with tab4:
        fig_alloc = go.Figure()
        fig_alloc.add_trace(go.Scatter(
            x=curve.index, y=curve["Alloc"],
            fill="tozeroy", fillcolor="rgba(0,255,136,0.08)",
            line=dict(color="#00ff88", width=1.5), name="TQQQ %"))
        fig_alloc.update_layout(
            height=300, template="plotly_dark",
            paper_bgcolor="#0f0f1c", plot_bgcolor="#0f0f1c",
            yaxis=dict(range=[0,105], ticksuffix="%", gridcolor="rgba(255,255,255,0.03)"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.03)"),
            font=dict(family="JetBrains Mono, monospace", size=10),
            margin=dict(l=60, r=20, t=20, b=40), showlegend=False)
        st.plotly_chart(fig_alloc, use_container_width=True)

        # Time-in-market stats
        avg_alloc = curve["Alloc"].mean()
        pct_full  = (curve["Alloc"] >= 90).mean() * 100
        pct_cash  = (curve["Alloc"] <= 10).mean() * 100
        c1, c2, c3 = st.columns(3)
        c1.metric("Avg TQQQ Allocation", f"{avg_alloc:.1f}%")
        c2.metric("Time at Full (≥90%)",  f"{pct_full:.1f}%")
        c3.metric("Time Defensive (≤10%)", f"{pct_cash:.1f}%")
