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
    static += GATHER_LOADOUT_PENALTY * quantity   # 6.0, CONDITIONAL on mismatch

`base = 6.0`, `bankPenalty = _BANKED_REGATHER_PENALTY = 100.0` and
`loadPenalty = GATHER_LOADOUT_PENALTY = 6.0` are production CONSTANTS, not free
parameters — the Lean model's `gatherCost` keeps them general (matching
`Formal.ActionCostNonneg`'s `distanceCost`/`qtyCost` convention), so this
harness pins the oracle at the literals the real code actually uses.

Most tests here take the `mismatch = False` branch by targeting an
`unregistered_resource` code with no entry in `GameData`'s recipe catalog:
`resource_skill_level` returns `None`, so `cost()` never reaches the
`pick_loadout_cached` branch. `drop_item_override` is set for the same reason
on the drop-item side: `drop_item()` short-circuits on it before ever calling
`game_data.resource_drop_item`, so an empty `GameData()` is a completely
faithful stand-in for the real game-data cache for that branch.

The `mismatch = True` branch is exercised separately, from
`test_loadout_penalty_scales_with_quantity` down. It has to be: until
2026-08-13 the loadout penalty was charged ONCE PER ACTION rather than per
unit, and the Lean model omitted the term entirely on the grounds that a
quantity-independent constant could affect neither non-negativity nor
monotonicity. That was true of the model and false of the economics — a
constant term meant an `OptimizeLoadout` re-arm could recover at most 6.0
against a 10.0 swap at ANY batch size, so the proven 2026-07-05 gather re-arm
died the moment the goals began sizing their gathers. The term is now modeled
AND scaled, and pinned here rather than excluded: an excluded term is a term
that can drift.

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
import dataclasses
from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.equipment.loadout_cache import pick_loadout_cached
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Gather
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.world_state import WorldState
from formal.diff.oracle_client import run_oracle

_BASE = Fraction(6)
_PENALTY = Fraction(100)          # _BANKED_REGATHER_PENALTY
_LOAD_PENALTY = Fraction(6)       # GATHER_LOADOUT_PENALTY
_DROP_ITEM = "test_ore"
_RESOURCE = "unregistered_resource"  # absent from GameData(): resource_skill_level -> None
_MISMATCH_RESOURCE = "mismatch_rocks"  # HAS a gather skill, so the loadout branch is reached
_BETTER_TOOL = "good_pick"


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


def _lean_gather_cost(dist: int, qty: int, banked: int, mismatch: bool) -> Fraction:
    args = [_BASE.numerator, _BASE.denominator, dist, 1,
            _PENALTY.numerator, _PENALTY.denominator,
            _LOAD_PENALTY.numerator, _LOAD_PENALTY.denominator,
            qty, banked, 1 if mismatch else 0]
    res = run_oracle("gather_cost", [args])[0]
    return Fraction(res["cost_num"], res["cost_den"])


def _check(dist: int, qty: int, banked: int) -> float:
    action = GatherAction(resource_code=_RESOURCE, quantity=qty,
                          locations=frozenset({(dist, 0)}),
                          drop_item_override=_DROP_ITEM)
    state = _state(0, 0, banked)
    py_cost = action.cost(state, GameData(), history=None)
    lean_cost = _lean_gather_cost(dist, qty, banked, mismatch=False)
    assert Fraction(py_cost) == lean_cost, (dist, qty, banked, py_cost, lean_cost)
    # Direct formula pin, independent of the oracle.
    assert py_cost == (6.0 + dist) * qty + min(banked, qty) * 100.0
    return py_cost


def _mismatch_game_data() -> GameData:
    """A resource WITH a gather skill plus a better owned tool, so
    `pick_loadout_cached(Gather("mining"), ...)` returns
    `{weapon_slot: good_pick}` and differs from the (empty) equipped loadout —
    the exact condition the shipped `cost` tests before charging the penalty."""
    gd = GameData()
    gd._resource_skill = {_MISMATCH_RESOURCE: ("mining", 1)}
    gd._item_stats = {
        _BETTER_TOOL: ItemStats(code=_BETTER_TOOL, level=1, type_="weapon",
                                skill_effects={"mining": -10}),
    }
    return gd


def _check_mismatch(dist: int, qty: int, banked: int) -> float:
    """`_check`'s twin on the `mismatch = True` branch."""
    gd = _mismatch_game_data()
    action = GatherAction(resource_code=_MISMATCH_RESOURCE, quantity=qty,
                          locations=frozenset({(dist, 0)}),
                          drop_item_override=_DROP_ITEM)
    state = dataclasses.replace(_state(0, 0, banked),
                                inventory={_BETTER_TOOL: 1},
                                equipment={"weapon_slot": None})
    assert pick_loadout_cached(Gather("mining"), state, gd) == {"weapon_slot": _BETTER_TOOL}, (
        "fixture is vacuous: the loadout must actually MISMATCH, or this only "
        "re-exercises the branch _check already covers")
    py_cost = action.cost(state, gd, history=None)
    lean_cost = _lean_gather_cost(dist, qty, banked, mismatch=True)
    assert Fraction(py_cost) == lean_cost, (dist, qty, banked, py_cost, lean_cost)
    assert py_cost == (6.0 + dist) * qty + min(banked, qty) * 100.0 + 6.0 * qty
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


# ─── The loadout branch: modeled since 2026-08-13, and PER UNIT ─────────────


@settings(max_examples=200, deadline=None)
@given(
    dist=st.integers(min_value=0, max_value=100),
    qty=st.integers(min_value=0, max_value=100),
    banked=st.integers(min_value=0, max_value=100),
)
def test_mismatch_branch_matches_lean(dist, qty, banked):
    """The same sweep as `test_gather_cost_matches_lean`, on the branch where
    the loadout term is live."""
    _check_mismatch(dist, qty, banked)


def test_loadout_penalty_scales_with_quantity():
    """THE regression pin. A batch of 4 pays 4 x 6.0 of loadout penalty, not
    6.0. Under the once-per-action charge this cost 42.0 and the test would
    read `36 + 6`; the difference (18.0) is exactly what an `OptimizeLoadout`
    re-arm has to be able to recover, and what it could not recover while the
    term was constant."""
    py = _check_mismatch(dist=3, qty=4, banked=0)
    assert py == (6.0 + 3) * 4 + 6.0 * 4
    assert py == 60.0


def test_loadout_penalty_at_qty_one_is_the_singleton_charge():
    """`gather_cost_one_is_base`'s hypothesis on this branch: at qty=1 the
    scaled and the old unscaled formula COINCIDE — which is precisely why the
    defect was invisible for as long as nothing set a quantity above 1."""
    py = _check_mismatch(dist=4, qty=1, banked=0)
    assert py == (6.0 + 4) * 1 + 6.0
    assert py == 16.0


def test_loadout_and_banked_penalties_compose():
    """Both conditional terms live at once, and neither absorbs the other:
    min(banked, qty) units carry the bank penalty while ALL qty units carry
    the loadout penalty."""
    py = _check_mismatch(dist=1, qty=10, banked=4)
    assert py == (6.0 + 1) * 10 + 4 * 100.0 + 6.0 * 10
    assert py == 530.0


def test_loadout_term_vanishes_at_qty_zero():
    """A zero-quantity batch costs 0 on this branch too — every term of the
    formula, including the loadout term, scales with qty."""
    assert _check_mismatch(dist=10, qty=0, banked=5) == 0.0


def test_batch_parity_against_the_singleton_chain():
    """`Formal.GatherCost.gather_cost_batch_parity` at runtime: with the bank
    covering the whole batch, ONE batched edge of size qty costs EXACTLY qty
    singleton edges.

    NOTE the `banked == qty` fixture — that is the theorem's real `qty <= banked`
    hypothesis, and it is why this test alone CANNOT pin the re-arm: full-cost
    parity is false below it (the bank term is deliberately not neutral for
    banked < qty), and `banked = 0` is the live configuration of the 2026-07-05
    defect. `test_loadout_term_parity_at_an_empty_bank` covers that corner."""
    qty = 5
    batched = _check_mismatch(dist=3, qty=qty, banked=qty)
    singleton = _check_mismatch(dist=3, qty=1, banked=1)
    assert batched == qty * singleton
    assert batched == 5 * ((6.0 + 3) + 100.0 + 6.0)


@settings(max_examples=200, deadline=None)
@given(
    dist=st.integers(min_value=0, max_value=100),
    qty=st.integers(min_value=0, max_value=100),
    banked=st.integers(min_value=0, max_value=100),
)
def test_loadout_term_parity_is_unconditional(dist, qty, banked):
    """`Formal.GatherCost.gather_cost_loadout_parity` at runtime, over the whole
    grid including `banked = 0`: the cost decomposes term-by-term, and the
    loadout residual is ALWAYS exactly qty copies of the singleton charge —
    no `qty <= banked` side condition anywhere.

    This is the property the gather re-arm depends on. Under the once-per-action
    charge the residual was a constant 6.0 instead of `6.0 * qty`, so an
    OptimizeLoadout could never recover more than one unit's worth at any batch
    size."""
    with_mismatch = _check_mismatch(dist, qty, banked)
    without = _check(dist, qty, banked)
    assert with_mismatch - without == 6.0 * qty
    assert without == (6.0 + dist) * qty + min(banked, qty) * 100.0


def test_loadout_term_parity_at_an_empty_bank():
    """The corner `gather_cost_batch_parity` cannot reach, named explicitly:
    a bot gathering a material it holds NONE of. 5 units of batch pay 5 units
    of penalty (30.0), not one (6.0) — a 24.0 spread, comfortably more than the
    10.0 one-slot swap an OptimizeLoadout re-arm costs, which is precisely why
    the re-arm is chosen again."""
    batched = _check_mismatch(dist=3, qty=5, banked=0)
    unpenalized = _check(dist=3, qty=5, banked=0)
    assert batched - unpenalized == 30.0
    assert batched == (6.0 + 3) * 5 + 0.0 + 6.0 * 5
    assert batched == 75.0


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
