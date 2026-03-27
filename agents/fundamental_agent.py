"""
agents/fundamental_agent.py — Fundamental Screener Agent
Fetches fundamental data and uses Claude to flag strong/weak stocks.
"""

import json
from typing import Dict, List, Optional
import anthropic
from utils.logger import get_logger, log_agent
import config

logger = get_logger("fundamental_agent")

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False


class FundamentalAgent:
    """
    Screens stocks on fundamental criteria:
    - P/E ratio vs sector average
    - Revenue & profit growth (QoQ, YoY)
    - Debt-to-equity
    - Return on Equity (ROE)
    - Promoter shareholding & pledging
    - FII/DII activity
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.fundamentals: Dict[str, Dict] = {}

    def fetch_fundamentals(self, symbol: str) -> Dict:
        """Fetch fundamental data for a symbol via yfinance."""
        if not YF_AVAILABLE:
            return self._mock_fundamentals(symbol)
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            info   = ticker.info
            return {
                "symbol":            symbol,
                "pe_ratio":          info.get("trailingPE"),
                "forward_pe":        info.get("forwardPE"),
                "pb_ratio":          info.get("priceToBook"),
                "ev_ebitda":         info.get("enterpriseToEbitda"),
                "roe":               info.get("returnOnEquity"),
                "roce":              info.get("returnOnCapitalEmployed"),
                "debt_equity":       info.get("debtToEquity"),
                "revenue_growth":    info.get("revenueGrowth"),
                "earnings_growth":   info.get("earningsGrowth"),
                "profit_margins":    info.get("profitMargins"),
                "current_ratio":     info.get("currentRatio"),
                "market_cap":        info.get("marketCap"),
                "52w_high":          info.get("fiftyTwoWeekHigh"),
                "52w_low":           info.get("fiftyTwoWeekLow"),
                "dividend_yield":    info.get("dividendYield"),
                "sector":            info.get("sector"),
                "industry":          info.get("industry"),
                "analyst_rating":    info.get("recommendationKey"),
                "target_mean_price": info.get("targetMeanPrice"),
                "eps_ttm":           info.get("trailingEps"),
                "book_value":        info.get("bookValue"),
            }
        except Exception as e:
            logger.warning(f"Fundamental fetch error for {symbol}: {e}")
            return self._mock_fundamentals(symbol)

    def _mock_fundamentals(self, symbol: str) -> Dict:
        """Mock fundamentals for testing."""
        import random
        random.seed(hash(symbol) % 2**31)
        return {
            "symbol":         symbol,
            "pe_ratio":       round(random.uniform(10, 45), 1),
            "pb_ratio":       round(random.uniform(1, 8), 2),
            "roe":            round(random.uniform(0.08, 0.35), 3),
            "debt_equity":    round(random.uniform(0.1, 2.0), 2),
            "revenue_growth": round(random.uniform(-0.05, 0.25), 3),
            "earnings_growth": round(random.uniform(-0.10, 0.30), 3),
            "profit_margins": round(random.uniform(0.05, 0.30), 3),
            "sector":         "Technology",
            "analyst_rating": random.choice(["buy", "hold", "sell"]),
        }

    def screen_watchlist(self, watchlist: List[str]) -> Dict[str, Dict]:
        """
        Run fundamental screening on watchlist.
        Returns dict of symbol → fundamental score & rating.
        """
        log_agent("FundamentalAgent", f"Screening {len(watchlist)} symbols...")
        results = {}
        for symbol in watchlist:
            data = self.fetch_fundamentals(symbol)
            score = self._score_fundamentals(data)
            data["fundamental_score"] = score
            data["fundamental_rating"] = (
                "STRONG" if score >= 0.7 else
                "MODERATE" if score >= 0.45 else "WEAK"
            )
            results[symbol] = data
        self.fundamentals = results
        log_agent("FundamentalAgent", "Fundamental screening complete")
        return results

    def _score_fundamentals(self, data: Dict) -> float:
        """Compute 0-1 fundamental quality score."""
        score = 0.0
        weight = 0.0

        # ROE > 15% is good (weight 3)
        roe = data.get("roe") or 0
        if roe > 0.20:    score += 3
        elif roe > 0.15:  score += 2
        elif roe > 0.10:  score += 1
        weight += 3

        # PE reasonable — sector-dependent, use 20 as rough benchmark (weight 2)
        pe = data.get("pe_ratio") or 999
        if 8 < pe < 20:   score += 2
        elif pe < 30:     score += 1
        weight += 2

        # Revenue growth positive (weight 2)
        rev = data.get("revenue_growth") or 0
        if rev > 0.15:    score += 2
        elif rev > 0.05:  score += 1
        weight += 2

        # Earnings growth (weight 2)
        eg = data.get("earnings_growth") or 0
        if eg > 0.20:     score += 2
        elif eg > 0.05:   score += 1
        weight += 2

        # Debt/equity < 1 (weight 2)
        de = data.get("debt_equity") or 0
        if de < 0.3:      score += 2
        elif de < 1.0:    score += 1
        weight += 2

        # Analyst rating (weight 1)
        rating = data.get("analyst_rating", "").lower()
        if "buy" in rating or "strong" in rating:
            score += 1
        weight += 1

        return round(score / weight, 3)

    def ask_claude_fundamental(self, symbol: str, data: Dict) -> str:
        """Ask Claude for a narrative fundamental assessment."""
        try:
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=300,
                system=config.SYSTEM_PROMPT_TRADING,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Give a brief fundamental assessment of {symbol} based on this data:\n"
                        f"{json.dumps({k: v for k, v in data.items() if v is not None}, indent=2)}\n"
                        f"Focus on: valuation (PE/PB), growth quality, balance sheet strength, "
                        f"and whether it's suitable for a swing/positional trade."
                    )
                }],
            )
            return response.content[0].text.strip()
        except Exception as e:
            return f"Fundamental analysis unavailable: {e}"
