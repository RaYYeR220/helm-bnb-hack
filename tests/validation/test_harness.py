import numpy as np
import pandas as pd
import pytest

from helm.validation.harness import (
    evaluate_windows,
    select_config,
    slice_window_metrics,
)
from helm.validation.windows import walk_forward_windows


def _index(n, start="2020-01-01"):
    return pd.date_range(start, periods=n, freq="D")


# --- slice_window_metrics -----------------------------------------------------

def test_slice_window_metrics_total_return_matches_hand_computation():
    idx = _index(10)
    rets = pd.Series(
        [np.nan, 0.01, -0.02, 0.03, 0.0, 0.01, -0.01, 0.02, 0.0, 0.01], index=idx
    )
    window = idx[2:7]  # values [-0.02, 0.03, 0.0, 0.01, -0.01]
    m = slice_window_metrics(rets, 1.0, window)
    # 0.98 * 1.03 * 1.0 * 1.01 * 0.99 - 1 == 0.00929906
    assert m["n_days"] == 5
    assert m["total_return"] == pytest.approx(0.00929906, abs=1e-8)
    assert set(m) == {"total_return", "sharpe", "sortino", "max_drawdown", "n_days"}


def test_slice_window_metrics_empty_window_is_zeroed():
    idx = _index(10)
    rets = pd.Series([np.nan] + [0.01] * 9, index=idx)
    # a window of dates not present in returns
    foreign = pd.date_range("2030-01-01", periods=3, freq="D")
    m = slice_window_metrics(rets, 1.0, foreign)
    assert m["n_days"] == 0
    assert m["total_return"] == 0.0
    assert m["sharpe"] == 0.0


# --- evaluate_windows ---------------------------------------------------------

def test_evaluate_windows_one_row_per_window_on_test_idx_only():
    idx = _index(100)
    rng = np.random.default_rng(0)
    rets = pd.Series([np.nan] + list(rng.normal(0.001, 0.01, 99)), index=idx)
    wins = walk_forward_windows(idx, n_windows=4, embargo=5)
    df = evaluate_windows(rets, wins)
    assert len(df) == 4
    assert list(df.columns) == [
        "window_id", "test_start", "test_end", "n_days",
        "total_return", "sharpe", "sortino", "max_drawdown",
    ]
    assert df["window_id"].tolist() == [0, 1, 2, 3]
    # the leading day-0 NaN (mirrors real engine output) is dropped by the
    # metric slice, so window 0 sees 24 return days; the rest see a full 25.
    assert df["n_days"].tolist() == [24, 25, 25, 25]


# --- select_config ------------------------------------------------------------

def _ab_configs(idx):
    n = len(idx)
    # A wins the early train, B wins the later (longer) train after a regime flip.
    a = np.where(np.arange(n) < 30, 0.01, -0.02)
    b = np.where(np.arange(n) < 30, -0.005, 0.02)
    jit = 0.0005 * np.sin(np.arange(n) * 1.3)  # deterministic finite vol
    return {
        "A": pd.Series(a + jit, index=idx),
        "B": pd.Series(b + jit, index=idx),
    }


def test_select_config_switches_per_train_window():
    idx = _index(90)
    configs = _ab_configs(idx)
    wins = walk_forward_windows(idx, n_windows=3, embargo=5)  # 30/window
    out = select_config(configs, wins, metric="sharpe")
    per = out["per_window"]
    # window 0 has empty train -> skipped; windows 1 and 2 are evaluated
    assert per["window_id"].tolist() == [1, 2]
    # window 1's train (early) favors A; window 2's train (post-flip) favors B
    assert per.set_index("window_id").loc[1, "chosen"] == "A"
    assert per.set_index("window_id").loc[2, "chosen"] == "B"
    assert out["n_trials"] == 2
    assert set(out["oos"]) >= {"sharpe", "total_return", "max_drawdown"}


def test_select_config_oos_differs_from_naive_in_sample_best():
    idx = _index(90)
    configs = _ab_configs(idx)
    wins = walk_forward_windows(idx, n_windows=3, embargo=5)
    out = select_config(configs, wins, metric="sharpe")
    # In window 1 the selector picks A but A bleeds out-of-sample (post-flip),
    # so the OOS mean is dragged down below B's strong late performance: the
    # honest estimate is NOT the in-sample champion's number.
    per = out["per_window"].set_index("window_id")
    assert per.loc[1, "total_return"] < 0       # A picked, but loses OOS
    assert per.loc[2, "total_return"] > 0       # B picked and wins OOS
    assert out["oos"]["total_return"] != per.loc[2, "total_return"]


def test_select_config_skips_windows_with_empty_train():
    idx = _index(90)
    configs = _ab_configs(idx)
    wins = walk_forward_windows(idx, n_windows=3, embargo=5)
    out = select_config(configs, wins, metric="sharpe")
    # 3 windows, window 0 has empty train -> only 2 rows
    assert len(out["per_window"]) == 2
