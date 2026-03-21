"""
backtest.py — Simple vectorised backtester for ArthAI strategies
Usage:
  python backtest.py --symbol RELIANCE --strategy momentum --days 365
  python backtest.py --watchlist --strategy breakout --days 180
"""

import argparse
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime
from rich.console import Console
from rich.table import Table

from data.market_data import market_data
from utils.indicators import compute_all_indicators, get_signal_summary, compute_momentum_score
import config

console = Console()


class Backtest:
    """Simple event-driven backtester."""

    def __init__(
        self,
        capital: float = 100_000,
        sl_pct: float = 0.015,
        target_pct: float = 0.03,
        max_position_pct: float = 0.10,
    ):
        self.capital         = capital
        self.sl_pct          = sl_pct
        self.target_pct      = target_pct
        self.max_position_pct = max_position_pct
        self.trades: List[Dict] = []
        self.equity_curve: List[float] = [capital]
        self.cash = capital

    def run_momentum(self, symbol: str, days: int = 365) -> Dict:
        """Backtest momentum strategy on a single symbol."""
        df = market_data.get_ohlcv(symbol, "day", days=days + 60)
        if df.empty or len(df) < 60:
            return {"error": f"Insufficient data for {symbol}"}

        df = compute_all_indicators(df)
        df = df.dropna().iloc[-days:]   # Use only requested period

        position     = None
        entry_price  = 0.0
        sl           = 0.0
        target       = 0.0

        for i in range(20, len(df)):
            row  = df.iloc[i]
            prev = df.iloc[i-1]
            date = df.index[i]
            close = float(row["close"])

            # Exit logic
            if position == "long":
                if close <= sl:
                    pnl = (sl - entry_price) / entry_price * 100
                    self._record_trade(symbol, date, "SELL", close, "stop_loss", pnl)
                    position = None
                elif close >= target:
                    pnl = (target - entry_price) / entry_price * 100
                    self._record_trade(symbol, date, "SELL", close, "target_hit", pnl)
                    position = None
                continue

            # Entry logic: simplified momentum check
            rsi       = float(row["rsi"])
            macd_hist = float(row["macd_hist"])
            ema_bull  = float(row["ema_9"]) > float(row["ema_21"]) > float(row["ema_50"])
            vol_ratio = float(row["vol_ratio"])
            above200  = close > float(row["ema_200"])

            if (
                position is None and
                55 <= rsi <= 72 and
                macd_hist > 0 and
                ema_bull and
                vol_ratio >= 1.4 and
                above200
            ):
                position    = "long"
                entry_price = close
                atr         = float(row["atr"])
                sl          = round(close - 1.5 * atr, 2)
                target      = round(close + 2.5 * atr, 2)
                self._record_trade(symbol, date, "BUY", close, "momentum_entry", 0)

        return self._compute_stats(symbol, days)

    def _record_trade(self, symbol, date, action, price, reason, pnl_pct):
        if action == "SELL" and self.trades:
            last_buy = next((t for t in reversed(self.trades) if t["action"] == "BUY"), None)
            if last_buy:
                qty  = int(self.cash * self.max_position_pct / last_buy["price"])
                pnl  = (price - last_buy["price"]) * qty
                self.cash += pnl
                self.equity_curve.append(self.cash)
        self.trades.append({
            "symbol": symbol,
            "date":   date,
            "action": action,
            "price":  price,
            "reason": reason,
            "pnl_pct": round(pnl_pct, 2),
        })

    def _compute_stats(self, symbol: str, days: int) -> Dict:
        sell_trades = [t for t in self.trades if t["action"] == "SELL"]
        if not sell_trades:
            return {"symbol": symbol, "trades": 0, "message": "No trades generated"}

        pnls      = [t["pnl_pct"] for t in sell_trades]
        winners   = [p for p in pnls if p > 0]
        losers    = [p for p in pnls if p <= 0]

        equity    = pd.Series(self.equity_curve)
        drawdown  = (equity / equity.cummax() - 1).min()

        total_return = (self.cash - self.capital) / self.capital * 100

        return {
            "symbol":        symbol,
            "period_days":   days,
            "total_trades":  len(sell_trades),
            "winners":       len(winners),
            "losers":        len(losers),
            "win_rate":      round(len(winners) / len(sell_trades) * 100, 1),
            "avg_win_pct":   round(np.mean(winners), 2) if winners else 0,
            "avg_loss_pct":  round(np.mean(losers), 2) if losers else 0,
            "profit_factor": round(
                sum(winners) / abs(sum(losers)), 2
            ) if losers else float("inf"),
            "total_return_pct": round(total_return, 2),
            "max_drawdown_pct": round(drawdown * 100, 2),
            "final_capital":    round(self.cash, 0),
            "expectancy":       round(np.mean(pnls), 2),
        }


def print_backtest_results(results: List[Dict]):
    table = Table(title="Backtest Results", show_header=True, header_style="bold cyan")
    for col in ["Symbol", "Trades", "Win%", "Avg Win%", "Avg Loss%",
                "P.Factor", "Return%", "Drawdown%", "Expectancy"]:
        table.add_column(col, justify="right" if col != "Symbol" else "left")

    for r in results:
        if "error" in r:
            continue
        wr_color   = "green" if r["win_rate"] > 50 else "red"
        ret_color  = "green" if r["total_return_pct"] > 0 else "red"
        table.add_row(
            r["symbol"],
            str(r["total_trades"]),
            f"[{wr_color}]{r['win_rate']}%[/]",
            f"[green]{r['avg_win_pct']}%[/]",
            f"[red]{r['avg_loss_pct']}%[/]",
            str(r["profit_factor"]),
            f"[{ret_color}]{r['total_return_pct']}%[/]",
            f"[red]{r['max_drawdown_pct']}%[/]",
            str(r["expectancy"]),
        )
    console.print(table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ArthAI Backtester")
    parser.add_argument("--symbol",    default="RELIANCE")
    parser.add_argument("--strategy",  default="momentum")
    parser.add_argument("--days",      type=int, default=365)
    parser.add_argument("--watchlist", action="store_true")
    args = parser.parse_args()

    symbols = config.DEFAULT_WATCHLIST if args.watchlist else [args.symbol.upper()]
    results = []

    for sym in symbols:
        console.print(f"[cyan]Backtesting {sym}...[/cyan]")
        bt = Backtest()
        result = bt.run_momentum(sym, args.days)
        results.append(result)
        console.print(f"  {sym}: {result.get('total_trades', 0)} trades, "
                      f"{result.get('win_rate', 0)}% win rate, "
                      f"{result.get('total_return_pct', 0)}% return")

    print_backtest_results(results)
