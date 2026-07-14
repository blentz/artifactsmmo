"""Differential test: real Python `prerequisites` (the data-derived ObtainItem
edge structure) and `combat_capable` (the `any` aggregation) must agree with the
proved Lean oracle over random recipe/drop tables and monster-beatable maps.

## prerequisites

For an UNSATISFIED `ObtainItem(code)`, `prerequisites` emits:
* if `recoverable.get(code, 0) > 0` (recycling licensed surplus can supply it,
  per `ai/recoverable_materials`) → NO prerequisites: a LEAF. The descent must
  not re-derive from raw resources what the bag already holds in crafted form;
* else if `code` has a recipe → one `ObtainItem(mat, qty)` per ingredient, in
  recipe order, and NOTHING else. The crafting-skill gate is no longer emitted as
  a prerequisite node (under-skill gear grinds planner-natively via the
  LevelSkill action, epic P3);
* else → no prerequisites (leaf). The old resource-drop → `ReachSkillLevel`
  branch is retired.

We use integer item codes (the model is `Nat`), a controlled fake GameData, and
a fake unsatisfied WorldState (empty inventory). We normalize the produced
`MetaGoal` list to comparable tuples and compare against the Lean oracle's
tagged-edge list over >= 200 random tables, randomizing the recoverable count per
trial so BOTH branches are exercised (asserted, not assumed) — including the
`> 0` boundary, where the code IS in the map at ZERO units and must still
descend.

## combat_capable

`combat_capable = any(predict_win(state, game_data, code) for code in
_monster_level)`. We monkeypatch `predict_win` to a controlled per-monster bool
and compare the `any()` result against the Lean oracle's `combatCapable` fold.
"""
import random
from types import SimpleNamespace

import artifactsmmo_cli.ai.tiers.prerequisite_graph as pg_mod
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.prerequisite_graph import combat_capable, prerequisites
from formal.diff.oracle_client import run_oracle


class _FakeStats:
    def __init__(self, crafting_skill: str | None, crafting_level: int,
                 type_: str | None = None):
        self.crafting_skill = crafting_skill
        self.crafting_level = crafting_level
        # `type_` only matters for the equippable-vs-resource branch in
        # ObtainItem.is_satisfied. None → falls through to the legacy
        # owned_count rule, preserving the original test semantics.
        self.type_ = type_


class _FakeGameData:
    """Exposes only the lookups `prerequisites` / `combat_capable` touch."""

    def __init__(self, recipe: dict[str, int] | None, stats: _FakeStats | None,
                 resource_drops: dict[str, str], resource_skill: dict[str, tuple[str, int]],
                 monster_level: dict[str, int]):
        self._recipe = recipe
        self._stats = stats
        self._resource_drops = resource_drops
        self._resource_skill = resource_skill
        self._monster_level = monster_level

    def crafting_recipe(self, code: str) -> dict[str, int] | None:
        return self._recipe

    def item_stats(self, code: str):
        return self._stats

    def resource_skill_level(self, code: str):
        return self._resource_skill.get(code)

    @property
    def resource_drops(self) -> dict[str, str]:
        return self._resource_drops

    @property
    def monster_levels(self) -> dict[str, int]:
        return self._monster_level


def _unsatisfied_state() -> SimpleNamespace:
    """A WorldState stand-in where every ObtainItem is unsatisfied (owned 0)."""
    return SimpleNamespace(inventory={}, bank_items=None, equipment={})


def _normalize_py(edges) -> list[tuple]:
    """MetaGoal list -> comparable tuples. The ObtainItem branch now emits ONLY
    ObtainItem(code,qty) edges, in produced ORDER (order-sensitive)."""
    out: list[tuple] = []
    for e in edges:
        if isinstance(e, ObtainItem):
            out.append(("item", int(e.code), int(e.quantity)))
        else:  # pragma: no cover - the ObtainItem branch emits only item edges
            raise AssertionError(f"unexpected edge {e!r}")
    return out


def _normalize_lean(lean: dict) -> list[tuple]:
    out: list[tuple] = []
    for e in lean["edges"]:
        out.append((e["kind"], int(e["a"]), int(e["b"])))
    return out


def _encode_prereq_args(recoverable_units: int, has_recipe: bool,
                        ingredients: list[tuple[int, int]]) -> list[int]:
    # The Lean model takes the GATE (`recoverable.get(code, 0) > 0`), not the
    # count: the boundary itself is what the differential must pin.
    args: list[int] = [1 if recoverable_units > 0 else 0,
                       1 if has_recipe else 0, len(ingredients)]
    for mat, qty in ingredients:
        args += [mat, qty]
    return args


def _build_prereq(rng: random.Random):
    """Random scenario hitting the recipe branch (item edges only), the leaf
    branch (no recipe) and the RECOVERABLE branch (recycling licensed surplus
    supplies the code → leaf). `recoverable_units` spans 0 (the `> 0` boundary:
    a code seen by recycling with ZERO licensed copies must still descend) and
    positive counts. Item codes are distinct so the Python recipe dict does not
    dedupe keys (the model keeps all edges)."""
    has_recipe = rng.random() < 0.6
    ingredients: list[tuple[int, int]] = []
    if has_recipe:
        n_ing = rng.randint(0, 4)
        mats = rng.sample(range(0, 21), n_ing)
        ingredients = [(mat, rng.randint(1, 9)) for mat in mats]
    code = rng.randint(0, 20)
    # 0 exercises the boundary; None means "code absent from the map entirely".
    recoverable_units = rng.choice([None, 0, 0, 1, 2, 18])
    return has_recipe, ingredients, code, recoverable_units


def _run_prereq(has_recipe, ingredients, code, recoverable_units=None):
    recipe = {str(mat): qty for mat, qty in ingredients} if has_recipe else None
    # item_stats only gates ObtainItem.is_satisfied (type_=None → owned-count
    # rule → unsatisfied on the empty state); prerequisites no longer reads the
    # crafting skill or any resource table.
    stats = _FakeStats(None, 0) if has_recipe else None
    gd = _FakeGameData(recipe, stats, {}, {}, {})
    recoverable = {} if recoverable_units is None else {str(code): recoverable_units}

    node = ObtainItem(str(code))
    py = _normalize_py(prerequisites(node, _unsatisfied_state(), gd, recoverable))

    args = _encode_prereq_args(recoverable_units or 0, has_recipe, ingredients)
    lean = _normalize_lean(run_oracle("prerequisite_graph", [args])[0])
    return py, lean


def test_prerequisites_matches_lean():
    rng = random.Random(20260527)
    seen_recoverable_leaf = 0
    seen_descent = 0
    for _ in range(240):
        scenario = _build_prereq(rng)
        py, lean = _run_prereq(*scenario)
        assert py == lean, f"prereq mismatch: scenario={scenario} py={py} lean={lean}"
        has_recipe, _ingredients, _code, units = scenario
        if has_recipe and (units or 0) > 0:
            seen_recoverable_leaf += 1
        elif has_recipe:
            seen_descent += 1
    # BOTH branches must actually be exercised — a differential that only ever
    # saw one of them would agree vacuously.
    assert seen_recoverable_leaf > 0 and seen_descent > 0, (
        f"branch coverage: recoverable={seen_recoverable_leaf} descent={seen_descent}")


def test_combat_capable_matches_lean(monkeypatch):
    rng = random.Random(777)
    for _ in range(240):
        n = rng.randint(0, 8)
        beatable = [rng.random() < 0.5 for _ in range(n)]
        monster_level = {str(i): rng.randint(1, 40) for i in range(n)}
        gd = _FakeGameData(None, None, {}, {}, monster_level)

        def fake_predict_win(state, game_data, code, _b=beatable):
            return _b[int(code)]

        monkeypatch.setattr(pg_mod, "predict_win", fake_predict_win)
        py = combat_capable(_unsatisfied_state(), gd)

        args = [n] + [1 if b else 0 for b in beatable]
        lean = run_oracle("combat_capable", [args])[0]["capable"]
        assert py == lean, f"combat mismatch: beatable={beatable} py={py} lean={lean}"


def test_recipe_branch_item_edges_only():
    """Concrete: craftable code 5, ingredients [(1,2),(3,4)], NOT recoverable.
    Edges = [item(1,2), item(3,4)] in order — NO skill edge. Pins recipe shape."""
    py, lean = _run_prereq(True, [(1, 2), (3, 4)], 5)
    assert py == [("item", 1, 2), ("item", 3, 4)]
    assert py == lean


def test_recipe_branch_no_ingredients_no_edges():
    """Concrete: craftable code 5 with an empty recipe ⇒ no edges."""
    py, lean = _run_prereq(True, [], 5)
    assert py == []
    assert py == lean


def test_leaf_branch_no_edges():
    """Concrete: non-craftable code 9 ⇒ leaf (no prerequisites)."""
    py, lean = _run_prereq(False, [], 9)
    assert py == []
    assert py == lean


def test_recoverable_craftable_is_a_leaf():
    """Concrete: the live 2026-07-13 shape — code 5 IS craftable with a real
    recipe, but 18 units are recoverable by recycling licensed surplus, so the
    descent stops. Both sides must drop the ingredient edges."""
    py, lean = _run_prereq(True, [(1, 2), (3, 4)], 5, 18)
    assert py == []
    assert py == lean


def test_zero_recoverable_still_descends():
    """Concrete boundary: the code IS in the recoverable map, at ZERO units. The
    gate is `> 0`, so the full recipe descent still happens (a `>= 0` mutation
    would collapse EVERY recipe to a leaf)."""
    py, lean = _run_prereq(True, [(1, 2), (3, 4)], 5, 0)
    assert py == [("item", 1, 2), ("item", 3, 4)]
    assert py == lean


def test_one_recoverable_unit_is_enough():
    """Concrete: ONE recoverable unit leafs, even against a recipe needing more.
    The rule is `> 0`, not "fully covers the need" — GOAP mixes recycle with
    gather/craft to make up the shortfall rather than facing an all-or-nothing
    cliff."""
    py, lean = _run_prereq(True, [(1, 9)], 5, 1)
    assert py == []
    assert py == lean
