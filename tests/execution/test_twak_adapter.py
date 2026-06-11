import json

from execution.twak_adapter import TwakAdapter

# The REAL credential-gate output captured live from twak 0.19.0 on this machine.
CRED_ERROR = json.dumps(
    {
        "error": "No API credentials found. Run `twak setup` (or set TWAK_ACCESS_ID and TWAK_HMAC_SECRET env vars).",
        "errorCode": "VALIDATION_ERROR",
    },
    indent=2,
)


class RunnerSpy:
    def __init__(self, code=0, stdout="{}", stderr=""):
        self.code, self.stdout, self.stderr = code, stdout, stderr
        self.argv = None

    def __call__(self, argv):
        self.argv = list(argv)
        return (self.code, self.stdout, self.stderr)


def test_quote_swap_builds_quote_only_argv_resolving_bsc_tokens():
    spy = RunnerSpy(stdout=json.dumps({"toAmount": "0.01"}))
    out = TwakAdapter(runner=spy).quote_swap(1.5, "ETH", "BNB")
    # ETH -> its BSC contract address; BNB -> WBNB
    assert spy.argv[:2] == ["swap", "1.5"]
    assert spy.argv[2] == "0x2170ed0880ac9a755fd29b2688956bd959f933f8"
    assert spy.argv[3] == "WBNB"
    assert "--quote-only" in spy.argv and "--json" in spy.argv
    assert "--password" not in spy.argv  # never executes
    assert out["ok"] is True
    assert out["quote"] == {"toAmount": "0.01"}


def test_quote_swap_usd_mode_uses_usd_flag():
    spy = RunnerSpy(stdout=json.dumps({"toAmount": "0.5"}))
    out = TwakAdapter(runner=spy).quote_swap_usd(50.0, "CAKE", "WBNB")
    # usd mode: 2 token args + --usd <amount>; CAKE -> its BSC contract address
    assert spy.argv[0] == "swap"
    assert spy.argv[1] == "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82"
    assert spy.argv[2] == "WBNB"
    i = spy.argv.index("--usd")
    assert spy.argv[i + 1] == "50"
    assert "--quote-only" in spy.argv
    assert out["ok"] is True


def test_quote_swap_parses_real_credential_error():
    spy = RunnerSpy(code=1, stdout=CRED_ERROR)
    out = TwakAdapter(runner=spy).quote_swap(1, "CAKE", "WBNB")
    assert out["ok"] is False
    assert out["error_code"] == "VALIDATION_ERROR"
    assert "API credentials" in out["error"]


def test_quote_swap_nonzero_exit_without_json():
    spy = RunnerSpy(code=127, stdout="", stderr="twak not found")
    out = TwakAdapter(runner=spy).quote_swap(1, "CAKE", "WBNB")
    assert out["ok"] is False
    assert "not found" in out["error"]


def test_quote_swap_slippage_flag():
    spy = RunnerSpy(stdout="{}")
    TwakAdapter(runner=spy).quote_swap(1, "CAKE", "WBNB", slippage=0.5)
    i = spy.argv.index("--slippage")
    assert spy.argv[i + 1] == "0.5"


def test_wallet_address_parses_nested_data():
    spy = RunnerSpy(stdout=json.dumps({"data": {"address": "0xabc"}}))
    assert TwakAdapter(runner=spy).wallet_address() == "0xabc"


def test_wallet_address_none_on_error():
    spy = RunnerSpy(code=1, stdout=CRED_ERROR)
    assert TwakAdapter(runner=spy).wallet_address() is None


def test_available_true_with_injected_runner():
    assert TwakAdapter(runner=RunnerSpy()).available() is True


def test_json_parse_tolerates_banner_noise():
    spy = RunnerSpy(stdout='twak v0.19.0\n{"toAmount": "1"}\n')
    out = TwakAdapter(runner=spy).quote_swap(1, "CAKE", "WBNB")
    assert out["ok"] is True
    assert out["quote"]["toAmount"] == "1"


def test_bsc_major_symbol_resolves_to_contract_address():
    spy = RunnerSpy(stdout="{}")
    TwakAdapter(runner=spy).quote_swap_usd(100, "WBNB", "CAKE")
    # CAKE on bsc must be passed as its BEP-20 contract address, not "CAKE"
    assert "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82" in spy.argv
    assert "CAKE" not in spy.argv


def test_unknown_symbol_passes_through_uppercased():
    spy = RunnerSpy(stdout="{}")
    TwakAdapter(runner=spy).quote_swap_usd(100, "WBNB", "wbtc")
    assert "WBTC" in spy.argv
