"""
config.py — Central configuration for ArthAI Trading System
All parameters can be overridden via .env
"""

import os
from dotenv import load_dotenv

load_dotenv(override=True)


# ── API Keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

KITE_API_KEY = os.getenv("KITE_API_KEY", "")
KITE_API_SECRET = os.getenv("KITE_API_SECRET", "")
KITE_ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN", "")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///arthaai.db")

# ── Testing flags ─────────────────────────────────────────────────────────────
FORCE_MARKET_OPEN = os.getenv("FORCE_MARKET_OPEN", "0") == "1"
FAST_CYCLE        = os.getenv("FAST_CYCLE", "0") == "1"


# ── Trading Mode ──────────────────────────────────────────────────────────────
TRADING_MODE = os.getenv("TRADING_MODE", "paper")   # "paper" | "live"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


# ── Capital & Risk ────────────────────────────────────────────────────────────
CAPITAL = float(os.getenv("CAPITAL", 2_500_000))          # ₹25 lakhs default
MAX_POSITION_PCT = float(os.getenv("MAX_POSITION_PCT", 5)) / 100
DAILY_LOSS_LIMIT_PCT = float(os.getenv("DAILY_LOSS_LIMIT_PCT", 2)) / 100
DEFAULT_SL_PCT = float(os.getenv("DEFAULT_SL_PCT", 1.5)) / 100
DEFAULT_TARGET_PCT = float(os.getenv("DEFAULT_TARGET_PCT", 3.0)) / 100
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", 15))
MAX_INTRADAY_TRADES = 50    # Circuit breaker: max trades per day


# ── Market Timing (IST) ───────────────────────────────────────────────────────
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"
PRE_OPEN = "09:00"
AVOID_FIRST_MINUTES = 15    # Skip first 15 min of market open (volatile)
AVOID_LAST_MINUTES = 10     # Square off all intraday before close


# ── Watchlist ─────────────────────────────────────────────────────────────────
NIFTY50_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
    "SBIN", "BHARTIARTL", "BAJFINANCE", "KOTAKBANK", "LT", "AXISBANK",
    "ASIANPAINT", "MARUTI", "SUNPHARMA", "TITAN", "ULTRACEMCO", "WIPRO",
    "ADANIENT", "ADANIPORTS", "NTPC", "POWERGRID", "TECHM", "NESTLEIND",
    "TATAMOTORS", "M&M", "HCLTECH", "TATASTEEL", "JSWSTEEL", "BAJAJFINSV",
    "ONGC", "COALINDIA", "GRASIM", "DIVISLAB", "EICHERMOT", "CIPLA",
    "APOLLOHOSP", "DRREDDY", "BPCL", "BRITANNIA", "HEROMOTOCO", "HINDALCO",
    "INDUSINDBK", "SBILIFE", "BAJAJ-AUTO", "LTIM", "TATACONSUM", "UPL",
    "VEDL", "PIDILITIND"
]

FNO_INDEX_SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"]

DEFAULT_WATCHLIST = NIFTY50_SYMBOLS[:20]   # Top 20 for scanning by default


# ── Technical Analysis ────────────────────────────────────────────────────────
TA_CONFIG = {
    "rsi_period": 14,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "bb_period": 20,
    "bb_std": 2,
    "ema_short": 9,
    "ema_medium": 21,
    "ema_long": 50,
    "ema_200": 200,
    "atr_period": 14,
    "volume_ma_period": 20,
}


# ── Agent Intervals (seconds) ─────────────────────────────────────────────────
# In production these run on longer intervals.
# Set FAST_CYCLE=1 in .env to use short intervals for testing/development.
import os as _os
_fast = os.getenv("FAST_CYCLE", "0") == "1"  # read fresh in case _os alias differs
AGENT_INTERVALS = {
    "orchestrator": 30   if _fast else 300,    # 30s test / 5 min prod
    "technical":    20   if _fast else 180,    # 20s test / 3 min prod
    "fundamental":  120  if _fast else 3600,   # 2 min test / 1 hr prod
    "news":         60   if _fast else 600,    # 1 min test / 10 min prod
    "risk":         10   if _fast else 30,     # 10s test / 30s prod
    "fo":           40   if _fast else 240,    # 40s test / 4 min prod
}


# ── Strategies ────────────────────────────────────────────────────────────────
ACTIVE_STRATEGIES = ["momentum", "mean_reversion"]
STRATEGY_CONFIG = {
    "momentum": {
        "lookback_days": 20,
        "min_momentum_score": 0.65,
        "volume_multiplier": 1.5,      # Volume must be 1.5x avg
    },
    "mean_reversion": {
        "bb_squeeze_threshold": 0.02,
        "rsi_range": (35, 65),
        "min_deviation_pct": 2.0,
    },
    "breakout": {
        "consolidation_days": 10,
        "breakout_volume_multiplier": 2.0,
        "atr_multiplier": 1.5,
    },
}


# ── Claude AI Prompts ─────────────────────────────────────────────────────────
SYSTEM_PROMPT_TRADING = """You are ArthAI, an expert AI trading assistant for Indian stock markets (NSE/BSE).
You have deep expertise in:
- Indian equity markets: NIFTY 50, SENSEX, BANK NIFTY, sector indices
- F&O trading: index/stock options, Greeks (delta, theta, gamma, vega), strategies
- Technical analysis: RSI, MACD, Bollinger Bands, Fibonacci, support/resistance, candlesticks
- Fundamental analysis: PE, EV/EBITDA, ROE, debt ratios for Indian companies
- SEBI regulations, circuit breakers, margin requirements, T+1 settlement
- Macro factors: RBI policy, INR/USD, FII/DII flows, GST data

Always respond with specific, actionable analysis. Use Indian number system (lakhs, crores).
Give all prices in ₹. Be concise. Structure responses clearly.
Format trade recommendations as: Entry | Stop Loss | Target | Rationale."""

SYSTEM_PROMPT_NEWS = """You are a financial news analyst specialising in Indian markets.
Analyse the provided news text and return a JSON object with:
{
  "sentiment": "bullish" | "bearish" | "neutral",
  "confidence": 0.0 to 1.0,
  "affected_stocks": ["SYMBOL1", "SYMBOL2"],
  "sectors": ["sector1"],
  "summary": "one sentence summary",
  "trading_implication": "specific action or observation"
}
Return only valid JSON, no other text."""

SYSTEM_PROMPT_TRADE_DECISION = """You are a disciplined quantitative trader for Indian equity markets.
Given the technical indicators, fundamental data, news sentiment, and risk parameters provided,
decide whether to BUY, SELL, or HOLD a stock.
Return a JSON object:
{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0 to 1.0,
  "entry_price": float,
  "stop_loss": float,
  "target": float,
  "quantity": int,
  "rationale": "brief explanation",
  "timeframe": "intraday" | "swing" | "positional"
}
Be conservative. Only recommend BUY/SELL if confidence > 0.65. Return only valid JSON."""
