"""Attribute realized backtest P&L to the active regime per period."""

import numpy as np
import pandas as pd


def regime_pnl_attribution(returns: pd.Series, regime_path: pd.Series) -> dict:
    """Bucket realized per-period returns by the active regime on each date.

    Parameters
    ----------
    returns : pd.Series
        Per-period net returns (e.g. BacktestResult.returns); NaN periods (such
        as the day-0 no-return-period) are dropped.
    regime_path : pd.Series
        date -> regime label. Dates with a return but no label are bucketed as
        "unclassified".

    Returns
    -------
    dict
        regime label -> {days, total_return, mean_return, share_of_pnl}, where
        total_return is the compounded product of (1+r)-1 over that regime's
        days, and share_of_pnl is each bucket's total_return divided by the sum
        of all buckets' total_return (0.0 for every bucket if that sum is 0).
    """
    r = returns.dropna()
    if len(r) == 0:
        return {}

    labels = regime_path.reindex(r.index)
    labels = labels.where(labels.notna(), "unclassified")

    buckets: dict[str, dict] = {}
    for label in labels.unique():
        mask = labels == label
        seg = r[mask]
        total = float(np.prod(1.0 + seg.to_numpy()) - 1.0)
        buckets[str(label)] = {
            "days": int(mask.sum()),
            "total_return": total,
            "mean_return": float(seg.mean()),
            "share_of_pnl": 0.0,  # filled below
        }

    grand_total = sum(b["total_return"] for b in buckets.values())
    if grand_total != 0.0:
        for b in buckets.values():
            b["share_of_pnl"] = b["total_return"] / grand_total

    return buckets
