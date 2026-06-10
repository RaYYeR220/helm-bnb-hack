import numpy as np
import pandas as pd
import pytest

from helm.validation.deflated_sharpe import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)


def test_psr_of_clearly_positive_series_vs_zero_is_near_one():
    # seed-0 normal(mean=0.002, std=0.01, n=500): per-period SR ~ 0.1706
    r = np.random.default_rng(0).normal(0.002, 0.01, 500)
    sd = r.std(ddof=1)
    sr = r.mean() / sd
    from scipy.stats import kurtosis as sp_kurt
    from scipy.stats import skew as sp_skew

    psr = probabilistic_sharpe_ratio(
        sr, 0.0, 500, float(sp_skew(r)), float(sp_kurt(r, fisher=False))
    )
    assert psr == pytest.approx(0.999903, abs=1e-4)
    assert psr > 0.9


def test_psr_is_one_half_when_sr_equals_benchmark():
    # SR == benchmark -> numerator is 0 -> Phi(0) == 0.5 exactly
    psr = probabilistic_sharpe_ratio(0.05, 0.05, 500, 0.0, 3.0)
    assert psr == pytest.approx(0.5, abs=1e-12)


def test_psr_n_obs_below_two_is_zero():
    assert probabilistic_sharpe_ratio(0.5, 0.0, 1, 0.0, 3.0) == 0.0


def test_psr_guards_non_positive_variance_term():
    # large positive skew drives the variance term negative -> guarded to 0.0
    # var_term = 1 - 10*0.5 + (3-1)/4 * 0.25 = -3.875 < 0
    assert probabilistic_sharpe_ratio(0.5, 0.0, 100, 10.0, 3.0) == 0.0


def test_expected_max_sharpe_single_trial_is_zero():
    assert expected_max_sharpe(1, 0.01) == 0.0


def test_expected_max_sharpe_increases_with_trials():
    vals = [expected_max_sharpe(n, 0.01) for n in (2, 5, 10, 20, 50, 100)]
    assert vals == sorted(vals)
    assert all(vals[i] < vals[i + 1] for i in range(len(vals) - 1))
    # pinned anchors
    assert expected_max_sharpe(2, 0.01) == pytest.approx(0.051976, abs=1e-5)
    assert expected_max_sharpe(5, 0.01) == pytest.approx(0.119259, abs=1e-5)
    assert expected_max_sharpe(10, 0.01) == pytest.approx(0.157460, abs=1e-5)


def test_dsr_of_strong_strategy_is_high():
    # seed-0 normal(0.002, 0.01, 500), 5 trials, sr_variance=0.01
    r = pd.Series(np.random.default_rng(0).normal(0.002, 0.01, 500))
    dsr = deflated_sharpe_ratio(r, n_trials=5, sr_variance=0.01)
    assert dsr == pytest.approx(0.869085, abs=1e-3)
    assert 0.80 < dsr < 0.95


def test_dsr_of_pure_noise_with_many_trials_is_low():
    # seed-0 normal(0.0, 0.01, 500), 50 trials, sr_variance=0.01 -> ~1e-8
    r = pd.Series(np.random.default_rng(0).normal(0.0, 0.01, 500))
    dsr = deflated_sharpe_ratio(r, n_trials=50, sr_variance=0.01)
    assert dsr < 0.5
    assert dsr == pytest.approx(0.0, abs=1e-3)


def test_dsr_empty_or_tiny_series_is_zero():
    assert deflated_sharpe_ratio(pd.Series([], dtype=float), 5, 0.01) == 0.0
    assert deflated_sharpe_ratio(pd.Series([0.01]), 5, 0.01) == 0.0


def test_dsr_zero_volatility_series_is_zero():
    assert deflated_sharpe_ratio(pd.Series([0.01] * 100), 5, 0.01) == 0.0
