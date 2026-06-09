import numpy as np
import pandas as pd

from helm.strategies.defensive import Defensive


def test_full_weight_to_the_present_stablecoin():
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    panel = pd.DataFrame(
        {"ETH": [2000.0, 2100.0, 2050.0], "USDT": [1.0, 1.0, 1.0]}, index=idx
    )
    w = Defensive().target_weights(panel)
    assert w["USDT"] == 1.0
    assert w["ETH"] == 0.0
    assert abs(w.sum() - 1.0) < 1e-9


def test_splits_across_multiple_present_stablecoins():
    idx = pd.date_range("2024-01-01", periods=2, freq="D")
    panel = pd.DataFrame(
        {"USDT": [1.0, 1.0], "USDC": [1.0, 1.0], "BTC": [60000.0, 61000.0]}, index=idx
    )
    w = Defensive().target_weights(panel)
    assert w["USDT"] == 0.5
    assert w["USDC"] == 0.5
    assert w["BTC"] == 0.0


def test_no_stablecoin_is_cash():
    idx = pd.date_range("2024-01-01", periods=2, freq="D")
    panel = pd.DataFrame({"ETH": [2000.0, 2100.0], "BTC": [60000.0, 61000.0]}, index=idx)
    w = Defensive().target_weights(panel)
    assert w.sum() == 0.0


def test_stablecoin_without_price_on_decision_day_is_skipped():
    idx = pd.date_range("2024-01-01", periods=2, freq="D")
    panel = pd.DataFrame(
        {"USDT": [1.0, np.nan], "USDC": [1.0, 1.0], "ETH": [2000.0, 2100.0]}, index=idx
    )
    w = Defensive().target_weights(panel)
    # only USDC has a price on the last day
    assert w["USDC"] == 1.0
    assert w["USDT"] == 0.0
    assert w["ETH"] == 0.0


def test_name():
    assert Defensive().name == "defensive"
