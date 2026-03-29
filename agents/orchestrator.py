"""
agents/orchestrator.py — Master Orchestrator Agent
Coordinates all sub-agents, aggregates signals, and places trades.
This is the brain of the system.
"""

import asyncio
import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import anthropic

from agents.technical_agent import TechnicalAgent
from agents.news_agent import NewsAgent
from agents.fundamental_agent import FundamentalAgent
from agents.risk_agent import RiskAgent
from agents.fo_agent import FOAgent
from data.market_data import market_data
from data.database import (
    init_db, save_trade, get_open_trades, get_today_pnl,
    get_today_trade_count, log_agent_event
)
from utils.logger import get_logger, log_agent, log_trade, print_portfolio_table
from utils.notifications import alert_trade, alert_daily_summary
import config

logger = get_logger("orchestrator")


class Orchestrator:
    """
    Master agent. Runs on a configurable interval.
    Cycle:
      1. Market status check
      2. Run sub-agents (async)
      3. Aggregate signals (technical + news + fundamental)
      4. Risk check
      5. Execute trades (paper or live)
      6. Monitor open positions (SL/TP)
      7. End-of-day summary
    """

    def __init__(self):
        self.client      = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY') or config.ANTHROPIC_API_KEY)
        self.technical   = TechnicalAgent()
        self.news        = NewsAgent()
        self.fundamental = FundamentalAgent()
        self.risk        = RiskAgent()
        self.fo          = FOAgent()

        self.watchlist   = config.DEFAULT_WATCHLIST
        self.positions: List[Dict] = []   # In-memory position tracker
        self.running     = False
        self._last_fundamental_run = 0.0
        self._last_news_run        = 0.0

        init_db()
        log_agent("Orchestrator", f"Initialised in {config.TRADING_MODE.upper()} mode")

    # ── Main loop ─────────────────────────────────────────────────────────────

    async def run_forever(self):
        """Infinite loop — runs every AGENT_INTERVALS['orchestrator'] seconds."""
        self.running = True
        log_agent("Orchestrator", "Starting main loop...")

        while self.running:
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error(f"Cycle error: {e}", exc_info=True)
                log_agent_event("orchestrator", f"Cycle error: {e}", "error")

            sleep_sec = config.AGENT_INTERVALS["orchestrator"]
            log_agent("Orchestrator", f"Sleeping {sleep_sec}s until next cycle...")
            await asyncio.sleep(sleep_sec)

    async def run_cycle(self):
        """One complete orchestration cycle."""
        now = datetime.now()
        log_agent("Orchestrator", f"=== Cycle start: {now.strftime('%H:%M:%S')} ===")

        # 1. Market check
        if not market_data.is_market_open():
            log_agent("Orchestrator", "Market closed — skipping trade cycle")
            if now.hour == 15 and now.minute >= 35:
                await self._end_of_day()
            return

        mins_left = market_data.minutes_to_close()
        log_agent("Orchestrator", f"{mins_left} minutes to market close")

        # 2. Run sub-agents (news + fundamental run less frequently)
        tasks = [self._run_technical()]
        if time.time() - self._last_news_run > config.AGENT_INTERVALS["news"]:
            tasks.append(self._run_news())
        if time.time() - self._last_fundamental_run > config.AGENT_INTERVALS["fundamental"]:
            tasks.append(self._run_fundamental())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        tech_signals = results[0] if not isinstance(results[0], Exception) else {}
        news_signals = self.news.signals
        fund_data    = self.fundamental.fundamentals

        # 3. Aggregate and rank opportunities
        opportunities = self._aggregate_signals(tech_signals, news_signals, fund_data)
        log_agent("Orchestrator", f"{len(opportunities)} opportunities found")

        # 4. Claude meta-decision
        if opportunities:
            trades_to_place = await self._claude_meta_decision(opportunities)
            # 5. Execute
            for trade in trades_to_place:
                await self._execute_trade(trade)

        # 6. Monitor existing positions
        await self._monitor_positions()

        # 7. Portfolio summary
        pnl = get_today_pnl()
        trades = get_today_trade_count()
        log_agent("Orchestrator", f"Today: {trades} trades | P&L: ₹{pnl:+,.0f}")

    # ── Sub-agent runners ─────────────────────────────────────────────────────

    async def _run_technical(self) -> Dict:
        return await self.technical.scan(self.watchlist)

    async def _run_news(self):
        signals = await self.news.run()
        self._last_news_run = time.time()
        return signals

    async def _run_fundamental(self):
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self.fundamental.screen_watchlist, self.watchlist
        )
        self._last_fundamental_run = time.time()
        return result

    # ── Signal aggregation ────────────────────────────────────────────────────

    def _aggregate_signals(
        self,
        tech: Dict,
        news: Dict,
        fund: Dict,
    ) -> List[Dict]:
        """
        Combine signals from all agents with weighted confidence.
        Weights: Technical=50%, News=30%, Fundamental=20%
        """
        all_symbols = set(list(tech.keys()) + list(news.keys()))
        opportunities = []

        for symbol in all_symbols:
            t = tech.get(symbol, {})
            n = news.get(symbol, {})
            f = fund.get(symbol, {})

            if t.get("action") == "HOLD" and not n:
                continue

            # Weighted confidence
            t_conf = t.get("confidence", 0) if t.get("action") not in ("HOLD", None) else 0
            n_conf = n.get("confidence", 0) if n.get("action") not in ("HOLD", None) else 0
            f_score = f.get("fundamental_score", 0.5) if f else 0.5

            # Alignment bonus: all agents agree
            actions = [a for a in [t.get("action"), n.get("action")] if a and a != "HOLD"]
            aligned = len(set(actions)) == 1 and len(actions) >= 2
            alignment_bonus = 0.1 if aligned else 0

            combined_conf = (t_conf * 0.50 + n_conf * 0.30 + f_score * 0.20) + alignment_bonus
            action = t.get("action") or n.get("action") or "HOLD"

            if combined_conf < 0.55 or action == "HOLD":
                continue

            opportunities.append({
                "symbol":      symbol,
                "action":      action,
                "confidence":  round(combined_conf, 3),
                "entry":       t.get("entry", 0),
                "stop_loss":   t.get("stop_loss", 0),
                "target":      t.get("target", 0),
                "quantity":    t.get("quantity", 1),
                "rationale":   (t.get("rationale", "") + " | " + n.get("summary", "")).strip(" |"),
                "timeframe":   t.get("timeframe", "intraday"),
                "tech_signal": t,
                "news_signal": n,
                "fund_score":  f_score,
            })

        return sorted(opportunities, key=lambda x: x["confidence"], reverse=True)[:5]

    # ── Claude meta-decision ──────────────────────────────────────────────────

    async def _claude_meta_decision(self, opportunities: List[Dict]) -> List[Dict]:
        """
        Send top opportunities to Claude for final prioritisation.
        Claude picks which ones to actually trade given portfolio state.
        """
        open_count  = len(get_open_trades())
        today_pnl   = get_today_pnl()
        risk_metrics = self.risk.compute_portfolio_risk(self.positions)

        prompt = f"""You are the master trading orchestrator for ArthAI.
Current portfolio state:
- Open positions: {open_count}/{config.MAX_OPEN_POSITIONS}
- Today P&L: ₹{today_pnl:+,.0f}
- Capital deployed: {risk_metrics.get('exposure_pct', 0):.1f}%
- Loss buffer used: {risk_metrics.get('loss_buffer_used', 0):.1f}%
- Trading mode: {config.TRADING_MODE.upper()}

Top signal opportunities:
{json.dumps([{k: v for k, v in opp.items() if k not in ('tech_signal', 'news_signal')} for opp in opportunities], indent=2)}

Select which trades to execute (max 3). Be conservative if P&L is negative or exposure is high.
Return JSON array of approved symbols: ["SYMBOL1", "SYMBOL2"] or empty [] if none."""

        try:
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip().replace("```json","").replace("```","").strip()
            approved = json.loads(raw)
            if not isinstance(approved, list):
                approved = []
            log_agent("Orchestrator", f"Claude approved: {approved}")
            return [o for o in opportunities if o["symbol"] in approved]
        except Exception as e:
            err = str(e)
            if "credit balance" in err or "400" in err or "401" in err:
                logger.warning("Claude unavailable (billing/auth) — using top-2 rule-based signals")
            else:
                logger.error(f"Meta-decision error: {e}")
            return opportunities[:2]

    # ── Trade execution ───────────────────────────────────────────────────────

    async def _execute_trade(self, trade: Dict) -> bool:
        symbol = trade["symbol"]
        action = trade["action"]

        # Get live LTP
        prices = market_data.get_ltp([symbol])
        ltp    = prices.get(symbol, trade.get("entry", 0))
        if not ltp:
            log_agent("Orchestrator", f"Cannot get LTP for {symbol}", "warn")
            return False

        # Update entry to current price for market orders
        entry = ltp
        sl    = trade["stop_loss"]
        tgt   = trade["target"]
        qty   = trade["quantity"]

        # Adjust SL/TP if entry shifted
        if sl > 0 and tgt > 0:
            sl_pct  = abs(trade["entry"] - sl) / trade["entry"] if trade["entry"] else config.DEFAULT_SL_PCT
            tgt_pct = abs(tgt - trade["entry"]) / trade["entry"] if trade["entry"] else config.DEFAULT_TARGET_PCT
            if action == "BUY":
                sl  = round(entry * (1 - sl_pct), 2)
                tgt = round(entry * (1 + tgt_pct), 2)
            else:
                sl  = round(entry * (1 + sl_pct), 2)
                tgt = round(entry * (1 - tgt_pct), 2)

        # Risk check
        risk_check = self.risk.approve_trade(
            symbol, action, entry, qty, sl, tgt, market_data
        )
        if not risk_check.approved:
            log_agent("Orchestrator", f"Trade rejected for {symbol}: {risk_check.reason}", "warn")
            return False

        qty = risk_check.adjusted_qty

        # Place order
        order_id = ""
        if config.TRADING_MODE == "live" and market_data.kite:
            order_id = self._place_kite_order(symbol, action, qty)
        else:
            order_id = f"PAPER-{int(time.time())}"

        # Save to DB
        save_trade(
            symbol=symbol, action=action, qty=qty, price=entry,
            stop_loss=sl, target=tgt,
            strategy=trade.get("timeframe", "intraday"),
            rationale=trade.get("rationale", ""),
            order_id=order_id,
        )

        # Update in-memory positions
        self.positions.append({
            "symbol": symbol, "action": action, "qty": qty,
            "price": entry, "ltp": entry,
            "stop_loss": sl, "target": tgt,
            "timeframe": trade.get("timeframe", "intraday"),
        })

        log_trade(action, symbol, qty, entry, mode=config.TRADING_MODE)
        alert_trade(action, symbol, qty, entry, sl, tgt, trade.get("rationale", ""))
        log_agent_event("orchestrator", f"{action} {qty}×{symbol} @ ₹{entry:,.2f} | SL={sl} TGT={tgt}")
        return True

    def _place_kite_order(self, symbol: str, action: str, qty: int) -> str:
        """Place order via Zerodha Kite Connect."""
        try:
            from kiteconnect import KiteConnect
            order_id = market_data.kite.place_order(
                tradingsymbol=symbol,
                exchange="NSE",
                transaction_type="BUY" if action == "BUY" else "SELL",
                quantity=qty,
                product="MIS",       # Intraday (MIS) or CNC for delivery
                order_type="MARKET",
            )
            log_agent("Orchestrator", f"Kite order placed: {order_id}")
            return str(order_id)
        except Exception as e:
            logger.error(f"Kite order error: {e}")
            return ""

    # ── Position monitoring ───────────────────────────────────────────────────

    async def _monitor_positions(self):
        """Check open positions for SL/TP hits."""
        if not self.positions:
            return

        symbols = [p["symbol"] for p in self.positions]
        prices  = market_data.get_ltp(symbols)
        for pos in self.positions:
            pos["ltp"] = prices.get(pos["symbol"], pos["price"])

        squareoff = self.risk.get_squareoff_candidates(self.positions, market_data)
        for pos in squareoff:
            log_agent("Orchestrator", f"Square off {pos['symbol']}: {pos['reason']}")
            exit_action = "SELL" if pos["action"] == "BUY" else "BUY"
            if config.TRADING_MODE == "live" and market_data.kite:
                self._place_kite_order(pos["symbol"], exit_action, pos["qty"])
            self.positions = [p for p in self.positions if p["symbol"] != pos["symbol"]]

    # ── End of day ────────────────────────────────────────────────────────────

    async def _end_of_day(self):
        pnl    = get_today_pnl()
        trades = get_today_trade_count()
        log_agent("Orchestrator", f"End of Day | P&L: ₹{pnl:+,.0f} | Trades: {trades}")
        alert_daily_summary(pnl, trades, winners=0)
        self.positions.clear()

    def stop(self):
        self.running = False
        log_agent("Orchestrator", "Stopping...")
