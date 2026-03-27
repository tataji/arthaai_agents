"""
dashboard/pages/page_analytics.py — Portfolio Analytics & Performance
Deep-dive into performance metrics, sector attribution, risk analysis.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import random
from datetime import datetime, timedelta
from dashboard.components.metrics import metric_card, fmt_inr, pnl_color
from dashboard.services.data_service import get_portfolio


def render():
    st.markdown('<div class="page-title">📈 Portfolio Analytics</div>', unsafe_allow_html=True)
    st.caption("Performance attribution, risk metrics, and portfolio health.")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_perf, tab_risk, tab_sector, tab_correlation, tab_kelly = st.tabs([
        "Performance", "Risk Metrics", "Sector Attribution", "Correlation", "Position Sizing"
    ])

    portfolio = get_portfolio()

    # ── Generate sample return series ─────────────────────────────────────────
    def mock_returns(n=252, seed=42, drift=0.0008, vol=0.015):
        rng = np.random.default_rng(seed)
        return rng.normal(drift, vol, n).tolist()

    r = mock_returns()

    try:
        from utils.portfolio_analytics import compute_portfolio_stats, compute_var, kelly_criterion
        stats = compute_portfolio_stats(r, mock_returns(252, seed=0, drift=0.0005))
        var_95, cvar_95 = compute_var(r, 0.95)
        var_99, cvar_99 = compute_var(r, 0.99)
    except Exception as e:
        st.warning(f"Analytics module: {e}")
        return

    # ── Performance tab ───────────────────────────────────────────────────────
    with tab_perf:
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            metric_card("Total Return", f"{stats.total_return_pct:+.2f}%",
                        sub=f"Annualised: {stats.annualised_return:+.2f}%",
                        color="green" if stats.total_return_pct >= 0 else "red")
        with m2:
            metric_card("Sharpe Ratio", f"{stats.sharpe_ratio:.3f}",
                        sub="Risk-adjusted return",
                        color="green" if stats.sharpe_ratio >= 1 else "red" if stats.sharpe_ratio < 0 else "")
        with m3:
            metric_card("Win Rate", f"{stats.win_rate:.1f}%",
                        sub=f"{stats.winners}W / {stats.losers}L")
        with m4:
            metric_card("Profit Factor", f"{stats.profit_factor:.2f}",
                        sub=f"Expectancy: {stats.expectancy:.3f}%")

        st.divider()

        # ── Equity curve ──────────────────────────────────────────────────────
        dates  = pd.date_range(end=datetime.now(), periods=len(r), freq="B")
        equity = np.cumprod(1 + np.array(r))
        bm_r   = mock_returns(252, seed=0, drift=0.0005)
        bm_eq  = np.cumprod(1 + np.array(bm_r))

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.7, 0.3], vertical_spacing=0.04)

        fig.add_trace(go.Scatter(
            x=dates, y=equity * 100_000,
            line=dict(color="#059669", width=2),
            fill="tozeroy", fillcolor="rgba(5,150,105,0.06)",
            name="Strategy"
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=bm_eq * 100_000,
            line=dict(color="#6b7280", width=1.5, dash="dot"),
            name="Benchmark (NIFTY)"
        ), row=1, col=1)

        # Drawdown
        running_max = np.maximum.accumulate(equity)
        drawdown    = (equity - running_max) / running_max * 100
        fig.add_trace(go.Scatter(
            x=dates, y=drawdown,
            fill="tozeroy", fillcolor="rgba(220,38,38,0.15)",
            line=dict(color="#dc2626", width=1),
            name="Drawdown %"
        ), row=2, col=1)

        fig.update_layout(
            height=420, paper_bgcolor="white", plot_bgcolor="white",
            margin=dict(l=50, r=20, t=20, b=40),
            font=dict(family="DM Sans", size=11),
            legend=dict(orientation="h", y=1.08),
        )
        fig.update_yaxes(tickprefix="₹", row=1)
        fig.update_yaxes(ticksuffix="%", row=2)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # ── Monthly returns heatmap ────────────────────────────────────────────
        st.markdown('<div class="section-title">Monthly Returns Heatmap</div>', unsafe_allow_html=True)
        monthly_r = (pd.Series(r, index=dates)
                     .resample("ME")
                     .apply(lambda x: np.prod(1 + x) - 1) * 100)
        monthly_df = monthly_r.to_frame("return")
        monthly_df["year"]  = monthly_df.index.year
        monthly_df["month"] = monthly_df.index.strftime("%b")

        pivot = monthly_df.pivot_table(values="return", index="year", columns="month")
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        pivot  = pivot.reindex(columns=[m for m in months if m in pivot.columns])

        fig_hm = go.Figure(go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale=[[0,"#fee2e2"],[0.5,"#f9fafb"],[1,"#d1fae5"]],
            zmid=0,
            text=[[f"{v:.1f}%" if not np.isnan(v) else "" for v in row] for row in pivot.values],
            texttemplate="%{text}",
            textfont=dict(size=10),
            showscale=True,
        ))
        fig_hm.update_layout(
            height=180, paper_bgcolor="white", plot_bgcolor="white",
            margin=dict(l=50, r=20, t=10, b=30),
            font=dict(family="DM Sans", size=11),
            xaxis=dict(side="top"),
        )
        st.plotly_chart(fig_hm, use_container_width=True, config={"displayModeBar": False})

    # ── Risk Metrics tab ──────────────────────────────────────────────────────
    with tab_risk:
        r1, r2, r3, r4 = st.columns(4)
        with r1:
            metric_card("Max Drawdown", f"{stats.max_drawdown_pct:.2f}%",
                        sub=f"{stats.max_drawdown_duration} day duration", color="red")
        with r2:
            metric_card("Volatility (Ann.)", f"{stats.volatility_pct:.2f}%", sub="Daily returns σ×√252")
        with r3:
            metric_card("VaR (95%)", f"{var_95:.2f}%", sub=f"CVaR: {cvar_95:.2f}%", color="red")
        with r4:
            metric_card("Sortino Ratio", f"{stats.sortino_ratio:.3f}",
                        sub="Downside-adjusted Sharpe",
                        color="green" if stats.sortino_ratio > 1 else "")

        st.divider()

        col_var, col_dist = st.columns(2)
        with col_var:
            st.markdown('<div class="section-title">Value at Risk Summary</div>', unsafe_allow_html=True)
            var_data = pd.DataFrame({
                "Metric": ["VaR 95%", "CVaR 95%", "VaR 99%", "CVaR 99%"],
                "Daily %": [f"{var_95:.3f}%", f"{cvar_95:.3f}%", f"{var_99:.3f}%", f"{cvar_99:.3f}%"],
                "Weekly ₹ (est.)": [
                    fmt_inr(portfolio["capital"] * var_95 / 100 * 5),
                    fmt_inr(portfolio["capital"] * cvar_95 / 100 * 5),
                    fmt_inr(portfolio["capital"] * var_99 / 100 * 5),
                    fmt_inr(portfolio["capital"] * cvar_99 / 100 * 5),
                ],
            })
            st.dataframe(var_data, hide_index=True, use_container_width=True)

            st.caption("VaR = maximum expected loss at given confidence. CVaR = average loss beyond VaR.")

        with col_dist:
            st.markdown('<div class="section-title">Return Distribution</div>', unsafe_allow_html=True)
            fig_dist = go.Figure()
            fig_dist.add_trace(go.Histogram(
                x=[v * 100 for v in r], nbinsx=50,
                marker_color="#2563eb", opacity=0.7, name="Returns",
            ))
            fig_dist.add_vline(x=0, line_color="#9ca3af", line_dash="dot")
            fig_dist.add_vline(x=-var_95, line_color="#dc2626", line_dash="dash",
                               annotation_text=f"VaR 95%: {var_95:.2f}%")
            fig_dist.update_layout(
                height=220, paper_bgcolor="white", plot_bgcolor="white",
                margin=dict(l=40, r=20, t=20, b=40),
                font=dict(family="DM Sans", size=11),
                showlegend=False,
                xaxis=dict(title="Daily Return %", gridcolor="rgba(0,0,0,0.05)"),
                yaxis=dict(title="Frequency", gridcolor="rgba(0,0,0,0.05)"),
            )
            st.plotly_chart(fig_dist, use_container_width=True, config={"displayModeBar": False})

        st.divider()
        st.markdown('<div class="section-title">Full Stats Table</div>', unsafe_allow_html=True)
        stats_df = pd.DataFrame({
            "Metric": [
                "Total Return", "Annualised Return", "Sharpe Ratio", "Sortino Ratio",
                "Calmar Ratio", "Max Drawdown", "Volatility", "Beta", "Alpha",
                "Win Rate", "Profit Factor", "Expectancy", "Best Trade", "Worst Trade",
            ],
            "Value": [
                f"{stats.total_return_pct:+.2f}%", f"{stats.annualised_return:+.2f}%",
                f"{stats.sharpe_ratio:.3f}", f"{stats.sortino_ratio:.3f}",
                f"{stats.calmar_ratio:.3f}", f"{stats.max_drawdown_pct:.2f}%",
                f"{stats.volatility_pct:.2f}%", f"{stats.beta:.3f}",
                f"{stats.alpha_pct:+.2f}%", f"{stats.win_rate:.1f}%",
                f"{stats.profit_factor:.2f}", f"{stats.expectancy:.3f}%",
                f"{stats.best_trade_pct:+.2f}%", f"{stats.worst_trade_pct:+.2f}%",
            ],
        })
        st.dataframe(stats_df, hide_index=True, use_container_width=True)

    # ── Sector Attribution tab ────────────────────────────────────────────────
    with tab_sector:
        positions = portfolio.get("positions", [])
        if not positions:
            positions = [
                {"symbol": "RELIANCE", "sector": "Energy",   "pnl": 12400, "value": 142000},
                {"symbol": "HDFCBANK", "sector": "Banking",  "pnl": -3200, "value": 77000},
                {"symbol": "INFY",     "sector": "IT",       "pnl": 8900,  "value": 84000},
                {"symbol": "SUNPHARMA","sector": "Pharma",   "pnl": 6700,  "value": 47000},
                {"symbol": "MARUTI",   "sector": "Auto",     "pnl": -1800, "value": 54600},
            ]

        try:
            from utils.portfolio_analytics import compute_sector_attribution
            sector_attr = compute_sector_attribution(positions)
        except Exception:
            sector_attr = {}

        if sector_attr:
            sa1, sa2 = st.columns(2)
            with sa1:
                sectors   = list(sector_attr.keys())
                pnl_vals  = [sector_attr[s]["pnl"] for s in sectors]
                bar_colors = ["#059669" if v >= 0 else "#dc2626" for v in pnl_vals]

                fig_sa = go.Figure(go.Bar(
                    x=pnl_vals, y=sectors, orientation="h",
                    marker_color=bar_colors,
                    hovertemplate="%{y}: ₹%{x:,.0f}<extra></extra>",
                ))
                fig_sa.update_layout(
                    title="P&L by Sector", height=250,
                    paper_bgcolor="white", plot_bgcolor="white",
                    margin=dict(l=100, r=20, t=40, b=20),
                    font=dict(family="DM Sans", size=11),
                    xaxis=dict(tickprefix="₹", gridcolor="rgba(0,0,0,0.05)"),
                )
                st.plotly_chart(fig_sa, use_container_width=True, config={"displayModeBar": False})

            with sa2:
                weights = [sector_attr[s]["weight_pct"] for s in sectors]
                colors  = ["#059669","#2563eb","#d97706","#7c3aed","#ec4899","#6b7280"]
                fig_pie = go.Figure(go.Pie(
                    labels=sectors, values=weights, hole=0.55,
                    marker=dict(colors=colors[:len(sectors)]),
                    textinfo="label+percent",
                    textfont=dict(size=11),
                ))
                fig_pie.update_layout(
                    title="Portfolio Weights", height=250,
                    paper_bgcolor="white", margin=dict(l=0, r=0, t=40, b=0),
                    font=dict(family="DM Sans", size=11), showlegend=False,
                )
                st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})

            # Table
            rows = []
            for sec, data in sector_attr.items():
                rows.append({
                    "Sector":      sec,
                    "P&L":        f"₹{data['pnl']:+,.0f}",
                    "P&L Contrib %": f"{data['pnl_contribution_pct']:+.1f}%",
                    "Weight %":   f"{data['weight_pct']:.1f}%",
                    "Positions":  data["count"],
                    "Symbols":    ", ".join(data["symbols"]),
                })
            df_sa = pd.DataFrame(rows)
            def style_pnl_s(val):
                return "color:#059669;font-weight:600" if "+" in val else "color:#dc2626;font-weight:600"
            st.dataframe(df_sa.style.map(style_pnl_s, subset=["P&L","P&L Contrib %"]),
                         hide_index=True, use_container_width=True)

    # ── Correlation tab ───────────────────────────────────────────────────────
    with tab_correlation:
        st.markdown('<div class="section-title">Return Correlation Matrix</div>', unsafe_allow_html=True)
        st.caption("Low correlation between holdings reduces portfolio risk.")

        symbols_for_corr = ["RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK",
                            "SUNPHARMA","MARUTI","WIPRO","ADANIENT","NTPC"]
        rng = np.random.default_rng(99)
        price_data = {sym: rng.normal(0.0005, 0.015, 120).tolist() for sym in symbols_for_corr}

        try:
            from utils.portfolio_analytics import position_correlation_matrix
            corr_df = position_correlation_matrix(price_data)
        except Exception:
            corr_df = pd.DataFrame(price_data).corr().round(3)

        fig_corr = go.Figure(go.Heatmap(
            z=corr_df.values,
            x=corr_df.columns.tolist(),
            y=corr_df.index.tolist(),
            colorscale=[[0,"#fee2e2"],[0.5,"#f9fafb"],[1,"#d1fae5"]],
            zmid=0, zmin=-1, zmax=1,
            text=[[f"{v:.2f}" for v in row] for row in corr_df.values],
            texttemplate="%{text}",
            textfont=dict(size=10),
            showscale=True,
        ))
        fig_corr.update_layout(
            height=380, paper_bgcolor="white",
            margin=dict(l=80, r=20, t=20, b=80),
            font=dict(family="DM Sans", size=11),
        )
        st.plotly_chart(fig_corr, use_container_width=True, config={"displayModeBar": False})
        st.caption("Values close to 1 = highly correlated (similar risk), close to -1 = inversely correlated (natural hedge), near 0 = uncorrelated.")

    # ── Kelly tab ─────────────────────────────────────────────────────────────
    with tab_kelly:
        st.markdown('<div class="section-title">Kelly Criterion Position Sizer</div>', unsafe_allow_html=True)
        st.caption("Optimal fraction of capital to risk per trade based on historical performance.")

        col_in, col_out = st.columns(2)
        with col_in:
            k_win_rate  = st.slider("Win Rate %", 30, 80, int(stats.win_rate))
            k_avg_win   = st.slider("Avg Win %",  0.5, 8.0, max(abs(stats.avg_win_pct), 1.0), 0.1)
            k_avg_loss  = st.slider("Avg Loss %", 0.5, 5.0, max(abs(stats.avg_loss_pct), 0.8), 0.1)
            k_capital   = st.number_input("Capital (₹)", value=int(portfolio["capital"]), step=100_000)

        try:
            from utils.portfolio_analytics import kelly_criterion
            kelly_f = kelly_criterion(k_win_rate / 100, k_avg_win / 100, k_avg_loss / 100)
        except Exception:
            b = k_avg_win / k_avg_loss
            kelly_f = max(0, min(0.25, (k_win_rate / 100) - (1 - k_win_rate / 100) / b))

        half_kelly = kelly_f / 2
        quarter_kelly = kelly_f / 4

        with col_out:
            st.markdown(f"""
<div style="background:#f9fafb;border-radius:12px;padding:16px;font-size:13px">
  <div style="color:#6b7280;font-size:11px;margin-bottom:8px">KELLY POSITION SIZES</div>

  <div style="margin-bottom:10px">
    <div style="color:#6b7280;font-size:11px">Full Kelly (aggressive)</div>
    <div style="font-size:20px;font-weight:600;color:#dc2626">{kelly_f*100:.1f}%</div>
    <div style="font-size:12px;color:#9ca3af">≈ {fmt_inr(k_capital * kelly_f)} per trade</div>
  </div>

  <div style="margin-bottom:10px">
    <div style="color:#6b7280;font-size:11px">Half Kelly (recommended)</div>
    <div style="font-size:20px;font-weight:600;color:#d97706">{half_kelly*100:.1f}%</div>
    <div style="font-size:12px;color:#9ca3af">≈ {fmt_inr(k_capital * half_kelly)} per trade</div>
  </div>

  <div>
    <div style="color:#6b7280;font-size:11px">Quarter Kelly (conservative)</div>
    <div style="font-size:20px;font-weight:600;color:#059669">{quarter_kelly*100:.1f}%</div>
    <div style="font-size:12px;color:#9ca3af">≈ {fmt_inr(k_capital * quarter_kelly)} per trade</div>
  </div>
</div>
""", unsafe_allow_html=True)

        st.info(
            "💡 **Recommendation:** Most professional traders use Half Kelly to reduce risk of ruin "
            "while still compounding capital efficiently. Full Kelly maximises long-run growth but "
            "leads to large drawdowns."
        )

        # Kelly vs fraction sweep chart
        fractions = np.linspace(0.01, 0.5, 100)
        long_run_growth = [
            (k_win_rate / 100) * np.log(1 + f * k_avg_win / 100) +
            (1 - k_win_rate / 100) * np.log(1 - f * k_avg_loss / 100)
            for f in fractions
        ]
        fig_k = go.Figure()
        fig_k.add_trace(go.Scatter(
            x=fractions * 100, y=long_run_growth,
            line=dict(color="#2563eb", width=2), fill="tozeroy",
            fillcolor="rgba(37,99,235,0.05)", name="Log-Growth Rate",
        ))
        fig_k.add_vline(x=kelly_f * 100, line_color="#dc2626", line_dash="dash",
                        annotation_text=f"Full Kelly {kelly_f*100:.1f}%")
        fig_k.add_vline(x=half_kelly * 100, line_color="#059669", line_dash="dot",
                        annotation_text=f"Half Kelly {half_kelly*100:.1f}%")
        fig_k.update_layout(
            height=220, paper_bgcolor="white", plot_bgcolor="white",
            margin=dict(l=40, r=40, t=30, b=40),
            font=dict(family="DM Sans", size=11),
            xaxis=dict(title="Position Size %", gridcolor="rgba(0,0,0,0.05)"),
            yaxis=dict(title="Expected Log-Growth", gridcolor="rgba(0,0,0,0.05)"),
        )
        st.plotly_chart(fig_k, use_container_width=True, config={"displayModeBar": False})
