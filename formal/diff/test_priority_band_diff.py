"""Differential test: real Python `clamp_into_band` must agree with the proved
Lean `clampIntoBand`, and the proven band invariant must hold on the Python side.

`clamp_into_band(floor, ceiling, bonus)` clamps `floor + bonus` into
`[floor, ceiling]`. We generate integer `(floor, ceiling, bonus)` triples
(including negative bonus, and arrange `floor <= ceiling` so the band invariant
holds), assert the Python result equals the Lean oracle, AND assert the proven
invariant `floor <= result <= ceiling` directly on the Python value.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.priority_band import clamp_into_band
from formal.diff.oracle_client import run_oracle


@settings(max_examples=300)
@given(
    floor=st.integers(min_value=-1000, max_value=1000),
    # ceiling >= floor: a real discretionary band; built as floor + nonneg span.
    span=st.integers(min_value=0, max_value=2000),
    # bonus may be negative, zero, or arbitrarily large in magnitude.
    bonus=st.integers(min_value=-5000, max_value=5000),
)
def test_python_matches_lean(floor, span, bonus):
    ceiling = floor + span
    py = clamp_into_band(floor, ceiling, bonus)
    lean = run_oracle("priority_band", [[floor, ceiling, bonus]])[0]
    assert py == lean["clamped"]
    # The proven band invariant: result never escapes [floor, ceiling].
    assert floor <= py <= ceiling


def test_large_negative_bonus_clamps_to_floor_against_lean():
    """A hugely negative bonus (e.g. a run of observed-negative char_xp) cannot
    push priority below the floor — pins the lower clamp against Lean."""
    lean = run_oracle("priority_band", [[30, 45, -100000]])[0]
    assert clamp_into_band(30, 45, -100000) == 30 == lean["clamped"]


def test_large_positive_bonus_clamps_to_ceiling_against_lean():
    """A hugely positive bonus cannot push priority above the ceiling (so it can
    never reach the survival floor 70) — pins the upper clamp against Lean."""
    lean = run_oracle("priority_band", [[30, 45, 100000]])[0]
    assert clamp_into_band(30, 45, 100000) == 45 == lean["clamped"]
    assert lean["clamped"] < 70  # below the survival floor, by construction
