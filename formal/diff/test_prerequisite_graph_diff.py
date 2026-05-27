"""Differential test: real Python `prerequisites` (the data-derived ObtainItem
edge structure) and `combat_capable` (the `any` aggregation) must agree with the
proved Lean oracle over random recipe/drop tables and monster-beatable maps.

## prerequisites

For an UNSATISFIED `ObtainItem(code)`, `prerequisites` emits:
* if `code` has a recipe → `ReachSkillLevel(crafting_skill, crafting_level)`
  (only when `crafting_skill` is a non-empty string) then one `ObtainItem(mat,
  qty)` per ingredient;
* elif `code` is the drop of a resource (first matching `_resource_drops` entry
  with a `resource_skill_level`) → that single `ReachSkillLevel`;
* else → no prerequisites (leaf).

We use integer item/skill/resource codes (the model is `Nat`), a controlled fake
GameData, and a fake unsatisfied WorldState (empty inventory). We normalize the
produced `MetaGoal` list to comparable tuples and compare against the Lean
oracle's tagged-edge list over >= 200 random tables (including the recipe
branch, the resource branch, and the leaf branch).

## combat_capable

`combat_capable = any(predict_win(state, game_data, code) for code in
_monster_level)`. We monkeypatch `predict_win` to a controlled per-monster bool
and compare the `any()` result against the Lean oracle's `combatCapable` fold.
"""
import random
from types import SimpleNamespace

import artifactsmmo_cli.ai.tiers.prerequisite_graph as pg_mod
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.prerequisite_graph import combat_capable, prerequisites
from formal.diff.oracle_client import run_oracle


class _FakeStats:
    def __init__(self, crafting_skill: str | None, crafting_level: int):
        self.crafting_skill = crafting_skill
        self.crafting_level = crafting_level


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


def _unsatisfied_state() -> SimpleNamespace:
    """A WorldState stand-in where every ObtainItem is unsatisfied (owned 0)."""
    return SimpleNamespace(inventory={}, bank_items=None, equipment={})


def _normalize_py(edges) -> list[tuple]:
    """MetaGoal list -> comparable tuples. ReachSkillLevel(skill,level) and
    ObtainItem(code,qty), in produced ORDER (the structure is order-sensitive)."""
    out: list[tuple] = []
    for e in edges:
        if isinstance(e, ReachSkillLevel):
            out.append(("skill", int(e.skill), int(e.level)))
        elif isinstance(e, ObtainItem):
            out.append(("item", int(e.code), int(e.quantity)))
        else:  # pragma: no cover - the ObtainItem branch emits only these two
            raise AssertionError(f"unexpected edge {e!r}")
    return out


def _normalize_lean(lean: dict) -> list[tuple]:
    out: list[tuple] = []
    for e in lean["edges"]:
        out.append((e["kind"], int(e["a"]), int(e["b"])))
    return out


def _encode_prereq_args(has_recipe: bool, ingredients: list[tuple[int, int]],
                        craft_skill: tuple[int, int] | None,
                        res_drops: list[tuple[int, int, tuple[int, int] | None]],
                        code: int) -> list[int]:
    args: list[int] = [1 if has_recipe else 0, len(ingredients)]
    for mat, qty in ingredients:
        args += [mat, qty]
    if craft_skill is not None:
        args += [1, craft_skill[0], craft_skill[1]]
    else:
        args += [0, 0, 0]
    args += [len(res_drops)]
    for res, drop, sk in res_drops:
        if sk is not None:
            args += [res, drop, 1, sk[0], sk[1]]
        else:
            args += [res, drop, 0, 0, 0]
    args += [code]
    return args


def _build_prereq(rng: random.Random):
    """Random scenario hitting recipe / resource / leaf branches.

    The crafting skill is modeled as a string only when present and non-empty
    (the Python `if stats.crafting_skill:` guard). Skill/resource/item codes are
    distinct integer ranges so they never collide in the comparison."""
    branch = rng.choice(["recipe", "resource", "leaf"])
    code = rng.randint(0, 20)

    # resource drops: (res_code, drop_item, optional (skill, level))
    res_drops: list[tuple[int, int, tuple[int, int] | None]] = []
    n_drops = rng.randint(0, 4)
    for d in range(n_drops):
        res = 100 + d
        drop = rng.randint(0, 20)
        if rng.random() < 0.7:
            sk = (200 + rng.randint(0, 5), rng.randint(1, 30))
        else:
            sk = None
        res_drops.append((res, drop, sk))

    has_recipe = branch == "recipe"
    ingredients: list[tuple[int, int]] = []
    craft_skill: tuple[int, int] | None = None
    if has_recipe:
        n_ing = rng.randint(0, 4)
        # distinct mat codes so the Python recipe dict does not dedupe keys
        # (the dict would collapse duplicate mats; the model keeps all edges)
        mats = rng.sample(range(0, 21), n_ing)
        ingredients = [(mat, rng.randint(1, 9)) for mat in mats]
        if rng.random() < 0.7:
            craft_skill = (200 + rng.randint(0, 5), rng.randint(1, 30))
    elif branch == "leaf":
        # ensure code is NOT a skilled drop: clear any matching skilled entry
        res_drops = [(r, dr, sk) for (r, dr, sk) in res_drops if not (dr == code and sk)]
    else:  # resource: ensure at least one skilled drop matches code
        res_drops.append((100 + n_drops, code, (200 + rng.randint(0, 5), rng.randint(1, 30))))

    return has_recipe, ingredients, craft_skill, res_drops, code


def _run_prereq(has_recipe, ingredients, craft_skill, res_drops, code):
    recipe = {str(mat): qty for mat, qty in ingredients} if has_recipe else None
    stats = None
    if has_recipe:
        skill_str = str(craft_skill[0]) if craft_skill is not None else None
        level = craft_skill[1] if craft_skill is not None else 0
        stats = _FakeStats(skill_str, level)
    resource_drops = {str(r): str(dr) for (r, dr, _sk) in res_drops}
    resource_skill = {str(r): (str(sk[0]), sk[1]) for (r, dr, sk) in res_drops if sk is not None}
    gd = _FakeGameData(recipe, stats, resource_drops, resource_skill, {})

    node = ObtainItem(str(code))
    py = _normalize_py(prerequisites(node, _unsatisfied_state(), gd))

    args = _encode_prereq_args(has_recipe, ingredients, craft_skill, res_drops, code)
    lean = _normalize_lean(run_oracle("prerequisite_graph", [args])[0])
    return py, lean


def test_prerequisites_matches_lean():
    rng = random.Random(20260527)
    for _ in range(240):
        scenario = _build_prereq(rng)
        py, lean = _run_prereq(*scenario)
        assert py == lean, f"prereq mismatch: scenario={scenario} py={py} lean={lean}"


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


def test_recipe_branch_with_skill_edges():
    """Concrete: craftable code 5, skill (200,7), ingredients [(1,2),(3,4)].
    Edges = [skill(200,7), item(1,2), item(3,4)] in order. Pins recipe shape."""
    py, lean = _run_prereq(True, [(1, 2), (3, 4)], (200, 7), [], 5)
    assert py == [("skill", 200, 7), ("item", 1, 2), ("item", 3, 4)]
    assert py == lean


def test_resource_branch_single_skill_edge():
    """Concrete: non-craftable code 9, dropped by resource 100 with skill (203,5).
    The first earlier drop of 9 with NO skill is skipped. Edges = [skill(203,5)]."""
    drops = [(100, 9, None), (101, 9, (203, 5)), (102, 9, (204, 8))]
    py, lean = _run_prereq(False, [], None, drops, 9)
    assert py == [("skill", 203, 5)]
    assert py == lean


def test_leaf_branch_no_edges():
    """Concrete: non-craftable code 9 with no matching skilled drop ⇒ leaf."""
    py, lean = _run_prereq(False, [], None, [(100, 4, (200, 1))], 9)
    assert py == []
    assert py == lean
