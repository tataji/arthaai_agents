"""
utils/portfolio_analytics.py — Portfolio performance analytics
Sharpe ratio, max drawdown, beta, correlation, attribution.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PortfolioStats:
    total_return_pct:   float
    annualised_return:  float
    sharpe_ratio:       float
    sortino_ratio:      float
    max_drawdown_pct:   float
    max_drawdown_duration: int   # days
    win_rate:           float
    profit_factor:      float
    expectancy:         float
    calmar_ratio:       float
    avg_trade_return:   float
    best_trade_pct:     float
    worst_trade_pct:    float
    total_trades:       int
    winners:            int
    losers:             int
    avg_win_pct:        float
    avg_loss_pct:       float
    volatility_pct:     float
    beta:               float
    alpha_pct:          float


def compute_portfolio_stats(
    returns: List[float],           # Daily P&L returns as decimals
    benchmark_returns: Optional[List[float]] = None,
    risk_free_rate: float = 0.065,  # RBI repo rate ~6.5%
) -> PortfolioStats:
    """
    Compute comprehensive portfolio performance statistics.
    """
    if not returns or len(returns) < 2:
        return _empty_stats()

    r = np.array(returns)
    n = len(r)

    # ── Core returns ──────────────────────────────────────────────────────────
    total_return     = float(np.prod(1 + r) - 1)
    annualised       = float((1 + total_return) ** (252 / n) - 1)
    daily_rf         = risk_free_rate / 252
    excess_returns   = r - daily_rf

    # ── Risk metrics ──────────────────────────────────────────────────────────
    vol           = float(np.std(r) * np.sqrt(252))
    sharpe        = float(np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)) if np.std(excess_returns) > 0 else 0
    downside      = r[r < 0]
    downside_std  = float(np.std(downside) * np.sqrt(252)) if len(downside) > 0 else 1e-9
    sortino       = float(np.mean(excess_returns) * 252 / downside_std) if downside_std > 0 else 0

    # ── Drawdown ──────────────────────────────────────────────────────────────
    equity           = np.cumprod(1 + r)
    running_max      = np.maximum.accumulate(equity)
    drawdown_series  = (equity - running_max) / running_max
    max_dd           = float(np.min(drawdown_series))
    calmar           = annualised / abs(max_dd) if max_dd != 0 else 0

    # Max drawdown duration
    in_drawdown      = drawdown_series < 0
    dd_duration      = _max_consecutive(in_drawdown)

    # ── Trade statistics (treat each non-zero return as a "trade") ────────────
    trades   = r[r != 0]
    winners  = trades[trades > 0]
    losers   = trades[trades < 0]
    win_rate = len(winners) / len(trades) if len(trades) > 0 else 0

    avg_win  = float(np.mean(winners)) if len(winners) > 0 else 0
    avg_loss = float(np.mean(losers))  if len(losers)  > 0 else 0
    pf       = abs(avg_win * len(winners)) / abs(avg_loss * len(losers)) if len(losers) > 0 and avg_loss != 0 else float("inf")
    exp      = win_rate * avg_win + (1 - win_rate) * avg_loss

    # ── Beta & Alpha vs benchmark ─────────────────────────────────────────────
    beta  = 1.0
    alpha = 0.0
    if benchmark_returns and len(benchmark_returns) == n:
        bm = np.array(benchmark_returns)
        cov_matrix = np.cov(r, bm)
        beta  = float(cov_matrix[0, 1] / cov_matrix[1, 1]) if cov_matrix[1, 1] > 0 else 1.0
        bm_annualised = float((1 + float(np.prod(1 + bm) - 1)) ** (252 / n) - 1)
        alpha = annualised - (daily_rf * 252 + beta * (bm_annualised - daily_rf * 252))

    return PortfolioStats(
        total_return_pct=round(total_return * 100, 2),
        annualised_return=round(annualised * 100, 2),
        sharpe_ratio=round(sharpe, 3),
        sortino_ratio=round(sortino, 3),
        max_drawdown_pct=round(max_dd * 100, 2),
        max_drawdown_duration=int(dd_duration),
        win_rate=round(win_rate * 100, 1),
        profit_factor=round(pf, 3),
        expectancy=round(exp * 100, 3),
        calmar_ratio=round(calmar, 3),
        avg_trade_return=round(float(np.mean(trades)) * 100, 3) if len(trades) > 0 else 0,
        best_trade_pct=round(float(np.max(trades)) * 100, 2) if len(trades) > 0 else 0,
        worst_trade_pct=round(float(np.min(trades)) * 100, 2) if len(trades) > 0 else 0,
        total_trades=len(trades),
        winners=len(winners),
        losers=len(losers),
        avg_win_pct=round(avg_win * 100, 2),
        avg_loss_pct=round(avg_loss * 100, 2),
        volatility_pct=round(vol * 100, 2),
        beta=round(beta, 3),
        alpha_pct=round(alpha * 100, 2),
    )


def _max_consecutive(arr: np.ndarray) -> int:
    """Count max consecutive True values."""
    max_run = run = 0
    for v in arr:
        run = run + 1 if v else 0
        max_run = max(max_run, run)
    return max_run


def _empty_stats() -> PortfolioStats:
    return PortfolioStats(**{f.name: 0 for f in PortfolioStats.__dataclass_fields__.values()})


def compute_sector_attribution(positions: List[Dict]) -> Dict[str, Dict]:
    """
    Compute P&L attribution by sector.
    positions: list of {symbol, sector, pnl, value}
    """
    sectors: Dict[str, Dict] = {}
    total_pnl = sum(p.get("pnl", 0) for p in positions)
    total_val = sum(p.get("value", 0) for p in positions) or 1

    for pos in positions:
        sector = pos.get("sector", "Other")
        if sector not in sectors:
            sectors[sector] = {"pnl": 0, "value": 0, "count": 0, "symbols": []}
        sectors[sector]["pnl"]    += pos.get("pnl", 0)
        sectors[sector]["value"]  += pos.get("value", 0)
        sectors[sector]["count"]  += 1
        sectors[sector]["symbols"].append(pos.get("symbol", ""))

    for sec in sectors:
        sectors[sec]["pnl_contribution_pct"] = round(
            sectors[sec]["pnl"] / total_pnl * 100 if total_pnl else 0, 2
        )
        sectors[sec]["weight_pct"] = round(
            sectors[sec]["value"] / total_val * 100, 2
        )
    return sectors


def compute_var(returns: List[float], confidence: float = 0.95) -> Tuple[float, float]:
    """
    Value at Risk (VaR) and Conditional VaR (CVaR / Expected Shortfall).
    Returns (VaR%, CVaR%) at given confidence level.
    """
    if not returns:
        return 0.0, 0.0
    r     = np.sort(np.array(returns))
    idx   = int((1 - confidence) * len(r))
    var   = -float(r[idx])
    cvar  = -float(np.mean(r[:idx])) if idx > 0 else var
    return round(var * 100, 3), round(cvar * 100, 3)


def position_correlation_matrix(price_data: Dict[str, List[float]]) -> pd.DataFrame:
    """
    Compute correlation matrix for a set of positions.
    price_data: {symbol: [daily_returns]}
    """
    df = pd.DataFrame(price_data)
    return df.corr().round(3)


def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """
    Kelly Criterion for optimal position sizing.
    Returns fraction of capital to risk (cap at 25% for safety).
    win_rate: 0–1, avg_win/avg_loss: positive decimals
    """
    if avg_loss <= 0:
        return 0.0
    b     = avg_win / avg_loss
    kelly = win_rate - (1 - win_rate) / b
    return round(min(max(kelly, 0), 0.25), 4)
