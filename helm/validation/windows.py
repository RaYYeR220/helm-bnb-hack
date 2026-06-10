"""Evaluation windows for the validation harness.

Two splitters turn a panel's date index into ``(train_idx, test_idx)`` pairs:

- ``walk_forward_windows`` carves the TAIL of the index into ``n_windows``
  contiguous, equal-length, non-overlapping test windows; each window's train
  index is every date strictly before ``(test_start - embargo)`` positions.
- ``combinatorial_windows`` splits the index into ``n_groups`` contiguous groups
  and, for every ``C(n_groups, n_test)`` combination, makes the test index the
  union of the chosen groups and the train index the remaining dates minus an
  ``embargo`` buffer adjacent to each test-group boundary on BOTH sides.

These produce index *slices* only. Per-day returns are evaluated by slicing a
single full-panel backtest (see ``helm.validation.harness``); the embargo exists
for honest CONFIG SELECTION, not for purging estimator leakage (the path is
already causal). Integer division is used throughout; leftover head rows that do
not fill a whole window/group belong to no test window.
"""

import itertools

import pandas as pd


def walk_forward_windows(
    index: pd.DatetimeIndex, n_windows: int, embargo: int = 5
) -> list[tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
    """Split the tail of ``index`` into ``n_windows`` contiguous test windows.

    Each window of equal length ``len(index) // n_windows`` covers the tail; any
    leftover head rows (``len(index) % n_windows``) belong to no test window. For
    each test window the train index is every date strictly before
    ``(test_start_position - embargo)``; if that cut is non-positive the train
    index is empty (the caller decides whether such a window is usable).
    """
    n = len(index)
    if n_windows < 1 or n == 0:
        return []
    win = n // n_windows
    if win == 0:
        return []
    head = n - win * n_windows  # leftover head rows (orphaned)

    out: list[tuple[pd.DatetimeIndex, pd.DatetimeIndex]] = []
    for k in range(n_windows):
        test_start = head + k * win
        test_end = test_start + win
        test_idx = index[test_start:test_end]
        cut = test_start - embargo
        train_idx = index[:cut] if cut > 0 else index[:0]
        out.append((train_idx, test_idx))
    return out


def combinatorial_windows(
    index: pd.DatetimeIndex,
    n_groups: int = 6,
    n_test: int = 2,
    embargo: int = 5,
) -> list[tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
    """Every ``C(n_groups, n_test)`` test/train split, with two-sided embargo.

    The index is split into ``n_groups`` equal contiguous groups covering the
    tail (leftover head rows form a buffer that is never a test group). For each
    combination of ``n_test`` groups: the test index is the union of those
    groups; the train index is all other positions minus an ``embargo`` buffer
    immediately before and after each chosen group (clipped to the index ends).
    Combinations are produced in ``itertools.combinations`` order (deterministic).
    """
    n = len(index)
    if n_groups < 1 or n_test < 1 or n_test > n_groups or n == 0:
        return []
    gsize = n // n_groups
    if gsize == 0:
        return []
    head = n - gsize * n_groups
    bounds = [(head + g * gsize, head + (g + 1) * gsize) for g in range(n_groups)]

    out: list[tuple[pd.DatetimeIndex, pd.DatetimeIndex]] = []
    for combo in itertools.combinations(range(n_groups), n_test):
        test_pos: set[int] = set()
        embargoed: set[int] = set()
        for g in combo:
            gs, ge = bounds[g]
            test_pos.update(range(gs, ge))
            for p in range(gs - embargo, gs):
                if 0 <= p < n:
                    embargoed.add(p)
            for p in range(ge, ge + embargo):
                if 0 <= p < n:
                    embargoed.add(p)
        train_pos = [
            p for p in range(n) if p not in test_pos and p not in embargoed
        ]
        out.append((index[train_pos], index[sorted(test_pos)]))
    return out
