"""
main.py — ArthAI Entry Point

Usage:
  python main.py --mode paper --force-market --fast --api-key sk-ant-...
  python main.py --mode paper
  python main.py --mode live
  python main.py --server
  python main.py --analyse RELIANCE
"""

import sys
import os
import argparse

def _early_parse():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--mode",         default="paper", choices=["paper", "live"])
    p.add_argument("--force-market", action="store_true")
    p.add_argument("--fast",         action="store_true")
    p.add_argument("--server",       action="store_true")
    p.add_argument("--analyse",      default="")
    p.add_argument("--api-key",      default="",
                   help="Anthropic API key (overrides .env)")
    args, _ = p.parse_known_args()

    os.environ["TRADING_MODE"] = args.mode
    if args.force_market:
        os.environ["FORCE_MARKET_OPEN"] = "1"
    if args.fast:
        os.environ["FAST_CYCLE"] = "1"
    if args.api_key:
        os.environ["ANTHROPIC_API_KEY"] = args.api_key
    return args

_args = _early_parse()

# Load .env AFTER CLI flags (CLI takes priority)
from dotenv import load_dotenv
load_dotenv()

# If key still missing, try reading .env manually as a fallback
if not os.environ.get("ANTHROPIC_API_KEY"):
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    os.environ["ANTHROPIC_API_KEY"] = key
                break

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
    if os.environ.get("FORCE_MARKET_OPEN") == "1":
        console.print("[yellow]  ⚠  --force-market active: bypassing market hours[/yellow]")
    if os.environ.get("FAST_CYCLE") == "1":
        console.print("[yellow]  ⚠  --fast active: 30s agent cycles[/yellow]")


async def run_agents():
    import config
    from agents.orchestrator import Orchestrator

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        console.print("[bold red]✗ ANTHROPIC_API_KEY not found.[/bold red]")
        console.print("[yellow]Pass it via CLI:[/yellow]")
        console.print("  [bold]python main.py --mode paper --force-market --fast --api-key sk-ant-...[/bold]")
        return

    console.print(f"[green]Starting agents in {config.TRADING_MODE.upper()} mode...[/green]")
    console.print(f"[dim]  API key: {api_key[:16]}...{api_key[-4:]}[/dim]")
    console.print(f"[dim]  Cycle:   {config.AGENT_INTERVALS['orchestrator']}s[/dim]")

    orch = Orchestrator()
    await orch.run_forever()


def run_server():
    import uvicorn
    from data.database import init_db
    init_db()
    console.print("[green]Starting API server → http://localhost:8000[/green]")
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
    if _args.analyse:
        run_analyse(_args.analyse.upper())
        return
    if _args.server:
        run_server()
        return
    try:
        asyncio.run(run_agents())
    except KeyboardInterrupt:
        console.print("\n[yellow]ArthAI stopped.[/yellow]")


if __name__ == "__main__":
    main()
