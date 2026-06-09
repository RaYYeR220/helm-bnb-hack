"""BSC token universe (the BNB Hack Track-1 eligible BEP-20 list)."""

import json
from functools import lru_cache
from pathlib import Path

_UNIVERSE_PATH = Path(__file__).with_name("universe_bsc_149.json")

# A liquid, data-rich subset used for smoke tests and quick runs.
MAJORS = ["ETH", "XRP", "ADA", "LINK", "DOGE", "AVAX", "DOT", "CAKE"]


@lru_cache(maxsize=1)
def load_universe() -> list[str]:
    """Return the deduplicated list of universe symbols, order-preserving."""
    data = json.loads(_UNIVERSE_PATH.read_text(encoding="utf-8"))
    seen: set[str] = set()
    out: list[str] = []
    for sym in data["symbols"]:
        if sym not in seen:
            seen.add(sym)
            out.append(sym)
    return out
