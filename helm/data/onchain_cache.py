"""On-chain parquet cache + TVL-derived regime features.

``OnchainCache`` mirrors ``OHLCVCache`` (parquet, root ``data_cache/onchain``)
but stores named Series (TVL series and per-symbol DEX volume series) as a
single-column frame so they survive a parquet roundtrip. ``build_onchain_features``
fetches (cache-first) the chain TVL and PancakeSwap TVL, derives three causal,
panel-aligned feature columns, and reindex-ffills them onto ``index``.

CAUSALITY: every feature value at date t is a function of TVL values at dates
<= t only (``pct_change``, running ``cummax``, and reindex+ffill never look
forward). Aligning to a price-panel ``index`` with ``reindex(index).ffill()``
carries the last KNOWN value forward, so a panel date with no fresh TVL print
reuses an earlier (past) value — never a future one. The frame is finite after
``ffill().fillna(0.0)``.
"""

from pathlib import Path

import pandas as pd


class OnchainCache:
    def __init__(self, root: str | Path = "data_cache/onchain"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "_")
        return self.root / f"{safe}.parquet"

    def get_series(self, key: str) -> pd.Series | None:
        p = self._path(key)
        if not p.exists():
            return None
        df = pd.read_parquet(p)
        if df.shape[1] == 0:
            return pd.Series(dtype=float)
        col = df.columns[0]
        return df[col].rename(col)

    def put_series(self, key: str, series: pd.Series) -> None:
        name = series.name if series.name is not None else key
        series.rename(name).to_frame().to_parquet(self._path(key))


def _fetch_cached(cache: OnchainCache, key: str, fetch) -> pd.Series:
    """Return the cached Series for ``key`` or fetch it, cache it, and return it."""
    s = cache.get_series(key)
    if s is not None:
        return s
    s = fetch()
    cache.put_series(key, s)
    return s


def build_onchain_features(
    defillama, cache: OnchainCache, index: pd.DatetimeIndex
) -> pd.DataFrame:
    """Causal, panel-aligned TVL feature frame for ``index``.

    Columns: ``tvl_mom20`` (chain TVL 20-day % change), ``tvl_dd`` (chain TVL
    drawdown from its running peak, <= 0), ``pancake_share_mom20`` (20-day %
    change of pancake_tvl / chain_tvl). Computed on the native daily TVL grid,
    then reindexed onto ``index`` with ffill (last-known-value) and zero-filled.
    """
    chain = _fetch_cached(cache, "bsc_tvl", lambda: defillama.chain_tvl("BSC"))
    pancake = _fetch_cached(
        cache, "pancake_tvl", lambda: defillama.protocol_chain_tvl()
    )
    chain = chain.sort_index()
    pancake = pancake.sort_index()

    tvl_mom20 = chain.pct_change(20)
    tvl_dd = chain / chain.cummax() - 1.0
    # align pancake onto the chain grid (last-known) before forming the share
    pancake_aligned = pancake.reindex(chain.index).ffill()
    share = pancake_aligned / chain
    pancake_share_mom20 = share.pct_change(20)

    native = pd.DataFrame(
        {
            "tvl_mom20": tvl_mom20,
            "tvl_dd": tvl_dd,
            "pancake_share_mom20": pancake_share_mom20,
        }
    )
    aligned = native.reindex(index).ffill().fillna(0.0)
    aligned.index = index
    return aligned[["tvl_mom20", "tvl_dd", "pancake_share_mom20"]]
