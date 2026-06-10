import pandas as pd

from helm.validation.windows import combinatorial_windows, walk_forward_windows


def _index(n, start="2020-01-01"):
    return pd.date_range(start, periods=n, freq="D")


# --- walk_forward_windows -----------------------------------------------------

def test_walk_forward_four_windows_of_25_cover_the_tail():
    idx = _index(100)
    wins = walk_forward_windows(idx, n_windows=4, embargo=5)
    assert len(wins) == 4
    for _, test_idx in wins:
        assert len(test_idx) == 25
    # contiguous, non-overlapping, tail-covering
    assert wins[0][1][0] == idx[0]
    assert wins[-1][1][-1] == idx[-1]
    # adjacent test windows abut with no gap
    assert wins[1][1][0] == wins[0][1][-1] + pd.Timedelta(days=1)


def test_walk_forward_leftover_head_rows_belong_to_no_window():
    # 103 // 4 == 25 -> 4 windows of 25 cover 100 rows; first 3 rows are orphan head
    idx = _index(103)
    wins = walk_forward_windows(idx, n_windows=4, embargo=5)
    assert all(len(t) == 25 for _, t in wins)
    assert wins[0][1][0] == idx[3]            # tail-aligned: first test row is position 3
    assert wins[-1][1][-1] == idx[-1]


def test_walk_forward_train_is_strictly_before_test_minus_embargo():
    idx = _index(100)
    wins = walk_forward_windows(idx, n_windows=4, embargo=5)
    for train_idx, test_idx in wins:
        # no train/test overlap
        assert len(set(train_idx) & set(test_idx)) == 0
        if len(train_idx) > 0:
            # 5-position embargo: train ends >= 6 calendar days before test start
            gap = (test_idx[0] - train_idx[-1]).days
            assert gap >= 6


def test_walk_forward_first_window_has_empty_train_when_embargo_eats_head():
    # window 0 starts at position 0; train cut = 0 - embargo < 0 -> empty train
    idx = _index(100)
    wins = walk_forward_windows(idx, n_windows=4, embargo=5)
    assert len(wins[0][0]) == 0
    assert len(wins[1][0]) == 20  # test1 starts at pos 25; train = positions [0, 20)


# --- combinatorial_windows ----------------------------------------------------

def test_combinatorial_produces_c_n_choose_k_combinations():
    idx = _index(100)
    cw = combinatorial_windows(idx, n_groups=6, n_test=2, embargo=5)
    assert len(cw) == 15  # C(6, 2)


def test_combinatorial_test_is_union_of_two_groups():
    idx = _index(100)
    cw = combinatorial_windows(idx, n_groups=6, n_test=2, embargo=5)
    # 100 // 6 == 16 -> each group is 16 rows, 2 groups -> 32 test rows
    for _, test_idx in cw:
        assert len(test_idx) == 32


def test_combinatorial_no_train_test_overlap():
    idx = _index(100)
    cw = combinatorial_windows(idx, n_groups=6, n_test=2, embargo=5)
    for train_idx, test_idx in cw:
        assert len(set(train_idx) & set(test_idx)) == 0


def test_combinatorial_embargo_excluded_on_both_sides_of_each_test_group():
    idx = _index(100)
    cw = combinatorial_windows(idx, n_groups=6, n_test=2, embargo=5)
    # group size 16, leftover head = 100 - 16*6 = 4, so group bounds start at pos 4:
    #   g0=[4,20) g1=[20,36) g2=[36,52) g3=[52,68) g4=[68,84) g5=[84,100)
    # combo (0, 3) is index 2 in itertools.combinations order: (0,1),(0,2),(0,3),...
    train_idx, test_idx = cw[2]
    train_pos = {idx.get_loc(d) for d in train_idx}
    # embargo on group 3 boundary: positions 47..51 (left) and 68..72 (right) excluded
    for p in (47, 48, 49, 50, 51, 68, 69, 70, 71, 72):
        assert p not in train_pos
    # embargo on group 0 boundary: left clipped to head (0..3), right 20..24 excluded
    for p in (0, 1, 2, 3, 20, 21, 22, 23, 24):
        assert p not in train_pos
