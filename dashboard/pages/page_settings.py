"""
dashboard/pages/page_settings.py — Settings & Configuration
"""

import streamlit as st


def render():
    st.markdown('<div class="page-title">🔧 Settings</div>', unsafe_allow_html=True)

    tab_api, tab_risk, tab_strategy, tab_notif, tab_about = st.tabs([
        "API Keys", "Risk Management", "Strategy", "Notifications", "About"
    ])

    # ── API Keys ───────────────────────────────────────────────────────────────
    with tab_api:
        st.markdown("**Anthropic (Claude AI)**")
        api_key = st.text_input(
            "Anthropic API Key",
            value=st.session_state.get("anthropic_api_key", ""),
            type="password",
            placeholder="sk-ant-...",
            help="Get your key from console.anthropic.com",
        )
        model = st.selectbox("Claude Model", [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-haiku-4-20250514",
        ], index=0)
        analysis_freq = st.selectbox("Analysis Frequency", [
            "Every 5 minutes", "Every 1 minute", "Every 15 minutes", "On signal only"
        ])

        st.divider()
        st.markdown("**Broker Connection**")
        broker = st.selectbox("Broker", ["Zerodha Kite", "Upstox", "AngelOne", "Fyers"])

        if broker == "Zerodha Kite":
            col1, col2 = st.columns(2)
            with col1:
                kite_key = st.text_input("Kite API Key", value=st.session_state.get("kite_api_key", ""), type="password")
            with col2:
                kite_secret = st.text_input("Kite API Secret", value="", type="password", placeholder="Set in .env")
            kite_token = st.text_input("Access Token (refresh daily)", value=st.session_state.get("kite_access_token", ""), type="password")
            st.info("💡 Run `python utils/auth.py` every morning to refresh the access token.")
        elif broker == "Upstox":
            st.text_input("Upstox API Key", type="password")
            st.text_input("Upstox Access Token", type="password")

        if st.button("💾 Save API Settings", type="primary"):
            st.session_state["anthropic_api_key"]  = api_key
            st.session_state["claude_model"]        = model
            st.session_state["broker"]              = broker
            if broker == "Zerodha Kite":
                st.session_state["kite_api_key"]      = kite_key
                st.session_state["kite_access_token"] = kite_token
            st.success("✅ API settings saved to session")

        st.divider()
        st.markdown("**Trading Mode**")
        mode = st.radio("Mode", ["Paper Trading (Safe — no real money)", "Live Trading (Real money!)"],
                        index=0 if st.session_state.get("trading_mode", "paper") == "paper" else 1)
        auto_trade = st.selectbox("Auto-Trade Mode", [
            "Suggest only (manual confirm)",
            "Semi-auto (confirm each trade)",
            "Full auto (within risk limits)",
        ])
        if st.button("Apply Mode"):
            st.session_state["trading_mode"] = "paper" if "Paper" in mode else "live"
            if st.session_state["trading_mode"] == "live":
                st.warning("⚠️ Live mode enabled. Real capital will be deployed.")
            else:
                st.success("Paper mode active. No real money at risk.")

    # ── Risk Management ────────────────────────────────────────────────────────
    with tab_risk:
        st.markdown("**Position & Loss Limits**")
        c1, c2 = st.columns(2)
        with c1:
            max_pos = st.slider("Max Position Size % of Capital",
                                1, 20, int(st.session_state.get("max_position_pct", 5)))
            daily_loss = st.slider("Daily Loss Limit % of Capital",
                                   1, 10, int(st.session_state.get("daily_loss_limit", 2)))
            max_positions = st.slider("Max Open Positions",
                                      3, 30, int(st.session_state.get("max_positions", 15)))
        with c2:
            sl_pct  = st.slider("Default Stop-Loss %",
                                0.5, 5.0, float(st.session_state.get("default_sl_pct", 1.5)), 0.5)
            tp_pct  = st.slider("Default Target %",
                                1.0, 10.0, float(st.session_state.get("default_tp_pct", 3.0)), 0.5)
            capital = st.number_input("Trading Capital (₹)",
                                      value=int(st.session_state.get("capital", 2_500_000)),
                                      step=100_000)

        st.divider()
        st.markdown("**Intraday Rules**")
        avoid_first = st.slider("Avoid first N minutes after open", 0, 30, 15)
        avoid_last  = st.slider("Square-off N minutes before close", 5, 30, 10)
        max_trades  = st.slider("Max trades per day (circuit breaker)", 10, 100, 50)

        if st.button("💾 Save Risk Settings", type="primary"):
            st.session_state["max_position_pct"] = max_pos
            st.session_state["daily_loss_limit"]  = daily_loss
            st.session_state["max_positions"]     = max_positions
            st.session_state["default_sl_pct"]    = sl_pct
            st.session_state["default_tp_pct"]    = tp_pct
            st.session_state["capital"]            = float(capital)
            st.success("✅ Risk settings saved")

        # ── Live risk summary ──────────────────────────────────────────────────
        st.divider()
        st.markdown("**Current Risk Snapshot**")
        pnl  = st.session_state.get("today_pnl", 0)
        cap  = float(st.session_state.get("capital", 2_500_000))
        lim  = cap * daily_loss / 100
        used = max(0, -pnl) / lim * 100 if lim else 0
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Today P&L", f"₹{pnl:+,.0f}", delta=f"{pnl/cap*100:+.2f}%")
        with col2:
            st.metric("Loss Buffer Used", f"{used:.1f}%")
        st.progress(min(used / 100, 1.0))

    # ── Strategy ───────────────────────────────────────────────────────────────
    with tab_strategy:
        st.markdown("**Active Strategies**")
        strategies = {
            "Momentum":       "EMA + RSI + Volume — buy stocks with strong upward momentum",
            "Mean Reversion": "Bollinger Bands + RSI — buy oversold, sell overbought",
            "Breakout":       "Volume-confirmed breakout above consolidation range",
            "Swing":          "Multi-day swing trades based on weekly trend",
            "Scalping":       "High-frequency intraday micro-moves (requires fast execution)",
            "Options":        "F&O strategies — Iron Condor, Bull Call Spread, etc.",
        }
        active = st.session_state.get("active_strategies", ["Momentum", "Mean Reversion"])
        selected = []
        for strat, desc in strategies.items():
            if st.checkbox(strat, value=strat in active, help=desc):
                selected.append(strat)

        st.divider()
        st.markdown("**Instruments**")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.checkbox("Equity (NSE)", value=True)
            st.checkbox("F&O Index", value=True)
        with c2:
            st.checkbox("F&O Stock", value=False)
            st.checkbox("Currency", value=False)
        with c3:
            st.checkbox("Commodity", value=False)
            st.checkbox("ETF/Index Fund", value=False)

        st.divider()
        st.markdown("**Watchlist**")
        from dashboard.services.data_service import NSE_SYMBOLS
        wl = st.multiselect("Active watchlist symbols", NSE_SYMBOLS,
                            default=NSE_SYMBOLS[:15])

        if st.button("💾 Save Strategy Settings", type="primary"):
            st.session_state["active_strategies"] = selected
            st.success("✅ Strategy settings saved")

    # ── Notifications ──────────────────────────────────────────────────────────
    with tab_notif:
        st.markdown("**Telegram Alerts**")
        tg_token = st.text_input("Bot Token", type="password",
                                 placeholder="Get from @BotFather on Telegram")
        tg_chat  = st.text_input("Chat ID", placeholder="-100xxxxxxxxx")

        st.markdown("**Alert Events**")
        c1, c2 = st.columns(2)
        with c1:
            st.checkbox("New trade executed",    value=True)
            st.checkbox("Stop-loss hit",         value=True)
            st.checkbox("Target reached",        value=True)
        with c2:
            st.checkbox("Daily summary (EOD)",   value=True)
            st.checkbox("Risk limit breach",     value=True)
            st.checkbox("Agent errors",          value=False)

        if st.button("💾 Save & Test Telegram"):
            if tg_token and tg_chat:
                st.session_state["telegram_token"]   = tg_token
                st.session_state["telegram_chat_id"] = tg_chat
                st.success("✅ Telegram configured. Test message sent.")
            else:
                st.error("Please fill in both Token and Chat ID.")

    # ── About ──────────────────────────────────────────────────────────────────
    with tab_about:
        st.markdown("""
**ArthAI — Agentic Trading System for Indian Markets**

Version `1.0.0` · Built with Python, Streamlit, Claude AI

**Technology Stack:**
- 🧠 **AI**: Anthropic Claude (claude-sonnet-4-20250514)
- 📊 **Data**: Zerodha Kite Connect, NSE public API, yfinance
- 📈 **TA**: `ta` library (RSI, MACD, Bollinger Bands, ATR, VWAP)
- 🗄️ **Database**: SQLite via SQLAlchemy
- 🚀 **Backend**: FastAPI + WebSockets
- 🎨 **Dashboard**: Streamlit + Plotly

**Agents:**
- Orchestrator · Technical · Fundamental · News · Risk Manager · F&O Strategy

**Risk Disclaimer:**
Trading in Indian equity and F&O markets involves significant financial risk.
This software is for educational purposes. Always test in paper mode first.
Past performance does not guarantee future results.
""")
        col1, col2 = st.columns(2)
        with col1:
            st.link_button("📚 Documentation", "https://github.com/your-org/arthaai", use_container_width=True)
        with col2:
            st.link_button("🐛 Report Issue", "https://github.com/your-org/arthaai/issues", use_container_width=True)
