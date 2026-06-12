import numpy as np
import pandas as pd
import pytest

from helm.data.onchain_cache import OnchainCache, build_flow_features


class _FakeCache:
    """In-memory cache exposing get_series, matching OnchainCache's contract."""

    def __init__(self, series: dict):
        self._d = dict(series)

    def get_series(self, key):
        return self._d.get(key)


def _series(vals, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(vals), freq="D")
    return pd.Series(vals, index=idx, dtype=float)


def test_columns_and_finite_output():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    cache = _FakeCache(
        {
            "whaleflow_AAA": _series([10, 12, 14, 16]),
            "cexflow_AAA": _series([1.0, -1.0, 2.0, -2.0]),
        }
    )
    feats = build_flow_features(cache, idx, ["AAA"], z_window=3, min_periods=2)
    assert list(feats.columns) == ["net_whale_flow_z", "net_cex_flow_z"]
    assert feats.index.equals(idx)
    assert feats.isna().sum().sum() == 0
    assert np.isfinite(feats.to_numpy()).all()


def test_whale_z_hand_computed_single_symbol():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    cache = _FakeCache({"whaleflow_AAA": _series([10, 12, 14, 16])})
    feats = build_flow_features(cache, idx, ["AAA"], z_window=3, min_periods=2)
    # trailing window [12,14,16] -> mean 14, sample std 2.0 -> z = (16-14)/2 = 1.0
    assert feats.iloc[3]["net_whale_flow_z"] == pytest.approx(1.0, abs=1e-9)


def test_market_aggregate_is_cross_sectional_mean():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    # two symbols; the market series is the row-wise mean before z-scoring
    cache = _FakeCache(
        {
            "whaleflow_AAA": _series([10, 12, 14, 16]),
            "whaleflow_BBB": _series([20, 22, 24, 26]),  # mean with AAA: [15,17,19,21]
        }
    )
    feats = build_flow_features(cache, idx, ["AAA", "BBB"], z_window=3, min_periods=2)
    # market mean [15,17,19,21]; trailing [17,19,21] mean 19 std 2.0 -> z=(21-19)/2=1.0
    assert feats.iloc[3]["net_whale_flow_z"] == pytest.approx(1.0, abs=1e-9)


def test_missing_symbols_tolerated():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    # only AAA cached; BBB/CCC absent -> aggregate over AAA alone, no crash
    cache = _FakeCache({"whaleflow_AAA": _series([10, 12, 14, 16])})
    feats = build_flow_features(cache, idx, ["AAA", "BBB", "CCC"], z_window=3, min_periods=2)
    assert feats.isna().sum().sum() == 0
    assert feats.iloc[3]["net_whale_flow_z"] == pytest.approx(1.0, abs=1e-9)


def test_no_data_at_all_returns_zero_frame():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    feats = build_flow_features(_FakeCache({}), idx, ["AAA"], z_window=3, min_periods=2)
    assert list(feats.columns) == ["net_whale_flow_z", "net_cex_flow_z"]
    assert (feats.to_numpy() == 0.0).all()


def test_causal_no_look_ahead_truncation_invariance():
    # the z at a fixed date must not change if future rows are appended.
    full_vals = [10, 12, 14, 16, 50, 5]  # a future spike at the tail
    idx_full = pd.date_range("2024-01-01", periods=6, freq="D")
    cache_full = _FakeCache({"whaleflow_AAA": _series(full_vals)})
    feats_full = build_flow_features(
        cache_full, idx_full, ["AAA"], z_window=3, min_periods=2
    )
    # truncate to the first 4 days
    idx_tr = idx_full[:4]
    cache_tr = _FakeCache({"whaleflow_AAA": _series(full_vals[:4])})
    feats_tr = build_flow_features(cache_tr, idx_tr, ["AAA"], z_window=3, min_periods=2)
    # the z at day index 3 is identical with or without the future spike
    assert feats_full.iloc[3]["net_whale_flow_z"] == pytest.approx(
        feats_tr.iloc[3]["net_whale_flow_z"], abs=1e-12
    )
