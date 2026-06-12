"""Curated BSC exchange hot-wallet addresses for the CEX-flow proxy.

Each address is the lower-cased BEP-20 hot wallet of a major centralized
exchange on BNB Smart Chain. Transfers whose RECEIVER is one of these is an
inflow (deposit -> typically pre-sell / distribution); whose SENDER is one of
these is an outflow (withdrawal -> typically accumulation). Sources are cited
per address. The Binance entries are verified live (2026-06-11) to return CEX
inflow/outflow hits for CAKE through the Bitquery adapter.

Provenance: addresses are widely-published exchange labels. The two Binance
wallets below are the canonical hot wallets referenced across BscScan label
clouds and the Bitquery spike brief; the remaining exchange wallets are
published hot-wallet labels. Keep this list conservative (precision over
recall): a non-exchange address mislabeled here would corrupt the CEX-flow
signal, whereas a missing wallet only mildly under-counts flow.
"""

BSC_EXCHANGE_WALLETS: dict[str, list[str]] = {
    # Binance — canonical BSC hot wallets (verified to return live hits, spike
    # 2026-06-11). Widely published BscScan labels "Binance: Hot Wallet".
    "binance": [
        "0x8894e0a0c962cb723c1976a4421c95949be2d4e3",  # Binance: Hot Wallet
        "0xf977814e90da44bfa03b6295a0616a897441acec",  # Binance: Hot Wallet 20
        "0x5a52e96bacdabb82fd05763e25335261b270efcb",  # Binance: Hot Wallet (BSC)
        "0xe2fc31f816a9b94326492132018c3aecc4a93ae1",  # Binance: Hot Wallet (BSC)
    ],
    # OKX — published BSC hot-wallet labels ("OKX" on BscScan).
    "okx": [
        "0x2c8fbb630289363ac80705a1a61273f76fd5a161",  # OKX (BSC)
    ],
    # Gate.io — published BSC hot-wallet label.
    "gate": [
        "0x0d0707963952f2fba59dd06f2b425ace40b492fe",  # Gate.io (BSC)
    ],
    # Bybit — published BSC hot-wallet label.
    "bybit": [
        "0xf89d7b9c864f589bbf53a82105107622b35eaa40",  # Bybit (BSC)
    ],
}

# Flat, de-duplicated list (order-preserving) for the inflow/outflow `in:` filter.
ALL_EXCHANGE_WALLETS: list[str] = list(
    dict.fromkeys(a for addrs in BSC_EXCHANGE_WALLETS.values() for a in addrs)
)
