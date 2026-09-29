"""Differential test: Python `craft_plan_full` ≡ Lean `craftPlan`.

A Hypothesis property over random small acyclic recipe DAGs WITH random
inventories and banks asserts the Python full-plan driver and the kernel-proved
Lean model emit the identical ordered plan (gather/withdraw/craft). A second
property empirically confirms the proved `craftPlan_reaches` conclusion: executing
the emitted plan reaches the target.
"""

import random
from collections import OrderedDict

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.craft_plan_driver_core import _apply_state, craft_plan_full
from artifactsmmo_cli.ai.next_craft_core import NextAction
from formal.diff.obtain_source_scenarios import SIX_KINDS, scenario, sources_to_json
from formal.diff.oracle_client import run_oracle_structured

_N = 6


def _make_recipes(seed: int) -> dict[str, dict[str, int]]:
    rng = random.Random(seed)
    recipes: dict[str, dict[str, int]] = {}
    for i in range(_N):
        pool = [f"item{j}" for j in range(i + 1, _N)]
        rng.shuffle(pool)
        k = rng.randint(0, min(2, len(pool)))
        if k == 0:
            continue
        recipes[f"item{i}"] = OrderedDict((pool[m], rng.randint(1, 4)) for m in range(k))
    return recipes


def _recipes_to_json(recipes: dict[str, dict[str, int]]) -> dict:
    return {item: [[inp, per] for inp, per in inputs.items()] for item, inputs in recipes.items()}


def _fuel(recipes: dict[str, dict[str, int]], qty: int) -> int:
    return (len(recipes) + 1) * (qty + 1) + 1


def _call_lean(recipes, owned, bank, target, qty) -> list[dict]:
    result = run_oracle_structured(
        "craft_plan",
        [[_recipes_to_json(recipes), dict(owned), dict(bank), target, qty, _fuel(recipes, qty)]],
    )[0]
    return result  # JSON array of {item,kind,qty}


def _assert_agree(py: list[NextAction], lean: list[dict], ctx: object) -> None:
    assert len(py) == len(lean), f"length {len(py)} vs {len(lean)}; ctx={ctx!r}"
    for i, (a, b) in enumerate(zip(py, lean, strict=True)):
        assert a.item == b["item"] and a.kind == b["kind"] and a.qty == b["qty"], (
            f"step {i}: {a!r} vs {b!r}; ctx={ctx!r}"
        )


@settings(max_examples=400, deadline=None)
@given(
    recipe_seed=st.integers(min_value=0, max_value=10_000),
    owned_seed=st.integers(min_value=0, max_value=10_000),
    bank_seed=st.integers(min_value=0, max_value=10_000),
    qty=st.integers(min_value=0, max_value=6),
)
def test_craft_plan_agrees(recipe_seed, owned_seed, bank_seed, qty) -> None:
    """Python full-plan driver ≡ Lean craftPlan on random DAGs + inventories + banks."""
    recipes = _make_recipes(recipe_seed)
    org = random.Random(owned_seed)
    owned = {f"item{i}": org.randint(0, 12) for i in range(_N) if org.random() < 0.5}
    brg = random.Random(bank_seed)
    bank = {f"item{i}": brg.randint(0, 12) for i in range(_N) if brg.random() < 0.5}
    py = craft_plan_full(recipes, owned, bank, "item0", qty)
    lean = _call_lean(recipes, owned, bank, "item0", qty)
    _assert_agree(py, lean, (recipe_seed, owned_seed, bank_seed, qty))


@settings(max_examples=300, deadline=None)
@given(
    recipe_seed=st.integers(min_value=0, max_value=10_000),
    owned_seed=st.integers(min_value=0, max_value=10_000),
    bank_seed=st.integers(min_value=0, max_value=10_000),
    qty=st.integers(min_value=1, max_value=6),
)
def test_craft_plan_reaches_target(recipe_seed, owned_seed, bank_seed, qty) -> None:
    """Executing the emitted plan reaches the target (empirical craftPlan_reaches)."""
    recipes = _make_recipes(recipe_seed)
    org = random.Random(owned_seed)
    owned = {f"item{i}": org.randint(0, 12) for i in range(_N) if org.random() < 0.5}
    brg = random.Random(bank_seed)
    bank = {f"item{i}": brg.randint(0, 12) for i in range(_N) if brg.random() < 0.5}
    plan = craft_plan_full(recipes, owned, bank, "item0", qty)
    cur_o, cur_b = dict(owned), dict(bank)
    for na in plan:
        cur_o, cur_b = _apply_state(recipes, cur_o, cur_b, na)
    assert cur_o.get("item0", 0) >= qty, (
        f"plan did not reach target: {cur_o.get('item0',0)} < {qty}; "
        f"ctx={(recipe_seed, owned_seed, bank_seed, qty)!r}"
    )


def test_shared_intermediate_chain() -> None:
    """Spot-check the shared-intermediate (consuming) case against the oracle."""
    recipes = {"item0": {"item1": 1, "item2": 1}, "item1": {"item3": 1}, "item2": {"item3": 1}}
    py = craft_plan_full(recipes, {}, {}, "item0", 1)
    lean = _call_lean(recipes, {}, {}, "item0", 1)
    _assert_agree(py, lean, "shared")
    assert sum(1 for na in py if na.kind == "gather") == 2  # item3 gathered twice


# ---------------------------------------------------------------------------
# SIX-source obtain model: full-plan agreement + reaches over ALL six kinds.
# ---------------------------------------------------------------------------


def _call_lean_sources(recipes, owned, bank, target, qty, sources) -> list[dict]:
    """Invoke the widened craft_plan oracle with a `sources` map (7th arg)."""
    return run_oracle_structured(
        "craft_plan",
        [
            [
                _recipes_to_json(recipes),
                dict(owned),
                dict(bank),
                target,
                qty,
                _fuel(recipes, qty),
                sources_to_json(sources),
            ]
        ],
    )[0]


def test_craft_plan_all_six_kinds_agree_and_reach() -> None:
    """Python `craft_plan_full(..., sources)` ≡ Lean AND the executed plan reaches
    the target, over ALL six kinds.

    300 trials cycle the featured kind with rng-varied parameters (including the
    recycle live-bound exhaustion MIXED plan). Every trial asserts Python≡Lean
    step-for-step and that executing the plan with `_apply_state(..., sources)`
    reaches `owned[target] >= qty` (the empirical `craftPlan_reaches` over the
    widened, RECYCLE-debiting model). The run asserts every kind was emitted.
    """
    rng = random.Random(20260715)
    seen: set[str] = set()
    for t in range(300):
        featured = SIX_KINDS[t % len(SIX_KINDS)]
        recipes, owned, bank, sources, target, qty = scenario(rng, featured)
        py = craft_plan_full(recipes, owned, bank, target, qty, sources)
        lean = _call_lean_sources(recipes, owned, bank, target, qty, sources)
        _assert_agree(py, lean, (t, featured))
        cur_o, cur_b = dict(owned), dict(bank)
        for na in py:
            cur_o, cur_b = _apply_state(recipes, cur_o, cur_b, na, sources)
        assert cur_o.get(target, 0) >= qty, (
            f"plan did not reach target: {cur_o.get(target, 0)} < {qty}; trial={t} ({featured})"
        )
        for na in py:
            seen.add(na.kind)
    assert seen == set(SIX_KINDS), f"kinds not all exercised: {seen}"


# ---------------------------------------------------------------------------
# Craft YIELD: a craft step is RUNS and the fold credits `runs * yield`.
# ---------------------------------------------------------------------------


def _call_lean_yields(recipes, owned, bank, target, qty, sources, yields) -> list[dict]:
    return run_oracle_structured(
        "craft_plan",
        [[_recipes_to_json(recipes), dict(owned), dict(bank), target, qty, _fuel(recipes, qty),
          sources_to_json(sources), dict(yields)]],
    )[0]


@settings(max_examples=300, deadline=None)
@given(
    recipe_seed=st.integers(min_value=0, max_value=10_000),
    state_seed=st.integers(min_value=0, max_value=10_000),
    qty=st.integers(min_value=0, max_value=6),
)
def test_craft_plan_agrees_and_reaches_with_yields(recipe_seed, state_seed, qty) -> None:
    """Python ≡ Lean step for step with random yields, and executing the plan
    with the same yields reaches the target."""
    recipes = _make_recipes(recipe_seed)
    rng = random.Random(state_seed)
    owned = {f"item{i}": rng.randint(0, 12) for i in range(_N) if rng.random() < 0.5}
    bank = {f"item{i}": rng.randint(0, 12) for i in range(_N) if rng.random() < 0.3}
    yields = {item: rng.randint(0, 3) for item in recipes if rng.random() < 0.7}
    py = craft_plan_full(recipes, owned, bank, "item0", qty, None, yields)
    lean = _call_lean_yields(recipes, owned, bank, "item0", qty, {}, yields)
    _assert_agree(py, lean, (recipe_seed, state_seed, qty, yields))
    cur_o, cur_b = dict(owned), dict(bank)
    for na in py:
        cur_o, cur_b = _apply_state(recipes, cur_o, cur_b, na, None, yields)
    assert cur_o.get("item0", 0) >= qty


def test_craft_plan_yields_with_all_six_kinds_agree_and_reach() -> None:
    rng = random.Random(20260930)
    changed = 0
    for t in range(300):
        featured = SIX_KINDS[t % len(SIX_KINDS)]
        recipes, owned, bank, sources, target, qty = scenario(rng, featured)
        yields = {item: rng.randint(1, 3) for item in recipes}
        py = craft_plan_full(recipes, owned, bank, target, qty, sources, yields)
        lean = _call_lean_yields(recipes, owned, bank, target, qty, sources, yields)
        _assert_agree(py, lean, (t, featured, yields))
        cur_o, cur_b = dict(owned), dict(bank)
        for na in py:
            cur_o, cur_b = _apply_state(recipes, cur_o, cur_b, na, sources, yields)
        assert cur_o.get(target, 0) >= qty, (t, featured, yields)
        changed += py != craft_plan_full(recipes, owned, bank, target, qty, sources)
    assert changed > 0, "no trial's plan depended on a yield"


def test_copper_ring_yield_two_plan() -> None:
    """Three rings, copper_bar yields 2: gather 20 ore, 2 bar-runs, 3 rings;
    the fold leaves 1 spare bar (the Lean witness, on the Python side)."""
    recipes = {"copper_ring": {"copper_bar": 1}, "copper_bar": {"copper_ore": 10}}
    yields = {"copper_bar": 2}
    py = craft_plan_full(recipes, {}, {}, "copper_ring", 3, None, yields)
    assert [(na.item, na.kind, na.qty) for na in py] == [
        ("copper_ore", "gather", 20), ("copper_bar", "craft", 2), ("copper_ring", "craft", 3)]
    cur_o: dict[str, int] = {}
    cur_b: dict[str, int] = {}
    for na in py:
        cur_o, cur_b = _apply_state(recipes, cur_o, cur_b, na, None, yields)
    assert (cur_o["copper_ring"], cur_o["copper_bar"], cur_o["copper_ore"]) == (3, 1, 0)
    _assert_agree(py, _call_lean_yields(recipes, {}, {}, "copper_ring", 3, {}, yields), "copper y2")
