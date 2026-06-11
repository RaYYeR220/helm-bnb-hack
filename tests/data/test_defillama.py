import httpx
import pandas as pd
import respx

from helm.data.defillama import DefiLlamaAdapter

BASE = "https://api.llama.fi"


def _chain_tvl_body():
    # unix-second dates: 1604016000 -> 2020-10-30, 1604102400 -> 2020-10-31,
    # 1604188800 -> 2020-11-01. Deliberately OUT OF ORDER with a duplicate date
    # to exercise sort + dedup-keep-last.
    return [
        {"date": 1604102400, "tvl": 13000000},
        {"date": 1604016000, "tvl": 12873962},
        {"date": 1604188800, "tvl": 14000000},
        {"date": 1604188800, "tvl": 14500000},  # dup of 2020-11-01 -> keep last
    ]


def _protocol_body():
    return {
        "id": "1",
        "name": "PancakeSwap AMM",
        "chainTvls": {
            "Binance": {
                "tvl": [
                    {"date": 1619049600, "totalLiquidityUSD": 598},
                    {"date": 1619136000, "totalLiquidityUSD": 1000000},
                    {"date": 1619222400, "totalLiquidityUSD": 2000000},
                ],
                "tokensInUsd": [],
                "tokens": [],
            },
            "Ethereum": {"tvl": [{"date": 1619049600, "totalLiquidityUSD": 42}]},
        },
    }


@respx.mock
def test_chain_tvl_parses_sorts_and_dedups():
    respx.get(f"{BASE}/v2/historicalChainTvl/BSC").mock(
        return_value=httpx.Response(200, json=_chain_tvl_body())
    )
    s = DefiLlamaAdapter(base_url=BASE).chain_tvl("BSC")
    assert isinstance(s, pd.Series)
    assert s.name == "tvl"
    assert isinstance(s.index, pd.DatetimeIndex)
    assert s.index.tz is None  # tz-naive
    # sorted ascending, deduped keep-last
    assert list(s.index) == list(
        pd.to_datetime(["2020-10-30", "2020-10-31", "2020-11-01"])
    )
    assert s.loc["2020-10-30"] == 12873962
    assert s.loc["2020-11-01"] == 14500000  # the LAST of the two dups


@respx.mock
def test_chain_tvl_index_is_normalized_midnight():
    respx.get(f"{BASE}/v2/historicalChainTvl/BSC").mock(
        return_value=httpx.Response(200, json=_chain_tvl_body())
    )
    s = DefiLlamaAdapter(base_url=BASE).chain_tvl("BSC")
    # all timestamps normalized to 00:00:00 (no intraday component)
    assert (s.index.normalize() == s.index).all()


@respx.mock
def test_protocol_chain_tvl_reads_binance_total_liquidity():
    respx.get(f"{BASE}/protocol/pancakeswap-amm").mock(
        return_value=httpx.Response(200, json=_protocol_body())
    )
    s = DefiLlamaAdapter(base_url=BASE).protocol_chain_tvl(
        "pancakeswap-amm", "Binance"
    )
    assert s.name == "protocol_tvl"
    assert s.index.tz is None
    assert list(s.values) == [598, 1000000, 2000000]
    assert s.loc["2021-04-22"] == 598


@respx.mock
def test_protocol_chain_tvl_missing_chain_key_returns_empty():
    respx.get(f"{BASE}/protocol/pancakeswap-amm").mock(
        return_value=httpx.Response(200, json=_protocol_body())
    )
    s = DefiLlamaAdapter(base_url=BASE).protocol_chain_tvl(
        "pancakeswap-amm", "Solana"  # not present
    )
    assert isinstance(s, pd.Series)
    assert len(s) == 0
    assert s.name == "protocol_tvl"


@respx.mock
def test_chain_tvl_empty_data_returns_empty_series():
    respx.get(f"{BASE}/v2/historicalChainTvl/BSC").mock(
        return_value=httpx.Response(200, json=[])
    )
    s = DefiLlamaAdapter(base_url=BASE).chain_tvl("BSC")
    assert isinstance(s, pd.Series)
    assert len(s) == 0
    assert s.name == "tvl"


@respx.mock
def test_no_auth_header_sent():
    captured = {}

    def _capture(request):
        captured["auth"] = request.headers.get("Authorization")
        captured["key"] = request.headers.get("X-CMC_PRO_API_KEY")
        return httpx.Response(200, json=[])

    respx.get(f"{BASE}/v2/historicalChainTvl/BSC").mock(side_effect=_capture)
    DefiLlamaAdapter(base_url=BASE).chain_tvl("BSC")
    assert captured["auth"] is None
    assert captured["key"] is None
