import numpy as np
import pandas as pd

from helm.backtest.attribution import regime_pnl_attribution


def test_buckets_days_and_compounds_per_regime():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    # day 0 has no return period (NaN), like a BacktestResult.returns series
    returns = pd.Series([np.nan, 0.10, -0.05, 0.02, 0.03], index=idx)
    regime_path = pd.Series(
        ["trending", "trending", "ranging", "trending", "ranging"], index=idx
    )
    out = regime_pnl_attribution(returns, regime_path)

    # trending: days 1 and 3 (NaN day 0 is dropped) -> r = 0.10, 0.02
    assert out["trending"]["days"] == 2
    expected_trending = (1.10 * 1.02) - 1.0
    assert abs(out["trending"]["total_return"] - expected_trending) < 1e-9
    assert abs(out["trending"]["mean_return"] - np.mean([0.10, 0.02])) < 1e-9

    # ranging: days 2 and 4 -> r = -0.05, 0.03
    assert out["ranging"]["days"] == 2
    expected_ranging = (0.95 * 1.03) - 1.0
    assert abs(out["ranging"]["total_return"] - expected_ranging) < 1e-9


def test_unclassified_bucket_for_dates_without_a_label():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.Series([np.nan, 0.01, 0.02, 0.03], index=idx)
    # regime path only labels the first two real-return days (idx[1], idx[2])
    regime_path = pd.Series(["trending", "trending"], index=idx[1:3])
    out = regime_pnl_attribution(returns, regime_path)
    # idx[3] has a return but no label -> "unclassified"
    assert "unclassified" in out
    assert out["unclassified"]["days"] == 1
    assert abs(out["unclassified"]["total_return"] - 0.03) < 1e-9


def test_share_of_pnl_sums_to_one_across_buckets():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.Series([np.nan, 0.10, 0.10, 0.10], index=idx)
    regime_path = pd.Series(["trending", "ranging", "trending"], index=idx[:3])
    out = regime_pnl_attribution(returns, regime_path)
    shares = sum(v["share_of_pnl"] for v in out.values())
    assert abs(shares - 1.0) < 1e-9


def test_empty_returns_yields_empty_dict():
    out = regime_pnl_attribution(pd.Series(dtype=float), pd.Series(dtype=object))
    assert out == {}
