"""
strategies/momentum.py — Momentum Strategy
Identifies stocks with strong upward price momentum and high volume.
"""

from typing import Dict, List, Optional
import pandas as pd
from utils.indicators import compute_all_indicators, get_signal_summary, compute_momentum_score
from data.market_data import market_data
from utils.logger import get_logger
import config

logger = get_logger("momentum_strategy")


class MomentumStrategy:
    """
    Momentum Strategy:
    - Stock must be in a clear uptrend (EMA 9 > 21 > 50)
    - RSI between 55–75 (strong but not overbought)
    - MACD histogram positive and growing
    - Volume 1.5x above 20-day average
    - Price above VWAP
    - Above 200 EMA (long-term bullish)
    """

    def __init__(self):
        self.cfg = config.STRATEGY_CONFIG["momentum"]

    def scan(self, watchlist: List[str]) -> List[Dict]:
        """Scan watchlist and return momentum candidates."""
        candidates = []
        for symbol in watchlist:
            try:
                result = self._check_symbol(symbol)
                if result:
                    candidates.append(result)
            except Exception as e:
                logger.error(f"Momentum scan error {symbol}: {e}")
        return sorted(candidates, key=lambda x: x["score"], reverse=True)

    def _check_symbol(self, symbol: str) -> Optional[Dict]:
        df = market_data.get_ohlcv(symbol, "day", days=100)
        if df.empty or len(df) < 50:
            return None

        df  = compute_all_indicators(df)
        sig = get_signal_summary(df)
        score = compute_momentum_score(df)

        if score < self.cfg["min_momentum_score"]:
            return None

        # Entry conditions
        if not (
            sig["ema_trend"] == "bullish" and
            sig["long_term_trend"] == "bullish" and
            55 <= sig["rsi"] <= 75 and
            sig["macd_hist"] > 0 and
            sig["vol_ratio"] >= self.cfg["volume_multiplier"] and
            sig["above_vwap"]
        ):
            return None

        # Calculate entry, SL, target using ATR
        atr   = sig["atr"]
        entry = sig["close"]
        sl    = round(entry - 1.5 * atr, 2)
        target = round(entry + 2.5 * atr, 2)

        return {
            "symbol":    symbol,
            "strategy":  "momentum",
            "action":    "BUY",
            "score":     score,
            "entry":     entry,
            "stop_loss": sl,
            "target":    target,
            "rsi":       sig["rsi"],
            "vol_ratio": sig["vol_ratio"],
            "rationale": (
                f"Strong momentum: RSI {sig['rsi']:.0f}, "
                f"vol {sig['vol_ratio']:.1f}x avg, EMA aligned bullish, "
                f"above VWAP. ATR-based SL={sl}, TGT={target}."
            ),
        }
