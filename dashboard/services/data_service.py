"""
dashboard/services/data_service.py — Data layer for the dashboard
Fetches live data from backend API or uses mock data when offline.
"""

import os
import sys
import time
import random
import requests
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

API_BASE = os.getenv("ARTHAAI_API_URL", "http://localhost:8000")
_USE_MOCK = True  # Flipped to False when API is reachable


def _api_get(path: str, timeout: int = 5) -> Optional[dict]:
    global _USE_MOCK
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=timeout)
        if r.status_code == 200:
            _USE_MOCK = False
            return r.json()
    except Exception:
        pass
    _USE_MOCK = True
    return None


# ── Mock data generators ──────────────────────────────────────────────────────

NSE_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "SBIN", "BHARTIARTL", "BAJFINANCE", "KOTAKBANK", "LT",
    "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA", "TITAN",
    "WIPRO", "ADANIENT", "NTPC", "TATAMOTORS", "HCLTECH",
]

SECTORS = {
    "RELIANCE": "Energy",    "TCS": "IT",         "HDFCBANK": "Banking",
    "INFY": "IT",            "ICICIBANK": "Banking", "SBIN": "Banking",
    "BHARTIARTL": "Telecom", "BAJFINANCE": "NBFC",  "KOTAKBANK": "Banking",
    "LT": "Infra",           "AXISBANK": "Banking",  "ASIANPAINT": "FMCG",
    "MARUTI": "Auto",        "SUNPHARMA": "Pharma",  "TITAN": "Consumer",
    "WIPRO": "IT",           "ADANIENT": "Conglomerate", "NTPC": "Power",
    "TATAMOTORS": "Auto",    "HCLTECH": "IT",
}

SEED_PRICES = {
    "RELIANCE": 2847, "TCS": 3912, "HDFCBANK": 1543, "INFY": 1682,
    "ICICIBANK": 1089, "SBIN": 812, "BHARTIARTL": 1542, "BAJFINANCE": 7240,
    "KOTAKBANK": 1892, "LT": 3621, "AXISBANK": 1187, "ASIANPAINT": 2890,
    "MARUTI": 10920, "SUNPHARMA": 1589, "TITAN": 3420, "WIPRO": 512,
    "ADANIENT": 2341, "NTPC": 389, "TATAMOTORS": 1021, "HCLTECH": 1782,
}


def _rand(sym: str, base: float, spread: float = 0.005) -> float:
    """Deterministic random tick around base price."""
    r = random.Random(int(time.time() // 10) + hash(sym))
    return round(base * (1 + r.uniform(-spread, spread)), 2)


def get_market_overview() -> Dict:
    live = _api_get("/api/market/overview")
    if live:
        return live
    r = random.Random(int(time.time() // 30))
    return {
        "nifty50":     {"value": 22847.55 + r.uniform(-80, 80),   "chg_pct": r.uniform(-0.5, 0.8)},
        "sensex":      {"value": 75234.10 + r.uniform(-200, 200), "chg_pct": r.uniform(-0.4, 0.7)},
        "banknifty":   {"value": 48120.30 + r.uniform(-150, 150), "chg_pct": r.uniform(-0.6, 0.5)},
        "finnifty":    {"value": 21380.00 + r.uniform(-80, 80),   "chg_pct": r.uniform(-0.4, 0.6)},
        "india_vix":   {"value": 13.42 + r.uniform(-0.5, 0.5),   "chg_pct": r.uniform(-2, 3)},
        "usdinr":      {"value": 83.42 + r.uniform(-0.2, 0.2),   "chg_pct": r.uniform(-0.1, 0.1)},
        "fii_net":     round(r.uniform(-2000, 3000), 0),
        "dii_net":     round(r.uniform(-1500, 2500), 0),
        "advance":     int(r.uniform(900, 1400)),
        "decline":     int(r.uniform(500, 900)),
    }


def get_portfolio() -> Dict:
    live = _api_get("/api/portfolio")
    if live:
        return live
    r = random.Random(int(time.time() // 60))
    positions = []
    for sym in ["RELIANCE", "ICICIBANK", "SUNPHARMA", "MARUTI", "ADANIENT"][:3]:
        base  = SEED_PRICES[sym]
        price = _rand(sym, base)
        qty   = r.randint(10, 100)
        avg   = round(base * r.uniform(0.97, 1.02), 2)
        pnl   = round((price - avg) * qty, 2)
        positions.append({
            "symbol": sym, "action": "BUY", "qty": qty,
            "avg_price": avg, "ltp": price, "pnl": pnl,
            "pnl_pct": round((price - avg) / avg * 100, 2),
            "stop_loss": round(avg * 0.985, 2),
            "target": round(avg * 1.03, 2),
            "sector": SECTORS.get(sym, "Other"),
        })
    pnl_total = sum(p["pnl"] for p in positions)
    return {
        "positions":    positions,
        "today_pnl":    round(pnl_total + r.uniform(-5000, 15000), 2),
        "today_trades": r.randint(5, 40),
        "open_count":   len(positions),
        "capital":      2_500_000,
        "deployed_pct": round(r.uniform(20, 55), 1),
    }


def get_watchlist() -> List[Dict]:
    live = _api_get("/api/watchlist")
    if live:
        return live.get("watchlist", [])

    SIGNALS = ["BUY", "BUY", "SELL", "HOLD", "BUY", "SELL", "HOLD"]
    result  = []
    r       = random.Random(int(time.time() // 30))
    for sym in NSE_SYMBOLS:
        base   = SEED_PRICES[sym]
        ltp    = _rand(sym, base)
        chg    = round((ltp - base) / base * 100, 2)
        signal = r.choice(SIGNALS)
        conf   = round(r.uniform(0.55, 0.92), 2) if signal != "HOLD" else round(r.uniform(0.3, 0.55), 2)
        rsi    = round(r.uniform(38, 72), 1)
        result.append({
            "symbol":     sym,
            "name":       sym.title(),
            "ltp":        ltp,
            "chg_pct":    chg,
            "sector":     SECTORS.get(sym, "Other"),
            "rsi":        rsi,
            "macd":       r.choice(["Bullish", "Bearish", "Neutral"]),
            "action":     signal,
            "confidence": conf,
            "entry":      round(ltp * r.uniform(0.99, 1.005), 2),
            "stop_loss":  round(ltp * 0.985, 2),
            "target":     round(ltp * 1.03, 2),
            "vol_ratio":  round(r.uniform(0.6, 2.8), 2),
            "atr":        round(base * 0.012, 2),
        })
    return result


def get_pnl_history(days: int = 30) -> pd.DataFrame:
    """Simulated intraday + daily P&L history."""
    r      = random.Random(42)
    dates  = pd.date_range(end=datetime.now(), periods=days * 8, freq="h")
    values = [0.0]
    for _ in range(len(dates) - 1):
        values.append(values[-1] + r.gauss(800, 4000))
    return pd.DataFrame({"datetime": dates, "pnl": values})


def get_ohlcv(symbol: str, days: int = 60) -> pd.DataFrame:
    """Mock OHLCV data for charting."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from data.market_data import market_data
        from utils.indicators import compute_all_indicators
        df = market_data.get_ohlcv(symbol, "day", days=days)
        if not df.empty:
            return compute_all_indicators(df)
    except Exception:
        pass

    # Fallback mock
    np.random.seed(hash(symbol) % 2**31)
    start = SEED_PRICES.get(symbol, 1000)
    dates = pd.bdate_range(end=datetime.now(), periods=days)
    ret   = np.random.normal(0.0005, 0.015, days)
    c     = start * np.exp(np.cumsum(ret))
    o     = c * (1 + np.random.normal(0, 0.005, days))
    h     = np.maximum(c, o) * (1 + abs(np.random.normal(0, 0.008, days)))
    lo    = np.minimum(c, o) * (1 - abs(np.random.normal(0, 0.008, days)))
    v     = np.random.randint(500_000, 5_000_000, days)
    df    = pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "volume": v}, index=dates)
    try:
        from utils.indicators import compute_all_indicators
        df = compute_all_indicators(df)
    except Exception:
        pass
    return df


def get_agent_status() -> Dict:
    live = _api_get("/api/agents/status")
    if live:
        return live
    r = random.Random(int(time.time() // 10))
    return {
        "Orchestrator":  {"status": "running", "tasks": r.randint(100, 200)},
        "Technical":     {"status": "running", "tasks": r.randint(500, 1200)},
        "Fundamental":   {"status": "running", "tasks": r.randint(50, 120)},
        "News":          {"status": "running", "tasks": r.randint(100, 300)},
        "Risk Manager":  {"status": "running", "tasks": r.randint(800, 1500)},
        "F&O Strategy":  {"status": "standby", "tasks": r.randint(10, 50)},
    }


def get_recent_logs(n: int = 20) -> List[Dict]:
    import streamlit as st
    logs = st.session_state.get("agent_logs", [])
    if logs:
        return logs[-n:]
    # Mock logs
    r = random.Random(int(time.time() // 5))
    messages = [
        ("Orchestrator",  "info",  "Cycle complete — 3 actionable signals found"),
        ("Technical",     "buy",   "SUNPHARMA BUY signal — RSI 71, MACD bullish crossover"),
        ("Risk Manager",  "warn",  "WIPRO position: 68% of daily loss consumed"),
        ("News",          "info",  "Reliance Q3 beat estimates — added to BUY list"),
        ("Technical",     "sell",  "TCS SELL signal — RSI 41, EMA bearish alignment"),
        ("F&O Strategy",  "info",  "NIFTY Iron Condor: VIX 13.4, theta +₹420/day"),
        ("Orchestrator",  "info",  "Claude meta-decision: approved ICICIBANK, SUNPHARMA"),
        ("Risk Manager",  "info",  "Portfolio risk: 34% deployed, buffer 12% used"),
    ]
    now = datetime.now()
    return [
        {
            "time":    (now - timedelta(minutes=i * 3 + r.randint(0, 2))).strftime("%H:%M:%S"),
            "agent":   msg[0],
            "level":   msg[1],
            "message": msg[2],
        }
        for i, msg in enumerate(messages[:n])
    ]


def get_backtest_result(symbol: str, strategy: str, days: int) -> Dict:
    """Run or fetch backtest results."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from backtest import Backtest
        bt     = Backtest()
        result = bt.run_momentum(symbol, days)
        return result
    except Exception:
        pass
    # Mock
    r = random.Random(hash(symbol + strategy) % 2**31)
    trades   = r.randint(15, 60)
    win_rate = r.uniform(45, 68)
    winners  = int(trades * win_rate / 100)
    return {
        "symbol":            symbol,
        "strategy":          strategy,
        "period_days":       days,
        "total_trades":      trades,
        "winners":           winners,
        "losers":            trades - winners,
        "win_rate":          round(win_rate, 1),
        "avg_win_pct":       round(r.uniform(1.5, 4.0), 2),
        "avg_loss_pct":      round(-r.uniform(0.8, 2.0), 2),
        "profit_factor":     round(r.uniform(1.1, 2.8), 2),
        "total_return_pct":  round(r.uniform(-5, 45), 2),
        "max_drawdown_pct":  round(-r.uniform(4, 18), 2),
        "final_capital":     round(100_000 * (1 + r.uniform(-0.05, 0.45)), 0),
        "expectancy":        round(r.uniform(0.2, 1.8), 2),
        "equity_curve":      _mock_equity_curve(r, days),
        "benchmark":         _mock_equity_curve(random.Random(0), days, drift=0.0002),
    }


def _mock_equity_curve(r, n: int, start: float = 100_000, drift: float = 0.0008) -> List[float]:
    curve = [start]
    for _ in range(n - 1):
        curve.append(curve[-1] * (1 + r.gauss(drift, 0.012)))
    return curve
