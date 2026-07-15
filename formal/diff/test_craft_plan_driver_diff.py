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
