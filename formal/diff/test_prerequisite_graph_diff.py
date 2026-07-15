"""Differential test: real Python `prerequisites` (the data-derived ObtainItem
edge structure) and `combat_capable` (the `any` aggregation) must agree with the
proved Lean oracle over random recipe/drop tables and monster-beatable maps.

## prerequisites

For an UNSATISFIED `ObtainItem(code)`, `prerequisites` emits:
* if the code has a READY non-craft `ai/obtain_sources` route (a bank withdraw,
  a recyclable licensed surplus, a live gather, a located permanent vendor, or a
  winnable drop) → NO prerequisites: a LEAF. The descent must not re-derive from
  raw resources what a ready route already covers;
* else if `code` has a recipe → one `ObtainItem(mat, qty)` per ingredient, in
  recipe order, and NOTHING else. The crafting-skill gate is no longer emitted as
  a prerequisite node (under-skill gear grinds planner-natively via the
  LevelSkill action, epic P3);
* else → no prerequisites (leaf). The old resource-drop → `ReachSkillLevel`
  branch is retired.

The Lean model (`Formal.PrerequisiteGraph.prereqEdges`) takes this as a plain
boolean GATE — it never cared what produced the flag (originally the
recycle-as-acquisition epic's bespoke `recoverable.get(code, 0) > 0` map; now
the one-obtain-model epic's `obtain_sources` route existence). We drive the
gate through a REAL `GameData` GATHER route (the simplest ready non-craft
source to construct: two dict assignments, no state/inventory interaction) so
the harness exercises the actual production wiring `prerequisites` now
consumes, not a hand-injected map.

We use integer item codes (the model is `Nat`), a real `GameData` with only the
looked-up tables populated, and a fake unsatisfied WorldState (empty
inventory). We normalize the produced `MetaGoal` list to comparable tuples and
compare against the Lean oracle's tagged-edge list over >= 200 random tables,
randomizing whether a ready source exists per trial so BOTH branches are
exercised (asserted, not assumed).

## combat_capable

`combat_capable = any(predict_win(state, game_data, code) for code in
_monster_level)`. We monkeypatch `predict_win` to a controlled per-monster bool
and compare the `any()` result against the Lean oracle's `combatCapable` fold.
"""
import random
from types import SimpleNamespace

import artifactsmmo_cli.ai.tiers.prerequisite_graph as pg_mod
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.prerequisite_graph import combat_capable, prerequisites
from formal.diff.oracle_client import run_oracle


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


def _encode_prereq_args(ready_source: bool, has_recipe: bool,
                        ingredients: list[tuple[int, int]]) -> list[int]:
    # The Lean model takes the plain GATE — it is agnostic to what drives it.
    args: list[int] = [1 if ready_source else 0,
                       1 if has_recipe else 0, len(ingredients)]
    for mat, qty in ingredients:
        args += [mat, qty]
    return args


def _build_prereq(rng: random.Random):
    """Random scenario hitting the recipe branch (item edges only), the leaf
    branch (no recipe), and the READY-SOURCE branch (a live GATHER route
    supplies the code → leaf). Item codes are distinct so the Python recipe
    dict does not dedupe keys (the model keeps all edges)."""
    has_recipe = rng.random() < 0.6
    ingredients: list[tuple[int, int]] = []
    if has_recipe:
        n_ing = rng.randint(0, 4)
        mats = rng.sample(range(0, 21), n_ing)
        ingredients = [(mat, rng.randint(1, 9)) for mat in mats]
    code = rng.randint(0, 20)
    ready_source = rng.random() < 0.5
    return has_recipe, ingredients, code, ready_source


def _run_prereq(has_recipe, ingredients, code, ready_source=False):
    gd = GameData()
    if has_recipe:
        recipe = {str(mat): qty for mat, qty in ingredients}
        gd._crafting_recipes = {str(code): recipe}
        # item_stats only gates ObtainItem.is_satisfied (type_="" -> falls
        # through to the owned-count rule -> unsatisfied on the empty state)
        # and `obtain_sources`' CRAFT arm (crafting_skill=None -> no CRAFT
        # source, so a ready-source scenario is driven ONLY by the GATHER arm
        # below, never accidentally by CRAFT).
        gd._item_stats = {str(code): ItemStats(code=str(code), level=1, type_="")}
    if ready_source:
        # The simplest ready non-craft `ai/obtain_sources` route to construct:
        # a resource whose primary drop IS `code`, with a live tile. Neither
        # assignment touches state/inventory, so it can never accidentally
        # trip the ObtainItem "already owned" short-circuit prerequisites
        # checks before the recipe/obtain_sources check is even reached.
        res = f"res_{code}"
        gd._resource_drops = {res: str(code)}
        gd._resource_locations = {res: [(0, 0)]}

    node = ObtainItem(str(code))
    py = _normalize_py(prerequisites(node, _unsatisfied_state(), gd, NO_PROFILE_CONTEXT))

    args = _encode_prereq_args(ready_source, has_recipe, ingredients)
    lean = _normalize_lean(run_oracle("prerequisite_graph", [args])[0])
    return py, lean


def test_prerequisites_matches_lean():
    rng = random.Random(20260527)
    seen_ready_source_leaf = 0
    seen_descent = 0
    for _ in range(240):
        scenario = _build_prereq(rng)
        py, lean = _run_prereq(*scenario)
        assert py == lean, f"prereq mismatch: scenario={scenario} py={py} lean={lean}"
        has_recipe, _ingredients, _code, ready_source = scenario
        if has_recipe and ready_source:
            seen_ready_source_leaf += 1
        elif has_recipe:
            seen_descent += 1
    # BOTH branches must actually be exercised — a differential that only ever
    # saw one of them would agree vacuously.
    assert seen_ready_source_leaf > 0 and seen_descent > 0, (
        f"branch coverage: ready_source_leaf={seen_ready_source_leaf} descent={seen_descent}")


def test_combat_capable_matches_lean(monkeypatch):
    rng = random.Random(777)
    for _ in range(240):
        n = rng.randint(0, 8)
        beatable = [rng.random() < 0.5 for _ in range(n)]
        gd = GameData()
        gd._monster_level = {str(i): rng.randint(1, 40) for i in range(n)}

        def fake_predict_win(state, game_data, code, _b=beatable):
            return _b[int(code)]

        monkeypatch.setattr(pg_mod, "predict_win", fake_predict_win)
        py = combat_capable(_unsatisfied_state(), gd)

        args = [n] + [1 if b else 0 for b in beatable]
        lean = run_oracle("combat_capable", [args])[0]["capable"]
        assert py == lean, f"combat mismatch: beatable={beatable} py={py} lean={lean}"


def test_recipe_branch_item_edges_only():
    """Concrete: craftable code 5, ingredients [(1,2),(3,4)], no ready source.
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


def test_ready_source_craftable_is_a_leaf():
    """Concrete: the live 2026-07-13 shape (generalized) — code 5 IS craftable
    with a real recipe, but a live GATHER route supplies it directly, so the
    descent stops. Both sides must drop the ingredient edges."""
    py, lean = _run_prereq(True, [(1, 2), (3, 4)], 5, ready_source=True)
    assert py == []
    assert py == lean


def test_absent_ready_source_still_descends():
    """Concrete: no ready source at all ⇒ the full recipe descent happens (the
    inverted-predicate mutation would collapse EVERY recipe to a leaf)."""
    py, lean = _run_prereq(True, [(1, 2), (3, 4)], 5, ready_source=False)
    assert py == [("item", 1, 2), ("item", 3, 4)]
    assert py == lean


def test_a_ready_source_is_enough_regardless_of_recipe_size():
    """Concrete: a ready source leafs even against a recipe needing many more
    units than any one application could deliver — capacity accounting is
    `ai/obtain_sources`' concern, not this layer's. GOAP mixes the ready
    source with gather/craft to make up any shortfall rather than facing an
    all-or-nothing cliff."""
    py, lean = _run_prereq(True, [(1, 9)], 5, ready_source=True)
    assert py == []
    assert py == lean
