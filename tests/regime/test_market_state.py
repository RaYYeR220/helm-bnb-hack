import numpy as np
import pandas as pd

from helm.regime.market_state import market_index, market_risk_off


def _panel(rets_per_asset: dict, start="2024-01-01"):
    n = len(next(iter(rets_per_asset.values())))
    idx = pd.date_range(start, periods=n, freq="D")
    cols = {
        k: 100.0 * np.cumprod(1.0 + np.asarray(r, dtype=float))
        for k, r in rets_per_asset.items()
    }
    return pd.DataFrame(cols, index=idx)


# --- market_index -------------------------------------------------------------

def test_market_index_rebases_each_name_to_one():
    panel = _panel({"A": [0.0] * 10, "B": [0.0] * 10})
    # different price levels (100 vs 100) but rebased index must start at 1.0
    idx = market_index(panel)
    assert abs(idx.iloc[0] - 1.0) < 1e-12
    assert abs(idx.iloc[-1] - 1.0) < 1e-12


def test_market_index_tracks_equal_weight_growth():
    # A grows 1%/day, B flat -> index ~ mean of the two rebased paths.
    # The fixture's first price already includes one return step, so 20 points
    # span 19 growth steps after rebasing to the first available price.
    panel = _panel({"A": [0.01] * 20, "B": [0.0] * 20})
    idx = market_index(panel)
    expected_last = (1.01 ** 19 + 1.0) / 2.0
    assert abs(idx.iloc[-1] - expected_last) < 1e-9


# --- market_risk_off ----------------------------------------------------------

def test_uptrend_is_risk_on():
    panel = _panel({k: [0.005] * 80 for k in ("A", "B", "C")})
    assert market_risk_off(panel, ma_window=50, dd_threshold=0.10) is False


def test_sustained_downtrend_is_risk_off():
    # steady -0.5%/day for 80 days: index below its 50-SMA AND in deep drawdown
    panel = _panel({k: [-0.005] * 80 for k in ("A", "B", "C")})
    assert market_risk_off(panel, ma_window=50, dd_threshold=0.10) is True


def test_sharp_drawdown_triggers_even_without_ma_history():
    # only 30 days of data (< ma_window): 20 up days then a -15% crash day
    rets = [0.004] * 29 + [-0.15]
    panel = _panel({k: rets for k in ("A", "B")})
    assert market_risk_off(panel, ma_window=50, dd_threshold=0.10) is True


def test_below_ma_triggers_without_deep_drawdown():
    # long flat plateau then a gentle -0.1%/day bleed: drawdown stays < 10%
    # but the index sits below its 50-SMA -> risk-off
    rets = [0.0] * 60 + [-0.001] * 40
    panel = _panel({k: rets for k in ("A", "B")})
    assert market_risk_off(panel, ma_window=50, dd_threshold=0.10) is True


def test_short_flat_history_is_risk_on():
    # too little data for the MA and no drawdown -> do not gate
    panel = _panel({k: [0.0] * 10 for k in ("A", "B")})
    assert market_risk_off(panel, ma_window=50, dd_threshold=0.10) is False


def test_empty_panel_is_risk_on():
    assert market_risk_off(pd.DataFrame(), ma_window=50, dd_threshold=0.10) is False
