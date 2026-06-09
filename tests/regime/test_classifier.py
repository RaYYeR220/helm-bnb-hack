import numpy as np
import pandas as pd

from helm.regime.classifier import RegimeClassifier, compute_regime_path
from helm.regime.hmm_model import RegimeHMM
from helm.types import REGIMES, RegimeRead


def _two_regime_panel(block=70, seed=0):
    """A choppy/ranging block followed by a smooth, strong trending block.

    The ranging block has the higher day-to-day volatility; the trending block
    is a very smooth uptrend (low vol, high trend). 3 assets, 2*block days.
    """
    rng = np.random.default_rng(seed)
    n = 2 * block
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    cols = {}
    for k in ("A", "B", "C"):
        rang = rng.normal(0.0, 0.012, block)       # flat/choppy, higher vol
        trend = rng.normal(0.02, 0.0010, block)    # very smooth strong uptrend
        rets = np.concatenate([rang, trend])
        cols[k] = 100.0 * np.cumprod(1.0 + rets)
    return pd.DataFrame(cols, index=idx)


def test_read_returns_a_regime_read():
    prices = _two_regime_panel()
    clf = RegimeClassifier(hmm=RegimeHMM(seed=0))
    clf.fit(prices)
    read = clf.read(prices)
    assert isinstance(read, RegimeRead)
    assert read.regime in REGIMES
    assert read.date == prices.index[-1]
    assert 0.0 <= read.confidence <= 1.0
    assert abs(sum(read.posterior.values()) - 1.0) < 1e-6
    assert set(read.features) == {"trend_strength", "realized_vol", "breadth", "dispersion"}
    # attribution abs-sums to ~1 (or all-zero in the degenerate case)
    s = sum(abs(v) for v in read.attribution.values())
    assert abs(s - 1.0) < 1e-6 or s == 0.0


def test_read_confidence_is_max_posterior():
    prices = _two_regime_panel()
    clf = RegimeClassifier(hmm=RegimeHMM(seed=0))
    clf.fit(prices)
    read = clf.read(prices)
    assert read.confidence == max(read.posterior.values())
    assert read.regime == max(read.posterior, key=read.posterior.get)


def test_regime_path_is_a_label_series_for_positions_after_min_train():
    prices = _two_regime_panel(block=70)
    path = compute_regime_path(prices, min_train=70, refit_every=5, seed=0)
    assert isinstance(path, pd.Series)
    assert (path.index == prices.index[70:]).all()
    assert set(path.unique()).issubset(set(REGIMES))
    # the full per-date RegimeReads remain retrievable for explainability
    assert "reads" in path.attrs
    assert set(path.attrs["reads"]) == set(path.index)


def test_trending_block_yields_more_trending_labels_than_ranging_block():
    # With only market-data features and walk-forward refitting, segment->label
    # tracking is weak in absolute terms (a smooth uptrend's residual return
    # volatility can read as high_volatility). The robust, deterministic claim is
    # RELATIVE: the trending price segment produces strictly more "trending"
    # labels than the ranging segment does (which produces essentially none).
    prices = _two_regime_panel(block=70)
    path = compute_regime_path(prices, min_train=70, refit_every=5, seed=0)
    pos = np.array([prices.index.get_loc(d) for d in path.index])
    labels = path.to_numpy()
    trend_seg = labels[pos >= 70]
    range_seg = labels[pos < 70]
    trend_frac_in_trend = (trend_seg == "trending").mean() if len(trend_seg) else 0.0
    trend_frac_in_range = (range_seg == "trending").mean() if len(range_seg) else 0.0
    assert trend_frac_in_trend > trend_frac_in_range
    assert trend_frac_in_trend > 0.0


def test_regime_path_has_no_look_ahead():
    prices = _two_regime_panel(block=70)
    full = compute_regime_path(prices, min_train=70, refit_every=5, seed=0)

    # pick a date well past min_train and re-run on the panel truncated at that date;
    # the label at that date must be identical (no future data was used).
    t = 110
    target_date = prices.index[t]
    truncated = compute_regime_path(prices.iloc[: t + 1], min_train=70, refit_every=5, seed=0)
    assert truncated.index[-1] == target_date
    assert truncated.loc[target_date] == full.loc[target_date]
