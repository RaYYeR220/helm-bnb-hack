# Helm execution layer (Trust Wallet Agent Kit)

The bridge from a Helm **RegimeRead** to **execution intents**, priced through
the Trust Wallet Agent Kit CLI (`twak`) — with two hard safety properties:

1. **Quotes only.** Every TWAK call carries `--quote-only` and never a
   `--password`. Nothing can be broadcast from this layer as shipped.
2. **Risk-off holds.** When Helm's gate fires (or the regime is
   `high_volatility`), the plan carries **zero intents** by construction —
   capital preservation is the action.

## What's here

- `intents.py` — pure logic: `weights_to_intents` diffs current vs target
  weights into an ordered trade list (sells first, dust-filtered);
  `regime_to_execution_plan` wraps it with regime / risk-off context.
- `twak_adapter.py` — thin subprocess wrapper over the `twak` CLI with an
  injectable runner (fully offline-testable): `quote_swap`, `quote_swap_usd`
  (USD-notional via `--usd`, matching the intents), `wallet_address`,
  `available`.
- `scripts/execution_demo.py` — the runnable demo:

```bash
uv run python scripts/execution_demo.py --offline   # canned trending read
uv run python scripts/execution_demo.py             # live read (CMC key)
```

## What was verified live (Windows, twak 0.19.0)

- `npm install -g @trustwallet/cli` → `twak --version` = 0.19.0.
- `twak chains --json` — 25 chains; BNB Smart Chain key is **`bsc`** (this CLI
  version has no `bsctestnet` entry; the testnet path described in the TWAK
  skills docs is not exposed by 0.19.0).
- `twak swap <amt> <from> <to> --chain bsc --quote-only --json` is the real
  quote command; `--usd <amount>` quotes a USD-equivalent notional.
- **Live quotes work with credentials.** With `TWAK_ACCESS_ID` +
  `TWAK_HMAC_SECRET` (from [portal.trustwallet.com](https://portal.trustwallet.com),
  loaded from `.env`), the demo fetches real PancakeSwap quotes — e.g. a
  $3,333 momentum buy returns `5.5158 WBNB -> 2473.18 CAKE` with a `minReceived`
  slippage floor. Without creds the CLI returns
  `{"error": "No API credentials found...", "errorCode": "VALIDATION_ERROR"}`
  and the demo surfaces that honestly per intent.
- **On `bsc`, Helm majors are passed as BEP-20 contract addresses.** The CLI
  resolves only a small builtin symbol set; `CAKE`/`ETH`/`LINK`/… are mapped to
  their contracts (`BSC_MAJOR_ADDRESSES`) so the quote resolves.

## The path to live execution (not enabled, deliberately)

Drop `--quote-only`, pass the wallet password, fund the agent wallet. We do
not ship that wiring: Helm is a Track 2 (Strategy Skills) entry and the point
of this layer is demonstrating the **interface** — strategy decides, TWAK
executes within guardrails — without entering the live-capital path.
