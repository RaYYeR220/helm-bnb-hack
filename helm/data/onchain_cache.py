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


def _market_aggregate(cache, prefix: str, symbols: list[str]) -> pd.Series:
    """Cross-sectional MEAN of cached per-symbol ``{prefix}{sym}`` series.

    Reads each symbol's Series (missing ones skipped), assembles a date x symbol
    frame, and returns the row-wise mean (skipna). Empty if no symbol is cached.
    Causal: each value is a same-date average of inputs, no time shift.
    """
    cols: dict[str, pd.Series] = {}
    for sym in symbols:
        s = cache.get_series(f"{prefix}{sym}")
        if s is not None and len(s) > 0:
            cols[sym] = s.sort_index()
    if not cols:
        return pd.Series(dtype=float)
    frame = pd.DataFrame(cols).sort_index()
    return frame.mean(axis=1, skipna=True)


def _trailing_z(s: pd.Series, z_window: int, min_periods: int) -> pd.Series:
    """Causal trailing z-score: ``(x_t - rollmean_t) / rollstd_t`` over the prior
    ``z_window`` values (pandas ``.rolling`` is backward-looking, so only data at
    dates <= t is used). Zero/NaN std -> 0.0; result is finite."""
    if s.empty:
        return s
    roll = s.rolling(z_window, min_periods=min_periods)
    mean = roll.mean()
    std = roll.std(ddof=1)
    z = (s - mean) / std.replace(0.0, pd.NA)
    return z.replace([float("inf"), float("-inf")], pd.NA).astype(float)


def build_flow_features(
    cache,
    index: pd.DatetimeIndex,
    symbols: list[str],
    z_window: int = 60,
    min_periods: int = 10,
) -> pd.DataFrame:
    """Causal, panel-aligned WHALE + CEX flow feature frame for ``index``.

    Columns: ``net_whale_flow_z`` (trailing z of the market-mean large-transfer
    whale-activity series, cache keys ``whaleflow_{sym}``) and ``net_cex_flow_z``
    (trailing z of the market-mean CEX net-inflow series, cache keys
    ``cexflow_{sym}``). Each is market-aggregated (cross-sectional mean across the
    cached symbols), then z-scored on a CAUSAL trailing window of ``z_window``
    days (data <= t only), then reindex-ffilled onto ``index`` and zero-filled.

    Missing symbols are tolerated (averaged over whatever is cached); if NEITHER
    kind has any cached symbol, the corresponding column is all zeros. The output
    is always finite (``ffill().fillna(0.0)``).
    """
    whale = _market_aggregate(cache, "whaleflow_", symbols)
    cexf = _market_aggregate(cache, "cexflow_", symbols)

    whale_z = _trailing_z(whale, z_window, min_periods).rename("net_whale_flow_z")
    cex_z = _trailing_z(cexf, z_window, min_periods).rename("net_cex_flow_z")

    native = pd.concat([whale_z, cex_z], axis=1)
    if native.empty:
        native = pd.DataFrame(
            columns=["net_whale_flow_z", "net_cex_flow_z"]
        )
    aligned = native.reindex(index).ffill().fillna(0.0)
    aligned.index = index
    # guarantee both columns exist even if one kind had no cached data
    for col in ("net_whale_flow_z", "net_cex_flow_z"):
        if col not in aligned.columns:
            aligned[col] = 0.0
    return aligned[["net_whale_flow_z", "net_cex_flow_z"]]
