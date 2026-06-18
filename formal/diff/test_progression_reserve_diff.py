"""Differential: the live `progression_reserve_core` must agree with the proved
Lean `ProgressionReserve` on the effective floor and the affordability decision.
Codes are integers 0..n-1 (stringified on both sides); buying = -1 encodes
None / a non-reserved code."""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.progression_reserve_core import affordable, effective_floor
from formal.diff.oracle_client import run_oracle


def _oracle_args(reserved: dict[str, int], gold: int, price: int, buying: int) -> list[int]:
    pairs: list[int] = []
    for code, cost in reserved.items():
        pairs.extend([int(code), cost])
    return [len(reserved), *pairs, gold, price, buying]


@settings(max_examples=300, deadline=None)
@given(
    costs=st.lists(st.integers(min_value=0, max_value=500), min_size=0, max_size=6),
    gold=st.integers(min_value=0, max_value=5000),
    price=st.integers(min_value=0, max_value=2000),
    buying=st.integers(min_value=-1, max_value=8),
)
def test_floor_and_affordable_match_lean(costs, gold, price, buying):
    reserved = {str(i): c for i, c in enumerate(costs)}
    py_buying = None if buying < 0 else str(buying)
    py_floor = effective_floor(reserved, py_buying)
    py_aff = affordable(gold, price, reserved, py_buying)
    lean = run_oracle("progression_reserve",
                      [_oracle_args(reserved, gold, price, buying)])[0]
    assert lean["floor"] == py_floor, (reserved, buying, py_floor, lean)
    assert lean["affordable"] == py_aff, (reserved, gold, price, buying, py_aff, lean)


def test_reserved_item_deduction_witness():
    reserved = {"0": 30, "1": 50}
    # buying reserved "0": floor 50; gold 80 affordable, 79 not.
    assert effective_floor(reserved, "0") == 50
    lean = run_oracle("progression_reserve", [_oracle_args(reserved, 80, 30, 0)])[0]
    assert lean["floor"] == 50 and lean["affordable"] is True
    lean2 = run_oracle("progression_reserve", [_oracle_args(reserved, 79, 30, 0)])[0]
    assert lean2["affordable"] is False
