"""CoinMarketCap Pro REST adapter (market data + historical OHLCV).

Auth header is `X-CMC_PRO_API_KEY` per CMC REST docs. The MCP path (used by the
Agent Hub Skill) is documented separately in Plan C; this adapter is the
deterministic data source for the backtest engine.
"""

import httpx
import pandas as pd


class CMCAdapter:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://pro-api.coinmarketcap.com",
        client: httpx.Client | None = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout, headers={"X-CMC_PRO_API_KEY": api_key, "Accept": "application/json"}
        )

    def close(self) -> None:
        """Close the underlying client if this adapter created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "CMCAdapter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _get(self, path: str, params: dict) -> dict:
        resp = self._client.get(f"{self.base_url}{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _extract_quotes(data: dict, symbol: str) -> list:
        """Pull the OHLCV quote list from a /v2 historical response.

        The /v2 endpoint keys `data` by the queried symbol and returns a LIST
        (one entry per CMC id sharing that symbol); the first entry is the
        canonical match. Falls back to a dict-per-symbol or a flat `quotes`
        (by-id) shape."""
        entry = data.get(symbol) if isinstance(data, dict) else None
        if isinstance(entry, list):
            return entry[0].get("quotes", []) if entry else []
        if isinstance(entry, dict):
            return entry.get("quotes", [])
        if isinstance(data, dict):
            return data.get("quotes", [])
        return []

    def quotes_latest(self, symbols: list[str], convert: str = "USD") -> dict:
        """Return {symbol: {price, volume_24h}} for the requested symbols."""
        data = self._get(
            "/v1/cryptocurrency/quotes/latest",
            {"symbol": ",".join(symbols), "convert": convert},
        ).get("data", {})
        out: dict[str, dict] = {}
        for sym, payload in data.items():
            q = (payload.get("quote") or {}).get(convert, {}) if isinstance(payload, dict) else {}
            out[sym] = {"price": q.get("price"), "volume_24h": q.get("volume_24h")}
        return out

    def ohlcv_historical(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str = "daily",
        convert: str = "USD",
    ) -> pd.DataFrame:
        """Daily OHLCV for one symbol as a DatetimeIndex DataFrame
        with columns [open, high, low, close, volume]."""
        payload = self._get(
            "/v2/cryptocurrency/ohlcv/historical",
            {
                "symbol": symbol,
                "time_start": start,
                "time_end": end,
                "interval": interval,
                "convert": convert,
            },
        )
        quotes = self._extract_quotes(payload.get("data") or {}, symbol)
        rows = []
        for q in quotes:
            usd = q["quote"][convert]
            rows.append(
                {
                    "time": pd.to_datetime(q["time_open"], utc=True).tz_convert(None).normalize(),
                    "open": usd["open"],
                    "high": usd["high"],
                    "low": usd["low"],
                    "close": usd["close"],
                    "volume": usd.get("volume"),
                }
            )
        if not rows:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        df = pd.DataFrame(rows).set_index("time").sort_index()
        df.index.name = None
        return df[["open", "high", "low", "close", "volume"]]
