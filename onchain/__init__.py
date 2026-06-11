"""Helm on-chain agent-commerce layer (deliverable E3).

This package wraps Helm — a regime-switching BSC strategy engine — as a
discoverable, hireable **on-chain agent** using the BNB AI Agent SDK
(``bnbagent``). Another agent can hire Helm for a regime read, pay into an
ERC-8183 escrow, receive the deliverable, and settle — all on BSC.

Layers (each maps to a real bnbagent primitive):

- **Identity** (ERC-8004) — :mod:`onchain.identity` registers Helm in the
  on-chain Identity Registry with an ``AgentEndpoint`` discovery card so other
  agents can find it. Registration is gas-free via the MegaFuel paymaster.
- **Commerce** (ERC-8183) — :mod:`onchain.regime_service` runs the PROVIDER
  loop: poll funded jobs, produce the deliverable (a Helm ``RegimeRead`` JSON),
  submit, settle. :mod:`onchain.client_demo` runs the BUYER side: discover,
  create job, fund escrow, await deliverable, settle.
- **Security** — every signing path goes through the SDK's ``SigningPolicy``
  (fail-closed EIP-712 gate) and, for x402 payments, ``X402Signer`` (per-call
  + session budget caps with recipient binding).
- **Storage** — deliverable manifests persist through a ``StorageProvider``
  (``LocalStorageProvider`` by default); the on-chain ``deliverable`` field is
  the keccak256 of the canonical manifest so verifiers can re-hash and confirm.

Dependency note
---------------
This package requires the **``agent``** dependency group, which is NOT part of
Helm's core install::

    uv sync --group agent       # or: uv add --group agent bnbagent[server]

The core ``helm/`` package never imports ``bnbagent``. To keep ``import helm``
and the core test suite free of the heavy web3 stack, this package imports
``bnbagent`` lazily (inside functions), so ``import onchain`` succeeds even
when the SDK is absent — only the functions that actually touch the chain
require it. The pure helpers (URI building, deliverable serialization) work
with zero SDK present.

The Helm engine itself is reused unchanged: the deliverable is produced by the
same ``RegimeRead`` path that backs ``scripts/helm_read.py``.
"""

from onchain.identity import build_agent_uri, register_helm_agent
from onchain.regime_service import (
    HELM_AGENT_DESCRIPTION,
    HELM_AGENT_NAME,
    build_deliverable_payload,
    regime_read_fn,
)

__all__ = [
    "build_agent_uri",
    "register_helm_agent",
    "build_deliverable_payload",
    "regime_read_fn",
    "HELM_AGENT_NAME",
    "HELM_AGENT_DESCRIPTION",
]
