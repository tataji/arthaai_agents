"""
main.py — ArthAI Entry Point
Usage:
  python main.py                    # Run agents only (default paper mode)
  python main.py --mode live        # Live trading (real money)
  python main.py --mode paper       # Paper trading
  python main.py --server           # Start API server + agents
  python main.py --backtest         # Run backtest (coming soon)
  python main.py --analyse RELIANCE # Quick single-stock analysis
"""

import argparse
import asyncio
import sys
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()   # load .env before anything else

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def print_banner():
    text = Text()
    text.append("  ArthAI ", style="bold green")
    text.append("— Agentic AI Trading System\n", style="white")
    text.append("  NSE & BSE | Powered by Claude AI + Zerodha Kite\n", style="dim")
    text.append(f"  {datetime.now().strftime('%d %b %Y  %H:%M IST')}", style="dim")
    console.print(Panel(text, border_style="green", padding=(1, 2)))


async def run_agents():
    from agents.orchestrator import Orchestrator
    import config
    orch = Orchestrator()
    console.print(f"[green]Starting agents in {config.TRADING_MODE.upper()} mode...[/green]")
    await orch.run_forever()


def run_server():
    import uvicorn
    from data.database import init_db
    init_db()
    console.print("[green]Starting API server on http://localhost:8000[/green]")
    console.print("[dim]Dashboard available at http://localhost:3000 (start frontend separately)[/dim]")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)


def run_analyse(symbol: str):
    """Quick CLI analysis for a single stock."""
    import asyncio
    from agents.technical_agent import TechnicalAgent
    from agents.fundamental_agent import FundamentalAgent
    import config

    console.print(f"[cyan]Analysing {symbol}...[/cyan]")
    tech  = TechnicalAgent()
    fund  = FundamentalAgent()

    # Technical
    signal = asyncio.run(tech.analyse_symbol(symbol))
    if signal:
        color = "green" if signal["action"] == "BUY" else "red" if signal["action"] == "SELL" else "yellow"
        console.print(f"\n[bold {color}]{signal['action']}[/] {symbol}")
        console.print(f"Confidence: {signal['confidence']:.0%}")
        console.print(f"Entry: ₹{signal.get('entry', 0):,.2f} | SL: ₹{signal.get('stop_loss', 0):,.2f} | Target: ₹{signal.get('target', 0):,.2f}")
        console.print(f"Rationale: {signal.get('rationale', '')}")

    # Fundamental
    fund_data = fund.fetch_fundamentals(symbol)
    score     = fund._score_fundamentals(fund_data)
    console.print(f"\nFundamental Score: {score:.0%} ({fund_data.get('fundamental_rating', '—')})")
    console.print(f"P/E: {fund_data.get('pe_ratio', '—')} | ROE: {fund_data.get('roe', 0)*100:.1f}% | D/E: {fund_data.get('debt_equity', '—')}")


def parse_args():
    parser = argparse.ArgumentParser(description="ArthAI Trading System")
    parser.add_argument("--mode", choices=["paper", "live"], help="Trading mode")
    parser.add_argument("--server", action="store_true", help="Start API server")
    parser.add_argument("--analyse", metavar="SYMBOL", help="Analyse a single stock")
    parser.add_argument("--watchlist", nargs="+", metavar="SYM", help="Override watchlist")
    return parser.parse_args()


def main():
    print_banner()
    args = parse_args()

    # Override trading mode from CLI
    if args.mode:
        import config
        config.TRADING_MODE = args.mode

    if args.analyse:
        run_analyse(args.analyse.upper())
        return

    if args.server:
        run_server()
        return

    # Default: run agents
    try:
        asyncio.run(run_agents())
    except KeyboardInterrupt:
        console.print("\n[yellow]ArthAI stopped.[/yellow]")


if __name__ == "__main__":
    main()
