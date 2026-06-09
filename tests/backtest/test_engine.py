import pytest
import numpy as np
import pandas as pd

from helm.backtest.engine import run_backtest
from helm.backtest.result import BacktestConfig
from helm.strategies.baselines import EqualWeight


def test_single_asset_compounds_without_fees():
    # one asset, +1%/day; equal-weight holds it fully; zero costs
    idx = pd.date_range("2024-01-01", periods=11, freq="D")
    prices = pd.DataFrame({"A": [100 * (1.01 ** i) for i in range(11)]}, index=idx)
    cfg = BacktestConfig(fee_bps=0.0, slippage_bps=0.0, initial_capital=100.0)
    res = run_backtest(prices, EqualWeight(), cfg)
    # 10 holding periods of +1%
    expected = 100.0 * (1.01 ** 10)
    assert abs(res.equity.iloc[-1] - expected) < 1e-6
    assert res.strategy_name == "equal_weight"


def test_fees_reduce_equity_on_turnover():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    prices = pd.DataFrame({"A": [100.0] * 5}, index=idx)  # flat prices
    no_fee = run_backtest(prices, EqualWeight(), BacktestConfig(fee_bps=0, slippage_bps=0, initial_capital=100.0))
    with_fee = run_backtest(prices, EqualWeight(), BacktestConfig(fee_bps=50, slippage_bps=0, initial_capital=100.0))
    # flat prices: no-fee equity stays 100; fee version pays the initial allocation cost
    assert abs(no_fee.equity.iloc[-1] - 100.0) < 1e-9
    assert with_fee.equity.iloc[-1] < 100.0


def test_metrics_attached():
    idx = pd.date_range("2024-01-01", periods=20, freq="D")
    rng = np.random.default_rng(0)
    prices = pd.DataFrame({"A": 100 * np.cumprod(1 + rng.normal(0.001, 0.01, 20))}, index=idx)
    res = run_backtest(prices, EqualWeight(), BacktestConfig())
    assert "sharpe" in res.metrics
    assert "max_drawdown" in res.metrics
    assert len(res.equity) == 20
    assert isinstance(res.metrics["sharpe"], float)
    assert res.metrics["max_drawdown"] <= 0.0
    assert 0.0 <= res.metrics["win_rate"] <= 1.0


def test_empty_panel_raises():
    with pytest.raises(ValueError):
        run_backtest(pd.DataFrame(), EqualWeight())
