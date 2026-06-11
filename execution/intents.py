"""Pure weight-diff -> execution-intent logic (deliverable E4, TWAK layer).

Helm produces *target portfolio weights* (``RegimeRouter.target_weights``). To
*act* on a read, the live-trading layer must turn the gap between where the
portfolio is now and where Helm wants it to be into a concrete, ordered list of
trades. That is exactly what this module does -- and nothing more.

Everything here is **pure**: no network, no subprocess, no clock. Given the
current weights, the target weights, and a portfolio size in USD, it emits a
deterministic list of ``intent`` dicts. The TWAK adapter (``twak_adapter.py``)
turns one intent into a *quote*; the demo wires them together. Keeping the
diff logic pure means it is fully unit-testable with zero TWAK present.

An *intent* is a plain dict::

    {
        "action": "buy" | "sell",   # buy = increase exposure, sell = decrease
        "symbol": "CAKE",           # the asset whose weight is changing
        "usd_amount": 123.45,       # absolute USD notional of the change
        "fraction": 0.05,           # signed weight delta (target - current)
    }

Ordering is deterministic: **sells first, then buys**, each block sorted by
descending USD notional. Sells-before-buys mirrors how a real rebalance frees
capital before deploying it. Dust trades (below ``min_trade_usd``) are dropped.
"""

from __future__ import annotations

import pandas as pd


def weights_to_intents(
    current_weights: pd.Series,
    target_weights: pd.Series,
    portfolio_usd: float,
    min_trade_usd: float = 10.0,
) -> list[dict]:
    """Diff current vs. target weights into an ordered list of trade intents.

    Pure / deterministic. For every symbol in either series, computes the signed
    weight delta ``target - current`` and converts it to a USD notional against
    ``portfolio_usd``. Deltas whose absolute USD notional is below
    ``min_trade_usd`` are treated as dust and skipped (no point paying gas/spread
    to move a few dollars). The surviving intents are ordered **sells first, then
    buys**, each block sorted by descending USD notional so the largest, most
    impactful trades lead.

    Args:
        current_weights: symbol -> current portfolio weight (fractions of NAV).
        target_weights:  symbol -> Helm's target weight (fractions of NAV).
        portfolio_usd:   total portfolio value in USD (must be > 0 to trade).
        min_trade_usd:   dust threshold; trades below this USD notional are
            dropped. Defaults to $10.

    Returns:
        A list of intent dicts (see module docstring). Empty when there is
        nothing material to do (already aligned, or ``portfolio_usd <= 0``).
    """
    if portfolio_usd <= 0:
        return []

    # Union of symbols across both sides; a name present in only one series is
    # treated as weight 0.0 on the missing side (full entry / full exit).
    symbols = sorted(set(current_weights.index) | set(target_weights.index))

    intents: list[dict] = []
    for sym in symbols:
        cur = float(current_weights.get(sym, 0.0))
        tgt = float(target_weights.get(sym, 0.0))
        delta = tgt - cur
        usd = abs(delta) * portfolio_usd
        if usd < min_trade_usd:
            continue  # dust -- not worth a trade
        intents.append(
            {
                "action": "buy" if delta > 0 else "sell",
                "symbol": sym,
                "usd_amount": round(usd, 2),
                "fraction": round(delta, 6),
            }
        )

    # Sells before buys; within each block, largest notional first. The symbol
    # is the final tiebreaker so ordering is fully deterministic.
    action_rank = {"sell": 0, "buy": 1}
    intents.sort(key=lambda it: (action_rank[it["action"]], -it["usd_amount"], it["symbol"]))
    return intents


# Regime label -> the stance Helm takes in that regime. Mirrors
# scripts/helm_read.recommended_stance / regime_backtest.build_router so the
# execution layer tells the same story as the read layer.
_STANCE = {
    "trending": "momentum",
    "ranging": "market portfolio",
    "high_volatility": "defensive",
}


def regime_to_execution_plan(
    read_dict: dict,
    current_weights: pd.Series,
    target_weights: pd.Series,
    portfolio_usd: float,
    min_trade_usd: float = 10.0,
) -> dict:
    """Wrap weight-diff intents with the regime / risk-off context from a read.

    Pure / deterministic. Consumes a ``read_dict`` in the shape emitted by
    ``scripts.helm_read.read_to_dict`` (keys ``regime``, ``risk_off``,
    ``recommended_stance``, ``date``, ``confidence``) and returns a structured
    *execution plan*:

    - When the read is **risk-off** (or the regime is ``high_volatility`` ->
      defensive), Helm's stance is *hold / preserve capital*. The plan carries
      **zero intents** and a human-readable note -- the safe path does nothing,
      which is itself a decision. Capital preservation is an action.
    - Otherwise (``ranging`` -> equal-weight rebalance, ``trending`` ->
      momentum top-N) the plan carries the diffed intents.

    The returned dict is JSON-ready (all values are str / float / int / list).

    Args:
        read_dict: a serialized RegimeRead (see ``helm_read.read_to_dict``).
        current_weights: symbol -> current weight.
        target_weights:  symbol -> Helm target weight (already regime-routed).
        portfolio_usd:   portfolio value in USD.
        min_trade_usd:   dust threshold passed through to ``weights_to_intents``.

    Returns:
        ``{regime, risk_off, stance, date, confidence, hold, note, intents}``.
    """
    regime = read_dict.get("regime", "")
    risk_off = bool(read_dict.get("risk_off", False))
    stance = read_dict.get("recommended_stance") or _STANCE.get(regime, "market portfolio")

    # Defensive / risk-off => hold. We do not trade into a confirmed downtrend
    # or a high-volatility regime: the safe move is to preserve, not reposition.
    hold = risk_off or regime == "high_volatility"

    if hold:
        why = "risk-off gate fired" if risk_off else "high-volatility regime"
        return {
            "regime": regime,
            "risk_off": risk_off,
            "stance": stance,
            "date": read_dict.get("date"),
            "confidence": read_dict.get("confidence"),
            "hold": True,
            "note": (
                f"HOLD / defensive ({why}) -- no rebalance intents. "
                "Preserving capital is the decision."
            ),
            "intents": [],
        }

    intents = weights_to_intents(
        current_weights, target_weights, portfolio_usd, min_trade_usd
    )
    if not intents:
        note = (
            f"{stance}: portfolio already aligned with target "
            f"(no trades above ${min_trade_usd:g})."
        )
    else:
        n_sell = sum(1 for it in intents if it["action"] == "sell")
        n_buy = len(intents) - n_sell
        note = f"{stance}: rebalance -> {n_sell} sell / {n_buy} buy intent(s)."

    return {
        "regime": regime,
        "risk_off": risk_off,
        "stance": stance,
        "date": read_dict.get("date"),
        "confidence": read_dict.get("confidence"),
        "hold": False,
        "note": note,
        "intents": intents,
    }
