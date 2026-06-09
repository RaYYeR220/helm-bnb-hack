import json

import pandas as pd

from helm.backtest.result import BacktestConfig, BacktestResult


def test_config_defaults():
    c = BacktestConfig()
    assert c.fee_bps == 10.0
    assert c.slippage_bps == 5.0
    assert c.initial_capital == 10_000.0


def test_result_to_json_roundtrip(tmp_path):
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    result = BacktestResult(
        equity=pd.Series([100.0, 101.0, 102.0], index=idx),
        returns=pd.Series([0.0, 0.01, 0.0099], index=idx),
        weights=pd.DataFrame({"A": [1.0, 1.0, 1.0]}, index=idx),
        trades=pd.DataFrame({"date": [idx[1]], "turnover": [1.0]}),
        metrics={"sharpe": 1.23, "total_return": 0.02},
        strategy_name="momentum",
    )
    out = tmp_path / "artifact.json"
    result.to_json(out)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["strategy_name"] == "momentum"
    assert loaded["metrics"]["sharpe"] == 1.23
    assert len(loaded["equity"]) == 3
    assert loaded["equity"][0]["value"] == 100.0
