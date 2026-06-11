"""ERC-8183 PROVIDER side — Helm sells a regime read as an on-chain service.

This module turns Helm into a hireable agent service. The provider loop:

1. polls the ERC-8183 kernel for **funded** jobs assigned to Helm's wallet,
2. for each, runs Helm's regime engine to produce a ``RegimeRead`` deliverable,
3. wraps it in the SDK's ``DeliverableManifest`` (keccak256 committed on-chain),
   uploads the full JSON via a ``StorageProvider``, and ``submit``s,
4. settlement is permissionless and handled by the buyer/operator after the
   dispute window (OptimisticPolicy silence-approves).

The SDK does the heavy lifting. We provide the **``on_job`` handler** that the
SDK's :func:`bnbagent.erc8183.server.create_erc8183_app` calls for every funded
job; the SDK then verifies, manifests, stores, and submits. The handler's only
job is to return the deliverable string — which is exactly Helm's job.

The deliverable is produced by an injectable ``read_fn`` so the loop is testable
offline: the default ``read_fn`` shells into the same engine path as
``scripts/helm_read.py``; tests inject a deterministic fake. The serialization
(``RegimeRead`` -> canonical JSON string) is a pure function and fully tested.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from helm.types import RegimeRead

# Helm's on-chain service identity (shared with onchain.identity).
HELM_AGENT_NAME = "helm-regime-read"
HELM_AGENT_DESCRIPTION = (
    "Helm: regime-switching, on-chain-flow-aware strategy read for the BSC "
    "majors. Returns a RegimeRead (regime label, confidence, posterior, top "
    "feature attribution, market risk-off gate, recommended stance) from a "
    "walk-forward HMM fused with on-chain TVL flow."
)

# Deliverable envelope version — bump if the payload shape below changes so
# downstream verifiers fail loudly rather than misread fields.
DELIVERABLE_VERSION = 1

# The handler returns this content_type in the DeliverableManifest.response.
DELIVERABLE_CONTENT_TYPE = "application/json"

# A read_fn produces (RegimeRead, risk_off) for a job. Network-bound by default;
# injected with a fake in tests.
ReadFn = Callable[[dict[str, Any]], "tuple[RegimeRead, bool]"]


# ---------------------------------------------------------------------------
# Deliverable serialization (pure / network-free — fully unit-tested)
# ---------------------------------------------------------------------------


def build_deliverable_payload(
    read: RegimeRead,
    risk_off: bool,
    *,
    job_id: int | None = None,
) -> dict[str, Any]:
    """Serialize a ``RegimeRead`` (+ risk-off flag) to the deliverable dict.

    Pure / network-free. This is the on-chain product Helm sells. It reuses the
    exact same field shape as ``scripts/helm_read.read_to_dict`` (so a buyer who
    knows the off-chain skill gets an identical payload), wrapped in a small
    versioned envelope that records the service identity and (optionally) the
    job id it answers. All numeric values are coerced to plain floats so
    ``json.dumps`` never sees a numpy / pandas type.
    """
    # Reuse the canonical RegimeRead serializer + stance logic from the live
    # skill so the on-chain deliverable and the off-chain skill never diverge.
    from scripts.helm_read import read_to_dict

    read_dict = read_to_dict(read, risk_off)
    payload: dict[str, Any] = {
        "version": DELIVERABLE_VERSION,
        "service": HELM_AGENT_NAME,
        "read": read_dict,
    }
    if job_id is not None:
        payload["job_id"] = job_id
    return payload


def serialize_deliverable(
    read: RegimeRead,
    risk_off: bool,
    *,
    job_id: int | None = None,
) -> str:
    """Canonical JSON string for the deliverable (sorted keys, compact).

    Deterministic across platforms — this exact string is what the SDK stores
    in the ``DeliverableManifest.response.content`` field and what the on-chain
    keccak256 commitment ultimately covers (via the manifest hash).
    """
    payload = build_deliverable_payload(read, risk_off, job_id=job_id)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Default read_fn — the live Helm engine (same path as scripts/helm_read.py)
# ---------------------------------------------------------------------------


def regime_read_fn(job: dict[str, Any], *, days: int = 200) -> tuple[RegimeRead, bool]:
    """Default ``read_fn``: run the live Helm engine, return ``(read, risk_off)``.

    Network-bound (hits CMC + builds the HMM); not exercised by the unit tests.
    Reuses ``scripts.helm_read._build_read`` so the on-chain service and the
    human-run skill share one engine path. The ``job`` dict is accepted for
    signature symmetry (a future version could read params from
    ``job["description"]`` — e.g. a requested panel length).
    """
    from scripts.helm_read import _build_read

    return _build_read(days)


# ---------------------------------------------------------------------------
# on_job handler factory — the seam the SDK server calls per funded job
# ---------------------------------------------------------------------------


def make_on_job(read_fn: ReadFn | None = None) -> Callable[[dict[str, Any]], str]:
    """Build the ``on_job(job) -> str`` handler the ERC-8183 server invokes.

    The returned callable is exactly the contract
    :func:`bnbagent.erc8183.server.create_erc8183_app` expects: it receives a
    verified funded ``job`` dict and returns the deliverable string. The SDK
    then manifests it (keccak256), uploads via the ``StorageProvider``, and
    ``submit``s on-chain — we never touch the wallet here.

    ``read_fn`` is injectable so the handler is testable with a deterministic
    fake; it defaults to the live :func:`regime_read_fn`.
    """
    fn: ReadFn = read_fn or regime_read_fn

    def on_job(job: dict[str, Any]) -> str:
        read, risk_off = fn(job)
        return serialize_deliverable(read, risk_off, job_id=job.get("jobId"))

    return on_job


# ---------------------------------------------------------------------------
# Provider app builder — wires the real SDK server
# ---------------------------------------------------------------------------


def build_provider_app(
    wallet_password: str,
    *,
    network: str = "bsc-testnet",
    service_price: int = 0,
    agent_url: str | None = None,
    storage_base_dir: str | None = None,
    read_fn: ReadFn | None = None,
    app_factory: Any | None = None,
):
    """Build the FastAPI provider app that serves Helm as an ERC-8183 agent.

    Wires the real SDK stack:

    - ``EVMWalletProvider`` (keystore-backed, ``SigningPolicy.strict_default``),
    - ``LocalStorageProvider`` for deliverable manifests,
    - ``ERC8183Config`` (service price floor + agent URL),
    - ``create_erc8183_app(on_job=make_on_job(read_fn))`` — which runs the
      funded-job poll loop and submits each deliverable.

    The funded poll loop is the SDK's; our contribution is the ``on_job``
    handler (the Helm read) plus the wiring. ``app_factory`` is a test seam:
    a callable ``(config, on_job) -> app`` substituted for
    ``create_erc8183_app`` so the wiring is unit-checkable without a live RPC.

    Returns the FastAPI app (run with uvicorn). See
    ``scripts/onchain_agent_demo.py --serve``.
    """
    on_job = make_on_job(read_fn)

    if app_factory is not None:
        # Test/offline seam — caller controls construction entirely.
        return app_factory(on_job)

    from bnbagent import EVMWalletProvider
    from bnbagent.erc8183.config import ERC8183Config
    from bnbagent.erc8183.server import create_erc8183_app
    from bnbagent.storage import LocalStorageProvider

    wallet = EVMWalletProvider(password=wallet_password)
    storage = LocalStorageProvider(
        base_dir=storage_base_dir or ".agent-data"
    )
    config = ERC8183Config(
        network=network,
        wallet_provider=wallet,
        storage=storage,
        service_price=str(service_price),
        agent_url=agent_url,
    )
    return create_erc8183_app(config=config, on_job=on_job)
