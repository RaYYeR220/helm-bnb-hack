import importlib

import pandas as pd


def test_backfill_script_imports_and_exposes_main_and_helpers():
    mod = importlib.import_module("scripts.onchain_backfill")
    assert hasattr(mod, "main")
    assert callable(mod.main)
    assert hasattr(mod, "dex_volume_panel")
    assert callable(mod.dex_volume_panel)
    assert hasattr(mod, "BSC_TOKEN_ADDRESSES")


def test_address_map_covers_all_eight_majors():
    from scripts.onchain_backfill import BSC_TOKEN_ADDRESSES
    from helm.data.universe import MAJORS

    assert set(BSC_TOKEN_ADDRESSES.keys()) == set(MAJORS)
    # all 0x-prefixed 42-char BEP-20 addresses
    for sym, addr in BSC_TOKEN_ADDRESSES.items():
        assert addr.startswith("0x")
        assert len(addr) == 42


def test_address_map_pins_known_contracts():
    from scripts.onchain_backfill import BSC_TOKEN_ADDRESSES

    assert BSC_TOKEN_ADDRESSES["CAKE"] == "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82"
    assert BSC_TOKEN_ADDRESSES["ETH"] == "0x2170ed0880ac9a755fd29b2688956bd959f933f8"


class _FakeCache:
    """Returns a single-column volume frame per dexvol key; None for others."""

    def __init__(self, present):
        self._present = present  # dict symbol -> pd.Series

    def get_series(self, key):
        if not key.startswith("dexvol_"):
            return None
        sym = key[len("dexvol_"):]
        return self._present.get(sym)


def test_dex_volume_panel_assembles_present_symbols_only():
    from scripts.onchain_backfill import dex_volume_panel

    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    cache = _FakeCache(
        {
            "ETH": pd.Series([1.0, 2.0, 3.0], index=idx, name="volume"),
            "CAKE": pd.Series([4.0, 5.0, 6.0], index=idx, name="volume"),
        }
    )
    panel = dex_volume_panel(cache, ["ETH", "CAKE", "DOGE"])
    assert list(panel.columns) == ["ETH", "CAKE"]  # DOGE missing -> skipped
    assert list(panel["ETH"]) == [1.0, 2.0, 3.0]
    assert list(panel["CAKE"]) == [4.0, 5.0, 6.0]


def test_dex_volume_panel_empty_when_nothing_cached():
    from scripts.onchain_backfill import dex_volume_panel

    panel = dex_volume_panel(_FakeCache({}), ["ETH", "CAKE"])
    assert panel.empty
