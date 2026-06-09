"""Shared regime types. The `RegimeRead` is the stable contract Plans C–E consume."""

from dataclasses import dataclass

import pandas as pd

# The three canonical market regimes. Order is fixed; downstream code maps by name.
REGIMES = ("trending", "ranging", "high_volatility")


@dataclass
class RegimeRead:
    """A single-date regime classification with explainability.

    - `regime`: the argmax regime label (one of REGIMES).
    - `posterior`: regime label -> probability (floats summing to ~1).
    - `confidence`: the max posterior probability.
    - `features`: feature name -> raw feature value at `date`.
    - `attribution`: feature name -> signed contribution fraction (abs values sum to ~1).
    """

    date: pd.Timestamp
    regime: str
    posterior: dict
    confidence: float
    features: dict
    attribution: dict
