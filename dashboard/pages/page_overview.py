"""
dashboard/pages/page_overview.py — Overview / Dashboard page
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random

from dashboard.components.metrics import metric_card, fmt_inr, pnl_color, signal_badge
from dashboard.components.charts import (
    pnl_curve_chart, portfolio_donut, sector_bar_chart, win_loss_chart
)
from dashboard.services.data_service import (
    get_market_overview, get_portfolio, get_pnl_history,
    get_watchlist, get_recent_logs
)


def render():
    # ── Header ────────────────────────────────────────────────────────────────
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown('<div class="page-title">📊 Market Overview</div>', unsafe_allow_html=True)
        st.caption(f"Last updated: {datetime.now().strftime('%d %b %Y, %H:%M:%S IST')}")
    with col_h2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ── Load data ─────────────────────────────────────────────────────────────
    market    = get_market_overview()
    portfolio = get_portfolio()

    # Update session state
    st.session_state["today_pnl"]      = portfolio["today_pnl"]
    st.session_state["today_trades"]   = portfolio["today_trades"]
    st.session_state["open_positions"] = portfolio["positions"]

    # ── Index row ─────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Indices</div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5, c6 = st.columns(6)

    def idx_metric(col, label, data):
        val   = data["value"]
        chg   = data["chg_pct"]
        color = "green" if chg >= 0 else "red"
        sign  = "+" if chg >= 0 else ""
        with col:
            metric_card(
                label,
                f"{val:,.2f}",
                sub=f"{sign}{chg:.2f}%",
                color=color,
            )

    idx_metric(c1, "NIFTY 50",   market["nifty50"])
    idx_metric(c2, "SENSEX",     market["sensex"])
    idx_metric(c3, "BANK NIFTY", market["banknifty"])
    idx_metric(c4, "FINNIFTY",   market["finnifty"])
    idx_metric(c5, "INDIA VIX",  market["india_vix"])
    with c6:
        chg   = market["usdinr"]["chg_pct"]
        color = "red" if chg >= 0 else "green"   # INR up = bad for exports
        metric_card("USD/INR", f"{market['usdinr']['value']:.2f}", f"{chg:+.2f}%", color)

    st.divider()

    # ── Portfolio metrics ─────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Portfolio</div>', unsafe_allow_html=True)
    p1, p2, p3, p4 = st.columns(4)

    pnl = portfolio["today_pnl"]
    with p1:
        metric_card("Today P&L", fmt_inr(pnl),
                    sub=f"{'+' if pnl >= 0 else ''}{pnl/portfolio['capital']*100:.2f}% return",
                    color="green" if pnl >= 0 else "red")
    with p2:
        metric_card("Capital", fmt_inr(portfolio["capital"]),
                    sub=f"{portfolio['deployed_pct']}% deployed")
    with p3:
        metric_card("Open Positions", str(portfolio["open_count"]),
                    sub=f"{portfolio['today_trades']} trades today")
    with p4:
        fii = market["fii_net"]
        metric_card("FII Net Flow", fmt_inr(fii),
                    sub=f"DII: {fmt_inr(market['dii_net'])}",
                    color="green" if fii >= 0 else "red")

    st.divider()

    # ── Main content grid ─────────────────────────────────────────────────────
    col_left, col_right = st.columns([2, 1])

    with col_left:
        # P&L curve
        st.markdown('<div class="section-title">Today\'s P&L Curve</div>', unsafe_allow_html=True)
        history = get_pnl_history(days=1)
        times   = history["datetime"].dt.strftime("%H:%M").tolist()
        pnl_vals = history["pnl"].tolist()
        st.plotly_chart(pnl_curve_chart(pnl_vals, times), use_container_width=True, config={"displayModeBar": False})

        # Top signals table
        st.markdown('<div class="section-title">Top AI Signals</div>', unsafe_allow_html=True)
        watchlist = get_watchlist()
        actionable = [w for w in watchlist if w["action"] in ("BUY", "SELL")]
        actionable.sort(key=lambda x: x["confidence"], reverse=True)

        if actionable:
            rows = []
            for s in actionable[:8]:
                chg_str = f"+{s['chg_pct']:.2f}%" if s["chg_pct"] >= 0 else f"{s['chg_pct']:.2f}%"
                rows.append({
                    "Symbol":     s["symbol"],
                    "LTP (₹)":    f"₹{s['ltp']:,.2f}",
                    "Chg":        chg_str,
                    "Signal":     s["action"],
                    "Conf":       f"{s['confidence']*100:.0f}%",
                    "Entry ₹":    f"₹{s['entry']:,.2f}",
                    "SL ₹":       f"₹{s['stop_loss']:,.2f}",
                    "Target ₹":   f"₹{s['target']:,.2f}",
                })
            df_signals = pd.DataFrame(rows)

            def color_signal(val):
                if val == "BUY":  return "background-color:#d1fae5;color:#065f46;font-weight:600"
                if val == "SELL": return "background-color:#fee2e2;color:#991b1b;font-weight:600"
                return ""
            def color_chg(val):
                return "color:#059669" if val.startswith("+") else "color:#dc2626"

            styled = (
                df_signals.style
                .map(color_signal, subset=["Signal"])
                .map(color_chg,    subset=["Chg"])
            )
            st.dataframe(styled, use_container_width=True, hide_index=True, height=280)

    with col_right:
        # Portfolio donut
        st.markdown('<div class="section-title">Allocation</div>', unsafe_allow_html=True)
        alloc = {"Large Cap": 42, "Mid Cap": 28, "F&O": 18, "Cash": 12}
        st.plotly_chart(portfolio_donut(alloc), use_container_width=True, config={"displayModeBar": False})

        # Market breadth
        st.markdown('<div class="section-title">Market Breadth</div>', unsafe_allow_html=True)
        adv = market["advance"]
        dec = market["decline"]
        unch = 1800 - adv - dec
        st.markdown(f"""
<div style="font-size:12px;display:flex;gap:12px;margin-bottom:8px">
  <span style="color:#059669">▲ Advance: <b>{adv}</b></span>
  <span style="color:#dc2626">▼ Decline: <b>{dec}</b></span>
  <span style="color:#6b7280">— Unch: <b>{unch}</b></span>
</div>""", unsafe_allow_html=True)
        st.progress(adv / (adv + dec + unch))

        # Win/loss summary
        r = random.Random(42)
        wins   = r.randint(8, 18)
        losses = r.randint(4, 10)
        st.markdown('<div class="section-title" style="margin-top:12px">Win / Loss</div>', unsafe_allow_html=True)
        st.plotly_chart(win_loss_chart(wins, losses, portfolio["today_pnl"]),
                        use_container_width=True, config={"displayModeBar": False})

    st.divider()

    # ── Activity log ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Agent Activity Log</div>', unsafe_allow_html=True)
    logs = get_recent_logs(12)
    level_colors = {
        "buy":  "#059669", "sell": "#dc2626",
        "warn": "#d97706", "info": "#374151",
        "error": "#991b1b",
    }
    for log in logs:
        color = level_colors.get(log["level"], "#374151")
        st.markdown(
            f'<div style="font-size:12px;padding:3px 0;border-bottom:1px solid rgba(0,0,0,0.04)">'
            f'<span style="color:#9ca3af;font-variant-numeric:tabular-nums">{log["time"]}</span>'
            f'&nbsp;&nbsp;<span style="color:#6b7280;font-size:11px">[{log["agent"]}]</span>'
            f'&nbsp;<span style="color:{color}">{log["message"]}</span></div>',
            unsafe_allow_html=True,
        )
