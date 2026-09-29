"""Differential test: Python `next_craft_target_pure` ≡ Lean `nextCraftTarget`.

Hypothesis property over random small acyclic recipe DAGs asserts that the
Python core and the kernel-proved Lean model agree on every input.

Encoding: recipes are sent as a JSON object {item: [[inp, per], ...], ...}.
The inputs ARRAY per item preserves Python dict insertion order (critical:
`nextHelper.find?` picks the FIRST short input, mirroring Python's
`for inp, per in recipe.items()`). The outer object's key order is irrelevant
(both sides do keyed lookup, not traversal).
"""

import random
from collections import OrderedDict

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.next_craft_core import NextAction, next_craft_target_pure
from formal.diff.obtain_source_scenarios import SIX_KINDS, scenario, sources_to_json
from formal.diff.oracle_client import run_oracle_structured

# Item universe: string codes "item0" .. "item{N-1}".
# Acyclicity: item i's inputs may only reference items with HIGHER index.
_N = 6


def _make_recipes(seed: int) -> dict[str, dict[str, int]]:
    """Build a random acyclic recipe set.

    Item "item{i}" may have 0–2 inputs, drawn only from items with higher
    indices (enforces acyclicity: higher index = deeper in DAG). Item "item0"
    is always the root target used in tests.
    """
    rng = random.Random(seed)
    recipes: dict[str, dict[str, int]] = {}
    for i in range(_N):
        pool = [f"item{j}" for j in range(i + 1, _N)]
        rng.shuffle(pool)
        k = rng.randint(0, min(2, len(pool)))
        if k == 0:
            continue  # raw item
        # Use OrderedDict to preserve insertion order (Python 3.7+ dicts do too,
        # but explicit is clearer for the encoding guarantee).
        recipes[f"item{i}"] = OrderedDict(
            (pool[m], rng.randint(1, 5)) for m in range(k)
        )
    return recipes


def _recipes_to_json(recipes: dict[str, dict[str, int]]) -> dict:
    """Encode recipes as a JSON-serialisable object {item: [[inp, per], ...]}.

    The inner list preserves the Python dict's insertion order, which must
    match `nextHelper.find?`'s traversal order.
    """
    return {
        item: [[inp, per] for inp, per in inputs.items()]
        for item, inputs in recipes.items()
    }


def _call_lean(
    recipes: dict[str, dict[str, int]],
    owned: dict[str, int],
    bank: dict[str, int],
    target: str,
    qty: int,
) -> dict | None:
    """Invoke the Lean oracle and return None or the result dict."""
    recipes_json = _recipes_to_json(recipes)
    owned_json = dict(owned)
    bank_json = dict(bank)
    fuel = len(recipes) + 1
    result = run_oracle_structured(
        "next_craft",
        [[recipes_json, owned_json, bank_json, target, qty, fuel]],
    )[0]
    # oracle returns JSON null as Python None
    if result is None:
        return None
    return result


def _assert_agree(
    py: NextAction | None,
    lean: dict | None,
    context: object,
) -> None:
    """Assert Python and Lean results agree."""
    if py is None:
        assert lean is None, f"Python→None but Lean→{lean!r}; ctx={context!r}"
    else:
        assert lean is not None, f"Python→{py!r} but Lean→None; ctx={context!r}"
        assert py.item == lean["item"], (
            f"item mismatch: {py.item!r} vs {lean['item']!r}; ctx={context!r}"
        )
        assert py.kind == lean["kind"], (
            f"kind mismatch: {py.kind!r} vs {lean['kind']!r}; ctx={context!r}"
        )
        assert py.qty == lean["qty"], (
            f"qty mismatch: {py.qty!r} vs {lean['qty']!r}; ctx={context!r}"
        )


# ---------------------------------------------------------------------------
# Hypothesis property
# ---------------------------------------------------------------------------


@settings(max_examples=400, deadline=None)
@given(
    recipe_seed=st.integers(min_value=0, max_value=10_000),
    owned_seed=st.integers(min_value=0, max_value=10_000),
    bank_seed=st.integers(min_value=0, max_value=10_000),
    qty=st.integers(min_value=0, max_value=10),
)
def test_next_craft_agrees(
    recipe_seed: int, owned_seed: int, bank_seed: int, qty: int
) -> None:
    """Python core ≡ Lean model on random acyclic DAGs WITH random banks.

    The random bank drives the `withdraw` branch on both sides; agreement on
    item/kind/qty (including kind == "withdraw") is what binds the Python core
    to the kernel-proved model.
    """
    recipes = _make_recipes(recipe_seed)
    rng = random.Random(owned_seed)
    owned = {
        f"item{i}": rng.randint(0, 20)
        for i in range(_N)
        if rng.random() < 0.5
    }
    brng = random.Random(bank_seed)
    bank = {
        f"item{i}": brng.randint(0, 20)
        for i in range(_N)
        if brng.random() < 0.5
    }
    target = "item0"
    py = next_craft_target_pure(recipes, owned, bank, target, qty)
    lean = _call_lean(recipes, owned, bank, target, qty)
    _assert_agree(py, lean, (recipe_seed, owned_seed, bank_seed, qty))


# ---------------------------------------------------------------------------
# Concrete copper_ring spot-check
# ---------------------------------------------------------------------------

_COPPER_RECIPES: dict[str, dict[str, int]] = {
    "copper_ring": {"copper_bar": 1},
    "copper_bar": {"copper_ore": 10},
}

_NO_BANK: dict[str, int] = {}


def test_copper_ring_gather_ore() -> None:
    """0 owned → first action = gather copper_ore (30 needed for 3 rings)."""
    owned: dict[str, int] = {}
    qty = 3
    py = next_craft_target_pure(_COPPER_RECIPES, owned, _NO_BANK, "copper_ring", qty)
    lean = _call_lean(_COPPER_RECIPES, owned, _NO_BANK, "copper_ring", qty)
    assert py == NextAction(item="copper_ore", kind="gather", qty=30)
    _assert_agree(py, lean, "copper_ring_0owned")


def test_copper_ring_craft_bar() -> None:
    """30 ore → next = craft copper_bar (need 3)."""
    owned = {"copper_ore": 30}
    qty = 3
    py = next_craft_target_pure(_COPPER_RECIPES, owned, _NO_BANK, "copper_ring", qty)
    lean = _call_lean(_COPPER_RECIPES, owned, _NO_BANK, "copper_ring", qty)
    assert py == NextAction(item="copper_bar", kind="craft", qty=3)
    _assert_agree(py, lean, "copper_ring_30ore")


def test_copper_ring_craft_ring() -> None:
    """30 ore + 3 bars → next = craft copper_ring (need 3)."""
    owned = {"copper_ore": 30, "copper_bar": 3}
    qty = 3
    py = next_craft_target_pure(_COPPER_RECIPES, owned, _NO_BANK, "copper_ring", qty)
    lean = _call_lean(_COPPER_RECIPES, owned, _NO_BANK, "copper_ring", qty)
    assert py == NextAction(item="copper_ring", kind="craft", qty=3)
    _assert_agree(py, lean, "copper_ring_all_inputs")


def test_copper_ring_satisfied() -> None:
    """Already own 3+ rings → None."""
    owned = {"copper_ring": 3}
    qty = 3
    py = next_craft_target_pure(_COPPER_RECIPES, owned, _NO_BANK, "copper_ring", qty)
    lean = _call_lean(_COPPER_RECIPES, owned, _NO_BANK, "copper_ring", qty)
    assert py is None
    _assert_agree(py, lean, "copper_ring_satisfied")


def test_copper_ring_partial_owned() -> None:
    """Partially own bars: 1 bar + 10 ore → need 2 more bars (20 more ore); gather."""
    owned = {"copper_bar": 1, "copper_ore": 10}
    qty = 3
    py = next_craft_target_pure(_COPPER_RECIPES, owned, _NO_BANK, "copper_ring", qty)
    lean = _call_lean(_COPPER_RECIPES, owned, _NO_BANK, "copper_ring", qty)
    # Need 2 more bars; each bar needs 10 ore; have 10 → still 10 short → gather.
    assert py == NextAction(item="copper_ore", kind="gather", qty=10)
    _assert_agree(py, lean, "copper_ring_partial")


def test_copper_ring_withdraw_banked_bar() -> None:
    """0 owned but 5 copper_bar BANKED → withdraw copper_bar (min(5, 3)=3), not a 30-ore gather.

    This is the non-vacuity guarantee that the differential exercises the new
    `withdraw` branch against the kernel-proved model — not just gather/craft.
    """
    owned: dict[str, int] = {}
    bank = {"copper_bar": 5}
    qty = 3
    py = next_craft_target_pure(_COPPER_RECIPES, owned, bank, "copper_ring", qty)
    lean = _call_lean(_COPPER_RECIPES, owned, bank, "copper_ring", qty)
    assert py == NextAction(item="copper_bar", kind="withdraw", qty=3)
    assert lean is not None and lean["kind"] == "withdraw"  # branch genuinely reached
    _assert_agree(py, lean, "copper_ring_withdraw")


def test_copper_ring_withdraw_capped_by_bank() -> None:
    """Bank holds fewer than needed: 2 banked bars, need 3 → withdraw min(2,3)=2."""
    owned: dict[str, int] = {}
    bank = {"copper_bar": 2}
    qty = 3
    py = next_craft_target_pure(_COPPER_RECIPES, owned, bank, "copper_ring", qty)
    lean = _call_lean(_COPPER_RECIPES, owned, bank, "copper_ring", qty)
    assert py == NextAction(item="copper_bar", kind="withdraw", qty=2)
    _assert_agree(py, lean, "copper_ring_withdraw_capped")


# ---------------------------------------------------------------------------
# SIX-source obtain model: exercise ALL six kinds through the widened oracle.
# ---------------------------------------------------------------------------


def _call_lean_sources(recipes, owned, bank, target, qty, sources) -> dict | None:
    """Invoke the widened oracle with a `sources` map (7th arg)."""
    fuel = len(recipes) + 1
    result = run_oracle_structured(
        "next_craft",
        [[_recipes_to_json(recipes), dict(owned), dict(bank), target, qty, fuel, sources_to_json(sources)]],
    )[0]
    return result if result is not None else None


def test_next_craft_all_six_kinds_agree() -> None:
    """Python `next_craft_target_pure(..., sources)` ≡ Lean over ALL six kinds.

    300 trials cycle the featured kind (gather/craft/withdraw/recycle/buy/drop)
    with rng-varied parameters; every trial asserts Python≡Lean, and the run
    asserts every one of the six kinds was genuinely emitted (a differential
    that only ever saw three kinds would agree vacuously).
    """
    rng = random.Random(20260714)
    seen: set[str] = set()
    for t in range(300):
        featured = SIX_KINDS[t % len(SIX_KINDS)]
        recipes, owned, bank, sources, target, qty = scenario(rng, featured)
        py = next_craft_target_pure(recipes, owned, bank, target, qty, sources)
        lean = _call_lean_sources(recipes, owned, bank, target, qty, sources)
        _assert_agree(py, lean, (t, featured))
        assert py is not None, f"trial {t} ({featured}) produced no action"
        seen.add(py.kind)
    assert seen == set(SIX_KINDS), f"kinds not all exercised: {seen}"


# ---------------------------------------------------------------------------
# Craft YIELD: a craft step is sized in RUNS, ⌈deficit / yield⌉ (2026-09-29).
# ---------------------------------------------------------------------------


def _random_yields(rng: random.Random, recipes: dict[str, dict[str, int]]) -> dict[str, int]:
    """Yields 0-3 for some craftable items; the rest absent. 0 and absent both
    read as 1 on both sides (`max(1, ...)` / `yields.get(item, 1)`), so they are
    kept in the draw on purpose."""
    return {item: rng.randint(0, 3) for item in recipes if rng.random() < 0.7}


def _call_lean_yields(recipes, owned, bank, target, qty, sources, yields) -> dict | None:
    fuel = len(recipes) + 1
    return run_oracle_structured(
        "next_craft",
        [[_recipes_to_json(recipes), dict(owned), dict(bank), target, qty, fuel,
          sources_to_json(sources), dict(yields)]],
    )[0]


@settings(max_examples=400, deadline=None)
@given(
    recipe_seed=st.integers(min_value=0, max_value=10_000),
    state_seed=st.integers(min_value=0, max_value=10_000),
    qty=st.integers(min_value=0, max_value=10),
)
def test_next_craft_agrees_with_yields(recipe_seed: int, state_seed: int, qty: int) -> None:
    """Python ≡ Lean when crafts yield more than one unit: the descent sizes a
    craft in runs and each input as `per * runs`."""
    recipes = _make_recipes(recipe_seed)
    rng = random.Random(state_seed)
    owned = {f"item{i}": rng.randint(0, 20) for i in range(_N) if rng.random() < 0.5}
    bank = {f"item{i}": rng.randint(0, 20) for i in range(_N) if rng.random() < 0.3}
    yields = _random_yields(rng, recipes)
    py = next_craft_target_pure(recipes, owned, bank, "item0", qty, None, None, yields)
    lean = _call_lean_yields(recipes, owned, bank, "item0", qty, {}, yields)
    _assert_agree(py, lean, (recipe_seed, state_seed, qty, yields))


def test_next_craft_yields_with_all_six_kinds_agree() -> None:
    """Yields on top of the six-source scenarios: Python ≡ Lean, and a yield
    above 1 genuinely changes some answer (the run would agree vacuously if the
    yield never reached a craft or an input size)."""
    rng = random.Random(20260929)
    changed = 0
    for t in range(300):
        featured = SIX_KINDS[t % len(SIX_KINDS)]
        recipes, owned, bank, sources, target, qty = scenario(rng, featured)
        yields = {item: rng.randint(1, 3) for item in recipes}
        py = next_craft_target_pure(recipes, owned, bank, target, qty, sources, None, yields)
        lean = _call_lean_yields(recipes, owned, bank, target, qty, sources, yields)
        _assert_agree(py, lean, (t, featured, yields))
        changed += py != next_craft_target_pure(recipes, owned, bank, target, qty, sources)
    assert changed > 0, "no trial's answer depended on a yield"


def test_copper_ring_yield_two_sizes_runs() -> None:
    """copper_bar yields 2: three rings need two bar-crafts, so 20 ore, and the
    craft step names 2 runs, not 3 bars."""
    yields = {"copper_bar": 2}
    py = next_craft_target_pure(_COPPER_RECIPES, {}, _NO_BANK, "copper_ring", 3, None, None, yields)
    assert py == NextAction("copper_ore", "gather", 20)
    py = next_craft_target_pure(_COPPER_RECIPES, {"copper_ore": 20}, _NO_BANK, "copper_ring", 3,
                                None, None, yields)
    assert py == NextAction("copper_bar", "craft", 2)
    lean = _call_lean_yields(_COPPER_RECIPES, {"copper_ore": 20}, _NO_BANK, "copper_ring", 3, {}, yields)
    _assert_agree(py, lean, "copper yield 2")
