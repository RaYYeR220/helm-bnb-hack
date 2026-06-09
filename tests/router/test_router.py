import pandas as pd

from helm.router.router import RegimeRouter, apply_hysteresis
from helm.strategies.base import Strategy


# --- apply_hysteresis ---------------------------------------------------------

def test_hysteresis_switches_after_threshold():
    labels = ["trending", "trending", "ranging", "trending", "trending", "trending"]
    # the lone "ranging" is a 1-length flicker; three trailing "trending" persist
    active = apply_hysteresis(labels, hysteresis=3, default="ranging")
    assert active == "trending"


def test_hysteresis_returns_default_before_any_regime_reaches_threshold():
    labels = ["trending", "ranging", "trending"]
    active = apply_hysteresis(labels, hysteresis=3, default="ranging")
    assert active == "ranging"


def test_short_flicker_does_not_switch():
    # establish trending (3 in a row), then a 2-length ranging flicker
    labels = ["trending", "trending", "trending", "ranging", "ranging", "trending"]
    active = apply_hysteresis(labels, hysteresis=3, default="ranging")
    assert active == "trending"


def test_hysteresis_one_means_immediate_switch():
    labels = ["trending", "ranging"]
    active = apply_hysteresis(labels, hysteresis=1, default="trending")
    assert active == "ranging"


def test_hysteresis_empty_returns_default():
    assert apply_hysteresis([], hysteresis=3, default="ranging") == "ranging"


# --- RegimeRouter -------------------------------------------------------------

class _ConstStrategy(Strategy):
    """Stub strategy that puts all weight on one recognizable column."""

    def __init__(self, name, col):
        self.name = name
        self.col = col

    def target_weights(self, prices_hist):
        w = self._zero_weights(prices_hist)
        if self.col in prices_hist.columns:
            w[self.col] = 1.0
        return w


def _panel(n=6):
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"TRN": [1.0] * n, "RNG": [1.0] * n, "VOL": [1.0] * n}, index=idx
    )


def test_router_delegates_to_hysteresis_selected_strategy():
    panel = _panel(6)
    regime_path = pd.Series(
        ["ranging", "ranging", "trending", "trending", "trending", "trending"],
        index=panel.index,
    )
    strategies = {
        "trending": _ConstStrategy("trending_stub", "TRN"),
        "ranging": _ConstStrategy("ranging_stub", "RNG"),
        "high_volatility": _ConstStrategy("vol_stub", "VOL"),
    }
    router = RegimeRouter(regime_path, strategies, hysteresis=3, default_regime="ranging")
    w = router.target_weights(panel)
    # three trailing "trending" labels (positions 3,4,5) reach the threshold
    assert w["TRN"] == 1.0
    assert w["RNG"] == 0.0
    assert router.name == "helm"


def test_router_holds_default_until_threshold_met():
    panel = _panel(3)
    regime_path = pd.Series(["trending", "ranging", "trending"], index=panel.index)
    strategies = {
        "trending": _ConstStrategy("trending_stub", "TRN"),
        "ranging": _ConstStrategy("ranging_stub", "RNG"),
        "high_volatility": _ConstStrategy("vol_stub", "VOL"),
    }
    router = RegimeRouter(regime_path, strategies, hysteresis=3, default_regime="ranging")
    w = router.target_weights(panel)
    # no regime persists 3 in a row -> default "ranging"
    assert w["RNG"] == 1.0


def test_router_returns_cash_when_date_not_in_path():
    panel = _panel(4)
    # regime path only covers the first two dates
    regime_path = pd.Series(["trending", "trending"], index=panel.index[:2])
    strategies = {
        "trending": _ConstStrategy("trending_stub", "TRN"),
        "ranging": _ConstStrategy("ranging_stub", "RNG"),
        "high_volatility": _ConstStrategy("vol_stub", "VOL"),
    }
    router = RegimeRouter(regime_path, strategies, hysteresis=2, default_regime="ranging")
    w = router.target_weights(panel)   # last panel date is past the path
    assert w.sum() == 0.0
