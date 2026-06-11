"""Offline tests for the ERC-8183 deliverable construction (provider side).

The deliverable is the on-chain product Helm sells: a ``RegimeRead`` -> canonical
JSON payload. These tests exercise the pure serialization helpers and the
``on_job`` handler with an injected fake ``read_fn`` — NO network, NO bnbagent
client, NO live HMM. They lock the payload shape (regime/confidence/stance/
risk-off/posterior/attribution) and the read_fn injection seam.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from helm.types import RegimeRead
from onchain.regime_service import (
    DELIVERABLE_VERSION,
    HELM_AGENT_NAME,
    build_deliverable_payload,
    make_on_job,
    serialize_deliverable,
)


def _sample_read() -> RegimeRead:
    return RegimeRead(
        date=pd.Timestamp("2026-06-10"),
        regime="trending",
        posterior={"trending": 0.72, "ranging": 0.20, "high_volatility": 0.08},
        confidence=0.72,
        features={"trend_strength": 1.4, "realized_vol": 0.02},
        attribution={"trend_strength": 0.61, "realized_vol": -0.09},
    )


def test_payload_shape_and_envelope():
    payload = build_deliverable_payload(_sample_read(), risk_off=False, job_id=42)
    assert payload["version"] == DELIVERABLE_VERSION
    assert payload["service"] == HELM_AGENT_NAME
    assert payload["job_id"] == 42
    read = payload["read"]
    assert read["regime"] == "trending"
    assert read["risk_off"] is False
    assert read["recommended_stance"] == "momentum"
    assert read["date"] == "2026-06-10"
    assert set(read["posterior"]) == {"trending", "ranging", "high_volatility"}
    assert set(read["attribution"]) == set(read["features"])


def test_payload_omits_job_id_when_absent():
    payload = build_deliverable_payload(_sample_read(), risk_off=False)
    assert "job_id" not in payload


def test_risk_off_overrides_stance_in_payload():
    payload = build_deliverable_payload(_sample_read(), risk_off=True, job_id=1)
    # regime label preserved, but the stance is forced defensive by the gate
    assert payload["read"]["regime"] == "trending"
    assert payload["read"]["risk_off"] is True
    assert payload["read"]["recommended_stance"] == "defensive"


def test_serialize_is_canonical_and_json_safe():
    s = serialize_deliverable(_sample_read(), risk_off=False, job_id=7)
    # canonical: sorted keys, compact separators, deterministic
    assert s == serialize_deliverable(_sample_read(), risk_off=False, job_id=7)
    assert ", " not in s and ": " not in s  # compact separators
    back = json.loads(s)
    assert back["job_id"] == 7
    # no numpy / Timestamp leakage — pure floats + strings
    assert isinstance(back["read"]["confidence"], float)


def test_on_job_uses_injected_read_fn_and_stamps_job_id():
    read = _sample_read()
    calls = []

    def fake_read_fn(job):
        calls.append(job)
        return read, False

    on_job = make_on_job(read_fn=fake_read_fn)
    out = on_job({"jobId": 99, "budget": 10**18})

    # the handler returns the canonical deliverable string for THIS job id
    assert json.loads(out)["job_id"] == 99
    assert json.loads(out)["read"]["regime"] == "trending"
    # the injected read_fn was called with the job dict
    assert calls == [{"jobId": 99, "budget": 10**18}]


def test_on_job_propagates_risk_off_from_read_fn():
    read = _sample_read()
    on_job = make_on_job(read_fn=lambda job: (read, True))
    out = json.loads(on_job({"jobId": 5}))
    assert out["read"]["risk_off"] is True
    assert out["read"]["recommended_stance"] == "defensive"


def test_on_job_handles_missing_job_id():
    # A job dict without 'jobId' must still produce a valid deliverable.
    on_job = make_on_job(read_fn=lambda job: (_sample_read(), False))
    out = json.loads(on_job({}))
    assert "job_id" not in out
    assert out["read"]["regime"] == "trending"


def test_deliverable_matches_off_chain_skill_shape():
    # The on-chain deliverable's `read` must equal scripts.helm_read.read_to_dict
    # so the on-chain service and the off-chain skill never diverge.
    from scripts.helm_read import read_to_dict

    read = _sample_read()
    payload = build_deliverable_payload(read, risk_off=False)
    assert payload["read"] == read_to_dict(read, False)


def test_default_read_fn_is_the_live_engine_path(monkeypatch):
    # make_on_job() with no read_fn must fall back to the live regime_read_fn.
    # We stub regime_read_fn (so no network) and confirm the default handler
    # calls it — proving the injection default is wired correctly.
    import onchain.regime_service as rs

    called = {}

    def fake_live(job):
        called["job"] = job
        return _sample_read(), False

    monkeypatch.setattr(rs, "regime_read_fn", fake_live)
    on_job = make_on_job()  # no read_fn -> must use regime_read_fn
    out = json.loads(on_job({"jobId": 11}))
    assert called["job"] == {"jobId": 11}
    assert out["job_id"] == 11
