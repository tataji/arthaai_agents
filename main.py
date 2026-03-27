"""
main.py — ArthAI Entry Point

Usage:
  python main.py --mode paper                    # Paper trading
  python main.py --mode paper --force-market     # Paper + bypass market hours (testing)
  python main.py --mode paper --fast             # Paper + short cycle intervals (testing)
  python main.py --mode live                     # Live trading (real money)
  python main.py --server                        # Start API server
  python main.py --analyse RELIANCE              # Quick stock analysis
"""

# ── Step 1: parse CLI flags BEFORE any other import ──────────────────────────
import sys
import os
import argparse

def _early_parse():
    """Minimal arg parse before dotenv/config loads — sets os.environ directly."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--mode",         default="paper", choices=["paper", "live"])
    p.add_argument("--force-market", action="store_true",
                   help="Bypass market-hours check (for testing outside 9:15-15:30)")
    p.add_argument("--fast",         action="store_true",
                   help="Use short agent cycle intervals (30s) for testing")
    p.add_argument("--server",       action="store_true")
    p.add_argument("--analyse",      default="")
    args, _ = p.parse_known_args()

    # Write directly into os.environ so every subsequent import sees the values
    os.environ["TRADING_MODE"] = args.mode
    if args.force_market:
        os.environ["FORCE_MARKET_OPEN"] = "1"
    if args.fast:
        os.environ["FAST_CYCLE"] = "1"
    return args

_early_args = _early_parse()

# ── Step 2: load .env (will not override values already set above) ────────────
from dotenv import load_dotenv
load_dotenv()   # CLI flags take priority; .env fills in everything else

# ── Step 3: now safe to import everything else ────────────────────────────────
import asyncio
from datetime import datetime

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

    # Show active test flags
    if os.environ.get("FORCE_MARKET_OPEN") == "1":
        console.print("[yellow]  ⚠  --force-market active: market-hours check bypassed[/yellow]")
    if os.environ.get("FAST_CYCLE") == "1":
        console.print("[yellow]  ⚠  --fast active: agent cycles every 30s[/yellow]")


async def run_agents():
    # Import config AFTER os.environ is populated
    import config
    from agents.orchestrator import Orchestrator

    # ── API key check ─────────────────────────────────────────────────────────
    api_key = "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"
    if not api_key:
        console.print("[bold red]ERROR: ANTHROPIC_API_KEY is not set.[/bold red]")
        console.print("[yellow]Add it to your .env file:[/yellow]")
        console.print("  ANTHROPIC_API_KEY=sk-ant-...")
        console.print("[yellow]Or pass it inline:[/yellow]")
        console.print("  [bold]set ANTHROPIC_API_KEY=sk-ant-...  && python main.py --mode paper --force-market --fast[/bold]")
        return
    console.print(f"[green]Starting agents in {config.TRADING_MODE.upper()} mode...[/green]")
    console.print(f"[dim]  FORCE_MARKET_OPEN = {config.FORCE_MARKET_OPEN}[/dim]")
    console.print(f"[dim]  FAST_CYCLE        = {config.FAST_CYCLE}[/dim]")
    console.print(f"[dim]  API key           = {api_key[:12]}...{api_key[-4:]}[/dim]")
    console.print(f"[dim]  Orchestrator interval = {config.AGENT_INTERVALS['orchestrator']}s[/dim]")

    orch = Orchestrator()
    await orch.run_forever()


def run_server():
    import uvicorn
    from data.database import init_db
    init_db()
    console.print("[green]Starting API server on http://localhost:8000[/green]")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)


def run_analyse(symbol: str):
    import asyncio as _asyncio
    from agents.technical_agent import TechnicalAgent
    from agents.fundamental_agent import FundamentalAgent

    console.print(f"[cyan]Analysing {symbol}...[/cyan]")
    tech = TechnicalAgent()
    fund = FundamentalAgent()

    signal = _asyncio.run(tech.analyse_symbol(symbol))
    if signal:
        color = "green" if signal["action"] == "BUY" else "red" if signal["action"] == "SELL" else "yellow"
        console.print(f"\n[bold {color}]{signal['action']}[/] {symbol}")
        console.print(f"Confidence : {signal['confidence']:.0%}")
        console.print(f"Entry      : ₹{signal.get('entry', 0):,.2f}")
        console.print(f"Stop Loss  : ₹{signal.get('stop_loss', 0):,.2f}")
        console.print(f"Target     : ₹{signal.get('target', 0):,.2f}")
        console.print(f"Rationale  : {signal.get('rationale', '')}")

    fund_data = fund.fetch_fundamentals(symbol)
    score     = fund._score_fundamentals(fund_data)
    console.print(f"\nFundamental Score : {score:.0%}  ({fund_data.get('fundamental_rating', '—')})")
    console.print(f"P/E: {fund_data.get('pe_ratio', '—')}  ROE: {fund_data.get('roe', 0)*100:.1f}%  D/E: {fund_data.get('debt_equity', '—')}")


def main():
    print_banner()

    if _early_args.analyse:
        run_analyse(_early_args.analyse.upper())
        return

    if _early_args.server:
        run_server()
        return

    try:
        asyncio.run(run_agents())
    except KeyboardInterrupt:
        console.print("\n[yellow]ArthAI stopped.[/yellow]")


if __name__ == "__main__":
    main()
