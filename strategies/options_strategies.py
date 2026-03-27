"""
strategies/options_strategies.py — Options Strategy Selector & Manager
Identifies the best F&O strategy based on market conditions.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from scipy.stats import norm
from utils.logger import get_logger

logger = get_logger("options_strategies")


@dataclass
class OptionLeg:
    action:     str    # BUY | SELL
    option_type: str   # CE | PE
    strike:     float
    premium:    float
    delta:      float = 0.0
    theta:      float = 0.0
    quantity:   int   = 1


@dataclass
class StrategyResult:
    name:           str
    legs:           List[OptionLeg]
    net_premium:    float          # positive = credit, negative = debit
    max_profit:     float
    max_loss:       float          # positive number (magnitude)
    breakevens:     List[float]
    daily_theta:    float
    net_delta:      float
    net_vega:       float
    rationale:      str
    suitability:    str            # "high IV" | "low IV" | "bullish" | "bearish" | "neutral"
    risk_reward:    float


def _bs(S, K, T, r, sigma, opt="CE") -> Dict:
    """Black-Scholes pricing and Greeks."""
    if T <= 0 or sigma <= 0:
        intrinsic = max(S - K, 0) if opt == "CE" else max(K - S, 0)
        return {"price": intrinsic, "delta": 1.0 if S > K and opt == "CE" else 0.0,
                "gamma": 0, "theta": 0, "vega": 0}
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if opt == "CE":
        price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
    else:
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = -norm.cdf(-d1)
    gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
    vega  = S * norm.pdf(d1) * math.sqrt(T) / 100
    theta = -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T)) / 365
    return {
        "price": round(price, 2), "delta": round(delta, 4),
        "gamma": round(gamma, 6), "theta": round(theta, 4),
        "vega":  round(vega, 4),
    }


def _round_strike(price: float, lot_step: float = 50.0) -> float:
    return round(price / lot_step) * lot_step


class OptionsStrategyManager:
    """
    Builds and evaluates options strategies for NIFTY / BANKNIFTY.
    Automatically selects the best strategy given current IV and trend.
    """

    def __init__(self, risk_free_rate: float = 0.065):
        self.r = risk_free_rate

    # ── Strategy Auto-Selector ─────────────────────────────────────────────────

    def recommend_strategy(
        self,
        spot: float,
        iv: float,            # e.g. 0.14 for 14%
        india_vix: float,     # raw VIX value e.g. 13.5
        trend: str,           # "bullish" | "bearish" | "neutral"
        dte: int,             # days to expiry
        lot_size: int = 50,
    ) -> List[StrategyResult]:
        """
        Returns ranked list of strategies best suited to current conditions.
        High VIX → favour premium selling (Iron Condor, Short Straddle)
        Low VIX  → favour buying (Long Straddle, Bull Call Spread)
        Strong trend → directional spreads
        """
        candidates = []

        # Vega preference
        high_iv = india_vix > 15

        if trend == "neutral":
            if high_iv:
                candidates.append(self.iron_condor(spot, iv, dte, lot_size))
                candidates.append(self.short_straddle(spot, iv, dte, lot_size))
                candidates.append(self.short_strangle(spot, iv, dte, lot_size))
            else:
                candidates.append(self.long_straddle(spot, iv, dte, lot_size))
                candidates.append(self.calendar_spread(spot, iv, dte, lot_size))

        elif trend == "bullish":
            candidates.append(self.bull_call_spread(spot, iv, dte, lot_size))
            candidates.append(self.bull_put_spread(spot, iv, dte, lot_size))
            if high_iv:
                candidates.append(self.covered_call(spot, iv, dte, lot_size))

        elif trend == "bearish":
            candidates.append(self.bear_put_spread(spot, iv, dte, lot_size))
            candidates.append(self.bear_call_spread(spot, iv, dte, lot_size))

        # Always include Iron Condor as baseline comparison
        if not any(s.name == "Iron Condor" for s in candidates):
            candidates.append(self.iron_condor(spot, iv, dte, lot_size))

        # Sort by risk/reward
        candidates.sort(key=lambda x: x.risk_reward, reverse=True)
        return candidates

    # ── Individual Strategies ──────────────────────────────────────────────────

    def iron_condor(
        self, spot: float, iv: float, dte: int,
        lot_size: int = 50, body_pct: float = 0.02, wing_pct: float = 0.04
    ) -> StrategyResult:
        T = dte / 365
        sc_k = _round_strike(spot * (1 + body_pct))
        bc_k = _round_strike(spot * (1 + body_pct + wing_pct))
        sp_k = _round_strike(spot * (1 - body_pct))
        bp_k = _round_strike(spot * (1 - body_pct - wing_pct))

        sc = _bs(spot, sc_k, T, self.r, iv, "CE")
        bc = _bs(spot, bc_k, T, self.r, iv, "CE")
        sp = _bs(spot, sp_k, T, self.r, iv, "PE")
        bp = _bs(spot, bp_k, T, self.r, iv, "PE")

        credit = sc["price"] - bc["price"] + sp["price"] - bp["price"]
        net    = credit * lot_size
        wing   = wing_pct * spot
        max_l  = (wing - credit) * lot_size
        theta  = (-sc["theta"] + bc["theta"] - sp["theta"] + bp["theta"]) * lot_size

        return StrategyResult(
            name="Iron Condor",
            legs=[
                OptionLeg("SELL", "CE", sc_k, sc["price"], sc["delta"], sc["theta"]),
                OptionLeg("BUY",  "CE", bc_k, bc["price"], bc["delta"], bc["theta"]),
                OptionLeg("SELL", "PE", sp_k, sp["price"], sp["delta"], sp["theta"]),
                OptionLeg("BUY",  "PE", bp_k, bp["price"], bp["delta"], bp["theta"]),
            ],
            net_premium=round(net, 0),
            max_profit=round(net, 0),
            max_loss=round(max_l, 0),
            breakevens=[round(sp_k - credit, 0), round(sc_k + credit, 0)],
            daily_theta=round(theta, 2),
            net_delta=round(sc["delta"] - bc["delta"] - sp["delta"] + bp["delta"], 4),
            net_vega=round((-sc["vega"] + bc["vega"] - sp["vega"] + bp["vega"]) * lot_size, 2),
            rationale=f"Range-bound premium sell. Profit if spot stays ₹{sp_k:,.0f}–₹{sc_k:,.0f}.",
            suitability="high IV",
            risk_reward=round(net / max_l, 3) if max_l > 0 else 0,
        )

    def bull_call_spread(
        self, spot: float, iv: float, dte: int,
        lot_size: int = 50, otm_pct: float = 0.02
    ) -> StrategyResult:
        T = dte / 365
        buy_k  = _round_strike(spot)
        sell_k = _round_strike(spot * (1 + otm_pct))

        bl = _bs(spot, buy_k,  T, self.r, iv, "CE")
        sl = _bs(spot, sell_k, T, self.r, iv, "CE")

        debit  = (bl["price"] - sl["price"]) * lot_size
        max_p  = (sell_k - buy_k) * lot_size - debit
        be     = buy_k + bl["price"] - sl["price"]

        return StrategyResult(
            name="Bull Call Spread",
            legs=[
                OptionLeg("BUY",  "CE", buy_k,  bl["price"], bl["delta"], bl["theta"]),
                OptionLeg("SELL", "CE", sell_k, sl["price"], sl["delta"], sl["theta"]),
            ],
            net_premium=-round(debit, 0),
            max_profit=round(max_p, 0),
            max_loss=round(debit, 0),
            breakevens=[round(be, 0)],
            daily_theta=round((-bl["theta"] + sl["theta"]) * lot_size, 2),
            net_delta=round((bl["delta"] - sl["delta"]) * lot_size, 2),
            net_vega=round((-bl["vega"] + sl["vega"]) * lot_size, 2),
            rationale=f"Bullish play. Profit if spot above ₹{be:,.0f} at expiry.",
            suitability="bullish",
            risk_reward=round(max_p / debit, 3) if debit > 0 else 0,
        )

    def bear_put_spread(
        self, spot: float, iv: float, dte: int,
        lot_size: int = 50, otm_pct: float = 0.02
    ) -> StrategyResult:
        T = dte / 365
        buy_k  = _round_strike(spot)
        sell_k = _round_strike(spot * (1 - otm_pct))

        bl = _bs(spot, buy_k,  T, self.r, iv, "PE")
        sl = _bs(spot, sell_k, T, self.r, iv, "PE")

        debit  = (bl["price"] - sl["price"]) * lot_size
        max_p  = (buy_k - sell_k) * lot_size - debit
        be     = buy_k - (bl["price"] - sl["price"])

        return StrategyResult(
            name="Bear Put Spread",
            legs=[
                OptionLeg("BUY",  "PE", buy_k,  bl["price"], bl["delta"], bl["theta"]),
                OptionLeg("SELL", "PE", sell_k, sl["price"], sl["delta"], sl["theta"]),
            ],
            net_premium=-round(debit, 0),
            max_profit=round(max_p, 0),
            max_loss=round(debit, 0),
            breakevens=[round(be, 0)],
            daily_theta=round((-bl["theta"] + sl["theta"]) * lot_size, 2),
            net_delta=round((bl["delta"] - sl["delta"]) * lot_size, 2),
            net_vega=round((-bl["vega"] + sl["vega"]) * lot_size, 2),
            rationale=f"Bearish play. Max profit if spot below ₹{sell_k:,.0f}.",
            suitability="bearish",
            risk_reward=round(max_p / debit, 3) if debit > 0 else 0,
        )

    def bear_call_spread(
        self, spot: float, iv: float, dte: int,
        lot_size: int = 50, otm_pct: float = 0.02
    ) -> StrategyResult:
        T = dte / 365
        sell_k = _round_strike(spot * (1 + otm_pct * 0.5))
        buy_k  = _round_strike(spot * (1 + otm_pct * 1.5))

        sl = _bs(spot, sell_k, T, self.r, iv, "CE")
        bl = _bs(spot, buy_k,  T, self.r, iv, "CE")

        credit = (sl["price"] - bl["price"]) * lot_size
        max_l  = (buy_k - sell_k) * lot_size - credit
        be     = sell_k + sl["price"] - bl["price"]

        return StrategyResult(
            name="Bear Call Spread",
            legs=[
                OptionLeg("SELL", "CE", sell_k, sl["price"], sl["delta"], sl["theta"]),
                OptionLeg("BUY",  "CE", buy_k,  bl["price"], bl["delta"], bl["theta"]),
            ],
            net_premium=round(credit, 0),
            max_profit=round(credit, 0),
            max_loss=round(max_l, 0),
            breakevens=[round(be, 0)],
            daily_theta=round((-sl["theta"] + bl["theta"]) * lot_size, 2),
            net_delta=round((-sl["delta"] + bl["delta"]) * lot_size, 2),
            net_vega=round((-sl["vega"] + bl["vega"]) * lot_size, 2),
            rationale=f"Bearish credit spread. Profit if spot stays below ₹{be:,.0f}.",
            suitability="bearish",
            risk_reward=round(credit / max_l, 3) if max_l > 0 else 0,
        )

    def bull_put_spread(
        self, spot: float, iv: float, dte: int,
        lot_size: int = 50, otm_pct: float = 0.02
    ) -> StrategyResult:
        T = dte / 365
        sell_k = _round_strike(spot * (1 - otm_pct * 0.5))
        buy_k  = _round_strike(spot * (1 - otm_pct * 1.5))

        sl = _bs(spot, sell_k, T, self.r, iv, "PE")
        bl = _bs(spot, buy_k,  T, self.r, iv, "PE")

        credit = (sl["price"] - bl["price"]) * lot_size
        max_l  = (sell_k - buy_k) * lot_size - credit
        be     = sell_k - (sl["price"] - bl["price"])

        return StrategyResult(
            name="Bull Put Spread",
            legs=[
                OptionLeg("SELL", "PE", sell_k, sl["price"], sl["delta"], sl["theta"]),
                OptionLeg("BUY",  "PE", buy_k,  bl["price"], bl["delta"], bl["theta"]),
            ],
            net_premium=round(credit, 0),
            max_profit=round(credit, 0),
            max_loss=round(max_l, 0),
            breakevens=[round(be, 0)],
            daily_theta=round((-sl["theta"] + bl["theta"]) * lot_size, 2),
            net_delta=round((-sl["delta"] + bl["delta"]) * lot_size, 2),
            net_vega=round((-sl["vega"] + bl["vega"]) * lot_size, 2),
            rationale=f"Bullish credit spread. Profit if spot stays above ₹{be:,.0f}.",
            suitability="bullish",
            risk_reward=round(credit / max_l, 3) if max_l > 0 else 0,
        )

    def short_straddle(
        self, spot: float, iv: float, dte: int, lot_size: int = 50
    ) -> StrategyResult:
        T = dte / 365
        k = _round_strike(spot)
        c = _bs(spot, k, T, self.r, iv, "CE")
        p = _bs(spot, k, T, self.r, iv, "PE")

        credit = (c["price"] + p["price"]) * lot_size
        be_up  = k + c["price"] + p["price"]
        be_dn  = k - c["price"] - p["price"]
        theta  = (-c["theta"] - p["theta"]) * lot_size

        return StrategyResult(
            name="Short Straddle",
            legs=[
                OptionLeg("SELL", "CE", k, c["price"], c["delta"], c["theta"]),
                OptionLeg("SELL", "PE", k, p["price"], p["delta"], p["theta"]),
            ],
            net_premium=round(credit, 0),
            max_profit=round(credit, 0),
            max_loss=float("inf"),
            breakevens=[round(be_dn, 0), round(be_up, 0)],
            daily_theta=round(theta, 2),
            net_delta=round(c["delta"] - p["delta"], 4),
            net_vega=round((-c["vega"] - p["vega"]) * lot_size, 2),
            rationale=f"High-IV premium sell. Profit if spot stays ₹{be_dn:,.0f}–₹{be_up:,.0f}.",
            suitability="high IV",
            risk_reward=0.5,   # Unlimited loss → normalised conservatively
        )

    def short_strangle(
        self, spot: float, iv: float, dte: int,
        lot_size: int = 50, otm_pct: float = 0.025
    ) -> StrategyResult:
        T = dte / 365
        sell_c = _round_strike(spot * (1 + otm_pct))
        sell_p = _round_strike(spot * (1 - otm_pct))

        c = _bs(spot, sell_c, T, self.r, iv, "CE")
        p = _bs(spot, sell_p, T, self.r, iv, "PE")

        credit = (c["price"] + p["price"]) * lot_size
        be_up  = sell_c + c["price"] + p["price"]
        be_dn  = sell_p - c["price"] - p["price"]

        return StrategyResult(
            name="Short Strangle",
            legs=[
                OptionLeg("SELL", "CE", sell_c, c["price"], c["delta"], c["theta"]),
                OptionLeg("SELL", "PE", sell_p, p["price"], p["delta"], p["theta"]),
            ],
            net_premium=round(credit, 0),
            max_profit=round(credit, 0),
            max_loss=float("inf"),
            breakevens=[round(be_dn, 0), round(be_up, 0)],
            daily_theta=round((-c["theta"] - p["theta"]) * lot_size, 2),
            net_delta=round(c["delta"] - p["delta"], 4),
            net_vega=round((-c["vega"] - p["vega"]) * lot_size, 2),
            rationale=f"Wider range than straddle. Profit ₹{be_dn:,.0f}–₹{be_up:,.0f}.",
            suitability="high IV",
            risk_reward=0.4,
        )

    def long_straddle(
        self, spot: float, iv: float, dte: int, lot_size: int = 50
    ) -> StrategyResult:
        T = dte / 365
        k = _round_strike(spot)
        c = _bs(spot, k, T, self.r, iv, "CE")
        p = _bs(spot, k, T, self.r, iv, "PE")

        debit  = (c["price"] + p["price"]) * lot_size
        be_up  = k + c["price"] + p["price"]
        be_dn  = k - c["price"] - p["price"]

        return StrategyResult(
            name="Long Straddle",
            legs=[
                OptionLeg("BUY", "CE", k, c["price"], c["delta"], c["theta"]),
                OptionLeg("BUY", "PE", k, p["price"], p["delta"], p["theta"]),
            ],
            net_premium=-round(debit, 0),
            max_profit=float("inf"),
            max_loss=round(debit, 0),
            breakevens=[round(be_dn, 0), round(be_up, 0)],
            daily_theta=round((c["theta"] + p["theta"]) * lot_size, 2),
            net_delta=round((c["delta"] + p["delta"]) * lot_size, 2),
            net_vega=round((c["vega"] + p["vega"]) * lot_size, 2),
            rationale=f"Big-move play. Profit if spot moves >₹{c['price']+p['price']:.0f} either way.",
            suitability="low IV",
            risk_reward=2.0,
        )

    def calendar_spread(
        self, spot: float, iv: float, dte: int, lot_size: int = 50
    ) -> StrategyResult:
        """Sell near-week, buy next-week same strike — time decay play."""
        T_near = max(dte / 365, 1 / 365)
        T_far  = (dte + 7) / 365
        k      = _round_strike(spot)

        near = _bs(spot, k, T_near, self.r, iv, "CE")
        far  = _bs(spot, k, T_far,  self.r, iv, iv * 1.05, "CE")

        debit = (far["price"] - near["price"]) * lot_size

        return StrategyResult(
            name="Calendar Spread",
            legs=[
                OptionLeg("SELL", "CE", k, near["price"], near["delta"], near["theta"]),
                OptionLeg("BUY",  "CE", k, far["price"],  far["delta"],  far["theta"]),
            ],
            net_premium=-round(debit, 0),
            max_profit=round(debit * 1.5, 0),
            max_loss=round(debit, 0),
            breakevens=[round(k * 0.98, 0), round(k * 1.02, 0)],
            daily_theta=round((-near["theta"] + far["theta"]) * lot_size, 2),
            net_delta=round((-near["delta"] + far["delta"]) * lot_size, 2),
            net_vega=round((-near["vega"] + far["vega"]) * lot_size, 2),
            rationale="Theta decay play — profit from near expiry decaying faster than far.",
            suitability="neutral",
            risk_reward=1.5,
        )

    def covered_call(
        self, spot: float, iv: float, dte: int, lot_size: int = 50
    ) -> StrategyResult:
        T      = dte / 365
        sell_k = _round_strike(spot * 1.02)
        sl     = _bs(spot, sell_k, T, self.r, iv, "CE")
        credit = sl["price"] * lot_size

        return StrategyResult(
            name="Covered Call",
            legs=[
                OptionLeg("SELL", "CE", sell_k, sl["price"], sl["delta"], sl["theta"]),
            ],
            net_premium=round(credit, 0),
            max_profit=round(credit + (sell_k - spot) * lot_size, 0),
            max_loss=round(spot * lot_size * 0.95, 0),
            breakevens=[round(spot - sl["price"], 0)],
            daily_theta=round(-sl["theta"] * lot_size, 2),
            net_delta=round((1.0 - sl["delta"]) * lot_size, 2),
            net_vega=round(-sl["vega"] * lot_size, 2),
            rationale=f"Existing long + sell OTM CE. Premium income, capped upside at ₹{sell_k:,.0f}.",
            suitability="bullish",
            risk_reward=0.8,
        )
