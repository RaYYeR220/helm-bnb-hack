"""Market-data feature engineering for the regime classifier.

Produces a per-date feature panel from a close-price panel (dates x symbols).
All features are causal: the value at date t uses only prices through t.
"""

import numpy as np
import pandas as pd

FEATURE_COLS = ["trend_strength", "realized_vol", "breadth", "dispersion"]


def _market_index_returns(prices: pd.DataFrame) -> pd.Series:
    """Equal-weight market index daily return: mean across names of per-name
    simple returns, skipping NaN. NaN where no name has a return that day."""
    per_name = prices.pct_change(fill_method=None)
    return per_name.mean(axis=1, skipna=True)


def compute_feature_panel(
    prices: pd.DataFrame,
    vol_window: int = 20,
    trend_window: int = 20,
    breadth_window: int = 20,
) -> pd.DataFrame:
    """Compute the four regime features per date.

    Columns (exact order): trend_strength, realized_vol, breadth, dispersion.

    - realized_vol: rolling std (ddof=0) of market-index returns over `vol_window`.
    - trend_strength: (rolling mean / rolling std) of market returns over
      `trend_window`; 0.0 where the std is 0 or NaN (a signed, Sharpe-like measure).
    - breadth: fraction of names (with data) whose trailing `breadth_window`
      cumulative return is > 0.
    - dispersion: cross-sectional std (over names) of the per-name trailing
      `breadth_window` cumulative return, per date.

    Leading rows that are entirely NaN (insufficient history) are dropped.
    """
    prices = prices.sort_index()

    mkt = _market_index_returns(prices)

    realized_vol = mkt.rolling(vol_window).std(ddof=0)

    roll_mean = mkt.rolling(trend_window).mean()
    roll_std = mkt.rolling(trend_window).std(ddof=0)
    trend_strength = roll_mean / roll_std
    trend_strength = trend_strength.where(
        (roll_std > 0) & roll_std.notna(), 0.0
    )

    # per-name trailing breadth_window cumulative return: price_t / price_{t-w} - 1
    shifted = prices.shift(breadth_window)
    cum_ret = prices / shifted - 1.0   # NaN where either endpoint is missing

    have = cum_ret.notna()
    n_have = have.sum(axis=1)
    n_pos = (cum_ret > 0).sum(axis=1)
    breadth = (n_pos / n_have).where(n_have > 0, np.nan)

    # cross-sectional std over names of the trailing-window cumulative return
    dispersion = cum_ret.std(axis=1, ddof=0, skipna=True)

    feats = pd.DataFrame(
        {
            "trend_strength": trend_strength,
            "realized_vol": realized_vol,
            "breadth": breadth,
            "dispersion": dispersion,
        },
        index=prices.index,
    )[FEATURE_COLS]

    # Drop leading rows that are entirely NaN (insufficient history). After the
    # first usable row, forward-fill any residual gaps and zero anything still
    # missing so the matrix is finite for the HMM/scaler.
    all_nan = feats.isna().all(axis=1)
    if all_nan.any():
        first_valid_pos = int((~all_nan).to_numpy().argmax())
        feats = feats.iloc[first_valid_pos:]
    feats = feats.ffill().fillna(0.0)
    return feats
