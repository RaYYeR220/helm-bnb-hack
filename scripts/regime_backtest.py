"""Manual end-to-end: build the live price panel, compute the causal regime path,
run the Helm router vs. static baselines, print a comparison + regime P&L
attribution, and write a combined JSON artifact.

Usage:
    # set CMC_API_KEY in .env first
    uv run python scripts/regime_backtest.py

This script hits the live CMC API and is run by a human; the unit tests only
import-check it. All pure helpers below are network-free.
"""

import json
from datetime import date, timedelta
from pathlib import Path

from helm.backtest.attribution import regime_pnl_attribution
from helm.backtest.engine import run_backtest
from helm.backtest.result import BacktestConfig
from helm.config import CMC_API_KEY, CMC_BASE_URL
from helm.data.cache import OHLCVCache, build_price_panel
from helm.data.cmc import CMCAdapter
from helm.data.universe import MAJORS
from helm.regime.classifier import compute_regime_path
from helm.router.router import RegimeRouter
from helm.strategies.baselines import EqualWeight
from helm.strategies.defensive import Defensive
from helm.strategies.mean_reversion import CrossSectionalMeanReversion
from helm.strategies.momentum import CrossSectionalMomentum

METRIC_KEYS = ["total_return", "sharpe", "sortino", "max_drawdown", "win_rate", "turnover"]


def format_metrics_table(results: dict) -> str:
    """Render a {strategy_name: metrics_dict} mapping as an aligned text table.

    Pure / network-free so it can be unit-tested.
    """
    name_w = max([len("strategy")] + [len(n) for n in results]) + 2
    header = "strategy".ljust(name_w) + "".join(f"{k:>14s}" for k in METRIC_KEYS)
    lines = [header, "-" * len(header)]
    for name, metrics in results.items():
        row = name.ljust(name_w) + "".join(
            f"{float(metrics.get(k, 0.0)):>14.4f}" for k in METRIC_KEYS
        )
        lines.append(row)
    return "\n".join(lines)


def build_router(regime_path) -> RegimeRouter:
    """Map each regime label to its sub-strategy and wrap in the router."""
    strategies = {
        "trending": CrossSectionalMomentum(lookback=30, top_n=3),
        "ranging": CrossSectionalMeanReversion(lookback=10, bottom_n=3),
        "high_volatility": Defensive(),
    }
    return RegimeRouter(
        regime_path, strategies, hysteresis=3, default_regime="ranging"
    )


def main() -> None:
    if not CMC_API_KEY:
        raise SystemExit("Set CMC_API_KEY in .env first.")

    end = date.today()
    start = end - timedelta(days=365)
    cache = OHLCVCache()
    with CMCAdapter(api_key=CMC_API_KEY, base_url=CMC_BASE_URL) as adapter:
        panel = build_price_panel(
            MAJORS, adapter, cache, start.isoformat(), end.isoformat()
        )
    print(f"Panel: {panel.shape[0]} days x {panel.shape[1]} symbols -> {list(panel.columns)}")

    regime_path = compute_regime_path(
        panel, min_train=60, refit_every=5, seed=0
    )
    print(f"Regime path: {len(regime_path)} classified days")
    print(regime_path.value_counts().to_string())

    cfg = BacktestConfig()
    router = build_router(regime_path)

    strategies = {
        "helm": router,
        "momentum": CrossSectionalMomentum(lookback=30, top_n=3),
        "mean_reversion": CrossSectionalMeanReversion(lookback=10, bottom_n=3),
        "equal_weight": EqualWeight(),
    }

    results = {}
    equities = {}
    for name, strat in strategies.items():
        res = run_backtest(panel, strat, cfg)
        results[name] = res.metrics
        equities[name] = res
        if name == "helm":
            helm_res = res

    print("\n=== Strategy comparison ===")
    print(format_metrics_table(results))

    print("\n=== Helm regime P&L attribution ===")
    attribution = regime_pnl_attribution(helm_res.returns, regime_path)
    for regime, stats in attribution.items():
        print(
            f"  {regime:16s} days={stats['days']:4d}  "
            f"total={stats['total_return']:+.4f}  "
            f"mean={stats['mean_return']:+.5f}  "
            f"share={stats['share_of_pnl']:+.3f}"
        )

    out_path = Path("data_cache/regime_artifact.json")
    payload = {
        "regime_path": [
            {"date": d.strftime("%Y-%m-%d"), "regime": str(r)}
            for d, r in regime_path.items()
        ],
        "regime_attribution": attribution,
        "strategies": {
            name: {
                "metrics": res.metrics,
                "equity": [
                    {"date": d.strftime("%Y-%m-%d"),
                     "value": (None if v != v else float(v))}
                    for d, v in res.equity.items()
                ],
            }
            for name, res in equities.items()
        },
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nArtifact written to {out_path}")


if __name__ == "__main__":
    main()
