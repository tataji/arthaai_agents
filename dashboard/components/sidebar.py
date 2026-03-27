"""
dashboard/components/sidebar.py — Sidebar navigation
"""

import streamlit as st
from datetime import datetime
from dashboard.state import get


def render_sidebar() -> str:
    with st.sidebar:
        # ── Logo ──────────────────────────────────────────────────────────
        st.markdown(
            '<div class="logo-text">Artha<span class="logo-accent">AI</span></div>',
            unsafe_allow_html=True,
        )
        st.caption("Agentic Trading · NSE & BSE")
        st.divider()

        # ── Mode indicator ─────────────────────────────────────────────────
        mode = st.session_state.get("trading_mode", "paper")
        if mode == "live":
            st.markdown(
                '🔴 &nbsp;<b style="color:#ef4444">LIVE TRADING</b>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '🟡 &nbsp;<b style="color:#f59e0b">Paper Trading</b>',
                unsafe_allow_html=True,
            )

        # ── Market status ──────────────────────────────────────────────────
        now = datetime.now()
        is_weekday = now.weekday() < 5
        market_open = (
            is_weekday
            and now.hour * 60 + now.minute >= 9 * 60 + 15
            and now.hour * 60 + now.minute <= 15 * 60 + 30
        )
        dot = "🟢" if market_open else "⚫"
        st.markdown(
            f"{dot} &nbsp;Market {'**Open**' if market_open else 'Closed'} &nbsp;"
            f"<span style='color:#9ca3af;font-size:12px'>{now.strftime('%H:%M IST')}</span>",
            unsafe_allow_html=True,
        )
        st.divider()

        # ── Navigation ─────────────────────────────────────────────────────
        st.markdown("**NAVIGATION**")
        nav_items = [
            ("📊", "Overview"),
            ("👁", "Watchlist"),
            ("🤖", "AI Chat"),
            ("💼", "Positions"),
            ("📈", "Analytics"),
            ("📋", "Options Chain"),
            ("⚙️", "Agents"),
            ("📐", "F&O Desk"),
            ("🔬", "Backtest"),
            ("🩺", "Health"),
            ("🔧", "Settings"),
        ]
        page = st.radio(
            "nav",
            [f"{icon}  {label}" for icon, label in nav_items],
            label_visibility="collapsed",
        )
        # Strip icon prefix
        selected = " ".join(page.split()[1:]) if page else "Overview"

        st.divider()

        # ── Quick stats ────────────────────────────────────────────────────
        pnl = st.session_state.get("today_pnl", 0)
        pnl_color = "#059669" if pnl >= 0 else "#dc2626"
        pnl_sign  = "+" if pnl >= 0 else ""
        st.markdown(f"""
<div style='font-size:11px;color:#9ca3af;margin-bottom:2px'>TODAY P&L</div>
<div style='font-size:17px;font-weight:600;color:{pnl_color}'>
  {pnl_sign}₹{abs(pnl):,.0f}
</div>
""", unsafe_allow_html=True)

        st.markdown(f"""
<div style='font-size:11px;color:#9ca3af;margin:8px 0 2px'>OPEN POSITIONS</div>
<div style='font-size:17px;font-weight:600'>
  {len(st.session_state.get('open_positions', []))}
  <span style='font-size:12px;font-weight:400;color:#9ca3af'>
    / {st.session_state.get('max_positions', 15)}
  </span>
</div>
""", unsafe_allow_html=True)

        st.divider()

        # ── Agent toggle ───────────────────────────────────────────────────
        running = st.session_state.get("agents_running", False)
        if st.button(
            "⏹ Stop Agents" if running else "▶ Start Agents",
            use_container_width=True,
            type="primary" if not running else "secondary",
        ):
            st.session_state["agents_running"] = not running
            st.rerun()

        # ── Auto-refresh toggle ────────────────────────────────────────────
        st.session_state["auto_refresh"] = st.toggle(
            "Auto-refresh", value=st.session_state.get("auto_refresh", True)
        )

        # ── Version ────────────────────────────────────────────────────────
        st.caption("ArthAI v1.0.0 · © 2024")

    return selected
