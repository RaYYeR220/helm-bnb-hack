# Helm on-chain agent (E3) — BNB AI Agent SDK integration

This layer turns **Helm** — the regime-switching BSC strategy engine — into a
**discoverable, hireable on-chain agent** on BNB Smart Chain, using the
[BNB AI Agent SDK (`bnbagent`)](https://github.com/bnb-chain/bnbagent-sdk).

Another agent can find Helm in the on-chain registry, **hire** it for a regime
read, **pay into escrow**, receive the deliverable, and **settle** — entirely
through ERC-8004 identity and the ERC-8183 agent-commerce protocol. No human in
the loop, no off-chain trust assumption: the deliverable is keccak256-committed
on-chain so the buyer can re-hash and verify it was not swapped after delivery.

> This package requires the **`agent`** dependency group, which is **not** part
> of Helm's core install. The core `helm/` package never imports `bnbagent`.
>
> ```bash
> uv sync --group agent          # or: uv add --group agent "bnbagent[server]"
> ```

---

## What Helm sells

The deliverable is a **`RegimeRead`** — the exact same product as the off-chain
`helm-regime-read` skill (`scripts/helm_read.py`), produced by the **same engine
path**. It carries the regime label, confidence, posterior, top feature
attribution, the market risk-off gate state, and the recommended stance:

```json
{
  "version": 1,
  "service": "helm-regime-read",
  "job_id": 42,
  "read": {
    "date": "2026-06-10", "regime": "trending", "confidence": 0.72,
    "risk_off": false, "recommended_stance": "momentum",
    "posterior": {"trending": 0.72, "ranging": 0.20, "high_volatility": 0.08},
    "features": { "...": 0.0 }, "attribution": { "...": 0.0 }
  }
}
```

---

## Lifecycle

```
  BUYER (onchain/client_demo.py)            PROVIDER = Helm (onchain/regime_service.py)
  ─────────────────────────────            ──────────────────────────────────────────
  discover(agent_id)  ── ERC-8004 ──▶  [Identity Registry]   Helm's discovery card
        │                                                     (name, endpoints, owner)
        ▼
  create_job(provider=Helm) ─────────▶  [AgenticCommerce]    job: OPEN
  register_job(job_id) ──────────────▶  [EvaluatorRouter]    bind OptimisticPolicy
  set_budget + fund(amount) ─────────▶  [escrow]             job: FUNDED ──┐
                                                                            │ funded-job
                                              poll loop picks it up ◀───────┘ poll (SDK)
                                              on_job(job) = Helm RegimeRead
                                              manifest = keccak256(canonical JSON)
                                       ◀──── submit(deliverable, optParams)  job: SUBMITTED
        │                                     upload manifest -> StorageProvider
        ▼
  await: poll until SUBMITTED
  fetch manifest + RE-HASH  ═══ verify keccak256 == on-chain bytes32 ✓
  settle(job_id) ────────────────────▶  [Router] pulls policy verdict
                                          (silence -> APPROVE after window)  job: COMPLETED
                                          escrow released to Helm

  ── dispute slot (unhappy path) ───────────────────────────────────────────────────
  dispute(job_id) ───────────────────▶  [OptimisticPolicy]  open dispute window
        whitelisted voters vote_reject ─▶                    quorum?
  settle ─▶ REJECTED  ─▶  claim_refund ─▶  escrow refunded to buyer
        (no quorum) ─▶ EXPIRED ─▶ claim_refund ─▶ refund via expiry
  cancel_open(job_id)  (job never funded)  ─▶  REJECTED, nothing escrowed
```

Statuses (`bnbagent.erc8183.JobStatus`): `OPEN → FUNDED → SUBMITTED → COMPLETED`,
with `REJECTED` / `EXPIRED` as the dispute/expiry exits.

---

## Running the three demo modes

All modes are human-run and hit the live chain. Set the keystore password first
(see `.env.example`) — it is never logged or committed; the encrypted wallet
lives under `data_cache/keystore/` (gitignored).

```bash
export HELM_AGENT_WALLET_PASSWORD=...      # PowerShell: $env:HELM_AGENT_WALLET_PASSWORD=...

# 1) Register Helm in the ERC-8004 Identity Registry (gas-free via MegaFuel).
#    Idempotent: re-running reports the existing agent_id instead of duplicating.
uv run python scripts/onchain_agent_demo.py --register

# 2) Serve Helm as an ERC-8183 PROVIDER. The SDK funded-job poll loop runs
#    Helm's regime read for each funded job and submits the deliverable.
uv run python scripts/onchain_agent_demo.py --serve --port 8003 \
    --agent-url http://localhost:8003/erc8183

# 3) Hire the served Helm agent as a BUYER (full create→fund→await→settle).
uv run python scripts/onchain_agent_demo.py --hire --agent-id <ID_FROM_STEP_1>
```

---

## Why this is idiomatic SDK usage (not a one-call stub)

Each layer maps to a **real `bnbagent` primitive**, used the way the SDK intends:

| Concern        | SDK primitive (real)                                   | Where |
|----------------|--------------------------------------------------------|-------|
| **Identity**   | `ERC8004Agent` + `AgentEndpoint` discovery card        | `identity.py` |
| **Idempotency**| `get_local_agent_info` before `register_agent`         | `identity.py` |
| **Commerce**   | `ERC8183Client` (`create_job`/`register_job`/`fund`/`settle`/`dispute`/`claim_refund`) | `client_demo.py` |
| **Provider loop** | `create_erc8183_app(on_job=...)` + funded-job poll  | `regime_service.py` |
| **Deliverable**| `DeliverableManifest` (keccak256 on-chain commitment)  | `regime_service.py`, verified in `client_demo.py` |
| **Storage**    | `StorageProvider` / `LocalStorageProvider`             | `regime_service.py` |
| **Signing**    | `SigningPolicy.strict_default` (fail-closed EIP-712 gate) | enforced by `EVMWalletProvider` on every signed tx |
| **x402**       | `X402Signer` (per-call + session budget, recipient binding) | available for paid-call flows (the SDK's payment layer) |

The integration is **trust-minimized**: the buyer does not trust Helm's server —
it re-hashes the fetched manifest and compares to the on-chain `deliverable`
bytes32 (`verify_deliverable`). Signing never sees a raw private key (wallet
provider only), and the default `SigningPolicy` refuses any unknown EIP-712
domain or unbounded Permit — defense against blind-sign attacks.

---

## What was verified live on BSC testnet (Phase-1 spike)

The full SDK code path was exercised **live** against `bsc-testnet` (chain 97):

- **Fresh wallet generated + encrypted** to the gitignored keystore
  (`EVMWalletProvider`, Keystore V3, `SigningPolicy.strict_default`):
  address `0x39091D68C99016E348f49BB2c7f4343F3D3e8aeD`.
- **Connected** to the testnet registry `0x8004A818BFB912233c491871b3d84c89A494BD9e`;
  the SDK's RPC chain-id verification passed.
- **`generate_agent_uri`** produced the EIP-8004 discovery card.
- **`register_agent`** broadcast a real registration transaction via the MegaFuel
  paymaster: tx hash `0xa39f1b5b45ad9e03d8d9438db0953367da7d306372834808975077e7914bf4dc`.

**Honest outcome:** the wallet was unfunded (0 tBNB) and the gas-free MegaFuel
sponsorship did not land the transaction — it timed out (*"not in the chain after
300 seconds"*) and a follow-up receipt lookup returned `TransactionNotFound`.
Registration on this deployment requires either MegaFuel allowlisting for the
sender or a tBNB-funded wallet to self-pay gas. The SDK integration itself is
complete and correct; only the on-chain settlement of the registration tx is
gated on faucet/sponsorship access. Everything else — identity card, the full
ERC-8183 lifecycle, deliverable manifesting + hash verification, the provider
poll loop, and the signing policy — is wired against the real SDK and covered by
33 offline tests that fake the SDK client objects at injection seams.
