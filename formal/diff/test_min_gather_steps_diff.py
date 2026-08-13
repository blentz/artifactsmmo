"""The live `min_gather_steps` (Python) must agree with the extracted Lean core
`Extracted.MinGatherSteps.min_gather_steps` on every input — and the batched
bound it computes must never exceed the per-unit `min_gathers` bound, the
property proved in `Formal.MinGatherStepsBound.minGatherSteps_le_minGathers`.

`min_gather_steps` counts DISTINCT raw leaves (one batched `GatherAction` serves
one material's whole deficit); `min_gathers` counts raw UNITS. Both thread and
CONSUME the same `owned` holdings depth-first, in the same sibling order, under
the same `len(recipes) + 1` fuel — so the two recursions walk the SAME call tree
and differ only in the accumulator. That shared shape is what the Lean proof
exploits, and it is what this harness pins: a divergence in either the leaf
accounting or the holdings threading shows up as a mismatch here.

The generators deliberately include CYCLIC recipe tables. A cycle is the only
way to reach the fuel-exhausted arm, which is the one arm where the two cores'
accounting genuinely differs (the batched core files the item as a leaf without
consulting `qty`, the per-unit core adds `qty`). It is also where the proof's
`PosRecipes` hypothesis becomes load-bearing — see
`test_zero_demand_breaks_the_bound`, which pins the counterexample rather than
pretending the bound is unconditional.

Item codes and recipe demands go over the wire as Nats; the two QUANTITY fields
(`qty` and each owned holding) are SIGNED, because both the Python and the Lean
core take `int` and the `qty <= 0` / `held < 0` arms are reachable in the model
even though the planner does not construct them. `test_negative_*` drive those
arms so agreement is pinned there too rather than assumed.
"""
import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.gather_floor import ceil_gathers
from artifactsmmo_cli.ai.min_gather_steps import min_gather_steps
from artifactsmmo_cli.ai.min_gathers import min_gathers
from formal.diff.oracle_client import run_oracle

_N = 6


def _oracle_args(recipes: dict[int, dict[int, int]], owned: dict[int, int],
                 item: int, qty: int) -> list[int]:
    triples: list[int] = []
    n = 0
    for parent, recipe in recipes.items():
        for sub, per in recipe.items():
            triples.extend([parent, sub, per])
            n += 1
    owned_pairs: list[int] = []
    no = 0
    for code, q in owned.items():
        owned_pairs.extend([code, q])
        no += 1
    return [n, *triples, no, *owned_pairs, item, qty]


def _make_dag(seed: int) -> dict[int, dict[int, int]]:
    """Random acyclic table over items 0..N-1 (children strictly greater)."""
    rng = random.Random(seed)
    recipes: dict[int, dict[int, int]] = {}
    for item in range(_N):
        free = list(range(item + 1, _N))
        rng.shuffle(free)
        k = rng.randint(0, min(3, len(free)))
        if k == 0:
            continue
        recipes[item] = {j: rng.randint(1, 4) for j in free[:k]}
    return recipes


def _make_cyclic(seed: int) -> dict[int, dict[int, int]]:
    """Random table with NO acyclicity constraint — a material may point back at
    an ancestor, so the fuel bound is what terminates the recursion."""
    rng = random.Random(seed)
    recipes: dict[int, dict[int, int]] = {}
    for item in range(_N):
        if rng.random() < 0.25:
            continue
        k = rng.randint(1, 3)
        recipes[item] = {rng.randrange(_N): rng.randint(1, 4) for _ in range(k)}
    return recipes


def _check(recipes: dict[int, dict[int, int]], owned: dict[int, int],
           item: int, qty: int) -> tuple[int, int]:
    py_steps = min_gather_steps(item, qty, recipes, dict(owned))
    py_gathers = min_gathers(item, qty, recipes, dict(owned))
    lean = run_oracle("min_gather_steps", [_oracle_args(recipes, owned, item, qty)])[0]
    assert lean["steps"] == py_steps, (recipes, owned, item, qty, py_steps, lean)
    assert lean["gathers"] == py_gathers, (recipes, owned, item, qty, py_gathers, lean)
    # The proved bound, re-checked on live data (both sides at once).
    assert py_steps <= py_gathers, (recipes, owned, item, qty, py_steps, py_gathers)
    return py_steps, py_gathers


@settings(max_examples=300, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000),
    owned_seed=st.integers(min_value=0, max_value=10_000),
    item=st.integers(min_value=0, max_value=_N - 1),
    qty=st.integers(min_value=0, max_value=12),
)
def test_dag_matches_lean(seed, owned_seed, item, qty):
    recipes = _make_dag(seed)
    rng = random.Random(owned_seed)
    owned = {i: rng.randint(0, 12) for i in range(_N) if rng.random() < 0.5}
    _check(recipes, owned, item, qty)


@settings(max_examples=300, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000),
    owned_seed=st.integers(min_value=0, max_value=10_000),
    item=st.integers(min_value=0, max_value=_N - 1),
    qty=st.integers(min_value=0, max_value=12),
)
def test_cyclic_matches_lean(seed, owned_seed, item, qty):
    """Same agreement over CYCLIC tables: the fuel-exhausted arm is reachable
    only here, and it is the arm the two cores account for differently."""
    recipes = _make_cyclic(seed)
    rng = random.Random(owned_seed)
    owned = {i: rng.randint(0, 12) for i in range(_N) if rng.random() < 0.5}
    _check(recipes, owned, item, qty)


def test_two_level_chain_is_one_leaf():
    """The whole point of the batched bound: 1 sword <- 6 iron <- 60 ore is ONE
    gather ACTION, against 60 raw units. Deterministic kill for a mutant that
    counted units, or that counted interior (craftable) nodes as leaves."""
    recipes = {0: {1: 6}, 1: {2: 10}}
    steps, gathers = _check(recipes, {}, 0, 1)
    assert (steps, gathers) == (1, 60)


def test_shared_leaf_counted_once():
    """Two parents claiming the SAME raw leaf still cost one batched gather —
    the leaf list is de-duplicated. Kills a mutant that appended
    unconditionally."""
    recipes = {0: {1: 2, 2: 3}, 1: {3: 5}, 2: {3: 7}}
    steps, gathers = _check(recipes, {}, 0, 1)
    assert steps == 1
    assert gathers == 31  # 2*5 + 3*7 units of item 3


def test_holdings_cover_everything():
    """Owned stock that covers the demand yields zero of BOTH bounds — the
    consume-threading must fire identically on both sides."""
    recipes = {0: {1: 6}, 1: {2: 10}}
    steps, gathers = _check(recipes, {1: 6}, 0, 1)
    assert (steps, gathers) == (0, 0)


def test_partial_holdings_still_one_leaf():
    """A partial cover reduces the UNIT count but not the ACTION count: the
    remaining deficit is still exactly one batched gather."""
    recipes = {0: {1: 6}, 1: {2: 10}}
    steps, gathers = _check(recipes, {1: 5}, 0, 1)
    assert (steps, gathers) == (1, 10)


def test_cycle_terminates_and_agrees():
    """A self-referential table: fuel, not acyclicity, is what stops the
    recursion, and both cores stop at the same place."""
    recipes = {0: {1: 1}, 1: {0: 1}}
    _check(recipes, {}, 0, 1)


def test_zero_demand_breaks_the_bound():
    """The proof's `PosRecipes` hypothesis is LOAD-BEARING, not decoration.

    With a zero-demand material inside a cycle the fuel-exhausted arm files a
    leaf the per-unit core never counts (it adds `qty = 0`), and the batched
    bound EXCEEDS the per-unit one. Real API recipes have positive quantities,
    so the planner cannot build this — but the theorem states the hypothesis
    rather than assuming it silently, and this test is why.
    """
    recipes = {0: {1: 1, 2: 0}, 1: {0: 1}}
    py_steps = min_gather_steps(0, 1, recipes, {})
    py_gathers = min_gathers(0, 1, recipes, {})
    assert (py_steps, py_gathers) == (2, 1)
    assert py_steps > py_gathers
    lean = run_oracle("min_gather_steps", [_oracle_args(recipes, {}, 0, 1)])[0]
    assert (lean["steps"], lean["gathers"]) == (py_steps, py_gathers)


@pytest.mark.parametrize("qty", [-1, -7])
def test_negative_qty_agrees(qty):
    """A non-positive `qty` fails the `remaining <= 0` guard immediately: both
    bounds are 0, on both sides. Pins the guard's boundary from below, which the
    non-negative generators cannot reach."""
    recipes = {0: {1: 3}, 1: {2: 4}}
    assert _check(recipes, {}, 0, qty) == (0, 0)


def test_negative_holding_inflates_the_demand():
    """A NEGATIVE holding makes `used = min(held, qty)` negative, so
    `remaining = qty - used` EXCEEDS `qty` — a debt the model charges back.
    Reachable arm, driven on both sides: with -5 of item 1 held, a 1-unit demand
    becomes 6, so 6*4 = 24 units of the raw leaf, still ONE batched gather."""
    recipes = {0: {1: 1}, 1: {2: 4}}
    steps, gathers = _check(recipes, {1: -5}, 0, 1)
    assert (steps, gathers) == (1, 24)


def test_negative_holding_with_zero_qty_still_gathers():
    """`qty = 0` against a negative holding still leaves positive `remaining`,
    so the qty <= 0 case is NOT a blanket short-circuit. Both cores must agree
    on that or the guard's semantics have drifted."""
    recipes = {0: {1: 2}}
    steps, gathers = _check(recipes, {0: -3}, 0, 0)
    assert (steps, gathers) == (1, 6)


def test_batched_bound_can_exceed_the_ceiled_unit_bound():
    """SCOPE LIMIT of `minGatherSteps_le_minGathers`, pinned on the Python side.

    The theorem compares the leaf count against the RAW-UNIT count. Production's
    mint term is `ceil_gathers(min_gathers(...), max_gather_yield)`. At
    max_gather_yield 1 those coincide; above it they do not — a demand spread
    over three distinct materials is 3 batched gather actions against a ceiled
    unit score of 1. So the switch is NOT more permissive everywhere: for
    multi-yield resources the gate tightens. Sound (three materials really do
    need three actions), but a behaviour change, not a non-event.
    """
    recipes = {0: {1: 1, 2: 1, 3: 1}}
    steps, gathers = _check(recipes, {}, 0, 1)
    assert (steps, gathers) == (3, 3)
    assert ceil_gathers(gathers, 1) == 3      # yield 1: the proved ordering holds
    assert ceil_gathers(gathers, 5) == 1      # yield 5: the new bound is LARGER
    assert steps > ceil_gathers(gathers, 5)


@pytest.mark.parametrize("qty", [0, 1, 2, 7, 40])
def test_qty_scaling_agrees(qty):
    """Quantity scales the UNIT bound but never the ACTION bound above the leaf
    count — pinned across the qty = 0 boundary."""
    recipes = {0: {1: 3}, 1: {2: 4}}
    steps, gathers = _check(recipes, {}, 0, qty)
    assert steps == (0 if qty <= 0 else 1)
    assert gathers == 12 * max(qty, 0)
