"""ERC-8183 BUYER side — another agent hires Helm for a regime read.

Runnable demo of the full agent-commerce lifecycle from the *client* (buyer)
perspective, built on ``ERC8183Client``:

Happy path
----------
1. **discover** Helm by agent id (ERC-8004 registry) → its provider address.
2. **create_job**(provider=Helm, expired_at, description) → escrow opened (Open).
3. **register_job**(job_id) → bind the OptimisticPolicy on the Router.
4. **set_budget** + **fund**(job_id, amount) → escrow funded (Funded). The SDK's
   floor-based ``approve`` tops up the payment-token allowance as needed.
5. **await** the deliverable: poll ``get_job_status`` until SUBMITTED, then fetch
   + hash-verify the ``DeliverableManifest`` against the on-chain bytes32.
6. **settle**(job_id) → permissionless; pulls the policy verdict (silence ->
   APPROVE after the dispute window) and releases escrow to Helm (Completed).

Unhappy path
------------
``dispute`` / ``vote_reject`` / ``claim_refund`` — after submission the buyer can
``dispute``; a whitelisted-voter quorum ``vote_reject``s; ``settle`` then yields
REJECTED and the buyer ``claim_refund``s. (And ``cancel_open`` rejects a job that
was never funded — nothing was escrowed.) This module exposes the calls; the
quorum/voter machinery is on-chain and operator-driven, so the live demo
documents it rather than forcing a quorum.

This file is import-safe without the ``agent`` group: ``bnbagent`` is imported
lazily inside the functions that touch the chain. The pure helpers
(``verify_deliverable``, the discovery parse) are tested offline with fakes.
"""

from __future__ import annotations

import time
from typing import Any

from onchain.regime_service import HELM_AGENT_NAME

# Default escrow budget: 1 unit of the payment token (U has 18 decimals on the
# testnet deployment). Kept small for a demo; the provider's service_price floor
# is the real gate.
DEFAULT_BUDGET_RAW = 1 * 10**18

# How long the buyer waits for Helm to submit before giving up (seconds), and
# how often it re-checks job status.
DEFAULT_AWAIT_TIMEOUT_S = 600
DEFAULT_POLL_INTERVAL_S = 15

# Default job lifetime: long enough to clear the policy dispute window so
# create_job's pre-flight (SubmissionTooLate guard) passes. The SDK reads the
# real dispute_window on-chain; this is just the buyer's requested ceiling.
DEFAULT_JOB_TTL_S = 8 * 24 * 3600  # 8 days


# ---------------------------------------------------------------------------
# Pure helpers (network-free — unit-tested offline)
# ---------------------------------------------------------------------------


def verify_deliverable(manifest_dict: dict[str, Any], on_chain_hash: bytes) -> bool:
    """Re-hash a fetched ``DeliverableManifest`` and compare to the on-chain bytes32.

    Pure / network-free. This is the trust-minimizing check the buyer runs: it
    reconstructs the manifest from the fetched JSON and confirms its keccak256
    equals the 32-byte ``deliverable`` the provider committed on-chain — proving
    the off-chain payload was not swapped after ``submit``. Uses the SDK's own
    ``DeliverableManifest`` so the canonicalization matches the provider's.
    """
    from bnbagent.erc8183.schema import DeliverableManifest

    manifest = DeliverableManifest.from_dict(manifest_dict)
    return manifest.verify(on_chain_hash)


def resolve_provider_address(agent_record: dict[str, Any]) -> str:
    """Extract Helm's provider (owner) address from an ERC-8004 registry record.

    Pure / network-free. The registry's ``get_agent_info`` / ``get_all_agents``
    records carry the owner under either ``owner`` or ``owner_address`` depending
    on the call; normalize both. Raises ``ValueError`` if neither is present so a
    bad discovery result fails loudly rather than sending escrow to nowhere.
    """
    addr = agent_record.get("owner") or agent_record.get("owner_address")
    if not addr:
        raise ValueError(
            f"agent record has no owner/owner_address: keys={sorted(agent_record)}"
        )
    return addr


# ---------------------------------------------------------------------------
# Discovery (ERC-8004)
# ---------------------------------------------------------------------------


def discover_helm(
    agent_id: int,
    *,
    network: str = "bsc-testnet",
    wallet_password: str | None = None,
    wallets_dir: str | None = None,
    agent_factory: Any | None = None,
) -> dict[str, Any]:
    """Look up Helm in the ERC-8004 registry by ``agent_id`` and return its card.

    Returns ``{"agent_id", "provider_address", "agent_uri", "name"}``. A read-only
    ERC8004 connection is enough; a wallet is only used to satisfy the SDK's
    constructor (it never signs here). ``agent_factory`` is the test seam.
    """
    if agent_factory is not None:
        agent = agent_factory()
    else:
        from bnbagent import ERC8004Agent, EVMWalletProvider

        # ERC8004Agent requires a wallet_provider even for reads; load Helm's
        # own keystore (or any available) purely to construct the client.
        wallet = EVMWalletProvider(
            password=wallet_password or "", wallets_dir=wallets_dir
        )
        agent = ERC8004Agent(wallet_provider=wallet, network=network)

    info = agent.get_agent_info(agent_id)
    return {
        "agent_id": agent_id,
        "provider_address": resolve_provider_address(info),
        "agent_uri": info.get("agentURI", ""),
        "name": HELM_AGENT_NAME,
    }


# ---------------------------------------------------------------------------
# Happy-path lifecycle
# ---------------------------------------------------------------------------


def hire_helm(
    *,
    provider_address: str,
    wallet_password: str,
    network: str = "bsc-testnet",
    budget_raw: int = DEFAULT_BUDGET_RAW,
    job_ttl_s: int = DEFAULT_JOB_TTL_S,
    description: str = "Helm regime read for BSC majors",
    await_timeout_s: int = DEFAULT_AWAIT_TIMEOUT_S,
    poll_interval_s: int = DEFAULT_POLL_INTERVAL_S,
    wallets_dir: str | None = None,
    client_factory: Any | None = None,
    on_event: Any | None = None,
) -> dict[str, Any]:
    """Run the full buyer lifecycle: create -> fund -> await -> settle.

    Returns a dict tracing each step (job id, tx hashes, deliverable url,
    hash-verification result, final status). ``client_factory`` returns an
    ``ERC8183Client``-shaped object (test seam); ``on_event`` is an optional
    ``(stage, detail)`` progress callback for the demo CLI.
    """
    log = on_event or (lambda stage, detail: None)
    client = _build_client(
        wallet_password=wallet_password,
        network=network,
        wallets_dir=wallets_dir,
        client_factory=client_factory,
    )
    trace: dict[str, Any] = {"provider": provider_address, "steps": []}

    expired_at = int(time.time()) + job_ttl_s

    # 1) create_job — opens the escrow with Helm as provider, Router as evaluator
    created = client.create_job(
        provider=provider_address,
        expired_at=expired_at,
        description=description,
    )
    job_id = created["jobId"]
    trace["job_id"] = job_id
    trace["steps"].append({"stage": "create_job", "tx": created.get("transactionHash")})
    log("create_job", {"job_id": job_id})

    # 2) register_job — bind the OptimisticPolicy on the Router for this job
    registered = client.register_job(job_id)
    trace["steps"].append(
        {"stage": "register_job", "tx": registered.get("transactionHash")}
    )
    log("register_job", {"job_id": job_id})

    # 3) set_budget + fund — escrow the payment (SDK tops up allowance via floor)
    client.set_budget(job_id, budget_raw)
    funded = client.fund(job_id, budget_raw)
    trace["steps"].append({"stage": "fund", "tx": funded.get("transactionHash")})
    log("fund", {"job_id": job_id, "budget_raw": budget_raw})

    # 4) await the deliverable — poll until SUBMITTED, then hash-verify
    deliverable = _await_deliverable(
        client, job_id, timeout_s=await_timeout_s, interval_s=poll_interval_s, log=log
    )
    trace["deliverable"] = deliverable
    trace["steps"].append({"stage": "await", **deliverable})

    # 5) settle — permissionless; releases escrow per the policy verdict
    settled = client.settle(job_id)
    trace["steps"].append({"stage": "settle", "tx": settled.get("transactionHash")})
    final_status = client.get_job_status(job_id)
    trace["final_status"] = getattr(final_status, "name", str(final_status))
    log("settle", {"job_id": job_id, "final_status": trace["final_status"]})

    return trace


def _await_deliverable(
    client: Any,
    job_id: int,
    *,
    timeout_s: int,
    interval_s: int,
    log: Any,
) -> dict[str, Any]:
    """Poll job status until SUBMITTED/COMPLETED, then fetch + hash-verify.

    Returns ``{"submitted": bool, "deliverable_url": str|None, "verified": bool}``.
    The hash-verify step re-hashes the fetched manifest against the on-chain
    ``deliverable`` bytes32 (see :func:`verify_deliverable`).
    """
    from bnbagent.erc8183.types import JobStatus

    deadline = time.time() + timeout_s
    status = client.get_job_status(job_id)
    while status not in (JobStatus.SUBMITTED, JobStatus.COMPLETED):
        if time.time() >= deadline:
            return {"submitted": False, "deliverable_url": None, "verified": False}
        if status in (JobStatus.REJECTED, JobStatus.EXPIRED):
            return {
                "submitted": False,
                "deliverable_url": None,
                "verified": False,
                "status": status.name,
            }
        log("await", {"job_id": job_id, "status": status.name})
        time.sleep(interval_s)
        status = client.get_job_status(job_id)

    url = client.get_deliverable_url(job_id)
    out: dict[str, Any] = {"submitted": True, "deliverable_url": url, "verified": False}

    # Hash-verify when we can fetch the manifest + the on-chain hash.
    try:
        on_chain_hash = bytes(client.get_job(job_id).deliverable)
        if url:
            manifest = _fetch_manifest(url)
            if manifest is not None:
                out["verified"] = verify_deliverable(manifest, on_chain_hash)
    except Exception as exc:  # noqa: BLE001 - verification is best-effort in demo
        out["verify_error"] = str(exc)
    return out


def _fetch_manifest(url: str) -> dict[str, Any] | None:
    """Fetch a deliverable manifest JSON from a file://, http(s)://, or ipfs:// URL."""
    import json
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme == "file":
        from pathlib import Path

        path = url[7:]
        return json.loads(Path(path).read_text(encoding="utf-8"))
    if parsed.scheme in ("http", "https"):
        import urllib.request

        with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310 - demo
            data = json.loads(resp.read().decode("utf-8"))
        # The agent server wraps the manifest under success; unwrap if present.
        return data.get("response") and data or data
    return None  # ipfs:// etc. left to the operator's gateway in the live demo


# ---------------------------------------------------------------------------
# Unhappy path
# ---------------------------------------------------------------------------


def dispute_and_refund(
    *,
    job_id: int,
    wallet_password: str,
    network: str = "bsc-testnet",
    wallets_dir: str | None = None,
    client_factory: Any | None = None,
    on_event: Any | None = None,
) -> dict[str, Any]:
    """Unhappy path: buyer disputes a submitted job, then claims a refund.

    Sequence: ``dispute(job_id)`` opens the dispute window; whitelisted voters
    ``vote_reject`` off-chain (operator-driven); after ``settle`` yields REJECTED
    the buyer ``claim_refund``s the escrow. If quorum is NOT reached the job
    instead EXPIRES and ``claim_refund`` recovers the escrow via the expiry path.

    Returns a trace dict. The voter quorum is on-chain machinery this function
    documents but cannot force; it issues ``dispute`` + ``claim_refund`` and
    reports the resulting status.
    """
    log = on_event or (lambda stage, detail: None)
    client = _build_client(
        wallet_password=wallet_password,
        network=network,
        wallets_dir=wallets_dir,
        client_factory=client_factory,
    )
    trace: dict[str, Any] = {"job_id": job_id, "steps": []}

    disputed = client.dispute(job_id)
    trace["steps"].append({"stage": "dispute", "tx": disputed.get("transactionHash")})
    log("dispute", {"job_id": job_id})

    # Settle reads the verdict (REJECTED if quorum voted, else after expiry).
    try:
        settled = client.settle(job_id)
        trace["steps"].append(
            {"stage": "settle", "tx": settled.get("transactionHash")}
        )
    except Exception as exc:  # noqa: BLE001 - settle may revert if window open
        trace["steps"].append({"stage": "settle", "error": str(exc)})

    refunded = client.claim_refund(job_id)
    trace["steps"].append(
        {"stage": "claim_refund", "tx": refunded.get("transactionHash")}
    )
    final_status = client.get_job_status(job_id)
    trace["final_status"] = getattr(final_status, "name", str(final_status))
    log("claim_refund", {"job_id": job_id, "final_status": trace["final_status"]})
    return trace


def cancel_open_job(
    *,
    job_id: int,
    wallet_password: str,
    network: str = "bsc-testnet",
    wallets_dir: str | None = None,
    client_factory: Any | None = None,
) -> dict[str, Any]:
    """Unhappy path: cancel a job that is still Open (never funded).

    ``cancel_open`` rejects an unfunded job — nothing was escrowed, so there is
    no refund to claim. Returns a small trace dict.
    """
    client = _build_client(
        wallet_password=wallet_password,
        network=network,
        wallets_dir=wallets_dir,
        client_factory=client_factory,
    )
    cancelled = client.cancel_open(job_id)
    status = client.get_job_status(job_id)
    return {
        "job_id": job_id,
        "tx": cancelled.get("transactionHash"),
        "final_status": getattr(status, "name", str(status)),
    }


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def _build_client(
    *,
    wallet_password: str,
    network: str,
    wallets_dir: str | None,
    client_factory: Any | None,
) -> Any:
    """Construct an ERC8183Client (buyer wallet) or call the injected factory."""
    if client_factory is not None:
        return client_factory()

    from bnbagent import ERC8183Client, EVMWalletProvider

    wallet = EVMWalletProvider(password=wallet_password, wallets_dir=wallets_dir)
    return ERC8183Client(wallet_provider=wallet, network=network)
