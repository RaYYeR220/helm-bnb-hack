# Helm

**A regime-switching BSC trading-strategy engine that reads the market's character before it picks a strategy — and holds cash when the trend says to.**

Most strategy bots run one mode. A momentum bot prints in trends and bleeds in
chop; a mean-reversion bot does the reverse and buys falling knives in a bear.
Helm classifies the current market regime each period from CoinMarketCap market
data fused with BSC on-chain TVL, then routes to the sub-strategy that fits —
**momentum in trends, the market portfolio in ranges, defensive in
high-volatility** — with a transparent trend-filter **risk-off gate** sitting
above the whole thing that overrides to cash on a confirmed downtrend.

Built for the BNB Hack (CoinMarketCap × Trust Wallet), **Track 2 — Strategy
Skills**, targeting the **Best Use of Agent Hub** special prize.

---

## The story in three parts

1. **Regime classification.** A 3-state Gaussian HMM over four causal,
   market-wide features (`trend_strength`, `realized_vol`, `breadth`,
   `dispersion`) labels each day `trending` / `ranging` / `high_volatility`.
   Labeling is deterministic and explainable: the highest-volatility state is
   `high_volatility`; of the rest, the one with the stronger absolute trend is
   `trending`. Every read ships with a posterior, a confidence, and a per-feature
   attribution — not a black box.
2. **On-chain TVL fusion.** BSC chain TVL and PancakeSwap share (DeFiLlama) are
   turned into three causal features (`tvl_mom20`, `tvl_dd`,
   `pancake_share_mom20`) and fused into the classifier before the HMM sees them.
   On-chain flow front-runs price on BSC; the fusion measurably improves the
   out-of-sample read.
3. **The risk-off gate.** The 3-state taxonomy can't tell an uptrend from a
   downtrend — a grinding bear reads as `ranging` and would route to
   mean-reversion, buying the knife. The gate is a textbook trend filter
   (equal-weight market index below its 50-day MA, **or** >10% off its running
   peak) that overrides the regime to **defensive** on positive evidence of a
   downtrend. This is the guardrail that kept Helm in cash through an 8-month
   bear.

---

## Headline results (validated, out-of-sample)

Walk-forward, 3 years, 8 BSC majors (ETH, XRP, ADA, LINK, DOGE, AVAX, DOT,
CAKE), out-of-sample window means:

| Variant | OOS Sharpe | Max drawdown |
| --- | ---: | ---: |
| **helm_gated_tvl** (regime + TVL fusion + risk-off gate) | **+0.57** | **−11.6%** |
| equal-weight market | — | −41.8% |

- **The risk gate held cash through an 8-month bear** — the −11.6% max drawdown
  vs the market's −41.8% is the gate doing its job, not a curve-fit.
- **Deflated Sharpe Ratio = 0.935**, computed with the true trial count (3 Helm
  variants) — i.e. the edge survives a correction for selection over the
  variants we tried.
- Bracketed by a block bootstrap and selected on walk-forward **train** windows,
  reported **out-of-sample**. No in-sample cherry-picking.

### The DQ-survival argument

Track 1 of this hackathon disqualifies any agent that breaches a **30%
drawdown cap**. We did not enter Track 1 (it requires real live capital), but the
cap is the right risk bar — and it is the cleanest way to state Helm's edge:

> **Every static baseline breaches the 30% drawdown DQ. Helm doesn't.**

The equal-weight market alone draws down −41.8%; a naive cross-sectional
mean-reversion bled ~−42% in the Aug–Oct 2025 top. Helm's gated variant tops out
at −11.6%. The point of regime-switching isn't a flashier return — it's
surviving the regime that kills single-mode bots.

---

## Architecture

```
                         ┌─────────────────────────────────────────┐
   CoinMarketCap  ──────▶│  Data layer (cache-first, parquet)       │
   (OHLCV, market)       │   helm/data: cmc, cache, universe        │
                         │                                          │
   DeFiLlama TVL  ──────▶│   onchain_cache  ─▶ build_onchain_features│
   GeckoTerminal  ──────▶│   (BSC TVL, PancakeSwap share, DEX vol)  │
   (DEX volume)          └───────────────────┬──────────────────────┘
                                             │  close-price panel + TVL features
                                             ▼
                         ┌─────────────────────────────────────────┐
                         │  Regime layer  (helm/regime)             │
                         │   features ─▶ HMM (3-state, 8 restarts)  │
                         │   ─▶ RegimeRead {label, posterior,       │
                         │        confidence, attribution}          │
                         └───────────────────┬──────────────────────┘
                                             │  causal walk-forward regime path
                                             ▼
                         ┌─────────────────────────────────────────┐
   market_risk_off ─────▶│  Router  (helm/router) + risk gate       │
   (50d-MA / 10% DD)     │   trending  ─▶ CrossSectionalMomentum    │
                         │   ranging   ─▶ EqualWeight (market port.) │
                         │   high_vol  ─▶ Defensive                 │
                         │   RISK-OFF  ─▶ override to Defensive     │
                         │   (hysteresis=3 to avoid whipsaw)        │
                         └───────────────────┬──────────────────────┘
                                             ▼
                         ┌─────────────────────────────────────────┐
                         │  Backtest + validation                   │
                         │   engine, metrics, regime P&L attribution│
                         │   walk-forward windows, deflated Sharpe, │
                         │   block bootstrap CIs                    │
                         └─────────────────────────────────────────┘
                                             │
                                             ▼
                         ┌─────────────────────────────────────────┐
                         │  CMC Agent Hub Skill  (skill/)           │
                         │   helm-regime-read ─▶ any LLM agent on   │
                         │   the cmc-mcp server                     │
                         └─────────────────────────────────────────┘
```

---

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
# 1. install
uv sync

# 2. configure — put your CoinMarketCap Pro key in .env
echo "CMC_API_KEY=your-api-key" > .env       # key from https://pro.coinmarketcap.com/login

# 3. run the pipeline (each script is cache-first and human-run)
uv run python scripts/smoke_backtest.py       # pull CMC OHLCV, momentum backtest, sanity check
uv run python scripts/regime_backtest.py      # Helm vs baselines + regime P&L attribution
uv run python scripts/onchain_backfill.py     # backfill BSC TVL + per-token DEX volume (cache)
uv run python scripts/onchain_validation.py   # walk-forward OOS: helm_gated_tvl vs market, DSR

# live regime read (the skill's Full mode)
uv run python scripts/helm_read.py            # human-readable RegimeRead
uv run python scripts/helm_read.py --json     # machine-readable JSON
```

Artifacts (equity curves, metrics, regime paths) are written to `data_cache/`.

---

## The Agent Hub Skill

`skill/helm-regime-read/` is a CoinMarketCap Agent Hub skill that exposes Helm's
regime read to **any LLM agent connected to the CMC MCP server** — no local
install needed for the live read. It follows the official
[skills-for-ai-agents-by-CoinMarketCap](https://github.com/openCMC/skills-for-ai-agents-by-CoinMarketCap)
format (YAML frontmatter, trigger lines, numbered workflow, per-tool failure
handling) and references only real `cmc-mcp` tools.

- **Live mode (MCP-only):** the agent pulls live data (global metrics, marketcap
  technicals, the BSC-majors cross-section, derivatives) and applies Helm's
  transparent regime heuristics — the documented 50d-MA / 10%-drawdown risk-off
  gate and the feature signatures — to produce a structured RegimeRead.
- **Full mode (local engine):** if the user has this repo, the skill defers to
  `scripts/helm_read.py` for the exact HMM-based read.

**Install — connect the CMC MCP server, then drop in the skill:**

```bash
# 1. wire up the CoinMarketCap MCP server (one-liner from the official docs)
claude mcp add cmc-mcp --transport http --url https://mcp.coinmarketcap.com/mcp \
  --header "X-CMC-MCP-API-KEY: your-api-key"

# 2. install the skill (copy into your agent's skills directory)
cp -r skill/helm-regime-read ~/.claude/skills/
```

Then trigger it: *"what regime is the market in"*, *"should I be defensive right
now"*, or `/helm-regime-read`.

---

## Test suite

```bash
uv run pytest          # 171 tests, fully green
```

Everything is unit-tested and **no test makes a live network call** — the
human-run scripts hit the API; the tests import-check them and exercise the pure
helpers offline. The validation modules (walk-forward windows, deflated Sharpe,
block bootstrap) are independently tested.

---

## Honest limitations

We'd rather state these than have a judge find them:

- **DEX-volume depth is ~182 days.** The free GeckoTerminal tier caps per-token
  daily candles at 182. On panel dates older than that, the on-chain-confirmed
  momentum variant degrades gracefully to plain momentum (keep-if-no-data
  fallback). TVL history (DeFiLlama) is deep; per-token DEX volume is not.
- **A flash-crash tail day exists in the sample.** Single-day extreme moves are
  in the data; Helm's defensive/risk-off stance mitigates but does not erase
  tail-day P&L. The reported drawdowns include it.
- **Market-data-only regime reads are weaker pre-fusion.** Without the on-chain
  TVL features, the bare 3-state HMM is less able to separate a grinding bear
  from a true range — which is exactly why the risk-off gate is a separate,
  hard-coded trend filter rather than something we ask the HMM to learn. The TVL
  fusion sharpens the read; the gate is the safety net that doesn't depend on it.
- **8-major universe for the headline numbers.** The full BEP-20 universe ships
  in `helm/data/universe_bsc_149.json`; the validated headline run uses the
  liquid, data-rich 8-major subset for clean OHLCV coverage.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Built for BNB Hack

Helm is a **Track 2 (Strategy Skills)** entry targeting the **Best Use of Agent
Hub** special prize. The three sponsor-SDK touchpoints:

- **CoinMarketCap Agent Hub — deep.** Live market data through the CMC MCP server
  *and* a native, format-correct Agent Hub Skill (`skill/helm-regime-read`) that
  composes Helm into any MCP-connected agent.
- **BNB AI Agent SDK — next layer.** The agent-runtime + BSC integration wrapping
  the engine for autonomous operation.
- **Trust Wallet Agent Kit (TWAK) — next layer.** Self-custody (paper/sim)
  execution to demonstrate the live path without entering the live-capital track.

*This is research tooling, not financial advice.*
