"""
utils/health_check.py — System health monitoring
Checks API connectivity, broker status, market data feeds, agent health.
"""

import os
import sys
import time
import requests
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class HealthStatus:
    name:     str
    ok:       bool
    message:  str
    latency:  float = 0.0    # ms
    details:  Dict  = field(default_factory=dict)


def check_anthropic_api(api_key: str = "") -> HealthStatus:
    """Ping Anthropic API with a minimal request."""
    key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        return HealthStatus("Anthropic API", False, "No API key configured")
    try:
        import anthropic
        t0     = time.perf_counter()
        client = anthropic.Anthropic(api_key=key)
        resp   = client.messages.create(
            model="claude-haiku-4-20250514",
            max_tokens=5,
            messages=[{"role": "user", "content": "ping"}],
        )
        ms = (time.perf_counter() - t0) * 1000
        return HealthStatus("Anthropic API", True, "Connected", latency=round(ms, 1))
    except Exception as e:
        return HealthStatus("Anthropic API", False, str(e)[:80])


def check_kite_api() -> HealthStatus:
    """Check Zerodha Kite Connect connection."""
    api_key    = os.getenv("KITE_API_KEY", "")
    acc_token  = os.getenv("KITE_ACCESS_TOKEN", "")
    if not api_key or not acc_token:
        return HealthStatus("Kite Connect", False, "API key / access token not set")
    try:
        from kiteconnect import KiteConnect
        t0   = time.perf_counter()
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(acc_token)
        profile = kite.profile()
        ms = (time.perf_counter() - t0) * 1000
        return HealthStatus(
            "Kite Connect", True,
            f"Connected as {profile.get('user_name', 'unknown')}",
            latency=round(ms, 1),
            details={"user_id": profile.get("user_id"), "broker": profile.get("broker")},
        )
    except Exception as e:
        return HealthStatus("Kite Connect", False, str(e)[:80])


def check_nse_feed() -> HealthStatus:
    """Check if NSE market data is accessible."""
    try:
        t0  = time.perf_counter()
        r   = requests.get("https://www.nseindia.com/api/marketStatus", timeout=8,
                           headers={"User-Agent": "Mozilla/5.0"})
        ms  = (time.perf_counter() - t0) * 1000
        if r.status_code == 200:
            data   = r.json()
            status = data.get("marketState", [{}])[0].get("marketStatus", "unknown")
            return HealthStatus("NSE Feed", True, f"Market status: {status}", latency=round(ms, 1))
        return HealthStatus("NSE Feed", False, f"HTTP {r.status_code}")
    except Exception as e:
        return HealthStatus("NSE Feed", False, str(e)[:80])


def check_database() -> HealthStatus:
    """Check database connection and integrity."""
    try:
        t0 = time.perf_counter()
        from data.database import SessionLocal, Trade, Signal
        with SessionLocal() as db:
            trade_count  = db.query(Trade).count()
            signal_count = db.query(Signal).count()
        ms = (time.perf_counter() - t0) * 1000
        return HealthStatus(
            "Database", True,
            f"{trade_count} trades, {signal_count} signals",
            latency=round(ms, 1),
        )
    except Exception as e:
        return HealthStatus("Database", False, str(e)[:80])


def check_telegram() -> HealthStatus:
    """Check Telegram bot connectivity."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return HealthStatus("Telegram", False, "Bot token not configured")
    try:
        t0  = time.perf_counter()
        r   = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
        ms  = (time.perf_counter() - t0) * 1000
        if r.status_code == 200:
            bot = r.json().get("result", {})
            return HealthStatus("Telegram", True, f"Bot: @{bot.get('username')}", latency=round(ms, 1))
        return HealthStatus("Telegram", False, f"HTTP {r.status_code}")
    except Exception as e:
        return HealthStatus("Telegram", False, str(e)[:80])


def check_yfinance() -> HealthStatus:
    """Check yfinance data feed."""
    try:
        import yfinance as yf
        t0     = time.perf_counter()
        ticker = yf.Ticker("RELIANCE.NS")
        info   = ticker.fast_info
        price  = getattr(info, "last_price", None)
        ms     = (time.perf_counter() - t0) * 1000
        if price:
            return HealthStatus("yFinance", True, f"RELIANCE.NS: ₹{price:.2f}", latency=round(ms, 1))
        return HealthStatus("yFinance", False, "No price data returned")
    except Exception as e:
        return HealthStatus("yFinance", False, str(e)[:80])


def run_all_checks(api_key: str = "") -> List[HealthStatus]:
    """Run all health checks and return results."""
    checks = [
        check_anthropic_api(api_key),
        check_kite_api(),
        check_nse_feed(),
        check_database(),
        check_telegram(),
        check_yfinance(),
    ]
    return checks


def system_summary(checks: List[HealthStatus]) -> Tuple[bool, str]:
    """Returns (all_ok, summary_message)."""
    ok_count    = sum(1 for c in checks if c.ok)
    total       = len(checks)
    all_ok      = ok_count == total
    critical_ok = all(c.ok for c in checks if c.name in ("Anthropic API", "Database"))
    summary     = f"{ok_count}/{total} services healthy"
    if not critical_ok:
        summary = "⚠️ Critical services down — " + summary
    return all_ok, summary


if __name__ == "__main__":
    """Quick CLI health check."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    console.print("\n[bold cyan]ArthAI System Health Check[/bold cyan]\n")

    checks = run_all_checks()
    table  = Table(show_header=True, header_style="bold")
    table.add_column("Service",  style="bold")
    table.add_column("Status")
    table.add_column("Message")
    table.add_column("Latency", justify="right")

    for c in checks:
        status = "[green]✓ OK[/green]" if c.ok else "[red]✗ FAIL[/red]"
        lat    = f"{c.latency:.0f}ms" if c.latency else "—"
        table.add_row(c.name, status, c.message, lat)

    console.print(table)
    all_ok, summary = system_summary(checks)
    console.print(f"\n{'[green]' if all_ok else '[yellow]'}{summary}[/]")
