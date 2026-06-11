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


def test_quote_swap_builds_quote_only_argv_with_aliases():
    spy = RunnerSpy(stdout=json.dumps({"toAmount": "0.01"}))
    out = TwakAdapter(runner=spy).quote_swap(1.5, "ETH", "BNB")
    assert spy.argv[:4] == ["swap", "1.5", "WETH", "WBNB"]
    assert "--quote-only" in spy.argv and "--json" in spy.argv
    assert "--password" not in spy.argv  # never executes
    assert out["ok"] is True
    assert out["quote"] == {"toAmount": "0.01"}


def test_quote_swap_usd_mode_uses_usd_flag():
    spy = RunnerSpy(stdout=json.dumps({"toAmount": "0.5"}))
    out = TwakAdapter(runner=spy).quote_swap_usd(50.0, "CAKE", "WBNB")
    # usd mode: 2 token args + --usd <amount>, no leading token amount
    assert spy.argv[:3] == ["swap", "CAKE", "WBNB"]
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
