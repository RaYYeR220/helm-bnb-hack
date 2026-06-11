"""ERC-8004 identity for Helm — discovery card + registration.

Two responsibilities:

- :func:`build_agent_uri` — construct the EIP-8004 registration file (the
  agent's discovery card) as a base64 ``data:`` URI. Pure / network-free; it
  reuses the SDK's ``AgentURIGenerator`` so the on-chain bytes are byte-identical
  to what ``ERC8004Agent.generate_agent_uri`` would produce, but without needing
  a live RPC connection (handy for tests and for offline inspection).
- :func:`register_helm_agent` — connect to BSC, build the URI, and register Helm
  in the on-chain Identity Registry. **Idempotent**: if this wallet already owns
  an agent with Helm's name, it reports the existing ``agent_id`` instead of
  registering a duplicate.

The discovery card advertises one ``AgentEndpoint`` named ``"ERC8183"`` pointing
at the job server's base URL (where buyers negotiate + fetch deliverables) plus
a human-facing ``"web"`` endpoint. Registration is gas-free on BSC via the SDK's
MegaFuel paymaster, so no tBNB is required for the identity step.
"""

from __future__ import annotations

from typing import Any

# Helm's stable discovery identity. Kept here (not in regime_service) so the URI
# builder has no dependency on the provider loop; regime_service re-exports them.
from onchain.regime_service import HELM_AGENT_DESCRIPTION, HELM_AGENT_NAME

# Default discovery endpoints baked into the registration card. The ERC8183
# endpoint is where buyers reach the job server (negotiate / job / response).
DEFAULT_ERC8183_ENDPOINT = "https://helm-agent.example/erc8183"
DEFAULT_WEB_ENDPOINT = "https://helm-agent.example/"
HELM_AGENT_VERSION = "1"

# Chain id for BSC testnet — only used to stamp the registrations field when an
# agent_id is supplied. Matches bnbagent's NETWORKS["bsc-testnet"].chain_id.
_BSC_TESTNET_CHAIN_ID = 97


def build_agent_uri(
    *,
    erc8183_endpoint: str = DEFAULT_ERC8183_ENDPOINT,
    web_endpoint: str = DEFAULT_WEB_ENDPOINT,
    name: str = HELM_AGENT_NAME,
    description: str = HELM_AGENT_DESCRIPTION,
    version: str = HELM_AGENT_VERSION,
    agent_id: int | None = None,
    chain_id: int = _BSC_TESTNET_CHAIN_ID,
    identity_registry: str | None = None,
) -> str:
    """Build Helm's ERC-8004 agent URI (a base64 ``data:application/json`` URI).

    Pure / network-free. Delegates to the SDK's ``AgentURIGenerator`` so the
    bytes match what an on-chain registration would store. The two endpoints
    are the discovery surface other agents use to find and hire Helm:

    - ``ERC8183`` → the job server (where the commerce lifecycle happens),
    - ``web``     → a human-facing landing page.

    When ``agent_id`` is provided, the SDK stamps the ``registrations`` field
    (``eip155:<chain_id>:<registry>``) so the card is self-describing — this is
    the form re-uploaded after a successful on-chain registration.
    """
    # Imported lazily: keeps ``import onchain`` working without the agent group,
    # and keeps the SDK's web3 import cost out of the core test suite.
    from bnbagent import AgentEndpoint
    from bnbagent.erc8004.agent_uri import AgentURIGenerator

    endpoints = [
        AgentEndpoint(name="ERC8183", endpoint=erc8183_endpoint, version=version),
        AgentEndpoint(name="web", endpoint=web_endpoint, version=version),
    ]
    return AgentURIGenerator.generate_agent_uri(
        name=name,
        description=description,
        endpoints=endpoints,
        agent_id=agent_id,
        identity_registry=identity_registry,
        chain_id=chain_id if agent_id is not None else None,
    )


def register_helm_agent(
    wallet_password: str,
    *,
    network: str = "bsc-testnet",
    erc8183_endpoint: str = DEFAULT_ERC8183_ENDPOINT,
    web_endpoint: str = DEFAULT_WEB_ENDPOINT,
    wallets_dir: str | None = None,
    agent_factory: Any | None = None,
) -> dict[str, Any]:
    """Register Helm as an ERC-8004 agent on ``network`` (idempotent).

    Lifecycle:

    1. Load/create the Helm wallet from the keystore (encrypted; password via
       ``wallet_password``, never logged). A fresh wallet is auto-generated on
       first run and saved under ``wallets_dir``.
    2. Connect to BSC through ``ERC8004Agent`` (verifies the RPC chain id).
    3. **Idempotency check** — if this wallet already owns an agent named
       :data:`HELM_AGENT_NAME`, return that record with ``"status": "exists"``
       instead of registering a duplicate.
    4. Otherwise build the discovery URI and call ``register_agent`` (gas-free
       via MegaFuel) and return ``"status": "registered"`` with the tx hash and
       assigned ``agent_id``.

    Returns a JSON-ready dict::

        {"status": "registered"|"exists", "agent_id": int|None,
         "address": "0x...", "tx_hash": "0x..."|None, "agent_uri": "data:...",
         "network": "bsc-testnet"}

    Parameters
    ----------
    agent_factory:
        Test seam. A zero-arg callable returning an object with the
        ``ERC8004Agent`` surface used here (``wallet_address``,
        ``get_local_agent_info``, ``generate_agent_uri``, ``register_agent``,
        ``contract_address``). Defaults to building a real ``ERC8004Agent``.
    """
    agent = _build_agent(
        wallet_password=wallet_password,
        network=network,
        wallets_dir=wallets_dir,
        agent_factory=agent_factory,
    )

    address = agent.wallet_address

    # --- idempotency: don't re-register a name this wallet already owns -------
    existing = agent.get_local_agent_info(HELM_AGENT_NAME)
    if existing is not None:
        return {
            "status": "exists",
            "agent_id": existing.get("agent_id"),
            "address": address,
            "tx_hash": None,
            "agent_uri": existing.get("agent_uri", ""),
            "network": network,
        }

    # --- register fresh -------------------------------------------------------
    agent_uri = agent.generate_agent_uri(
        name=HELM_AGENT_NAME,
        description=HELM_AGENT_DESCRIPTION,
        endpoints=_discovery_endpoints(erc8183_endpoint, web_endpoint),
    )
    result = agent.register_agent(agent_uri=agent_uri)
    return {
        "status": "registered",
        "agent_id": result.get("agentId"),
        "address": address,
        "tx_hash": result.get("transactionHash"),
        "agent_uri": result.get("agentURI", agent_uri),
        "network": network,
    }


def _discovery_endpoints(erc8183_endpoint: str, web_endpoint: str) -> list:
    """Build the AgentEndpoint discovery list (lazy SDK import)."""
    from bnbagent import AgentEndpoint

    return [
        AgentEndpoint(
            name="ERC8183", endpoint=erc8183_endpoint, version=HELM_AGENT_VERSION
        ),
        AgentEndpoint(name="web", endpoint=web_endpoint, version=HELM_AGENT_VERSION),
    ]


def _build_agent(
    *,
    wallet_password: str,
    network: str,
    wallets_dir: str | None,
    agent_factory: Any | None,
) -> Any:
    """Construct an ERC8004Agent (or call the injected factory for tests)."""
    if agent_factory is not None:
        return agent_factory()

    from bnbagent import ERC8004Agent, EVMWalletProvider

    wallet = EVMWalletProvider(password=wallet_password, wallets_dir=wallets_dir)
    return ERC8004Agent(wallet_provider=wallet, network=network)
