from helm.data.universe import load_universe, MAJORS


def test_load_universe_returns_deduped_symbols():
    syms = load_universe()
    assert isinstance(syms, list)
    assert all(isinstance(s, str) for s in syms)
    assert len(syms) == len(set(syms)), "universe must be deduplicated"
    assert len(syms) >= 100
    assert "ETH" in syms and "CAKE" in syms


def test_majors_subset_is_in_universe():
    syms = set(load_universe())
    assert set(MAJORS).issubset(syms)
    assert len(MAJORS) >= 5
