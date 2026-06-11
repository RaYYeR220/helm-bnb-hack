"""Human-run on-chain backfill: per-token BSC DEX volume + TVL into the cache.

For each major: discover its highest-reserve BSC pool (GeckoTerminal), pull up
to ``--days`` daily OHLCV candles (free-tier cap 182), and store the per-symbol
daily volume Series to the onchain cache under ``dexvol_{symbol}``. Also backfill
the two DeFiLlama TVL series (``bsc_tvl``, ``pancake_tvl``). Prints a summary
table. Spaces GeckoTerminal calls via the adapter's min-interval throttle.

The BSC_TOKEN_ADDRESSES map is the BEP-20 contract for each major (all verified
to resolve to a live BSC pool). DEX-volume history is only ~182 days deep; that
is honest and intentional — the confirmation strategy degrades to plain momentum
on older dates.

Usage:
    uv run python scripts/onchain_backfill.py --days 182
"""

import argparse

import pandas as pd

from helm.data.defillama import DefiLlamaAdapter
from helm.data.geckoterminal import GeckoTerminalAdapter
from helm.data.onchain_cache import OnchainCache
from helm.data.universe import MAJORS

# Real BEP-20 (wrapped) contract addresses on BSC for the 8 majors. Every one
# resolves to a liquid PancakeSwap pool (verified live).
BSC_TOKEN_ADDRESSES: dict[str, str] = {
    "CAKE": "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82",
    "ETH":  "0x2170ed0880ac9a755fd29b2688956bd959f933f8",
    "XRP":  "0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe",
    "ADA":  "0x3ee2200efb3400fabb9aacf31297cbdd1d435d47",
    "DOGE": "0xba2ae424d960c26247dd6c32edc70b295c744c43",
    "LINK": "0xf8a0bf9cf54bb92f17374d9e9a321e6a111a51bd",
    "DOT":  "0x7083609fce4d1d8dc0c979aab8c869ea2c873402",
    "AVAX": "0x1ce0c2827e2ef14d5c4f29a091d735a204794041",
}


def dex_volume_panel(cache, symbols: list[str]) -> pd.DataFrame:
    """Per-symbol DEX volume panel from the cache (missing symbols skipped).

    Pure / network-free: reads ``dexvol_{symbol}`` Series from ``cache`` and
    assembles a date x symbol frame. Symbols with no cached series are omitted.
    """
    cols: dict[str, pd.Series] = {}
    for sym in symbols:
        s = cache.get_series(f"dexvol_{sym}")
        if s is not None and len(s) > 0:
            cols[sym] = s
    if not cols:
        return pd.DataFrame()
    panel = pd.DataFrame(cols).sort_index()
    ordered = [s for s in symbols if s in panel.columns]
    return panel[ordered]


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill BSC on-chain data")
    parser.add_argument(
        "--days", type=int, default=182, help="daily candles to request (cap 182)"
    )
    args = parser.parse_args()
    limit = min(args.days, 182)

    cache = OnchainCache()

    # --- per-token DEX volume -------------------------------------------------
    summary = []
    with GeckoTerminalAdapter() as gt:
        for sym in MAJORS:
            addr = BSC_TOKEN_ADDRESSES.get(sym)
            if addr is None:
                summary.append((sym, "no-address", 0, 0.0))
                continue
            pool = gt.token_top_pool(addr)
            if pool is None:
                summary.append((sym, "no-pool", 0, 0.0))
                continue
            ohlcv = gt.pool_ohlcv_daily(pool["pool_address"], limit=limit)
            if ohlcv.empty:
                summary.append((sym, pool["pool_address"][:10], 0, 0.0))
                continue
            vol = ohlcv["volume"].rename("volume")
            cache.put_series(f"dexvol_{sym}", vol)
            latest = float(vol.iloc[-1])
            summary.append((sym, pool["pool_address"][:10], len(vol), latest))

    # --- TVL series -----------------------------------------------------------
    with DefiLlamaAdapter() as llama:
        chain = llama.chain_tvl("BSC")
        cache.put_series("bsc_tvl", chain)
        pancake = llama.protocol_chain_tvl()
        cache.put_series("pancake_tvl", pancake)
    print(f"TVL: bsc_tvl={len(chain)} days, pancake_tvl={len(pancake)} days")

    # --- summary table --------------------------------------------------------
    print(f"\n{'symbol':8s}{'pool':14s}{'days':>6s}{'latest_vol':>16s}")
    print("-" * 44)
    for sym, pool, days, latest in summary:
        print(f"{sym:8s}{pool:14s}{days:>6d}{latest:>16.2f}")


if __name__ == "__main__":
    main()
