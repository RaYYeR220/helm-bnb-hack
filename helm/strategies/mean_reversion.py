"""Cross-sectional mean reversion: long the most-oversold names."""

import pandas as pd

from helm.strategies.base import Strategy


class CrossSectionalMeanReversion(Strategy):
    """Rank names by trailing return over `lookback` days; equal-weight the
    `bottom_n` with the most NEGATIVE return (the most oversold), among names
    with sufficient history. Cash (all zeros) if fewer than `lookback+1` rows.
    """

    name = "mean_reversion"

    def __init__(self, lookback: int = 10, bottom_n: int = 5):
        self.lookback = lookback
        self.bottom_n = bottom_n

    def target_weights(self, prices_hist: pd.DataFrame) -> pd.Series:
        w = self._zero_weights(prices_hist)
        if len(prices_hist) < self.lookback + 1:
            return w
        recent = prices_hist.iloc[-1]
        past = prices_hist.iloc[-self.lookback - 1]
        ret = (recent / past - 1.0).dropna()
        if len(ret) == 0:
            return w
        losers = ret.nsmallest(self.bottom_n)
        if len(losers) == 0:
            return w
        w[losers.index] = 1.0 / len(losers)
        return w
