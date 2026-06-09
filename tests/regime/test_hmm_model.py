import numpy as np
import pandas as pd

from helm.regime.features import FEATURE_COLS
from helm.regime.hmm_model import RegimeHMM


def _three_regime_features(block=80, seed=0):
    """Concatenate three clearly-distinct, well-separated feature blocks.

    The three regimes sit at three CORNERS of feature space so no single regime
    dominates the standardized variance (which would let EM collapse two of them
    into one state). Block length is generous so EM has enough data.

    high_vol block:   high realized_vol, high dispersion, mid trend/breadth.
    trending block:   high +trend_strength, high breadth, low vol.
    ranging block:    slightly-negative trend, low breadth, low vol.
    """
    rng = np.random.default_rng(seed)

    def rows(trend_mu, vol_mu, breadth_mu, disp_mu, trend_sd, vol_sd, breadth_sd, disp_sd, k):
        return np.column_stack([
            rng.normal(trend_mu, trend_sd, k),
            rng.normal(vol_mu, vol_sd, k),
            rng.normal(breadth_mu, breadth_sd, k),
            rng.normal(disp_mu, disp_sd, k),
        ])

    high_vol = rows(0.0, 0.08, 0.50, 0.15, 0.05, 0.004, 0.02, 0.005, block)   # big vol & dispersion
    trending = rows(3.0, 0.012, 0.95, 0.03, 0.08, 0.003, 0.01, 0.004, block)  # big +trend, high breadth
    ranging = rows(-0.2, 0.012, 0.20, 0.03, 0.05, 0.003, 0.02, 0.004, block)  # low trend & breadth

    mat = np.vstack([high_vol, trending, ranging])
    idx = pd.date_range("2024-01-01", periods=3 * block, freq="D")
    return pd.DataFrame(mat, index=idx, columns=FEATURE_COLS), block


def test_predict_proba_returns_labeled_probabilities():
    feats, _ = _three_regime_features()
    hmm = RegimeHMM(seed=0).fit(feats)
    proba = hmm.predict_proba(feats)
    assert list(proba.columns) == ["trending", "ranging", "high_volatility"]
    assert proba.index.equals(feats.index)
    rowsums = proba.sum(axis=1)
    assert np.allclose(rowsums.to_numpy(), 1.0, atol=1e-6)


def test_each_block_is_assigned_its_intended_label():
    feats, block = _three_regime_features()
    hmm = RegimeHMM(seed=0).fit(feats)
    proba = hmm.predict_proba(feats)
    labels = proba.idxmax(axis=1).to_numpy()

    def majority(arr):
        vals, counts = np.unique(arr, return_counts=True)
        return vals[int(np.argmax(counts))]

    assert majority(labels[0:block]) == "high_volatility"
    assert majority(labels[block:2 * block]) == "trending"
    assert majority(labels[2 * block:3 * block]) == "ranging"


def test_signatures_high_volatility_has_largest_realized_vol():
    feats, _ = _three_regime_features()
    hmm = RegimeHMM(seed=0).fit(feats)
    sigs = hmm.signatures()
    assert set(sigs) == {"trending", "ranging", "high_volatility"}
    hv = sigs["high_volatility"]["realized_vol"]
    assert hv == max(s["realized_vol"] for s in sigs.values())
    # trending has the largest absolute standardized trend among the rest
    tr = abs(sigs["trending"]["trend_strength"])
    rg = abs(sigs["ranging"]["trend_strength"])
    assert tr >= rg


def test_fit_is_deterministic_for_fixed_seed():
    feats, _ = _three_regime_features()
    a = RegimeHMM(seed=0).fit(feats).predict_proba(feats)
    b = RegimeHMM(seed=0).fit(feats).predict_proba(feats)
    assert np.allclose(a.to_numpy(), b.to_numpy())
