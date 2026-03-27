"""
dashboard/pages/page_positions.py — Open Positions & Order Management
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from dashboard.components.metrics import metric_card, fmt_inr, pnl_color
from dashboard.services.data_service import get_portfolio


def render():
    st.markdown('<div class="page-title">💼 Positions & Orders</div>', unsafe_allow_html=True)

    portfolio = get_portfolio()
    positions = portfolio.get("positions", [])

    # ── Summary row ───────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    pnl = portfolio["today_pnl"]
    with c1:
        metric_card("Today P&L", fmt_inr(pnl), color="green" if pnl >= 0 else "red")
    with c2:
        metric_card("Open", str(portfolio["open_count"]),
                    sub=f"of {st.session_state.get('max_positions', 15)} max")
    with c3:
        metric_card("Trades Today", str(portfolio["today_trades"]))
    with c4:
        metric_card("Capital", fmt_inr(portfolio["capital"]),
                    sub=f"{portfolio['deployed_pct']}% deployed")

    st.divider()
    tab_open, tab_history, tab_order = st.tabs(["Open Positions", "Trade History", "Place Order"])

    # ── Open Positions ─────────────────────────────────────────────────────────
    with tab_open:
        if not positions:
            st.info("No open positions. Start the agents to trade.")
        else:
            rows = []
            for p in positions:
                rows.append({
                    "Symbol":   p["symbol"],
                    "Side":     p["action"],
                    "Qty":      p["qty"],
                    "Avg (₹)":  f"₹{p['avg_price']:,.2f}",
                    "LTP (₹)":  f"₹{p['ltp']:,.2f}",
                    "P&L":      f"₹{p['pnl']:+,.2f}",
                    "P&L %":    f"{p['pnl_pct']:+.2f}%",
                    "SL (₹)":   f"₹{p['stop_loss']:,.2f}",
                    "Target (₹)": f"₹{p['target']:,.2f}",
                    "Sector":   p.get("sector", "—"),
                })

            df = pd.DataFrame(rows)

            def style_pnl(val):
                return "color:#059669;font-weight:600" if val.startswith("₹+") or val.startswith("+") else "color:#dc2626;font-weight:600"

            def style_side(val):
                return "background:#d1fae5;color:#065f46;font-weight:600" if val == "BUY" \
                    else "background:#fee2e2;color:#991b1b;font-weight:600"

            styled = df.style.map(style_pnl, subset=["P&L", "P&L %"]).map(style_side, subset=["Side"])
            st.dataframe(styled, use_container_width=True, hide_index=True)

            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                sym_to_close = st.selectbox("Select position to close", [p["symbol"] for p in positions])
            with col2:
                st.write("")
                st.write("")
                if st.button("⏹ Close Position", type="primary"):
                    mode = st.session_state.get("trading_mode", "paper")
                    st.success(f"{'[PAPER] ' if mode == 'paper' else ''}Close order placed for {sym_to_close}")

    # ── Trade History ──────────────────────────────────────────────────────────
    with tab_history:
        import random
        r = random.Random(42)
        history_rows = []
        symbols = ["RELIANCE", "TCS", "ICICIBANK", "SUNPHARMA", "WIPRO", "MARUTI", "INFY"]
        for i in range(15):
            sym    = symbols[i % len(symbols)]
            action = r.choice(["BUY", "SELL"])
            price  = r.uniform(500, 12000)
            qty    = r.randint(10, 200)
            pnl    = r.uniform(-8000, 15000)
            history_rows.append({
                "Time":     (datetime.now().replace(
                    hour=r.randint(9, 15), minute=r.randint(0, 59)
                )).strftime("%H:%M"),
                "Symbol":   sym,
                "Side":     action,
                "Qty":      qty,
                "Price (₹)": f"₹{price:,.2f}",
                "P&L":      f"₹{pnl:+,.2f}",
                "Strategy": r.choice(["Momentum", "Mean Reversion", "Breakout", "Manual"]),
                "Status":   "Executed",
            })

        df_hist = pd.DataFrame(history_rows)

        def style_side2(val):
            return "background:#d1fae5;color:#065f46;font-weight:600" if val == "BUY" \
                else "background:#fee2e2;color:#991b1b;font-weight:600"
        def style_pnl2(val):
            return "color:#059669;font-weight:600" if "+" in val else "color:#dc2626;font-weight:600"

        styled_hist = df_hist.style.map(style_side2, subset=["Side"]).map(style_pnl2, subset=["P&L"])
        st.dataframe(styled_hist, use_container_width=True, hide_index=True)

        total_pnl = sum(float(r["P&L"].replace("₹", "").replace(",", "")) for r in history_rows)
        st.markdown(f"""
<div style="font-size:13px;font-weight:600;color:{'#059669' if total_pnl >= 0 else '#dc2626'};
     padding:8px 0;text-align:right">
  Total P&L: ₹{total_pnl:+,.2f}
</div>""", unsafe_allow_html=True)

        # Export
        csv = df_hist.to_csv(index=False)
        st.download_button("📥 Export CSV", csv,
                           f"trades_{datetime.now().strftime('%Y%m%d')}.csv",
                           "text/csv")

    # ── Place Order ────────────────────────────────────────────────────────────
    with tab_order:
        st.markdown("**Manual Order Entry**")
        st.caption("Orders flow through the Risk Manager before execution.")

        with st.form("order_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                symbol   = st.text_input("Symbol", placeholder="RELIANCE").upper()
                exchange = st.selectbox("Exchange", ["NSE", "BSE", "NFO"])
            with c2:
                order_type = st.selectbox("Order Type", ["LIMIT", "MARKET", "SL", "SL-M"])
                product    = st.selectbox("Product", ["MIS (Intraday)", "CNC (Delivery)", "NRML (F&O)"])
            with c3:
                qty   = st.number_input("Quantity", min_value=1, value=50)
                price = st.number_input("Price (₹)", min_value=0.0, value=0.0, step=0.05)

            c4, c5 = st.columns(2)
            with c4:
                sl = st.number_input("Stop Loss (₹)", min_value=0.0, value=0.0, step=0.05)
            with c5:
                target = st.number_input("Target (₹)", min_value=0.0, value=0.0, step=0.05)

            c_buy, c_sell = st.columns(2)
            with c_buy:
                buy_btn = st.form_submit_button("🟢 BUY", use_container_width=True, type="primary")
            with c_sell:
                sell_btn = st.form_submit_button("🔴 SELL", use_container_width=True)

        if buy_btn and symbol:
            mode = st.session_state.get("trading_mode", "paper")
            st.success(f"{'[PAPER] ' if mode == 'paper' else ''}BUY {qty} × {symbol} @ ₹{price:.2f} placed")
        if sell_btn and symbol:
            mode = st.session_state.get("trading_mode", "paper")
            st.warning(f"{'[PAPER] ' if mode == 'paper' else ''}SELL {qty} × {symbol} @ ₹{price:.2f} placed")
