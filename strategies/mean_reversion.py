"""
strategies/mean_reversion.py — Mean Reversion Strategy
Identifies oversold/overbought stocks likely to revert to mean.
"""

from typing import Dict, List, Optional
from utils.indicators import compute_all_indicators, get_signal_summary
from data.market_data import market_data
from utils.logger import get_logger
import config

logger = get_logger("mean_reversion_strategy")


class MeanReversionStrategy:
    """
    Mean Reversion Strategy:
    - Price touches or breaks Bollinger Band (lower for buy, upper for sell)
    - RSI oversold (<35 for buy) or overbought (>65 for sell)
    - Price deviation from 20-day SMA > 2%
    - Low ADX (< 25) = no strong trend = range bound
    - High BB width squeeze before expansion
    """

    def __init__(self):
        self.cfg = config.STRATEGY_CONFIG["mean_reversion"]

    def scan(self, watchlist: List[str]) -> List[Dict]:
        candidates = []
        for symbol in watchlist:
            try:
                result = self._check_symbol(symbol)
                if result:
                    candidates.append(result)
            except Exception as e:
                logger.error(f"MeanRev scan error {symbol}: {e}")
        return sorted(candidates, key=lambda x: abs(x.get("deviation", 0)), reverse=True)

    def _check_symbol(self, symbol: str) -> Optional[Dict]:
        df = market_data.get_ohlcv(symbol, "day", days=60)
        if df.empty or len(df) < 25:
            return None

        df  = compute_all_indicators(df)
        sig = get_signal_summary(df)

        close   = sig["close"]
        bb_mid  = df["bb_mid"].iloc[-1]
        deviation = (close - bb_mid) / bb_mid   # % deviation from mid BB

        # BUY setup: oversold bounce
        if (
            sig["rsi"] < 35 and
            sig["bb_position"] == "below_lower" and
            abs(deviation) >= self.cfg["min_deviation_pct"] / 100 and
            sig["adx"] < 28
        ):
            atr    = sig["atr"]
            entry  = close
            sl     = round(entry - 1.2 * atr, 2)
            target = round(bb_mid, 2)   # Target is mean (BB midline)

            return {
                "symbol":    symbol,
                "strategy":  "mean_reversion",
                "action":    "BUY",
                "entry":     entry,
                "stop_loss": sl,
                "target":    target,
                "deviation": round(deviation * 100, 2),
                "rationale": (
                    f"Oversold mean reversion: RSI {sig['rsi']:.0f}, "
                    f"below lower BB, deviation {deviation*100:.1f}% from mean. "
                    f"Target: BB midline ₹{target:,.0f}."
                ),
            }

        # SELL setup: overbought fade
        if (
            sig["rsi"] > 65 and
            sig["bb_position"] == "above_upper" and
            deviation >= self.cfg["min_deviation_pct"] / 100 and
            sig["adx"] < 28
        ):
            atr    = sig["atr"]
            entry  = close
            sl     = round(entry + 1.2 * atr, 2)
            target = round(bb_mid, 2)

            return {
                "symbol":    symbol,
                "strategy":  "mean_reversion",
                "action":    "SELL",
                "entry":     entry,
                "stop_loss": sl,
                "target":    target,
                "deviation": round(deviation * 100, 2),
                "rationale": (
                    f"Overbought fade: RSI {sig['rsi']:.0f}, "
                    f"above upper BB, deviation {deviation*100:.1f}% from mean. "
                    f"Target: BB midline ₹{target:,.0f}."
                ),
            }

        return None
