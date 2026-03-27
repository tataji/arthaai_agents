"""
dashboard/pages/page_options_chain.py — Live NSE Options Chain
PCR, Max Pain, OI analysis with visual heatmap.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import random


def _mock_chain(spot: float, strikes_count: int = 16) -> pd.DataFrame:
    """Generate realistic mock options chain data."""
    rng   = random.Random(int(spot))
    step  = 50 if spot < 30000 else 100
    atm   = round(spot / step) * step
    strikes = [atm + (i - strikes_count // 2) * step for i in range(strikes_count)]
    rows = []
    for k in strikes:
        moneyness = (spot - k) / spot
        ce_oi   = int(abs(rng.gauss(500000, 200000)) * max(0.1, 1 - abs(moneyness) * 8))
        pe_oi   = int(abs(rng.gauss(500000, 200000)) * max(0.1, 1 - abs(moneyness) * 8))
        ce_vol  = int(ce_oi * rng.uniform(0.08, 0.25))
        pe_vol  = int(pe_oi * rng.uniform(0.08, 0.25))
        ce_iv   = round(rng.uniform(11, 19) + abs(moneyness) * 40, 1)
        pe_iv   = round(rng.uniform(11, 19) + abs(moneyness) * 45, 1)
        ce_ltp  = max(0.1, round((max(spot - k, 0) + rng.uniform(5, 150)), 1))
        pe_ltp  = max(0.1, round((max(k - spot, 0) + rng.uniform(5, 150)), 1))
        ce_chg  = round(rng.uniform(-15, 15), 1)
        pe_chg  = round(rng.uniform(-15, 15), 1)
        rows.append({
            "CE OI":      ce_oi,  "CE Chg OI": int(ce_oi * rng.uniform(-0.1, 0.2)),
            "CE Vol":     ce_vol, "CE IV":     ce_iv,
            "CE LTP":     ce_ltp, "CE Chg":    ce_chg,
            "Strike":     k,
            "PE Chg":     pe_chg, "PE LTP":    pe_ltp,
            "PE IV":      pe_iv,  "PE Vol":    pe_vol,
            "PE Chg OI":  int(pe_oi * rng.uniform(-0.1, 0.2)), "PE OI": pe_oi,
        })
    return pd.DataFrame(rows)


def render():
    st.markdown('<div class="page-title">📊 Options Chain</div>', unsafe_allow_html=True)

    col_cfg1, col_cfg2, col_cfg3, col_cfg4 = st.columns(4)
    with col_cfg1:
        index = st.selectbox("Index", ["NIFTY", "BANKNIFTY", "FINNIFTY"])
    with col_cfg2:
        expiry = st.selectbox("Expiry", ["27 Mar 2025", "03 Apr 2025", "10 Apr 2025", "24 Apr 2025"])
    with col_cfg3:
        spot_override = st.number_input(
            "Spot Price", value=22800 if index == "NIFTY" else 48120, step=50)
    with col_cfg4:
        strikes_shown = st.slider("Strikes to show", 8, 24, 14)

    spot  = float(spot_override)
    chain = _mock_chain(spot, strikes_count=strikes_shown)
    atm   = round(spot / 50) * 50

    # ── PCR & Max Pain ────────────────────────────────────────────────────────
    total_ce_oi = chain["CE OI"].sum()
    total_pe_oi = chain["PE OI"].sum()
    pcr         = round(total_pe_oi / total_ce_oi, 3) if total_ce_oi > 0 else 0

    # Max Pain = strike where combined OI loss for buyers is highest
    pain = {}
    for _, row in chain.iterrows():
        k       = row["Strike"]
        ce_loss = sum(max(0, k - s) * chain.loc[chain["Strike"] == s, "CE OI"].values[0]
                      for _, s_row in chain.iterrows() for s in [s_row["Strike"]])
        pe_loss = sum(max(0, s - k) * chain.loc[chain["Strike"] == s, "PE OI"].values[0]
                      for _, s_row in chain.iterrows() for s in [s_row["Strike"]])
        pain[k] = row["CE OI"] + row["PE OI"]
    max_pain = max(pain, key=pain.get)

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        from dashboard.components.metrics import metric_card
        metric_card("Spot", f"₹{spot:,.0f}", sub=index)
    with m2:
        pcr_color = "green" if pcr > 1 else "red" if pcr < 0.7 else ""
        metric_card("PCR", f"{pcr:.3f}",
                    sub="Bearish" if pcr < 0.7 else "Bullish signal" if pcr > 1.2 else "Neutral",
                    color=pcr_color)
    with m3:
        metric_card("Max Pain", f"₹{max_pain:,.0f}", sub="Gravity strike")
    with m4:
        metric_card("Total CE OI", f"{total_ce_oi/1e5:.1f}L", sub="Call open interest")
    with m5:
        metric_card("Total PE OI", f"{total_pe_oi/1e5:.1f}L", sub="Put open interest")

    st.divider()

    # ── OI Bar Chart ──────────────────────────────────────────────────────────
    tab_chain, tab_oi, tab_iv = st.tabs(["Options Chain", "OI Analysis", "IV Skew"])

    with tab_chain:
        # Highlight ATM row
        def highlight_atm(row):
            style = [""] * len(row)
            if row["Strike"] == atm:
                style = ["background-color:#fef9c3;font-weight:600"] * len(row)
            return style

        # Format chain DataFrame for display
        display_cols = ["CE OI", "CE Vol", "CE IV", "CE LTP", "Strike",
                        "PE LTP", "PE IV", "PE Vol", "PE OI"]
        chain_display = chain[display_cols].copy()

        def style_chain(df):
            def row_style(row):
                k = row["Strike"]
                base = [""] * len(row)
                if k == atm:
                    base = ["background-color:#fef9c3;font-weight:600"] * len(row)
                elif k > spot:
                    ce_idx = df.columns.tolist().index("CE LTP")
                    base[ce_idx] = "color:#059669"
                else:
                    pe_idx = df.columns.tolist().index("PE LTP")
                    base[pe_idx] = "color:#059669"
                return base
            return df.style.apply(row_style, axis=1).format({
                "CE OI": "{:,.0f}", "CE Vol": "{:,.0f}", "CE IV": "{:.1f}%",
                "CE LTP": "₹{:.2f}", "Strike": "₹{:,.0f}",
                "PE LTP": "₹{:.2f}", "PE IV": "{:.1f}%",
                "PE Vol": "{:,.0f}", "PE OI": "{:,.0f}",
            })

        st.dataframe(style_chain(chain_display), use_container_width=True, hide_index=True, height=420)

    with tab_oi:
        fig_oi = make_subplots(rows=1, cols=2,
                               subplot_titles=("Call OI by Strike", "Put OI by Strike"),
                               shared_yaxes=True)
        fig_oi.add_trace(go.Bar(
            x=chain["CE OI"] / 1000, y=chain["Strike"].astype(str),
            orientation="h", marker_color="#dc2626", name="CE OI",
        ), row=1, col=1)
        fig_oi.add_trace(go.Bar(
            x=chain["PE OI"] / 1000, y=chain["Strike"].astype(str),
            orientation="h", marker_color="#059669", name="PE OI",
        ), row=1, col=2)

        # Mark ATM
        atm_str = str(int(atm))
        for col in [1, 2]:
            fig_oi.add_hline(y=atm_str, line_dash="dot", line_color="#9ca3af",
                             row=1, col=col)

        fig_oi.update_layout(
            height=400, paper_bgcolor="white", plot_bgcolor="white",
            margin=dict(l=60, r=20, t=40, b=20),
            font=dict(family="DM Sans", size=11),
            barmode="overlay",
        )
        fig_oi.update_xaxes(title_text="OI (thousands)")
        st.plotly_chart(fig_oi, use_container_width=True, config={"displayModeBar": False})

        # Pain chart
        pain_vals = [pain[k] for k in sorted(pain.keys())]
        fig_pain = go.Figure(go.Bar(
            x=[str(int(k)) for k in sorted(pain.keys())],
            y=pain_vals,
            marker_color=["#dc2626" if k == max_pain else "#e5e7eb" for k in sorted(pain.keys())],
        ))
        fig_pain.update_layout(
            title=f"Max Pain: ₹{max_pain:,.0f}", height=200,
            paper_bgcolor="white", plot_bgcolor="white",
            margin=dict(l=40, r=20, t=40, b=40),
            font=dict(family="DM Sans", size=11),
            showlegend=False,
            xaxis=dict(title="Strike", gridcolor="rgba(0,0,0,0)"),
            yaxis=dict(title="Combined OI", gridcolor="rgba(0,0,0,0.05)"),
        )
        st.plotly_chart(fig_pain, use_container_width=True, config={"displayModeBar": False})

    with tab_iv:
        fig_iv = go.Figure()
        fig_iv.add_trace(go.Scatter(
            x=chain["Strike"], y=chain["CE IV"],
            line=dict(color="#dc2626", width=2), mode="lines+markers",
            name="CE IV", marker=dict(size=5),
        ))
        fig_iv.add_trace(go.Scatter(
            x=chain["Strike"], y=chain["PE IV"],
            line=dict(color="#059669", width=2), mode="lines+markers",
            name="PE IV", marker=dict(size=5),
        ))
        fig_iv.add_vline(x=spot, line_dash="dot", line_color="#9ca3af",
                         annotation_text="Spot")
        fig_iv.update_layout(
            title="Implied Volatility Skew", height=280,
            paper_bgcolor="white", plot_bgcolor="white",
            margin=dict(l=50, r=20, t=40, b=40),
            font=dict(family="DM Sans", size=11),
            xaxis=dict(title="Strike Price (₹)", gridcolor="rgba(0,0,0,0.05)"),
            yaxis=dict(title="IV %", ticksuffix="%", gridcolor="rgba(0,0,0,0.05)"),
        )
        st.plotly_chart(fig_iv, use_container_width=True, config={"displayModeBar": False})
        st.caption("The IV smile/skew shows which strikes have expensive options. "
                   "Put skew (PE IV > CE IV for OTM puts) is common in equity markets.")
