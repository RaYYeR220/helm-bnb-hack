from helm.data.exchange_wallets import (
    ALL_EXCHANGE_WALLETS,
    BSC_EXCHANGE_WALLETS,
)


def test_table_is_non_empty_and_has_binance():
    assert isinstance(BSC_EXCHANGE_WALLETS, dict)
    assert len(BSC_EXCHANGE_WALLETS) >= 1
    assert "binance" in BSC_EXCHANGE_WALLETS
    assert len(BSC_EXCHANGE_WALLETS["binance"]) >= 2


def test_every_address_is_lowercase_hex():
    for exchange, addrs in BSC_EXCHANGE_WALLETS.items():
        assert isinstance(addrs, list)
        assert len(addrs) >= 1
        for a in addrs:
            assert a == a.lower(), f"{exchange} address not lower-cased: {a}"
            assert a.startswith("0x")
            assert len(a) == 42  # 0x + 40 hex chars


def test_known_binance_hot_wallets_present():
    # the two wallets verified to return live CEX-flow hits in the spike
    binance = set(BSC_EXCHANGE_WALLETS["binance"])
    assert "0x8894e0a0c962cb723c1976a4421c95949be2d4e3" in binance
    assert "0xf977814e90da44bfa03b6295a0616a897441acec" in binance


def test_all_exchange_wallets_is_flattened_and_complete():
    flat = []
    for addrs in BSC_EXCHANGE_WALLETS.values():
        flat.extend(addrs)
    assert set(ALL_EXCHANGE_WALLETS) == set(flat)
    # no address lost; flat list is non-empty and itself lower-cased
    assert len(ALL_EXCHANGE_WALLETS) == len(set(ALL_EXCHANGE_WALLETS))
    assert all(a == a.lower() for a in ALL_EXCHANGE_WALLETS)
