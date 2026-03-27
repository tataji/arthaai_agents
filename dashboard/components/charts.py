"""
dashboard/components/charts.py — Reusable Plotly chart builders
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import Optional, List


COLORS = {
    "green":      "#059669",
    "green_fill": "rgba(5,150,105,0.08)",
    "red":        "#dc2626",
    "red_fill":   "rgba(220,38,38,0.08)",
    "blue":       "#2563eb",
    "amber":      "#d97706",
    "gray":       "#6b7280",
    "bg":         "#ffffff",
    "grid":       "rgba(0,0,0,0.05)",
}

LAYOUT_BASE = dict(
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=dict(family="DM Sans, sans-serif", size=12, color="#374151"),
    margin=dict(l=40, r=20, t=30, b=40),
    legend=dict(
        bgcolor="rgba(255,255,255,0.9)",
        bordercolor="rgba(0,0,0,0.05)",
        borderwidth=1,
        font=dict(size=11),
    ),
    xaxis=dict(
        gridcolor=COLORS["grid"],
        showgrid=True,
        zeroline=False,
        tickfont=dict(size=10),
    ),
    yaxis=dict(
        gridcolor=COLORS["grid"],
        showgrid=True,
        zeroline=False,
        tickfont=dict(size=10),
    ),
)


def pnl_curve_chart(pnl_data: List[float], labels: Optional[List[str]] = None) -> go.Figure:
    """Smooth equity/P&L curve chart."""
    xs = labels or list(range(len(pnl_data)))
    color = COLORS["green"] if pnl_data[-1] >= 0 else COLORS["red"]
    fill  = COLORS["green_fill"] if pnl_data[-1] >= 0 else COLORS["red_fill"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs, y=pnl_data,
        mode="lines",
        line=dict(color=color, width=2, shape="spline", smoothing=0.3),
        fill="tozeroy",
        fillcolor=fill,
        name="P&L",
        hovertemplate="₹%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**LAYOUT_BASE, height=220, showlegend=False)
    fig.add_hline(y=0, line_dash="dot", line_color=COLORS["gray"], line_width=1)
    return fig


def candlestick_chart(df: pd.DataFrame, symbol: str = "") -> go.Figure:
    """OHLCV candlestick with volume bars and key indicators."""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.02,
    )

    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["open"],  high=df["high"],
        low=df["low"],    close=df["close"],
        increasing=dict(fillcolor=COLORS["green"], line=dict(color=COLORS["green"])),
        decreasing=dict(fillcolor=COLORS["red"],   line=dict(color=COLORS["red"])),
        name="Price",
        showlegend=False,
    ), row=1, col=1)

    # EMA lines
    if "ema_9" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["ema_9"],
            line=dict(color=COLORS["amber"], width=1),
            name="EMA 9", hoverinfo="skip",
        ), row=1, col=1)
    if "ema_21" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["ema_21"],
            line=dict(color=COLORS["blue"], width=1),
            name="EMA 21", hoverinfo="skip",
        ), row=1, col=1)

    # Volume
    colors = [COLORS["green"] if c >= o else COLORS["red"]
              for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["volume"],
        marker_color=colors, marker_opacity=0.5,
        name="Volume", showlegend=False,
    ), row=2, col=1)

    fig.update_layout(
        **{k: v for k, v in LAYOUT_BASE.items() if k not in ("xaxis", "yaxis")},
        height=380,
        title=dict(text=symbol, font=dict(size=14, color="#111827")),
        xaxis_rangeslider_visible=False,
        margin=dict(l=50, r=20, t=40, b=40),
    )
    fig.update_yaxes(tickprefix="₹", row=1)
    return fig


def rsi_macd_chart(df: pd.DataFrame) -> go.Figure:
    """RSI and MACD indicator chart."""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.5, 0.5],
        vertical_spacing=0.05,
        subplot_titles=("RSI (14)", "MACD"),
    )

    if "rsi" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["rsi"],
            line=dict(color=COLORS["blue"], width=1.5),
            name="RSI", fill="tozeroy",
            fillcolor="rgba(37,99,235,0.05)",
        ), row=1, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color=COLORS["red"],   row=1, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color=COLORS["green"], row=1, col=1)
        fig.add_hrect(y0=30, y1=70, fillcolor="rgba(0,0,0,0.02)",
                      line_width=0, row=1, col=1)

    if "macd" in df.columns:
        colors = [COLORS["green"] if v >= 0 else COLORS["red"]
                  for v in df.get("macd_hist", [0] * len(df))]
        fig.add_trace(go.Bar(
            x=df.index, y=df["macd_hist"], marker_color=colors,
            name="MACD Hist", opacity=0.6,
        ), row=2, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["macd"],
            line=dict(color=COLORS["blue"], width=1.2), name="MACD",
        ), row=2, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["macd_signal"],
            line=dict(color=COLORS["amber"], width=1.2), name="Signal",
        ), row=2, col=1)

    fig.update_layout(
        **{k: v for k, v in LAYOUT_BASE.items() if k not in ("xaxis", "yaxis")},
        height=320, showlegend=True,
        margin=dict(l=50, r=20, t=40, b=40),
    )
    return fig


def portfolio_donut(allocations: dict) -> go.Figure:
    """Portfolio allocation donut chart."""
    colors = [COLORS["green"], COLORS["blue"], COLORS["amber"],
              COLORS["gray"], "#8b5cf6", "#ec4899"]
    fig = go.Figure(go.Pie(
        labels=list(allocations.keys()),
        values=list(allocations.values()),
        hole=0.60,
        marker=dict(colors=colors[:len(allocations)]),
        textinfo="label+percent",
        textfont=dict(size=11),
        hovertemplate="%{label}: %{value:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="white",
        margin=dict(l=10, r=10, t=10, b=10),
        height=220,
        showlegend=False,
        font=dict(family="DM Sans, sans-serif", size=11),
    )
    return fig


def sector_bar_chart(sectors: dict) -> go.Figure:
    """Horizontal bar chart for sector exposure."""
    df = pd.DataFrame(list(sectors.items()), columns=["Sector", "Exposure"])
    df = df.sort_values("Exposure")
    colors = [COLORS["green"] if v > 0 else COLORS["red"] for v in df["Exposure"]]

    fig = go.Figure(go.Bar(
        x=df["Exposure"],
        y=df["Sector"],
        orientation="h",
        marker_color=colors,
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        **{k: v for k, v in LAYOUT_BASE.items() if k not in ("xaxis", "yaxis")},
        height=max(200, len(sectors) * 32),
        margin=dict(l=100, r=30, t=20, b=40),
        showlegend=False,
    )
    fig.update_xaxes(ticksuffix="%")
    return fig


def win_loss_chart(wins: int, losses: int, total_pnl: float) -> go.Figure:
    """Win/loss donut with P&L annotation."""
    fig = go.Figure(go.Pie(
        labels=["Wins", "Losses"],
        values=[max(wins, 0), max(losses, 0)],
        hole=0.65,
        marker=dict(colors=[COLORS["green"], COLORS["red"]]),
        textinfo="label+value",
        textfont=dict(size=11),
    ))
    color = COLORS["green"] if total_pnl >= 0 else COLORS["red"]
    sign  = "+" if total_pnl >= 0 else ""
    fig.add_annotation(
        text=f"{sign}₹{abs(total_pnl):,.0f}",
        font=dict(size=14, color=color, family="DM Sans"),
        showarrow=False,
    )
    fig.update_layout(
        paper_bgcolor="white",
        margin=dict(l=10, r=10, t=10, b=10),
        height=200,
        showlegend=True,
        legend=dict(font=dict(size=11)),
        font=dict(family="DM Sans, sans-serif"),
    )
    return fig


def backtest_equity_curve(equity: List[float], benchmark: Optional[List[float]] = None) -> go.Figure:
    """Equity curve vs optional benchmark."""
    xs = list(range(len(equity)))
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs, y=equity,
        line=dict(color=COLORS["green"], width=2),
        fill="tozeroy",
        fillcolor=COLORS["green_fill"],
        name="Strategy",
    ))
    if benchmark:
        fig.add_trace(go.Scatter(
            x=xs, y=benchmark,
            line=dict(color=COLORS["gray"], width=1.5, dash="dot"),
            name="Benchmark (Buy & Hold)",
        ))
    fig.update_layout(
        **LAYOUT_BASE,
        height=280,
        title=dict(text="Equity Curve", font=dict(size=13)),
    )
    fig.update_yaxes(tickprefix="₹")
    return fig
