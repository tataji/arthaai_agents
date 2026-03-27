"""
agents/news_agent.py — News & Sentiment Analysis Agent
Scrapes financial news and uses Claude to extract trading signals.
"""

import os
import json
import asyncio
import aiohttp
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import anthropic
from utils.logger import get_logger, log_agent
from data.database import save_signal
import config

logger = get_logger("news_agent")

NEWS_SOURCES = [
    {
        "name": "Moneycontrol",
        "url": "https://www.moneycontrol.com/news/business/markets/",
        "article_selector": "li.clearfix h2 a",
    },
    {
        "name": "Economic Times Markets",
        "url": "https://economictimes.indiatimes.com/markets/stocks/news",
        "article_selector": "div.eachStory h3 a",
    },
    {
        "name": "LiveMint",
        "url": "https://www.livemint.com/market/stock-market-news",
        "article_selector": "h2.headline a",
    },
]


class NewsAgent:
    """
    Fetches financial news headlines from Indian financial portals,
    uses Claude to extract sentiment and affected stocks, and generates
    news-based trading signals.
    """

    def __init__(self):
        self.client   = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY') or config.ANTHROPIC_API_KEY)
        self.headlines: List[str] = []
        self.signals:   Dict[str, Dict] = {}

    async def run(self) -> Dict[str, Dict]:
        """Main run: fetch news → analyse → return signals."""
        log_agent("NewsAgent", "Fetching news...")
        self.headlines = await self._fetch_headlines()
        log_agent("NewsAgent", f"Fetched {len(self.headlines)} headlines")

        if not self.headlines:
            return {}

        self.signals = await self._analyse_headlines(self.headlines)
        return self.signals

    # ── Headline fetching ─────────────────────────────────────────────────────

    async def _fetch_headlines(self) -> List[str]:
        """Scrape headlines from multiple sources."""
        all_headlines = []
        timeout = aiohttp.ClientTimeout(total=15)
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ArthAI/1.0)"}

        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            for source in NEWS_SOURCES:
                try:
                    async with session.get(source["url"]) as resp:
                        html = await resp.text()
                    soup = BeautifulSoup(html, "lxml")
                    items = soup.select(source["article_selector"])
                    headlines = [el.get_text(strip=True) for el in items[:10]]
                    all_headlines.extend(headlines)
                    log_agent("NewsAgent", f"{source['name']}: {len(headlines)} headlines")
                except Exception as e:
                    logger.warning(f"Failed to fetch {source['name']}: {e}")
                await asyncio.sleep(1)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for h in all_headlines:
            if h and h not in seen:
                seen.add(h)
                unique.append(h)
        return unique[:30]   # Top 30 unique headlines

    # ── Claude analysis ───────────────────────────────────────────────────────

    async def _analyse_headlines(self, headlines: List[str]) -> Dict[str, Dict]:
        """
        Send headlines to Claude for bulk sentiment analysis.
        Returns per-stock signals derived from news.
        """
        headlines_text = "\n".join(f"{i+1}. {h}" for i, h in enumerate(headlines))

        prompt = f"""Analyse these Indian financial market headlines and extract trading signals.

HEADLINES:
{headlines_text}

For each headline that has a clear bullish or bearish implication for specific stocks or sectors,
extract a signal. Return a JSON array of signals:
[
  {{
    "headline_index": 1,
    "symbols": ["RELIANCE", "ONGC"],
    "sector": "Energy",
    "sentiment": "bullish",
    "confidence": 0.75,
    "summary": "one-line explanation",
    "trading_action": "Consider BUY on RELIANCE — beat estimates"
  }},
  ...
]

Rules:
- Only include actionable signals (confidence >= 0.55)
- Use exact NSE symbols (RELIANCE not Reliance Industries)
- For index news, use "NIFTY" or "BANKNIFTY" as symbol
- Return only valid JSON array, no other text."""

        try:
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=1000,
                system=config.SYSTEM_PROMPT_NEWS,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()

            # Handle both array and object responses
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                parsed = [parsed]

            # Build per-symbol signal dict
            signals = {}
            for item in parsed:
                for sym in item.get("symbols", []):
                    action = "BUY" if item["sentiment"] == "bullish" else \
                             "SELL" if item["sentiment"] == "bearish" else "HOLD"
                    signals[sym] = {
                        "action":    action,
                        "confidence": item.get("confidence", 0.5),
                        "summary":   item.get("summary", ""),
                        "headline":  headlines[item.get("headline_index", 1) - 1],
                        "rationale": item.get("trading_action", ""),
                    }
                    if action != "HOLD":
                        save_signal(
                            symbol=sym, action=action,
                            confidence=item.get("confidence", 0.5),
                            source="news_agent",
                            rationale=item.get("trading_action", ""),
                        )
            log_agent("NewsAgent", f"Extracted signals for: {list(signals.keys())}")
            return signals

        except json.JSONDecodeError as e:
            logger.error(f"News JSON parse error: {e}")
            return {}
        except Exception as e:
            logger.error(f"News analysis error: {e}")
            return {}

    # ── Quick single-headline analysis ───────────────────────────────────────

    def analyse_headline_quick(self, headline: str) -> Dict:
        """Synchronous quick analysis for a single headline."""
        try:
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=200,
                system=config.SYSTEM_PROMPT_NEWS,
                messages=[{"role": "user", "content": f"Analyse: {headline}"}],
            )
            raw = response.content[0].text.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(raw)
        except Exception as e:
            return {"sentiment": "neutral", "confidence": 0.0, "affected_stocks": []}
