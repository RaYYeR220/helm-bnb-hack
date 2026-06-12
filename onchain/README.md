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

## Verified live on BSC testnet — Helm is a registered on-chain agent

Helm is **registered and confirmed on-chain** on `bsc-testnet` (chain 97):

| | |
| --- | --- |
| **Agent ID** | **1368** |
| **Agent wallet** | `0xf90635d961B53Aa2E1314d05baBd95525aee51fA` |
| **Registration tx** | `0x573cedf22fe0ad3680ac4ca1df778b3c48c0922d47c035ff7606877d753d1625` |
| **Receipt** | status `1` (success), block `112821096` |
| **Identity Registry** | `0x8004A818BFB912233c491871b3d84c89A494BD9e` (EIP-8004) |

Verify it yourself:

```bash
# the registration receipt (status 0x1)
curl -s https://data-seed-prebsc-1-s1.bnbchain.org:8545 -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_getTransactionReceipt","params":["0x573cedf22fe0ad3680ac4ca1df778b3c48c0922d47c035ff7606877d753d1625"]}'
# or on the explorer
# https://testnet.bscscan.com/tx/0x573cedf22fe0ad3680ac4ca1df778b3c48c0922d47c035ff7606877d753d1625
```

What ran, live:

- **Fresh wallet** generated + encrypted to the gitignored keystore
  (`EVMWalletProvider`, Keystore V3, `SigningPolicy.strict_default`).
- **`generate_agent_uri`** produced the EIP-8004 discovery card (base64 `data:`
  URI with the ERC-8183 service endpoint), embedded in the on-chain registration.
- **`register_agent`** broadcast and **landed gas-free via the MegaFuel
  paymaster** — the wallet paid nothing; the tx is final at block 112821096.
- **Idempotent**: re-running `--register` reports the existing `agent_id=1368`
  via `get_local_agent_info` instead of duplicating.

The ERC-8183 commerce loop (`create_job` → `fund` → `submit` → `settle` /
`dispute` / `claim_refund`), deliverable manifesting + keccak hash verification,
the provider poll loop, the `LocalStorageProvider`, and the strict `SigningPolicy`
are all wired against the real SDK and covered by **33 offline tests** that fake
the SDK client at injection seams.

### Live escrow round-trip — verified up to the token gate

Running `--serve` + `--hire` live against the testnet contracts gets this far,
honestly:

- The provider boots (uvicorn + the SDK funded-job poll loop). ✓
- `create_job` **lands on-chain** — unlike registration, the ERC-8183 commerce
  ops are *not* MegaFuel-sponsored, so this needs a little tBNB for gas (the
  wallet was funded with 0.02 tBNB; the job is created). ✓
- `set_budget` then reverts with `ZeroBudget()` — the escrow **requires a
  positive budget in the payment token `U`** (`0xc70B8741…5565`, an immutable
  `MinimalERC20` on the commerce kernel). `U` has **no public faucet/mint** on
  this testnet deployment, so a non-zero, fundable budget needs `U` from the
  program's distributor. Until then, `fund` → `submit` → `settle` are exercised
  only in the offline tests.

So: identity is **live on-chain** (agent 1368), job creation is **live on-chain**,
and the funded settlement is gated solely on obtaining the `U` test token — not
on any missing integration. Fund the wallet with `U` and the same `--hire` run
completes the create → fund → submit → settle → keccak-verify loop end to end.
