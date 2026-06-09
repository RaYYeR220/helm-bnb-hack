"""Baseline strategies used as backtest comparators."""

import pandas as pd

from helm.strategies.base import Strategy


class EqualWeight(Strategy):
    """Equal weight across every name that has a price on the decision day."""

    name = "equal_weight"

    def target_weights(self, prices_hist: pd.DataFrame) -> pd.Series:
        w = self._zero_weights(prices_hist)
        if len(prices_hist) == 0:
            return w
        last = prices_hist.iloc[-1]
        available = last.dropna().index
        if len(available) == 0:
            return w
        w[available] = 1.0 / len(available)
        return w
