"""Circular block bootstrap for return-series metrics.

A plain i.i.d. bootstrap destroys the autocorrelation in financial returns and
understates the variance of path-dependent metrics. The CIRCULAR block bootstrap
resamples contiguous blocks (wrapping around the end of the series) so short-run
dependence is preserved within each block. ``bootstrap_metric_ci`` maps any
``returns -> float`` metric over the resampled paths and returns a percentile
confidence interval around the point estimate.
"""

import numpy as np
import pandas as pd


def circular_block_bootstrap(
    returns: pd.Series,
    n_boot: int = 1000,
    block_len: int = 10,
    seed: int = 0,
) -> np.ndarray:
    """Resample ``returns`` into ``n_boot`` circular-block paths of length ``n``.

    NaNs are dropped first (``n == len(returns.dropna())``). Each path is built
    by drawing ``ceil(n / block_len)`` random start positions and copying
    ``block_len`` consecutive values from each (indices taken modulo ``n`` so
    blocks wrap around the end), then truncating the concatenation to ``n``.
    Returns an array of shape ``(n_boot, n)``.
    """
    r = returns.dropna().to_numpy()
    n = len(r)
    if n == 0:
        return np.empty((n_boot, 0), dtype=float)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_len))
    offsets = np.arange(block_len)
    out = np.empty((n_boot, n), dtype=float)
    for b in range(n_boot):
        starts = rng.integers(0, n, size=n_blocks)
        idxs = (starts[:, None] + offsets[None, :]) % n  # (n_blocks, block_len)
        out[b] = r[idxs.ravel()][:n]
    return out


def bootstrap_metric_ci(
    returns: pd.Series,
    metric_fn,
    n_boot: int = 1000,
    block_len: int = 10,
    seed: int = 0,
    ci: float = 0.90,
) -> dict:
    """Percentile confidence interval for ``metric_fn`` under block resampling.

    ``metric_fn`` maps a 1-D returns ``np.ndarray`` to a float. Returns a dict
    with ``point`` (metric on the original series), ``samples`` (the metric over
    every bootstrap path, shape ``(n_boot,)``), and ``lo``/``hi`` — the
    ``(1 - ci)/2`` and ``1 - (1 - ci)/2`` quantiles of ``samples``.
    """
    boots = circular_block_bootstrap(returns, n_boot, block_len, seed)
    samples = np.array([float(metric_fn(boots[b])) for b in range(n_boot)])
    point = float(metric_fn(returns.dropna().to_numpy()))
    alpha = (1.0 - ci) / 2.0
    lo = float(np.quantile(samples, alpha))
    hi = float(np.quantile(samples, 1.0 - alpha))
    return {"lo": lo, "hi": hi, "point": point, "samples": samples}
