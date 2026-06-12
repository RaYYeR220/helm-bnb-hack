"""Human-run whale/CEX flow validation through the Plan D harness.

Builds the live price panel (CMC, cache-first), builds the on-chain TVL feature
frame (DeFiLlama via build_onchain_features) AND the whale/CEX flow feature frame
(build_flow_features from the cached whaleflow_/cexflow_ series), concatenates them
into ONE extra_features frame, and computes TWO causal regime paths with the SAME
seed:

  - tvl       : extra_features = TVL features only (Plan C baseline)
  - tvl_flow  : extra_features = TVL features + whale/CEX flow features (Plan F)

It then assembles THREE Helm variants as full-panel per-day return Series:

  - helm_gated_tvl           : router on the TVL-only regime path (baseline)
  - helm_gated_tvl_flow      : router on the TVL+flow-augmented regime path
  - helm_gated_tvl_flow_veto : TVL+flow regime path, AND the trending slot is the
        OnchainConfirmedMomentum with the CEX-inflow veto wired (cex_inflow = the
        per-symbol CEX net-inflow panel from the cache)

plus an equal_weight reference. The three Helm variants are selected on walk-
forward TRAIN windows (select_config) and reported OOS; the OOS-selected variant's
Sharpe is deflated for the true trial count (n_trials=3) and bracketed by a block
bootstrap. Writes data_cache/flow_validation_artifact.json.

HONEST-DEPTH NOTE: unlike the GeckoTerminal DEX-volume series (~182 days), the
Bitquery whale + CEX flow series have FULL token history (combined dataset; CAKE
back to 2020-09-22), so the flow features cover the entire backtest window. The
only depth caveat is the per-token whale THRESHOLD heuristic (native units, not
USD-normalized) and the exchange-wallet coverage (a conservative curated set;
under-counted exchanges only soften, never invert, the signal). Printed at run.

Usage:
    # set CMC_API_KEY and BITQUERY_API_KEY in .env; run whale_backfill.py first
    uv run python scripts/flow_validation.py --days 1095
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
from helm.data.onchain_cache import (
    OnchainCache,
    build_flow_features,
    build_onchain_features,
)
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

from scripts.whale_backfill import flow_panel
from scripts.regime_backtest import format_metrics_table

HELM_VARIANTS = (
    "helm_gated_tvl",
    "helm_gated_tvl_flow",
    "helm_gated_tvl_flow_veto",
)


def build_helm_configs_offline(series: dict) -> dict:
    """Passthrough packaging pre-built per-day return Series into the harness-
    ready config dict. Pure / network-free (unit-testable)."""
    return dict(series)


def _router(regime_path, trending_strategy=None, risk_gate=market_risk_off):
    """Risk-off-gated RegimeRouter; optionally override the trending slot."""
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
    parser = argparse.ArgumentParser(description="Helm whale/CEX flow validation")
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

    # --- TVL features + flow features -> one extra_features frame --------------
    onchain_cache = OnchainCache()
    with DefiLlamaAdapter() as llama:
        tvl_feats = build_onchain_features(llama, onchain_cache, panel.index)
    flow_feats = build_flow_features(onchain_cache, panel.index, MAJORS)
    tvl_flow_feats = tvl_feats.join(flow_feats)
    print(f"TVL features : {list(tvl_feats.columns)}")
    print(f"Flow features: {list(flow_feats.columns)}")

    # flow coverage (non-zero rows) -> honest depth printout
    flow_cover = int((flow_feats.abs().sum(axis=1) > 0).sum())
    print(
        f"Flow-feature coverage: {flow_cover}/{panel.shape[0]} panel days non-zero "
        f"(Bitquery combined dataset has full token history; run whale_backfill.py "
        f"to populate whaleflow_/cexflow_ series)."
    )

    # --- two causal regime paths, same seed -----------------------------------
    tvl_path = compute_regime_path(
        panel, min_train=60, refit_every=5, seed=0, extra_features=tvl_feats
    )
    tvl_flow_path = compute_regime_path(
        panel, min_train=60, refit_every=5, seed=0, extra_features=tvl_flow_feats
    )
    print(f"TVL path: {len(tvl_path)} days; TVL+flow path: {len(tvl_flow_path)} days")
    print("TVL     :", tvl_path.value_counts().to_dict())
    print("TVL+flow:", tvl_flow_path.value_counts().to_dict())

    # --- CEX-inflow panel for the veto variant --------------------------------
    cex_panel = flow_panel(onchain_cache, MAJORS, kind="cex")
    cex_arg = None if cex_panel.empty else cex_panel
    confirmed_trending = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=30, top_n=3),
        cex_inflow=cex_arg,
        cex_veto_threshold=2.0,
        confirm_window=7,
    )

    cfg = BacktestConfig()
    strategies = {
        "helm_gated_tvl": _router(tvl_path),
        "helm_gated_tvl_flow": _router(tvl_flow_path),
        "helm_gated_tvl_flow_veto": _router(tvl_flow_path, confirmed_trending),
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

    print("\n=== Walk-forward config selection (flow Helm variants) ===")
    print(selection["per_window"].to_string(index=False))
    print("OOS aggregate:")
    for k, v in selection["oos"].items():
        print(f"  {k:24s} {v:+.5f}")

    # --- per-config mean OOS --------------------------------------------------
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
            f"  {name:28s} sharpe={s['mean_sharpe']:+.4f}  "
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
    out_path = Path("data_cache/flow_validation_artifact.json")
    payload = {
        "panel": {"days": int(panel.shape[0]), "symbols": list(panel.columns)},
        "tvl_feature_cols": list(tvl_feats.columns),
        "flow_feature_cols": list(flow_feats.columns),
        "flow_coverage_days": flow_cover,
        "regime_value_counts": {
            "tvl": {str(k): int(v) for k, v in tvl_path.value_counts().items()},
            "tvl_flow": {str(k): int(v) for k, v in tvl_flow_path.value_counts().items()},
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
