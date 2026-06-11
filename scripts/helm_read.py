"""Human-run live RegimeRead: the exact HMM-based read for the BSC majors.

Builds the live CMC close-price panel (cache-first, ~200 days, MAJORS), fuses the
on-chain TVL feature frame (DeFiLlama via the onchain cache; skipped gracefully if
the cache is empty), runs the walk-forward HMM regime classifier, applies the same
`market_risk_off` trend-filter gate the router uses, and prints a RegimeRead:
regime, confidence, posterior, top attribution features, the risk-off flag, and the
recommended stance.

This is the "Full mode" backing the helm-regime-read skill. It hits the live CMC
API and is run by a human; the unit tests only import-check it and exercise the
pure helpers (`read_to_dict`, `format_read`, `recommended_stance`) offline.

Usage:
    # set CMC_API_KEY in .env first
    uv run python scripts/helm_read.py            # human-readable report
    uv run python scripts/helm_read.py --json     # machine-readable JSON
    uv run python scripts/helm_read.py --days 250
"""

import argparse
import json
from datetime import date, timedelta

from helm.types import RegimeRead

# regime label -> recommended stance (matches scripts/regime_backtest.build_router)
_STANCE = {
    "trending": "momentum",
    "ranging": "market portfolio",
    "high_volatility": "defensive",
}


def recommended_stance(regime: str, risk_off: bool) -> str:
    """Map a regime label to Helm's stance, honoring the risk-off override.

    Pure / network-free. The risk-off gate (a market-level trend filter) overrides
    every regime to ``defensive`` -- this mirrors the router's risk_gate, which
    forces the defensive sub-strategy on a confirmed downtrend regardless of the
    HMM read. Unknown regimes fall back to ``market portfolio`` (the neutral stance).
    """
    if risk_off:
        return "defensive"
    return _STANCE.get(regime, "market portfolio")


def read_to_dict(read: RegimeRead, risk_off: bool) -> dict:
    """Serialize a RegimeRead (+ risk-off flag + stance) to a JSON-ready dict.

    Pure / network-free. Coerces the Timestamp to an ISO date string and all
    numeric values to floats so ``json.dumps`` never sees a numpy / pandas type.
    """
    return {
        "date": read.date.strftime("%Y-%m-%d"),
        "regime": read.regime,
        "confidence": float(read.confidence),
        "risk_off": bool(risk_off),
        "recommended_stance": recommended_stance(read.regime, risk_off),
        "posterior": {k: float(v) for k, v in read.posterior.items()},
        "features": {k: float(v) for k, v in read.features.items()},
        "attribution": {k: float(v) for k, v in read.attribution.items()},
    }


def format_read(read: RegimeRead, risk_off: bool, top_k: int = 3) -> str:
    """Render a RegimeRead as a compact human-readable report.

    Pure / network-free. Surfaces the regime, confidence, posterior, the top-k
    attribution features by absolute contribution, the risk-off gate state, and
    the recommended stance.
    """
    stance = recommended_stance(read.regime, risk_off)
    gate = (
        "FIRED -- index <50d MA or >10% off peak -> forced defensive"
        if risk_off
        else "CLEAR"
    )

    posterior = " | ".join(
        f"{k}={v:.2f}"
        for k, v in sorted(read.posterior.items(), key=lambda kv: -kv[1])
    )

    top = sorted(read.attribution.items(), key=lambda kv: -abs(kv[1]))[:top_k]
    attr_lines = [
        f"  {name:16s} {contrib:+.3f}  (raw={read.features.get(name, float('nan')):+.4f})"
        for name, contrib in top
    ]

    lines = [
        f"=== Helm RegimeRead -- {read.date.strftime('%Y-%m-%d')} ===",
        f"Regime:            {read.regime}   (confidence {read.confidence:.2f})",
        f"Risk-off gate:     {gate}",
        f"Recommended stance: {stance}",
        f"Posterior:         {posterior}",
        "Top attribution:",
        *attr_lines,
    ]
    return "\n".join(lines)


def _build_read(days: int):
    """Live: build the panel + on-chain features, fit the HMM, return the latest
    RegimeRead and the risk-off flag. Network-bound; not exercised by the tests."""
    # Imports are local so the module imports cleanly (and the pure helpers are
    # testable) without pulling the network/data stack at import time.
    from helm.config import CMC_API_KEY, CMC_BASE_URL
    from helm.data.cache import OHLCVCache, build_price_panel
    from helm.data.cmc import CMCAdapter
    from helm.data.defillama import DefiLlamaAdapter
    from helm.data.onchain_cache import OnchainCache, build_onchain_features
    from helm.data.universe import MAJORS
    from helm.regime.classifier import RegimeClassifier
    from helm.regime.hmm_model import RegimeHMM
    from helm.regime.features import FEATURE_COLS
    from helm.regime.market_state import market_risk_off

    if not CMC_API_KEY:
        raise SystemExit("Set CMC_API_KEY in .env first.")

    end = date.today()
    start = end - timedelta(days=days)
    cache = OHLCVCache()
    with CMCAdapter(api_key=CMC_API_KEY, base_url=CMC_BASE_URL) as adapter:
        panel = build_price_panel(
            MAJORS, adapter, cache, start.isoformat(), end.isoformat()
        )
    if panel.empty:
        raise SystemExit("Empty price panel -- check CMC_API_KEY / connectivity.")
    print(
        f"Panel: {panel.shape[0]} days x {panel.shape[1]} symbols "
        f"-> {list(panel.columns)}"
    )

    # --- on-chain TVL features (cache-first; graceful skip on a cold/empty cache)
    onchain_feats = None
    try:
        onchain_cache = OnchainCache()
        with DefiLlamaAdapter() as llama:
            feats = build_onchain_features(llama, onchain_cache, panel.index)
        if feats is not None and not feats.empty and (feats != 0.0).any().any():
            onchain_feats = feats
            print(f"On-chain features fused: {list(feats.columns)}")
        else:
            print("On-chain features empty -- proceeding market-data only.")
    except Exception as exc:  # noqa: BLE001 - on-chain is best-effort here
        print(f"On-chain features unavailable ({exc}) -- proceeding market-data only.")

    # --- exact HMM read on the full window -----------------------------------
    cols = (
        None
        if onchain_feats is None
        else list(FEATURE_COLS) + list(onchain_feats.columns)
    )
    clf = RegimeClassifier(
        hmm=RegimeHMM(seed=0, feature_cols=cols),
        extra_features=onchain_feats,
    )
    clf.fit(panel)
    read = clf.read(panel)

    risk_off = market_risk_off(panel)
    return read, risk_off


def main() -> None:
    parser = argparse.ArgumentParser(description="Helm live RegimeRead")
    parser.add_argument("--days", type=int, default=200, help="panel length")
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON"
    )
    args = parser.parse_args()

    read, risk_off = _build_read(args.days)

    if args.json:
        print(json.dumps(read_to_dict(read, risk_off), indent=2))
    else:
        print()
        print(format_read(read, risk_off))


if __name__ == "__main__":
    main()
