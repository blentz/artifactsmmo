"""Differential: the live `effective_floor_multi` must agree with the proved
Lean `effectiveFloorMulti` on the JOINT reserve floor for a duplicate-free leaf
set. Codes are integers 0..n-1 (stringified on both sides); the buying set is
sampled as DISTINCT codes (the `List.Nodup` contract of the proved core)."""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.progression_reserve_core import (
    effective_floor,
    effective_floor_multi,
    reserve_total,
)
from formal.diff.oracle_client import run_oracle


def _oracle_args(reserved: dict[str, int], buying: list[int]) -> list[int]:
    pairs: list[int] = []
    for code, cost in reserved.items():
        pairs.extend([int(code), cost])
    return [len(reserved), *pairs, len(buying), *buying]


@settings(max_examples=400, deadline=None)
@given(
    costs=st.lists(st.integers(min_value=0, max_value=500), min_size=0, max_size=6),
    buying=st.lists(
        st.integers(min_value=0, max_value=8), min_size=0, max_size=6, unique=True
    ),
)
def test_floor_multi_matches_lean(costs, buying):
    reserved = {str(i): c for i, c in enumerate(costs)}
    py_buying = [str(b) for b in buying]
    py_floor = effective_floor_multi(reserved, py_buying)
    lean = run_oracle("progression_reserve_multi", [_oracle_args(reserved, buying)])[0]
    assert lean["floor_multi"] == py_floor, (reserved, buying, py_floor, lean)


@settings(max_examples=400, deadline=None)
@given(
    costs=st.lists(st.integers(min_value=0, max_value=500), min_size=1, max_size=6),
    x=st.integers(min_value=0, max_value=8),
)
def test_singleton_reduces_to_single_leaf(costs, x):
    """`effective_floor_multi(r, [x]) == effective_floor(r, x)` — the Python
    generalization claim, cross-checked against Lean's floor_multi arm."""
    reserved = {str(i): c for i, c in enumerate(costs)}
    key = str(x)
    py_single = effective_floor(reserved, key)
    py_multi = effective_floor_multi(reserved, [key])
    assert py_multi == py_single
    lean = run_oracle("progression_reserve_multi", [_oracle_args(reserved, [x])])[0]
    assert lean["floor_multi"] == py_single, (reserved, x, py_single, lean)


def test_joint_dedup_witness():
    """Two distinct reserved leaves bought together dedup BOTH reservations —
    the single-leaf floor would only dedup one, over-protecting the reserve."""
    reserved = {"0": 30, "1": 50}
    # Joint buy of {0,1}: floor = total(80) - 30 - 50 = 0.
    assert effective_floor_multi(reserved, ["0", "1"]) == 0
    # Single-leaf floor for either dedups only its own cost.
    assert effective_floor(reserved, "0") == 50
    assert effective_floor(reserved, "1") == 30
    lean = run_oracle("progression_reserve_multi",
                      [_oracle_args(reserved, [0, 1])])[0]
    assert lean["floor_multi"] == 0, lean
    # Floor-plus-cost identity holds for the distinct set.
    dedup = sum(reserved.get(b, 0) for b in ("0", "1"))
    assert effective_floor_multi(reserved, ["0", "1"]) + dedup == reserve_total(reserved)


def test_unreserved_leaves_protect_full_reserve():
    """Buying only leaves with no reservation credits nothing — the whole
    reserve is protected."""
    reserved = {"0": 40, "1": 60}
    assert effective_floor_multi(reserved, ["7", "8"]) == reserve_total(reserved)
    lean = run_oracle("progression_reserve_multi",
                      [_oracle_args(reserved, [7, 8])])[0]
    assert lean["floor_multi"] == 100, lean
