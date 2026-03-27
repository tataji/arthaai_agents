"""
dashboard/state.py — Streamlit session state management
"""

import streamlit as st
from datetime import datetime


def init_state():
    """Initialize all session state keys with defaults."""
    defaults = {
        # App
        "trading_mode":      "paper",
        "market_open":       True,
        "last_refresh":      None,
        "auto_refresh":      True,
        "refresh_interval":  30,

        # Portfolio
        "capital":           2_500_000.0,
        "today_pnl":         0.0,
        "today_trades":      0,
        "open_positions":    [],

        # Signals
        "signals":           {},
        "watchlist_data":    [],
        "agent_logs":        [],

        # Chat
        "chat_history":      [
            {
                "role":    "assistant",
                "content": (
                    "Namaste! I'm your ArthAI trading assistant for NSE & BSE markets. "
                    "Ask me about stocks, F&O strategies, technical analysis, or your portfolio."
                ),
            }
        ],
        "chat_loading":      False,

        # Settings
        "anthropic_api_key": "",
        "kite_api_key":      "",
        "kite_access_token": "",
        "telegram_token":    "",
        "telegram_chat_id":  "",
        "max_position_pct":  5.0,
        "daily_loss_limit":  2.0,
        "default_sl_pct":    1.5,
        "default_tp_pct":    3.0,
        "max_positions":     15,
        "active_strategies": ["Momentum", "Mean Reversion"],
        "broker":            "Zerodha",

        # Agents
        "agents_running":    False,
        "agent_status":      {
            "Orchestrator":     {"status": "idle",    "tasks": 0},
            "Technical":        {"status": "idle",    "tasks": 0},
            "Fundamental":      {"status": "idle",    "tasks": 0},
            "News":             {"status": "idle",    "tasks": 0},
            "Risk Manager":     {"status": "idle",    "tasks": 0},
            "F&O Strategy":     {"status": "idle",    "tasks": 0},
        },

        # F&O
        "fo_results":        {},
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get(key, default=None):
    return st.session_state.get(key, default)


def set_val(key, value):
    st.session_state[key] = value


def append_log(agent: str, message: str, level: str = "info"):
    logs = st.session_state.get("agent_logs", [])
    logs.append({
        "time":    datetime.now().strftime("%H:%M:%S"),
        "agent":   agent,
        "message": message,
        "level":   level,
    })
    # Keep last 200 logs
    st.session_state["agent_logs"] = logs[-200:]
