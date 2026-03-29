"""
agents/technical_agent.py — Technical Analysis Agent
Scans watchlist for technical setups and generates BUY/SELL signals.
"""

import os
import json
import asyncio
from typing import Dict, List, Optional
import anthropic
from data.market_data import market_data
from data.database import save_signal
from utils.indicators import compute_all_indicators, get_signal_summary, compute_momentum_score
from utils.logger import get_logger, log_signal, log_agent
import config

logger = get_logger("technical_agent")


class TechnicalAgent:
    """
    Runs technical analysis on each symbol in the watchlist.
    Uses TA indicators + Claude AI to generate trade signals.
    """

    def __init__(self):
        self.client  = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY') or config.ANTHROPIC_API_KEY)
        self.signals: Dict[str, Dict] = {}

    # ── Main scan loop ────────────────────────────────────────────────────────

    async def scan(self, watchlist: List[str]) -> Dict[str, Dict]:
        """
        Scan all symbols and return signals dict.
        {symbol: {action, confidence, entry, sl, target, rationale, indicators}}
        """
        log_agent("TechnicalAgent", f"Scanning {len(watchlist)} symbols...")
        results = {}

        for symbol in watchlist:
            try:
                signal = await self.analyse_symbol(symbol)
                if signal:
                    results[symbol] = signal
                    if signal["action"] != "HOLD":
                        log_signal(symbol, signal["action"],
                                   signal["confidence"], signal["rationale"])
                        save_signal(
                            symbol=symbol,
                            action=signal["action"],
                            confidence=signal["confidence"],
                            source="technical_agent",
                            price=signal.get("entry", 0),
                            rsi=signal.get("indicators", {}).get("rsi", 0),
                            macd=signal.get("indicators", {}).get("macd", 0),
                            rationale=signal["rationale"],
                        )
                await asyncio.sleep(0.5)   # avoid rate limits
            except Exception as e:
                logger.error(f"Error analysing {symbol}: {e}")

        self.signals = results
        log_agent("TechnicalAgent", f"Scan complete. {sum(1 for s in results.values() if s['action'] != 'HOLD')} actionable signals")
        return results

    async def analyse_symbol(self, symbol: str) -> Optional[Dict]:
        """Full technical analysis for one symbol."""
        # Fetch OHLCV
        df_daily  = market_data.get_ohlcv(symbol, "day", days=200)
        df_hourly = market_data.get_ohlcv(symbol, "60minute", days=30)

        if df_daily.empty or len(df_daily) < 50:
            logger.warning(f"Insufficient data for {symbol}")
            return None

        # Compute indicators
        df_daily  = compute_all_indicators(df_daily)
        df_hourly = compute_all_indicators(df_hourly) if not df_hourly.empty else df_daily

        daily_sig  = get_signal_summary(df_daily)
        hourly_sig = get_signal_summary(df_hourly)
        momentum   = compute_momentum_score(df_daily)

        # Quick rule-based pre-filter (avoid unnecessary Claude calls)
        pre_filter = self._rule_based_prefilter(daily_sig, momentum)
        if pre_filter == "SKIP":
            return {"action": "HOLD", "confidence": 0.3,
                    "rationale": "No clear setup", "indicators": daily_sig}

        # Claude AI decision
        signal = await self._claude_analyse(symbol, daily_sig, hourly_sig, momentum)
        if signal:
            signal["indicators"] = daily_sig
        return signal

    def _rule_based_prefilter(self, sig: Dict, momentum: float) -> str:
        """
        Fast pre-filter to avoid calling Claude on every symbol.
        Returns 'PROCEED' or 'SKIP'.
        """
        # Strong buy setup
        if (sig["rsi"] > 50 and sig["macd_hist"] > 0 and
                sig["ema_trend"] == "bullish" and sig["vol_ratio"] > 1.2):
            return "PROCEED"

        # Strong sell setup
        if (sig["rsi"] < 50 and sig["macd_hist"] < 0 and
                sig["ema_trend"] == "bearish" and sig["vol_ratio"] > 1.2):
            return "PROCEED"

        # Oversold bounce candidate
        if sig["rsi"] < 35 and sig["bb_position"] == "below_lower":
            return "PROCEED"

        # Overbought reversal candidate
        if sig["rsi"] > 68 and sig["bb_position"] == "above_upper":
            return "PROCEED"

        # MACD crossover
        if sig["macd_cross"] != "none":
            return "PROCEED"

        return "SKIP"

    async def _claude_analyse(
        self, symbol: str, daily: Dict, hourly: Dict, momentum: float
    ) -> Optional[Dict]:
        """Ask Claude to make the final trade decision. Falls back to rule-based if API unavailable."""
        prompt = f"""Analyse {symbol} (NSE) and provide a trade decision.

DAILY INDICATORS:
- Close: ₹{daily['close']}
- RSI(14): {daily['rsi']}
- MACD: {daily['macd']:.4f} | Signal: {daily['macd_signal']:.4f} | Hist: {daily['macd_hist']:.4f}
- MACD Cross: {daily['macd_cross']}
- EMA Trend: {daily['ema_trend']} (9/21/50 EMA alignment)
- Long-term trend: {daily['long_term_trend']} (vs 200 EMA)
- Bollinger Band: {daily['bb_position']} | Width: {daily['bb_width']:.3f}
- ADX: {daily['adx']} (trend strength)
- ATR: ₹{daily['atr']}
- Volume Ratio vs 20d avg: {daily['vol_ratio']:.2f}x
- VWAP: ₹{daily['vwap']} | Above VWAP: {daily['above_vwap']}
- Support: ₹{daily['support']} | Resistance: ₹{daily['resistance']}
- Candlestick: doji={daily['doji']}, hammer={daily['hammer']}, engulfing={daily['engulfing']}

HOURLY INDICATORS:
- RSI: {hourly['rsi']} | MACD Cross: {hourly['macd_cross']}
- EMA Trend: {hourly['ema_trend']} | Above VWAP: {hourly['above_vwap']}

MOMENTUM SCORE: {momentum:.2f}/1.0

Provide BUY/SELL/HOLD decision with entry, SL, target for intraday/swing trade.
Risk params: SL max 2%, R:R minimum 1:1.5.
{config.SYSTEM_PROMPT_TRADE_DECISION}"""

        try:
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            decision = json.loads(raw)
            return {
                "action":     decision.get("action", "HOLD"),
                "confidence": float(decision.get("confidence", 0.5)),
                "entry":      float(decision.get("entry_price", daily["close"])),
                "stop_loss":  float(decision.get("stop_loss", 0)),
                "target":     float(decision.get("target", 0)),
                "quantity":   int(decision.get("quantity", 1)),
                "rationale":  decision.get("rationale", ""),
                "timeframe":  decision.get("timeframe", "intraday"),
            }
        except json.JSONDecodeError as e:
            logger.error(f"Claude JSON parse error for {symbol}: {e}")
            return None
        except Exception as e:
            # 400 = low credits / bad request, 401 = bad key — fall back to rules
            logger.warning(f"Claude unavailable for {symbol} ({e}) — using rule-based signal")
            return self._rule_based_signal(symbol, daily, momentum)

    def _rule_based_signal(self, symbol: str, sig: Dict, momentum: float) -> Dict:
        """
        Pure rule-based signal when Claude API is unavailable.
        Uses RSI + EMA trend + MACD + volume to generate BUY/SELL/HOLD.
        """
        close  = sig["close"]
        atr    = sig["atr"] or close * 0.015
        action = "HOLD"
        confidence = 0.50
        reasons = []

        # BUY conditions
        buy_score = 0
        if sig["rsi"] > 50:                          buy_score += 1; reasons.append(f"RSI {sig['rsi']:.0f}>50")
        if sig["ema_trend"] == "bullish":             buy_score += 2; reasons.append("EMA bullish")
        if sig["macd_hist"] > 0:                     buy_score += 1; reasons.append("MACD+")
        if sig["macd_cross"] == "bullish":            buy_score += 1; reasons.append("MACD cross↑")
        if sig["vol_ratio"] > 1.3:                   buy_score += 1; reasons.append(f"Vol {sig['vol_ratio']:.1f}x")
        if sig["above_vwap"]:                        buy_score += 1; reasons.append("above VWAP")
        if sig["long_term_trend"] == "bullish":      buy_score += 1; reasons.append("above 200EMA")
        if sig["bb_position"] == "below_lower":      buy_score += 1; reasons.append("BB oversold")

        # SELL conditions
        sell_score = 0
        if sig["rsi"] < 50:                          sell_score += 1
        if sig["ema_trend"] == "bearish":            sell_score += 2
        if sig["macd_hist"] < 0:                     sell_score += 1
        if sig["macd_cross"] == "bearish":           sell_score += 1
        if not sig["above_vwap"]:                    sell_score += 1
        if sig["long_term_trend"] == "bearish":      sell_score += 1
        if sig["bb_position"] == "above_upper":      sell_score += 1

        if buy_score >= 4 and buy_score > sell_score:
            action     = "BUY"
            confidence = min(0.50 + buy_score * 0.06, 0.85)
            entry      = close
            stop_loss  = round(entry - 1.5 * atr, 2)
            target     = round(entry + 2.5 * atr, 2)
            rationale  = f"Rule-based BUY: {', '.join(reasons)}"
        elif sell_score >= 4 and sell_score > buy_score:
            action     = "SELL"
            confidence = min(0.50 + sell_score * 0.06, 0.85)
            entry      = close
            stop_loss  = round(entry + 1.5 * atr, 2)
            target     = round(entry - 2.5 * atr, 2)
            rationale  = f"Rule-based SELL: bearish alignment"
        else:
            return {"action": "HOLD", "confidence": 0.40, "entry": close,
                    "stop_loss": 0, "target": 0, "quantity": 0,
                    "rationale": "Rule-based: no clear setup", "timeframe": "intraday"}

        return {
            "action":    action,
            "confidence": round(confidence, 2),
            "entry":     close,
            "stop_loss": stop_loss,
            "target":    target,
            "quantity":  max(1, int(50000 / close)),
            "rationale": rationale,
            "timeframe": "intraday",
        }

    def get_top_signals(self, n: int = 5) -> List[Dict]:
        """Return top N signals sorted by confidence, excluding HOLDs."""
        actionable = [
            {**v, "symbol": k}
            for k, v in self.signals.items()
            if v.get("action") in ("BUY", "SELL")
        ]
        return sorted(actionable, key=lambda x: x["confidence"], reverse=True)[:n]
