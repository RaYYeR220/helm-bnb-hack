import importlib

import numpy as np
import pandas as pd


def test_validation_script_imports_and_exposes_main():
    mod = importlib.import_module("scripts.onchain_validation")
    assert hasattr(mod, "main")
    assert callable(mod.main)
    assert hasattr(mod, "build_helm_configs_offline")
    assert callable(mod.build_helm_configs_offline)
    assert hasattr(mod, "HELM_VARIANTS")


def test_helm_variants_are_the_three_documented_configs():
    from scripts.onchain_validation import HELM_VARIANTS

    assert HELM_VARIANTS == (
        "helm_gated",
        "helm_gated_tvl",
        "helm_gated_tvl_confirmed",
    )


def test_build_helm_configs_offline_packages_named_return_series():
    from scripts.onchain_validation import build_helm_configs_offline

    idx = pd.date_range("2024-01-01", periods=50, freq="D")
    rng = np.random.default_rng(0)
    series = {
        name: pd.Series(rng.normal(0.001, 0.01, 50), index=idx)
        for name in (
            "helm_gated",
            "helm_gated_tvl",
            "helm_gated_tvl_confirmed",
            "equal_weight",
        )
    }
    configs = build_helm_configs_offline(series)
    # exactly the four named configs, each a per-day return Series
    assert set(configs.keys()) == set(series.keys())
    for name, s in configs.items():
        assert isinstance(s, pd.Series)
        assert len(s) == 50
    # the helm-variant subset is a subset of the keys (used for select_config)
    from scripts.onchain_validation import HELM_VARIANTS

    assert set(HELM_VARIANTS).issubset(set(configs.keys()))
