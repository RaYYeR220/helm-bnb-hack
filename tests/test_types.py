import pandas as pd

from helm.types import REGIMES, RegimeRead


def test_regimes_has_the_three_canonical_labels():
    assert REGIMES == ("trending", "ranging", "high_volatility")
    assert len(REGIMES) == 3


def test_regime_read_carries_all_fields():
    read = RegimeRead(
        date=pd.Timestamp("2024-03-01"),
        regime="trending",
        posterior={"trending": 0.7, "ranging": 0.2, "high_volatility": 0.1},
        confidence=0.7,
        features={"trend_strength": 1.2, "realized_vol": 0.01,
                  "breadth": 0.8, "dispersion": 0.05},
        attribution={"trend_strength": 0.6, "realized_vol": -0.1,
                     "breadth": 0.25, "dispersion": 0.05},
    )
    assert read.regime == "trending"
    assert read.regime in REGIMES
    assert read.date == pd.Timestamp("2024-03-01")
    assert read.confidence == 0.7
    assert abs(sum(read.posterior.values()) - 1.0) < 1e-9
    assert set(read.features) == {"trend_strength", "realized_vol", "breadth", "dispersion"}
    assert abs(sum(abs(v) for v in read.attribution.values()) - 1.0) < 1e-9
