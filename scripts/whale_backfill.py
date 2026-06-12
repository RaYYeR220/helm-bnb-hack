"""Human-run whale + CEX flow backfill: per-token Bitquery flow into the cache.

For each major, fetch from Bitquery (cache-first, like onchain_backfill -- skip
already-cached symbols, retry/backoff politely on transient errors):

- daily WHALE flow: large-transfer (Amount >= WHALE_MIN_AMOUNT[sym]) daily volume,
  stored as ``whaleflow_{sym}`` (the build_flow_features "whale activity" series).
- daily CEX flow: net_inflow vs ALL_EXCHANGE_WALLETS, stored as ``cexflow_{sym}``.

Bitquery's ``dataset: combined`` has FULL token history (verified: CAKE from
2020-09-22), so a single aggregated query per token covers the whole backtest
window in one call -- far deeper than the GeckoTerminal 182-day DEX-volume cap.
The free tier is POINT-metered, so we keep it to TWO queries per token (one whale,
one CEX) and cache the result to parquet forever.

WHALE THRESHOLD CHOICE: WHALE_MIN_AMOUNT is a per-token map in NATIVE token units
(not USD), because Bitquery's Amount filter is token-denominated. A "whale"
large-transfer threshold is set per token to roughly the upper tail of typical
single transfers (documented per token below); tokens absent from the map fall
back to WHALE_MIN_AMOUNT_DEFAULT. This is a deliberate, honest heuristic -- it is
NOT a USD-normalized cut, and the resulting series is treated as a z-scored
ACTIVITY signal (see build_flow_features), so the absolute threshold only sets
which transfers count as "large", not the scale of the feature.

Usage:
    # set BITQUERY_API_KEY in .env first
    uv run python scripts/whale_backfill.py --start 2021-01-01 --end 2026-06-01
"""

import argparse
import time
from datetime import date, timedelta

import pandas as pd

from helm.config import BITQUERY_API_KEY
from helm.data.bitquery import BitqueryAdapter
from helm.data.exchange_wallets import ALL_EXCHANGE_WALLETS
from helm.data.onchain_cache import OnchainCache
from helm.data.universe import MAJORS

from scripts.onchain_backfill import BSC_TOKEN_ADDRESSES

# Per-token large-transfer threshold in NATIVE token units. Chosen ~upper tail of
# single transfers per token (honest heuristic; see module docstring). Tokens not
# listed use WHALE_MIN_AMOUNT_DEFAULT.
WHALE_MIN_AMOUNT_DEFAULT = "10000"
WHALE_MIN_AMOUNT: dict[str, str] = {
    "CAKE": "10000",   # CAKE ~ $2-3 -> ~$20-30k+ transfers
    "ETH":  "10",      # BSC-pegged ETH
    "XRP":  "50000",
    "ADA":  "50000",
    "DOGE": "1000000",
    "LINK": "5000",
    "DOT":  "5000",
    "AVAX": "2000",
}


def flow_panel(cache, symbols: list[str], kind: str = "whale") -> pd.DataFrame:
    """Per-symbol flow panel from the cache (missing symbols skipped).

    Pure / network-free: ``kind="whale"`` reads ``whaleflow_{sym}``, ``kind="cex"``
    reads ``cexflow_{sym}``; assembles a date x symbol frame. Symbols with no
    cached series are omitted; an empty result is an empty frame."""
    prefix = "whaleflow_" if kind == "whale" else "cexflow_"
    cols: dict[str, pd.Series] = {}
    for sym in symbols:
        s = cache.get_series(f"{prefix}{sym}")
        if s is not None and len(s) > 0:
            cols[sym] = s
    if not cols:
        return pd.DataFrame()
    panel = pd.DataFrame(cols).sort_index()
    ordered = [s for s in symbols if s in panel.columns]
    return panel[ordered]


def _retry(fn, attempts: int = 3, backoff: float = 2.0):
    """Call ``fn`` with polite exponential backoff on transient errors."""
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - backfill is best-effort
            last = exc
            if i < attempts - 1:
                time.sleep(backoff * (2 ** i))
    raise last


def backfill_flows(adapter, cache, symbols, addresses, start, end) -> list:
    """Cache-first per-token whale + CEX backfill; returns summary rows.

    For each symbol: if BOTH whaleflow_{sym} and cexflow_{sym} are already cached
    (non-empty), skip (do not re-burn metered points). Else fetch the missing
    side(s) and store them. Returns (sym, whale_days, cex_days, status)."""
    summary = []
    for sym in symbols:
        addr = addresses.get(sym)
        if addr is None:
            summary.append((sym, 0, 0, "no-address"))
            continue
        whale_cached = cache.get_series(f"whaleflow_{sym}")
        cex_cached = cache.get_series(f"cexflow_{sym}")
        if (whale_cached is not None and len(whale_cached) > 0
                and cex_cached is not None and len(cex_cached) > 0):
            summary.append((sym, len(whale_cached), len(cex_cached), "cached"))
            continue
        min_amt = WHALE_MIN_AMOUNT.get(sym, WHALE_MIN_AMOUNT_DEFAULT)
        if whale_cached is None or len(whale_cached) == 0:
            wf = _retry(
                lambda: adapter.daily_token_flow(addr, start, end, min_amount=min_amt)
            )
            whale_series = (
                wf["volume"].rename("whale_volume") if not wf.empty
                else pd.Series(dtype=float, name="whale_volume")
            )
            cache.put_series(f"whaleflow_{sym}", whale_series)
        else:
            whale_series = whale_cached
        if cex_cached is None or len(cex_cached) == 0:
            cf = _retry(
                lambda: adapter.daily_cex_flow(addr, ALL_EXCHANGE_WALLETS, start, end)
            )
            cex_series = (
                cf["net_inflow"].rename("cex_net_inflow") if not cf.empty
                else pd.Series(dtype=float, name="cex_net_inflow")
            )
            cache.put_series(f"cexflow_{sym}", cex_series)
        else:
            cex_series = cex_cached
        summary.append((sym, len(whale_series), len(cex_series), "fetched"))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill BSC whale + CEX flow")
    today = date.today()
    parser.add_argument("--start", default=(today - timedelta(days=1095)).isoformat())
    parser.add_argument("--end", default=today.isoformat())
    args = parser.parse_args()

    if not BITQUERY_API_KEY:
        raise SystemExit("Set BITQUERY_API_KEY in .env first.")

    cache = OnchainCache()
    with BitqueryAdapter(api_key=BITQUERY_API_KEY) as adapter:
        summary = backfill_flows(
            adapter, cache, MAJORS, BSC_TOKEN_ADDRESSES, args.start, args.end
        )

    print(f"\n{'symbol':8s}{'whale_days':>12s}{'cex_days':>10s}{'status':>10s}")
    print("-" * 40)
    for sym, wd, cd, status in summary:
        print(f"{sym:8s}{wd:>12d}{cd:>10d}{status:>10s}")


if __name__ == "__main__":
    main()
