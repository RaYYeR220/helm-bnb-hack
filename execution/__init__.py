"""Helm execution layer (deliverable E4) -- the signal -> safe-execution path.

This package maps a Helm read (a ``RegimeRead`` + the regime-routed target
portfolio weights) to **execution intents**, and turns each intent into a
*read-only swap quote* via the **Trust Wallet Agent Kit** CLI (``twak``). It is
deliberately lean and honest: a clean execution adapter + demo that shows the
live-trading interface **without real capital and without ever broadcasting**.

Two safe modes only:

- ``--quote-only`` swaps on BSC mainnet (build/quote, never executed).
- (documented) BSC testnet ERC-20 transfer/approve -- not exercised here, see
  ``execution/README.md`` for why the spike couldn't reach it on this CLI.

Pieces:

- :mod:`execution.intents` -- **pure** weight-diff -> intent logic
  (``weights_to_intents``, ``regime_to_execution_plan``). No network, no twak.
- :mod:`execution.twak_adapter` -- :class:`~execution.twak_adapter.TwakAdapter`,
  a thin subprocess wrapper around ``twak`` with an **injectable runner** seam
  so it is fully offline-testable.

Nothing Node-related lands in the Python package: ``twak`` is a global / dev CLI
invoked by subprocess, and the adapter degrades gracefully when it is absent.
"""

from execution.intents import regime_to_execution_plan, weights_to_intents
from execution.twak_adapter import TwakAdapter

__all__ = [
    "weights_to_intents",
    "regime_to_execution_plan",
    "TwakAdapter",
]
