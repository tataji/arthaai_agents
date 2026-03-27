"""
agents/fo_agent.py — F&O Strategy Agent
Manages options strategies: Iron Condor, Bull Call Spread, Straddle, etc.
Calculates Greeks and identifies IV-based opportunities.
"""

import json
import math
from typing import Dict, List, Optional, Tuple
import anthropic
from scipy.stats import norm
from utils.logger import get_logger, log_agent
import config

logger = get_logger("fo_agent")


class FOAgent:
    """F&O Strategy Agent — identifies and manages options positions."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    # ── Black-Scholes Greeks ──────────────────────────────────────────────────

    def black_scholes(
        self,
        S: float,   # Spot price
        K: float,   # Strike price
        T: float,   # Time to expiry (years)
        r: float,   # Risk-free rate (0.065 for India)
        sigma: float,  # Implied volatility
        option_type: str = "CE"
    ) -> Dict:
        """Compute option price and Greeks."""
        if T <= 0 or sigma <= 0:
            return {"price": 0, "delta": 0, "gamma": 0, "theta": 0, "vega": 0}

        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        if option_type == "CE":
            price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
            delta = norm.cdf(d1)
        else:  # PE
            price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            delta = -norm.cdf(-d1)

        gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
        vega  = S * norm.pdf(d1) * math.sqrt(T) / 100    # per 1% IV change
        theta = -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T)) / 365  # per day

        return {
            "price": round(price, 2),
            "delta": round(delta, 4),
            "gamma": round(gamma, 6),
            "theta": round(theta, 4),
            "vega":  round(vega, 4),
            "d1":    round(d1, 4),
            "d2":    round(d2, 4),
        }

    # ── Strategy builders ─────────────────────────────────────────────────────

    def iron_condor(
        self,
        spot: float,
        iv: float,
        days_to_expiry: int,
        lot_size: int = 50,
        wing_width_pct: float = 0.04,
        body_width_pct: float = 0.02,
    ) -> Dict:
        """
        Iron Condor: sell OTM call + put, buy further OTM call + put.
        Best in high-IV, range-bound market.
        """
        T = days_to_expiry / 365
        r = 0.065  # India risk-free rate

        # Strikes
        sell_call = round(spot * (1 + body_width_pct) / 50) * 50
        buy_call  = round(spot * (1 + body_width_pct + wing_width_pct) / 50) * 50
        sell_put  = round(spot * (1 - body_width_pct) / 50) * 50
        buy_put   = round(spot * (1 - body_width_pct - wing_width_pct) / 50) * 50

        # Prices
        sc = self.black_scholes(spot, sell_call, T, r, iv, "CE")
        bc = self.black_scholes(spot, buy_call,  T, r, iv, "CE")
        sp = self.black_scholes(spot, sell_put,  T, r, iv, "PE")
        bp = self.black_scholes(spot, buy_put,   T, r, iv, "PE")

        net_credit    = (sc["price"] - bc["price"] + sp["price"] - bp["price"]) * lot_size
        max_loss      = (wing_width_pct * spot - net_credit / lot_size) * lot_size
        breakeven_up  = sell_call + net_credit / lot_size
        breakeven_down = sell_put - net_credit / lot_size

        return {
            "strategy": "Iron Condor",
            "legs": [
                {"action": "SELL", "type": "CE", "strike": sell_call, "premium": sc["price"]},
                {"action": "BUY",  "type": "CE", "strike": buy_call,  "premium": bc["price"]},
                {"action": "SELL", "type": "PE", "strike": sell_put,  "premium": sp["price"]},
                {"action": "BUY",  "type": "PE", "strike": buy_put,   "premium": bp["price"]},
            ],
            "net_credit":     round(net_credit, 0),
            "max_profit":     round(net_credit, 0),
            "max_loss":       round(max_loss, 0),
            "breakeven_up":   round(breakeven_up, 0),
            "breakeven_down": round(breakeven_down, 0),
            "profit_range":   f"₹{buy_put}–₹{buy_call}",
            "greeks": {
                "net_delta": round(sc["delta"] - bc["delta"] - sp["delta"] + bp["delta"], 4),
                "net_theta": round((-sc["theta"] + bc["theta"] - sp["theta"] + bp["theta"]) * lot_size, 2),
                "net_vega":  round((-sc["vega"]  + bc["vega"]  - sp["vega"]  + bp["vega"])  * lot_size, 2),
            },
        }

    def bull_call_spread(
        self,
        spot: float,
        iv: float,
        days_to_expiry: int,
        lot_size: int = 50,
        otm_pct: float = 0.02,
    ) -> Dict:
        """Bull Call Spread: buy ATM call, sell OTM call."""
        T = days_to_expiry / 365
        r = 0.065

        buy_strike  = round(spot / 50) * 50
        sell_strike = round(spot * (1 + otm_pct) / 50) * 50

        buy_leg  = self.black_scholes(spot, buy_strike,  T, r, iv, "CE")
        sell_leg = self.black_scholes(spot, sell_strike, T, r, iv, "CE")

        net_debit = (buy_leg["price"] - sell_leg["price"]) * lot_size
        max_profit = (sell_strike - buy_strike) * lot_size - net_debit
        breakeven  = buy_strike + (buy_leg["price"] - sell_leg["price"])

        return {
            "strategy": "Bull Call Spread",
            "legs": [
                {"action": "BUY",  "type": "CE", "strike": buy_strike,  "premium": buy_leg["price"]},
                {"action": "SELL", "type": "CE", "strike": sell_strike, "premium": sell_leg["price"]},
            ],
            "net_debit":   round(net_debit, 0),
            "max_profit":  round(max_profit, 0),
            "max_loss":    round(net_debit, 0),
            "breakeven":   round(breakeven, 0),
        }

    def short_straddle(
        self,
        spot: float,
        iv: float,
        days_to_expiry: int,
        lot_size: int = 50,
    ) -> Dict:
        """Short Straddle: sell ATM call + ATM put. High IV play."""
        T = days_to_expiry / 365
        r = 0.065

        strike   = round(spot / 50) * 50
        call_leg = self.black_scholes(spot, strike, T, r, iv, "CE")
        put_leg  = self.black_scholes(spot, strike, T, r, iv, "PE")

        credit       = (call_leg["price"] + put_leg["price"]) * lot_size
        breakeven_up = strike + call_leg["price"] + put_leg["price"]
        breakeven_dn = strike - call_leg["price"] - put_leg["price"]

        return {
            "strategy":      "Short Straddle",
            "legs": [
                {"action": "SELL", "type": "CE", "strike": strike, "premium": call_leg["price"]},
                {"action": "SELL", "type": "PE", "strike": strike, "premium": put_leg["price"]},
            ],
            "net_credit":    round(credit, 0),
            "max_profit":    round(credit, 0),
            "breakeven_up":  round(breakeven_up, 0),
            "breakeven_down": round(breakeven_dn, 0),
            "warning":       "Unlimited risk above/below breakevens. Use stop-loss at 2x premium.",
        }

    # ── Claude F&O advisory ───────────────────────────────────────────────────

    def ask_claude_fo_strategy(
        self, index: str, spot: float, vix: float, days_to_expiry: int,
        market_trend: str
    ) -> str:
        """Ask Claude to recommend an F&O strategy given market conditions."""
        try:
            prompt = (
                f"Index: {index} | Spot: ₹{spot:,.0f} | INDIA VIX: {vix} | "
                f"Days to expiry: {days_to_expiry} | Market trend: {market_trend}\n\n"
                f"Recommend the best F&O strategy. Consider: IV level (VIX), trend direction, "
                f"theta decay, risk appetite. Provide: strategy name, setup, breakevens, "
                f"max profit/loss, and key risks. Use Indian lot sizes (NIFTY=50, BANKNIFTY=15)."
            )
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=400,
                system=config.SYSTEM_PROMPT_TRADING,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            return f"F&O advisory unavailable: {e}"
