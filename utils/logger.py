"""
utils/logger.py — Structured logging with Rich console output
"""

import logging
import sys
from datetime import datetime
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich import print as rprint
import config

console = Console()


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, markup=True)],
    )
    return logging.getLogger(name)


def log_trade(action: str, symbol: str, qty: int, price: float,
              pnl: float = 0.0, mode: str = "paper") -> None:
    tag = f"[bold {'green' if action == 'BUY' else 'red'}]{action}[/]"
    mode_tag = "[yellow]PAPER[/]" if mode == "paper" else "[bold red]LIVE[/]"
    console.log(
        f"{mode_tag} {tag} {symbol} × {qty} @ ₹{price:,.2f}"
        + (f" | P&L: ₹{pnl:+,.2f}" if pnl else "")
    )


def log_signal(symbol: str, signal: str, confidence: float, rationale: str) -> None:
    color = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}.get(signal, "white")
    console.log(
        f"[bold {color}]{signal}[/] {symbol} | conf={confidence:.0%} | {rationale[:80]}"
    )


def log_agent(agent_name: str, message: str, level: str = "info") -> None:
    color = {"info": "cyan", "warn": "yellow", "error": "red"}.get(level, "white")
    console.log(f"[{color}][{agent_name}][/] {message}")


def print_portfolio_table(positions: list) -> None:
    table = Table(title="Portfolio Snapshot", show_header=True, header_style="bold cyan")
    table.add_column("Symbol", style="bold")
    table.add_column("Qty", justify="right")
    table.add_column("Avg Price", justify="right")
    table.add_column("LTP", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("P&L %", justify="right")

    for pos in positions:
        pnl = pos.get("pnl", 0)
        pnl_pct = pos.get("pnl_pct", 0)
        color = "green" if pnl >= 0 else "red"
        table.add_row(
            pos["symbol"],
            str(pos["qty"]),
            f"₹{pos['avg_price']:,.2f}",
            f"₹{pos['ltp']:,.2f}",
            f"[{color}]₹{pnl:+,.2f}[/]",
            f"[{color}]{pnl_pct:+.2f}%[/]",
        )
    console.print(table)
