"""GeckoTerminal adapter: BSC DEX pool discovery + daily OHLCV.

JSON:API envelope, network id ``bsc``, pool ids ``bsc_{address}``. Two methods:

- ``token_top_pool`` picks a token's highest-``reserve_in_usd`` pool and returns
  the address (prefix stripped), reserve, and rolling 24h volume.
- ``pool_ohlcv_daily`` returns up to 182 daily candles (the free-tier HARD CAP)
  from ``/ohlcv/day``; the envelope is ``data.attributes.ohlcv_list`` with rows
  ``[ts_unix_SECONDS, open, high, low, close, volume_usd]`` returned NEWEST-FIRST.

GOTCHAS pinned from the live API: ``reserve_in_usd`` and the ``volume_usd``
buckets are STRINGS; OHLCV timestamps are unix SECONDS (10 digits — the spike's
"ms" note is wrong); candles are descending and must be re-sorted ascending. The
free tier exposes no rate-limit headers and 429s after ~6-8 rapid calls, so the
adapter enforces a ``min_interval_s`` (default 3.0s) sleep between requests; tests
pass ``min_interval_s=0`` to disable it. Daily OHLCV is capped at ~182 days; cache
aggressively (see ``onchain_cache``).
"""

import time

import httpx
import pandas as pd

_OHLCV_COLS = ["open", "high", "low", "close", "volume"]


def _to_float(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


class GeckoTerminalAdapter:
    def __init__(
        self,
        base_url: str = "https://api.geckoterminal.com/api/v2",
        client: httpx.Client | None = None,
        timeout: float = 30.0,
        min_interval_s: float = 3.0,
        max_retries: int = 3,
        backoff_s: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.min_interval_s = min_interval_s
        self.max_retries = max_retries
        self.backoff_s = backoff_s
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={"Accept": "application/json", "User-Agent": "helm/onchain"},
        )
        self._last_call_at: float | None = None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "GeckoTerminalAdapter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _throttle(self) -> None:
        """Sleep only if the previous call was < ``min_interval_s`` ago."""
        if self.min_interval_s <= 0 or self._last_call_at is None:
            return
        wait = self.min_interval_s - (time.monotonic() - self._last_call_at)
        if wait > 0:
            time.sleep(wait)

    def _get(self, path: str, params: dict | None = None) -> dict:
        """GET with throttle + 429 retry.

        The free tier rate-limits aggressively (a global per-minute counter,
        not just burst). On 429 we honor ``Retry-After`` when present, else
        wait ``backoff_s`` (scaled by attempt), up to ``max_retries`` waits."""
        attempt = 0
        while True:
            self._throttle()
            resp = self._client.get(f"{self.base_url}{path}", params=params)
            self._last_call_at = time.monotonic()
            if resp.status_code == 429 and attempt < self.max_retries:
                attempt += 1
                retry_after = _to_float(resp.headers.get("Retry-After"))
                wait = retry_after if retry_after > 0 else self.backoff_s * attempt
                if wait > 0:
                    time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()

    def token_top_pool(
        self, token_address: str, network: str = "bsc"
    ) -> dict | None:
        """Highest-reserve pool for a token, or None if it has no pools.

        Returns ``{"pool_address": <id minus '{network}_' prefix>,
        "reserve_usd": float, "volume_24h": float}``."""
        data = self._get(
            f"/networks/{network}/tokens/{token_address}/pools",
            {"page": 1},
        )
        pools = data.get("data", []) if isinstance(data, dict) else []
        if not pools:
            return None
        best = max(
            pools, key=lambda p: _to_float(p["attributes"].get("reserve_in_usd"))
        )
        attrs = best["attributes"]
        pool_id = best.get("id", "")
        prefix = f"{network}_"
        pool_address = (
            pool_id[len(prefix):] if pool_id.startswith(prefix) else pool_id
        )
        vol_24h = _to_float((attrs.get("volume_usd") or {}).get("h24"))
        return {
            "pool_address": pool_address,
            "reserve_usd": _to_float(attrs.get("reserve_in_usd")),
            "volume_24h": vol_24h,
        }

    def pool_ohlcv_daily(
        self, pool_address: str, network: str = "bsc", limit: int = 182
    ) -> pd.DataFrame:
        """Up to ``limit`` daily candles (free-tier cap 182) as an OHLCV frame.

        Parses ``data.attributes.ohlcv_list`` (``[ts_unix_s, o, h, l, c, vol]``),
        normalizes the second timestamps to a tz-naive midnight DatetimeIndex, and
        sorts ascending. Empty input -> empty frame with the standard columns."""
        data = self._get(
            f"/networks/{network}/pools/{pool_address}/ohlcv/day",
            {"aggregate": 1, "limit": limit},
        )
        attrs = (data.get("data") or {}).get("attributes", {})
        rows = attrs.get("ohlcv_list", []) or []
        if not rows:
            return pd.DataFrame(columns=_OHLCV_COLS)
        index = pd.to_datetime(
            [r[0] for r in rows], unit="s", utc=True
        ).tz_convert(None).normalize()
        df = pd.DataFrame(
            [[r[1], r[2], r[3], r[4], r[5]] for r in rows],
            columns=_OHLCV_COLS,
            index=index,
        )
        df = df.sort_index()
        df.index.name = None
        return df
