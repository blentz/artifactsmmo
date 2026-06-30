from artifactsmmo_cli.ai import thresholds


def test_critical_hp_fraction_value():
    assert thresholds.CRITICAL_HP_FRACTION == 0.75


def test_float_views_equal_legacy_literals():
    # These MUST equal the old re-typed literals exactly (no behavior change).
    assert thresholds.CRAFT_RELIEF_FRACTION == 0.70
    assert thresholds.PRESSURE_HIGH_FRACTION == 0.85
    assert thresholds.DEPOSIT_FULL_FRACTION == 0.90
    assert thresholds.PRESSURE_CRITICAL_FRACTION == 0.95


def test_float_views_equal_their_rationals():
    assert thresholds.CRAFT_RELIEF_FRACTION == thresholds.CRAFT_RELIEF_NUM / thresholds.CRAFT_RELIEF_DEN
    assert thresholds.PRESSURE_HIGH_FRACTION == thresholds.PRESSURE_HIGH_NUM / thresholds.PRESSURE_HIGH_DEN
    assert thresholds.DEPOSIT_FULL_FRACTION == thresholds.DEPOSIT_FULL_NUM / thresholds.DEPOSIT_FULL_DEN
    assert thresholds.PRESSURE_CRITICAL_FRACTION == thresholds.PRESSURE_CRITICAL_NUM / thresholds.PRESSURE_CRITICAL_DEN


def test_ladder_strictly_ascending():
    assert (thresholds.CRAFT_RELIEF_FRACTION
            < thresholds.PRESSURE_HIGH_FRACTION
            < thresholds.DEPOSIT_FULL_FRACTION
            < thresholds.PRESSURE_CRITICAL_FRACTION)


def test_pressure_high_pair_is_the_extracted_watermark():
    # The pair Lean mirrors (was inventory_caps DISCARD_WATERMARK_NUM/DEN).
    assert (thresholds.PRESSURE_HIGH_NUM, thresholds.PRESSURE_HIGH_DEN) == (17, 20)
