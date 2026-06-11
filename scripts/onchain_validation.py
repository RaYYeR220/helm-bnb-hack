"""Human-run on-chain validation through the Plan D harness.

Builds the live price panel (CMC, cache-first), builds the on-chain TVL feature
frame (DeFiLlama via the onchain cache), computes TWO causal regime paths with
the SAME seed -- a baseline (no extras) and a 'tvl' path (extra_features = the
on-chain frame) -- and assembles THREE Helm variants as full-panel per-day
return Series:

  - helm_gated            : router on the baseline regime path (risk-off gated)
  - helm_gated_tvl        : router on the TVL-augmented regime path
  - helm_gated_tvl_confirmed : TVL path, but the trending slot is the
        OnchainConfirmedMomentum (dex_volume from the cache via dex_volume_panel)

plus an equal_weight reference. The three Helm variants are selected on
walk-forward TRAIN windows (select_config) and reported OOS; the OOS-selected
variant's Sharpe is deflated for the true trial count (n_trials=3) and bracketed
by a block bootstrap. Writes data_cache/onchain_validation_artifact.json.

HONEST-DEPTH NOTE: per-token DEX volume only covers ~182 days. On earlier panel
dates the OnchainConfirmedMomentum keep-if-no-data fallback degrades it to plain
momentum, so helm_gated_tvl_confirmed differs from helm_gated_tvl only over the
recent ~6-month window. This is printed at run time.

Usage:
    # set CMC_API_KEY in .env first
    uv run python scripts/onchain_validation.py --days 1095
"""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from helm.backtest.engine import run_backtest
from helm.backtest.result import BacktestConfig
from helm.config import CMC_API_KEY, CMC_BASE_URL
from helm.data.cache import OHLCVCache, build_price_panel
from helm.data.cmc import CMCAdapter
from helm.data.defillama import DefiLlamaAdapter
from helm.data.onchain_cache import OnchainCache, build_onchain_features
from helm.data.universe import MAJORS
from helm.regime.classifier import compute_regime_path
from helm.regime.market_state import market_risk_off
from helm.strategies.baselines import EqualWeight
from helm.strategies.defensive import Defensive
from helm.strategies.momentum import CrossSectionalMomentum
from helm.strategies.momentum_confirmed import OnchainConfirmedMomentum
from helm.router.router import RegimeRouter
from helm.validation.bootstrap import bootstrap_metric_ci
from helm.validation.deflated_sharpe import deflated_sharpe_ratio
from helm.validation.harness import evaluate_windows, select_config
from helm.validation.windows import walk_forward_windows

from scripts.onchain_backfill import dex_volume_panel
from scripts.regime_backtest import format_metrics_table

HELM_VARIANTS = (
    "helm_gated",
    "helm_gated_tvl",
    "helm_gated_tvl_confirmed",
)


def build_helm_configs_offline(series: dict) -> dict:
    """Passthrough that packages pre-built per-day return Series into the
    harness-ready config dict. Pure / network-free (unit-testable).

    Real runs build the Series via run_backtest; this indirection keeps the
    config-assembly contract testable offline.
    """
    return dict(series)


def _router(regime_path, trending_strategy=None, risk_gate=market_risk_off):
    """Build a risk-off-gated RegimeRouter; optionally override the trending
    slot (used to inject OnchainConfirmedMomentum)."""
    trending = trending_strategy or CrossSectionalMomentum(lookback=30, top_n=3)
    strategies = {
        "trending": trending,
        "ranging": EqualWeight(),
        "high_volatility": Defensive(),
    }
    return RegimeRouter(
        regime_path, strategies, hysteresis=3, default_regime="ranging",
        risk_gate=risk_gate,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Helm on-chain validation run")
    parser.add_argument("--days", type=int, default=1095, help="panel length")
    args = parser.parse_args()

    if not CMC_API_KEY:
        raise SystemExit("Set CMC_API_KEY in .env first.")

    end = date.today()
    start = end - timedelta(days=args.days)
    cache = OHLCVCache()
    with CMCAdapter(api_key=CMC_API_KEY, base_url=CMC_BASE_URL) as adapter:
        panel = build_price_panel(
            MAJORS, adapter, cache, start.isoformat(), end.isoformat()
        )
    print(f"Panel: {panel.shape[0]} days x {panel.shape[1]} symbols -> {list(panel.columns)}")

    # --- on-chain features (cache-first; live DeFiLlama on a cold cache) -------
    onchain_cache = OnchainCache()
    with DefiLlamaAdapter() as llama:
        onchain_feats = build_onchain_features(llama, onchain_cache, panel.index)
    print(f"On-chain features: {list(onchain_feats.columns)}")

    # --- two causal regime paths, same seed -----------------------------------
    base_path = compute_regime_path(panel, min_train=60, refit_every=5, seed=0)
    tvl_path = compute_regime_path(
        panel, min_train=60, refit_every=5, seed=0, extra_features=onchain_feats
    )
    print(f"Baseline regime path: {len(base_path)} days; TVL path: {len(tvl_path)} days")
    print("Baseline:", base_path.value_counts().to_dict())
    print("TVL     :", tvl_path.value_counts().to_dict())

    # --- DEX-volume panel for the confirmed variant ---------------------------
    dexvol = dex_volume_panel(onchain_cache, MAJORS)
    dex_cover = 0 if dexvol.empty else len(dexvol)
    print(
        f"DEX-volume coverage: {dex_cover} days "
        f"(panel is {panel.shape[0]} days; earlier dates degrade to plain "
        f"momentum via keep-if-no-data)."
    )

    cfg = BacktestConfig()
    confirmed_trending = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=30, top_n=3),
        dex_volume=(None if dexvol.empty else dexvol),
        confirm_window=7,
    )

    strategies = {
        "helm_gated": _router(base_path),
        "helm_gated_tvl": _router(tvl_path),
        "helm_gated_tvl_confirmed": _router(tvl_path, confirmed_trending),
        "equal_weight": EqualWeight(),
    }
    raw_returns = {
        name: run_backtest(panel, strat, cfg).returns
        for name, strat in strategies.items()
    }
    configs = build_helm_configs_offline(raw_returns)

    # --- walk-forward selection over the THREE helm variants ------------------
    windows = walk_forward_windows(panel.index, n_windows=6, embargo=5)
    helm_configs = {k: configs[k] for k in HELM_VARIANTS}
    selection = select_config(helm_configs, windows, metric="sharpe")

    print("\n=== Walk-forward config selection (on-chain Helm variants) ===")
    print(selection["per_window"].to_string(index=False))
    print("OOS aggregate:")
    for k, v in selection["oos"].items():
        print(f"  {k:24s} {v:+.5f}")

    # --- per-config mean OOS (all configs, like validation_run) ---------------
    print("\n=== Mean OOS metrics per config ===")
    per_config_oos = {}
    for name, returns in configs.items():
        ev = evaluate_windows(returns, windows)
        per_config_oos[name] = {
            "mean_sharpe": float(ev["sharpe"].mean()),
            "mean_total_return": float(ev["total_return"].mean()),
            "mean_max_drawdown": float(ev["max_drawdown"].mean()),
        }
        s = per_config_oos[name]
        print(
            f"  {name:26s} sharpe={s['mean_sharpe']:+.4f}  "
            f"total={s['mean_total_return']:+.4f}  maxDD={s['mean_max_drawdown']:+.4f}"
        )

    # --- OOS-selected variant -------------------------------------------------
    chosen = selection["per_window"]["chosen"]
    selected_variant = chosen.mode().iloc[0] if len(chosen) else HELM_VARIANTS[0]
    selected_returns = configs[selected_variant]
    print(f"\nOOS-selected Helm variant: {selected_variant}")

    # --- Deflated Sharpe with the TRUE trial count (3 variants) ---------------
    n_trials = len(HELM_VARIANTS)
    per_period_srs = []
    for k in HELM_VARIANTS:
        r = configs[k].dropna().to_numpy()
        sd = r.std(ddof=1) if len(r) > 1 else 0.0
        per_period_srs.append(r.mean() / sd if sd > 1e-12 else 0.0)
    sr_variance = max(
        float(np.var(per_period_srs, ddof=1)) if len(per_period_srs) > 1 else 0.0,
        1e-12,
    )
    dsr = deflated_sharpe_ratio(
        selected_returns, n_trials=n_trials, sr_variance=sr_variance
    )
    print(f"Deflated Sharpe (n_trials={n_trials}, sr_var={sr_variance:.3e}): {dsr:.4f}")

    # --- bootstrap CIs for the selected variant -------------------------------
    ann_sharpe = (
        lambda x: float(x.mean() / x.std(ddof=1) * np.sqrt(365))
        if x.std(ddof=1) > 1e-12 else 0.0
    )
    total_return = lambda x: float(np.prod(1.0 + x) - 1.0)
    sharpe_ci = bootstrap_metric_ci(
        selected_returns, ann_sharpe, n_boot=1000, block_len=10, seed=0
    )
    tr_ci = bootstrap_metric_ci(
        selected_returns, total_return, n_boot=1000, block_len=10, seed=0
    )
    print(
        f"Bootstrap 90% CI  sharpe=[{sharpe_ci['lo']:+.3f}, {sharpe_ci['hi']:+.3f}] "
        f"point={sharpe_ci['point']:+.3f}"
    )
    print(
        f"Bootstrap 90% CI  total_return=[{tr_ci['lo']:+.3f}, {tr_ci['hi']:+.3f}] "
        f"point={tr_ci['point']:+.3f}"
    )

    # --- artifact -------------------------------------------------------------
    out_path = Path("data_cache/onchain_validation_artifact.json")
    payload = {
        "panel": {"days": int(panel.shape[0]), "symbols": list(panel.columns)},
        "onchain_feature_cols": list(onchain_feats.columns),
        "dex_volume_coverage_days": int(dex_cover),
        "regime_value_counts": {
            "baseline": {str(k): int(v) for k, v in base_path.value_counts().items()},
            "tvl": {str(k): int(v) for k, v in tvl_path.value_counts().items()},
        },
        "selection": {
            "oos": {k: float(v) for k, v in selection["oos"].items()},
            "n_trials": selection["n_trials"],
            "selected_variant": selected_variant,
        },
        "per_config_oos": per_config_oos,
        "deflated_sharpe": {
            "value": float(dsr),
            "n_trials": n_trials,
            "sr_variance": float(sr_variance),
        },
        "bootstrap": {
            "sharpe": {k: float(v) for k, v in sharpe_ci.items() if k != "samples"},
            "total_return": {k: float(v) for k, v in tr_ci.items() if k != "samples"},
        },
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nArtifact written to {out_path}")


if __name__ == "__main__":
    main()
