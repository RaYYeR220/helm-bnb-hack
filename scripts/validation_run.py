"""Manual end-to-end validation: build a long live panel, run every candidate
config as a single full-panel backtest, select the best Helm variant on
walk-forward TRAIN windows, report it out-of-sample, deflate its Sharpe for the
true trial count, bootstrap its confidence intervals, and write a JSON artifact.

Usage:
    # set CMC_API_KEY in .env first
    uv run python scripts/validation_run.py --days 1095

This script hits the live CMC API and is run by a human; the unit tests only
import-check it and exercise the pure ``make_confirmed_gate`` factory. All other
helpers below are network-free.
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
from helm.data.universe import MAJORS
from helm.regime.classifier import compute_regime_path
from helm.regime.market_state import market_risk_off
from helm.strategies.baselines import EqualWeight
from helm.strategies.momentum import CrossSectionalMomentum
from helm.validation.bootstrap import bootstrap_metric_ci
from helm.validation.deflated_sharpe import deflated_sharpe_ratio
from helm.validation.harness import evaluate_windows, select_config
from helm.validation.windows import walk_forward_windows

# build_router is the live regime->strategy mapping defined in regime_backtest.
from scripts.regime_backtest import build_router

HELM_VARIANTS = (
    "helm_gated",
    "helm_gate_confirm2",
    "helm_gate_confirm3",
    "helm_ungated",
)


def make_confirmed_gate(base_gate, confirm: int):
    """Wrap a boolean risk gate so its state only flips after ``confirm``
    CONSECUTIVE confirming reads (debounce flickers).

    The returned closure carries mutable state (current active flag, the last
    raw read, and the consecutive-read streak) across sequential calls. It is
    therefore valid ONLY inside a single sequential backtest run, which walks
    days in order; construct a FRESH gate per ``run_backtest`` call. The gate
    starts in the risk-ON (active=False) state and flips to risk-OFF only after
    ``confirm`` consecutive True reads, and back to risk-ON only after
    ``confirm`` consecutive False reads. A one-day flicker never flips it.
    """
    state = {"active": False, "last": None, "streak": 0}

    def gate(prices_hist) -> bool:
        raw = bool(base_gate(prices_hist))
        if raw == state["last"]:
            state["streak"] += 1
        else:
            state["last"] = raw
            state["streak"] = 1
        if raw != state["active"] and state["streak"] >= confirm:
            state["active"] = raw
        return state["active"]

    return gate


def build_configs(panel, regime_path, cfg) -> dict:
    """Run each candidate strategy as one full-panel backtest -> return Series.

    A fresh confirmation gate is constructed per backtest (its state is sequential
    and single-run only). Returns a dict config-name -> per-day net-return Series.
    """
    momentum = CrossSectionalMomentum(lookback=30, top_n=3)

    def gated_strategy():
        return build_router(regime_path, risk_gate=market_risk_off)

    def confirm_strategy(confirm: int):
        gate = make_confirmed_gate(market_risk_off, confirm=confirm)
        return build_router(regime_path, risk_gate=gate)

    strategies = {
        "helm_gated": gated_strategy(),
        "helm_gate_confirm2": confirm_strategy(2),
        "helm_gate_confirm3": confirm_strategy(3),
        "helm_ungated": build_router(regime_path),
        "momentum": momentum,
        "equal_weight": EqualWeight(),
    }
    return {
        name: run_backtest(panel, strat, cfg).returns
        for name, strat in strategies.items()
    }


def _records(df) -> list:
    """JSON-serializable records from a DataFrame (Timestamps -> ISO strings)."""
    out = []
    for _, row in df.iterrows():
        rec = {}
        for k, v in row.items():
            if hasattr(v, "strftime"):
                rec[k] = v.strftime("%Y-%m-%d")
            elif v is None or (isinstance(v, float) and v != v):
                rec[k] = None
            else:
                rec[k] = float(v) if isinstance(v, (int, float, np.floating)) else v
        out.append(rec)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Helm validation harness run")
    parser.add_argument(
        "--days", type=int, default=1095, help="panel length in days (default 1095)"
    )
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

    regime_path = compute_regime_path(panel, min_train=60, refit_every=5, seed=0)
    print(f"Regime path: {len(regime_path)} classified days")
    print(regime_path.value_counts().to_string())

    cfg = BacktestConfig()
    configs = build_configs(panel, regime_path, cfg)

    # --- config selection on walk-forward windows (Helm variants only) --------
    windows = walk_forward_windows(panel.index, n_windows=6, embargo=5)
    helm_configs = {k: configs[k] for k in HELM_VARIANTS}
    selection = select_config(helm_configs, windows, metric="sharpe")

    print("\n=== Walk-forward config selection (Helm variants) ===")
    print(selection["per_window"].to_string(index=False))
    print("OOS aggregate:")
    for k, v in selection["oos"].items():
        print(f"  {k:24s} {v:+.5f}")

    # --- per-config OOS evaluation (all configs, baselines as reference) ------
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
            f"  {name:20s} sharpe={s['mean_sharpe']:+.4f}  "
            f"total={s['mean_total_return']:+.4f}  maxDD={s['mean_max_drawdown']:+.4f}"
        )

    # --- pick the OOS-selected Helm variant (most-chosen across windows) ------
    chosen = selection["per_window"]["chosen"]
    selected_variant = (
        chosen.mode().iloc[0] if len(chosen) else HELM_VARIANTS[0]
    )
    selected_returns = configs[selected_variant]
    print(f"\nOOS-selected Helm variant: {selected_variant}")

    # --- Deflated Sharpe with the TRUE trial count ----------------------------
    n_trials = len(HELM_VARIANTS)
    per_period_srs = []
    for k in HELM_VARIANTS:
        r = configs[k].dropna().to_numpy()
        sd = r.std(ddof=1) if len(r) > 1 else 0.0
        per_period_srs.append(r.mean() / sd if sd > 1e-12 else 0.0)
    sr_variance = max(float(np.var(per_period_srs, ddof=1)) if len(per_period_srs) > 1 else 0.0, 1e-12)
    dsr = deflated_sharpe_ratio(selected_returns, n_trials=n_trials, sr_variance=sr_variance)
    print(f"Deflated Sharpe (n_trials={n_trials}, sr_var={sr_variance:.3e}): {dsr:.4f}")

    # --- bootstrap confidence intervals for the selected variant --------------
    ann_sharpe = lambda x: float(x.mean() / x.std(ddof=1) * np.sqrt(365)) if x.std(ddof=1) > 1e-12 else 0.0
    total_return = lambda x: float(np.prod(1.0 + x) - 1.0)
    sharpe_ci = bootstrap_metric_ci(selected_returns, ann_sharpe, n_boot=1000, block_len=10, seed=0)
    tr_ci = bootstrap_metric_ci(selected_returns, total_return, n_boot=1000, block_len=10, seed=0)
    print(
        f"Bootstrap 90% CI  sharpe=[{sharpe_ci['lo']:+.3f}, {sharpe_ci['hi']:+.3f}] "
        f"point={sharpe_ci['point']:+.3f}"
    )
    print(
        f"Bootstrap 90% CI  total_return=[{tr_ci['lo']:+.3f}, {tr_ci['hi']:+.3f}] "
        f"point={tr_ci['point']:+.3f}"
    )

    # --- artifact -------------------------------------------------------------
    out_path = Path("data_cache/validation_artifact.json")
    payload = {
        "panel": {"days": int(panel.shape[0]), "symbols": list(panel.columns)},
        "regime_value_counts": {str(k): int(v) for k, v in regime_path.value_counts().items()},
        "selection": {
            "per_window": _records(selection["per_window"]),
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
