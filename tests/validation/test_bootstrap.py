import numpy as np
import pandas as pd

from helm.validation.bootstrap import bootstrap_metric_ci, circular_block_bootstrap


def _returns(n=365, seed=42):
    return pd.Series(np.random.default_rng(seed).normal(0.001, 0.01, n))


def _ann_sharpe(r: np.ndarray) -> float:
    sd = r.std(ddof=1)
    return float(r.mean() / sd * np.sqrt(365)) if sd > 0 else 0.0


def test_bootstrap_is_deterministic_for_fixed_seed():
    r = _returns()
    a = circular_block_bootstrap(r, n_boot=100, block_len=10, seed=0)
    b = circular_block_bootstrap(r, n_boot=100, block_len=10, seed=0)
    assert np.array_equal(a, b)


def test_bootstrap_shape_is_n_boot_by_n():
    r = _returns(n=365)
    out = circular_block_bootstrap(r, n_boot=100, block_len=10, seed=0)
    assert out.shape == (100, 365)


def test_bootstrap_drops_nan_then_matches_clean_length():
    r = pd.Series([np.nan] + list(np.random.default_rng(1).normal(0, 0.01, 200)))
    out = circular_block_bootstrap(r, n_boot=50, block_len=7, seed=0)
    assert out.shape == (50, 200)  # NaN dropped, n == 200


def test_every_resampled_value_is_from_the_original_series():
    r = _returns(n=200)
    out = circular_block_bootstrap(r, n_boot=100, block_len=10, seed=0)
    original = set(np.round(r.dropna().to_numpy(), 12))
    resampled = set(np.round(out.flatten(), 12))
    assert resampled.issubset(original)


def test_ci_brackets_the_point_estimate_for_sharpe():
    r = _returns()
    res = bootstrap_metric_ci(
        r, _ann_sharpe, n_boot=1000, block_len=10, seed=0, ci=0.90
    )
    assert set(res) == {"lo", "hi", "point", "samples"}
    assert res["lo"] <= res["point"] <= res["hi"]
    assert res["samples"].shape == (1000,)


def test_ci_brackets_the_point_estimate_for_total_return():
    r = _returns()
    total_return = lambda x: float(np.prod(1.0 + x) - 1.0)
    res = bootstrap_metric_ci(
        r, total_return, n_boot=1000, block_len=10, seed=0, ci=0.90
    )
    assert res["lo"] <= res["point"] <= res["hi"]
    assert res["lo"] < res["hi"]
