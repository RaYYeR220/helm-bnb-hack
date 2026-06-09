import numpy as np
import pandas as pd
import pytest

from helm.backtest.metrics import (
    sharpe,
    sortino,
    max_drawdown,
    win_rate,
    turnover,
    compute_metrics,
)


def test_sharpe_zero_for_constant_returns():
    r = pd.Series([0.0, 0.0, 0.0, 0.0])
    assert sharpe(r) == 0.0


def test_sharpe_zero_volatility_guarded():
    r = pd.Series([0.01] * 100)
    # zero volatility -> guarded to 0.0 (avoid div-by-zero)
    assert sharpe(r) == 0.0


def test_sharpe_is_float_for_noisy_series():
    noisy = pd.Series(np.random.default_rng(0).normal(0.001, 0.01, 500))
    assert isinstance(sharpe(noisy), float)


def test_max_drawdown_simple():
    equity = pd.Series([100, 120, 90, 110])  # peak 120 -> trough 90
    assert max_drawdown(equity) == pytest.approx(-0.25)


def test_win_rate():
    r = pd.Series([0.01, -0.02, 0.03, 0.0, -0.01])
    # wins = strictly positive = 2 of 5
    assert win_rate(r) == 0.4


def test_turnover_of_constant_weights_is_zero():
    w = pd.DataFrame({"A": [0.5, 0.5], "B": [0.5, 0.5]})
    assert turnover(w) == 0.0


def test_compute_metrics_returns_expected_keys():
    equity = pd.Series([100.0, 101.0, 102.0, 101.0, 103.0])
    returns = equity.pct_change().dropna()
    weights = pd.DataFrame({"A": [1.0, 1.0, 1.0, 1.0]})
    m = compute_metrics(equity, returns, weights)
    for k in ("sharpe", "sortino", "max_drawdown", "win_rate", "turnover", "total_return"):
        assert k in m
