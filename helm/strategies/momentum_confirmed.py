"""On-chain-confirmed cross-sectional momentum.

Wraps a ``CrossSectionalMomentum`` and uses per-symbol DEX volume to CONFIRM or
VETO each positive-momentum candidate before allocating:

- CONFIRM (keep) a name if its DEX-volume mean over the trailing
  ``confirm_window`` days (data <= the decision date) is >= its mean over the
  prior ``confirm_window`` days (rising / steady on-chain activity).
- VETO (drop) a name if its trailing-window mean has fallen by MORE than 50%
  versus the prior window (collapsing activity — momentum without flow).
- KEEP a name with no usable DEX series (honest graceful fallback: with no
  on-chain data the strategy degrades to plain momentum).

Survivors are re-equal-weighted; if every candidate is vetoed (or the base has
no conviction) the result is all-zero (cash). All reads are causal: only volume
rows with date <= the decision date are inspected.
"""

import pandas as pd

from helm.strategies.base import Strategy


class OnchainConfirmedMomentum(Strategy):
    name = "momentum_onchain"

    def __init__(
        self,
        base,
        dex_volume: pd.DataFrame | None = None,
        confirm_window: int = 7,
    ):
        self.base = base
        self.dex_volume = (
            dex_volume.sort_index() if dex_volume is not None else None
        )
        self.confirm_window = confirm_window

    def _confirmed(self, symbol: str, decision_date) -> bool:
        """True if ``symbol`` should be kept given its DEX-volume trend.

        Keep-if-no-data: an absent symbol or insufficient history returns True.
        """
        if self.dex_volume is None or symbol not in self.dex_volume.columns:
            return True
        # causal: only rows at/before the decision date
        col = self.dex_volume[symbol].loc[:decision_date].dropna()
        w = self.confirm_window
        if len(col) < 2 * w:
            return True  # not enough history to judge -> keep
        prior = col.iloc[-2 * w : -w].mean()
        trail = col.iloc[-w:].mean()
        if prior <= 0:
            return True  # cannot form a ratio -> keep
        if trail >= prior:
            return True  # rising / steady -> confirm
        # falling: veto only if it collapsed by more than 50%
        return (trail / prior) >= 0.5

    def target_weights(self, prices_hist: pd.DataFrame) -> pd.Series:
        base_w = self.base.target_weights(prices_hist)
        # no on-chain data at all -> behave exactly like plain momentum
        if self.dex_volume is None:
            return base_w
        candidates = list(base_w[base_w > 0].index)
        if not candidates:
            return base_w  # already cash / no conviction
        decision_date = prices_hist.index[-1]
        survivors = [
            s for s in candidates if self._confirmed(s, decision_date)
        ]
        w = self._zero_weights(prices_hist)
        if not survivors:
            return w  # everything vetoed -> cash
        w[survivors] = 1.0 / len(survivors)
        return w
