import pandas as pd

from helm.strategies.baselines import EqualWeight


def _panel():
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    return pd.DataFrame(
        {"A": [1.0, 1.1, 1.2], "B": [2.0, 2.0, 2.0], "C": [None, 3.0, 3.3]},
        index=idx,
    )


def test_equal_weight_splits_across_available_names():
    strat = EqualWeight()
    w = strat.target_weights(_panel())
    # last row has A, B, C all present -> 1/3 each
    assert abs(w.sum() - 1.0) < 1e-9
    assert abs(w["A"] - 1 / 3) < 1e-9
    assert abs(w["B"] - 1 / 3) < 1e-9


def test_equal_weight_skips_names_with_no_price():
    idx = pd.date_range("2024-01-01", periods=2, freq="D")
    panel = pd.DataFrame({"A": [1.0, 1.1], "B": [None, None]}, index=idx)
    w = EqualWeight().target_weights(panel)
    assert w["A"] == 1.0
    assert w["B"] == 0.0
