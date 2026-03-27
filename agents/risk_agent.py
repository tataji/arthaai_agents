"""
agents/risk_agent.py — Risk Management Agent
Enforces all risk rules. No trade executes without Risk Agent approval.
"""

import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from utils.logger import get_logger, log_agent
from utils.notifications import alert_risk_breach
from data.database import get_today_pnl, get_today_trade_count, get_open_trades
import config

logger = get_logger("risk_agent")


@dataclass
class RiskCheck:
    approved: bool
    reason: str
    adjusted_qty: int = 0
    adjusted_sl: float = 0.0


class RiskAgent:
    """
    Enforces all risk rules before any trade is placed.
    Rules:
      1. Daily loss limit — halt all trading if breached
      2. Max position size — cap each trade at N% of capital
      3. Max open positions — don't open more than limit
      4. Max daily trades — circuit breaker
      5. Minutes to close — auto square off / stop new trades
      6. Stop-loss mandatory — every trade must have SL
      7. Risk:Reward minimum — must be at least 1:1.5
    """

    def __init__(self):
        self.trading_halted = False
        self.halt_reason    = ""
        self._capital       = config.CAPITAL

    # ── Main approval gate ────────────────────────────────────────────────────

    def approve_trade(
        self,
        symbol: str,
        action: str,
        price: float,
        qty: int,
        stop_loss: float,
        target: float,
        market_data=None,
    ) -> RiskCheck:
        """
        Central approval gate. Returns RiskCheck with approved=True/False.
        All agents must call this before placing any order.
        """
        # Hard halt
        if self.trading_halted:
            return RiskCheck(False, f"Trading halted: {self.halt_reason}")

        # Market timing
        if market_data and not market_data.is_market_open():
            return RiskCheck(False, "Market is closed")

        mins_left = market_data.minutes_to_close() if market_data else 999
        if mins_left < config.AVOID_LAST_MINUTES and action == "BUY":
            return RiskCheck(False, f"Only {mins_left} min to close — no new buys")

        # Daily loss limit
        today_pnl = get_today_pnl()
        loss_limit = self._capital * config.DAILY_LOSS_LIMIT_PCT
        if today_pnl <= -loss_limit:
            reason = f"Daily loss limit hit: ₹{today_pnl:,.0f} (limit ₹{-loss_limit:,.0f})"
            self._halt(reason)
            return RiskCheck(False, reason)

        # Max daily trades
        trade_count = get_today_trade_count()
        if trade_count >= config.MAX_INTRADAY_TRADES:
            return RiskCheck(False, f"Max daily trades ({config.MAX_INTRADAY_TRADES}) reached")

        # Max open positions
        open_trades = get_open_trades()
        if len(open_trades) >= config.MAX_OPEN_POSITIONS and action == "BUY":
            return RiskCheck(False, f"Max open positions ({config.MAX_OPEN_POSITIONS}) reached")

        # Stop-loss mandatory
        if stop_loss <= 0:
            return RiskCheck(False, "Stop-loss is required for every trade")

        # SL direction check
        if action == "BUY" and stop_loss >= price:
            return RiskCheck(False, f"SL ({stop_loss}) must be below entry ({price}) for BUY")
        if action == "SELL" and stop_loss <= price:
            return RiskCheck(False, f"SL ({stop_loss}) must be above entry ({price}) for SELL")

        # Risk:Reward
        risk   = abs(price - stop_loss)
        reward = abs(target - price) if target > 0 else 0
        if target > 0 and reward < risk * 1.5:
            return RiskCheck(False, f"R:R {reward/risk:.2f} below minimum 1.5")

        # Position sizing
        max_position_value = self._capital * config.MAX_POSITION_PCT
        desired_value = qty * price
        adjusted_qty  = qty

        if desired_value > max_position_value:
            adjusted_qty = int(max_position_value // price)
            if adjusted_qty <= 0:
                return RiskCheck(False, f"Price ₹{price:,.0f} exceeds max position ₹{max_position_value:,.0f}")
            log_agent("RiskAgent", f"Qty reduced {qty}→{adjusted_qty} for {symbol} (position limit)")

        # ATR-based SL check (SL should not be < 0.5% or > 5%)
        sl_pct = abs(price - stop_loss) / price
        if sl_pct < 0.003:
            return RiskCheck(False, f"SL too tight: {sl_pct:.2%}")
        if sl_pct > 0.08:
            return RiskCheck(False, f"SL too wide: {sl_pct:.2%}")

        return RiskCheck(
            approved=True,
            reason="All risk checks passed",
            adjusted_qty=adjusted_qty,
            adjusted_sl=stop_loss,
        )

    # ── Square off ────────────────────────────────────────────────────────────

    def get_squareoff_candidates(self, positions: list, market_data=None) -> list:
        """
        Returns positions that should be squared off:
        - Stop-loss hit
        - Target hit
        - End of day (intraday positions)
        - Risk limit breach
        """
        candidates = []
        mins_left  = market_data.minutes_to_close() if market_data else 999

        for pos in positions:
            ltp = pos.get("ltp", pos["price"])
            if pos["action"] == "BUY":
                if ltp <= pos["stop_loss"]:
                    candidates.append({**pos, "reason": "stop_loss_hit"})
                elif pos.get("target") and ltp >= pos["target"]:
                    candidates.append({**pos, "reason": "target_hit"})
                elif mins_left <= config.AVOID_LAST_MINUTES and pos.get("timeframe") == "intraday":
                    candidates.append({**pos, "reason": "eod_squareoff"})
            elif pos["action"] == "SELL":
                if ltp >= pos["stop_loss"]:
                    candidates.append({**pos, "reason": "stop_loss_hit"})
                elif pos.get("target") and ltp <= pos["target"]:
                    candidates.append({**pos, "reason": "target_hit"})

        return candidates

    # ── Portfolio risk metrics ────────────────────────────────────────────────

    def compute_portfolio_risk(self, positions: list) -> Dict:
        total_exposure   = sum(p["qty"] * p["ltp"] for p in positions)
        total_risk       = sum(abs(p["ltp"] - p["stop_loss"]) * p["qty"]
                               for p in positions if p.get("stop_loss"))
        today_pnl        = get_today_pnl()
        loss_limit       = self._capital * config.DAILY_LOSS_LIMIT_PCT
        pnl_buffer_used  = abs(today_pnl) / loss_limit if today_pnl < 0 else 0

        return {
            "total_exposure": round(total_exposure, 2),
            "total_risk":     round(total_risk, 2),
            "exposure_pct":   round(total_exposure / self._capital * 100, 2),
            "today_pnl":      round(today_pnl, 2),
            "loss_buffer_used": round(pnl_buffer_used * 100, 1),
            "open_positions": len(positions),
            "trading_halted": self.trading_halted,
        }

    def _halt(self, reason: str) -> None:
        self.trading_halted = True
        self.halt_reason    = reason
        alert_risk_breach(reason)
        log_agent("RiskAgent", f"HALT: {reason}", "error")

    def resume_trading(self) -> None:
        """Manually resume trading (e.g., after reviewing the breach)."""
        self.trading_halted = False
        self.halt_reason    = ""
        log_agent("RiskAgent", "Trading manually resumed")
