"""AI signals: KAMA, RSI, ATR and market evaluation.

This module computes indicators and evaluates market state according to AETMS rules:
- BUY: Close > KAMA(200) AND RSI crosses above 50 AND Sentiment > 0.6
- SELL: Close < KAMA(200) AND RSI crosses below 50 AND Sentiment < -0.6
- HOLD otherwise
"""
from __future__ import annotations

import logging
import math
import random
from typing import Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def kama(series: pd.Series, n: int = 200, fast: int = 2, slow: int = 30) -> pd.Series:
    """Compute Kaufman's Adaptive Moving Average (KAMA).

    This implementation is iterative but vectorized enough for typical dataset sizes.
    """
    price = series.fillna(method="ffill").astype(float)
    length = len(price)
    kama = pd.Series(index=price.index, dtype=float)

    change = price.diff(n).abs()
    volatility = price.diff().abs().rolling(window=n, min_periods=1).sum()
    er = change / (volatility.replace(0, np.nan))
    er = er.fillna(0.0).clip(0.0, 1.0)

    fast_sc = 2.0 / (fast + 1.0)
    slow_sc = 2.0 / (slow + 1.0)

    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

    # initialize with SMA of first n values or first price
    if length == 0:
        return kama
    init_idx = 0
    if length >= n:
        init_idx = n - 1
        kama.iloc[init_idx] = price.iloc[: n].mean()
    else:
        kama.iloc[0] = price.iloc[0]
        init_idx = 0

    for i in range(init_idx + 1, length):
        prev = kama.iloc[i - 1]
        if math.isnan(prev):
            prev = price.iloc[i - 1]
        kama.iloc[i] = prev + sc.iloc[i] * (price.iloc[i] - prev)

    return kama


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period, min_periods=1).mean()
    return atr


def get_ai_sentiment(symbol: str) -> float:
    """Mock AI sentiment function. Returns float in [-1.0, 1.0].

    Deterministic-ish per symbol using seeded random to make tests reproducible.
    """
    seed = abs(hash(symbol)) % (2 ** 32)
    rnd = random.Random(seed)
    # map to -1..1
    return rnd.uniform(-1.0, 1.0)


def evaluate_market_state(df: pd.DataFrame, symbol: str) -> Dict:
    """Evaluate market state and return action, confidence and atr.

    df is expected to have columns: 'open','high','low','close','volume'
    """
    try:
        if df is None or len(df) < 3:
            return {"action": "HOLD", "confidence": 0.0, "atr": 0.0}

        close = df["close"].astype(float)
        k = kama(close, n=200)
        r = rsi(close, period=14)
        a = atr(df, period=14)

        last_close = close.iloc[-1]
        last_kama = k.iloc[-1]
        last_rsi = r.iloc[-1]
        prev_rsi = r.iloc[-2]
        last_atr = float(a.iloc[-1]) if not a.empty else 0.0

        sentiment = get_ai_sentiment(symbol)

        # RSI crosses
        rsi_cross_up = (prev_rsi < 50.0) and (last_rsi >= 50.0)
        rsi_cross_down = (prev_rsi > 50.0) and (last_rsi <= 50.0)

        action = "HOLD"
        confidence = 0.0

        if (last_close > last_kama) and rsi_cross_up and (sentiment > 0.6):
            action = "BUY"
            # confidence scales with sentiment above 0.6
            confidence = 0.6 + 0.4 * min(1.0, (sentiment - 0.6) / 0.4)
        elif (last_close < last_kama) and rsi_cross_down and (sentiment < -0.6):
            action = "SELL"
            confidence = 0.6 + 0.4 * min(1.0, (-sentiment - 0.6) / 0.4)
        else:
            # auto-close if sentiment drops below 0.0
            if sentiment < 0.0:
                action = "HOLD"
                confidence = 0.1
            else:
                action = "HOLD"
                confidence = 0.0

        return {"action": action, "confidence": float(round(confidence, 3)), "atr": float(last_atr), "kama": float(last_kama), "rsi": float(last_rsi), "sentiment": float(round(sentiment, 3))}
    except Exception:
        logger.exception("Error evaluating market state")
        return {"action": "HOLD", "confidence": 0.0, "atr": 0.0}


__all__ = ["kama", "rsi", "atr", "get_ai_sentiment", "evaluate_market_state"]
