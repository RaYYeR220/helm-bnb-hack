import numpy as np
import pandas as pd

from helm.regime.features import compute_feature_panel

FEATURE_COLS = ["trend_strength", "realized_vol", "breadth", "dispersion"]


def _uptrend_panel(n=80, seed=0):
    """Three assets all in a strong, low-noise uptrend."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    cols = {}
    for k in ("A", "B", "C"):
        rets = rng.normal(0.01, 0.002, n)        # ~+1%/day, tiny noise
        cols[k] = 100.0 * np.cumprod(1.0 + rets)
    return pd.DataFrame(cols, index=idx)


def _flat_choppy_panel(n=80, seed=1):
    """Three assets oscillating around a flat level — no net trend."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    cols = {}
    for k in ("A", "B", "C"):
        rets = rng.normal(0.0, 0.01, n)          # zero drift, real noise
        cols[k] = 100.0 * np.cumprod(1.0 + rets)
    return pd.DataFrame(cols, index=idx)


def test_columns_are_exactly_the_four_features_in_order():
    feats = compute_feature_panel(_uptrend_panel())
    assert list(feats.columns) == FEATURE_COLS


def test_no_leading_all_nan_rows():
    feats = compute_feature_panel(_uptrend_panel())
    # leading insufficient-history rows are dropped; no row is entirely NaN
    assert not feats.isna().all(axis=1).any()
    assert len(feats) > 0


def test_uptrend_has_high_positive_trend_and_high_breadth():
    feats = compute_feature_panel(_uptrend_panel())
    tail = feats.iloc[-1]
    assert tail["trend_strength"] > 1.0         # strong, Sharpe-like positive trend
    assert tail["breadth"] > 0.9                # nearly all names up over the window


def test_flat_choppy_has_near_zero_trend():
    feats = compute_feature_panel(_flat_choppy_panel())
    # the average |trend_strength| over the panel stays small for a no-drift series
    assert feats["trend_strength"].abs().mean() < 0.7


def test_realized_vol_higher_in_choppy_than_smooth_uptrend():
    smooth = compute_feature_panel(_uptrend_panel())
    choppy = compute_feature_panel(_flat_choppy_panel())
    assert choppy["realized_vol"].mean() > smooth["realized_vol"].mean()


def test_breadth_in_unit_interval():
    feats = compute_feature_panel(_flat_choppy_panel())
    assert (feats["breadth"] >= 0.0).all()
    assert (feats["breadth"] <= 1.0).all()


def test_handles_missing_data_without_crashing():
    panel = _uptrend_panel()
    panel.iloc[:10, 0] = np.nan   # A has no early data
    panel.iloc[40, 1] = np.nan    # B has a single hole
    feats = compute_feature_panel(panel)
    assert list(feats.columns) == FEATURE_COLS
    assert len(feats) > 0
    assert np.isfinite(feats.to_numpy()).all()
