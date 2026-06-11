"""Security tests for the buyer-side deliverable fetcher.

The deliverable URL comes from on-chain ``optParams`` — provider-controlled
input. The fetcher must not allow SSRF (private/loopback targets), arbitrary
local file reads (file:// outside an opted-in sandbox), or unbounded reads.
"""

import json

import pytest

from onchain.client_demo import (
    MAX_MANIFEST_BYTES,
    _fetch_manifest,
    _is_private_ip,
)


# --- file:// sandbox ----------------------------------------------------------

def test_file_url_rejected_without_sandbox(tmp_path):
    p = tmp_path / "m.json"
    p.write_text('{"a": 1}', encoding="utf-8")
    assert _fetch_manifest(p.as_uri()) is None


def test_file_url_inside_sandbox_is_read(tmp_path):
    p = tmp_path / "m.json"
    p.write_text('{"a": 1}', encoding="utf-8")
    out = _fetch_manifest(p.as_uri(), fetch_sandbox_dir=str(tmp_path))
    assert out == {"a": 1}


def test_file_url_escaping_sandbox_is_rejected(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside = tmp_path / "secret.json"
    outside.write_text('{"secret": true}', encoding="utf-8")
    # path traversal out of the sandbox must be refused
    assert _fetch_manifest(outside.as_uri(), fetch_sandbox_dir=str(sandbox)) is None


def test_oversize_file_rejected(tmp_path):
    p = tmp_path / "big.json"
    p.write_text('{"pad": "' + "x" * (MAX_MANIFEST_BYTES + 10) + '"}', encoding="utf-8")
    assert _fetch_manifest(p.as_uri(), fetch_sandbox_dir=str(tmp_path)) is None


# --- http(s) SSRF guard ---------------------------------------------------------

@pytest.mark.parametrize(
    "ip,expected",
    [
        ("127.0.0.1", True),
        ("10.1.2.3", True),
        ("172.16.0.9", True),
        ("192.168.1.1", True),
        ("169.254.0.5", True),
        ("::1", True),
        ("8.8.8.8", False),
        ("104.16.1.1", False),
    ],
)
def test_is_private_ip(ip, expected):
    assert _is_private_ip(ip) is expected


def test_http_to_private_host_rejected_by_default(monkeypatch):
    monkeypatch.setattr(
        "onchain.client_demo._resolve_host_ips", lambda host: ["127.0.0.1"]
    )
    assert _fetch_manifest("http://localhost:8183/m.json") is None


def test_http_to_private_host_allowed_with_opt_in(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "onchain.client_demo._resolve_host_ips", lambda host: ["127.0.0.1"]
    )
    payload = json.dumps({"ok": 1}).encode()

    class FakeResp:
        headers = {"Content-Length": str(len(payload))}
        def read(self, n=-1):
            return payload
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        "onchain.client_demo._urlopen", lambda url, timeout: FakeResp()
    )
    out = _fetch_manifest("http://localhost:8183/m.json", allow_local_http=True)
    assert out == {"ok": 1}


def test_http_oversize_content_length_rejected(monkeypatch):
    monkeypatch.setattr(
        "onchain.client_demo._resolve_host_ips", lambda host: ["8.8.8.8"]
    )

    class FakeResp:
        headers = {"Content-Length": str(MAX_MANIFEST_BYTES + 1)}
        def read(self, n=-1):
            return b"{}"
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        "onchain.client_demo._urlopen", lambda url, timeout: FakeResp()
    )
    assert _fetch_manifest("https://example.com/m.json") is None
