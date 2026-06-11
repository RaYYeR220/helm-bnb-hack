"""Offline tests for ERC-8004 identity (onchain/identity.py).

Covers the pure URI builder (real SDK ``AgentURIGenerator``, no RPC) and the
idempotent ``register_helm_agent`` logic branches with a FAKE ERC8004 agent
injected at the ``agent_factory`` seam — NO network, NO wallet, NO chain.
"""

from __future__ import annotations

import base64
import json

import pytest

from onchain.identity import (
    HELM_AGENT_NAME,
    build_agent_uri,
    register_helm_agent,
)


# --------------------------------------------------------------------------- #
# build_agent_uri — pure (uses the SDK's AgentURIGenerator, no RPC)
# --------------------------------------------------------------------------- #


def _decode_uri(uri: str) -> dict:
    assert uri.startswith("data:application/json;base64,")
    return json.loads(base64.b64decode(uri.split(",", 1)[1]))


def test_build_agent_uri_has_discovery_card():
    card = _decode_uri(build_agent_uri())
    assert card["name"] == HELM_AGENT_NAME
    assert card["description"]
    names = {svc["name"] for svc in card["services"]}
    assert names == {"ERC8183", "web"}


def test_build_agent_uri_endpoints_are_configurable():
    uri = build_agent_uri(
        erc8183_endpoint="https://my-host/erc8183",
        web_endpoint="https://my-host/",
    )
    card = _decode_uri(uri)
    erc = next(s for s in card["services"] if s["name"] == "ERC8183")
    assert erc["endpoint"] == "https://my-host/erc8183"


def test_build_agent_uri_stamps_registrations_when_agent_id_and_registry_given():
    # The SDK only populates `registrations` when agent_id + chain_id + the
    # identity_registry address are ALL present (matches AgentURIGenerator).
    card = _decode_uri(
        build_agent_uri(agent_id=7, chain_id=97, identity_registry="0xREG")
    )
    regs = card["registrations"]
    assert regs and regs[0]["agentId"] == 7
    assert regs[0]["agentRegistry"] == "eip155:97:0xREG"


def test_build_agent_uri_no_registrations_without_agent_id():
    card = _decode_uri(build_agent_uri())
    assert card["registrations"] == []


def test_build_agent_uri_no_registrations_without_registry():
    # agent_id given but no registry -> SDK omits registrations (real behavior).
    card = _decode_uri(build_agent_uri(agent_id=7, chain_id=97))
    assert card["registrations"] == []


# --------------------------------------------------------------------------- #
# register_helm_agent — idempotency branches with a fake agent
# --------------------------------------------------------------------------- #


class _FakeAgent:
    """Minimal stand-in for ERC8004Agent (the surface register_helm_agent uses)."""

    def __init__(self, *, existing=None, agent_id=123, tx="0xabc"):
        self._existing = existing
        self._agent_id = agent_id
        self._tx = tx
        self.wallet_address = "0xHELMWALLET"
        self.registered_uri = None
        self.generated = None

    def get_local_agent_info(self, name):
        return self._existing

    def generate_agent_uri(self, *, name, description, endpoints):
        self.generated = {"name": name, "endpoints": endpoints}
        return "data:application/json;base64,ZmFrZQ=="

    def register_agent(self, *, agent_uri):
        self.registered_uri = agent_uri
        return {
            "agentId": self._agent_id,
            "transactionHash": self._tx,
            "agentURI": agent_uri,
        }


def test_register_fresh_agent_registers_and_returns_id():
    fake = _FakeAgent(existing=None, agent_id=42, tx="0xdeadbeef")
    result = register_helm_agent("pw", agent_factory=lambda: fake)

    assert result["status"] == "registered"
    assert result["agent_id"] == 42
    assert result["tx_hash"] == "0xdeadbeef"
    assert result["address"] == "0xHELMWALLET"
    assert result["network"] == "bsc-testnet"
    # it actually generated a URI with Helm's name + both endpoints and registered it
    assert fake.registered_uri is not None
    assert fake.generated["name"] == HELM_AGENT_NAME
    assert {e.name for e in fake.generated["endpoints"]} == {"ERC8183", "web"}


def test_register_is_idempotent_when_already_owned():
    existing = {"agent_id": 9, "agent_uri": "data:...prior", "owner_address": "0xHELMWALLET"}
    fake = _FakeAgent(existing=existing)
    result = register_helm_agent("pw", agent_factory=lambda: fake)

    assert result["status"] == "exists"
    assert result["agent_id"] == 9
    assert result["tx_hash"] is None
    assert result["agent_uri"] == "data:...prior"
    # idempotent: it must NOT have registered a duplicate
    assert fake.registered_uri is None


def test_register_passes_network_through():
    fake = _FakeAgent(existing=None)
    result = register_helm_agent("pw", network="bsc-mainnet", agent_factory=lambda: fake)
    assert result["network"] == "bsc-mainnet"
