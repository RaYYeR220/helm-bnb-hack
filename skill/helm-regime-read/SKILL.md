---
name: helm-regime-read
description: |
  Reads the current BSC market regime through Helm's regime classifier and recommends the active sub-strategy.
  Use when the user asks what regime the market is in, whether to be defensive, or which stance Helm would take right now. This applies Helm's transparent regime heuristics (trend-filter risk-off gate + feature signatures) on top of live CoinMarketCap data to produce a structured RegimeRead: regime label, confidence, feature attribution, recommended stance, and the risk-off override.
  Trigger: "what regime is the market in", "should I be defensive right now", "what would Helm do", "is the market risk-off", "BSC market regime", "which stance should I take", "/helm-regime-read"
license: MIT
compatibility: ">=1.0.0"
user-invocable: true
allowed-tools:
  - mcp__cmc-mcp__search_cryptos
  - mcp__cmc-mcp__get_global_metrics_latest
  - mcp__cmc-mcp__get_crypto_marketcap_technical_analysis
  - mcp__cmc-mcp__get_crypto_quotes_latest
  - mcp__cmc-mcp__get_crypto_technical_analysis
  - mcp__cmc-mcp__get_global_crypto_derivatives_metrics
---

# Helm Regime Read Skill

Helm is a regime-switching BSC trading-strategy engine. It fuses CoinMarketCap
market data with on-chain TVL, classifies the market into one of three regimes
(`trending` / `ranging` / `high_volatility`) with an HMM, applies a transparent
trend-filter risk-off gate, and routes to the matching sub-strategy.

This skill exposes Helm's regime read to any agent connected to the CMC MCP
server. It produces a **RegimeRead** — regime + confidence + feature attribution
+ recommended stance + risk-off override — using live CMC data and Helm's
documented heuristics. No local install required for the **Live mode** below.

## Prerequisites

Before reading the regime, verify the CMC MCP tools are available. If tools fail
or return connection errors, ask the user to set up the MCP connection:

```json
{
  "mcpServers": {
    "cmc-mcp": {
      "url": "https://mcp.coinmarketcap.com/mcp",
      "headers": {
        "X-CMC-MCP-API-KEY": "your-api-key"
      }
    }
  }
}
```

Get your API key from https://pro.coinmarketcap.com/login

## Core Principle

A regime is not a price call — it is a description of the current return-generating
environment, made BEFORE choosing a strategy. Fetch the market-wide signals first
(trend, breadth, volatility), classify, then let the regime pick the stance.
Surface the feature attribution so the call is auditable, and always check the
risk-off override last: a grinding downtrend can read as `ranging` and must not be
allowed to route into a mean-reversion "buy the dip" — the trend filter overrides.

## The Helm taxonomy (what each regime means)

- **trending** — a directional market with a persistent signed drift. Stance:
  **momentum** (Helm runs cross-sectional momentum: long the top movers).
- **ranging** — no informative directional edge. Stance: **market portfolio**
  (equal-weight broad exposure — when the regime is uninformative the neutral
  stance is breadth, not a concentrated active bet).
- **high_volatility** — elevated realized vol / unstable cross-section. Stance:
  **defensive** (de-risk: cut gross, hold cash/stable weight).

On top of the three regimes sits the **risk-off gate** (a market-level trend
filter). When it fires, it overrides the regime stance to **defensive**,
regardless of what the HMM said. This is the guardrail that kept Helm in cash
through an 8-month bear in out-of-sample testing.

## Helm's regime features (compute these from live data)

Helm classifies on four causal, market-wide features (every value at date *t*
uses only data through *t*). The HMM's labeling rule keys off two of them, so you
can reproduce the read directionally without the model:

| Feature | Meaning | Drives |
| --- | --- | --- |
| `trend_strength` | 20-day (mean / std) of equal-weight market-index daily returns — a signed Sharpe-like drift measure | high \|trend_strength\| → **trending** |
| `realized_vol` | 20-day std of market-index daily returns | highest `realized_vol` → **high_volatility** |
| `breadth` | fraction of names whose trailing 20-day cumulative return is > 0 | confirms direction / participation |
| `dispersion` | cross-sectional std (across names) of the trailing 20-day cumulative return | confirms a stable vs. fractured cross-section |

HMM labeling rule (deterministic): the state with the **highest mean standardized
`realized_vol`** is `high_volatility`; of the remaining two, the one with the
**higher mean |standardized `trend_strength`|** is `trending`, the other is
`ranging`. Use the live signals to infer which state today resembles.

## The risk-off gate (transparent thresholds — these are the real ones)

The gate fires (market is risk-off → force **defensive**) if EITHER:

1. **Drawdown gate** — the equal-weight market index is more than **10% below its
   running peak** (`dd_threshold = 0.10`), OR
2. **Trend gate** — the index sits **below its 50-day simple moving average**
   (`ma_window = 50`), provided at least 50 index observations exist.

With no computable signal the gate returns **False** — it only fires on positive
evidence of a downtrend. The drawdown leg is checked first.

## Regime-read workflow (Live mode, MCP-only)

### Step 1: Market-wide health and sentiment

Call `get_global_metrics_latest` to get:
- Total market cap and 24h/7d/30d changes (proxy for index drift / drawdown)
- **Fear & Greed Index** (Extreme Fear ↔ Extreme Greed)
- BTC / ETH dominance and **Altcoin Season Index** (breadth proxy)
- Total volume

Map these to Helm's features: sustained negative 7d/30d change + falling from a
recent peak → trend/drawdown risk-off pressure. Extreme Greed with a strong
positive 30d change → `trending` candidate. Flat changes + neutral Fear & Greed →
`ranging` candidate.

### Step 2: Market technical structure (the trend gate)

Call `get_crypto_marketcap_technical_analysis` to get total-market-cap moving
averages, RSI, and MACD. This is your direct proxy for Helm's **trend gate** and
`trend_strength`:
- Total market cap **below its longer moving average (≈50d/200d)** → trend gate
  leans risk-off.
- RSI mid-range + flat MACD → low `trend_strength` → `ranging`.
- Strong MACD with rising price above the MA → high `trend_strength` → `trending`.

### Step 3: BSC majors cross-section (breadth, dispersion, drawdown)

Resolve the Helm BSC-major universe to CMC IDs with `search_cryptos`
(symbols: **ETH, XRP, ADA, LINK, DOGE, AVAX, DOT, CAKE**), then batch
`get_crypto_quotes_latest` with the comma-joined IDs. From the per-name 7d/30d
changes, compute Helm's cross-sectional features:
- **breadth** ≈ fraction of the 8 names with a positive trailing return.
- **dispersion** ≈ spread of those returns (tight = coherent regime; wide =
  fractured / high-vol).
- **drawdown** ≈ how far an equal-weight blend of the 8 sits below its recent
  peak (the **10% drawdown gate**).

### Step 4: Per-name trend confirmation (optional, sharpens trending vs ranging)

For a tighter read, call `get_crypto_technical_analysis` on 2–3 of the majors
(e.g. ETH id=1027, plus CAKE) to check whether names sit above/below their 50d/200d
MA and their RSI. Broad above-MA + healthy RSI confirms `trending`; mixed confirms
`ranging`.

### Step 5: Volatility / leverage confirmation (high_volatility check)

Call `get_global_crypto_derivatives_metrics`. Spiking liquidations, extreme funding,
and a sharp open-interest swing corroborate elevated **`realized_vol`** → lean
`high_volatility`. Combined with a wide Step-3 dispersion, classify
`high_volatility` even if direction is unclear.

### Step 6: Classify, then apply the risk-off override

1. Pick the regime: highest volatility/dispersion + liquidation spike →
   `high_volatility`; else strong signed trend (high \|trend_strength\|, one-sided
   breadth, above-MA) → `trending`; else → `ranging`.
2. Set a **confidence** (high / medium / low) from how cleanly the signals agree.
3. **Run the risk-off gate (Step thresholds above).** If the market index is
   >10% below its peak OR below its 50d MA, set `risk_off = true` and **override
   the stance to defensive**, noting the regime the HMM would otherwise have read.
4. Map the (possibly overridden) regime to a stance: trending → momentum,
   ranging → market portfolio, high_volatility / risk-off → defensive.

## Output template

Present the read as a compact markdown report:

```
## Helm RegimeRead — BSC majors ([date])

**Regime:** [trending / ranging / high_volatility]   **Confidence:** [high/medium/low]
**Recommended stance:** [momentum / market portfolio / defensive]
**Risk-off gate:** [CLEAR | FIRED — index <50d MA / >10% off peak → forced defensive]

### Signals
- Market cap: $X.XX T (7d X.X% | 30d X.X%)   — drift / drawdown
- Fear & Greed: XX ([label])
- BTC dominance: XX% | Altcoin Season: XX   — breadth
- Total-mktcap technicals: RSI XX, MACD [bullish/bearish], price [above/below] MA
- Derivatives: OI $XXX B, funding X.XX%, liquidations $XXX M

### Feature attribution (Helm's read)
- trend_strength: [high/low/negative] → [supports trending / ranging]
- realized_vol:   [elevated/normal]   → [supports high_volatility / not]
- breadth:        XX% of 8 majors positive
- dispersion:     [tight/wide] cross-section

### Stance
[1-2 sentences: which sub-strategy Helm activates and why; if the gate fired,
state that the trend filter overrode the regime to cash/defensive.]

_Helm regime read, not financial advice. Live mode is a heuristic reproduction of
Helm's classifier; run Full mode below for the exact HMM-based read._
```

## Full mode (local Helm engine — exact HMM read + evidence)

If the user has the Helm repo checked out, the live heuristics above can be
replaced with the exact HMM-based classifier:

```bash
# exact RegimeRead (HMM + on-chain TVL fusion + risk-off gate)
uv run python scripts/helm_read.py            # human-readable report
uv run python scripts/helm_read.py --json     # machine-readable JSON
```

`helm_read.py` builds the live CMC price panel for the BSC majors (~200 days),
fuses on-chain TVL features (skipped gracefully if the on-chain cache is empty),
runs the walk-forward HMM regime classifier, applies the same `market_risk_off`
gate, and prints regime / confidence / posterior / top attribution features /
risk-off flag / recommended stance.

For the validated evidence behind the stances, point the user to:

```bash
uv run python scripts/regime_backtest.py      # Helm vs baselines + regime P&L attribution
uv run python scripts/onchain_validation.py   # walk-forward OOS: helm_gated_tvl vs market, DSR
```

Prefer Full mode whenever the repo is available — it is the ground truth; Live
mode is the MCP-only approximation.

## Handling tool failures

If individual tools fail during the read:

1. **get_global_metrics_latest fails**: Critical for sentiment/breadth and the
   drawdown proxy. Retry once, then proceed on Steps 2-3 and note "Global metrics
   unavailable — confidence downgraded."
2. **get_crypto_marketcap_technical_analysis fails**: You lose the direct trend-gate
   proxy. Fall back to the Step-3 equal-weight cross-section for the 50d-MA / 10%-
   drawdown check and note the substitution.
3. **search_cryptos fails**: Cannot resolve major IDs. Use known anchors
   (BTC id=1, ETH id=1027) for `get_crypto_quotes_latest` and read breadth on a
   reduced set; note the universe was truncated.
4. **get_crypto_quotes_latest fails**: Cross-sectional breadth/dispersion/drawdown
   are unavailable. Retry once, then classify from Steps 1-2 only and lower
   confidence to at most "medium".
5. **get_crypto_technical_analysis fails**: Skip Step 4 (per-name confirmation);
   it only sharpens trending-vs-ranging and is non-blocking.
6. **get_global_crypto_derivatives_metrics fails**: Skip the leverage check; infer
   `high_volatility` from Step-3 dispersion alone and note derivatives were
   unavailable.

Always produce a RegimeRead with the data available rather than abandoning the
read. State which signals were missing and how that affected confidence. If the
risk-off gate cannot be evaluated (no usable index series), report
`Risk-off gate: INDETERMINATE` and default to the more conservative stance.
