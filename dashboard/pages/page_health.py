"""
dashboard/pages/page_health.py — System Health Monitor
"""

import streamlit as st
import time
from datetime import datetime


def render():
    st.markdown('<div class="page-title">🩺 System Health</div>', unsafe_allow_html=True)
    st.caption("Check connectivity of all ArthAI services before starting trading.")

    col_run, col_status = st.columns([1, 3])
    with col_run:
        run_checks = st.button("▶ Run Health Check", type="primary", use_container_width=True)
        auto_check = st.toggle("Auto-check every 5 min", value=False)

    if run_checks or (auto_check and time.time() % 300 < 5):
        with st.spinner("Running health checks..."):
            try:
                from utils.health_check import run_all_checks, system_summary
                api_key = st.session_state.get("anthropic_api_key", "")
                checks  = run_all_checks(api_key)
                all_ok, summary = system_summary(checks)
                st.session_state["health_checks"]    = checks
                st.session_state["health_summary"]   = summary
                st.session_state["health_all_ok"]    = all_ok
                st.session_state["health_checked_at"] = datetime.now().strftime("%H:%M:%S")
            except Exception as e:
                st.error(f"Health check error: {e}")

    checks  = st.session_state.get("health_checks", [])
    summary = st.session_state.get("health_summary", "")
    all_ok  = st.session_state.get("health_all_ok", None)
    checked = st.session_state.get("health_checked_at", "")

    if summary:
        if all_ok:
            st.success(f"✅ {summary}")
        else:
            st.warning(f"⚠️ {summary}")

    if checks:
        st.caption(f"Last checked: {checked}")
        for c in checks:
            icon    = "✅" if c.ok else "❌"
            latency = f"  `{c.latency:.0f}ms`" if c.latency else ""
            with st.expander(f"{icon} {c.name}{latency}", expanded=not c.ok):
                if c.ok:
                    st.success(c.message)
                else:
                    st.error(c.message)
                if c.details:
                    for k, v in c.details.items():
                        st.caption(f"{k}: {v}")
    else:
        st.info("Click **Run Health Check** to verify all services.")

    st.divider()
    st.markdown("**Quick Diagnostics**")

    diag_col1, diag_col2 = st.columns(2)
    with diag_col1:
        st.markdown("**Environment Variables**")
        env_vars = [
            ("ANTHROPIC_API_KEY", "Anthropic AI"),
            ("KITE_API_KEY",      "Zerodha Kite"),
            ("KITE_ACCESS_TOKEN", "Kite Session"),
            ("TELEGRAM_BOT_TOKEN","Telegram Bot"),
            ("DATABASE_URL",      "Database"),
        ]
        import os
        for var, label in env_vars:
            session_val = st.session_state.get(var.lower(), "")
            env_val     = os.getenv(var, "")
            present     = bool(session_val or env_val)
            icon        = "✅" if present else "❌"
            st.markdown(
                f'<div style="font-size:12px;padding:3px 0">{icon} {label}</div>',
                unsafe_allow_html=True
            )

    with diag_col2:
        st.markdown("**Python Dependencies**")
        packages = [
            ("anthropic",     "Claude AI"),
            ("streamlit",     "Dashboard"),
            ("plotly",        "Charts"),
            ("kiteconnect",   "Zerodha"),
            ("yfinance",      "Market data"),
            ("ta",            "Indicators"),
            ("scipy",         "Math/Stats"),
            ("sqlalchemy",    "Database ORM"),
        ]
        for pkg, label in packages:
            try:
                __import__(pkg)
                st.markdown(f'<div style="font-size:12px;padding:3px 0">✅ {label}</div>',
                            unsafe_allow_html=True)
            except ImportError:
                st.markdown(f'<div style="font-size:12px;padding:3px 0;color:#dc2626">❌ {label} — run: pip install {pkg}</div>',
                            unsafe_allow_html=True)
