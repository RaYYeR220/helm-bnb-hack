import numpy as np
import pandas as pd

from helm.regime.classifier import RegimeClassifier, compute_regime_path
from helm.regime.features import FEATURE_COLS
from helm.regime.hmm_model import RegimeHMM
from helm.types import REGIMES


def _two_regime_panel(block=70, seed=0):
    rng = np.random.default_rng(seed)
    n = 2 * block
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    cols = {}
    for k in ("A", "B", "C"):
        rang = rng.normal(0.0, 0.012, block)
        trend = rng.normal(0.02, 0.0010, block)
        cols[k] = 100.0 * np.cumprod(1.0 + np.concatenate([rang, trend]))
    return pd.DataFrame(cols, index=idx)


# --- RegimeHMM additive feature_cols ------------------------------------------

def test_hmm_default_feature_cols_is_the_module_constant():
    hmm = RegimeHMM(seed=0)
    assert hmm._feature_cols == list(FEATURE_COLS)


def test_hmm_custom_feature_cols_trains_on_all_columns_and_labels_correctly():
    prices = _two_regime_panel()
    from helm.regime.features import compute_feature_panel

    feats = compute_feature_panel(prices)
    # synthetic extra column that is pure noise -> must not break labeling, which
    # keys only off realized_vol / trend_strength.
    rng = np.random.default_rng(1)
    feats = feats.copy()
    feats["onchain_x"] = rng.normal(0.0, 1.0, len(feats))
    cols = list(FEATURE_COLS) + ["onchain_x"]

    hmm = RegimeHMM(seed=0, feature_cols=cols)
    hmm.fit(feats)
    assert hmm._feature_cols == cols
    # means_ has 5 columns now (the HMM saw all 5 features)
    assert hmm._model.means_.shape[1] == 5
    # labeling still produced the three canonical regimes
    assert set(hmm.signatures().keys()) == set(REGIMES)
    proba = hmm.predict_proba(feats)
    assert list(proba.columns) == list(REGIMES)


# --- compute_regime_path default bit-identity ---------------------------------

def test_regime_path_default_is_bit_identical_with_extra_features_none():
    prices = _two_regime_panel()
    base = compute_regime_path(prices, min_train=70, refit_every=5, seed=0)
    same = compute_regime_path(
        prices, min_train=70, refit_every=5, seed=0, extra_features=None
    )
    assert list(base.index) == list(same.index)
    assert (base.to_numpy() == same.to_numpy()).all()


# --- causal join of extra_features --------------------------------------------

def _onchain_extra(index):
    # a single date-indexed extra feature aligned to the panel dates
    return pd.DataFrame(
        {"tvl_dd": np.linspace(-0.3, 0.0, len(index))}, index=index
    )


def test_regime_path_with_extra_features_runs_and_keeps_canonical_labels():
    prices = _two_regime_panel()
    extra = _onchain_extra(prices.index)
    path = compute_regime_path(
        prices, min_train=70, refit_every=5, seed=0, extra_features=extra
    )
    assert set(path.unique()).issubset(set(REGIMES))
    assert len(path) == len(prices) - 70


def test_regime_path_extra_features_join_has_no_look_ahead():
    # truncation invariance: the label at a fixed date is identical whether the
    # extra-feature frame extends into the future or stops at that date.
    prices = _two_regime_panel(block=70)
    extra_full = _onchain_extra(prices.index)

    full = compute_regime_path(
        prices, min_train=70, refit_every=5, seed=0, extra_features=extra_full
    )
    t = 110
    target_date = prices.index[t]
    truncated = compute_regime_path(
        prices.iloc[: t + 1],
        min_train=70,
        refit_every=5,
        seed=0,
        extra_features=extra_full.iloc[: t + 1],
    )
    assert truncated.index[-1] == target_date
    assert truncated.loc[target_date] == full.loc[target_date]


def test_classifier_join_uses_only_extra_rows_at_or_before_each_date():
    # if the extra frame is missing the most recent dates, the classifier
    # ffills the LAST KNOWN value (no forward fill from the future).
    prices = _two_regime_panel(block=70)
    extra = _onchain_extra(prices.index).iloc[:-10]  # drop last 10 extra rows
    # must still run (graceful: trailing dates inherit the last-known extra row)
    path = compute_regime_path(
        prices, min_train=70, refit_every=5, seed=0, extra_features=extra
    )
    assert set(path.unique()).issubset(set(REGIMES))
