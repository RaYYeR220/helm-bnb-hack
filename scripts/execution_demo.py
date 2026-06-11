"""Human-run execution demo: RegimeRead -> execution plan -> TWAK quotes.

Shows the live-trading interface WITHOUT moving funds: Helm's regime read is
turned into rebalance intents, and each intent is priced with a read-only TWAK
``--quote-only`` quote. Nothing is ever broadcast (no ``--password`` is passed;
``--quote-only`` is always set).

Usage:
    uv run python scripts/execution_demo.py --offline        # canned read, no APIs
    uv run python scripts/execution_demo.py                  # live read (CMC key)
    # TWAK quotes additionally need Trust Wallet API creds:
    #   twak setup   (or TWAK_ACCESS_ID / TWAK_HMAC_SECRET env vars)
"""

import argparse
import json

import pandas as pd

from execution.intents import regime_to_execution_plan
from execution.twak_adapter import TwakAdapter

# Canned read for --offline: a trending regime, gate clear, so the demo shows
# actual intents + quotes rather than a hold.
OFFLINE_READ = {
    "regime": "trending",
    "risk_off": False,
    "recommended_stance": "momentum",
    "date": "2026-06-09",
    "confidence": 0.87,
}

# Demo book: an all-cash $10k portfolio entering a momentum top-3.
OFFLINE_TARGET = {"CAKE": 1 / 3, "LINK": 1 / 3, "DOGE": 1 / 3}


def plan_from_read(read: dict, target: dict, portfolio_usd: float) -> dict:
    """Pure helper: wrap a read + target weights into an execution plan."""
    return regime_to_execution_plan(
        read,
        current_weights=pd.Series(dtype=float),  # all cash
        target_weights=pd.Series(target, dtype=float),
        portfolio_usd=portfolio_usd,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Helm -> TWAK execution demo")
    parser.add_argument("--offline", action="store_true", help="use a canned read")
    parser.add_argument("--portfolio-usd", type=float, default=10_000.0)
    parser.add_argument("--top", type=int, default=3, help="max intents to quote")
    args = parser.parse_args()

    if args.offline:
        read = OFFLINE_READ
        target = OFFLINE_TARGET
    else:
        # Live read: same engine path as scripts/helm_read (needs CMC key).
        from scripts.helm_read import _build_read, read_to_dict

        read_obj, risk_off = _build_read(days=200)
        read = read_to_dict(read_obj, risk_off)
        # The demo quotes a representative momentum top-3 basket; live target
        # weights come from the router in the backtest/agent paths.
        target = OFFLINE_TARGET

    plan = plan_from_read(read, target, args.portfolio_usd)
    print("=== Helm execution plan ===")
    print(json.dumps(plan, indent=2, default=str))

    if plan["hold"] or not plan["intents"]:
        print("\nNo trades to quote (hold/aligned). That is the decision.")
        return

    twak = TwakAdapter()
    if not twak.available():
        print("\ntwak CLI not found — install with: npm install -g @trustwallet/cli")
        return

    print(f"\n=== TWAK quotes (read-only, top {args.top}) ===")
    for intent in plan["intents"][: args.top]:
        # buys: WBNB -> asset; sells: asset -> WBNB. USD-notional via --usd.
        if intent["action"] == "buy":
            q = twak.quote_swap_usd(intent["usd_amount"], "WBNB", intent["symbol"])
        else:
            q = twak.quote_swap_usd(intent["usd_amount"], intent["symbol"], "WBNB")
        if q["ok"]:
            print(f"  {intent['action']:4s} {intent['symbol']:6s} ${intent['usd_amount']:>10.2f}  quote: {json.dumps(q['quote'])[:120]}")
        else:
            print(f"  {intent['action']:4s} {intent['symbol']:6s} ${intent['usd_amount']:>10.2f}  quote unavailable: {q['error'][:100]}")
    print("\nNothing was broadcast. Quotes only -- the live path is documented in execution/README.md.")


if __name__ == "__main__":
    main()
