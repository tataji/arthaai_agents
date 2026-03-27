"""
data/market_data.py — Live market data via Zerodha Kite Connect
Falls back to yfinance for paper trading / testing
"""

import os
import time
from dotenv import load_dotenv
load_dotenv(override=True)
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from utils.logger import get_logger
import config

logger = get_logger("market_data")

# ── Kite Connect ──────────────────────────────────────────────────────────────
try:
    from kiteconnect import KiteConnect, KiteTicker
    KITE_AVAILABLE = True
except ImportError:
    KITE_AVAILABLE = False
    logger.warning("kiteconnect not installed — using yfinance fallback")

# ── yfinance fallback ─────────────────────────────────────────────────────────
try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False


class MarketData:
    """
    Unified market data interface.
    Uses Kite Connect in live mode, yfinance in paper/test mode.
    """

    def __init__(self):
        self.kite: Optional[KiteConnect] = None
        self._instrument_cache: Dict = {}
        self._ltp_cache: Dict = {}
        self._last_ltp_update: float = 0.0

        if config.TRADING_MODE == "live" and KITE_AVAILABLE:
            self._init_kite()
        else:
            logger.info("Market data: yfinance fallback mode")

    def _init_kite(self) -> None:
        if not config.KITE_API_KEY or not config.KITE_ACCESS_TOKEN:
            logger.error("Kite API key / access token not set in .env")
            return
        try:
            self.kite = KiteConnect(api_key=config.KITE_API_KEY)
            self.kite.set_access_token(config.KITE_ACCESS_TOKEN)
            profile = self.kite.profile()
            logger.info(f"Kite connected: {profile['user_name']}")
        except Exception as e:
            logger.error(f"Kite init failed: {e}")

    # ── OHLCV History ─────────────────────────────────────────────────────────

    def get_ohlcv(
        self,
        symbol: str,
        interval: str = "day",
        days: int = 200,
        exchange: str = "NSE",
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candles.
        interval: minute | 3minute | 5minute | 15minute | 30minute | 60minute | day
        """
        if self.kite:
            return self._kite_ohlcv(symbol, interval, days, exchange)
        return self._yf_ohlcv(symbol, interval, days)

    def _kite_ohlcv(self, symbol: str, interval: str, days: int, exchange: str) -> pd.DataFrame:
        try:
            instruments = self._get_instruments(exchange)
            token = instruments.get(symbol)
            if not token:
                logger.warning(f"Instrument token not found for {symbol}")
                return pd.DataFrame()

            to_date   = datetime.now()
            from_date = to_date - timedelta(days=days)

            candles = self.kite.historical_data(
                instrument_token=token,
                from_date=from_date,
                to_date=to_date,
                interval=interval,
            )
            df = pd.DataFrame(candles)
            df.rename(columns={"date": "datetime"}, inplace=True)
            df.set_index("datetime", inplace=True)
            return df[["open", "high", "low", "close", "volume"]]
        except Exception as e:
            logger.error(f"Kite OHLCV error for {symbol}: {e}")
            return pd.DataFrame()

    def _yf_ohlcv(self, symbol: str, interval: str, days: int) -> pd.DataFrame:
        if not YF_AVAILABLE:
            return self._generate_mock_ohlcv(symbol, days)
        try:
            yf_symbol = f"{symbol}.NS"
            interval_map = {
                "minute": "1m", "5minute": "5m", "15minute": "15m",
                "30minute": "30m", "60minute": "1h", "day": "1d"
            }
            yf_interval = interval_map.get(interval, "1d")
            period = f"{min(days, 730)}d"
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period=period, interval=yf_interval)
            df.columns = [c.lower() for c in df.columns]
            df = df.rename(columns={"stock splits": "splits"})
            return df[["open", "high", "low", "close", "volume"]]
        except Exception as e:
            logger.warning(f"yfinance fallback failed for {symbol}: {e}")
            return self._generate_mock_ohlcv(symbol, days)

    def _generate_mock_ohlcv(self, symbol: str, days: int) -> pd.DataFrame:
        """Deterministic mock data for offline testing."""
        np.random.seed(hash(symbol) % 2**31)
        start_price = 1000 + (hash(symbol) % 5000)
        dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
        returns = np.random.normal(0.0005, 0.015, days)
        closes  = start_price * np.exp(np.cumsum(returns))
        opens   = closes * (1 + np.random.normal(0, 0.005, days))
        highs   = np.maximum(closes, opens) * (1 + abs(np.random.normal(0, 0.008, days)))
        lows    = np.minimum(closes, opens) * (1 - abs(np.random.normal(0, 0.008, days)))
        vols    = np.random.randint(500_000, 5_000_000, days)
        return pd.DataFrame(
            {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
            index=dates,
        )

    # ── Live Quotes ───────────────────────────────────────────────────────────

    def get_ltp(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, float]:
        """Get last traded prices for a list of symbols."""
        if self.kite:
            return self._kite_ltp(symbols, exchange)
        return self._yf_ltp(symbols)

    def _kite_ltp(self, symbols: List[str], exchange: str) -> Dict[str, float]:
        try:
            query = [f"{exchange}:{s}" for s in symbols]
            resp = self.kite.ltp(query)
            return {
                s.split(":")[1]: resp[s]["last_price"]
                for s in resp
            }
        except Exception as e:
            logger.error(f"Kite LTP error: {e}")
            return {}

    def _yf_ltp(self, symbols: List[str]) -> Dict[str, float]:
        result = {}
        for sym in symbols:
            try:
                if YF_AVAILABLE:
                    t = yf.Ticker(f"{sym}.NS")
                    info = t.fast_info
                    result[sym] = float(info.last_price)
                else:
                    result[sym] = 1000.0 + (hash(sym) % 5000)
            except Exception:
                result[sym] = 0.0
        return result

    def get_quote(self, symbol: str, exchange: str = "NSE") -> Dict:
        """Full quote with OHLC, bid/ask, OI."""
        if not self.kite:
            return {}
        try:
            resp = self.kite.quote([f"{exchange}:{symbol}"])
            return resp.get(f"{exchange}:{symbol}", {})
        except Exception as e:
            logger.error(f"Quote error {symbol}: {e}")
            return {}

    # ── Instrument Cache ──────────────────────────────────────────────────────

    def _get_instruments(self, exchange: str = "NSE") -> Dict[str, int]:
        if exchange in self._instrument_cache:
            return self._instrument_cache[exchange]
        try:
            instruments = self.kite.instruments(exchange)
            mapping = {i["tradingsymbol"]: i["instrument_token"] for i in instruments}
            self._instrument_cache[exchange] = mapping
            return mapping
        except Exception as e:
            logger.error(f"Instrument fetch error: {e}")
            return {}

    # ── Options Chain ─────────────────────────────────────────────────────────

    def get_options_chain(self, index: str = "NIFTY", expiry: Optional[str] = None) -> pd.DataFrame:
        """Fetch options chain for index or stock."""
        if not self.kite:
            logger.info("Options chain requires live Kite connection")
            return pd.DataFrame()
        try:
            instruments = self.kite.instruments("NFO")
            df = pd.DataFrame(instruments)
            df = df[df["name"] == index]
            if expiry:
                df = df[df["expiry"].astype(str) == expiry]
            return df
        except Exception as e:
            logger.error(f"Options chain error: {e}")
            return pd.DataFrame()

    # ── Market Status ─────────────────────────────────────────────────────────

    def is_market_open(self) -> bool:
        # config.FORCE_MARKET_OPEN is set from .env at startup via config.py
        if config.FORCE_MARKET_OPEN:
            return True
        now = datetime.now()
        if now.weekday() >= 5:    # Saturday/Sunday
            return False
        open_t  = now.replace(hour=9, minute=15, second=0, microsecond=0)
        close_t = now.replace(hour=15, minute=30, second=0, microsecond=0)
        return open_t <= now <= close_t

    def minutes_to_close(self) -> int:
        if config.FORCE_MARKET_OPEN:
            return 999
        now   = datetime.now()
        close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        delta = (close - now).total_seconds() / 60
        return max(0, int(delta))


# ── Singleton instance ────────────────────────────────────────────────────────
market_data = MarketData()
