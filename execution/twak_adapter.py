"""Thin subprocess wrapper around the Trust Wallet Agent Kit CLI (``twak``).

This is Helm's **execution surface** for deliverable E4. It does not move funds:
it asks ``twak`` for read-only *swap quotes* (``--quote-only``) and the agent
wallet address. The point is to demonstrate the live-trading interface -- "what
Helm WOULD execute" -- without ever broadcasting a transaction or touching real
capital.

Design: a single :class:`TwakAdapter` with an **injectable runner** (the test
seam). In production the runner shells out to ``twak`` (via ``twak`` on PATH or
``npx @trustwallet/cli``); in tests we inject a fake runner that returns canned
CLI output, so the whole adapter -- argument construction *and* output parsing --
is unit-tested with **zero Node / network**. No real ``twak`` call ever happens
in the test suite.

What the spike verified live (Windows, ``twak`` v0.19.0, 2026-06-11)
-------------------------------------------------------------------
- ``npx @trustwallet/cli --version`` -> ``0.19.0`` (CLI installs + runs).
- ``twak chains --json`` lists 25 chains; **BNB Smart Chain key is ``bsc``**
  (the ``--chain`` flag takes a *key*, not a numeric id; there is **no**
  ``bsctestnet`` entry in this CLI version).
- ``twak swap <amt> <from> <to> --chain bsc --quote-only --json`` is the real
  quote command, and ``--json`` is supported.
- Data / swap commands require API credentials (``TWAK_ACCESS_ID`` +
  ``TWAK_HMAC_SECRET``, via ``twak setup`` or env). With credentials present,
  ``swap ... --quote-only --json`` returns a real quote, e.g.
  ``{"input": "5.5158 WBNB", "output": "2473.18 CAKE", "minReceived": "2448.45 CAKE", "provider": ...}``.
  Without them it returns ``{"error": "...No API credentials found...",
  "errorCode": "VALIDATION_ERROR"}`` and a non-zero exit. The adapter parses both
  shapes; the demo reports either outcome honestly.
- On ``bsc`` the CLI resolves only a small builtin symbol set; the Helm majors
  (CAKE, ETH, LINK, ...) must be passed as BEP-20 **contract addresses** (see
  ``BSC_MAJOR_ADDRESSES`` / ``_resolve_token``) or the CLI returns
  ``Unknown token: <SYM> on bsc``.

The parser is defensive: it surfaces whatever the quote object contains and never
assumes a field is present.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Sequence

# A runner takes argv (after the leading "twak"/"npx ..." program) and returns
# (returncode, stdout, stderr). This is the single injection seam.
Runner = Callable[[Sequence[str]], "tuple[int, str, str]"]

# Map Helm universe symbols -> the on-chain tradable symbol the CLI understands.
# Native coins are wrapped (BNB->WBNB) since DEX swaps trade wrapped ERC-20s.
SYMBOL_ALIASES = {
    "BNB": "WBNB",
}

# BEP-20 contract addresses for the Helm BSC-major universe. twak on `bsc`
# resolves only a small builtin symbol set; everything else must be passed as a
# 0x contract address ("Unknown token: CAKE on bsc. Use a contract address...").
# These are the same wrapped/peg contracts the on-chain backfill uses.
BSC_MAJOR_ADDRESSES = {
    "CAKE": "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82",
    "ETH": "0x2170ed0880ac9a755fd29b2688956bd959f933f8",
    "XRP": "0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe",
    "ADA": "0x3ee2200efb3400fabb9aacf31297cbdd1d435d47",
    "DOGE": "0xba2ae424d960c26247dd6c32edc70b295c744c43",
    "LINK": "0xf8a0bf9cf54bb92f17374d9e9a321e6a111a51bd",
    "DOT": "0x7083609fce4d1d8dc0c979aab8c869ea2c873402",
    "AVAX": "0x1ce0c2827e2ef14d5c4f29a091d735a204794041",
}


def _resolve_token(sym: str, chain: str) -> str:
    """Token argument for the CLI: a BSC-major contract address on ``bsc``,
    else the alias-mapped, uppercased symbol."""
    up = sym.upper()
    if up.startswith("0X"):
        return sym  # already a contract address
    if chain == "bsc" and up in BSC_MAJOR_ADDRESSES:
        return BSC_MAJOR_ADDRESSES[up]
    return SYMBOL_ALIASES.get(up, up)

# Default quote asset for a buy/sell notional on BSC: WBNB is the canonical
# pair leg on PancakeSwap. The demo swaps <asset> <-> WBNB for the quote.
DEFAULT_QUOTE_ASSET = "WBNB"
DEFAULT_CHAIN = "bsc"


def _default_runner(argv: Sequence[str]) -> tuple[int, str, str]:
    """Real runner: invoke the ``twak`` CLI, preferring ``twak`` on PATH and
    falling back to ``npx --yes @trustwallet/cli``. Never raises on a non-zero
    exit -- returns (code, stdout, stderr) for the caller to interpret."""
    program = _resolve_program()
    if program is None:
        return (127, "", "twak CLI not found on PATH and npx unavailable")
    proc = subprocess.run(  # noqa: S603 - argv is built from typed, validated parts
        [*program, *argv],
        capture_output=True,
        text=True,
        check=False,
    )
    return (proc.returncode, proc.stdout or "", proc.stderr or "")


def _resolve_program() -> list[str] | None:
    """Return the argv prefix that launches twak, or None if unavailable.

    Uses the FULL resolved path from ``shutil.which``: on Windows the npm shim
    is ``twak.cmd``, and ``CreateProcess`` only executes batch files when the
    explicit extensioned path is given (bare "twak" raises WinError 2)."""
    twak = shutil.which("twak")
    if twak:
        return [twak]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "@trustwallet/cli"]
    return None


class TwakAdapter:
    """Read-only Helm -> TWAK execution adapter.

    All methods are *safe*: they fetch quotes and addresses, never broadcast.
    The runner seam (``runner=``) makes every method offline-testable.
    """

    def __init__(
        self,
        runner: Runner | None = None,
        chain: str = DEFAULT_CHAIN,
        quote_asset: str = DEFAULT_QUOTE_ASSET,
    ):
        self._runner = runner or _default_runner
        self.chain = chain
        self.quote_asset = quote_asset

    # -- capability -------------------------------------------------------

    def available(self) -> bool:
        """True iff the ``twak`` CLI is reachable (on PATH, or via npx).

        Note: *reachable* != *usable* -- the data commands additionally require
        TWAK API credentials. This only checks the binary is present so the demo
        can degrade gracefully. When a custom runner is injected we assume the
        seam is wired and report True."""
        if self._runner is not _default_runner:
            return True
        return _resolve_program() is not None

    # -- reads ------------------------------------------------------------

    def quote_swap(
        self,
        amount: float,
        from_sym: str,
        to_sym: str,
        slippage: float | None = None,
    ) -> dict:
        """Fetch a read-only swap quote: ``twak swap <amount> <from> <to>
        --chain <chain> --quote-only --json``.

        Never executes (``--quote-only`` is always set; no ``--password`` is ever
        passed). Returns a normalized dict::

            {"ok": True,  "from": ..., "to": ..., "amount": ..., "chain": ...,
             "quote": {<raw quote object from twak>}, "raw": "<stdout>"}
            {"ok": False, "error": "...", "error_code": "...", "raw": "<stdout>"}

        Parsing: ``twak`` emits a JSON object on stdout under ``--json``. A
        successful quote is that object; a failure is
        ``{"error", "errorCode"}`` (the credential-gate shape the spike hit).
        """
        from_t = _resolve_token(from_sym, self.chain)
        to_t = _resolve_token(to_sym, self.chain)
        argv = [
            "swap",
            _fmt_amount(amount),
            from_t,
            to_t,
            "--chain",
            self.chain,
            "--quote-only",
            "--json",
        ]
        if slippage is not None:
            argv += ["--slippage", _fmt_amount(slippage)]

        code, out, err = self._runner(argv)
        parsed = _parse_json_object(out)

        if parsed is not None and "error" in parsed:
            return {
                "ok": False,
                "error": str(parsed.get("error")),
                "error_code": parsed.get("errorCode"),
                "from": from_t,
                "to": to_t,
                "amount": amount,
                "chain": self.chain,
                "raw": out.strip(),
            }
        if code != 0 or parsed is None:
            return {
                "ok": False,
                "error": (err or out or f"twak exited {code}").strip(),
                "error_code": None,
                "from": from_t,
                "to": to_t,
                "amount": amount,
                "chain": self.chain,
                "raw": (out or err).strip(),
            }
        return {
            "ok": True,
            "from": from_t,
            "to": to_t,
            "amount": amount,
            "chain": self.chain,
            "quote": parsed,
            "raw": out.strip(),
        }

    def quote_swap_usd(
        self,
        usd_amount: float,
        from_sym: str,
        to_sym: str,
        slippage: float | None = None,
    ) -> dict:
        """Fetch a read-only quote for a USD-equivalent notional: ``twak swap
        <from> <to> --usd <amount> --chain <chain> --quote-only --json``.

        This matches Helm's intents, which are denominated in USD notional
        (``usd_amount`` from ``weights_to_intents``). Same safety + return
        contract as :meth:`quote_swap`."""
        from_t = _resolve_token(from_sym, self.chain)
        to_t = _resolve_token(to_sym, self.chain)
        argv = [
            "swap",
            from_t,
            to_t,
            "--usd",
            _fmt_amount(usd_amount),
            "--chain",
            self.chain,
            "--quote-only",
            "--json",
        ]
        if slippage is not None:
            argv += ["--slippage", _fmt_amount(slippage)]

        code, out, err = self._runner(argv)
        parsed = _parse_json_object(out)

        if parsed is not None and "error" in parsed:
            return {
                "ok": False,
                "error": str(parsed.get("error")),
                "error_code": parsed.get("errorCode"),
                "from": from_t,
                "to": to_t,
                "amount": usd_amount,
                "chain": self.chain,
                "raw": out.strip(),
            }
        if code != 0 or parsed is None:
            return {
                "ok": False,
                "error": (err or out or f"twak exited {code}").strip(),
                "error_code": None,
                "from": from_t,
                "to": to_t,
                "amount": usd_amount,
                "chain": self.chain,
                "raw": (out or err).strip(),
            }
        return {
            "ok": True,
            "from": from_t,
            "to": to_t,
            "amount": usd_amount,
            "chain": self.chain,
            "quote": parsed,
            "raw": out.strip(),
        }

    def wallet_address(self, password: str | None = None) -> str | None:
        """Return the agent wallet address for ``self.chain``, or None.

        Runs ``twak wallet address --chain <chain> --json``. The password (if
        given) is forwarded so the keystore can be unlocked; it is **never
        logged** -- only handed to the subprocess. Returns None when no wallet is
        configured, creds are missing, or the address can't be parsed."""
        argv = ["wallet", "address", "--chain", self.chain, "--json"]
        if password:
            argv += ["--password", password]
        code, out, _err = self._runner(argv)
        parsed = _parse_json_object(out)
        if not parsed or "error" in parsed:
            return None
        # twak emits {"address": "0x..."} (possibly nested under "data").
        addr = parsed.get("address")
        if addr is None and isinstance(parsed.get("data"), dict):
            addr = parsed["data"].get("address")
        return str(addr) if addr else None


def _fmt_amount(x: float) -> str:
    """Format a number for the CLI: trim trailing zeros, keep it human-readable."""
    s = f"{float(x):.8f}".rstrip("0").rstrip(".")
    return s or "0"


def _parse_json_object(text: str) -> dict | None:
    """Best-effort: extract the first top-level JSON object from CLI stdout.

    ``twak --json`` prints a single JSON value, but be defensive about banner
    lines or trailing noise: try a whole-string parse first, then fall back to
    slicing from the first ``{`` to the last ``}``. Returns None if no object
    is found or it isn't a dict."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        val = json.loads(text)
        return val if isinstance(val, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        val = json.loads(text[start : end + 1])
        return val if isinstance(val, dict) else None
    except json.JSONDecodeError:
        return None
