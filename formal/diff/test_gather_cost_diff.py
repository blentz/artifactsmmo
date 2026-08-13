"""Differential test: real `GatherAction.cost` (the BATCHED gather edge) must
agree EXACTLY with the proved Lean `Formal.GatherCost.gatherCost`.

Task 5 (`5b0c9c37`) gave `GatherAction` a `quantity` and made its cost scale
with it. A* optimality rests on every edge cost being non-negative
(`Formal.ActionCostNonneg`); multiplying by a planner-chosen quantity is
exactly where that could break, so `Formal.GatherCost` proves it rather than
assuming it, and this harness pins the real Python against that proof.

The shipped `GatherAction.cost` (history=None branch) computes:

    static = (6.0 + dist) * quantity
    static += min(banked, quantity) * _BANKED_REGATHER_PENALTY   # 100.0
    static += GATHER_LOADOUT_PENALTY                              # conditional, unscaled

`base = 6.0` and `penalty = _BANKED_REGATHER_PENALTY = 100.0` are production
CONSTANTS, not free parameters — the Lean model's `gatherCost` keeps them
general (matching `Formal.ActionCostNonneg`'s `distanceCost`/`qtyCost`
convention), so this harness pins the oracle at the two literals the real code
actually uses.

The loadout penalty is EXCLUDED from both the harness and the Lean model (see
`Formal/GatherCost.lean`'s docstring): every test here targets an
`unregistered_resource` code with no entry in `GameData`'s recipe catalog, so
`resource_skill_level` returns `None` and `cost()` never reaches the
`pick_loadout_cached` branch that would add it. `drop_item_override` is set
for the same reason on the drop-item side: `drop_item()` short-circuits on it
before ever calling `game_data.resource_drop_item`, so an empty `GameData()`
is a completely faithful stand-in for the real game-data cache for this
formula.

`history=None` is passed throughout (the docstring-declared boundary):
`GatherAction.cost` returns `learned_cost_pure(static, 0.0, 1.0,
has_history=False) == static` on that branch — exactly the static term
`gatherCost` models. The `LearningStore`-blended branch is covered by
`Formal.ActionCostNonneg.learnedCost_nonneg`, not here.

Since every input to the formula is an integer (`base`, `dist`, `penalty` are
all whole numbers in production; `quantity`/`banked` are `Nat`), the result is
always an exact integer-valued float — so Python and Lean are compared via
`Fraction`, which catches any drift bit-exactly rather than accepting
floating-point slop.
"""
from fractions import Fraction

import pytest
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState
from formal.diff.oracle_client import run_oracle

_BASE = Fraction(6)
_PENALTY = Fraction(100)
_DROP_ITEM = "test_ore"
_RESOURCE = "unregistered_resource"  # absent from GameData(): resource_skill_level -> None


def _state(x: int, y: int, banked: int) -> WorldState:
    """Minimal WorldState shell for `GatherAction.cost`, mirroring
    `test_action_cost_nonneg_diff.py`'s `_state` helper plus a controllable
    `bank_items` entry for `_DROP_ITEM`."""
    return WorldState(
        character="t", level=10, xp=0, max_xp=100,
        hp=50, max_hp=100, gold=100,
        skills={}, x=x, y=y,
        inventory={}, inventory_max=100,
        inventory_slots_max=100,
        equipment={}, cooldown_expires=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        bank_items=({_DROP_ITEM: banked} if banked else {}), bank_gold=0, pending_items=(),
    )


def _lean_gather_cost(dist: int, qty: int, banked: int) -> Fraction:
    args = [_BASE.numerator, _BASE.denominator, dist, 1,
            _PENALTY.numerator, _PENALTY.denominator, qty, banked]
    res = run_oracle("gather_cost", [args])[0]
    return Fraction(res["cost_num"], res["cost_den"])


def _check(dist: int, qty: int, banked: int) -> float:
    action = GatherAction(resource_code=_RESOURCE, quantity=qty,
                          locations=frozenset({(dist, 0)}),
                          drop_item_override=_DROP_ITEM)
    state = _state(0, 0, banked)
    py_cost = action.cost(state, GameData(), history=None)
    lean_cost = _lean_gather_cost(dist, qty, banked)
    assert Fraction(py_cost) == lean_cost, (dist, qty, banked, py_cost, lean_cost)
    # Direct formula pin, independent of the oracle.
    assert py_cost == (6.0 + dist) * qty + min(banked, qty) * 100.0
    return py_cost


# ─── Property-based sweep over the declared grid ─────────────────────────────


@settings(max_examples=300, deadline=None)
@given(
    dist=st.integers(min_value=0, max_value=200),
    qty=st.integers(min_value=0, max_value=100),
    banked=st.integers(min_value=0, max_value=100),
)
def test_gather_cost_matches_lean(dist, qty, banked):
    _check(dist, qty, banked)


# ─── Boundary cases named explicitly, per the task brief ────────────────────


def test_qty_zero():
    """A zero-quantity batch (constructible even though the planner never
    emits one via `is_applicable`) costs exactly 0: both terms scale with qty."""
    assert _check(dist=10, qty=0, banked=5) == 0.0


def test_qty_one_no_banked():
    """The pre-batching singleton edge, no bank interaction."""
    assert _check(dist=4, qty=1, banked=0) == 10.0  # (6+4)*1 + 0


def test_qty_one_with_banked():
    """`gather_cost_one_is_base`'s exact hypothesis: qty=1, banked >= 1."""
    assert _check(dist=4, qty=1, banked=3) == 110.0  # (6+4)*1 + 1*100


def test_banked_zero():
    """No bank coverage at all: the penalty term is fully absent regardless
    of quantity."""
    assert _check(dist=2, qty=20, banked=0) == 160.0  # (6+2)*20 + 0


def test_banked_exceeds_qty():
    """`banked > qty`: the penalty term is capped at `qty` units (the whole
    batch is covered by the bank), never at `banked`."""
    py = _check(dist=1, qty=5, banked=50)
    assert py == (6.0 + 1) * 5 + 5 * 100.0  # min(50, 5) = 5, not 50
    assert py == 535.0


def test_banked_equals_qty():
    """`banked == qty`: the boundary between `min` picking `banked` and
    picking `qty` — both sides agree exactly at equality."""
    py = _check(dist=0, qty=8, banked=8)
    assert py == 6.0 * 8 + 8 * 100.0
    assert py == 848.0


def test_banked_partial_shortfall():
    """`0 < banked < qty`: only the covered prefix is penalized, the
    remaining deficit gathers carry no penalty."""
    py = _check(dist=3, qty=10, banked=4)
    assert py == (6.0 + 3) * 10 + 4 * 100.0  # min(4, 10) = 4
    assert py == 490.0


def test_large_quantity():
    """A large batch (deep into planner territory: many cycles' worth of
    material demand in one edge) still agrees bit-exactly."""
    py = _check(dist=15, qty=5000, banked=200)
    assert py == (6.0 + 15) * 5000 + 200 * 100.0
    assert py == 125000.0


def test_zero_distance():
    """Standing on the node already (`dist = 0`): only the base rate scales."""
    assert _check(dist=0, qty=6, banked=0) == 36.0  # 6*6


# ─── Monotonicity: a bigger batch is never cheaper ───────────────────────────
# Runtime mirror of `Formal.GatherCost.gather_cost_monotone`: the property that
# stops the planner manufacturing a cheaper plan by inflating a quantity.


@settings(max_examples=200, deadline=None)
@given(
    dist=st.integers(min_value=0, max_value=100),
    q1=st.integers(min_value=0, max_value=100),
    extra=st.integers(min_value=0, max_value=100),
    banked=st.integers(min_value=0, max_value=100),
)
def test_monotone_in_quantity(dist, q1, extra, banked):
    q2 = q1 + extra
    cost1 = _check(dist, q1, banked)
    cost2 = _check(dist, q2, banked)
    assert cost1 <= cost2


# ─── History-blended branch: excluded from this model, delegated instead ────


def test_history_none_is_exactly_static():
    """Pins the documented boundary: `history=None` returns the bare static
    term this whole file models, with no learned-cost blending at all."""
    action = GatherAction(resource_code=_RESOURCE, quantity=7,
                          locations=frozenset({(3, 0)}), drop_item_override=_DROP_ITEM)
    state = _state(0, 0, banked=2)
    static = action.cost(state, GameData(), history=None)
    assert static == (6.0 + 3) * 7 + 2 * 100.0


@pytest.mark.parametrize("qty,banked,dist", [(0, 0, 0), (1, 1, 1), (1000, 1000, 500)])
def test_negative_inputs_are_unreachable_by_construction(qty, banked, dist):
    """`quantity` and `bank_items` counts are never negative in production
    (`effective_quantity` and the server-reported bank both bottom out at 0),
    so the Lean model's `Nat` domain for `qty`/`banked` is the right one — this
    is a smoke check that the non-negative corner (including the coincident
    qty=banked=dist point) still agrees, not a claim the negative corner is
    reachable."""
    assert _check(dist, qty, banked) >= 0.0
