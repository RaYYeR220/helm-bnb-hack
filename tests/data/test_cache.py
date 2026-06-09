import pandas as pd

from helm.data.cache import OHLCVCache, build_price_panel


def _ohlcv(closes, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(closes), freq="D")
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": [1.0] * len(closes)},
        index=idx,
    )


def test_cache_put_get_roundtrip(tmp_path):
    cache = OHLCVCache(root=tmp_path)
    df = _ohlcv([1.0, 2.0, 3.0])
    assert cache.get("ETH") is None
    cache.put("ETH", df)
    loaded = cache.get("ETH")
    assert loaded is not None
    assert list(loaded["close"]) == [1.0, 2.0, 3.0]


def test_build_price_panel_uses_cache_then_adapter(tmp_path):
    cache = OHLCVCache(root=tmp_path)
    cache.put("ETH", _ohlcv([10.0, 11.0, 12.0]))

    class FakeAdapter:
        def __init__(self):
            self.calls = []

        def ohlcv_historical(self, symbol, start, end, **kw):
            self.calls.append(symbol)
            return _ohlcv([5.0, 6.0, 7.0])

    adapter = FakeAdapter()
    panel = build_price_panel(["ETH", "CAKE"], adapter, cache, "2024-01-01", "2024-01-03")
    # ETH served from cache (no adapter call), CAKE fetched
    assert adapter.calls == ["CAKE"]
    assert list(panel.columns) == ["ETH", "CAKE"]
    assert panel["ETH"].iloc[0] == 10.0
    assert panel["CAKE"].iloc[0] == 5.0
    # CAKE now cached
    assert cache.get("CAKE") is not None


def test_build_price_panel_skips_failed_symbols(tmp_path):
    cache = OHLCVCache(root=tmp_path)

    class FlakyAdapter:
        def ohlcv_historical(self, symbol, start, end, **kw):
            if symbol == "BAD":
                raise RuntimeError("no data")
            return _ohlcv([1.0, 2.0, 3.0])

    panel = build_price_panel(["ETH", "BAD"], FlakyAdapter(), cache, "2024-01-01", "2024-01-03")
    assert "ETH" in panel.columns
    assert "BAD" not in panel.columns
