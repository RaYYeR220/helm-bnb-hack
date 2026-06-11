"""DeFiLlama adapter (keyless): multi-year BSC liquidity TVL series.

Two endpoints supply market-level DeFi liquidity at full historical depth (5+
years daily) for the regime feature panel:

- ``/v2/historicalChainTvl/{chain}`` -> ``[{date(unix s), tvl}]`` — whole-chain
  TVL (BSC).
- ``/protocol/{protocol}`` -> ``chainTvls[chain_key]["tvl"]`` =
  ``[{date(unix s), totalLiquidityUSD}]`` — one DEX's TVL on one chain.

GOTCHAS pinned from the live API: the per-chain key for BSC is ``"Binance"``
(NOT ``"BSC"``), and the per-protocol field is ``totalLiquidityUSD`` (NOT
``tvl``). Dates are unix SECONDS. This adapter follows the CMCAdapter client
pattern but sends NO auth header (the API is keyless).
"""

import httpx
import pandas as pd


def _to_daily_series(records: list, value_key: str, name: str) -> pd.Series:
    """``[{date(unix s), <value_key>}]`` -> tz-naive, midnight-normalized, sorted,
    dedup-keep-last daily Series named ``name``. Empty input -> empty Series."""
    if not records:
        return pd.Series(dtype=float, name=name)
    dates = pd.to_datetime(
        [r["date"] for r in records], unit="s", utc=True
    ).tz_convert(None).normalize()
    values = [r[value_key] for r in records]
    s = pd.Series(values, index=dates, name=name, dtype=float)
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s


class DefiLlamaAdapter:
    def __init__(
        self,
        base_url: str = "https://api.llama.fi",
        client: httpx.Client | None = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout, headers={"Accept": "application/json"}
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "DefiLlamaAdapter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _get(self, path: str):
        resp = self._client.get(f"{self.base_url}{path}")
        resp.raise_for_status()
        return resp.json()

    def chain_tvl(self, chain: str = "BSC") -> pd.Series:
        """Whole-chain daily TVL Series (name ``tvl``)."""
        data = self._get(f"/v2/historicalChainTvl/{chain}")
        records = data if isinstance(data, list) else []
        return _to_daily_series(records, "tvl", "tvl")

    def protocol_chain_tvl(
        self, protocol: str = "pancakeswap-amm", chain_key: str = "Binance"
    ) -> pd.Series:
        """One protocol's daily TVL on one chain (name ``protocol_tvl``).

        Reads ``chainTvls[chain_key]["tvl"]`` (field ``totalLiquidityUSD``); a
        missing chain key yields an empty Series."""
        data = self._get(f"/protocol/{protocol}")
        chain_tvls = data.get("chainTvls", {}) if isinstance(data, dict) else {}
        entry = chain_tvls.get(chain_key, {})
        records = entry.get("tvl", []) if isinstance(entry, dict) else []
        return _to_daily_series(records, "totalLiquidityUSD", "protocol_tvl")
