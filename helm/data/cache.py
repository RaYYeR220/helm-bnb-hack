"""Local OHLCV cache (parquet) and price-panel assembly.

The cache makes the backtest reproducible and rate-limit-free: each symbol's
OHLCV is fetched once, persisted to parquet, and reused. `build_price_panel`
returns the close-price panel (dates x symbols) the backtest engine consumes.
"""

from pathlib import Path

import pandas as pd


class OHLCVCache:
    def __init__(self, root: str | Path = "data_cache/ohlcv"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, symbol: str) -> Path:
        safe = symbol.replace("/", "_")
        return self.root / f"{safe}.parquet"

    def get(self, symbol: str) -> pd.DataFrame | None:
        p = self._path(symbol)
        if not p.exists():
            return None
        return pd.read_parquet(p)

    def put(self, symbol: str, df: pd.DataFrame) -> None:
        df.to_parquet(self._path(symbol))


def build_price_panel(
    symbols: list[str],
    adapter,
    cache: OHLCVCache,
    start: str,
    end: str,
    interval: str = "daily",
) -> pd.DataFrame:
    """Assemble a close-price panel. Cache hits skip the adapter; symbols whose
    fetch fails or returns empty are skipped (logged via the returned columns)."""
    closes: dict[str, pd.Series] = {}
    for sym in symbols:
        df = cache.get(sym)
        if df is None:
            try:
                df = adapter.ohlcv_historical(sym, start, end, interval=interval)
            except Exception:
                continue
            if df is None or df.empty:
                continue
            cache.put(sym, df)
        if df.empty:
            continue
        closes[sym] = df["close"]
    if not closes:
        return pd.DataFrame()
    panel = pd.DataFrame(closes)
    panel = panel.sort_index()
    # preserve requested column order for the symbols that survived
    ordered = [s for s in symbols if s in panel.columns]
    return panel[ordered]
