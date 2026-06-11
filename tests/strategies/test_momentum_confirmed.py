import numpy as np
import pandas as pd

from helm.strategies.momentum_confirmed import OnchainConfirmedMomentum
from helm.strategies.momentum import CrossSectionalMomentum


def _rising_prices(n=40, start="2024-01-01"):
    """3 names all trending up so plain momentum picks all positive."""
    idx = pd.date_range(start, periods=n, freq="D")
    base = np.linspace(100, 140, n)
    return pd.DataFrame(
        {"A": base, "B": base * 1.01, "C": base * 0.99}, index=idx
    )


def _vol_frame(index, a_series, b_series, c_series):
    return pd.DataFrame({"A": a_series, "B": b_series, "C": c_series}, index=index)


def test_strategy_name_is_momentum_onchain():
    s = OnchainConfirmedMomentum(CrossSectionalMomentum(lookback=20, top_n=3))
    assert s.name == "momentum_onchain"


def test_rising_volume_confirms_and_keeps_all_winners():
    prices = _rising_prices()
    idx = prices.index
    # all three volumes rising over the last 14 days
    ramp = np.linspace(1.0, 20.0, len(idx))
    vol = _vol_frame(idx, ramp, ramp * 2, ramp * 0.5)
    s = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=20, top_n=3),
        dex_volume=vol,
        confirm_window=7,
    )
    w = s.target_weights(prices)
    held = w[w > 0]
    assert set(held.index) == {"A", "B", "C"}
    assert np.allclose(held.values, 1.0 / 3.0)


def test_collapsed_volume_vetoes_that_name():
    prices = _rising_prices()
    idx = prices.index
    flat = np.full(len(idx), 10.0)
    # A keeps steady volume; B collapses in the last 7 days (10 -> 2, ratio 0.2)
    b_vol = np.concatenate([np.full(len(idx) - 7, 10.0), np.full(7, 2.0)])
    vol = _vol_frame(idx, flat, b_vol, flat)
    s = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=20, top_n=3),
        dex_volume=vol,
        confirm_window=7,
    )
    w = s.target_weights(prices)
    held = w[w > 0]
    assert "B" not in held.index            # vetoed (collapsed > 50%)
    assert set(held.index) == {"A", "C"}    # survivors
    assert np.allclose(held[held > 0].values, 0.5)  # renormalized over 2


def test_absent_symbol_is_kept_graceful_fallback():
    prices = _rising_prices()
    idx = prices.index
    flat = np.full(len(idx), 10.0)
    # only A and C have DEX volume; B is absent from the frame -> keep B
    vol = pd.DataFrame({"A": flat, "C": flat}, index=idx)
    s = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=20, top_n=3),
        dex_volume=vol,
        confirm_window=7,
    )
    w = s.target_weights(prices)
    held = w[w > 0]
    assert set(held.index) == {"A", "B", "C"}  # B kept despite no DEX data


def test_no_dex_volume_at_all_degrades_to_plain_momentum():
    prices = _rising_prices()
    base = CrossSectionalMomentum(lookback=20, top_n=3)
    s = OnchainConfirmedMomentum(base, dex_volume=None, confirm_window=7)
    w_confirmed = s.target_weights(prices)
    w_plain = base.target_weights(prices)
    pd.testing.assert_series_equal(w_confirmed, w_plain)


def test_insufficient_price_history_is_cash():
    # fewer rows than lookback+1 -> base returns all zeros -> cash
    prices = _rising_prices(n=10)
    s = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=20, top_n=3), confirm_window=7
    )
    w = s.target_weights(prices)
    assert (w == 0.0).all()


def test_all_names_vetoed_returns_cash():
    prices = _rising_prices()
    idx = prices.index
    # every name collapses -> every winner vetoed -> all-zero / cash
    collapse = np.concatenate([np.full(len(idx) - 7, 10.0), np.full(7, 1.0)])
    vol = _vol_frame(idx, collapse, collapse, collapse)
    s = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=20, top_n=3),
        dex_volume=vol,
        confirm_window=7,
    )
    w = s.target_weights(prices)
    assert (w == 0.0).all()


def test_uses_only_volume_at_or_before_decision_date():
    # volume rows AFTER the decision date must not affect the decision.
    prices = _rising_prices(n=40)
    idx = prices.index
    flat = np.full(len(idx), 10.0)
    vol = _vol_frame(idx, flat, flat, flat)
    # append a future-dated spike that should be ignored
    future = pd.date_range(idx[-1] + pd.Timedelta(days=1), periods=5, freq="D")
    spike = pd.DataFrame(
        {"A": [1e9] * 5, "B": [1e9] * 5, "C": [1e9] * 5}, index=future
    )
    vol_with_future = pd.concat([vol, spike])
    s = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=20, top_n=3),
        dex_volume=vol_with_future,
        confirm_window=7,
    )
    w_future = s.target_weights(prices)
    s2 = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=20, top_n=3),
        dex_volume=vol,
        confirm_window=7,
    )
    w_plain = s2.target_weights(prices)
    pd.testing.assert_series_equal(w_future, w_plain)
