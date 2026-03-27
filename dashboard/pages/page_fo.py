"""
dashboard/pages/page_fo.py — F&O Desk (Options Calculator & Strategies)
"""

import streamlit as st
import math
from scipy.stats import norm


def black_scholes(S, K, T, r, sigma, opt="CE"):
    if T <= 0 or sigma <= 0:
        return {"price": 0, "delta": 0, "gamma": 0, "theta": 0, "vega": 0}
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if opt == "CE":
        price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
    else:
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = -norm.cdf(-d1)
    gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
    vega  = S * norm.pdf(d1) * math.sqrt(T) / 100
    theta = -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T)) / 365
    return {"price": round(price, 2), "delta": round(delta, 4),
            "gamma": round(gamma, 6), "theta": round(theta, 4), "vega": round(vega, 4)}


def render():
    st.markdown('<div class="page-title">📐 F&O Desk</div>', unsafe_allow_html=True)
    st.caption("Options pricing, Greek analysis & strategy builder")

    tab_calc, tab_iron, tab_spread, tab_straddle = st.tabs([
        "Options Calculator", "Iron Condor", "Bull Call Spread", "Short Straddle"
    ])

    r_free = 0.065

    # ── Options Calculator ─────────────────────────────────────────────────────
    with tab_calc:
        st.markdown("**Black-Scholes Options Pricer**")
        c1, c2, c3 = st.columns(3)
        with c1:
            spot    = st.number_input("Spot Price (₹)", value=22800.0, step=50.0)
            strike  = st.number_input("Strike Price (₹)", value=23000.0, step=50.0)
        with c2:
            dte     = st.number_input("Days to Expiry", value=7, min_value=1, max_value=90)
            iv      = st.slider("Implied Volatility %", min_value=5, max_value=60, value=14)
        with c3:
            opt_type = st.radio("Option Type", ["CE (Call)", "PE (Put)"])

        otype = "CE" if "CE" in opt_type else "PE"
        T     = dte / 365
        sigma = iv / 100
        result = black_scholes(spot, strike, T, r_free, sigma, otype)

        st.divider()
        g1, g2, g3, g4, g5 = st.columns(5)
        with g1:
            st.metric("Premium (₹)", f"₹{result['price']:.2f}")
        with g2:
            st.metric("Delta", f"{result['delta']:.4f}",
                      help="Change in option price per ₹1 change in spot")
        with g3:
            st.metric("Gamma", f"{result['gamma']:.6f}",
                      help="Rate of change of delta")
        with g4:
            st.metric("Theta (₹/day)", f"₹{result['theta']:.2f}",
                      help="Time decay per calendar day")
        with g5:
            st.metric("Vega (₹/1% IV)", f"₹{result['vega']:.2f}",
                      help="Change in premium per 1% IV change")

        st.divider()
        st.markdown("**Greeks Sensitivity**")
        import numpy as np
        import plotly.graph_objects as go

        spots   = np.linspace(spot * 0.9, spot * 1.1, 50)
        premiums = [black_scholes(s, strike, T, r_free, sigma, otype)["price"] for s in spots]
        deltas   = [black_scholes(s, strike, T, r_free, sigma, otype)["delta"] for s in spots]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=spots, y=premiums, name="Premium", line=dict(color="#2563eb", width=2)))
        fig.add_trace(go.Scatter(x=spots, y=deltas, name="Delta", line=dict(color="#059669", width=2), yaxis="y2"))
        fig.add_vline(x=spot, line_dash="dot", line_color="#9ca3af")
        fig.update_layout(
            height=260,
            paper_bgcolor="white", plot_bgcolor="white",
            margin=dict(l=40, r=40, t=30, b=40),
            font=dict(family="DM Sans", size=11),
            legend=dict(font=dict(size=11)),
            yaxis=dict(title="Premium (₹)", gridcolor="rgba(0,0,0,0.05)"),
            yaxis2=dict(title="Delta", overlaying="y", side="right", gridcolor="rgba(0,0,0,0)"),
            xaxis=dict(title="Spot Price (₹)", gridcolor="rgba(0,0,0,0.05)"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Iron Condor ────────────────────────────────────────────────────────────
    with tab_iron:
        st.markdown("**Iron Condor Builder**")
        st.caption("Best when India VIX is high (>15) and market is range-bound.")

        c1, c2, c3 = st.columns(3)
        with c1:
            ic_spot = st.number_input("Index Spot (₹)", value=22800.0, step=50.0, key="ic_spot")
            ic_iv   = st.slider("IV %", 8, 40, 14, key="ic_iv")
        with c2:
            ic_dte     = st.number_input("DTE", value=7, min_value=1, max_value=30, key="ic_dte")
            ic_index   = st.selectbox("Index", ["NIFTY", "BANKNIFTY"], key="ic_index")
        with c3:
            lot_size   = 50 if ic_index == "NIFTY" else 15
            ic_body    = st.slider("Body Width %", 1, 5, 2, key="ic_body") / 100
            ic_wing    = st.slider("Wing Width %", 1, 8, 4, key="ic_wing") / 100

        S, T2, sig2 = ic_spot, ic_dte / 365, ic_iv / 100
        sc_k = round(S * (1 + ic_body) / 50) * 50
        bc_k = round(S * (1 + ic_body + ic_wing) / 50) * 50
        sp_k = round(S * (1 - ic_body) / 50) * 50
        bp_k = round(S * (1 - ic_body - ic_wing) / 50) * 50

        sc = black_scholes(S, sc_k, T2, r_free, sig2, "CE")
        bc = black_scholes(S, bc_k, T2, r_free, sig2, "CE")
        sp = black_scholes(S, sp_k, T2, r_free, sig2, "PE")
        bp = black_scholes(S, bp_k, T2, r_free, sig2, "PE")

        net_credit = (sc["price"] - bc["price"] + sp["price"] - bp["price"]) * lot_size
        max_loss   = (ic_wing * S - net_credit / lot_size) * lot_size
        be_up      = sc_k + net_credit / lot_size
        be_dn      = sp_k - net_credit / lot_size

        st.divider()
        l1, l2, l3, l4 = st.columns(4)
        l1.metric("Net Credit (₹)", f"₹{net_credit:,.0f}", help="Max profit if market stays in range")
        l2.metric("Max Loss (₹)", f"₹{max_loss:,.0f}", help="If market moves beyond wings")
        l3.metric("Breakeven Up", f"₹{be_up:,.0f}")
        l4.metric("Breakeven Down", f"₹{be_dn:,.0f}")

        net_theta = (-sc["theta"] + bc["theta"] - sp["theta"] + bp["theta"]) * lot_size
        st.info(f"📅 **Daily Theta Decay:** ₹{net_theta:.0f}/day  |  "
                f"**Profit Range:** ₹{bp_k:,.0f} – ₹{bc_k:,.0f}")

        st.markdown(f"""
| Leg | Action | Type | Strike | Premium |
|-----|--------|------|--------|---------|
| 1 | SELL | {ic_index} CE | ₹{sc_k:,.0f} | ₹{sc['price']:.2f} |
| 2 | BUY  | {ic_index} CE | ₹{bc_k:,.0f} | ₹{bc['price']:.2f} |
| 3 | SELL | {ic_index} PE | ₹{sp_k:,.0f} | ₹{sp['price']:.2f} |
| 4 | BUY  | {ic_index} PE | ₹{bp_k:,.0f} | ₹{bp['price']:.2f} |
""")

    # ── Bull Call Spread ───────────────────────────────────────────────────────
    with tab_spread:
        st.markdown("**Bull Call Spread Builder**")
        st.caption("Directional bullish play with limited risk. Good when bullish but IV is high.")

        c1, c2, c3 = st.columns(3)
        with c1:
            bcs_spot = st.number_input("Spot (₹)", value=22800.0, step=50.0, key="bcs_spot")
            bcs_iv   = st.slider("IV %", 8, 40, 14, key="bcs_iv")
        with c2:
            bcs_dte = st.number_input("DTE", value=14, min_value=1, max_value=60, key="bcs_dte")
            bcs_idx = st.selectbox("Index", ["NIFTY", "BANKNIFTY"], key="bcs_idx")
        with c3:
            bcs_otm = st.slider("OTM Width %", 1, 5, 2, key="bcs_otm") / 100

        S3, T3, sig3 = bcs_spot, bcs_dte / 365, bcs_iv / 100
        buy_k  = round(S3 / 50) * 50
        sell_k = round(S3 * (1 + bcs_otm) / 50) * 50
        ls3    = 50 if bcs_idx == "NIFTY" else 15

        buy_leg  = black_scholes(S3, buy_k,  T3, r_free, sig3, "CE")
        sell_leg = black_scholes(S3, sell_k, T3, r_free, sig3, "CE")

        net_debit  = (buy_leg["price"] - sell_leg["price"]) * ls3
        max_profit = (sell_k - buy_k) * ls3 - net_debit
        be3        = buy_k + (buy_leg["price"] - sell_leg["price"])

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Net Debit (₹)", f"₹{net_debit:,.0f}")
        m2.metric("Max Profit (₹)", f"₹{max_profit:,.0f}")
        m3.metric("Breakeven", f"₹{be3:,.0f}")
        m4.metric("RoI", f"{max_profit/net_debit*100:.0f}%" if net_debit else "—")

    # ── Short Straddle ──────────────────────────────────────────────────────────
    with tab_straddle:
        st.markdown("**Short Straddle**")
        st.warning("⚠️ High-risk strategy with unlimited loss potential. Use with strict stop-loss (2× premium).")

        c1, c2 = st.columns(2)
        with c1:
            ss_spot = st.number_input("Spot (₹)", value=22800.0, step=50.0, key="ss_spot")
            ss_iv   = st.slider("IV %", 8, 40, 15, key="ss_iv")
        with c2:
            ss_dte  = st.number_input("DTE", value=5, min_value=1, max_value=30, key="ss_dte")
            ss_idx  = st.selectbox("Index", ["NIFTY", "BANKNIFTY"], key="ss_idx")

        S4, T4, sig4 = ss_spot, ss_dte / 365, ss_iv / 100
        k4   = round(S4 / 50) * 50
        ls4  = 50 if ss_idx == "NIFTY" else 15
        call = black_scholes(S4, k4, T4, r_free, sig4, "CE")
        put  = black_scholes(S4, k4, T4, r_free, sig4, "PE")

        credit = (call["price"] + put["price"]) * ls4
        be_u   = k4 + call["price"] + put["price"]
        be_d   = k4 - call["price"] - put["price"]
        theta4 = (-call["theta"] - put["theta"]) * ls4

        n1, n2, n3, n4 = st.columns(4)
        n1.metric("Net Credit (₹)", f"₹{credit:,.0f}")
        n2.metric("Max Profit (₹)", f"₹{credit:,.0f}")
        n3.metric("BE Upper", f"₹{be_u:,.0f}")
        n4.metric("BE Lower", f"₹{be_d:,.0f}")
        st.info(f"📅 Daily Theta: ₹{theta4:.0f}/day  |  Stop-Loss at ₹{credit*2:,.0f} loss")
