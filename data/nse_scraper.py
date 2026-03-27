"""
data/nse_scraper.py — NSE public data scraper
Fetches FII/DII activity, circuit breakers, corporate actions, OI data.
All from NSE's public API (no auth required).
"""

import requests
import pandas as pd
from typing import Dict, List, Optional
from utils.logger import get_logger

logger = get_logger("nse_scraper")

NSE_BASE = "https://www.nseindia.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com",
}


class NSEScraper:
    """Scrapes NSE public data endpoints."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._init_cookies()

    def _init_cookies(self):
        """NSE requires cookies — visit homepage first."""
        try:
            self.session.get(NSE_BASE, timeout=10)
        except Exception as e:
            logger.warning(f"NSE cookie init failed: {e}")

    def _get(self, endpoint: str) -> Optional[Dict]:
        try:
            url  = f"{NSE_BASE}{endpoint}"
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"NSE {endpoint}: HTTP {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"NSE fetch error {endpoint}: {e}")
            return None

    # ── Market data ───────────────────────────────────────────────────────────

    def get_market_status(self) -> Dict:
        """NSE market status."""
        data = self._get("/api/marketStatus")
        return data or {}

    def get_indices(self) -> List[Dict]:
        """All NSE indices with current values."""
        data = self._get("/api/allIndices")
        return data.get("data", []) if data else []

    def get_nifty50_constituents(self) -> pd.DataFrame:
        """NIFTY 50 constituents with current data."""
        data = self._get("/api/equity-stockIndices?index=NIFTY%2050")
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data.get("data", []))

    # ── FII/DII Activity ──────────────────────────────────────────────────────

    def get_fii_dii_activity(self) -> Dict:
        """
        FII/DII buy-sell data.
        Returns today's provisional figures.
        """
        data = self._get("/api/fiidiiTradeReact")
        return data or {}

    def get_fii_derivatives(self) -> Dict:
        """FII derivatives (F&O) participation data."""
        data = self._get("/api/fiiDiiParticipation")
        return data or {}

    # ── Options data ──────────────────────────────────────────────────────────

    def get_option_chain(self, symbol: str = "NIFTY") -> Dict:
        """
        Full options chain for index or stock.
        symbol: NIFTY, BANKNIFTY, or NSE stock symbol
        """
        endpoint = f"/api/option-chain-indices?symbol={symbol}" \
            if symbol in ("NIFTY", "BANKNIFTY", "FINNIFTY") \
            else f"/api/option-chain-equities?symbol={symbol}"
        return self._get(endpoint) or {}

    def get_max_pain(self, symbol: str = "NIFTY") -> Optional[float]:
        """
        Calculate Max Pain (strike where option buyers lose most).
        Max pain = strike with highest combined OI (calls + puts).
        """
        chain_data = self.get_option_chain(symbol)
        if not chain_data:
            return None
        try:
            records = chain_data["records"]["data"]
            pain_scores = {}
            for record in records:
                strike = record["strikePrice"]
                ce_oi  = record.get("CE", {}).get("openInterest", 0)
                pe_oi  = record.get("PE", {}).get("openInterest", 0)
                pain_scores[strike] = ce_oi + pe_oi
            return max(pain_scores, key=pain_scores.get)
        except Exception as e:
            logger.error(f"Max pain calculation error: {e}")
            return None

    def get_pcr(self, symbol: str = "NIFTY") -> Optional[float]:
        """
        Put-Call Ratio (PCR) — gauge of market sentiment.
        PCR > 1.2: bearish (too many puts = contrarian bullish signal)
        PCR < 0.7: bullish (too many calls = contrarian bearish signal)
        """
        chain_data = self.get_option_chain(symbol)
        if not chain_data:
            return None
        try:
            records   = chain_data["records"]["data"]
            total_ce  = sum(r.get("CE", {}).get("openInterest", 0) for r in records)
            total_pe  = sum(r.get("PE", {}).get("openInterest", 0) for r in records)
            return round(total_pe / total_ce, 3) if total_ce > 0 else None
        except Exception as e:
            logger.error(f"PCR error: {e}")
            return None

    # ── Circuit breakers ──────────────────────────────────────────────────────

    def get_circuit_breakers(self) -> Dict:
        """Stocks hitting upper/lower circuit today."""
        data = self._get("/api/live-analysis-data?index=securities in F%26O")
        return data or {}

    # ── Corporate actions ─────────────────────────────────────────────────────

    def get_corporate_actions(self, symbol: str) -> List[Dict]:
        """Upcoming corporate actions (dividends, bonuses, splits) for a stock."""
        data = self._get(f"/api/corporateInfo?symbol={symbol}")
        if not data:
            return []
        return data.get("corporate", {}).get("corpInfo", [])

    def get_board_meetings(self) -> List[Dict]:
        """Upcoming board meetings (results announcements)."""
        data = self._get("/api/event-calendar")
        return data or []


# Singleton
nse_scraper = NSEScraper()
