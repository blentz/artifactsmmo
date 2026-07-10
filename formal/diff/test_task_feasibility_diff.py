"""Differential test: real Python `task_requirement` / `_item_skill_gap` must
agree with the proved Lean `task_feasibility` oracle.

`task_requirement(state, game_data)` decides whether the active task is feasible:
* items task -> `_item_skill_gap` recurses the craft closure (cycle-safe via a
  `seen` set), returning the UNMET crafting-skill requirement with the HIGHEST
  `required_level` (= `crafting_level`), or `None` if all skills are met.
* monsters task -> gates iff `monster_level > 0 ∧ monster_level > level + 2`.

We model items as int codes (`Nat` in Lean). A controlled fake `GameData`
exposes `item_stats` (with `crafting_skill` / `crafting_level`),
`crafting_recipe`, and `monster_level`. A real `WorldState` carries `skills`,
`level`, `task_code` / `task_type` / `task_total`.

We assert over >= 200 random recipe graphs (including CYCLIC and DIAMOND):
* the worst `required_level` (0 == None) matches the Lean oracle;
* `None`-ness matches;
and over (monster_level, char_level) pairs including the `+2` boundary:
* the monster gate bool matches.
"""
import random

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.task_feasibility import task_requirement
from artifactsmmo_cli.ai.world_state import WorldState
from formal.diff.oracle_client import run_oracle

# A fixed pool of distinct skill names, one per item code, so each item that has
# a crafting skill keys into a distinct char skill level (matching the Lean
# per-item SkillLevel/CraftLevel tables).
_SKILLS = [f"skill{i}" for i in range(16)]


def _stats(code: int, crafting_skill: str | None = None, crafting_level: int = 0) -> ItemStats:
    """Build an ItemStats with the required positional fields, exposing only the
    crafting skill/level the model reads."""
    return ItemStats(code=str(code), level=1, type_="resource",
                     crafting_skill=crafting_skill, crafting_level=crafting_level)


class _FakeGameData:
    def __init__(self, recipes: dict[int, dict[int, int]],
                 item_stats: dict[int, ItemStats], monster_levels: dict[int, int]):
        self._recipes = {str(k): {str(s): q for s, q in v.items()} for k, v in recipes.items()}
        self._stats = {str(k): v for k, v in item_stats.items()}
        self._monster_levels = {str(k): v for k, v in monster_levels.items()}

    def item_stats(self, code: str) -> ItemStats | None:
        return self._stats.get(code)

    def crafting_recipe(self, code: str) -> dict[str, int] | None:
        return self._recipes.get(code)

    def monster_level(self, code: str) -> int:
        return self._monster_levels.get(code, 0)


def _make_state(task_code: str, task_type: str, task_total: int,
                level: int, skills: dict[str, int]) -> WorldState:
    return WorldState(
        character="c", level=level, xp=0, max_xp=100, hp=10, max_hp=10, gold=0,
        skills=skills, x=0, y=0, inventory={}, inventory_max=100,
        inventory_slots_max=100,
        equipment={}, cooldown_expires=None, task_code=task_code, task_type=task_type,
        task_progress=0, task_total=task_total, bank_items=None,
        bank_gold=None, pending_items=None,
    )


def _rand_items_case(rng: random.Random, allow_cycle: bool):
    """Random recipe graph + per-item crafting skill/level + char skill levels."""
    n = rng.randint(1, 8)
    items = list(range(n))
    recipes: dict[int, dict[int, int]] = {}
    for it in items:
        if rng.random() < 0.55:
            n_sub = rng.randint(1, 3)
            subs: dict[int, int] = {}
            for _ in range(n_sub):
                if allow_cycle:
                    sub = rng.randint(0, n - 1)
                else:
                    if it + 1 > n - 1:
                        continue
                    sub = rng.randint(it + 1, n - 1)
                if sub != it or allow_cycle:
                    subs[sub] = rng.randint(1, 5)
            if subs:
                recipes[it] = subs
    item_stats: dict[int, ItemStats] = {}
    char_skills: dict[str, int] = {}
    for it in items:
        # Some items have a crafting skill; some are raw (no skill).
        if rng.random() < 0.7:
            skill = _SKILLS[it]
            craft_level = rng.randint(1, 30)
            item_stats[it] = _stats(it, crafting_skill=skill, crafting_level=craft_level)
            # char's level for that skill: sometimes below (unmet), sometimes >=
            char_skills[skill] = rng.randint(0, 30)
        else:
            item_stats[it] = _stats(it)  # no crafting_skill
    task_item = rng.choice(items)
    char_level = rng.randint(1, 30)
    return recipes, item_stats, char_skills, task_item, char_level


def _encode_items(recipes, item_stats, char_skills, task_item, fuel) -> list[int]:
    # recipe edges (item, sub), ingredient-only
    edges: list[int] = []
    n_edges = 0
    for item, sub_map in recipes.items():
        for sub in sub_map:
            edges += [item, sub]
            n_edges += 1
    # hasSkill table, craftLevel table, skillLevel(for that item) table
    skill_pairs: list[int] = []
    craft_pairs: list[int] = []
    lvl_pairs: list[int] = []
    n_skill = n_craft = n_lvl = 0
    for item, stats in item_stats.items():
        if stats.crafting_skill:
            skill_pairs += [item, 1]
            craft_pairs += [item, stats.crafting_level]
            lvl_pairs += [item, char_skills.get(stats.crafting_skill, 0)]
        else:
            skill_pairs += [item, 0]
            craft_pairs += [item, 0]
            lvl_pairs += [item, 0]
        n_skill += 1
        n_craft += 1
        n_lvl += 1
    args = (
        [n_edges] + edges
        + [n_skill] + skill_pairs
        + [n_craft] + craft_pairs
        + [n_lvl] + lvl_pairs
        + [task_item, fuel]
    )
    return args


@settings(max_examples=260, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_items_python_matches_lean(seed):
    rng = random.Random(seed)
    allow_cycle = rng.random() < 0.5
    recipes, item_stats, char_skills, task_item, char_level = _rand_items_case(rng, allow_cycle)
    state = _make_state(str(task_item), "items", 5, char_level, char_skills)
    gd = _FakeGameData(recipes, item_stats, {})
    req = task_requirement(state, gd)
    py_level = req.required_level if req is not None else 0

    fuel = 2 * len(item_stats) + 4
    args = _encode_items(recipes, item_stats, char_skills, task_item, fuel)
    lean = run_oracle("task_feasibility_items", [args])[0]
    ctx = (f"recipes={recipes} stats={item_stats} skills={char_skills} "
           f"task={task_item} allow_cycle={allow_cycle}")
    assert py_level == lean["required_level"], f"level mismatch: {ctx} lean={lean}"
    assert (req is None) == (lean["required_level"] == 0), f"none mismatch: {ctx} lean={lean}"


def test_items_diamond_binds():
    """Diamond: 0 -> {1,2}, 1 -> 3, 2 -> 3. The worst gap is the MAX crafting
    level over unmet items, regardless of which arm it lives in."""
    recipes = {0: {1: 2, 2: 3}, 1: {3: 5}, 2: {3: 7}}
    # item 3 (base) has the highest crafting level and is unmet -> it should win
    item_stats = {
        0: _stats(0, crafting_skill="skill0", crafting_level=5),
        1: _stats(1, crafting_skill="skill1", crafting_level=8),
        2: _stats(2, crafting_skill="skill2", crafting_level=4),
        3: _stats(3, crafting_skill="skill3", crafting_level=20),
    }
    char_skills = {"skill0": 0, "skill1": 0, "skill2": 0, "skill3": 0}
    state = _make_state("0", "items", 5, 1, char_skills)
    gd = _FakeGameData(recipes, item_stats, {})
    req = task_requirement(state, gd)
    assert req is not None and req.required_level == 20
    args = _encode_items(recipes, item_stats, char_skills, 0, 12)
    lean = run_oracle("task_feasibility_items", [args])[0]
    assert lean["required_level"] == 20


def test_items_cyclic_terminates_and_binds():
    """Cycle 0 -> 1 -> 0: the closure must terminate (seen guard) and the worst
    gap is the max over both unmet items."""
    recipes = {0: {1: 2}, 1: {0: 3}}
    item_stats = {
        0: _stats(0, crafting_skill="skill0", crafting_level=12),
        1: _stats(1, crafting_skill="skill1", crafting_level=7),
    }
    char_skills = {"skill0": 0, "skill1": 0}
    state = _make_state("0", "items", 5, 1, char_skills)
    gd = _FakeGameData(recipes, item_stats, {})
    req = task_requirement(state, gd)
    assert req is not None and req.required_level == 12
    args = _encode_items(recipes, item_stats, char_skills, 0, 8)
    lean = run_oracle("task_feasibility_items", [args])[0]
    assert lean["required_level"] == 12


def test_items_all_met_is_none():
    """Every item's skill is met -> feasible -> None (worst = 0)."""
    recipes = {0: {1: 2}}
    item_stats = {
        0: _stats(0, crafting_skill="skill0", crafting_level=3),
        1: _stats(1, crafting_skill="skill1", crafting_level=4),
    }
    char_skills = {"skill0": 5, "skill1": 5}
    state = _make_state("0", "items", 5, 1, char_skills)
    gd = _FakeGameData(recipes, item_stats, {})
    assert task_requirement(state, gd) is None
    args = _encode_items(recipes, item_stats, char_skills, 0, 8)
    lean = run_oracle("task_feasibility_items", [args])[0]
    assert lean["required_level"] == 0


@settings(max_examples=200, deadline=None)
@given(monster_level=st.integers(min_value=0, max_value=60),
       char_level=st.integers(min_value=0, max_value=60))
def test_monster_gate_matches_lean(monster_level, char_level):
    state = _make_state("M", "monsters", 5, char_level, {})
    gd = _FakeGameData({}, {}, {"M": monster_level})
    req = task_requirement(state, gd)
    py_gates = req is not None
    lean = run_oracle("task_feasibility_monster", [[monster_level, char_level]])[0]
    assert py_gates == lean["gates"], (
        f"gate mismatch monster={monster_level} char={char_level} "
        f"py={py_gates} lean={lean}")


def test_monster_gate_plus_two_boundary():
    """The +2 boundary: monster EXACTLY at char_level + 2 must NOT gate; +3 must.
    Pins the strict-greater-than margin (MONSTER_LEVEL_MARGIN = 2)."""
    for char in range(0, 50):
        boundary = char + 2
        just_past = char + 3
        # boundary: feasible (no gate)
        state = _make_state("M", "monsters", 5, char, {})
        gd = _FakeGameData({}, {}, {"M": boundary})
        assert task_requirement(state, gd) is None
        lean = run_oracle("task_feasibility_monster", [[boundary, char]])[0]
        assert lean["gates"] is False
        # just past: gates
        gd2 = _FakeGameData({}, {}, {"M": just_past})
        assert task_requirement(state, gd2) is not None
        lean2 = run_oracle("task_feasibility_monster", [[just_past, char]])[0]
        assert lean2["gates"] is True
