import importlib

import pandas as pd


class _FakeCache:
    def __init__(self, series):
        self._d = dict(series)

    def get_series(self, key):
        return self._d.get(key)


def test_module_imports_and_exposes_entrypoints():
    mod = importlib.import_module("scripts.whale_backfill")
    assert callable(mod.main)
    assert callable(mod.flow_panel)
    # reuses the majors' BSC contracts from the on-chain backfill
    from scripts.onchain_backfill import BSC_TOKEN_ADDRESSES

    assert mod.BSC_TOKEN_ADDRESSES is BSC_TOKEN_ADDRESSES
    # documents a default whale threshold per token (a numeric/str map or scalar)
    assert hasattr(mod, "WHALE_MIN_AMOUNT")


def test_flow_panel_whale_kind_reads_whaleflow_keys():
    from scripts.whale_backfill import flow_panel

    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    cache = _FakeCache(
        {
            "whaleflow_AAA": pd.Series([1.0, 2.0, 3.0], index=idx),
            "whaleflow_BBB": pd.Series([4.0, 5.0, 6.0], index=idx),
            "cexflow_AAA": pd.Series([7.0, 8.0, 9.0], index=idx),
        }
    )
    panel = flow_panel(cache, ["AAA", "BBB", "CCC"], kind="whale")
    assert list(panel.columns) == ["AAA", "BBB"]  # CCC absent -> skipped
    assert panel.loc[idx[2], "BBB"] == 6.0


def test_flow_panel_cex_kind_reads_cexflow_keys():
    from scripts.whale_backfill import flow_panel

    idx = pd.date_range("2024-01-01", periods=2, freq="D")
    cache = _FakeCache({"cexflow_AAA": pd.Series([7.0, 8.0], index=idx)})
    panel = flow_panel(cache, ["AAA", "BBB"], kind="cex")
    assert list(panel.columns) == ["AAA"]
    assert panel.loc[idx[1], "AAA"] == 8.0


def test_flow_panel_empty_when_nothing_cached():
    from scripts.whale_backfill import flow_panel

    panel = flow_panel(_FakeCache({}), ["AAA"], kind="whale")
    assert panel.empty
