"""
tests/test_core.py — Core unit tests for ArthAI
Run: pytest tests/ -v
"""

import sys
import os
import math
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Indicators ─────────────────────────────────────────────────────────────────

class TestIndicators:
    def _make_df(self, n=100, seed=42):
        np.random.seed(seed)
        dates  = pd.date_range("2024-01-01", periods=n, freq="B")
        closes = 1000 * np.exp(np.cumsum(np.random.normal(0.001, 0.015, n)))
        opens  = closes * (1 + np.random.normal(0, 0.005, n))
        highs  = np.maximum(closes, opens) * (1 + abs(np.random.normal(0, 0.007, n)))
        lows   = np.minimum(closes, opens) * (1 - abs(np.random.normal(0, 0.007, n)))
        vols   = np.random.randint(500_000, 3_000_000, n).astype(float)
        return pd.DataFrame(
            {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
            index=dates,
        )

    def test_compute_all_indicators_runs(self):
        from utils.indicators import compute_all_indicators
        df = self._make_df()
        result = compute_all_indicators(df)
        assert "rsi" in result.columns
        assert "macd" in result.columns
        assert "bb_upper" in result.columns
        assert "ema_9" in result.columns
        assert "vwap" in result.columns

    def test_rsi_bounds(self):
        from utils.indicators import compute_all_indicators
        df = compute_all_indicators(self._make_df())
        rsi = df["rsi"].dropna()
        assert (rsi >= 0).all() and (rsi <= 100).all()

    def test_signal_summary_keys(self):
        from utils.indicators import compute_all_indicators, get_signal_summary
        df  = compute_all_indicators(self._make_df())
        sig = get_signal_summary(df)
        required = ["close", "rsi", "macd", "ema_trend", "long_term_trend",
                    "bb_position", "atr", "vol_ratio", "above_vwap", "support", "resistance"]
        for key in required:
            assert key in sig, f"Missing key: {key}"

    def test_momentum_score_range(self):
        from utils.indicators import compute_all_indicators, compute_momentum_score
        df    = compute_all_indicators(self._make_df())
        score = compute_momentum_score(df)
        assert 0.0 <= score <= 1.0


# ── Risk Agent ─────────────────────────────────────────────────────────────────

class TestRiskAgent:
    def test_sl_direction_buy(self):
        from agents.risk_agent import RiskAgent
        ra = RiskAgent()
        result = ra.approve_trade("RELIANCE", "BUY", 2800.0, 50, sl=2900.0, target=2950.0)
        assert not result.approved
        assert "SL" in result.reason

    def test_sl_direction_sell(self):
        from agents.risk_agent import RiskAgent
        ra = RiskAgent()
        result = ra.approve_trade("RELIANCE", "SELL", 2800.0, 50, sl=2700.0, target=2650.0)
        assert not result.approved
        assert "SL" in result.reason

    def test_valid_buy(self):
        from agents.risk_agent import RiskAgent
        ra = RiskAgent()
        result = ra.approve_trade("RELIANCE", "BUY", 2800.0, 50, sl=2750.0, target=2900.0)
        assert result.approved

    def test_sl_too_tight(self):
        from agents.risk_agent import RiskAgent
        ra = RiskAgent()
        result = ra.approve_trade("RELIANCE", "BUY", 2800.0, 10, sl=2799.0, target=2900.0)
        assert not result.approved

    def test_missing_sl(self):
        from agents.risk_agent import RiskAgent
        ra = RiskAgent()
        result = ra.approve_trade("RELIANCE", "BUY", 2800.0, 50, sl=0, target=2900.0)
        assert not result.approved
        assert "Stop-loss" in result.reason

    def test_daily_halt(self):
        from agents.risk_agent import RiskAgent
        import config
        ra = RiskAgent()
        ra._halt("Test halt")
        result = ra.approve_trade("RELIANCE", "BUY", 2800.0, 50, sl=2750.0, target=2900.0)
        assert not result.approved

    def test_rr_ratio(self):
        from agents.risk_agent import RiskAgent
        ra = RiskAgent()
        # R:R = 1:1 (below 1.5 minimum)
        result = ra.approve_trade("RELIANCE", "BUY", 2800.0, 50, sl=2750.0, target=2850.0)
        assert not result.approved
        assert "R:R" in result.reason

    def test_position_sizing_adjusts_qty(self):
        from agents.risk_agent import RiskAgent
        import config
        ra = RiskAgent()
        # Request qty 10000 which would exceed max_position_pct
        result = ra.approve_trade("RELIANCE", "BUY", 2800.0, 10000, sl=2720.0, target=2960.0)
        if result.approved:
            max_val = config.CAPITAL * config.MAX_POSITION_PCT
            assert result.adjusted_qty * 2800.0 <= max_val * 1.01


# ── F&O Agent ──────────────────────────────────────────────────────────────────

class TestFOAgent:
    def test_black_scholes_call(self):
        from agents.fo_agent import FOAgent
        fo     = FOAgent()
        result = fo.black_scholes(S=22800, K=23000, T=7/365, r=0.065, sigma=0.14, option_type="CE")
        assert result["price"] > 0
        assert 0 <= result["delta"] <= 1
        assert result["theta"] < 0
        assert result["vega"] > 0

    def test_black_scholes_put(self):
        from agents.fo_agent import FOAgent
        fo     = FOAgent()
        result = fo.black_scholes(S=22800, K=23000, T=7/365, r=0.065, sigma=0.14, option_type="PE")
        assert result["price"] > 0
        assert -1 <= result["delta"] <= 0

    def test_iron_condor_credit_positive(self):
        from agents.fo_agent import FOAgent
        fo     = FOAgent()
        result = fo.iron_condor(spot=22800, iv=0.14, days_to_expiry=7)
        assert result["net_credit"] > 0
        assert result["max_profit"] == result["net_credit"]
        assert result["breakeven_up"] > result["breakeven_down"]
        assert len(result["legs"]) == 4

    def test_bull_call_spread(self):
        from agents.fo_agent import FOAgent
        fo     = FOAgent()
        result = fo.bull_call_spread(spot=22800, iv=0.14, days_to_expiry=14)
        assert result["net_debit"] > 0
        assert result["max_profit"] > 0
        assert result["max_loss"] == result["net_debit"]

    def test_expiry_zero(self):
        from agents.fo_agent import FOAgent
        fo     = FOAgent()
        result = fo.black_scholes(S=22800, K=23000, T=0, r=0.065, sigma=0.14)
        assert result["price"] == 0


# ── Fundamental Agent ──────────────────────────────────────────────────────────

class TestFundamentalAgent:
    def test_score_range(self):
        from agents.fundamental_agent import FundamentalAgent
        fa   = FundamentalAgent()
        data = fa._mock_fundamentals("RELIANCE")
        score = fa._score_fundamentals(data)
        assert 0.0 <= score <= 1.0

    def test_strong_score_high_roe(self):
        from agents.fundamental_agent import FundamentalAgent
        fa   = FundamentalAgent()
        data = {
            "roe": 0.30, "pe_ratio": 18, "revenue_growth": 0.20,
            "earnings_growth": 0.25, "debt_equity": 0.2,
            "analyst_rating": "strong_buy",
        }
        score = fa._score_fundamentals(data)
        assert score > 0.7

    def test_weak_score_high_debt(self):
        from agents.fundamental_agent import FundamentalAgent
        fa   = FundamentalAgent()
        data = {
            "roe": 0.05, "pe_ratio": 80, "revenue_growth": -0.10,
            "earnings_growth": -0.15, "debt_equity": 3.5,
            "analyst_rating": "sell",
        }
        score = fa._score_fundamentals(data)
        assert score < 0.4


# ── Data Service (dashboard) ───────────────────────────────────────────────────

class TestDataService:
    def test_market_overview_keys(self):
        from dashboard.services.data_service import get_market_overview
        data = get_market_overview()
        for key in ["nifty50", "sensex", "banknifty", "india_vix"]:
            assert key in data
            assert "value" in data[key]
            assert "chg_pct" in data[key]

    def test_watchlist_structure(self):
        from dashboard.services.data_service import get_watchlist
        wl = get_watchlist()
        assert len(wl) > 0
        for item in wl:
            assert "symbol"     in item
            assert "ltp"        in item
            assert "action"     in item
            assert "confidence" in item
            assert item["action"] in ("BUY", "SELL", "HOLD")

    def test_portfolio_structure(self):
        from dashboard.services.data_service import get_portfolio
        p = get_portfolio()
        for key in ["positions", "today_pnl", "today_trades", "open_count", "capital"]:
            assert key in p

    def test_ohlcv_mock(self):
        from dashboard.services.data_service import get_ohlcv
        df = get_ohlcv("RELIANCE", days=30)
        assert not df.empty
        assert len(df) >= 20
        assert "close" in df.columns

    def test_backtest_result_keys(self):
        from dashboard.services.data_service import get_backtest_result
        r = get_backtest_result("TCS", "Momentum", 180)
        for key in ["total_trades", "win_rate", "profit_factor", "total_return_pct"]:
            assert key in r


# ── Metrics helpers ────────────────────────────────────────────────────────────

class TestMetricHelpers:
    def test_fmt_inr_crore(self):
        from dashboard.components.metrics import fmt_inr
        assert "Cr" in fmt_inr(25_000_000)

    def test_fmt_inr_lakh(self):
        from dashboard.components.metrics import fmt_inr
        assert "L" in fmt_inr(500_000)

    def test_fmt_inr_small(self):
        from dashboard.components.metrics import fmt_inr
        result = fmt_inr(1234.56)
        assert "₹" in result

    def test_signal_badge(self):
        from dashboard.components.metrics import signal_badge
        assert "badge-buy"  in signal_badge("BUY")
        assert "badge-sell" in signal_badge("SELL")
        assert "badge-hold" in signal_badge("HOLD")
