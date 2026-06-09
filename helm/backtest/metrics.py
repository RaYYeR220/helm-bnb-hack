"""Backtest performance metrics. All functions are pure and deterministic."""

import numpy as np
import pandas as pd

PERIODS_PER_YEAR = 365  # crypto trades every day


def sharpe(returns: pd.Series, periods_per_year: int = PERIODS_PER_YEAR) -> float:
    """Annualized Sharpe ratio. Returns 0.0 when volatility is zero."""
    r = returns.dropna()
    if len(r) == 0:
        return 0.0
    sd = r.std(ddof=1)  # sample std — standard Sharpe convention
    if sd == 0 or np.isnan(sd) or sd < 1e-12:
        return 0.0
    return float(np.sqrt(periods_per_year) * r.mean() / sd)


def sortino(returns: pd.Series, periods_per_year: int = PERIODS_PER_YEAR) -> float:
    """Annualized Sortino ratio (downside deviation). 0.0 when no downside."""
    r = returns.dropna()
    if len(r) == 0:
        return 0.0
    downside = r[r < 0]
    dd = downside.std(ddof=1)  # sample downside deviation
    if dd == 0 or np.isnan(dd):
        return 0.0
    return float(np.sqrt(periods_per_year) * r.mean() / dd)


def max_drawdown(equity: pd.Series) -> float:
    """Largest peak-to-trough decline, as a negative fraction (e.g. -0.25)."""
    eq = equity.dropna()
    if len(eq) == 0:
        return 0.0
    running_peak = eq.cummax()
    drawdown = eq / running_peak - 1.0
    return float(drawdown.min())


def win_rate(returns: pd.Series) -> float:
    """Fraction of periods with strictly positive return."""
    r = returns.dropna()
    if len(r) == 0:
        return 0.0
    return float((r > 0).sum() / len(r))


def turnover(weights: pd.DataFrame) -> float:
    """Average one-sided turnover per rebalance (sum of |Δweight| across names)."""
    if len(weights) < 2:
        return 0.0
    deltas = weights.fillna(0.0).diff().abs().sum(axis=1)
    return float(deltas.iloc[1:].mean())


def compute_metrics(
    equity: pd.Series, returns: pd.Series, weights: pd.DataFrame
) -> dict:
    """Bundle the full metric suite into a JSON-serializable dict."""
    eq = equity.dropna()
    total_return = float(eq.iloc[-1] / eq.iloc[0] - 1.0) if len(eq) >= 2 else 0.0
    return {
        "sharpe": sharpe(returns),
        "sortino": sortino(returns),
        "max_drawdown": max_drawdown(equity),
        "win_rate": win_rate(returns),
        "turnover": turnover(weights),
        "total_return": total_return,
    }
