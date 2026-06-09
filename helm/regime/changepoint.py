"""Bayesian Online Change-point Detection (Adams & MacKay, 2007).

Conjugate Normal-inverse-Gamma prior over an unknown mean & variance, giving a
Student-t posterior predictive. Returns, per observation, the change-point
probability: the posterior mass that the run has just (re)started.

Implementation note (mathematically load-bearing): under a constant scalar
hazard the renormalized posterior at run length exactly 0, `P(r_t = 0)`, equals
the hazard at every step — the per-length predictive factors out of numerator
and denominator identically, so `R[0]` carries no signal. The detectable
change-point quantity is the posterior mass on a *short* run (length 0 OR 1):
at a change the run-length posterior collapses off the long, well-fit run onto
the freshly-started short run, so `R[0] + R[1]` spikes toward 1. We return that.
"""

import numpy as np
from scipy.stats import t as student_t


def bocpd(
    x,
    hazard: float = 1.0 / 100.0,
    mu0: float = 0.0,
    kappa0: float = 1.0,
    alpha0: float = 1.0,
    beta0: float = 1.0,
) -> np.ndarray:
    """Run BOCPD over the 1-D series `x`.

    Parameters
    ----------
    x : array-like
        Observations.
    hazard : float
        Constant hazard H = P(changepoint) per step.
    mu0, kappa0, alpha0, beta0 : float
        Normal-inverse-Gamma prior hyperparameters.

    Returns
    -------
    np.ndarray
        Same length as `x`; element t = change-point probability at step t,
        i.e. the posterior mass that the run has just (re)started (run length
        0 or 1). Bounded in [0, 1]; spikes toward 1 at a regime change.
    """
    x = np.asarray(x, dtype=float).ravel()
    n = len(x)
    cp_prob = np.zeros(n, dtype=float)
    if n == 0:
        return cp_prob

    H = float(hazard)

    # Complexity note: the run-length arrays grow by one element per step (no
    # pruning), so this is O(n^2). Fine for backtest-length series (<= a few
    # thousand points); prune the run-length tail if ever fed very long inputs.

    # Run-length distribution R: R[r] = P(run length == r). Grows by one each step.
    R = np.array([1.0])

    # Per-run-length NIG parameters (index r aligns with R).
    mu = np.array([mu0], dtype=float)
    kappa = np.array([kappa0], dtype=float)
    alpha = np.array([alpha0], dtype=float)
    beta = np.array([beta0], dtype=float)

    for t in range(n):
        xt = x[t]

        # Student-t posterior predictive for each current run length.
        # df = 2*alpha, loc = mu, scale = sqrt(beta*(kappa+1)/(alpha*kappa)).
        df = 2.0 * alpha
        scale = np.sqrt(beta * (kappa + 1.0) / (alpha * kappa))
        pred_prob = student_t.pdf(xt, df=df, loc=mu, scale=scale)

        # Growth probabilities: stay in the same run (no changepoint).
        growth = R * pred_prob * (1.0 - H)
        # Changepoint probability: collapse to run length 0.
        cp = float(np.sum(R * pred_prob * H))

        # New run-length distribution: index 0 = changepoint, 1.. = grown runs.
        new_R = np.empty(len(R) + 1, dtype=float)
        new_R[0] = cp
        new_R[1:] = growth

        total = new_R.sum()
        if total <= 0.0 or not np.isfinite(total):
            # Degenerate predictive (numerical underflow): reset to a fresh run.
            new_R = np.zeros(len(R) + 1, dtype=float)
            new_R[0] = 1.0
            total = 1.0
        new_R /= total
        R = new_R

        # Change-point probability: posterior mass that the run has just
        # (re)started (run length 0 or 1). P(r=0) alone is pinned at the hazard
        # and carries no signal; the short-run mass spikes at a regime change.
        cp_prob[t] = R[0] + (R[1] if len(R) > 1 else 0.0)

        # Update NIG params. New run-length 0 gets the prior; runs 1.. get the
        # sequential conjugate update of the run that preceded them.
        new_mu = np.empty(len(mu) + 1, dtype=float)
        new_kappa = np.empty(len(kappa) + 1, dtype=float)
        new_alpha = np.empty(len(alpha) + 1, dtype=float)
        new_beta = np.empty(len(beta) + 1, dtype=float)

        new_mu[0] = mu0
        new_kappa[0] = kappa0
        new_alpha[0] = alpha0
        new_beta[0] = beta0

        new_kappa[1:] = kappa + 1.0
        new_alpha[1:] = alpha + 0.5
        new_mu[1:] = (kappa * mu + xt) / (kappa + 1.0)
        new_beta[1:] = beta + (kappa * (xt - mu) ** 2) / (2.0 * (kappa + 1.0))

        mu, kappa, alpha, beta = new_mu, new_kappa, new_alpha, new_beta

    return cp_prob
