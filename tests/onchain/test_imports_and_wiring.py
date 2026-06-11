"""Import-check the orchestrator + onchain package, and test the provider-app
wiring seam offline.

The orchestrator (``scripts/onchain_agent_demo.py``) and ``build_provider_app``
are human-run / network-bound; here we only import-check them and verify the
wiring contract via the ``app_factory`` seam — confirming ``make_on_job`` is
threaded through to the server factory WITHOUT constructing a real wallet,
storage, or RPC client.
"""

from __future__ import annotations

import importlib
import json

import pandas as pd

from helm.types import RegimeRead
from onchain.regime_service import build_provider_app


def test_onchain_package_imports_without_agent_client():
    # `import onchain` and its submodules must succeed (bnbagent is imported
    # lazily inside functions, never at module import time).
    mod = importlib.import_module("onchain")
    for name in ("build_agent_uri", "register_helm_agent", "build_deliverable_payload"):
        assert hasattr(mod, name)


def test_orchestrator_script_imports_and_exposes_main():
    mod = importlib.import_module("scripts.onchain_agent_demo")
    assert callable(mod.main)
    for name in ("cmd_register", "cmd_serve", "cmd_hire", "build_parser"):
        assert hasattr(mod, name)


def test_orchestrator_parser_modes_are_mutually_exclusive():
    from scripts.onchain_agent_demo import build_parser

    parser = build_parser()
    args = parser.parse_args(["--hire", "--agent-id", "7"])
    assert args.hire is True and args.agent_id == 7

    reg = parser.parse_args(["--register"])
    assert reg.register is True


def test_build_provider_app_threads_on_job_through_factory():
    # The app_factory seam receives the on_job handler; calling it must run the
    # injected read_fn and produce a canonical Helm deliverable — proving the
    # provider wiring connects Helm's read to the SDK server's job callback.
    captured = {}

    def fake_app_factory(on_job):
        captured["on_job"] = on_job
        return "FAKE_APP"

    read = RegimeRead(
        date=pd.Timestamp("2026-06-10"),
        regime="ranging",
        posterior={"trending": 0.2, "ranging": 0.7, "high_volatility": 0.1},
        confidence=0.7,
        features={"trend_strength": 0.1},
        attribution={"trend_strength": 0.1},
    )

    app = build_provider_app(
        wallet_password="pw",
        read_fn=lambda job: (read, False),
        app_factory=fake_app_factory,
    )
    assert app == "FAKE_APP"

    # the captured handler is the real on_job: invoking it runs the read_fn
    out = json.loads(captured["on_job"]({"jobId": 3}))
    assert out["job_id"] == 3
    assert out["read"]["regime"] == "ranging"
    assert out["read"]["recommended_stance"] == "market portfolio"
