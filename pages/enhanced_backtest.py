"""
pages/enhanced_backtest.py
Enhanced strategy backtest — dual momentum, vol targeting, SMA50 filter,
QQQ RS, GOVZ/EDV/IEF defensive rotation, yield curve, VIX reversal.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.data import fetch_all, compute_signals
from utils.signals_enhanced import (
    compute_enhanced_signals, run_enhanced_backtest,
    DEFENSIVE_ASSETS, get_current_enhanced_signals
)
from utils.backtest import run_backtest, REGIME_PRESETS, underwater_periods

DEFAULT_BLEND = {"btal": 40, "tlt": 30, "gold": 15, "sqqq": 0, "cash": 15}

ASSET_COLORS = {
    "GOVZ": "#4488ff", "EDV": "#6699ff", "TLT": "#88aaff",
    "IEF":  "#aabbff", "GLD": "#ffcc44", "BTAL": "#44ffcc",
    "SGOV": "#888888", "SQQQ": "#ff6644",
}


def render():
    st.markdown("# 🚀 ENHANCED STRATEGY")
    st.markdown("---")

    with st.sidebar:
        st.markdown("### Enhancement Toggles")
        use_dm  = st.toggle("Dual Momentum Defense", value=True)
        use_vt  = st.toggle("Volatility Targeting",  value=True)
        use_sma = st.toggle("TQQQ SMA50 Cap",        value=True)
        use_qqq = st.toggle("QQQ vs SPY RS Filter",  value=True)
        show_base = st.toggle("Show Baseline Overlay", value=True)
        st.markdown("---")
        st.markdown("### Rate Regime")
        regime = st.radio("", list(REGIME_PRESETS.keys()),
                          format_func=lambda k: REGIME_PRESETS[k]["label"], index=0)
        start_yr = st.slider("Start Year", 2011, 2022, 2011)

    start_dt = f"{start_yr}-01-01"

    with st.spinner("Fetching data and computing enhanced signals…"):
        try:
            df_raw  = fetch_all()
            df_enh  = compute_enhanced_signals(df_raw)
            df_base = compute_signals(df_raw)
        except Exception as e:
            st.error(f"Data error: {e}")
            return

    try:
        enh_result = run_enhanced_backtest(
            df_enh, DEFAULT_BLEND,
            use_dual_momentum=use_dm, use_vol_targeting=use_vt,
            use_sma50_filter=use_sma, use_qqq_rs=use_qqq,
            regime=regime, start_date=start_dt,
        )
        base_result = run_backtest(df_base, DEFAULT_BLEND, regime=regime,
                                   start_date=start_dt) if show_base else None
    except Exception as e:
        st.error(f"Backtest error: {e}")
        return

    es  = enh_result["stats"]["strat"]
    cfg = REGIME_PRESETS[regime]

    # ── Live signals ──────────────────────────────────────────────────────────
    try:
        live = get_current_enhanced_signals(df_enh)
    except Exception:
        live = {}

    if live:
        st.markdown("### 📡 CURRENT ENHANCED SIGNAL")
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        c1.metric("TQQQ Alloc",      f"{live['tqqq_alloc']*100:.0f}%",
                  f"{(live['tqqq_alloc']-live['prev_alloc'])*100:+.0f}% vs prev")
        c2.metric("Vol Scalar",      f"{live['vol_scalar']:.2f}×")
        c3.metric("DD Scalar",       f"{live['dd_scalar']:.2f}×")
        c4.metric("Defense #1",      live.get("def_asset1","—"))
        c5.metric("Defense #2",      live.get("def_asset2","—"))
        c6.metric("QQQ Leading",     "✅" if live.get("qqq_leading") else "❌")

        if live.get("vix_reversal"):
            st.success("⚡ VIX SPIKE REVERSAL BUY TRIGGER ACTIVE")
        if not live.get("tqqq_above_sma"):
            st.warning("⚠ TQQQ below SMA50 — allocation capped at 50%")
        st.markdown("---")

    # ── Stats ─────────────────────────────────────────────────────────────────
    st.markdown("### 📊 PERFORMANCE COMPARISON")
    stat_cols = st.columns(4)
    labels    = ["CAGR","MAX DD","SHARPE","CALMAR"]
    enh_vals  = [f"{es['cagr']*100:.1f}%", f"{es['maxdd']:.1f}%",
                 f"{es['sharpe']:.2f}", f"{es['calmar']:.2f}"]

    if show_base and base_result:
        bs = base_result["stats"]["strat"]
        base_vals    = [f"{bs['cagr']*100:.1f}%", f"{bs['maxdd']:.1f}%",
                        f"{bs['sharpe']:.2f}", f"{bs['calmar']:.2f}"]
        enh_floats   = [es['cagr']*100, abs(es['maxdd']),  es['sharpe'],  es['calmar']]
        base_floats  = [bs['cagr']*100, abs(bs['maxdd']),  bs['sharpe'],  bs['calmar']]
        higher_better= [True, False, True, True]
        for col, lbl, ev, bv, ef, bf, hb in zip(
                stat_cols, labels, enh_vals, base_vals,
                enh_floats, base_floats, higher_better):
            improved = (ef > bf) if hb else (ef < bf)
            col.metric(f"Enhanced — {lbl}", ev,
                       delta=f"{'▲' if improved else '▼'} baseline {bv}",
                       delta_color="normal" if improved else "inverse")
    else:
        for col, lbl, ev in zip(stat_cols, labels, enh_vals):
            col.metric(f"Enhanced — {lbl}", ev)

    fv = st.columns(3)
    fv[0].metric("SPY B&H",        f"${enh_result['stats']['spy']['final']:,.0f}")
    fv[1].metric("TQQQ B&H",       f"${enh_result['stats']['tqqq']['final']:,.0f}")
    fv[2].metric("Enhanced Final", f"${es['final']:,.0f}")
    st.markdown("---")

    # ── Charts ────────────────────────────────────────────────────────────────
    curve = enh_result["curve_df"]
    base_curve = base_result["curve_df"] if (show_base and base_result) else None

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Equity","📉 Drawdown","📅 Annual","🔄 Defense Rotation","⚙ Alloc Detail"
    ])

    def base_layout(fig, h=400, log=True):
        fig.update_layout(
            height=h, template="plotly_dark",
            paper_bgcolor="#0f0f1c", plot_bgcolor="#0f0f1c",
            yaxis_type="log" if log else "linear",
            font=dict(family="JetBrains Mono, monospace", size=10),
            legend=dict(orientation="h", y=-0.14),
            margin=dict(l=60,r=20,t=20,b=55),
            xaxis=dict(gridcolor="#ffffff08"),
            yaxis=dict(gridcolor="#ffffff08"))

    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=curve.index, y=curve["SPY"],
            name="SPY B&H",  line=dict(color="#4488ff44", width=1.2)))
        fig.add_trace(go.Scatter(x=curve.index, y=curve["TQQQ"],
            name="TQQQ B&H", line=dict(color="#ff664444", width=1.2)))
        if base_curve is not None:
            fig.add_trace(go.Scatter(x=base_curve.index, y=base_curve["Strategy"],
                name="Baseline", line=dict(color="#ffffff55", width=1.5, dash="dash")))
        fig.add_trace(go.Scatter(x=curve.index, y=curve["Strategy"],
            name="Enhanced",   line=dict(color="#00ff88",  width=2.5)))
        base_layout(fig, h=400, log=True)
        fig.update_yaxes(title="Portfolio Value ($, log)")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig_dd = go.Figure()
        fig_dd.add_trace(go.Scatter(x=curve.index, y=curve["TQQQ_DD"],
            name="TQQQ B&H", fill="tozeroy", fillcolor="#ff664412",
            line=dict(color="#ff664488", width=1)))
        fig_dd.add_trace(go.Scatter(x=curve.index, y=curve["SPY_DD"],
            name="SPY B&H",  fill="tozeroy", fillcolor="#4488ff12",
            line=dict(color="#4488ff88", width=1)))
        if base_curve is not None:
            fig_dd.add_trace(go.Scatter(x=base_curve.index, y=base_curve["Strat_DD"],
                name="Baseline", fill="tozeroy", fillcolor="#ffffff08",
                line=dict(color="#ffffff55", width=1.5, dash="dash")))
        fig_dd.add_trace(go.Scatter(x=curve.index, y=curve["Strat_DD"],
            name="Enhanced", fill="tozeroy", fillcolor="#00ff8818",
            line=dict(color="#00ff88", width=2)))
        fig_dd.add_hline(y=-50, line_dash="dot", line_color="#ff000055",
                         annotation_text="-50%")
        base_layout(fig_dd, h=380, log=False)
        fig_dd.update_yaxes(title="Drawdown (%)", ticksuffix="%")
        st.plotly_chart(fig_dd, use_container_width=True)

        ud = underwater_periods(curve["Strat_DD"], threshold=-15)
        if not ud.empty:
            st.markdown("**Drawdown periods >15%**")
            ud["max_dd"] = ud["max_dd"].apply(lambda x: f"{x:.1f}%")
            st.dataframe(ud.rename(columns={"start":"Start","end":"End",
                "duration_days":"Days","max_dd":"Max DD"}),
                use_container_width=True, hide_index=True)

    with tab3:
        annual = enh_result["annual"]
        fig_a = go.Figure()
        for col, color in [("SPY","#4488ff"),("TQQQ","#ff6644"),("Strategy","#00ff88")]:
            if col in annual.columns:
                v = annual[col]
                fig_a.add_trace(go.Bar(name=col, x=annual.index.astype(str), y=v,
                    marker_color=[color if x >= 0 else "#ff333377" for x in v], opacity=0.85))
        if show_base and base_result and "Strategy" in base_result["annual"].columns:
            ba = base_result["annual"]["Strategy"]
            fig_a.add_trace(go.Scatter(name="Baseline",
                x=ba.index.astype(str), y=ba,
                mode="markers+lines",
                line=dict(color="#ffffff55", dash="dot"), marker=dict(size=6)))
        fig_a.add_hline(y=0, line_color="#ffffff22")
        base_layout(fig_a, h=380, log=False)
        fig_a.update_layout(barmode="group")
        fig_a.update_yaxes(title="Annual Return (%)", ticksuffix="%")
        st.plotly_chart(fig_a, use_container_width=True)

    with tab4:
        md = enh_result.get("monthly_def")
        if use_dm and md is not None and len(md.dropna()) > 0:
            md = md.dropna()
            counts = md.value_counts().reset_index()
            counts.columns = ["Asset","Months"]
            counts["Color"] = counts["Asset"].map(ASSET_COLORS).fillna("#aaa")

            col_pie, col_tbl = st.columns([1,1])
            with col_pie:
                fig_p = go.Figure(go.Pie(
                    labels=counts["Asset"], values=counts["Months"],
                    marker_colors=counts["Color"].tolist(),
                    hole=0.4, textinfo="label+percent"))
                fig_p.update_layout(
                    height=300, template="plotly_dark",
                    paper_bgcolor="#0f0f1c",
                    font=dict(family="JetBrains Mono, monospace", size=11),
                    showlegend=False, margin=dict(l=20,r=20,t=20,b=20))
                st.plotly_chart(fig_p, use_container_width=True)

            with col_tbl:
                st.markdown("**Months per defensive asset**")
                st.dataframe(counts[["Asset","Months"]],
                             use_container_width=True, hide_index=True)
                st.markdown("**How dual momentum works:**")
                st.markdown("""
At the start of each month, every defensive asset is scored by its
3-month absolute return. Assets with **negative absolute momentum**
are excluded — if all are negative, the model goes to SGOV (T-bills).
The top 2 remaining assets split the defensive bucket 60/40.
""")

            # Timeline
            fig_tl = go.Figure(go.Scatter(
                x=md.index.to_timestamp(), y=md.values,
                mode="markers",
                marker=dict(color=[ASSET_COLORS.get(a,"#888") for a in md.values],
                            size=10, symbol="square"),
                text=md.values, hovertemplate="%{text}<br>%{x}"))
            fig_tl.update_layout(
                height=180, template="plotly_dark",
                paper_bgcolor="#0f0f1c", plot_bgcolor="#0f0f1c",
                yaxis=dict(visible=False),
                xaxis=dict(gridcolor="#ffffff08"),
                font=dict(family="JetBrains Mono, monospace", size=9),
                margin=dict(l=10,r=10,t=30,b=30),
                title="Defense asset held each month (color = asset)")
            st.plotly_chart(fig_tl, use_container_width=True)
        else:
            st.info("Enable 'Dual Momentum Defense' toggle to see rotation history.")

    with tab5:
        # Allocation components breakdown
        alloc_data = df_enh.dropna(subset=["TQQQ_ALLOC"]).loc[curve.index[0]:].copy()

        fig_a2 = go.Figure()
        fig_a2.add_trace(go.Scatter(
            x=curve.index, y=curve["Alloc"],
            fill="tozeroy", fillcolor="rgba(0,255,136,0.08)",
            line=dict(color="#00ff88", width=2), name="Final TQQQ %"))

        if "VOL_SCALAR" in alloc_data.columns:
            fig_a2.add_trace(go.Scatter(
                x=alloc_data.index, y=alloc_data["VOL_SCALAR"]*100,
                line=dict(color="#ffcc44", width=1, dash="dot"), name="Vol Scalar ×100"))
        if "DD_SCALAR" in alloc_data.columns:
            fig_a2.add_trace(go.Scatter(
                x=alloc_data.index, y=alloc_data["DD_SCALAR"]*100,
                line=dict(color="#ff8844", width=1, dash="dot"), name="DD Scalar ×100"))

        base_layout(fig_a2, h=320, log=False)
        fig_a2.update_yaxes(title="Allocation / Scalar %", ticksuffix="%", range=[0,110])
        st.plotly_chart(fig_a2, use_container_width=True)

        a1, a2, a3 = st.columns(3)
        a1.metric("Avg TQQQ Alloc",    f"{curve['Alloc'].mean():.1f}%")
        a2.metric("Time at Full (≥90%)",f"{(curve['Alloc']>=90).mean()*100:.1f}%")
        a3.metric("Time Defensive (≤10%)",f"{(curve['Alloc']<=10).mean()*100:.1f}%")

        if "VOL_SCALAR" in alloc_data.columns:
            b1, b2 = st.columns(2)
            b1.metric("Avg Vol Scalar", f"{alloc_data['VOL_SCALAR'].mean():.2f}×")
            b2.metric("Times Vol Capped (<0.7×)",
                      f"{(alloc_data['VOL_SCALAR']<0.7).mean()*100:.1f}% of days")
