"""Cross-sectional momentum: long the strongest positive-momentum names."""

import pandas as pd

from helm.strategies.base import Strategy


class CrossSectionalMomentum(Strategy):
    """Rank names by trailing return over `lookback` days; equal-weight the
    top `top_n` with strictly positive momentum. Others (and cash when no
    positive names) get zero weight.
    """

    name = "momentum"

    def __init__(self, lookback: int = 30, top_n: int = 5):
        self.lookback = lookback
        self.top_n = top_n

    def target_weights(self, prices_hist: pd.DataFrame) -> pd.Series:
        w = self._zero_weights(prices_hist)
        if len(prices_hist) < self.lookback + 1:
            return w
        recent = prices_hist.iloc[-1]
        past = prices_hist.iloc[-self.lookback - 1]
        mom = (recent / past - 1.0).dropna()
        winners = mom.nlargest(self.top_n)
        winners = winners[winners > 0]
        if len(winners) == 0:
            return w
        w[winners.index] = 1.0 / len(winners)
        return w
