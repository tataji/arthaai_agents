"""
utils/indicators.py — Technical indicator calculations
Uses ta library + custom implementations for Indian market specifics
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import ta
from config import TA_CONFIG


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all technical indicators on an OHLCV DataFrame.
    Columns required: open, high, low, close, volume
    Returns enriched DataFrame with all indicator columns.
    """
    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # ── Trend Indicators ─────────────────────────────────────────────────────
    df["ema_9"]   = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    df["ema_21"]  = ta.trend.EMAIndicator(close, window=21).ema_indicator()
    df["ema_50"]  = ta.trend.EMAIndicator(close, window=50).ema_indicator()
    df["ema_200"] = ta.trend.EMAIndicator(close, window=200).ema_indicator()
    df["sma_20"]  = ta.trend.SMAIndicator(close, window=20).sma_indicator()

    macd = ta.trend.MACD(
        close,
        window_fast=TA_CONFIG["macd_fast"],
        window_slow=TA_CONFIG["macd_slow"],
        window_sign=TA_CONFIG["macd_signal"],
    )
    df["macd"]        = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"]   = macd.macd_diff()

    adx = ta.trend.ADXIndicator(high, low, close, window=14)
    df["adx"]    = adx.adx()
    df["adx_pos"] = adx.adx_pos()
    df["adx_neg"] = adx.adx_neg()

    # ── Momentum Indicators ───────────────────────────────────────────────────
    df["rsi"] = ta.momentum.RSIIndicator(
        close, window=TA_CONFIG["rsi_period"]
    ).rsi()

    stoch = ta.momentum.StochasticOscillator(high, low, close)
    df["stoch_k"] = stoch.stoch()
    df["stoch_d"] = stoch.stoch_signal()

    df["cci"] = ta.trend.CCIIndicator(high, low, close, window=20).cci()
    df["williams_r"] = ta.momentum.WilliamsRIndicator(high, low, close).williams_r()

    # ── Volatility Indicators ─────────────────────────────────────────────────
    bb = ta.volatility.BollingerBands(
        close,
        window=TA_CONFIG["bb_period"],
        window_dev=TA_CONFIG["bb_std"],
    )
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_mid"]   = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]
    df["bb_pct"]   = bb.bollinger_pband()

    df["atr"] = ta.volatility.AverageTrueRange(
        high, low, close, window=TA_CONFIG["atr_period"]
    ).average_true_range()

    # ── Volume Indicators ─────────────────────────────────────────────────────
    df["vol_ma"] = volume.rolling(window=TA_CONFIG["volume_ma_period"]).mean()
    df["vol_ratio"] = volume / df["vol_ma"]

    df["obv"] = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
    df["vwap"] = _compute_vwap(df)

    # ── Support & Resistance ──────────────────────────────────────────────────
    df["pivot"] = (high + low + close) / 3
    df["r1"] = 2 * df["pivot"] - low
    df["s1"] = 2 * df["pivot"] - high
    df["r2"] = df["pivot"] + (high - low)
    df["s2"] = df["pivot"] - (high - low)

    # ── Candlestick Patterns ──────────────────────────────────────────────────
    df["doji"]       = _is_doji(df)
    df["hammer"]     = _is_hammer(df)
    df["engulfing"]  = _is_engulfing(df)
    df["morning_star"] = _is_morning_star(df)

    return df


def _compute_vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP — Volume Weighted Average Price (resets each session)."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_tpv = (typical_price * df["volume"]).cumsum()
    cumulative_vol = df["volume"].cumsum()
    return cumulative_tpv / cumulative_vol


def _is_doji(df: pd.DataFrame, threshold: float = 0.001) -> pd.Series:
    body = abs(df["close"] - df["open"])
    range_ = df["high"] - df["low"]
    return (body / (range_ + 1e-9)) < threshold


def _is_hammer(df: pd.DataFrame) -> pd.Series:
    body = abs(df["close"] - df["open"])
    lower_wick = df[["open", "close"]].min(axis=1) - df["low"]
    upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
    return (lower_wick > 2 * body) & (upper_wick < body)


def _is_engulfing(df: pd.DataFrame) -> pd.Series:
    prev_open  = df["open"].shift(1)
    prev_close = df["close"].shift(1)
    bullish = (df["close"] > df["open"]) & (prev_close < prev_open) & \
              (df["open"] < prev_close) & (df["close"] > prev_open)
    bearish = (df["close"] < df["open"]) & (prev_close > prev_open) & \
              (df["open"] > prev_close) & (df["close"] < prev_open)
    return bullish.astype(int) - bearish.astype(int)   # +1 bullish, -1 bearish


def _is_morning_star(df: pd.DataFrame) -> pd.Series:
    c1_bearish = df["close"].shift(2) < df["open"].shift(2)
    c2_small   = abs(df["close"].shift(1) - df["open"].shift(1)) < \
                 abs(df["close"].shift(2) - df["open"].shift(2)) * 0.3
    c3_bullish = df["close"] > df["open"]
    return c1_bearish & c2_small & c3_bullish


def get_signal_summary(df: pd.DataFrame) -> Dict:
    """
    Summarise latest indicator values into a trading signal dict.
    Returns a dict suitable for passing to Claude or strategy logic.
    """
    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) > 1 else latest

    # MACD crossover
    macd_cross = "bullish" if (latest["macd"] > latest["macd_signal"] and
                               prev["macd"] <= prev["macd_signal"]) else \
                 "bearish" if (latest["macd"] < latest["macd_signal"] and
                               prev["macd"] >= prev["macd_signal"]) else "none"

    # EMA alignment
    ema_bullish = latest["ema_9"] > latest["ema_21"] > latest["ema_50"]
    ema_bearish = latest["ema_9"] < latest["ema_21"] < latest["ema_50"]
    ema_trend   = "bullish" if ema_bullish else ("bearish" if ema_bearish else "mixed")

    # Bollinger band position
    if latest["close"] > latest["bb_upper"]:
        bb_position = "above_upper"
    elif latest["close"] < latest["bb_lower"]:
        bb_position = "below_lower"
    else:
        bb_position = "inside"

    # Above/below 200 EMA
    long_term_trend = "bullish" if latest["close"] > latest["ema_200"] else "bearish"

    return {
        "close":          round(float(latest["close"]), 2),
        "rsi":            round(float(latest["rsi"]), 1),
        "macd":           round(float(latest["macd"]), 4),
        "macd_signal":    round(float(latest["macd_signal"]), 4),
        "macd_hist":      round(float(latest["macd_hist"]), 4),
        "macd_cross":     macd_cross,
        "ema_trend":      ema_trend,
        "adx":            round(float(latest["adx"]), 1),
        "bb_position":    bb_position,
        "bb_width":       round(float(latest["bb_width"]), 4),
        "bb_pct":         round(float(latest["bb_pct"]), 2),
        "atr":            round(float(latest["atr"]), 2),
        "vol_ratio":      round(float(latest["vol_ratio"]), 2),
        "vwap":           round(float(latest["vwap"]), 2),
        "stoch_k":        round(float(latest["stoch_k"]), 1),
        "stoch_d":        round(float(latest["stoch_d"]), 1),
        "long_term_trend": long_term_trend,
        "support":        round(float(latest["s1"]), 2),
        "resistance":     round(float(latest["r1"]), 2),
        "above_vwap":     bool(latest["close"] > latest["vwap"]),
        "doji":           bool(latest["doji"]),
        "hammer":         bool(latest["hammer"]),
        "engulfing":      int(latest["engulfing"]),
    }


def compute_momentum_score(df: pd.DataFrame) -> float:
    """
    Composite momentum score 0-1 for screening.
    Higher = stronger upward momentum.
    """
    sig = get_signal_summary(df)
    score = 0.0
    weights = 0.0

    # RSI (weight 2)
    if sig["rsi"] > 50:
        score += ((sig["rsi"] - 50) / 50) * 2
    weights += 2

    # EMA trend (weight 3)
    if sig["ema_trend"] == "bullish":
        score += 3
    elif sig["ema_trend"] == "bearish":
        score += 0
    else:
        score += 1.5
    weights += 3

    # MACD (weight 2)
    if sig["macd"] > sig["macd_signal"] and sig["macd_hist"] > 0:
        score += 2
    elif sig["macd_cross"] == "bullish":
        score += 1.5
    weights += 2

    # Volume (weight 1)
    if sig["vol_ratio"] > 1.5:
        score += 1
    elif sig["vol_ratio"] > 1.0:
        score += 0.5
    weights += 1

    # Above VWAP (weight 1)
    score += (1 if sig["above_vwap"] else 0)
    weights += 1

    # ADX trend strength (weight 1)
    if sig["adx"] > 25:
        score += 1
    weights += 1

    return round(score / weights, 3)
