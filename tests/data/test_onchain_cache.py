import pandas as pd
import pytest

from helm.data.onchain_cache import OnchainCache, build_onchain_features


def _chain_series():
    idx = pd.date_range("2024-01-01", periods=30, freq="D")
    return pd.Series(
        [100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
         110, 111, 112, 113, 114, 115, 116, 117, 118, 119,
         120, 121, 122, 118, 114, 110, 106, 102, 100, 99],
        index=idx, dtype=float, name="tvl",
    )


def _pancake_series():
    idx = pd.date_range("2024-01-01", periods=30, freq="D")
    return pd.Series(
        [40, 40, 41, 41, 42, 42, 43, 43, 44, 44,
         45, 45, 46, 46, 47, 47, 48, 48, 49, 49,
         50, 50, 51, 49, 47, 45, 43, 41, 40, 39],
        index=idx, dtype=float, name="protocol_tvl",
    )


class _FakeAdapter:
    """Counts how often each TVL series is fetched (to prove cache-first)."""

    def __init__(self):
        self.chain_calls = 0
        self.protocol_calls = 0

    def chain_tvl(self, chain="BSC"):
        self.chain_calls += 1
        return _chain_series()

    def protocol_chain_tvl(self, protocol="pancakeswap-amm", chain_key="Binance"):
        self.protocol_calls += 1
        return _pancake_series()


def test_features_hand_computed_values(tmp_path):
    cache = OnchainCache(root=tmp_path)
    index = _chain_series().index
    feats = build_onchain_features(_FakeAdapter(), cache, index)
    assert list(feats.columns) == ["tvl_mom20", "tvl_dd", "pancake_share_mom20"]
    assert feats.index.equals(index)
    r20 = feats.iloc[20]
    assert r20["tvl_mom20"] == pytest.approx(0.2, abs=1e-9)
    assert r20["tvl_dd"] == pytest.approx(0.0, abs=1e-9)
    assert r20["pancake_share_mom20"] == pytest.approx(0.0416666667, abs=1e-7)
    r29 = feats.iloc[29]
    assert r29["tvl_mom20"] == pytest.approx(-0.0917431193, abs=1e-7)
    assert r29["tvl_dd"] == pytest.approx(-0.1885245902, abs=1e-7)
    assert r29["pancake_share_mom20"] == pytest.approx(-0.0241046832, abs=1e-7)


def test_features_are_finite_with_leading_zeros(tmp_path):
    cache = OnchainCache(root=tmp_path)
    index = _chain_series().index
    feats = build_onchain_features(_FakeAdapter(), cache, index)
    # ffill().fillna(0.0): leading mom rows (pos < 20) are 0, drawdown at t0 is 0
    assert feats.isna().sum().sum() == 0
    assert feats.iloc[0]["tvl_mom20"] == 0.0
    assert feats.iloc[0]["pancake_share_mom20"] == 0.0
    assert feats.iloc[0]["tvl_dd"] == 0.0


def test_features_reindex_to_a_finer_panel_index_ffill(tmp_path):
    cache = OnchainCache(root=tmp_path)
    # a panel index that EXTENDS one day past the TVL data -> ffill-to-last-known
    index = pd.date_range("2024-01-01", periods=31, freq="D")
    feats = build_onchain_features(_FakeAdapter(), cache, index)
    assert feats.index.equals(index)
    # the extra trailing day carries the last known feature values (ffill)
    assert feats.iloc[30]["tvl_dd"] == pytest.approx(feats.iloc[29]["tvl_dd"], abs=1e-12)


def test_cache_first_avoids_refetch(tmp_path):
    cache = OnchainCache(root=tmp_path)
    index = _chain_series().index
    adapter = _FakeAdapter()
    build_onchain_features(adapter, cache, index)
    assert adapter.chain_calls == 1
    assert adapter.protocol_calls == 1
    # second build reads from cache, no new fetches
    build_onchain_features(adapter, cache, index)
    assert adapter.chain_calls == 1
    assert adapter.protocol_calls == 1


def test_cache_series_roundtrip(tmp_path):
    cache = OnchainCache(root=tmp_path)
    assert cache.get_series("bsc_tvl") is None
    cache.put_series("bsc_tvl", _chain_series())
    loaded = cache.get_series("bsc_tvl")
    assert loaded is not None
    assert loaded.name == "tvl"
    assert list(loaded.values) == list(_chain_series().values)
