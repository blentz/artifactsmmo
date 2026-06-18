"""ceil_gathers: raw gather UNITS -> gather ACTIONS by per-gather drop yield."""

from artifactsmmo_cli.ai.gather_floor import ceil_gathers


def test_unit_yield_is_identity():
    """max_yield == 1 keeps the exact gather count (single-drop resources)."""
    for units in range(0, 25):
        assert ceil_gathers(units, 1) == units


def test_multi_yield_ceils():
    assert ceil_gathers(0, 3) == 0
    assert ceil_gathers(1, 3) == 1
    assert ceil_gathers(3, 3) == 1
    assert ceil_gathers(4, 3) == 2
    assert ceil_gathers(480, 3) == 160
    assert ceil_gathers(16, 2) == 8


def test_never_exceeds_units():
    """Sound lower bound: ceil(units/y) <= units for y >= 1."""
    for units in range(0, 50):
        for y in range(1, 6):
            assert ceil_gathers(units, y) <= units
