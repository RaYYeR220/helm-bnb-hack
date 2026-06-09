"""Strategy interface. Strategies map a price-history window to target weights."""

from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    """A long-only cross-sectional strategy.

    Implementations receive the price panel *through the decision day* (the day
    whose close is the most recent row) and return target portfolio weights for
    the next holding period. Weights are a Series indexed by symbol, long-only,
    summing to <= 1.0 (the remainder is cash). No conviction -> all zeros.
    """

    name: str = "strategy"

    @abstractmethod
    def target_weights(self, prices_hist: pd.DataFrame) -> pd.Series:
        ...

    @staticmethod
    def _zero_weights(prices_hist: pd.DataFrame) -> pd.Series:
        return pd.Series(0.0, index=prices_hist.columns)
