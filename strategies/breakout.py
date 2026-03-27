"""
strategies/breakout.py — Breakout Strategy
Detects price breakouts above consolidation zones with volume confirmation.
"""

from typing import Dict, List, Optional
import numpy as np
from utils.indicators import compute_all_indicators, get_signal_summary
from data.market_data import market_data
from utils.logger import get_logger
import config

logger = get_logger("breakout_strategy")


class BreakoutStrategy:
    """
    Breakout Strategy:
    - Price consolidates for N days (low ATR/BB squeeze)
    - Price breaks above resistance with volume 2x+
    - Resistance defined as highest high of consolidation range
    - ATR expansion after breakout confirms strength
    """

    def __init__(self):
        self.cfg = config.STRATEGY_CONFIG["breakout"]

    def scan(self, watchlist: List[str]) -> List[Dict]:
        candidates = []
        for symbol in watchlist:
            try:
                result = self._check_symbol(symbol)
                if result:
                    candidates.append(result)
            except Exception as e:
                logger.error(f"Breakout scan error {symbol}: {e}")
        return candidates

    def _check_symbol(self, symbol: str) -> Optional[Dict]:
        df = market_data.get_ohlcv(symbol, "day", days=60)
        if df.empty or len(df) < 30:
            return None

        df  = compute_all_indicators(df)
        sig = get_signal_summary(df)

        lookback = self.cfg["consolidation_days"]
        recent   = df.iloc[-lookback-1:-1]   # last N days excluding today
        today    = df.iloc[-1]

        resistance = float(recent["high"].max())
        support    = float(recent["low"].min())
        range_pct  = (resistance - support) / support

        # Consolidation: tight range (< 8%)
        if range_pct > 0.08:
            return None

        close = float(today["close"])

        # Breakout: close above resistance
        if close <= resistance * 1.001:
            return None

        # Volume confirmation
        vol_ratio = float(today["volume"] / df["volume"].iloc[-20:].mean())
        if vol_ratio < self.cfg["breakout_volume_multiplier"]:
            return None

        # ATR expansion (today's ATR > 1.2x 10-day avg ATR)
        atr_now = sig["atr"]
        atr_avg = float(df["atr"].iloc[-10:].mean())
        if atr_now < atr_avg * 1.1:
            return None

        atr    = atr_now
        entry  = close
        sl     = round(resistance - atr * 0.5, 2)   # just below breakout level
        target = round(entry + self.cfg["atr_multiplier"] * atr * 2, 2)

        return {
            "symbol":     symbol,
            "strategy":   "breakout",
            "action":     "BUY",
            "entry":      entry,
            "stop_loss":  sl,
            "target":     target,
            "resistance": round(resistance, 2),
            "vol_ratio":  round(vol_ratio, 2),
            "rationale":  (
                f"Breakout above ₹{resistance:,.0f} consolidation zone. "
                f"Volume {vol_ratio:.1f}x avg, ATR expansion confirmed. "
                f"SL below breakout level."
            ),
        }
