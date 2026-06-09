"""Defensive (risk-off) strategy: rotate into stablecoins, else cash."""

import pandas as pd

from helm.strategies.base import Strategy


class Defensive(Strategy):
    """If any configured stablecoin has a price on the decision day, equal-weight
    across the present stablecoins; otherwise hold cash (all zeros).
    """

    name = "defensive"

    def __init__(self, stablecoins=("USDT", "USDC", "DAI", "TUSD", "FDUSD")):
        self.stablecoins = tuple(stablecoins)

    def target_weights(self, prices_hist: pd.DataFrame) -> pd.Series:
        w = self._zero_weights(prices_hist)
        if len(prices_hist) == 0:
            return w
        last = prices_hist.iloc[-1]
        present = [
            s for s in self.stablecoins
            if s in prices_hist.columns and pd.notna(last.get(s))
        ]
        if not present:
            return w
        w[present] = 1.0 / len(present)
        return w
