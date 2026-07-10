"""Differential test: real Python `select_bank_deposits` (and `_keep_codes`) must
agree with the proved Lean `bank_selection` oracle over random states.

`select_bank_deposits(state, game_data)` computes a KEEP-SET — {TASKS_COIN} ∪
{task_code} ∪ {inventory HP-restore items} ∪ {best fighting weapon} ∪
recipe_materials({crafting_target} ∪ {items-task code}) — then deposits exactly
the inventory items with qty>0 NOT in the keep set, sorted by (-sell_value, code).

We use integer item codes (the Lean model uses `Nat`) and drive the REAL Python
via a real `GameData` (with `_item_stats`, `_crafting_recipes`, `_npc_sell_prices`
populated) and a real `WorldState`. The same state is encoded for the Lean oracle
as flat int args. We assert:
* keep set matches (as a set),
* deposit list matches EXACTLY (codes AND order),
* deposits ∩ keep = ∅ (the freeze invariant),
over >= 200 random states INCLUDING a case where a recipe material IS the
items-task item (the PursueTask-freeze case).
"""
import random

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.bank_selection import _keep_codes, select_bank_deposits
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState
from formal.diff.oracle_client import run_oracle

# tasks_coin is the string TASKS_COIN_CODE; we reserve integer code 0 to mean it.
TASKS_COIN_INT = 0


def _code(n: int) -> str:
    """Map an integer code to a string item code (0 == the tasks coin)."""
    return TASKS_COIN_CODE if n == TASKS_COIN_INT else f"item_{n}"


def _build_game_data(
    recipes: dict[int, dict[int, int]],
    attrs: dict[int, dict],
) -> GameData:
    gd = GameData()
    gd._crafting_recipes = {
        _code(k): {_code(s): q for s, q in v.items()} for k, v in recipes.items()
    }
    npc_prices: dict[str, int] = {}
    for code, a in attrs.items():
        stats = ItemStats(
            code=_code(code),
            level=1,
            type_=a["type_"],
            hp_restore=a["hp_restore"],
            skill_effects={"woodcutting": 1} if a["is_tool"] else {},
            attack={"fire": a["attack"]} if a["attack"] else {},
        )
        gd._item_stats[_code(code)] = stats
        if a["sell"] > 0:
            npc_prices[_code(code)] = a["sell"]
    gd._npc_sell_prices = {"npc_a": npc_prices}
    return gd


def _build_state(
    inventory: dict[int, int],
    equipped: list[int],
    task_code: int | None,
    task_is_items: bool,
    crafting_target: int | None,
    inventory_max: int = 1000,
    inventory_slots_max: int | None = None,
) -> WorldState:
    equipment: dict[str, str | None] = {
        f"slot_{i}": _code(c) for i, c in enumerate(equipped)
    }
    return WorldState(
        character="t",
        level=10,
        xp=0,
        max_xp=100,
        hp=100,
        max_hp=100,
        gold=0,
        skills={},
        x=0,
        y=0,
        inventory={_code(c): q for c, q in inventory.items()},
        inventory_max=inventory_max,
        inventory_slots_max=(inventory_slots_max if inventory_slots_max is not None
                             else inventory_max),
        equipment=equipment,
        cooldown_expires=None,
        task_code=(_code(task_code) if task_code is not None else None),
        task_type=("items" if task_is_items else ("monsters" if task_code is not None else None)),
        task_progress=0,
        task_total=0,
        bank_items=None,
        bank_gold=None,
        pending_items=None,
        crafting_target=(_code(crafting_target) if crafting_target is not None else None),
    )


def _encode_args(
    inventory: dict[int, int],
    equipped: list[int],
    task_code: int | None,
    task_is_items: bool,
    crafting_target: int | None,
    recipes: dict[int, dict[int, int]],
    attrs: dict[int, dict],
    fuel: int,
    inventory_max: int = 1000,
    inventory_slots_max: int | None = None,
) -> list[int]:
    args: list[int] = [TASKS_COIN_INT]
    args += [1, task_code] if task_code is not None else [0, 0]
    args += [1 if task_is_items else 0]
    args += [1, crafting_target] if crafting_target is not None else [0, 0]
    inv_items = list(inventory.items())
    args += [len(inv_items)]
    for code, qty in inv_items:
        args += [code, qty]
    args += [len(equipped)]
    args += list(equipped)
    triples: list[int] = []
    n_recipe = 0
    for item, sub_map in recipes.items():
        for sub, qty in sub_map.items():
            triples += [item, sub, qty]
            n_recipe += 1
    args += [n_recipe] + triples
    attr_items = list(attrs.items())
    args += [len(attr_items)]
    for code, a in attr_items:
        is_weapon = 1 if a["type_"] == "weapon" else 0
        args += [code, a["attack"], is_weapon, 1 if a["is_tool"] else 0, a["hp_restore"], a["sell"]]
    slots_max = inventory_slots_max if inventory_slots_max is not None else inventory_max
    args += [fuel, inventory_max, slots_max]
    return args


def _keep_set_ints(state: WorldState, gd: GameData) -> set[int]:
    keep = _keep_codes(state, gd)
    out: set[int] = set()
    for c in keep:
        if c == TASKS_COIN_CODE:
            out.add(TASKS_COIN_INT)
        elif c.startswith("item_"):
            out.add(int(c[len("item_"):]))
    return out


def _run(inventory, equipped, task_code, task_is_items, crafting_target, recipes, attrs, fuel,
         inventory_max=1000, inventory_slots_max=None):
    gd = _build_game_data(recipes, attrs)
    state = _build_state(inventory, equipped, task_code, task_is_items, crafting_target,
                         inventory_max, inventory_slots_max)

    py_keep = _keep_set_ints(state, gd)
    py_deposits = [
        (TASKS_COIN_INT if c == TASKS_COIN_CODE else int(c[len("item_"):]), q)
        for c, q in select_bank_deposits(state, gd)
    ]

    args = _encode_args(
        inventory, equipped, task_code, task_is_items, crafting_target, recipes, attrs, fuel,
        inventory_max, inventory_slots_max,
    )
    lean = run_oracle("bank_selection", [args])[0]
    lean_keep = set(lean["keep"])
    lean_deposits = [(cq[0], cq[1]) for cq in lean["deposits"]]
    return py_keep, py_deposits, lean_keep, lean_deposits


def _rand_state(rng: random.Random):
    """Random bank-selection state over integer item codes 1..n (0 = tasks coin)."""
    n = rng.randint(1, 8)
    items = list(range(1, n + 1))
    # recipes: some items craftable from others
    recipes: dict[int, dict[int, int]] = {}
    for it in items:
        if rng.random() < 0.45:
            subs: dict[int, int] = {}
            for _ in range(rng.randint(1, 3)):
                sub = rng.choice(items)
                if sub != it:
                    subs[sub] = rng.randint(1, 4)
            if subs:
                recipes[it] = subs
    # attributes per item
    attrs: dict[int, dict] = {}
    for it in items:
        roll = rng.random()
        if roll < 0.3:
            type_ = "weapon"
        elif roll < 0.45:
            type_ = "consumable"
        else:
            type_ = "resource"
        attrs[it] = {
            "type_": type_,
            "attack": rng.randint(0, 50) if type_ == "weapon" else 0,
            "is_tool": (type_ == "weapon" and rng.random() < 0.3),
            "hp_restore": rng.randint(1, 30) if type_ == "consumable" and rng.random() < 0.7 else 0,
            "sell": rng.randint(0, 100),
        }
    inventory = {it: rng.randint(0, 5) for it in items if rng.random() < 0.7}
    # sometimes include the tasks coin in inventory
    if rng.random() < 0.4:
        inventory[TASKS_COIN_INT] = rng.randint(1, 5)
        attrs[TASKS_COIN_INT] = {"type_": "currency", "attack": 0, "is_tool": False,
                                 "hp_restore": 0, "sell": 0}
    equipped = rng.sample(items, rng.randint(0, min(3, len(items))))
    task_code = rng.choice(items) if rng.random() < 0.6 else None
    task_is_items = task_code is not None and rng.random() < 0.6
    crafting_target = rng.choice(items) if rng.random() < 0.6 else None
    fuel = 2 * n + 6
    return inventory, equipped, task_code, task_is_items, crafting_target, recipes, attrs, fuel


@settings(max_examples=240, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_python_matches_lean(seed):
    rng = random.Random(seed)
    state = _rand_state(rng)
    py_keep, py_deposits, lean_keep, lean_deposits = _run(*state)
    ctx = f"seed={seed} state={state}"
    assert py_keep == lean_keep, f"keep mismatch: {ctx}\n py={py_keep} lean={lean_keep}"
    assert py_deposits == lean_deposits, (
        f"deposits mismatch (order matters): {ctx}\n py={py_deposits} lean={lean_deposits}"
    )
    # freeze invariant: no deposited code is in the keep set
    dep_codes = {c for c, _ in py_deposits}
    assert dep_codes.isdisjoint(py_keep), f"freeze violated: {ctx} dep={dep_codes} keep={py_keep}"
    assert dep_codes.isdisjoint(lean_keep)


def test_recipe_material_is_task_item_freeze_case():
    """The documented FREEZE case: a recipe material of the items-task item is the
    very input PursueTask must gather/craft. It must be KEPT (never banked), even
    when it has a high sell value. Items: task item 1 crafts from materials 2 and 3;
    2 crafts from raw 4. All of 2, 3, 4 are recipe materials of the task item and
    must be protected."""
    # item 1 (task item) <- {2:2, 3:1}; item 2 <- {4:5}
    recipes = {1: {2: 2, 3: 1}, 2: {4: 5}}
    attrs = {
        1: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 10},
        2: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 99},
        3: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 88},
        4: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 77},
        5: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 50},
    }
    # inventory holds all materials (high sell value) plus an unrelated item 5
    inventory = {1: 1, 2: 3, 3: 4, 4: 5, 5: 2}
    equipped: list[int] = []
    task_code = 1
    task_is_items = True
    crafting_target = None
    fuel = 16

    py_keep, py_deposits, lean_keep, lean_deposits = _run(
        inventory, equipped, task_code, task_is_items, crafting_target, recipes, attrs, fuel
    )
    assert py_keep == lean_keep
    assert py_deposits == lean_deposits
    # materials 2, 3, 4 (and the task item 1) must all be kept; only 5 is depositable
    assert {1, 2, 3, 4}.issubset(py_keep), f"task inputs not protected: {py_keep}"
    dep_codes = {c for c, _ in py_deposits}
    assert dep_codes == {5}, f"only unrelated item 5 should deposit, got {dep_codes}"
    assert dep_codes.isdisjoint(py_keep)


def test_last_resort_at_full_bag_matches_lean():
    """free==0 with the whole bag keep-set: Python and Lean both bank ONE least-
    critical keep item (a recipe material here), agreeing exactly. This exercises the
    last-resort branch the older cases (inventory_max=1000) never reached."""
    recipes = {1: {2: 2, 3: 1}}  # task item 1 <- materials 2, 3 (both kept)
    attrs = {
        1: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 5},
        2: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 0},
        3: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 0},
    }
    inventory = {1: 1, 2: 3, 3: 4}  # used = 8 == inventory_max → free == 0
    py_keep, py_deposits, lean_keep, lean_deposits = _run(
        inventory, [], 1, True, None, recipes, attrs, 12, inventory_max=8,
    )
    assert py_keep == lean_keep
    assert py_deposits == lean_deposits  # last-resort agreement (codes AND order)
    assert len(py_deposits) == 1  # exactly one stack freed
    code, _ = py_deposits[0]
    # a recipe material (non-critical) is shed before the task item / coins.
    assert code in {2, 3} and code not in {TASKS_COIN_INT, 1}


def test_last_resort_at_slots_full_quantity_headroom_matches_lean():
    """SLOT-AWARE last-resort (follow-up 2026-07-09): every inventory SLOT is
    occupied (slots_free==0) but the total quantity cap has plenty of headroom
    (inventory_free>0), and the whole bag is keep-set. Python and Lean must BOTH
    fire the last-resort (banking one non-critical keep stack) — the older
    inventory_free==0-only gate never reached this reachable stall."""
    recipes = {1: {2: 1, 3: 1}}  # task item 1 <- materials 2, 3 (both kept)
    attrs = {
        1: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 5},
        2: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 0},
        3: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 0},
    }
    inventory = {1: 1, 2: 1, 3: 1}  # 3 stacks, total qty 3
    # inventory_max=100 → free = 97 > 0 (quantity headroom);
    # inventory_slots_max=3 → slots_used=3, slots_free=0 (all slots full).
    py_keep, py_deposits, lean_keep, lean_deposits = _run(
        inventory, [], 1, True, None, recipes, attrs, 12,
        inventory_max=100, inventory_slots_max=3,
    )
    assert py_keep == lean_keep
    assert py_deposits == lean_deposits  # slots-full last-resort agreement
    assert len(py_deposits) == 1  # exactly one stack freed to open a slot
    code, _ = py_deposits[0]
    # a recipe material (non-critical) sheds before the task item / coins.
    assert code in {2, 3} and code not in {TASKS_COIN_INT, 1}


def test_slots_full_with_bankable_uses_normal_path_matches_lean():
    """slots_free==0 but something is normally bankable → the NORMAL deposit path
    fires (not the last-resort), and Python and Lean agree even with the slot
    condition now live."""
    recipes: dict[int, dict[int, int]] = {}
    attrs = {
        1: {"type_": "weapon", "attack": 10, "is_tool": False, "hp_restore": 0, "sell": 5},
        2: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 7},
    }
    inventory = {1: 1, 2: 1}  # 2 stacks; slots_max=2 → slots_free=0, but qty headroom
    py_keep, py_deposits, lean_keep, lean_deposits = _run(
        inventory, [], None, False, None, recipes, attrs, 8,
        inventory_max=100, inventory_slots_max=2,
    )
    assert py_deposits == lean_deposits
    assert py_deposits == [(2, 1)]  # weapon kept; resource banked normally, no last-resort


def test_full_bag_with_bankable_uses_normal_path_matches_lean():
    """free==0 but something is normally bankable → the NORMAL deposit path fires (not
    the last-resort), and Python and Lean agree."""
    recipes: dict[int, dict[int, int]] = {}
    attrs = {
        1: {"type_": "weapon", "attack": 10, "is_tool": False, "hp_restore": 0, "sell": 5},
        2: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 7},
    }
    inventory = {1: 1, 2: 5}  # used = 6 == inventory_max → free == 0
    py_keep, py_deposits, lean_keep, lean_deposits = _run(
        inventory, [], None, False, None, recipes, attrs, 8, inventory_max=6,
    )
    assert py_deposits == lean_deposits
    assert py_deposits == [(2, 5)]  # weapon kept; resource banked normally, no last-resort


def test_best_weapon_protected_over_tool():
    """The best fighting weapon (max-attack non-tool weapon over inv+equipped) is
    kept; a TOOL is not a fighting-weapon candidate (argmax tie rule pinned
    against Lean) but IS kept by the banked-tool ferry protection (2026-07-05):
    the working kit never deposits."""
    recipes: dict[int, dict[int, int]] = {}
    attrs = {
        1: {"type_": "weapon", "attack": 30, "is_tool": False, "hp_restore": 0, "sell": 5},
        2: {"type_": "weapon", "attack": 50, "is_tool": True, "hp_restore": 0, "sell": 5},  # tool
        3: {"type_": "weapon", "attack": 20, "is_tool": False, "hp_restore": 0, "sell": 5},
    }
    inventory = {1: 1, 2: 1, 3: 1}
    py_keep, py_deposits, lean_keep, lean_deposits = _run(
        inventory, [], None, False, None, recipes, attrs, 8
    )
    assert py_keep == lean_keep
    assert py_deposits == lean_deposits
    # best fighting weapon = item 1 (attack 30, non-tool). Item 2 is a tool —
    # excluded from the weapon argmax but KEPT as the working gathering kit.
    assert 1 in py_keep and 2 in py_keep
    dep_codes = {c for c, _ in py_deposits}
    assert dep_codes == {3}, f"only the weaker weapon should deposit, got {dep_codes}"
