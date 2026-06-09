import numpy as np

from helm.regime.changepoint import bocpd


def test_output_shape_and_range():
    rng = np.random.default_rng(0)
    x = rng.normal(0.0, 1.0, 100)
    cp = bocpd(x)
    assert isinstance(cp, np.ndarray)
    assert cp.shape == (100,)
    assert np.all(cp >= 0.0) and np.all(cp <= 1.0 + 1e-9)


def test_detects_mean_shift_at_index_50():
    rng = np.random.default_rng(42)
    seg1 = rng.normal(0.0, 0.1, 50)
    seg2 = rng.normal(5.0, 0.1, 50)
    x = np.concatenate([seg1, seg2])

    cp = bocpd(x, hazard=1.0 / 100.0)

    window = cp[45:56]
    peak_idx = 45 + int(np.argmax(window))
    peak_val = cp[peak_idx]

    baseline = np.median(cp[5:45])

    # a clear changepoint spike lands inside [45, 55]
    assert 45 <= peak_idx <= 55
    # and it is much larger than the quiet first-segment baseline
    assert peak_val > 3.0 * max(baseline, 1e-6)


def test_flat_series_has_no_strong_changepoint():
    rng = np.random.default_rng(7)
    x = rng.normal(0.0, 0.1, 120)
    cp = bocpd(x, hazard=1.0 / 100.0)
    # no late-series spike dwarfs the steady-state baseline
    baseline = np.median(cp[20:])
    assert cp[20:].max() < 5.0 * max(baseline, 1e-6) + 0.05
