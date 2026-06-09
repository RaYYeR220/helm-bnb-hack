import numpy as np
import pandas as pd

from helm.strategies.momentum import CrossSectionalMomentum


def _trending_panel(n=40):
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    up = np.linspace(1.0, 2.0, n)        # A: clear uptrend
    flat = np.ones(n) * 1.5              # B: flat
    down = np.linspace(2.0, 1.0, n)      # C: clear downtrend
    return pd.DataFrame({"A": up, "B": flat, "C": down}, index=idx)


def test_momentum_longs_the_winner_skips_the_loser():
    strat = CrossSectionalMomentum(lookback=20, top_n=1)
    w = strat.target_weights(_trending_panel())
    assert w["A"] == 1.0          # only positive-momentum winner
    assert w["B"] == 0.0
    assert w["C"] == 0.0


def test_momentum_holds_cash_with_insufficient_history():
    strat = CrossSectionalMomentum(lookback=30, top_n=2)
    short = _trending_panel(n=10)  # fewer rows than lookback+1
    w = strat.target_weights(short)
    assert w.sum() == 0.0


def test_momentum_all_negative_goes_to_cash():
    idx = pd.date_range("2024-01-01", periods=40, freq="D")
    down = np.linspace(2.0, 1.0, 40)
    panel = pd.DataFrame({"A": down, "B": down * 0.9}, index=idx)
    w = CrossSectionalMomentum(lookback=20, top_n=2).target_weights(panel)
    assert w.sum() == 0.0          # no positive momentum -> cash


def test_momentum_top_n_larger_than_universe():
    # top_n exceeds the number of names; nlargest must not error,
    # and only strictly-positive-momentum names get weight.
    strat = CrossSectionalMomentum(lookback=20, top_n=10)
    w = strat.target_weights(_trending_panel())
    assert w["A"] == 1.0     # only A has positive momentum in the trending panel
    assert abs(w.sum() - 1.0) < 1e-9
