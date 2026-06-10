import importlib

import pandas as pd


def test_validation_run_imports_and_exposes_main_and_gate_factory():
    mod = importlib.import_module("scripts.validation_run")
    assert hasattr(mod, "main")
    assert callable(mod.main)
    assert hasattr(mod, "make_confirmed_gate")
    assert callable(mod.make_confirmed_gate)


def _scripted_gate(sequence):
    """A base gate that ignores its input and returns the next scripted bool."""
    it = iter(sequence)

    def gate(_prices_hist):
        return next(it)

    return gate


def test_make_confirmed_gate_requires_n_consecutive_to_flip_either_way():
    from scripts.validation_run import make_confirmed_gate

    # raw sequence with one-day flickers; confirm=2 must ignore single flickers
    raw = [False, False, True, False, True, True, True, False, True, False, False, False]
    gate = make_confirmed_gate(_scripted_gate(raw), confirm=2)
    dummy = pd.DataFrame({"A": [1.0, 2.0]})
    got = [int(gate(dummy)) for _ in raw]
    # flips ON only after 2 consecutive True (positions 4,5 -> True at pos 5);
    # one-day flicker at pos 7 does NOT flip back; flips OFF after 2 consecutive
    # False (positions 9,10 -> False at pos 10).
    assert got == [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0]


def test_make_confirmed_gate_confirm_three_needs_three_in_a_row():
    from scripts.validation_run import make_confirmed_gate

    raw = [False, False, True, False, True, True, True, False, True, False, False, False]
    gate = make_confirmed_gate(_scripted_gate(raw), confirm=3)
    dummy = pd.DataFrame({"A": [1.0, 2.0]})
    got = [int(gate(dummy)) for _ in raw]
    # 3 consecutive True at positions 4,5,6 -> True at pos 6;
    # 3 consecutive False at positions 9,10,11 -> False at pos 11.
    assert got == [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0]


def test_make_confirmed_gate_fresh_instances_are_independent():
    from scripts.validation_run import make_confirmed_gate

    base_true = lambda _: True
    g1 = make_confirmed_gate(base_true, confirm=1)
    dummy = pd.DataFrame({"A": [1.0, 2.0]})
    assert g1(dummy) is True            # confirm=1 flips immediately
    # a fresh gate over the same base starts from the default (off) state
    g2 = make_confirmed_gate(base_true, confirm=3)
    assert g2(dummy) is False           # needs 3 confirmations, only 1 seen
