"""Portfolio backtest engine: daily cross-sectional replay with costs.

Timing convention (no look-ahead): on each day t >= 1 we form target weights
from prices through day t-1, then earn the close-to-close return from t-1 to t.
Turnover (vs the previous target) is charged at (fee_bps + slippage_bps).
"""

import pandas as pd

from helm.backtest.metrics import compute_metrics
from helm.backtest.result import BacktestConfig, BacktestResult
from helm.strategies.base import Strategy


def run_backtest(
    prices: pd.DataFrame, strategy: Strategy, config: BacktestConfig | None = None
) -> BacktestResult:
    config = config or BacktestConfig()
    prices = prices.sort_index()
    if prices.shape[0] < 2 or prices.shape[1] == 0:
        raise ValueError(
            "run_backtest needs a price panel with >=2 dates and >=1 symbol; "
            f"got shape {prices.shape} (no symbols had data for the window?)."
        )
    dates = prices.index
    cost_rate = (config.fee_bps + config.slippage_bps) / 10_000.0

    n_cols = prices.shape[1]
    prev_w = pd.Series(0.0, index=prices.columns)

    equity_vals: list[float] = [config.initial_capital]
    period_returns: list[float] = [float("nan")]   # day-0 has no return period
    weight_rows: list[pd.Series] = [prev_w.copy()]
    trade_rows: list[dict] = []

    equity = config.initial_capital
    for t in range(1, len(dates)):
        hist = prices.iloc[:t]                     # through day t-1
        w = strategy.target_weights(hist).reindex(prices.columns).fillna(0.0)

        turn = float((w - prev_w).abs().sum())
        cost = turn * cost_rate

        asset_ret = (prices.iloc[t] / prices.iloc[t - 1] - 1.0).fillna(0.0)
        gross = float((w * asset_ret).sum())
        net = gross - cost
        equity *= (1.0 + net)

        equity_vals.append(equity)
        period_returns.append(net)
        weight_rows.append(w.copy())
        if turn > 0:
            trade_rows.append({"date": dates[t].strftime("%Y-%m-%d"), "turnover": turn, "cost": cost})
        prev_w = w

    equity_s = pd.Series(equity_vals, index=dates, name="equity")
    returns_s = pd.Series(period_returns, index=dates, name="returns")
    weights_df = pd.DataFrame(weight_rows, index=dates)
    trades_df = pd.DataFrame(trade_rows)

    metrics = compute_metrics(equity_s, returns_s, weights_df)
    return BacktestResult(
        equity=equity_s,
        returns=returns_s,
        weights=weights_df,
        trades=trades_df,
        metrics=metrics,
        strategy_name=strategy.name,
        meta={"n_assets": n_cols, "fee_bps": config.fee_bps, "slippage_bps": config.slippage_bps},
    )
