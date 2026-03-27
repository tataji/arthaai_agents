"""
dashboard/styles.py — Custom CSS for ArthAI Streamlit dashboard
"""

import streamlit as st


def inject_css():
    st.markdown("""
<style>
/* ── Reset & Base ─────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif !important;
}

/* ── Main layout ──────────────────────────────────────────────────────── */
.main .block-container {
    padding: 1.5rem 2rem 2rem 2rem;
    max-width: 100%;
}

/* ── Hide default Streamlit elements ──────────────────────────────────── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* ── Sidebar ──────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #0d1117 !important;
    border-right: 1px solid #21262d;
}
[data-testid="stSidebar"] * { color: #e6edf3 !important; }
[data-testid="stSidebar"] .stRadio label {
    padding: 6px 10px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px !important;
    transition: background 0.15s;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: #21262d;
}

/* ── Metric cards ─────────────────────────────────────────────────────── */
.metric-card {
    background: #ffffff;
    border: 0.5px solid rgba(0,0,0,0.08);
    border-radius: 12px;
    padding: 16px 18px;
    transition: box-shadow 0.15s;
}
.metric-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.metric-label {
    font-size: 11px;
    font-weight: 500;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
}
.metric-value {
    font-size: 24px;
    font-weight: 600;
    color: #111827;
    line-height: 1.2;
}
.metric-sub {
    font-size: 12px;
    color: #6b7280;
    margin-top: 4px;
}
.metric-value.green { color: #059669; }
.metric-value.red   { color: #dc2626; }

/* ── Signal badges ────────────────────────────────────────────────────── */
.badge {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.3px;
}
.badge-buy  { background: #d1fae5; color: #065f46; }
.badge-sell { background: #fee2e2; color: #991b1b; }
.badge-hold { background: #fef3c7; color: #92400e; }
.badge-blue { background: #dbeafe; color: #1e40af; }
.badge-gray { background: #f3f4f6; color: #374151; }

/* ── Agent status cards ───────────────────────────────────────────────── */
.agent-card {
    background: #ffffff;
    border: 0.5px solid rgba(0,0,0,0.08);
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 10px;
}
.agent-name { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.agent-desc { font-size: 12px; color: #6b7280; line-height: 1.5; }
.agent-running { color: #059669; font-size: 12px; font-weight: 500; }
.agent-standby { color: #d97706; font-size: 12px; font-weight: 500; }

/* ── Chat bubbles ─────────────────────────────────────────────────────── */
.chat-container {
    max-height: 480px;
    overflow-y: auto;
    padding: 8px 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.chat-msg-user {
    background: #f3f4f6;
    border-radius: 12px 12px 4px 12px;
    padding: 10px 14px;
    max-width: 80%;
    align-self: flex-end;
    font-size: 13px;
    margin-left: auto;
}
.chat-msg-ai {
    background: #ecfdf5;
    border-radius: 12px 12px 12px 4px;
    padding: 10px 14px;
    max-width: 85%;
    font-size: 13px;
    color: #064e3b;
    border-left: 3px solid #10b981;
    white-space: pre-wrap;
    line-height: 1.6;
}
.chat-msg-thinking {
    background: #f9fafb;
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 12px;
    color: #9ca3af;
    font-style: italic;
}

/* ── Page header ──────────────────────────────────────────────────────── */
.page-header {
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(0,0,0,0.06);
}
.page-title {
    font-size: 20px;
    font-weight: 600;
    color: #111827;
    margin: 0;
}
.page-subtitle { font-size: 13px; color: #6b7280; margin-top: 2px; }

/* ── Status dot ───────────────────────────────────────────────────────── */
.status-dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    margin-right: 5px;
}
.dot-green { background: #10b981; animation: pulse 1.5s infinite; }
.dot-red   { background: #ef4444; }
.dot-amber { background: #f59e0b; }
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.3; }
}

/* ── Data tables ──────────────────────────────────────────────────────── */
.stDataFrame { font-size: 12px !important; }
.stDataFrame thead { background: #f9fafb; }
[data-testid="stDataFrame"] table { width: 100%; }

/* ── Buttons ──────────────────────────────────────────────────────────── */
.stButton > button {
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.15s;
}
.stButton > button:hover { transform: translateY(-1px); }

/* ── Inputs ───────────────────────────────────────────────────────────── */
.stTextInput input, .stSelectbox select, .stNumberInput input {
    border-radius: 8px !important;
    font-size: 13px !important;
}

/* ── Progress bars ────────────────────────────────────────────────────── */
.confidence-bar {
    height: 4px;
    background: #e5e7eb;
    border-radius: 2px;
    overflow: hidden;
    margin-top: 4px;
}
.confidence-fill { height: 100%; border-radius: 2px; }
.fill-green { background: #10b981; }
.fill-red   { background: #ef4444; }
.fill-amber { background: #f59e0b; }

/* ── Section headers ──────────────────────────────────────────────────── */
.section-title {
    font-size: 14px;
    font-weight: 600;
    color: #374151;
    margin-bottom: 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid rgba(0,0,0,0.06);
}

/* ── Logo ─────────────────────────────────────────────────────────────── */
.logo-text {
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.5px;
}
.logo-accent { color: #10b981; }

/* ── Risk gauge ───────────────────────────────────────────────────────── */
.risk-bar-wrap {
    background: #f3f4f6;
    border-radius: 4px;
    height: 8px;
    overflow: hidden;
    margin: 6px 0;
}
.risk-bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s ease;
}

/* ── Tabs ─────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: transparent;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    padding: 6px 14px;
}
.stTabs [aria-selected="true"] {
    background: #ecfdf5 !important;
    color: #059669 !important;
}

/* ── Expanders ────────────────────────────────────────────────────────── */
.streamlit-expanderHeader { font-size: 13px; font-weight: 500; }

/* ── Scrollbar ────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #f1f5f9; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)
