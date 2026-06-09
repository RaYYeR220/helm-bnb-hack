import numpy as np
import pandas as pd

from helm.strategies.mean_reversion import CrossSectionalMeanReversion


def _panel_with_one_crash(n=20):
    """A, B flat; C drops sharply on the last day (most oversold)."""
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    a = np.ones(n) * 100.0
    b = np.ones(n) * 50.0
    c = np.ones(n) * 80.0
    c[-1] = 40.0   # -50% on the final step
    return pd.DataFrame({"A": a, "B": b, "C": c}, index=idx)


def test_longs_the_oversold_name():
    strat = CrossSectionalMeanReversion(lookback=10, bottom_n=1)
    w = strat.target_weights(_panel_with_one_crash())
    assert w["C"] == 1.0     # the crashed name is the most oversold
    assert w["A"] == 0.0
    assert w["B"] == 0.0
    assert abs(w.sum() - 1.0) < 1e-9


def test_equal_weights_the_bottom_n():
    idx = pd.date_range("2024-01-01", periods=15, freq="D")
    # three names with distinct trailing returns: C and D most negative
    base = {
        "A": np.linspace(100, 110, 15),   # up
        "B": np.linspace(100, 100, 15),   # flat
        "C": np.linspace(100, 80, 15),    # down
        "D": np.linspace(100, 70, 15),    # down more
    }
    panel = pd.DataFrame(base, index=idx)
    w = CrossSectionalMeanReversion(lookback=10, bottom_n=2).target_weights(panel)
    assert w["C"] == 0.5
    assert w["D"] == 0.5
    assert w["A"] == 0.0
    assert w["B"] == 0.0


def test_insufficient_history_is_cash():
    strat = CrossSectionalMeanReversion(lookback=10, bottom_n=2)
    short = _panel_with_one_crash(n=5)   # fewer than lookback+1 rows
    w = strat.target_weights(short)
    assert w.sum() == 0.0


def test_name():
    assert CrossSectionalMeanReversion().name == "mean_reversion"
