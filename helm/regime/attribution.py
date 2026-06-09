"""Per-feature attribution for a regime read.

Each feature's contribution is the product of its standardized value and the
regime signature's standardized value for that feature (a dot-product term).
Contributions are normalized so their absolute values sum to 1, keeping sign.
"""


def attribute(features_z: dict, signature_z: dict) -> dict:
    """Signed contribution fraction per feature.

    contribution[f] = features_z[f] * signature_z[f]
    then divided by sum_f |contribution[f]| (equal zeros if that sum is 0).
    Only keys present in BOTH dicts are used.
    """
    keys = [k for k in features_z if k in signature_z]
    raw = {k: float(features_z[k]) * float(signature_z[k]) for k in keys}
    total = sum(abs(v) for v in raw.values())
    if total <= 0.0:
        return {k: 0.0 for k in keys}
    return {k: v / total for k, v in raw.items()}
