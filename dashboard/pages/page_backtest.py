"""
dashboard/pages/page_backtest.py — Strategy Backtesting
"""

import streamlit as st
import pandas as pd
from dashboard.components.charts import backtest_equity_curve
from dashboard.services.data_service import get_backtest_result, NSE_SYMBOLS

STRATEGIES = ["Momentum", "Mean Reversion", "Breakout"]


def render():
    st.markdown('<div class="page-title">🔬 Strategy Backtest</div>', unsafe_allow_html=True)
    st.caption("Test trading strategies on historical NSE data before going live.")

    col_cfg, col_results = st.columns([1, 2])

    with col_cfg:
        st.markdown("**Configuration**")
        symbol   = st.selectbox("Symbol", NSE_SYMBOLS, index=0)
        strategy = st.selectbox("Strategy", STRATEGIES)
        days     = st.selectbox("Period", [90, 180, 365, 730], index=2, format_func=lambda x: f"{x} days")
        capital  = st.number_input("Starting Capital (₹)", value=100_000, step=10_000)

        st.markdown("**Risk Parameters**")
        sl_pct  = st.slider("Stop Loss %",  0.5, 5.0, 1.5, 0.5)
        tgt_pct = st.slider("Target %",     1.0, 10.0, 3.0, 0.5)
        pos_pct = st.slider("Position Size %", 5, 25, 10, 5)

        run = st.button("▶ Run Backtest", type="primary", use_container_width=True)

    with col_results:
        if run or st.session_state.get("bt_run"):
            st.session_state["bt_run"] = True
            with st.spinner(f"Backtesting {strategy} on {symbol} ({days} days)…"):
                result = get_backtest_result(symbol, strategy, days)

            if "error" in result:
                st.error(result["error"])
            else:
                # ── Key metrics ────────────────────────────────────────────
                st.markdown("**Results**")
                m1, m2, m3, m4 = st.columns(4)
                ret_color = "#059669" if result["total_return_pct"] >= 0 else "#dc2626"
                m1.metric("Total Return", f"{result['total_return_pct']:+.2f}%",
                          delta=f"{'Beat' if result['total_return_pct'] > 10 else 'Under'} benchmark")
                m2.metric("Win Rate", f"{result['win_rate']:.1f}%")
                m3.metric("Profit Factor", f"{result['profit_factor']:.2f}",
                          help=">1.5 is good, >2 is excellent")
                m4.metric("Max Drawdown", f"{result['max_drawdown_pct']:.2f}%")

                m5, m6, m7, m8 = st.columns(4)
                m5.metric("Total Trades", result["total_trades"])
                m6.metric("Winners", result["winners"])
                m7.metric("Avg Win", f"{result['avg_win_pct']:.2f}%")
                m8.metric("Avg Loss", f"{result['avg_loss_pct']:.2f}%")

                st.divider()

                # ── Equity curve ───────────────────────────────────────────
                st.plotly_chart(
                    backtest_equity_curve(result["equity_curve"], result.get("benchmark")),
                    use_container_width=True,
                    config={"displayModeBar": False},
                )

                # ── Trade breakdown ────────────────────────────────────────
                st.markdown("**Performance Summary**")
                summary = {
                    "Metric": [
                        "Starting Capital", "Final Capital", "Net Profit",
                        "Total Trades", "Win Rate", "Profit Factor",
                        "Avg Win %", "Avg Loss %", "Expectancy",
                        "Max Drawdown",
                    ],
                    "Value": [
                        f"₹{capital:,.0f}",
                        f"₹{result['final_capital']:,.0f}",
                        f"₹{result['final_capital'] - capital:+,.0f}",
                        str(result["total_trades"]),
                        f"{result['win_rate']:.1f}%",
                        f"{result['profit_factor']:.2f}",
                        f"{result['avg_win_pct']:.2f}%",
                        f"{result['avg_loss_pct']:.2f}%",
                        f"{result['expectancy']:.2f}%",
                        f"{result['max_drawdown_pct']:.2f}%",
                    ],
                }
                st.dataframe(pd.DataFrame(summary), hide_index=True, use_container_width=True)

                # ── Export ─────────────────────────────────────────────────
                df_export = pd.DataFrame(summary)
                csv = df_export.to_csv(index=False)
                st.download_button("📥 Export Results CSV", csv,
                                   f"backtest_{symbol}_{strategy}.csv", "text/csv")

                # ── Disclaimer ─────────────────────────────────────────────
                st.caption(
                    "⚠️ Past performance does not guarantee future results. "
                    "Backtest results are simulated and may differ from live trading "
                    "due to slippage, impact cost, and execution delays."
                )
        else:
            st.info("Configure parameters on the left and click **Run Backtest** to start.")

    # ── Multi-symbol scan ─────────────────────────────────────────────────────
    st.divider()
    st.markdown("**Multi-Symbol Batch Backtest**")
    st.caption("Run the same strategy across multiple symbols to find the best performers.")

    batch_syms     = st.multiselect("Select symbols", NSE_SYMBOLS, default=NSE_SYMBOLS[:6])
    batch_strategy = st.selectbox("Strategy", STRATEGIES, key="batch_strat")
    batch_days     = st.selectbox("Period", [90, 180, 365], index=1,
                                  format_func=lambda x: f"{x} days", key="batch_days")

    if st.button("▶ Run Batch Backtest", use_container_width=True):
        rows = []
        pbar = st.progress(0)
        for i, sym in enumerate(batch_syms):
            r = get_backtest_result(sym, batch_strategy, batch_days)
            if "error" not in r:
                rows.append({
                    "Symbol":      sym,
                    "Return %":    f"{r['total_return_pct']:+.2f}%",
                    "Win Rate":    f"{r['win_rate']:.1f}%",
                    "Trades":      r["total_trades"],
                    "P.Factor":    f"{r['profit_factor']:.2f}",
                    "Drawdown %":  f"{r['max_drawdown_pct']:.2f}%",
                    "Expectancy":  f"{r['expectancy']:.2f}%",
                })
            pbar.progress((i + 1) / len(batch_syms))

        pbar.empty()
        if rows:
            df_batch = pd.DataFrame(rows)
            def style_ret(val):
                return "color:#059669;font-weight:600" if "+" in val else "color:#dc2626;font-weight:600"
            st.dataframe(
                df_batch.style.map(style_ret, subset=["Return %"]),
                use_container_width=True, hide_index=True,
            )
            csv = df_batch.to_csv(index=False)
            st.download_button("📥 Export Batch Results", csv, "batch_backtest.csv", "text/csv")
