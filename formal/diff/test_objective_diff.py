"""Differential test: real Python `is_attainable`, `CharacterObjective.from_game_data`
(gear selection), and `gap` / `is_complete` must agree with the proved Lean oracle.

* `is_attainable(code, game_data)` (objective.py:15) bottoms a craft chain out in
  gatherables, cycle-safe via a `_path` set. We feed random recipe graphs
  (including CYCLIC and drop-only shapes) and assert the attainability bool.
* `CharacterObjective.from_game_data` ranks each gear type by `(-equip_value,
  code)`, filters to attainable, zips to slots: the first slot gets the
  highest-equip_value ATTAINABLE item. We assert the per-(first-)slot best code.
* `gap` / `is_complete` produce integer gaps and a completeness bool. We assert
  the char gap, skill/gear gap sums and denominators, and `is_complete`.

Integer item/equip-value codes; controlled fake GameData exposing only the fields
these functions read. The same data is encoded for the Lean oracle (flat ints).
"""
import random
from fractions import Fraction

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, is_attainable
from artifactsmmo_cli.ai.world_state import SKILL_NAMES, WorldState
from formal.diff.oracle_client import run_oracle


def _make_state(level: int, skills: dict[str, int],
                equipment: dict[str, str | None]) -> WorldState:
    return WorldState(
        character="t", level=level, xp=0, max_xp=100, hp=1, max_hp=1, gold=0,
        skills=skills, x=0, y=0, inventory={}, inventory_max=100,
        equipment=equipment, cooldown_expires=None, task_code=None,
        task_type=None, task_progress=0, task_total=0, bank_items=None,
        bank_gold=None, pending_items=None)


class _FakeGameData:
    """Minimal GameData stand-in exposing only what objective.py reads."""

    MAX_CHARACTER_LEVEL = 50
    MAX_SKILL_LEVEL = 50

    def __init__(self, recipes: dict[int, dict[int, int]], drops: dict[int, int],
                 item_stats: dict[int, ItemStats]):
        # recipe maps item -> {mat: qty}; mat/qty values irrelevant to attainability
        self._crafting_recipes = {str(k): {str(m): q for m, q in v.items()}
                                  for k, v in recipes.items()}
        self._resource_drops = {str(r): str(d) for r, d in drops.items()}
        self._item_stats = {str(c): s for c, s in item_stats.items()}

    def crafting_recipe(self, code: str):
        return self._crafting_recipes.get(code)

    def item_stats(self, code: str):
        return self._item_stats.get(code)

    @property
    def resource_drops(self) -> dict[str, str]:
        return self._resource_drops

    @property
    def all_item_stats(self) -> dict[str, ItemStats]:
        return self._item_stats

    @property
    def max_character_level(self) -> int:
        return self.MAX_CHARACTER_LEVEL

    @property
    def max_skill_level(self) -> int:
        return self.MAX_SKILL_LEVEL


# ---------------------------------------------------------------------------
# is_attainable
# ---------------------------------------------------------------------------

def _encode_attainable(recipes, drops, query, fuel):
    edges = []
    n_edges = 0
    for item, mats in recipes.items():
        for mat in mats:
            edges += [item, mat]
            n_edges += 1
    has_list = list(recipes.keys())
    drop_items = sorted(set(drops.values()))
    args = ([n_edges] + edges
            + [len(has_list)] + has_list
            + [len(drop_items)] + drop_items
            + [query, fuel])
    return args


def _rand_attainable_graph(rng, allow_cycle):
    n = rng.randint(1, 8)
    items = list(range(n))
    recipes: dict[int, dict[int, int]] = {}
    for it in items:
        if rng.random() < 0.5:
            subs: dict[int, int] = {}
            for _ in range(rng.randint(1, 3)):
                if allow_cycle:
                    mat = rng.randint(0, n - 1)
                else:
                    if it + 1 > n - 1:
                        continue
                    mat = rng.randint(it + 1, n - 1)
                subs[mat] = rng.randint(1, 5)
            if subs:
                recipes[it] = subs
    drops: dict[int, int] = {}
    for d in range(rng.randint(0, 5)):
        drops[100 + d] = rng.randint(0, n - 1)
    query = rng.choice(items)
    fuel = 2 * n + 4
    return recipes, drops, query, fuel


@settings(max_examples=240, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_is_attainable_matches_lean(seed):
    rng = random.Random(seed)
    allow_cycle = rng.random() < 0.5
    recipes, drops, query, fuel = _rand_attainable_graph(rng, allow_cycle)
    gd = _FakeGameData(recipes, drops, {})
    py = is_attainable(str(query), gd)
    args = _encode_attainable(recipes, drops, query, fuel)
    lean = run_oracle("objective_attainable", [args])[0]
    ctx = (f"recipes={recipes} drops={drops} query={query} cycle={allow_cycle}")
    assert py == lean["is_attainable"], f"attainable mismatch: {ctx} lean={lean}"


def test_attainable_cyclic_is_false():
    """a<->b cycle, neither a drop: not attainable (cycle never bottoms out)."""
    recipes = {0: {1: 1}, 1: {0: 1}}
    drops: dict[int, int] = {}
    gd = _FakeGameData(recipes, drops, {})
    assert is_attainable("0", gd) is False
    args = _encode_attainable(recipes, drops, 0, 8)
    assert run_oracle("objective_attainable", [args])[0]["is_attainable"] is False


def test_attainable_drop_only_leaf_false():
    """0 crafts from 1; 1 has no recipe and is not a drop: 0 not attainable."""
    recipes = {0: {1: 1}}
    gd = _FakeGameData(recipes, {}, {})
    assert is_attainable("0", gd) is False
    args = _encode_attainable(recipes, {}, 0, 8)
    assert run_oracle("objective_attainable", [args])[0]["is_attainable"] is False


def test_attainable_chain_true():
    """0 crafts from drop-leaf 1: attainable."""
    recipes = {0: {1: 1}}
    drops = {100: 1}
    gd = _FakeGameData(recipes, drops, {})
    assert is_attainable("0", gd) is True
    args = _encode_attainable(recipes, drops, 0, 8)
    assert run_oracle("objective_attainable", [args])[0]["is_attainable"] is True


# ---------------------------------------------------------------------------
# gear selection (best attainable per first slot of a type)
# ---------------------------------------------------------------------------

def _stats(code: int, type_: str, attack: int, resistance: int, hp_restore: int) -> ItemStats:
    return ItemStats(code=str(code), level=1, type_=type_,
                     attack={"fire": attack} if attack else {},
                     resistance={"fire": resistance} if resistance else {},
                     hp_restore=hp_restore)


@settings(max_examples=200, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_best_gear_matches_lean(seed):
    rng = random.Random(seed)
    # one gear type (weapon) so the first slot is weapon_slot; random items
    n = rng.randint(1, 8)
    recipes: dict[int, dict[int, int]] = {}
    drops: dict[int, int] = {}
    item_stats: dict[int, ItemStats] = {}
    # base drop leaf for craftable items
    drops[100] = 999
    item_stats[999] = _stats(999, "resource_internal", 0, 0, 0)
    codes = list(range(n))
    lean_items = []
    for c in codes:
        atk = rng.randint(0, 9)
        res = rng.randint(0, 9)
        hp = rng.randint(0, 9)
        item_stats[c] = _stats(c, "weapon", atk, res, hp)
        # attainability: half craftable-from-drop (attainable), half drop-only-fail
        if rng.random() < 0.6:
            recipes[c] = {999: 1}  # craft from drop leaf -> attainable
            attainable = True
        else:
            recipes[c] = {998: 1}  # craft from unknown non-drop -> NOT attainable
            attainable = False
        # P4a: equip_value IS an exact int — no float boundary cast.
        val = equip_value(item_stats[c])
        lean_items.append((c, val, 1 if attainable else 0))

    gd = _FakeGameData(recipes, drops, item_stats)
    obj = CharacterObjective.from_game_data(gd)
    py_weapon = obj.target_gear.get("weapon_slot")  # str | None
    py_code = int(py_weapon) if py_weapon is not None else -1

    args = [len(lean_items)]
    for c, v, a in lean_items:
        args += [c, v, a]
    lean = run_oracle("objective_best_gear", [args])[0]
    ctx = f"items={lean_items}"
    assert py_code == lean["chosen_code"], f"gear code mismatch: {ctx} lean={lean}"


# ---------------------------------------------------------------------------
# gap / is_complete
# ---------------------------------------------------------------------------

@settings(max_examples=200, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_gap_matches_lean(seed):
    """Drive the REAL `CharacterObjective.gap` and bind its integer gaps to Lean.

    We build a real objective with ONE weapon-slot target (a drop-grounded
    weapon) and a random equipped weapon, plus a random char level and skills.
    The real `gap` produces char_level_gap, skill_gaps, and gear_gaps; we feed
    the corresponding (target, have) integer pairs to the Lean oracle and assert
    the integer numerators/denominators and is_complete agree."""
    rng = random.Random(seed)
    level = rng.randint(1, 55)
    skills = {s: rng.randint(1, 55) for s in SKILL_NAMES}

    # one attainable weapon target (craft from drop leaf) + a random equipped one
    item_stats = {
        999: _stats(999, "resource_internal", 0, 0, 0),
        1: _stats(1, "weapon", rng.randint(1, 9), rng.randint(0, 9), rng.randint(0, 9)),
    }
    recipes = {1: {999: 1}}
    drops = {100: 999}
    target_val = equip_value(item_stats[1])  # P4a: exact int

    # equipped weapon: maybe none, maybe a weaker/stronger item
    have_val = 0
    equipment: dict[str, str | None] = {"weapon_slot": None}
    if rng.random() < 0.6:
        eq = _stats(2, "weapon", rng.randint(0, 12), rng.randint(0, 12), rng.randint(0, 12))
        item_stats[2] = eq
        equipment["weapon_slot"] = "2"
        have_val = equip_value(eq)  # P4a: exact int

    gd = _FakeGameData(recipes, drops, item_stats)
    obj = CharacterObjective.from_game_data(gd)
    state = _make_state(level, skills, equipment)
    py_gap = obj.gap(state)

    py_char = py_gap.char_level_gap
    py_skill_sum = sum(py_gap.skill_gaps.values())
    py_skill_denom = len(SKILL_NAMES) * gd.max_skill_level
    # P4a: gear gaps are exact ints — the sum is an int, no rounding cast.
    py_gear_sum = sum(py_gap.gear_gaps.values())
    # gear denom = sum of target gear item values (here just the one weapon)
    py_gear_denom = target_val if obj.target_gear.get("weapon_slot") else 0
    py_complete = py_gap.is_complete

    skill_pairs = [(gd.max_skill_level, skills[s]) for s in SKILL_NAMES]
    gear_pairs = [(target_val, have_val)] if obj.target_gear.get("weapon_slot") else []
    args = [gd.max_character_level, level, len(skill_pairs)]
    for t, h in skill_pairs:
        args += [t, h]
    args += [len(gear_pairs)]
    for t, h in gear_pairs:
        args += [t, h]
    lean = run_oracle("objective_gap", [args])[0]
    ctx = f"level={level} target_val={target_val} have_val={have_val}"
    assert py_char == lean["char_gap"], f"char gap: {ctx} {lean}"
    assert py_skill_sum == lean["skill_gap_sum"], f"skill gap: {ctx} {lean}"
    assert py_skill_denom == lean["skill_denom"], f"skill denom: {ctx} {lean}"
    assert py_gear_sum == lean["gear_gap_sum"], f"gear gap: {ctx} {lean}"
    assert py_gear_denom == lean["gear_denom"], f"gear denom: {ctx} {lean}"
    assert py_complete == lean["is_complete"], f"complete: {ctx} {lean}"
    # P4a: the production fractions are EXACT rationals — pin them against the
    # oracle's integer numerators/denominators with zero tolerance.
    assert py_gap.char_level_fraction == Fraction(lean["char_gap"], gd.max_character_level)
    assert py_gap.skills_fraction == Fraction(lean["skill_gap_sum"], lean["skill_denom"])
    if lean["gear_denom"] > 0:
        assert py_gap.gear_fraction == Fraction(lean["gear_gap_sum"], lean["gear_denom"])
    else:
        assert py_gap.gear_fraction == Fraction(0)
    # integer fraction bound, verified integer-only: 0 <= gap <= denom
    assert 0 <= lean["skill_gap_sum"] <= lean["skill_denom"]
    if lean["gear_denom"] > 0:
        assert 0 <= lean["gear_gap_sum"] <= lean["gear_denom"]
    assert 0 <= lean["char_gap"] <= gd.max_character_level
