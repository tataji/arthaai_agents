"""
dashboard/components/metrics.py — Metric card and badge helpers
"""

import streamlit as st
from typing import Optional


def metric_card(label: str, value: str, sub: str = "",
                color: str = "", delta: Optional[float] = None):
    """Render a styled metric card."""
    val_class = ""
    if color == "green":   val_class = ' class="metric-value green"'
    elif color == "red":   val_class = ' class="metric-value red"'
    else:                  val_class = ' class="metric-value"'

    sub_html = f'<div class="metric-sub">{sub}</div>' if sub else ""
    delta_html = ""
    if delta is not None:
        d_color = "#059669" if delta >= 0 else "#dc2626"
        d_sign  = "▲" if delta >= 0 else "▼"
        delta_html = f'<div style="font-size:11px;color:{d_color};margin-top:3px">{d_sign} {abs(delta):.2f}%</div>'

    st.markdown(f"""
<div class="metric-card">
  <div class="metric-label">{label}</div>
  <div{val_class}>{value}</div>
  {sub_html}
  {delta_html}
</div>
""", unsafe_allow_html=True)


def signal_badge(action: str) -> str:
    """Return HTML badge for a signal action."""
    cls = {"BUY": "badge-buy", "SELL": "badge-sell", "HOLD": "badge-hold"}.get(action, "badge-gray")
    return f'<span class="badge {cls}">{action}</span>'


def status_badge(label: str, status: str) -> str:
    """Running/idle status badge."""
    dot_cls = "dot-green" if status == "running" else "dot-amber" if status == "standby" else "dot-red"
    return f'<span class="status-dot {dot_cls}"></span>{label}'


def confidence_bar(pct: float, action: str = "BUY") -> str:
    """HTML confidence progress bar."""
    fill_cls = "fill-green" if action == "BUY" else "fill-red" if action == "SELL" else "fill-amber"
    return f"""
<div class="confidence-bar">
  <div class="confidence-fill {fill_cls}" style="width:{pct*100:.0f}%"></div>
</div>
<div style="font-size:10px;color:#9ca3af;text-align:right">{pct*100:.0f}%</div>
"""


def pnl_color(value: float) -> str:
    return "#059669" if value >= 0 else "#dc2626"


def fmt_inr(value: float) -> str:
    """Format number as Indian Rupees."""
    if abs(value) >= 1_00_00_000:
        return f"₹{value/1_00_00_000:.2f}Cr"
    elif abs(value) >= 1_00_000:
        return f"₹{value/1_00_000:.2f}L"
    else:
        return f"₹{value:,.2f}"


def render_agent_card(name: str, desc: str, status: str, tasks: int):
    """Render an agent status card."""
    dot   = "dot-green" if status == "running" else "dot-amber"
    label = "Running" if status == "running" else "Standby"
    pct   = min(100, tasks / 50)
    color = "#059669" if status == "running" else "#d97706"

    st.markdown(f"""
<div class="agent-card">
  <div class="agent-name">{name}</div>
  <div class="agent-desc">{desc}</div>
  <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">
    <span><span class="status-dot {dot}"></span>
    <span style="font-size:12px;font-weight:500;color:{color}">{label}</span></span>
    <span style="font-size:11px;color:#9ca3af">{tasks:,} actions</span>
  </div>
  <div class="risk-bar-wrap" style="margin-top:6px">
    <div class="risk-bar-fill" style="width:{pct:.0f}%;background:{color}"></div>
  </div>
</div>
""", unsafe_allow_html=True)
