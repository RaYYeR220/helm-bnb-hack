"""Market-level risk-off detection (the Regime v2 trend-filter gate).

The 3-state HMM taxonomy (trending / ranging / high_volatility) cannot tell an
uptrend from a downtrend: a grinding bear market reads as "ranging" and routes
to mean-reversion, which then buys falling knives. This module supplies the
missing guardrail: a transparent, principled trend filter — equal-weight market
index below its moving average, or in a deep drawdown from its running peak,
means risk-off. This is textbook trend-following risk management (not tuned to
any particular window) and is validated out-of-sample by the Plan D harness.
"""

import pandas as pd


def market_index(prices: pd.DataFrame) -> pd.Series:
    """Equal-weight market index: each name rebased to 1.0 at its first
    available price, then averaged across the names with data per date."""
    first_prices = prices.bfill().iloc[0]
    rebased = prices / first_prices
    return rebased.mean(axis=1, skipna=True)


def market_risk_off(
    prices_hist: pd.DataFrame,
    ma_window: int = 50,
    dd_threshold: float = 0.10,
) -> bool:
    """True when the market is in a confirmed downtrend on the decision day.

    Risk-off if either:
    - the equal-weight market index sits below its `ma_window`-day SMA
      (requires at least `ma_window` index observations), or
    - the index is more than `dd_threshold` below its running peak
      (computable from any history length).

    With no data (or no computable signal) returns False — the gate only
    fires on positive evidence of a downtrend.
    """
    if len(prices_hist) == 0 or prices_hist.shape[1] == 0:
        return False
    idx = market_index(prices_hist.sort_index()).dropna()
    if len(idx) == 0:
        return False

    last = float(idx.iloc[-1])

    drawdown = last / float(idx.cummax().iloc[-1]) - 1.0
    if drawdown < -dd_threshold:
        return True

    if len(idx) >= ma_window:
        ma = float(idx.rolling(ma_window).mean().iloc[-1])
        if last < ma:
            return True

    return False
