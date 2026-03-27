"""
dashboard/pages/page_watchlist.py — Watchlist & Stock Analysis page
"""

import streamlit as st
import pandas as pd
from dashboard.components.charts import candlestick_chart, rsi_macd_chart
from dashboard.components.metrics import metric_card, fmt_inr
from dashboard.services.data_service import get_watchlist, get_ohlcv

SECTORS_ALL = ["All", "IT", "Banking", "Pharma", "Auto", "Energy",
               "FMCG", "NBFC", "Infra", "Telecom", "Power", "Consumer", "Conglomerate"]
SIGNALS_ALL = ["All", "BUY", "SELL", "HOLD"]


def render():
    st.markdown('<div class="page-title">👁 Watchlist & Screener</div>', unsafe_allow_html=True)

    # ── Filters ───────────────────────────────────────────────────────────────
    f1, f2, f3, f4 = st.columns([2, 2, 2, 1])
    with f1:
        sector_filter = st.selectbox("Sector", SECTORS_ALL, key="wl_sector")
    with f2:
        signal_filter = st.selectbox("Signal", SIGNALS_ALL, key="wl_signal")
    with f3:
        sort_by = st.selectbox("Sort by", ["Confidence", "Change %", "RSI", "Volume Ratio"], key="wl_sort")
    with f4:
        st.write("")
        refresh = st.button("🔄 Refresh", use_container_width=True)

    if refresh:
        st.cache_data.clear()

    # ── Data ──────────────────────────────────────────────────────────────────
    data = get_watchlist()

    if sector_filter != "All":
        data = [d for d in data if d["sector"] == sector_filter]
    if signal_filter != "All":
        data = [d for d in data if d["action"] == signal_filter]

    sort_map = {
        "Confidence":  lambda x: x["confidence"],
        "Change %":    lambda x: abs(x["chg_pct"]),
        "RSI":         lambda x: x["rsi"],
        "Volume Ratio": lambda x: x["vol_ratio"],
    }
    data = sorted(data, key=sort_map[sort_by], reverse=True)

    # ── Summary chips ─────────────────────────────────────────────────────────
    buys  = sum(1 for d in data if d["action"] == "BUY")
    sells = sum(1 for d in data if d["action"] == "SELL")
    holds = sum(1 for d in data if d["action"] == "HOLD")

    st.markdown(f"""
<div style="display:flex;gap:10px;margin:8px 0 12px">
  <span class="badge badge-buy">BUY {buys}</span>
  <span class="badge badge-sell">SELL {sells}</span>
  <span class="badge badge-hold">HOLD {holds}</span>
  <span style="font-size:12px;color:#9ca3af;align-self:center">{len(data)} stocks shown</span>
</div>
""", unsafe_allow_html=True)

    # ── Table ─────────────────────────────────────────────────────────────────
    rows = []
    for s in data:
        chg_str = f"{'+' if s['chg_pct'] >= 0 else ''}{s['chg_pct']:.2f}%"
        rsi_str = f"{s['rsi']:.0f}"
        rows.append({
            "Symbol":   s["symbol"],
            "LTP (₹)":  f"₹{s['ltp']:,.2f}",
            "Chg %":    chg_str,
            "Sector":   s["sector"],
            "RSI":      rsi_str,
            "MACD":     s["macd"],
            "Vol Ratio": f"{s['vol_ratio']:.2f}x",
            "Signal":   s["action"],
            "Conf %":   f"{s['confidence']*100:.0f}%",
            "Entry":    f"₹{s['entry']:,.2f}",
            "SL":       f"₹{s['stop_loss']:,.2f}",
            "Target":   f"₹{s['target']:,.2f}",
        })

    df = pd.DataFrame(rows)

    def style_signal(val):
        m = {"BUY": "background:#d1fae5;color:#065f46;font-weight:600",
             "SELL": "background:#fee2e2;color:#991b1b;font-weight:600",
             "HOLD": "background:#fef3c7;color:#92400e;font-weight:600"}
        return m.get(val, "")

    def style_chg(val):
        return "color:#059669" if val.startswith("+") else "color:#dc2626"

    def style_rsi(val):
        v = float(val)
        if v > 70: return "color:#dc2626;font-weight:600"
        if v < 30: return "color:#059669;font-weight:600"
        return ""

    def style_macd(val):
        if val == "Bullish": return "color:#059669"
        if val == "Bearish": return "color:#dc2626"
        return "color:#6b7280"

    styled = (
        df.style
        .map(style_signal, subset=["Signal"])
        .map(style_chg,    subset=["Chg %"])
        .map(style_rsi,    subset=["RSI"])
        .map(style_macd,   subset=["MACD"])
    )
    st.dataframe(styled, use_container_width=True, hide_index=True, height=380)

    # ── Stock detail drill-down ───────────────────────────────────────────────
    st.divider()
    st.markdown('<div class="section-title">📈 Stock Detail</div>', unsafe_allow_html=True)

    symbols = [d["symbol"] for d in data]
    col_sym, col_tf = st.columns([2, 2])
    with col_sym:
        selected_sym = st.selectbox("Select Symbol", symbols, key="detail_sym")
    with col_tf:
        days_choice = st.selectbox("Period", ["30 days", "60 days", "90 days", "180 days"], index=1, key="detail_days")

    days = int(days_choice.split()[0])

    if selected_sym:
        detail = next((d for d in data if d["symbol"] == selected_sym), None)
        if detail:
            d1, d2, d3, d4 = st.columns(4)
            with d1:
                metric_card("LTP", f"₹{detail['ltp']:,.2f}",
                            sub=f"{'+' if detail['chg_pct'] >= 0 else ''}{detail['chg_pct']:.2f}% today",
                            color="green" if detail["chg_pct"] >= 0 else "red")
            with d2:
                metric_card("RSI (14)", f"{detail['rsi']:.1f}",
                            sub="Overbought" if detail["rsi"] > 70 else "Oversold" if detail["rsi"] < 30 else "Neutral")
            with d3:
                metric_card("Signal", detail["action"],
                            sub=f"Confidence: {detail['confidence']*100:.0f}%",
                            color="green" if detail["action"] == "BUY" else "red" if detail["action"] == "SELL" else "")
            with d4:
                metric_card("Volume", f"{detail['vol_ratio']:.2f}×",
                            sub="vs 20-day avg volume")

        with st.spinner(f"Loading chart for {selected_sym}…"):
            df_ohlcv = get_ohlcv(selected_sym, days=days)

        if not df_ohlcv.empty:
            tab_candle, tab_indicators = st.tabs(["Candlestick", "Indicators"])
            with tab_candle:
                st.plotly_chart(
                    candlestick_chart(df_ohlcv, selected_sym),
                    use_container_width=True, config={"displayModeBar": False},
                )
            with tab_indicators:
                st.plotly_chart(
                    rsi_macd_chart(df_ohlcv),
                    use_container_width=True, config={"displayModeBar": False},
                )
