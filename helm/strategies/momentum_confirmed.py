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
        cex_inflow: pd.DataFrame | None = None,
        cex_veto_threshold: float = 2.0,
    ):
        self.base = base
        self.dex_volume = (
            dex_volume.sort_index() if dex_volume is not None else None
        )
        self.confirm_window = confirm_window
        # date x symbol CEX net-inflow proxy; a candidate whose trailing inflow
        # z-score (data <= decision date) exceeds cex_veto_threshold is dropped
        # (distribution to exchanges). None -> no CEX veto (bit-identical default).
        self.cex_inflow = (
            cex_inflow.sort_index() if cex_inflow is not None else None
        )
        self.cex_veto_threshold = cex_veto_threshold

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

    def _cex_vetoed(self, symbol: str, decision_date) -> bool:
        """True if ``symbol`` should be VETOED for abnormally high CEX inflow.

        Keep-if-no-data: an absent symbol or insufficient history returns False
        (not vetoed). Causal: only inflow rows at/before the decision date are
        used. The trailing-window z-score is (last_value - prior_window_mean) /
        prior_window_std over the ``confirm_window`` days ending at the decision
        date; a z above ``cex_veto_threshold`` fires the veto.
        """
        if self.cex_inflow is None or symbol not in self.cex_inflow.columns:
            return False
        col = self.cex_inflow[symbol].loc[:decision_date].dropna()
        w = self.confirm_window
        if len(col) < 2 * w:
            return False  # not enough history to judge -> do not veto
        window = col.iloc[-w:]
        prior = col.iloc[-2 * w : -w]
        mu = prior.mean()
        sd = prior.std(ddof=1)
        if not sd or sd <= 0:
            # flat prior — if the current value is materially above the flat
            # baseline treat it as infinite z (veto); otherwise keep.
            return bool(window.iloc[-1] > mu * (1 + self.cex_veto_threshold))
        z = (window.iloc[-1] - mu) / sd
        return bool(z > self.cex_veto_threshold)

    def target_weights(self, prices_hist: pd.DataFrame) -> pd.Series:
        base_w = self.base.target_weights(prices_hist)
        # no on-chain data at all -> behave exactly like plain momentum
        if self.dex_volume is None and self.cex_inflow is None:
            return base_w
        candidates = list(base_w[base_w > 0].index)
        if not candidates:
            return base_w  # already cash / no conviction
        decision_date = prices_hist.index[-1]
        survivors = [
            s
            for s in candidates
            if self._confirmed(s, decision_date)
            and not self._cex_vetoed(s, decision_date)
        ]
        w = self._zero_weights(prices_hist)
        if not survivors:
            return w  # everything vetoed -> cash
        w[survivors] = 1.0 / len(survivors)
        return w
