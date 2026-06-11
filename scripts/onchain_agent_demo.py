"""Orchestrator for Helm's on-chain agent (deliverable E3) — three modes.

Helm wrapped as a discoverable, hireable ERC-8004 / ERC-8183 agent on BSC.

    # 1) Register Helm in the ERC-8004 Identity Registry (gas-free via MegaFuel)
    uv run python scripts/onchain_agent_demo.py --register

    # 2) Run the PROVIDER loop: serve Helm as an ERC-8183 job server
    uv run python scripts/onchain_agent_demo.py --serve --port 8003 \
        --agent-url http://localhost:8003/erc8183

    # 3) Run the BUYER demo: hire the served Helm agent for a regime read
    uv run python scripts/onchain_agent_demo.py --hire --agent-id 42

Env (see .env.example):
    HELM_AGENT_WALLET_PASSWORD   keystore password (REQUIRED; never logged)
    HELM_KEYSTORE_DIR            keystore directory (default data_cache/keystore)

This script is human-run and hits the live chain. The unit tests only
import-check it and exercise the pure helpers in ``onchain/`` with fakes — no
network. Private keys live only in the gitignored keystore; nothing here prints
or commits a secret.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()  # keystore password (HELM_AGENT_WALLET_PASSWORD) comes from .env

# Keystore lives under the gitignored data_cache/ tree by default.
DEFAULT_KEYSTORE_DIR = os.path.join("data_cache", "keystore")


def _password() -> str:
    pw = os.environ.get("HELM_AGENT_WALLET_PASSWORD")
    if not pw:
        sys.exit(
            "Set HELM_AGENT_WALLET_PASSWORD (keystore password). "
            "See .env.example. It is never logged or committed."
        )
    return pw


def _keystore_dir() -> str:
    d = os.environ.get("HELM_KEYSTORE_DIR", DEFAULT_KEYSTORE_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def _print_event(stage: str, detail: dict) -> None:
    print(f"  [{stage}] {json.dumps(detail, default=str)}")


def cmd_register(args: argparse.Namespace) -> None:
    from onchain.identity import register_helm_agent

    print(f"Registering Helm on {args.network} (ERC-8004, gas-free via MegaFuel)...")
    result = register_helm_agent(
        _password(),
        network=args.network,
        erc8183_endpoint=args.agent_url or "https://helm-agent.example/erc8183",
        wallets_dir=_keystore_dir(),
    )
    print(json.dumps(result, indent=2, default=str))
    if result["status"] == "registered":
        print(f"\nHelm registered: agent_id={result['agent_id']} tx={result['tx_hash']}")
    else:
        print(f"\nHelm already registered: agent_id={result['agent_id']} (idempotent)")


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    from onchain.regime_service import build_provider_app

    agent_url = args.agent_url or f"http://localhost:{args.port}/erc8183"
    print(f"Serving Helm as an ERC-8183 provider on :{args.port}  (agent_url={agent_url})")
    print("The SDK funded-job poll loop will run Helm's regime read per funded job.")
    app = build_provider_app(
        _password(),
        network=args.network,
        service_price=args.service_price,
        agent_url=agent_url,
        storage_base_dir=args.storage_dir,
    )
    uvicorn.run(app, host="0.0.0.0", port=args.port)


def cmd_hire(args: argparse.Namespace) -> None:
    from onchain.client_demo import discover_helm, hire_helm

    pw = _password()
    ks = _keystore_dir()

    print(f"Discovering Helm agent_id={args.agent_id} on {args.network}...")
    card = discover_helm(
        args.agent_id,
        network=args.network,
        wallet_password=pw,
        wallets_dir=ks,
    )
    print(json.dumps(card, indent=2, default=str))

    print("\nHiring Helm (create -> register -> fund -> await -> settle)...")
    trace = hire_helm(
        provider_address=card["provider_address"],
        wallet_password=pw,
        network=args.network,
        budget_raw=args.budget,
        wallets_dir=ks,
        on_event=_print_event,
        # same-machine demo opt-ins for the deliverable fetcher: file:// reads
        # are sandboxed to the provider's storage dir; localhost http allowed
        # only when explicitly flagged.
        fetch_sandbox_dir=args.storage_dir,
        allow_local_http=args.allow_local_fetch,
    )
    print("\n=== Lifecycle trace ===")
    print(json.dumps(trace, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Helm on-chain agent demo (E3)")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--register", action="store_true", help="register Helm (ERC-8004)")
    mode.add_argument("--serve", action="store_true", help="run the provider loop (ERC-8183)")
    mode.add_argument("--hire", action="store_true", help="run the buyer demo")

    p.add_argument("--network", default="bsc-testnet")
    p.add_argument("--agent-url", default=None, help="public base URL of the job server")
    p.add_argument("--port", type=int, default=8003)
    p.add_argument("--service-price", type=int, default=0, help="min budget floor (raw units)")
    p.add_argument("--storage-dir", default=None, help="deliverable storage dir")
    p.add_argument("--agent-id", type=int, default=None, help="Helm's ERC-8004 agent id (hire)")
    p.add_argument("--budget", type=int, default=10**18, help="escrow budget in raw token units")
    p.add_argument(
        "--allow-local-fetch",
        action="store_true",
        help="allow the buyer to fetch deliverables from localhost/private hosts "
        "(same-machine demo only; off by default)",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.register:
        cmd_register(args)
    elif args.serve:
        cmd_serve(args)
    elif args.hire:
        if args.agent_id is None:
            sys.exit("--hire requires --agent-id (Helm's ERC-8004 agent id)")
        cmd_hire(args)


if __name__ == "__main__":
    main()
