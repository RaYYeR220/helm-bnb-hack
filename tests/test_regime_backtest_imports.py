import importlib


def test_regime_backtest_script_imports_and_exposes_main():
    mod = importlib.import_module("scripts.regime_backtest")
    assert hasattr(mod, "main")
    assert callable(mod.main)
    # the comparison helper is pure and testable without network
    assert hasattr(mod, "format_metrics_table")
    assert callable(mod.format_metrics_table)


def test_format_metrics_table_renders_all_rows_and_columns():
    from scripts.regime_backtest import METRIC_KEYS, format_metrics_table
    table = format_metrics_table({
        "helm": {k: 0.1 for k in METRIC_KEYS},
        "momentum": {k: 0.2 for k in METRIC_KEYS},
    })
    assert "helm" in table
    assert "momentum" in table
    for k in METRIC_KEYS:
        assert k in table
    # header + separator + 2 data rows
    assert len(table.splitlines()) == 4
