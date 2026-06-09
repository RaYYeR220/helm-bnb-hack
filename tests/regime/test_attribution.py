from helm.regime.attribution import attribute


def test_aligned_feature_dominates():
    features_z = {"trend_strength": 2.0, "realized_vol": -0.1,
                  "breadth": 0.2, "dispersion": 0.0}
    signature_z = {"trend_strength": 2.0, "realized_vol": -0.05,
                   "breadth": 0.3, "dispersion": 0.0}
    attr = attribute(features_z, signature_z)
    # trend_strength's contribution dwarfs the others
    assert abs(attr["trend_strength"]) > abs(attr["breadth"])
    assert abs(attr["trend_strength"]) > abs(attr["realized_vol"])


def test_abs_contributions_sum_to_one():
    features_z = {"a": 1.0, "b": -2.0, "c": 0.5}
    signature_z = {"a": 1.0, "b": 1.0, "c": -1.0}
    attr = attribute(features_z, signature_z)
    assert abs(sum(abs(v) for v in attr.values()) - 1.0) < 1e-9


def test_sign_is_preserved():
    # feature opposes its signature -> negative contribution
    features_z = {"a": -3.0, "b": 0.0}
    signature_z = {"a": 2.0, "b": 1.0}
    attr = attribute(features_z, signature_z)
    assert attr["a"] < 0.0


def test_all_zero_returns_equal_zeros():
    features_z = {"a": 0.0, "b": 0.0}
    signature_z = {"a": 0.0, "b": 0.0}
    attr = attribute(features_z, signature_z)
    assert attr == {"a": 0.0, "b": 0.0}


def test_only_shared_keys_are_used():
    features_z = {"a": 1.0, "b": 1.0, "extra": 99.0}
    signature_z = {"a": 1.0, "b": 1.0}
    attr = attribute(features_z, signature_z)
    assert set(attr) == {"a", "b"}
