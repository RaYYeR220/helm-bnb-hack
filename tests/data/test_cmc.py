import httpx
import pandas as pd
import respx

from helm.data.cmc import CMCAdapter

BASE = "https://pro-api.coinmarketcap.com"


@respx.mock
def test_quotes_latest_parses_price():
    route = respx.get(f"{BASE}/v1/cryptocurrency/quotes/latest").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "ETH": {"quote": {"USD": {"price": 3000.0, "volume_24h": 1.0}}},
                }
            },
        )
    )
    adapter = CMCAdapter(api_key="k", base_url=BASE)
    quotes = adapter.quotes_latest(["ETH"])
    assert route.called
    assert quotes["ETH"]["price"] == 3000.0


# Real /v2 shape: `data` is keyed by the queried symbol and holds a LIST
# (one entry per CMC id sharing that symbol), each with a `quotes` array.
def _v2_ohlcv_body():
    return {
        "data": {
            "ETH": [
                {
                    "id": 1027,
                    "name": "Ethereum",
                    "symbol": "ETH",
                    "quotes": [
                        {"time_open": "2024-01-01T00:00:00.000Z",
                         "quote": {"USD": {"open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10}}},
                        {"time_open": "2024-01-02T00:00:00.000Z",
                         "quote": {"USD": {"open": 1.5, "high": 2.5, "low": 1.0, "close": 2.0, "volume": 12}}},
                    ],
                }
            ]
        }
    }


@respx.mock
def test_ohlcv_historical_returns_dataframe():
    respx.get(f"{BASE}/v2/cryptocurrency/ohlcv/historical").mock(
        return_value=httpx.Response(200, json=_v2_ohlcv_body())
    )
    adapter = CMCAdapter(api_key="k", base_url=BASE)
    df = adapter.ohlcv_historical("ETH", "2024-01-01", "2024-01-02")
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df["close"].iloc[-1] == 2.0


@respx.mock
def test_ohlcv_historical_handles_flat_by_id_shape():
    # Fallback: some responses put `quotes` directly under `data` (by-id query).
    respx.get(f"{BASE}/v2/cryptocurrency/ohlcv/historical").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"quotes": [
                {"time_open": "2024-01-01T00:00:00.000Z",
                 "quote": {"USD": {"open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10}}},
            ]}},
        )
    )
    adapter = CMCAdapter(api_key="k", base_url=BASE)
    df = adapter.ohlcv_historical("ETH", "2024-01-01", "2024-01-01")
    assert df["close"].iloc[-1] == 1.5


@respx.mock
def test_auth_header_sent():
    captured = {}

    def _capture(request):
        captured["key"] = request.headers.get("X-CMC_PRO_API_KEY")
        return httpx.Response(200, json={"data": {}})

    respx.get(f"{BASE}/v1/cryptocurrency/quotes/latest").mock(side_effect=_capture)
    CMCAdapter(api_key="secret", base_url=BASE).quotes_latest(["ETH"])
    assert captured["key"] == "secret"
