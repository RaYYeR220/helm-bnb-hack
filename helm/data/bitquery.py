"""Bitquery EVM adapter (keyed GraphQL): per-token whale + CEX flow on BSC.

Endpoint ``https://streaming.bitquery.io/graphql``; auth header
``Authorization: Bearer <BITQUERY_API_KEY>``. Uses ``dataset: combined`` for
FULL historical depth (verified: CAKE transfers back to 2020-09-22; a 365-day
server-aggregated query returns all 365 daily points in one call). Two methods:

- ``daily_token_flow`` — daily aggregated transfer flow for one token: ``count``
  and summed ``Amount`` per calendar day, with an optional large-transfer (whale)
  ``min_amount`` filter (``Transfer.Amount.ge``). Returns a date-indexed frame
  ``[volume, count]``.
- ``daily_cex_flow`` — combined exchange inflow (Receiver ∈ wallets) and outflow
  (Sender ∈ wallets) in ONE aliased GraphQL query. Returns ``[inflow, outflow,
  net_inflow]`` (net_inflow = inflow - outflow; positive = net flow TO exchanges
  ~ sell pressure).

GOTCHAS pinned from the live API: the aggregation interval enum is
``Time(interval: {in: days, count: 1})`` (NOT ``{in: day}``); ordering is
``orderBy: {ascendingByField: "Block_Date"}``; the aggregate fields are
``count`` (no args) and ``sum(of: Transfer_Amount)``; and BOTH ``count`` and the
summed amount come back as STRINGS. ``Date`` is an ISO-Z midnight stamp. An empty
date range returns an empty list (clean empty-range guard). The adapter follows
the CMCAdapter client pattern; tests are respx-mocked from captured shapes.
"""

import httpx
import pandas as pd

_ENDPOINT = "https://streaming.bitquery.io/graphql"
_AGG_FIELDS = (
    'Block { Date: Time(interval: {in: days, count: 1}) }\n'
    "        count\n"
    "        sum_amount: sum(of: Transfer_Amount)"
)


def _iso_z(date: str) -> str:
    """``YYYY-MM-DD`` (or already-ISO) -> the ``YYYY-MM-DDT00:00:00Z`` the API wants."""
    return date if "T" in date else f"{date}T00:00:00Z"


def _addr_list(wallets: list[str]) -> str:
    """``["0xa","0xb"]`` -> the GraphQL array literal ``["0xa", "0xb"]``."""
    return "[" + ", ".join(f'"{w}"' for w in wallets) + "]"


def _rows_to_frame(rows: list, vol_name: str, cnt_name: str) -> pd.DataFrame:
    """Aggregated Transfers rows -> tz-naive, midnight, ascending date-indexed
    frame with a volume column (summed amount, float) and a count column (int).
    Empty input -> empty frame with the two named columns."""
    if not rows:
        return pd.DataFrame(columns=[vol_name, cnt_name])
    idx = pd.to_datetime(
        [r["Block"]["Date"] for r in rows], utc=True
    ).tz_convert(None).normalize()
    df = pd.DataFrame(
        {
            vol_name: [float(r["sum_amount"]) for r in rows],
            cnt_name: [int(r["count"]) for r in rows],
        },
        index=idx,
    )
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df.index.name = None
    return df


class BitqueryAdapter:
    def __init__(
        self,
        api_key: str,
        base_url: str = _ENDPOINT,
        client: httpx.Client | None = None,
        timeout: float = 60.0,
    ):
        self.base_url = base_url
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "BitqueryAdapter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _post(self, query: str) -> dict:
        resp = self._client.post(self.base_url, json={"query": query})
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("errors"):
            msgs = "; ".join(e.get("message", "") for e in payload["errors"])
            raise RuntimeError(f"Bitquery GraphQL error: {msgs}")
        return payload.get("data") or {}

    def daily_token_flow(
        self,
        contract: str,
        start: str,
        end: str,
        min_amount: str | None = None,
    ) -> pd.DataFrame:
        """Daily aggregated transfer flow for ``contract`` between ``start`` and
        ``end`` (``YYYY-MM-DD``). Optional whale filter ``min_amount`` (token
        units, as a STRING e.g. ``"10000"``) adds ``Transfer.Amount.ge``.
        Returns a date-indexed frame ``[volume, count]``."""
        amount_filter = f'\n          Amount: {{ge: "{min_amount}"}}' if min_amount else ""
        query = f"""
query {{
  EVM(network: bsc, dataset: combined) {{
    Transfers(
      where: {{
        Block: {{Time: {{since: "{_iso_z(start)}", till: "{_iso_z(end)}"}}}}
        Transfer: {{
          Currency: {{SmartContract: {{is: "{contract}"}}}}{amount_filter}
        }}
      }}
      orderBy: {{ascendingByField: "Block_Date"}}
    ) {{
        {_AGG_FIELDS}
    }}
  }}
}}
"""
        data = self._post(query)
        rows = ((data.get("EVM") or {}).get("Transfers")) or []
        return _rows_to_frame(rows, "volume", "count")

    def daily_cex_flow(
        self,
        contract: str,
        exchange_wallets: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Combined exchange inflow/outflow for ``contract`` vs ``exchange_wallets``
        in ONE query. inflow = transfers with Receiver in the set; outflow =
        Sender in the set. Returns ``[inflow, outflow, net_inflow]`` (net_inflow =
        inflow - outflow). Missing dates on either side are zero-filled."""
        wl = _addr_list(exchange_wallets)
        time_filter = f'Block: {{Time: {{since: "{_iso_z(start)}", till: "{_iso_z(end)}"}}}}'
        cur = f'Currency: {{SmartContract: {{is: "{contract}"}}}}'
        query = f"""
query {{
  EVM(network: bsc, dataset: combined) {{
    inflow: Transfers(
      where: {{
        {time_filter}
        Transfer: {{{cur} Receiver: {{in: {wl}}}}}
      }}
      orderBy: {{ascendingByField: "Block_Date"}}
    ) {{
        {_AGG_FIELDS}
    }}
    outflow: Transfers(
      where: {{
        {time_filter}
        Transfer: {{{cur} Sender: {{in: {wl}}}}}
      }}
      orderBy: {{ascendingByField: "Block_Date"}}
    ) {{
        {_AGG_FIELDS}
    }}
  }}
}}
"""
        evm = self._post(query).get("EVM") or {}
        inflow = _rows_to_frame(evm.get("inflow") or [], "inflow", "_in_cnt")
        outflow = _rows_to_frame(evm.get("outflow") or [], "outflow", "_out_cnt")
        if inflow.empty and outflow.empty:
            return pd.DataFrame(columns=["inflow", "outflow", "net_inflow"])
        joined = pd.concat(
            [inflow["inflow"], outflow["outflow"]], axis=1
        ).sort_index().fillna(0.0)
        joined["net_inflow"] = joined["inflow"] - joined["outflow"]
        return joined[["inflow", "outflow", "net_inflow"]]
