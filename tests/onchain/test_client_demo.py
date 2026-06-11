"""Offline tests for the ERC-8183 BUYER lifecycle (onchain/client_demo.py).

Drives the full happy-path and unhappy-path lifecycles against a SCRIPTED FAKE
``ERC8183Client`` injected at the ``client_factory`` seam — NO network, NO
wallet, NO chain. Asserts the exact call ordering (create -> register ->
set_budget -> fund -> await -> settle) and the job-status state machine, plus
the pure helpers (deliverable hash-verify, owner-address resolution).
"""

from __future__ import annotations

import pytest

from bnbagent.erc8183.schema import DeliverableManifest
from bnbagent.erc8183.types import Job, JobStatus
from onchain.client_demo import (
    cancel_open_job,
    dispute_and_refund,
    hire_helm,
    resolve_provider_address,
    verify_deliverable,
)

ZERO32 = b"\x00" * 32


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #


def _manifest(content: str = "hello") -> DeliverableManifest:
    return DeliverableManifest(
        version=1,
        job_id=1,
        chain_id=97,
        contracts={"commerce": "0xC", "router": "0xR", "policy": "0xP"},
        response={"content": content, "content_type": "application/json"},
        metadata={},
    )


def test_verify_deliverable_true_on_matching_hash():
    m = _manifest()
    assert verify_deliverable(m.to_dict(), m.manifest_hash()) is True


def test_verify_deliverable_false_on_tampered_payload():
    m = _manifest("original")
    on_chain = m.manifest_hash()
    # buyer fetches a swapped payload — hash must NOT match the on-chain commit
    tampered = _manifest("swapped").to_dict()
    assert verify_deliverable(tampered, on_chain) is False


def test_resolve_provider_address_accepts_both_owner_keys():
    assert resolve_provider_address({"owner": "0xA"}) == "0xA"
    assert resolve_provider_address({"owner_address": "0xB"}) == "0xB"


def test_resolve_provider_address_raises_without_owner():
    with pytest.raises(ValueError):
        resolve_provider_address({"name": "helm"})


# --------------------------------------------------------------------------- #
# Scripted fake ERC8183Client
# --------------------------------------------------------------------------- #


class _FakeClient:
    """Scripted ERC8183Client: records calls and walks a status timeline."""

    def __init__(self, *, status_timeline=None, deliverable_hash=ZERO32, provider="0xHELM"):
        # status_timeline: list of JobStatus values returned on successive
        # get_job_status() calls (consumed in order; last value sticks).
        self._timeline = list(status_timeline or [JobStatus.SUBMITTED])
        self._deliverable_hash = deliverable_hash
        self._provider = provider
        self.calls: list[tuple] = []
        self._job_id = 100

    # -- writes -------------------------------------------------------------
    def create_job(self, *, provider, expired_at, description):
        self.calls.append(("create_job", provider, description))
        return {"jobId": self._job_id, "transactionHash": "0xcreate"}

    def register_job(self, job_id):
        self.calls.append(("register_job", job_id))
        return {"transactionHash": "0xregister"}

    def set_budget(self, job_id, amount):
        self.calls.append(("set_budget", job_id, amount))
        return {"transactionHash": "0xbudget"}

    def fund(self, job_id, amount):
        self.calls.append(("fund", job_id, amount))
        return {"transactionHash": "0xfund"}

    def settle(self, job_id):
        self.calls.append(("settle", job_id))
        return {"transactionHash": "0xsettle"}

    def dispute(self, job_id):
        self.calls.append(("dispute", job_id))
        return {"transactionHash": "0xdispute"}

    def claim_refund(self, job_id):
        self.calls.append(("claim_refund", job_id))
        return {"transactionHash": "0xrefund"}

    def cancel_open(self, job_id):
        self.calls.append(("cancel_open", job_id))
        return {"transactionHash": "0xcancel"}

    # -- reads --------------------------------------------------------------
    def get_job_status(self, job_id):
        self.calls.append(("get_job_status", job_id))
        if len(self._timeline) > 1:
            return self._timeline.pop(0)
        return self._timeline[0]

    def get_deliverable_url(self, job_id):
        self.calls.append(("get_deliverable_url", job_id))
        return None  # demo: no fetchable URL, so verify stays False

    def get_job(self, job_id):
        return Job(
            id=job_id, client="0xBUYER", provider=self._provider, evaluator="0xR",
            description="", budget=10**18, expired_at=2**40,
            status=JobStatus.SUBMITTED, hook="0xR",
            deliverable=self._deliverable_hash, submitted_at=1,
        )


def _stages(trace):
    return [s["stage"] for s in trace["steps"]]


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #


def test_hire_helm_runs_full_lifecycle_in_order():
    fake = _FakeClient(status_timeline=[JobStatus.SUBMITTED])
    trace = hire_helm(
        provider_address="0xHELM",
        wallet_password="pw",
        budget_raw=5 * 10**18,
        client_factory=lambda: fake,
        poll_interval_s=0,
    )

    # exact write ordering of the lifecycle
    write_calls = [c[0] for c in fake.calls if c[0] != "get_job_status"]
    assert write_calls[:5] == [
        "create_job", "register_job", "set_budget", "fund", "get_deliverable_url",
    ]
    assert "settle" in write_calls

    assert trace["job_id"] == 100
    assert _stages(trace) == ["create_job", "register_job", "fund", "await", "settle"]
    # create_job got the provider; fund got the budget
    assert ("create_job", "0xHELM", "Helm regime read for BSC majors") in fake.calls
    assert ("fund", 100, 5 * 10**18) in fake.calls


def test_hire_helm_waits_through_funded_then_submitted():
    # status goes FUNDED (still working) -> SUBMITTED (deliverable ready)
    fake = _FakeClient(
        status_timeline=[JobStatus.FUNDED, JobStatus.FUNDED, JobStatus.SUBMITTED]
    )
    trace = hire_helm(
        provider_address="0xHELM",
        wallet_password="pw",
        client_factory=lambda: fake,
        poll_interval_s=0,
    )
    assert trace["deliverable"]["submitted"] is True
    # it polled status more than once before seeing SUBMITTED
    status_polls = [c for c in fake.calls if c[0] == "get_job_status"]
    assert len(status_polls) >= 3


def test_hire_helm_reports_rejected_without_submission():
    fake = _FakeClient(status_timeline=[JobStatus.REJECTED])
    trace = hire_helm(
        provider_address="0xHELM",
        wallet_password="pw",
        client_factory=lambda: fake,
        poll_interval_s=0,
    )
    assert trace["deliverable"]["submitted"] is False
    assert trace["deliverable"]["status"] == "REJECTED"


def test_hire_helm_times_out_when_never_submitted():
    fake = _FakeClient(status_timeline=[JobStatus.FUNDED])  # never advances
    trace = hire_helm(
        provider_address="0xHELM",
        wallet_password="pw",
        client_factory=lambda: fake,
        await_timeout_s=0,  # immediate timeout
        poll_interval_s=0,
    )
    assert trace["deliverable"]["submitted"] is False


def test_hire_helm_hash_verifies_when_manifest_fetchable(tmp_path, monkeypatch):
    # Provider committed a real manifest hash on-chain; buyer fetches the JSON
    # from a file:// URL and the hash-verify must succeed.
    m = _manifest("regime-read-payload")
    on_chain = m.manifest_hash()

    manifest_file = tmp_path / "deliverable.json"
    import json as _json

    manifest_file.write_text(_json.dumps(m.to_dict()), encoding="utf-8")
    file_url = manifest_file.as_uri()

    class _VerifyClient(_FakeClient):
        def get_deliverable_url(self, job_id):
            return file_url

        def get_job(self, job_id):
            job = super().get_job(job_id)
            return Job(
                id=job.id, client=job.client, provider=job.provider,
                evaluator=job.evaluator, description=job.description,
                budget=job.budget, expired_at=job.expired_at,
                status=JobStatus.SUBMITTED, hook=job.hook,
                deliverable=on_chain, submitted_at=1,
            )

    fake = _VerifyClient(status_timeline=[JobStatus.SUBMITTED])
    trace = hire_helm(
        provider_address="0xHELM",
        wallet_password="pw",
        client_factory=lambda: fake,
        poll_interval_s=0,
        # file:// deliverables are only honored inside an explicit sandbox dir
        fetch_sandbox_dir=str(tmp_path),
    )
    assert trace["deliverable"]["verified"] is True


def test_hire_helm_refuses_file_manifest_outside_sandbox(tmp_path):
    # Same setup but WITHOUT the sandbox opt-in: the buyer must refuse the
    # provider-supplied file:// URL and leave the deliverable unverified.
    m = _manifest("regime-read-payload")
    on_chain = m.manifest_hash()

    manifest_file = tmp_path / "deliverable.json"
    import json as _json

    manifest_file.write_text(_json.dumps(m.to_dict()), encoding="utf-8")
    file_url = manifest_file.as_uri()

    class _VerifyClient(_FakeClient):
        def get_deliverable_url(self, job_id):
            return file_url

        def get_job(self, job_id):
            job = super().get_job(job_id)
            return Job(
                id=job.id, client=job.client, provider=job.provider,
                evaluator=job.evaluator, description=job.description,
                budget=job.budget, expired_at=job.expired_at,
                status=JobStatus.SUBMITTED, hook=job.hook,
                deliverable=on_chain, submitted_at=1,
            )

    fake = _VerifyClient(status_timeline=[JobStatus.SUBMITTED])
    trace = hire_helm(
        provider_address="0xHELM",
        wallet_password="pw",
        client_factory=lambda: fake,
        poll_interval_s=0,
    )
    assert trace["deliverable"]["submitted"] is True
    assert trace["deliverable"]["verified"] is False


# --------------------------------------------------------------------------- #
# Unhappy paths
# --------------------------------------------------------------------------- #


def test_dispute_and_refund_calls_dispute_settle_refund():
    fake = _FakeClient(status_timeline=[JobStatus.REJECTED])
    trace = dispute_and_refund(
        job_id=100, wallet_password="pw", client_factory=lambda: fake
    )
    stages = _stages(trace)
    assert stages == ["dispute", "settle", "claim_refund"]
    assert trace["final_status"] == "REJECTED"
    assert ("dispute", 100) in fake.calls
    assert ("claim_refund", 100) in fake.calls


def test_dispute_and_refund_tolerates_settle_revert():
    class _SettleReverts(_FakeClient):
        def settle(self, job_id):
            raise RuntimeError("dispute window still open")

    fake = _SettleReverts(status_timeline=[JobStatus.EXPIRED])
    trace = dispute_and_refund(
        job_id=100, wallet_password="pw", client_factory=lambda: fake
    )
    settle_step = next(s for s in trace["steps"] if s["stage"] == "settle")
    assert "error" in settle_step
    # refund still attempted (expiry path)
    assert ("claim_refund", 100) in fake.calls
    assert trace["final_status"] == "EXPIRED"


def test_cancel_open_job_rejects_unfunded_job():
    fake = _FakeClient(status_timeline=[JobStatus.REJECTED])
    result = cancel_open_job(job_id=100, wallet_password="pw", client_factory=lambda: fake)
    assert ("cancel_open", 100) in fake.calls
    assert result["final_status"] == "REJECTED"
    assert result["tx"] == "0xcancel"
