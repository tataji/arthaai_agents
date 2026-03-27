"""
data/database.py — SQLite database for trades, signals, and logs
"""

from sqlalchemy import (
    create_engine, Column, Integer, Float, String,
    DateTime, Boolean, Text, func
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime
from typing import List, Optional
import config

Base = declarative_base()
engine = create_engine(config.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


# ── Models ────────────────────────────────────────────────────────────────────

class Trade(Base):
    __tablename__ = "trades"
    id         = Column(Integer, primary_key=True, index=True)
    timestamp  = Column(DateTime, default=datetime.now)
    symbol     = Column(String, index=True)
    exchange   = Column(String, default="NSE")
    action     = Column(String)          # BUY | SELL
    qty        = Column(Integer)
    price      = Column(Float)
    stop_loss  = Column(Float, nullable=True)
    target     = Column(Float, nullable=True)
    pnl        = Column(Float, nullable=True)
    status     = Column(String, default="open")  # open | closed | cancelled
    mode       = Column(String, default="paper") # paper | live
    strategy   = Column(String, nullable=True)
    rationale  = Column(Text, nullable=True)
    order_id   = Column(String, nullable=True)   # Broker order ID


class Signal(Base):
    __tablename__ = "signals"
    id          = Column(Integer, primary_key=True, index=True)
    timestamp   = Column(DateTime, default=datetime.now)
    symbol      = Column(String, index=True)
    action      = Column(String)          # BUY | SELL | HOLD
    confidence  = Column(Float)
    source      = Column(String)          # agent name
    rsi         = Column(Float, nullable=True)
    macd        = Column(Float, nullable=True)
    price       = Column(Float, nullable=True)
    rationale   = Column(Text, nullable=True)
    acted_upon  = Column(Boolean, default=False)


class AgentLog(Base):
    __tablename__ = "agent_logs"
    id         = Column(Integer, primary_key=True, index=True)
    timestamp  = Column(DateTime, default=datetime.now)
    agent      = Column(String, index=True)
    level      = Column(String, default="info")
    message    = Column(Text)


class DailySummary(Base):
    __tablename__ = "daily_summary"
    id          = Column(Integer, primary_key=True, index=True)
    date        = Column(String, unique=True)    # YYYY-MM-DD
    total_trades = Column(Integer, default=0)
    winners     = Column(Integer, default=0)
    losers      = Column(Integer, default=0)
    gross_pnl   = Column(Float, default=0.0)
    net_pnl     = Column(Float, default=0.0)     # after brokerage
    max_drawdown = Column(Float, default=0.0)
    capital_deployed = Column(Float, default=0.0)


def init_db() -> None:
    Base.metadata.create_all(engine)


# ── CRUD helpers ──────────────────────────────────────────────────────────────

def save_trade(
    symbol: str, action: str, qty: int, price: float,
    stop_loss: float = 0, target: float = 0,
    strategy: str = "", rationale: str = "",
    order_id: str = "", exchange: str = "NSE"
) -> Trade:
    with SessionLocal() as db:
        trade = Trade(
            symbol=symbol, exchange=exchange, action=action, qty=qty,
            price=price, stop_loss=stop_loss, target=target,
            strategy=strategy, rationale=rationale, order_id=order_id,
            mode=config.TRADING_MODE,
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)
        return trade


def close_trade(trade_id: int, exit_price: float) -> Optional[Trade]:
    with SessionLocal() as db:
        trade = db.query(Trade).filter(Trade.id == trade_id).first()
        if not trade:
            return None
        mult = 1 if trade.action == "BUY" else -1
        trade.pnl    = round((exit_price - trade.price) * mult * trade.qty, 2)
        trade.status = "closed"
        db.commit()
        db.refresh(trade)
        return trade


def save_signal(
    symbol: str, action: str, confidence: float, source: str,
    price: float = 0, rsi: float = 0, macd: float = 0, rationale: str = ""
) -> None:
    with SessionLocal() as db:
        sig = Signal(
            symbol=symbol, action=action, confidence=confidence,
            source=source, price=price, rsi=rsi, macd=macd, rationale=rationale,
        )
        db.add(sig)
        db.commit()


def get_open_trades() -> List[Trade]:
    with SessionLocal() as db:
        return db.query(Trade).filter(Trade.status == "open").all()


def get_today_pnl() -> float:
    today = datetime.now().strftime("%Y-%m-%d")
    with SessionLocal() as db:
        result = db.query(func.sum(Trade.pnl)).filter(
            Trade.status == "closed",
            func.date(Trade.timestamp) == today,
        ).scalar()
        return float(result or 0.0)


def get_today_trade_count() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    with SessionLocal() as db:
        return db.query(Trade).filter(
            func.date(Trade.timestamp) == today,
        ).count()


def log_agent_event(agent: str, message: str, level: str = "info") -> None:
    with SessionLocal() as db:
        entry = AgentLog(agent=agent, level=level, message=message)
        db.add(entry)
        db.commit()
