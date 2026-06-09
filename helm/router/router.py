"""Regime router: switch sub-strategies by regime, with hysteresis.

The router consumes a per-date regime-label series, walks it with hysteresis to
suppress short flickers, and delegates `target_weights` to the regime-appropriate
sub-strategy. An optional `risk_gate` (Regime v2) overrides everything: when the
gate reports a confirmed market downtrend, the router goes defensive regardless
of the HMM regime — the 3-state taxonomy cannot tell up-trends from down-trends,
and mean-reverting into a bear market buys falling knives.
"""

from typing import Callable

import pandas as pd

from helm.strategies.base import Strategy


def apply_hysteresis(labels: list[str], hysteresis: int, default: str) -> str:
    """Walk the label sequence and return the active regime at the end.

    The active regime only switches to a candidate label once that candidate has
    persisted for `hysteresis` consecutive observations. Before any regime first
    reaches the threshold, the active regime is `default`.
    """
    active = default
    candidate: str | None = None
    streak = 0
    confirmed = False  # has any regime reached the threshold yet?

    for lab in labels:
        if lab == candidate:
            streak += 1
        else:
            candidate = lab
            streak = 1

        if streak >= hysteresis:
            active = candidate
            confirmed = True

    return active if confirmed else default


class RegimeRouter(Strategy):
    """A `Strategy` that delegates to a regime-specific sub-strategy."""

    name = "helm"

    def __init__(
        self,
        regime_path: pd.Series,
        strategies: dict[str, Strategy],
        hysteresis: int = 3,
        default_regime: str = "ranging",
        risk_gate: Callable[[pd.DataFrame], bool] | None = None,
    ):
        self.regime_path = regime_path.sort_index()
        self.strategies = strategies
        self.hysteresis = hysteresis
        self.default_regime = default_regime
        self.risk_gate = risk_gate

    def target_weights(self, prices_hist: pd.DataFrame) -> pd.Series:
        # Regime v2: the risk-off gate overrides regime routing entirely —
        # capital preservation first, regardless of what the HMM says.
        if self.risk_gate is not None and self.risk_gate(prices_hist):
            return self.strategies["high_volatility"].target_weights(prices_hist)
        date = prices_hist.index[-1]
        if len(self.regime_path) == 0 or date not in self.regime_path.index:
            return self._zero_weights(prices_hist)
        labels = list(self.regime_path.loc[:date])
        active = apply_hysteresis(labels, self.hysteresis, self.default_regime)
        strat = self.strategies[active]
        return strat.target_weights(prices_hist)
