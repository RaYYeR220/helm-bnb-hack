"""Deflated Sharpe Ratio (Bailey & López de Prado, 2014).

The Deflated Sharpe Ratio (DSR) corrects a strategy's observed Sharpe for
(a) the number of independent configurations tried (selection bias / multiple
testing) and (b) the non-normality of the returns. It is the probability that
the true Sharpe exceeds an expected-maximum benchmark drawn from ``n_trials``
random strategies — the honest "is this edge real, given how hard I looked?"

Conventions:
- Sharpe ratios here are PER-PERIOD (not annualized). The same units must be
  used for the observed SR, the benchmark, and ``sr_variance``.
- Kurtosis is RAW (a normal distribution has kurt == 3), matching
  ``scipy.stats.kurtosis(fisher=False)``.
"""

import numpy as np
import pandas as pd
from scipy.stats import kurtosis as _kurtosis
from scipy.stats import norm
from scipy.stats import skew as _skew

_EULER_MASCHERONI = 0.5772156649


def probabilistic_sharpe_ratio(
    observed_sr: float,
    benchmark_sr: float,
    n_obs: int,
    skew: float,
    kurt: float,
) -> float:
    """PSR: probability the true (per-period) Sharpe exceeds ``benchmark_sr``.

        PSR = Phi( (SR - SR*) * sqrt(n - 1)
                   / sqrt(1 - skew*SR + ((kurt - 1) / 4) * SR^2) )

    ``skew`` and ``kurt`` are the moments of the return series (kurt raw, normal
    == 3). When the variance term under the square root is non-positive the
    statistic is undefined; we return 0.0. ``n_obs < 2`` returns 0.0.
    """
    if n_obs < 2:
        return 0.0
    sr = observed_sr
    var_term = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    if var_term <= 0.0:
        return 0.0
    z = (observed_sr - benchmark_sr) * np.sqrt(n_obs - 1.0) / np.sqrt(var_term)
    return float(norm.cdf(z))


def expected_max_sharpe(n_trials: int, sr_variance: float) -> float:
    """Expected maximum (per-period) Sharpe across ``n_trials`` random strategies.

        E[max] = sqrt(sr_variance)
                 * ((1 - gamma) * Phi^-1(1 - 1/N) + gamma * Phi^-1(1 - 1/(N*e)))

    with gamma the Euler-Mascheroni constant. A single trial (N == 1) cannot be
    "the max of a search", so it deflates to the zero benchmark -> 0.0.
    """
    if n_trials <= 1:
        return 0.0
    n = float(n_trials)
    e = np.e
    quantile = (
        (1.0 - _EULER_MASCHERONI) * norm.ppf(1.0 - 1.0 / n)
        + _EULER_MASCHERONI * norm.ppf(1.0 - 1.0 / (n * e))
    )
    return float(np.sqrt(sr_variance) * quantile)


def deflated_sharpe_ratio(
    returns: pd.Series, n_trials: int, sr_variance: float
) -> float:
    """DSR: PSR of ``returns`` against the expected-max-Sharpe benchmark.

    Computes the per-period Sharpe (mean / std, ddof=1) plus skew/raw-kurtosis of
    ``returns.dropna()``, derives the benchmark from
    ``expected_max_sharpe(n_trials, sr_variance)``, and returns the PSR. Empty,
    single-observation, or zero-volatility inputs return 0.0.
    """
    r = returns.dropna().to_numpy()
    n = len(r)
    if n < 2:
        return 0.0
    sd = r.std(ddof=1)
    if sd == 0.0 or np.isnan(sd) or sd < 1e-12:
        return 0.0
    sr = float(r.mean() / sd)
    sk = float(_skew(r))
    ku = float(_kurtosis(r, fisher=False))
    benchmark = expected_max_sharpe(n_trials, sr_variance)
    return probabilistic_sharpe_ratio(sr, benchmark, n, sk, ku)
