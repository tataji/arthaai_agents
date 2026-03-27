"""
dashboard/pages/page_agents.py — Agent Control & Monitoring
"""

import streamlit as st
from dashboard.components.metrics import render_agent_card, metric_card
from dashboard.services.data_service import get_agent_status, get_recent_logs

AGENT_DESCRIPTIONS = {
    "Orchestrator":  "Master coordinator. Aggregates all sub-agent signals, runs Claude meta-decision, and places final trades within risk limits.",
    "Technical":     "Continuously scans NSE/BSE symbols for technical setups — RSI, MACD, Bollinger Bands, EMA crossovers, candlestick patterns.",
    "Fundamental":   "Monitors earnings, PE ratios, ROE, FII/DII activity, debt levels, and promoter pledging across NIFTY 50.",
    "News":          "Scrapes Moneycontrol, ET, LiveMint every 10 minutes. Uses Claude to extract sentiment and market-moving signals.",
    "Risk Manager":  "Hard gate for every trade. Enforces position sizing, daily loss limit, SL requirements, and R:R minimums.",
    "F&O Strategy":  "Identifies options opportunities — Iron Condor for high IV, Bull Call Spread for directional moves, manages Greeks.",
}


def render():
    st.markdown('<div class="page-title">⚙️ Agent Control Centre</div>', unsafe_allow_html=True)

    agent_statuses = get_agent_status()

    # ── Global controls ───────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    running = st.session_state.get("agents_running", False)
    with c1:
        if st.button(
            "⏹ Stop All Agents" if running else "▶ Start All Agents",
            use_container_width=True,
            type="primary" if not running else "secondary",
        ):
            st.session_state["agents_running"] = not running
            if not running:
                for k in agent_statuses:
                    agent_statuses[k]["status"] = "running"
            else:
                for k in agent_statuses:
                    agent_statuses[k]["status"] = "idle"
            st.rerun()
    with c2:
        mode = st.selectbox("Trading Mode",
                            ["Paper (Safe)", "Live (Real Money)"],
                            key="mode_select",
                            index=0 if st.session_state.get("trading_mode") == "paper" else 1)
        st.session_state["trading_mode"] = "paper" if "Paper" in mode else "live"
    with c3:
        st.metric("Active Agents", sum(1 for v in agent_statuses.values() if v["status"] == "running"))
    with c4:
        total_actions = sum(v.get("tasks", 0) for v in agent_statuses.values())
        st.metric("Total Actions Today", f"{total_actions:,}")

    st.divider()

    # ── Agent cards ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Agent Status</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for i, (name, status_data) in enumerate(agent_statuses.items()):
        with cols[i % 3]:
            render_agent_card(
                name=name,
                desc=AGENT_DESCRIPTIONS.get(name, ""),
                status=status_data["status"],
                tasks=status_data.get("tasks", 0),
            )

    st.divider()

    # ── Live log ──────────────────────────────────────────────────────────────
    col_log, col_risk = st.columns([2, 1])

    with col_log:
        st.markdown('<div class="section-title">Live Activity Log</div>', unsafe_allow_html=True)
        logs = get_recent_logs(20)
        level_colors = {
            "buy":   "#059669",
            "sell":  "#dc2626",
            "warn":  "#d97706",
            "info":  "#374151",
            "error": "#991b1b",
            "fo":    "#7c3aed",
            "risk":  "#d97706",
        }
        log_html = ""
        for log in logs:
            color = level_colors.get(log["level"], "#374151")
            agent_badge = f'<span style="background:#f3f4f6;color:#6b7280;font-size:10px;padding:1px 5px;border-radius:3px">{log["agent"]}</span>'
            log_html += (
                f'<div style="font-size:11.5px;padding:4px 0;border-bottom:1px solid rgba(0,0,0,0.04)">'
                f'<span style="color:#9ca3af;font-variant-numeric:tabular-nums;min-width:52px;display:inline-block">{log["time"]}</span>'
                f'&nbsp;{agent_badge}&nbsp;'
                f'<span style="color:{color}">{log["message"]}</span>'
                f'</div>'
            )
        st.markdown(
            f'<div style="max-height:400px;overflow-y:auto">{log_html}</div>',
            unsafe_allow_html=True,
        )

    with col_risk:
        st.markdown('<div class="section-title">Risk Dashboard</div>', unsafe_allow_html=True)

        capital = st.session_state.get("capital", 2_500_000)
        pnl     = st.session_state.get("today_pnl", 0)
        loss_limit = capital * st.session_state.get("daily_loss_limit", 2.0) / 100
        buffer_used = max(0, -pnl) / loss_limit * 100 if loss_limit else 0

        st.markdown(f"""
<div style="margin-bottom:12px">
  <div style="font-size:12px;color:#6b7280;margin-bottom:4px">Daily Loss Buffer</div>
  <div class="risk-bar-wrap">
    <div class="risk-bar-fill" style="width:{min(buffer_used, 100):.0f}%;
         background:{'#dc2626' if buffer_used > 75 else '#f59e0b' if buffer_used > 40 else '#059669'}">
    </div>
  </div>
  <div style="font-size:11px;color:#9ca3af;text-align:right">{buffer_used:.0f}% used</div>
</div>

<div style="font-size:12px">
  <div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid rgba(0,0,0,0.05)">
    <span style="color:#6b7280">Max Position</span>
    <span>{st.session_state.get('max_position_pct', 5.0):.0f}% of capital</span>
  </div>
  <div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid rgba(0,0,0,0.05)">
    <span style="color:#6b7280">Daily Loss Limit</span>
    <span style="color:#dc2626">₹{loss_limit:,.0f}</span>
  </div>
  <div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid rgba(0,0,0,0.05)">
    <span style="color:#6b7280">Default SL</span>
    <span>{st.session_state.get('default_sl_pct', 1.5):.1f}%</span>
  </div>
  <div style="display:flex;justify-content:space-between;padding:4px 0">
    <span style="color:#6b7280">Default Target</span>
    <span>{st.session_state.get('default_tp_pct', 3.0):.1f}%</span>
  </div>
</div>

<div style="margin-top:12px;font-size:12px;font-weight:600;
     color:{'#dc2626' if st.session_state.get('trading_mode') == 'live' else '#d97706'}">
  {'🔴 LIVE MODE — Real money at risk' if st.session_state.get('trading_mode') == 'live'
   else '🟡 Paper Trading — Simulation only'}
</div>
""", unsafe_allow_html=True)

        if buffer_used > 80:
            st.error("⚠️ Daily loss limit approaching! Review positions.")
        elif buffer_used > 50:
            st.warning("Loss buffer 50%+ consumed. Be cautious.")
