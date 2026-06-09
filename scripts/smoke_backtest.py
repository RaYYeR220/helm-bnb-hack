"""Manual end-to-end smoke: pull real CMC daily OHLCV for the majors, run the
momentum backtest, print metrics, and write the artifact.

Usage:
    # set CMC_API_KEY in .env first
    uv run python scripts/smoke_backtest.py
"""

from datetime import date, timedelta

from helm.config import CMC_API_KEY, CMC_BASE_URL
from helm.data.cmc import CMCAdapter
from helm.data.cache import OHLCVCache, build_price_panel
from helm.data.universe import MAJORS
from helm.strategies.momentum import CrossSectionalMomentum
from helm.backtest.engine import run_backtest
from helm.backtest.result import BacktestConfig


def main() -> None:
    if not CMC_API_KEY:
        raise SystemExit("Set CMC_API_KEY in .env first.")

    end = date.today()
    start = end - timedelta(days=365)
    adapter = CMCAdapter(api_key=CMC_API_KEY, base_url=CMC_BASE_URL)
    cache = OHLCVCache()

    panel = build_price_panel(
        MAJORS, adapter, cache, start.isoformat(), end.isoformat()
    )
    print(f"Panel: {panel.shape[0]} days x {panel.shape[1]} symbols -> {list(panel.columns)}")

    result = run_backtest(panel, CrossSectionalMomentum(lookback=30, top_n=3), BacktestConfig())
    print("Metrics:")
    for k, v in result.metrics.items():
        print(f"  {k:14s}: {v:.4f}")

    out = "data_cache/smoke_artifact.json"
    result.to_json(out)
    print(f"Artifact written to {out}")


if __name__ == "__main__":
    main()
