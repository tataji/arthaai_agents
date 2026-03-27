"""
server.py — FastAPI REST API + WebSocket server
Powers the React frontend dashboard with live data.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.orchestrator import Orchestrator
from data.market_data import market_data
from data.database import (
    init_db, get_open_trades, get_today_pnl, get_today_trade_count, save_trade
)
import config
import anthropic

app = FastAPI(title="ArthAI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global orchestrator instance
orchestrator = Orchestrator()
claude_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

# WebSocket connection manager
active_websockets: List[WebSocket] = []


# ── Request models ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_history: List[Dict] = []


class TradeRequest(BaseModel):
    symbol: str
    action: str   # BUY | SELL
    qty: int
    price: float
    stop_loss: float = 0
    target: float = 0
    exchange: str = "NSE"


# ── REST Endpoints ────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "mode": config.TRADING_MODE,
        "market_open": market_data.is_market_open(),
        "time": datetime.now().isoformat(),
    }


@app.get("/api/portfolio")
def get_portfolio():
    open_trades = get_open_trades()
    today_pnl   = get_today_pnl()
    trade_count = get_today_trade_count()
    symbols = [t.symbol for t in open_trades]
    prices  = market_data.get_ltp(symbols) if symbols else {}

    positions = []
    for t in open_trades:
        ltp = prices.get(t.symbol, t.price)
        mult = 1 if t.action == "BUY" else -1
        pnl  = (ltp - t.price) * mult * t.qty
        positions.append({
            "id":        t.id,
            "symbol":    t.symbol,
            "action":    t.action,
            "qty":       t.qty,
            "avg_price": t.price,
            "ltp":       round(ltp, 2),
            "pnl":       round(pnl, 2),
            "pnl_pct":   round(pnl / (t.price * t.qty) * 100, 2),
            "stop_loss": t.stop_loss,
            "target":    t.target,
        })

    return {
        "positions":     positions,
        "today_pnl":     round(today_pnl, 2),
        "today_trades":  trade_count,
        "open_count":    len(positions),
        "capital":       config.CAPITAL,
    }


@app.get("/api/watchlist")
def get_watchlist():
    symbols = orchestrator.watchlist
    prices  = market_data.get_ltp(symbols)
    signals = orchestrator.technical.signals

    result = []
    for sym in symbols:
        ltp    = prices.get(sym, 0)
        signal = signals.get(sym, {})
        result.append({
            "symbol":     sym,
            "ltp":        round(ltp, 2),
            "action":     signal.get("action", "—"),
            "confidence": signal.get("confidence", 0),
            "entry":      signal.get("entry", 0),
            "stop_loss":  signal.get("stop_loss", 0),
            "target":     signal.get("target", 0),
            "rationale":  signal.get("rationale", ""),
            "indicators": signal.get("indicators", {}),
        })

    return {"watchlist": result}


@app.get("/api/signals")
def get_signals():
    return {"signals": orchestrator.technical.signals}


@app.get("/api/risk")
def get_risk():
    positions = orchestrator.positions
    return orchestrator.risk.compute_portfolio_risk(positions)


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Claude AI chat endpoint for the trading assistant."""
    messages = req.conversation_history + [{"role": "user", "content": req.message}]
    try:
        response = claude_client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=1000,
            system=config.SYSTEM_PROMPT_TRADING,
            messages=messages,
        )
        reply = response.content[0].text
        return {"reply": reply, "model": config.CLAUDE_MODEL}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trade")
def place_trade(req: TradeRequest):
    """Manually place a trade (paper or live)."""
    from agents.risk_agent import RiskAgent
    risk = orchestrator.risk
    check = risk.approve_trade(
        req.symbol, req.action, req.price, req.qty,
        req.stop_loss, req.target, market_data
    )
    if not check.approved:
        raise HTTPException(status_code=400, detail=check.reason)

    trade = save_trade(
        symbol=req.symbol, action=req.action,
        qty=check.adjusted_qty, price=req.price,
        stop_loss=req.stop_loss, target=req.target,
        exchange=req.exchange,
    )
    return {"trade_id": trade.id, "status": "placed", "mode": config.TRADING_MODE}


@app.get("/api/market/quote/{symbol}")
def get_quote(symbol: str):
    ltp = market_data.get_ltp([symbol])
    quote = market_data.get_quote(symbol)
    return {"symbol": symbol, "ltp": ltp.get(symbol, 0), "quote": quote}


@app.get("/api/fo/iron_condor/{index}")
def get_iron_condor(index: str, spot: float = 22800, iv: float = 0.14, dte: int = 7):
    result = orchestrator.fo.iron_condor(spot, iv, dte,
                                          lot_size=50 if index == "NIFTY" else 15)
    return result


@app.post("/api/agents/start")
async def start_agents():
    asyncio.create_task(orchestrator.run_forever())
    return {"status": "agents_started"}


@app.post("/api/agents/stop")
def stop_agents():
    orchestrator.stop()
    return {"status": "agents_stopped"}


# ── WebSocket for live updates ─────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    active_websockets.append(ws)
    try:
        while True:
            data = {
                "type": "tick",
                "time": datetime.now().isoformat(),
                "market_open": market_data.is_market_open(),
                "today_pnl": round(get_today_pnl(), 2),
                "today_trades": get_today_trade_count(),
            }
            await ws.send_json(data)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        active_websockets.remove(ws)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
