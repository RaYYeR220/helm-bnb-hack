"""Evaluation/selection harness — one backtest per config, then slice.

CAUSALITY ARGUMENT (why no per-window refit, no estimator purging):

``compute_regime_path`` labels each day t using only data <= t, and
``run_backtest`` recomputes target weights every day from the price history
through t-1. Therefore the per-day net return on day t is IDENTICAL no matter
where the backtest run ends — the run is a pure causal replay. We can run ONE
full-panel backtest per strategy/config and SLICE the resulting per-day return
Series into evaluation windows; there is no leakage from "future" rows into a
window's returns because no future row ever touched them. Classic CPCV "purging"
of estimator leakage is thus structurally unnecessary for PATH EVALUATION.

Purge/embargo mechanics still matter for CONFIG SELECTION: if we choose a config
(e.g. a gate-hysteresis setting) by looking at some windows, we must REPORT it on
disjoint, embargoed windows, or we are just curve-fitting. ``select_config`` does
exactly that — it picks the best config on each TRAIN window and records that
config's TEST-window metrics, yielding an honest out-of-sample estimate of the
selection procedure itself. That is the harness's real job.
"""

import numpy as np
import pandas as pd

from helm.backtest.metrics import max_drawdown, sharpe, sortino

_METRICS = ("total_return", "sharpe", "sortino", "max_drawdown")


def slice_window_metrics(
    returns: pd.Series, equity_start: float, window: pd.DatetimeIndex
) -> dict:
    """Metrics of ``returns`` restricted to ``window``, on a rebuilt equity path.

    Slices the per-day return Series to the window dates (dropping NaN / absent
    dates), compounds an equity path from ``equity_start``, and returns
    ``total_return``, ``sharpe``, ``sortino``, ``max_drawdown`` (via the existing
    ``helm.backtest.metrics`` functions) plus ``n_days``. An empty slice returns
    zeros.
    """
    r = returns.reindex(window).dropna()
    n = len(r)
    if n == 0:
        return {
            "total_return": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "max_drawdown": 0.0,
            "n_days": 0,
        }
    equity = equity_start * (1.0 + r).cumprod()
    total_return = float(equity.iloc[-1] / equity_start - 1.0)
    return {
        "total_return": total_return,
        "sharpe": sharpe(r),
        "sortino": sortino(r),
        "max_drawdown": max_drawdown(equity),
        "n_days": n,
    }


def evaluate_windows(
    returns: pd.Series, windows: list[tuple]
) -> pd.DataFrame:
    """One row per ``(train, test)`` pair: TEST-window metrics of ``returns``.

    Train indices are ignored here (pure evaluation, not selection). Columns:
    ``window_id, test_start, test_end, n_days, total_return, sharpe, sortino,
    max_drawdown``.
    """
    rows: list[dict] = []
    for wid, (_, test_idx) in enumerate(windows):
        m = slice_window_metrics(returns, 1.0, test_idx)
        rows.append(
            {
                "window_id": wid,
                "test_start": (test_idx[0] if len(test_idx) else pd.NaT),
                "test_end": (test_idx[-1] if len(test_idx) else pd.NaT),
                "n_days": m["n_days"],
                "total_return": m["total_return"],
                "sharpe": m["sharpe"],
                "sortino": m["sortino"],
                "max_drawdown": m["max_drawdown"],
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "window_id", "test_start", "test_end", "n_days",
            "total_return", "sharpe", "sortino", "max_drawdown",
        ],
    )


def _train_score(returns: pd.Series, train_idx: pd.DatetimeIndex, metric: str) -> float:
    """Mean ``metric`` of a config over the train window (slice then score)."""
    r = returns.reindex(train_idx).dropna()
    if len(r) == 0:
        return float("-inf")
    m = slice_window_metrics(returns, 1.0, train_idx)
    return float(m.get(metric, float("-inf")))


def select_config(
    configs: dict[str, pd.Series],
    windows: list[tuple],
    metric: str = "sharpe",
) -> dict:
    """Pick the best config per TRAIN window, report its TEST-window metrics.

    ``configs`` maps config-name -> full-panel per-day return Series. For each
    ``(train, test)`` window: skip the window if its train index is empty; else
    choose the config with the best ``metric`` over the TRAIN dates and record
    that config's TEST-window metrics. Returns:

    - ``per_window``: DataFrame(window_id, chosen, n_days, total_return, sharpe,
      sortino, max_drawdown) on the TEST idx for the chosen config.
    - ``oos``: aggregate dict with mean/median of each metric over the windows.
    - ``n_trials``: ``len(configs)`` (the honest trial count for the DSR).
    """
    rows: list[dict] = []
    for wid, (train_idx, test_idx) in enumerate(windows):
        if len(train_idx) == 0:
            continue
        best_name = None
        best_score = float("-inf")
        for name, returns in configs.items():
            score = _train_score(returns, train_idx, metric)
            if score > best_score:
                best_score = score
                best_name = name
        if best_name is None:
            continue
        test_m = slice_window_metrics(configs[best_name], 1.0, test_idx)
        rows.append(
            {
                "window_id": wid,
                "chosen": best_name,
                "n_days": test_m["n_days"],
                "total_return": test_m["total_return"],
                "sharpe": test_m["sharpe"],
                "sortino": test_m["sortino"],
                "max_drawdown": test_m["max_drawdown"],
            }
        )
    per = pd.DataFrame(
        rows,
        columns=[
            "window_id", "chosen", "n_days",
            "total_return", "sharpe", "sortino", "max_drawdown",
        ],
    )
    oos: dict = {}
    if len(per):
        for m in _METRICS:
            oos[m] = float(per[m].mean())
            oos[f"{m}_median"] = float(per[m].median())
    return {"per_window": per, "oos": oos, "n_trials": len(configs)}
