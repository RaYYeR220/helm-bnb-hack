import httpx
import pandas as pd
import respx

from helm.data.bitquery import BitqueryAdapter

URL = "https://streaming.bitquery.io/graphql"
CAKE = "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82"


def _token_flow_body():
    # REAL daily-aggregated shape: count + sum_amount are STRINGS; Date is an
    # ISO-Z midnight stamp. Deliberately given OUT OF ORDER to exercise the sort.
    return {
        "data": {
            "EVM": {
                "Transfers": [
                    {"Block": {"Date": "2026-06-02T00:00:00Z"},
                     "count": "68212", "sum_amount": "9628917.542057067854378542"},
                    {"Block": {"Date": "2026-06-01T00:00:00Z"},
                     "count": "78750", "sum_amount": "242952426.408141373112166704"},
                    {"Block": {"Date": "2026-06-03T00:00:00Z"},
                     "count": "71619", "sum_amount": "9244085.617485391374181690"},
                ]
            }
        }
    }


def _cex_flow_body():
    # REAL combined shape: two aliased selections in ONE response.
    return {
        "data": {
            "EVM": {
                "inflow": [
                    {"Block": {"Date": "2026-06-05T00:00:00Z"},
                     "count": "150", "sum_amount": "353556.755147133367626530"},
                    {"Block": {"Date": "2026-06-06T00:00:00Z"},
                     "count": "121", "sum_amount": "333443.716811569731254312"},
                ],
                "outflow": [
                    {"Block": {"Date": "2026-06-05T00:00:00Z"},
                     "count": "66", "sum_amount": "506395.065911150000000000"},
                    {"Block": {"Date": "2026-06-06T00:00:00Z"},
                     "count": "32", "sum_amount": "250990.132855840000000000"},
                ],
            }
        }
    }


@respx.mock
def test_daily_token_flow_parses_sorts_and_types():
    respx.post(URL).mock(return_value=httpx.Response(200, json=_token_flow_body()))
    df = BitqueryAdapter(api_key="k").daily_token_flow(
        CAKE, "2026-06-01", "2026-06-04"
    )
    assert list(df.columns) == ["volume", "count"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.tz is None
    # sorted ascending despite out-of-order input
    assert list(df.index) == list(
        pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-03"])
    )
    # string fields parsed to numerics
    assert df["count"].dtype.kind in "if"
    assert df.loc["2026-06-01", "count"] == 78750
    assert df.loc["2026-06-01", "volume"] == float("242952426.408141373112166704")


@respx.mock
def test_daily_token_flow_passes_min_amount_threshold_into_query():
    captured = {}

    def _capture(request):
        captured["body"] = request.content.decode()
        return httpx.Response(200, json=_token_flow_body())

    respx.post(URL).mock(side_effect=_capture)
    BitqueryAdapter(api_key="k").daily_token_flow(
        CAKE, "2026-06-01", "2026-06-04", min_amount="10000"
    )
    # the whale Amount filter is present in the GraphQL body
    assert "Amount" in captured["body"]
    assert "10000" in captured["body"]
    # and the contract + date range are wired in
    assert CAKE in captured["body"]
    assert "2026-06-01" in captured["body"]
    assert "2026-06-04" in captured["body"]


@respx.mock
def test_daily_token_flow_omits_amount_filter_when_no_threshold():
    captured = {}

    def _capture(request):
        captured["body"] = request.content.decode()
        return httpx.Response(200, json=_token_flow_body())

    respx.post(URL).mock(side_effect=_capture)
    BitqueryAdapter(api_key="k").daily_token_flow(CAKE, "2026-06-01", "2026-06-04")
    # Transfer_Amount is always present (aggregate field); the FILTER "Amount: {ge:}"
    # must be absent when no threshold is given.
    assert "ge:" not in captured["body"]


@respx.mock
def test_daily_cex_flow_parses_inflow_outflow_and_net():
    respx.post(URL).mock(return_value=httpx.Response(200, json=_cex_flow_body()))
    wallets = ["0x8894e0a0c962cb723c1976a4421c95949be2d4e3"]
    df = BitqueryAdapter(api_key="k").daily_cex_flow(
        CAKE, wallets, "2026-06-05", "2026-06-07"
    )
    assert list(df.columns) == ["inflow", "outflow", "net_inflow"]
    assert df.index.tz is None
    assert list(df.index) == list(pd.to_datetime(["2026-06-05", "2026-06-06"]))
    inflow_0 = float("353556.755147133367626530")
    outflow_0 = float("506395.065911150000000000")
    assert df.loc["2026-06-05", "inflow"] == inflow_0
    assert df.loc["2026-06-05", "outflow"] == outflow_0
    # net_inflow = inflow - outflow (positive = net sell pressure to exchanges)
    assert df.loc["2026-06-05", "net_inflow"] == inflow_0 - outflow_0


@respx.mock
def test_daily_cex_flow_aligns_mismatched_dates_with_zero_fill():
    # inflow has a date outflow lacks -> outer-join, missing side -> 0.0
    body = {
        "data": {
            "EVM": {
                "inflow": [
                    {"Block": {"Date": "2026-06-05T00:00:00Z"},
                     "count": "1", "sum_amount": "100.0"},
                    {"Block": {"Date": "2026-06-06T00:00:00Z"},
                     "count": "1", "sum_amount": "200.0"},
                ],
                "outflow": [
                    {"Block": {"Date": "2026-06-05T00:00:00Z"},
                     "count": "1", "sum_amount": "40.0"},
                ],
            }
        }
    }
    respx.post(URL).mock(return_value=httpx.Response(200, json=body))
    df = BitqueryAdapter(api_key="k").daily_cex_flow(
        CAKE, ["0xabc"], "2026-06-05", "2026-06-07"
    )
    assert df.loc["2026-06-06", "outflow"] == 0.0           # zero-filled
    assert df.loc["2026-06-06", "net_inflow"] == 200.0      # 200 - 0


@respx.mock
def test_empty_range_returns_empty_frames():
    respx.post(URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"EVM": {"Transfers": []}}}
        )
    )
    df = BitqueryAdapter(api_key="k").daily_token_flow(CAKE, "2027-01-01", "2027-01-02")
    assert df.empty
    assert list(df.columns) == ["volume", "count"]


@respx.mock
def test_empty_cex_range_returns_empty_frame():
    respx.post(URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"EVM": {"inflow": [], "outflow": []}}}
        )
    )
    df = BitqueryAdapter(api_key="k").daily_cex_flow(
        CAKE, ["0xabc"], "2027-01-01", "2027-01-02"
    )
    assert df.empty
    assert list(df.columns) == ["inflow", "outflow", "net_inflow"]


@respx.mock
def test_sends_bearer_auth_header():
    captured = {}

    def _capture(request):
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"data": {"EVM": {"Transfers": []}}})

    respx.post(URL).mock(side_effect=_capture)
    BitqueryAdapter(api_key="SECRET").daily_token_flow(CAKE, "2026-06-01", "2026-06-02")
    assert captured["auth"] == "Bearer SECRET"


@respx.mock
def test_graphql_errors_raise():
    import pytest

    respx.post(URL).mock(
        return_value=httpx.Response(
            200, json={"data": None, "errors": [{"message": "bad enum"}]}
        )
    )
    with pytest.raises(RuntimeError, match="bad enum"):
        BitqueryAdapter(api_key="k").daily_token_flow(CAKE, "2026-06-01", "2026-06-02")
