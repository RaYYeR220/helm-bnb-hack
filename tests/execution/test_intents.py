import pandas as pd

from execution.intents import regime_to_execution_plan, weights_to_intents


def _w(d):
    return pd.Series(d, dtype=float)


# --- weights_to_intents ---------------------------------------------------------

def test_sells_first_then_buys_largest_notional_first():
    cur = _w({"A": 0.5, "B": 0.3, "C": 0.2})
    tgt = _w({"A": 0.0, "B": 0.6, "C": 0.4})
    intents = weights_to_intents(cur, tgt, portfolio_usd=1000.0)
    assert [i["action"] for i in intents] == ["sell", "buy", "buy"]
    assert intents[0]["symbol"] == "A" and intents[0]["usd_amount"] == 500.0
    assert intents[1]["symbol"] == "B" and intents[1]["usd_amount"] == 300.0
    assert intents[2]["symbol"] == "C" and intents[2]["usd_amount"] == 200.0


def test_symbol_union_handles_full_entry_and_exit():
    cur = _w({"OLD": 1.0})
    tgt = _w({"NEW": 1.0})
    intents = weights_to_intents(cur, tgt, portfolio_usd=100.0)
    assert {(i["action"], i["symbol"]) for i in intents} == {
        ("sell", "OLD"),
        ("buy", "NEW"),
    }


def test_dust_trades_skipped():
    cur = _w({"A": 0.500})
    tgt = _w({"A": 0.505})  # $5 on a $1000 book < $10 dust floor
    assert weights_to_intents(cur, tgt, portfolio_usd=1000.0) == []


def test_zero_portfolio_returns_no_intents():
    assert weights_to_intents(_w({"A": 0.0}), _w({"A": 1.0}), portfolio_usd=0.0) == []


def test_intents_are_json_ready():
    intents = weights_to_intents(_w({"A": 0.0}), _w({"A": 0.5}), portfolio_usd=100.0)
    import json

    json.dumps(intents)  # must not raise


# --- regime_to_execution_plan ----------------------------------------------------

def _read(regime="ranging", risk_off=False):
    return {
        "regime": regime,
        "risk_off": risk_off,
        "recommended_stance": None,
        "date": "2026-06-09",
        "confidence": 0.9,
    }


def test_risk_off_holds_with_zero_intents():
    plan = regime_to_execution_plan(
        _read(regime="ranging", risk_off=True),
        _w({"A": 1.0}),
        _w({"A": 0.0}),
        portfolio_usd=1000.0,
    )
    assert plan["hold"] is True
    assert plan["intents"] == []
    assert "risk-off" in plan["note"]


def test_high_volatility_regime_holds():
    plan = regime_to_execution_plan(
        _read(regime="high_volatility"),
        _w({"A": 1.0}),
        _w({}),
        portfolio_usd=1000.0,
    )
    assert plan["hold"] is True
    assert plan["intents"] == []


def test_ranging_rebalance_carries_intents_and_note():
    plan = regime_to_execution_plan(
        _read(regime="ranging"),
        _w({"A": 1.0}),
        _w({"A": 0.5, "B": 0.5}),
        portfolio_usd=1000.0,
    )
    assert plan["hold"] is False
    assert len(plan["intents"]) == 2
    assert "1 sell / 1 buy" in plan["note"]


def test_aligned_portfolio_notes_no_trades():
    plan = regime_to_execution_plan(
        _read(regime="ranging"),
        _w({"A": 0.5, "B": 0.5}),
        _w({"A": 0.5, "B": 0.5}),
        portfolio_usd=1000.0,
    )
    assert plan["hold"] is False
    assert plan["intents"] == []
    assert "already aligned" in plan["note"]


# --- demo script ----------------------------------------------------------------

def test_execution_demo_imports_and_offline_plan():
    import importlib

    mod = importlib.import_module("scripts.execution_demo")
    assert callable(mod.main)
    plan = mod.plan_from_read(mod.OFFLINE_READ, mod.OFFLINE_TARGET, 9000.0)
    assert plan["hold"] is False
    assert len(plan["intents"]) == 3
    assert all(i["action"] == "buy" for i in plan["intents"])
    assert abs(sum(i["usd_amount"] for i in plan["intents"]) - 9000.0) < 1.0
