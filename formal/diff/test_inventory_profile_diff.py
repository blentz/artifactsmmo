"""Differential test: real Python `overstock_excess` (the space-driven, profile-
preserving overstock core in `src/artifactsmmo_cli/ai/inventory_caps.py`) must
agree bit-for-bit with the proved Lean `overstockExcess` /
`underPressure` (formal/Formal/InventoryProfile.lean).

This bridges the model↔code gap for the per-goal inventory-profile design
(spec 2026-06-07): the live function computing whether to shed inventory is the
SAME function the kernel proved space-driven (free slots ⇒ no overstock),
profile-protecting (held ≤ target ⇒ never overstock), and monotone.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.inventory_caps import overstock_excess
from formal.diff.oracle_client import run_oracle


@settings(max_examples=400)
@given(
    held=st.integers(min_value=0, max_value=200),
    profile_target=st.integers(min_value=0, max_value=200),
    useful_floor=st.integers(min_value=0, max_value=200),
    used=st.integers(min_value=0, max_value=200),
    cap=st.integers(min_value=0, max_value=200),
    # Vary the watermark across the full ratio range (incl. degenerate 0/x and
    # x/x) so the cross-multiplication boundary is exercised, not just 17/20.
    watermark_num=st.integers(min_value=0, max_value=20),
    watermark_den=st.integers(min_value=1, max_value=20),
)
def test_python_matches_lean(held, profile_target, useful_floor, used, cap,
                             watermark_num, watermark_den):
    py = overstock_excess(held, profile_target, useful_floor, used, cap,
                          watermark_num, watermark_den)
    lean = run_oracle(
        "inventory_profile",
        [[held, profile_target, useful_floor, used, cap,
          watermark_num, watermark_den]],
    )[0]
    assert py == lean["excess"], (
        f"excess mismatch: py={py} lean={lean['excess']} "
        f"held={held} target={profile_target} floor={useful_floor} "
        f"used={used} cap={cap} wm={watermark_num}/{watermark_den}"
    )
    # The under-pressure flag is the gate; check it agrees too (a Python
    # mutation that flips the pressure comparison is then killed).
    py_pressure = cap > 0 and used * watermark_den >= cap * watermark_num
    assert py_pressure == lean["under_pressure"], (
        f"pressure mismatch: py={py_pressure} lean={lean['under_pressure']}"
    )


def test_profile_protection_binds_against_lean():
    """Deterministic: at full pressure, held == profile_target (floor 0) is
    NOT overstock; the SAME inputs with target 0 ARE overstock. Pins the
    profile-protection theorem against the live function (kills a 'drop the
    profile floor' mutant the random search may miss)."""
    protected = run_oracle("inventory_profile", [[10, 10, 0, 20, 20, 17, 20]])[0]
    unprotected = run_oracle("inventory_profile", [[10, 0, 0, 20, 20, 17, 20]])[0]
    assert overstock_excess(10, 10, 0, 20, 20, 17, 20) == protected["excess"] == 0
    assert overstock_excess(10, 0, 0, 20, 20, 17, 20) == unprotected["excess"] == 10


def test_space_driven_binds_against_lean():
    """Deterministic: 16/20 = 80% (below the 17/20 watermark) ⇒ 0 overstock
    even with held 100 over floor 0. Pins the space-driven theorem (kills a
    'drop the watermark gate' mutant)."""
    lean = run_oracle("inventory_profile", [[100, 0, 0, 16, 20, 17, 20]])[0]
    assert overstock_excess(100, 0, 0, 16, 20, 17, 20) == lean["excess"] == 0
    # One slot fuller (17/20) flips it on.
    lean_on = run_oracle("inventory_profile", [[100, 0, 0, 17, 20, 17, 20]])[0]
    assert overstock_excess(100, 0, 0, 17, 20, 17, 20) == lean_on["excess"] == 100
