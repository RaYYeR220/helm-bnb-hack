import httpx
import pandas as pd
import respx

from helm.data.geckoterminal import GeckoTerminalAdapter

BASE = "https://api.geckoterminal.com/api/v2"


def _pools_body():
    # Two pools; the SECOND has the higher reserve_in_usd (strings, as live).
    # The chosen pool id has the 'bsc_' prefix that must be stripped.
    return {
        "data": [
            {
                "id": "bsc_0x7f51c8aaa6b0599abd16674e2b17fec7a9f674a1",
                "type": "pool",
                "attributes": {
                    "address": "0x7f51c8aaa6b0599abd16674e2b17fec7a9f674a1",
                    "reserve_in_usd": "4117702.8356",
                    "volume_usd": {"h1": "2411.04", "h24": "796963.43"},
                },
            },
            {
                "id": "bsc_0x0ed7e52944161450477ee417de9cd3a859b14fd0",
                "type": "pool",
                "attributes": {
                    "address": "0x0ed7e52944161450477ee417de9cd3a859b14fd0",
                    "reserve_in_usd": "13748889.202",
                    "volume_usd": {"h1": "8449.98", "h24": "307522.16"},
                },
            },
        ]
    }


def _ohlcv_body():
    # data.attributes.ohlcv_list, candles NEWEST-FIRST (descending ts), unix s.
    # 1781136000 -> 2026-06-11, 1781049600 -> 2026-06-10, 1780963200 -> 2026-06-09.
    return {
        "data": {
            "id": "...",
            "type": "ohlcv_request_response",
            "attributes": {
                "ohlcv_list": [
                    [1781136000, 1.2927, 1.3253, 1.2925, 1.3051, 120388.39],
                    [1781049600, 1.3098, 1.3279, 1.2769, 1.2888, 290191.36],
                    [1780963200, 1.3139, 1.3492, 1.2727, 1.3098, 390334.71],
                ]
            },
        },
        "meta": {"base": {"symbol": "Cake"}, "quote": {"symbol": "WBNB"}},
    }


@respx.mock
def test_token_top_pool_picks_highest_reserve_and_strips_prefix():
    respx.get(
        f"{BASE}/networks/bsc/tokens/0xCAKE/pools"
    ).mock(return_value=httpx.Response(200, json=_pools_body()))
    a = GeckoTerminalAdapter(min_interval_s=0)
    pool = a.token_top_pool("0xCAKE")
    # the SECOND pool wins on reserve; prefix 'bsc_' stripped from the id
    assert pool["pool_address"] == "0x0ed7e52944161450477ee417de9cd3a859b14fd0"
    assert pool["reserve_usd"] == 13748889.202   # parsed from string
    assert pool["volume_24h"] == 307522.16       # h24 string -> float


@respx.mock
def test_token_top_pool_none_when_no_pools():
    respx.get(f"{BASE}/networks/bsc/tokens/0xNONE/pools").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    assert GeckoTerminalAdapter(min_interval_s=0).token_top_pool("0xNONE") is None


@respx.mock
def test_pool_ohlcv_daily_parses_envelope_and_sorts_ascending():
    respx.get(
        f"{BASE}/networks/bsc/pools/0xPOOL/ohlcv/day"
    ).mock(return_value=httpx.Response(200, json=_ohlcv_body()))
    df = GeckoTerminalAdapter(min_interval_s=0).pool_ohlcv_daily("0xPOOL")
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.tz is None
    # NEWEST-FIRST input must come out OLDEST-FIRST (ascending)
    assert list(df.index) == list(
        pd.to_datetime(["2026-06-09", "2026-06-10", "2026-06-11"])
    )
    assert df["close"].iloc[-1] == 1.3051   # the 2026-06-11 close
    assert df["volume"].iloc[0] == 390334.71  # the 2026-06-09 volume


@respx.mock
def test_pool_ohlcv_daily_empty_list_returns_empty_df():
    respx.get(f"{BASE}/networks/bsc/pools/0xPOOL/ohlcv/day").mock(
        return_value=httpx.Response(
            200, json={"data": {"attributes": {"ohlcv_list": []}}}
        )
    )
    df = GeckoTerminalAdapter(min_interval_s=0).pool_ohlcv_daily("0xPOOL")
    assert df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


@respx.mock
def test_ohlcv_limit_param_is_passed_through():
    captured = {}

    def _capture(request):
        captured["url"] = str(request.url)
        return httpx.Response(200, json=_ohlcv_body())

    respx.get(f"{BASE}/networks/bsc/pools/0xPOOL/ohlcv/day").mock(side_effect=_capture)
    GeckoTerminalAdapter(min_interval_s=0).pool_ohlcv_daily("0xPOOL", limit=182)
    assert "limit=182" in captured["url"]
    assert "aggregate=1" in captured["url"]


def test_default_min_interval_is_three_seconds():
    # documents the free-tier safe cadence without making a network call
    a = GeckoTerminalAdapter()
    assert a.min_interval_s == 3.0


@respx.mock
def test_429_is_retried_with_backoff_then_succeeds():
    addr = "0x2170ed0880ac9a755fd29b2688956bd959f933f8"
    route = respx.get(f"{BASE}/networks/bsc/tokens/{addr}/pools").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json=_pools_body()),
        ]
    )
    gt = GeckoTerminalAdapter(min_interval_s=0, backoff_s=0)
    pool = gt.token_top_pool(addr)
    assert route.call_count == 2
    assert pool is not None


@respx.mock
def test_429_exhausts_retries_then_raises():
    addr = "0x2170ed0880ac9a755fd29b2688956bd959f933f8"
    respx.get(f"{BASE}/networks/bsc/tokens/{addr}/pools").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"})
    )
    gt = GeckoTerminalAdapter(min_interval_s=0, backoff_s=0, max_retries=2)
    import pytest as _pytest
    with _pytest.raises(httpx.HTTPStatusError):
        gt.token_top_pool(addr)
