"""Offline tests for scripts/helm_read.py.

The script's live path hits the CMC API and is run by a human; these tests only
import-check it and exercise the pure, network-free helpers (`read_to_dict` and
`format_read`) on a hand-constructed RegimeRead. No live calls.
"""

import importlib
import json

import pandas as pd

from helm.types import RegimeRead


def _sample_read() -> RegimeRead:
    return RegimeRead(
        date=pd.Timestamp("2026-06-10"),
        regime="trending",
        posterior={"trending": 0.71, "ranging": 0.21, "high_volatility": 0.08},
        confidence=0.71,
        features={
            "trend_strength": 1.4,
            "realized_vol": 0.02,
            "breadth": 0.75,
            "dispersion": 0.11,
        },
        attribution={
            "trend_strength": 0.62,
            "realized_vol": -0.10,
            "breadth": 0.20,
            "dispersion": 0.08,
        },
    )


def test_helm_read_script_imports_and_exposes_main():
    mod = importlib.import_module("scripts.helm_read")
    assert hasattr(mod, "main")
    assert callable(mod.main)
    for name in ("read_to_dict", "format_read", "recommended_stance"):
        assert hasattr(mod, name)
        assert callable(getattr(mod, name))


def test_recommended_stance_maps_regimes_and_gate():
    from scripts.helm_read import recommended_stance

    assert recommended_stance("trending", risk_off=False) == "momentum"
    assert recommended_stance("ranging", risk_off=False) == "market portfolio"
    assert recommended_stance("high_volatility", risk_off=False) == "defensive"
    # the risk-off gate overrides every regime to defensive
    assert recommended_stance("trending", risk_off=True) == "defensive"
    assert recommended_stance("ranging", risk_off=True) == "defensive"


def test_read_to_dict_is_json_serializable_and_complete():
    from scripts.helm_read import read_to_dict

    d = read_to_dict(_sample_read(), risk_off=False)
    # round-trips through JSON (no numpy / Timestamp leakage)
    text = json.dumps(d)
    back = json.loads(text)

    assert back["regime"] == "trending"
    assert back["date"] == "2026-06-10"
    assert back["risk_off"] is False
    assert back["recommended_stance"] == "momentum"
    assert abs(back["confidence"] - 0.71) < 1e-9
    assert set(back["posterior"]) == {"trending", "ranging", "high_volatility"}
    assert set(back["features"]) == {
        "trend_strength",
        "realized_vol",
        "breadth",
        "dispersion",
    }
    assert set(back["attribution"]) == set(back["features"])


def test_read_to_dict_reflects_risk_off_override():
    from scripts.helm_read import read_to_dict

    d = read_to_dict(_sample_read(), risk_off=True)
    assert d["risk_off"] is True
    # trending regime label is preserved, but the stance is overridden
    assert d["regime"] == "trending"
    assert d["recommended_stance"] == "defensive"


def test_format_read_contains_key_fields_and_top_attribution():
    from scripts.helm_read import format_read

    text = format_read(_sample_read(), risk_off=False)
    assert "trending" in text
    assert "2026-06-10" in text
    assert "momentum" in text
    # confidence rendered as a percentage-ish number
    assert "0.71" in text or "71" in text
    # the dominant attribution feature is surfaced
    assert "trend_strength" in text


def test_format_read_announces_risk_off_when_gated():
    from scripts.helm_read import format_read

    clear = format_read(_sample_read(), risk_off=False)
    fired = format_read(_sample_read(), risk_off=True)
    assert "defensive" in fired.lower()
    # the two renderings differ on the gate line
    assert clear != fired
