"""
dashboard/app.py — ArthAI Streamlit Dashboard
Production-ready multi-page trading dashboard for Indian markets.

Run:
    streamlit run dashboard/app.py
"""

import streamlit as st

st.set_page_config(
    page_title="ArthAI — NSE/BSE Trading",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/your-org/arthaai",
        "Report a bug": "https://github.com/your-org/arthaai/issues",
        "About": "ArthAI — Agentic AI Trading for Indian Markets",
    },
)

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.pages import (
    page_overview, page_watchlist, page_ai_chat, page_positions,
    page_agents, page_fo, page_backtest, page_settings,
    page_analytics, page_options_chain, page_health,
)
from dashboard.components.sidebar import render_sidebar
from dashboard.state import init_state
from dashboard.styles import inject_css

inject_css()
init_state()
page = render_sidebar()

PAGES = {
    "Overview":      page_overview.render,
    "Watchlist":     page_watchlist.render,
    "AI Chat":       page_ai_chat.render,
    "Positions":     page_positions.render,
    "Analytics":     page_analytics.render,
    "Options Chain": page_options_chain.render,
    "Agents":        page_agents.render,
    "F&O Desk":      page_fo.render,
    "Backtest":      page_backtest.render,
    "Health":        page_health.render,
    "Settings":      page_settings.render,
}

if page in PAGES:
    PAGES[page]()
else:
    page_overview.render()
