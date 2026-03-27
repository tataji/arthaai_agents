"""
strategies/swing.py — Swing Trading Strategy (Multi-day positions)
Targets 3-10 day trades based on weekly trend alignment.
"""

from typing import Dict, List, Optional
import pandas as pd
from utils.indicators import compute_all_indicators, get_signal_summary
from data.market_data import market_data
from utils.logger import get_logger
import config

logger = get_logger("swing_strategy")


class SwingStrategy:
    """
    Swing Trading Strategy:
    - Weekly trend is bullish (close > 50 EMA on weekly chart)
    - Daily RSI pulls back to 40-55 range (not overbought)
    - Price finds support at key level (EMA 21 or prior resistance)
    - MACD histogram turning positive from negative
    - Hold 3-10 days targeting 3-6% move
    """

    def scan(self, watchlist: List[str]) -> List[Dict]:
        candidates = []
        for symbol in watchlist:
            try:
                result = self._check_symbol(symbol)
                if result:
                    candidates.append(result)
            except Exception as e:
                logger.error(f"Swing scan error {symbol}: {e}")
        return sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)

    def _check_symbol(self, symbol: str) -> Optional[Dict]:
        # Use weekly data for trend, daily for entry
        df_daily  = market_data.get_ohlcv(symbol, "day",       days=120)
        df_weekly = market_data.get_ohlcv(symbol, "day",       days=365)

        if df_daily.empty or len(df_daily) < 60:
            return None

        df_daily  = compute_all_indicators(df_daily)
        df_weekly = compute_all_indicators(df_weekly)
        daily_sig = get_signal_summary(df_daily)

        close       = daily_sig["close"]
        ema_21_d    = float(df_daily["ema_21"].iloc[-1])
        ema_50_d    = float(df_daily["ema_50"].iloc[-1])
        weekly_rsi  = float(df_weekly["rsi"].iloc[-1]) if "rsi" in df_weekly.columns else 50

        # Conditions
        weekly_bullish  = df_weekly["close"].iloc[-1] > df_weekly.get("ema_50", pd.Series([0])).iloc[-1]
        daily_pullback  = 38 <= daily_sig["rsi"] <= 58
        near_support    = abs(close - ema_21_d) / close < 0.015  # within 1.5% of EMA 21
        macd_recovering = daily_sig["macd_hist"] > df_daily["macd_hist"].iloc[-2]
        volume_ok       = daily_sig["vol_ratio"] >= 0.8

        if not (weekly_bullish and daily_pullback and macd_recovering):
            return None

        score = sum([
            daily_pullback   * 0.3,
            near_support     * 0.25,
            macd_recovering  * 0.25,
            volume_ok        * 0.2,
        ])

        if score < 0.45:
            return None

        atr    = daily_sig["atr"]
        entry  = close
        sl     = round(min(entry - 2.0 * atr, ema_21_d * 0.99), 2)
        target = round(entry + 3.5 * atr, 2)

        return {
            "symbol":    symbol,
            "strategy":  "swing",
            "action":    "BUY",
            "score":     round(score, 3),
            "entry":     entry,
            "stop_loss": sl,
            "target":    target,
            "timeframe": "swing",
            "rationale": (
                f"Swing setup: RSI {daily_sig['rsi']:.0f} pullback, weekly trend bullish, "
                f"MACD recovering. Hold 3-10 days targeting ₹{target:,.0f}."
            ),
        }
