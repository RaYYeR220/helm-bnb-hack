import numpy as np
import pandas as pd

from helm.strategies.momentum import CrossSectionalMomentum
from helm.strategies.momentum_confirmed import OnchainConfirmedMomentum


def _rising_prices(n=40, start="2024-01-01"):
    idx = pd.date_range(start, periods=n, freq="D")
    base = np.linspace(100, 140, n)
    return pd.DataFrame({"A": base, "B": base * 1.01, "C": base * 0.99}, index=idx)


def test_high_cex_inflow_z_vetoes_that_name():
    prices = _rising_prices()
    idx = prices.index
    # A, C flat CEX inflow; B has a huge tail spike -> trailing z >> threshold
    flat = np.full(len(idx), 1.0)
    b_inflow = np.concatenate([np.full(len(idx) - 3, 1.0), np.full(3, 1000.0)])
    cex = pd.DataFrame({"A": flat, "B": b_inflow, "C": flat}, index=idx)
    s = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=20, top_n=3),
        cex_inflow=cex,
        cex_veto_threshold=2.0,
        confirm_window=7,
    )
    w = s.target_weights(prices)
    held = w[w > 0]
    assert "B" not in held.index            # vetoed on CEX inflow spike
    assert set(held.index) == {"A", "C"}
    assert np.allclose(held.values, 0.5)    # renormalized over the 2 survivors


def test_absent_cex_symbol_is_kept():
    prices = _rising_prices()
    idx = prices.index
    flat = np.full(len(idx), 1.0)
    # B missing from the CEX frame -> keep B (graceful fallback)
    cex = pd.DataFrame({"A": flat, "C": flat}, index=idx)
    s = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=20, top_n=3),
        cex_inflow=cex,
        cex_veto_threshold=2.0,
        confirm_window=7,
    )
    w = s.target_weights(prices)
    assert set(w[w > 0].index) == {"A", "B", "C"}


def test_cex_inflow_none_is_byte_identical_to_no_veto():
    # default None must reproduce the dex-only behavior exactly
    prices = _rising_prices()
    idx = prices.index
    ramp = np.linspace(1.0, 20.0, len(idx))
    vol = pd.DataFrame({"A": ramp, "B": ramp * 2, "C": ramp * 0.5}, index=idx)
    s_no = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=20, top_n=3),
        dex_volume=vol,
        confirm_window=7,
    )
    s_none = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=20, top_n=3),
        dex_volume=vol,
        confirm_window=7,
        cex_inflow=None,
    )
    pd.testing.assert_series_equal(
        s_no.target_weights(prices), s_none.target_weights(prices)
    )


def test_cex_veto_uses_only_inflow_at_or_before_decision_date():
    # a post-decision inflow spike must not change the decision (causality)
    prices = _rising_prices(n=40)
    idx = prices.index
    flat = np.full(len(idx), 1.0)
    cex = pd.DataFrame({"A": flat, "B": flat, "C": flat}, index=idx)
    future = pd.date_range(idx[-1] + pd.Timedelta(days=1), periods=5, freq="D")
    spike = pd.DataFrame(
        {"A": [1e9] * 5, "B": [1e9] * 5, "C": [1e9] * 5}, index=future
    )
    cex_future = pd.concat([cex, spike])
    w_future = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=20, top_n=3),
        cex_inflow=cex_future,
        cex_veto_threshold=2.0,
        confirm_window=7,
    ).target_weights(prices)
    w_plain = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=20, top_n=3),
        cex_inflow=cex,
        cex_veto_threshold=2.0,
        confirm_window=7,
    ).target_weights(prices)
    pd.testing.assert_series_equal(w_future, w_plain)


def test_insufficient_cex_history_keeps_name():
    # fewer than 2*confirm_window CEX rows -> cannot judge -> keep
    prices = _rising_prices()
    idx = prices.index
    short = pd.DataFrame(
        {"A": [1.0] * len(idx), "B": [1.0] * len(idx), "C": [1.0] * len(idx)},
        index=idx,
    )
    # confirm_window large enough that 2*w > len(idx)
    s = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=20, top_n=3),
        cex_inflow=short,
        cex_veto_threshold=2.0,
        confirm_window=25,
    )
    assert set(s.target_weights(prices)[lambda w: w > 0].index) == {"A", "B", "C"}


def test_zero_baseline_prior_does_not_veto_small_positive_inflow():
    # Prior window is all zeros (no CEX activity), current window has a tiny
    # positive net inflow. A flat ZERO baseline must NOT veto on any positive
    # value -- only a flat NON-zero baseline with a material spike vetoes.
    import numpy as np
    import pandas as pd

    from helm.strategies.momentum import CrossSectionalMomentum
    from helm.strategies.momentum_confirmed import OnchainConfirmedMomentum

    n = 40
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    # B trends up so momentum picks it; A flat
    prices = pd.DataFrame(
        {"A": np.ones(n) * 100.0, "B": np.linspace(100, 200, n)}, index=idx
    )
    # B CEX inflow: 37 zeros then 3 tiny positives -> flat-zero prior
    cex = pd.DataFrame(
        {"B": [0.0] * 37 + [0.5, 0.4, 0.6]}, index=idx
    )
    strat = OnchainConfirmedMomentum(
        CrossSectionalMomentum(lookback=20, top_n=1),
        confirm_window=3,
        cex_inflow=cex,
        cex_veto_threshold=2.0,
    )
    w = strat.target_weights(prices)
    assert w.get("B", 0.0) > 0.0  # not vetoed by a zero baseline
