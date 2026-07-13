"""Differential test: the real Python `select_bank_deposits` (and
`hard_critical_codes`) must agree with the proved Lean `bank_selection` oracle
over random states.

`select_bank_deposits(state, game_data, ctx)` is QUANTITY-typed: for every held
code it banks `inventory_keep.bankable(code) = max(0, bag - keep_in_bag(code))`,
sorted by `(-sell_value, code)`. It used to compute a keep-SET and bank whole
stacks; a code-set can only mean "keep ALL copies", which is why 18 copper_axe
were never banked. Both sides are driven through that change here.

**What is bound, and how.** `keep_in_bag` is OPAQUE on the Lean side (the keep
authority's combinator is proved in `Formal.InventoryKeep`; its reasons are
game-data searches). So this harness calls the REAL
`inventory_keep.keep_in_bag` for every code in the state's universe and feeds the
resulting quantity vector to the oracle — the same discipline
`test_inventory_keep_diff.py` uses. Nothing is reimplemented: the Python side is
the production `select_bank_deposits`, the Lean side is the proved selector over
the SAME keep quantities. A divergence therefore means the SELECTOR (the surplus
arithmetic, the sort, the last-resort branch) drifted from the proof.

We use integer item codes (the Lean model uses `Nat`) and drive the REAL Python
via a real `GameData` (with `_item_stats`, `_crafting_recipes`, `_npc_sell_prices`
populated) and a real `WorldState`. We assert over >= 200 random states:
* the hard-critical set matches (the last-resort criticality ranking: coin, task
  item, HP consumables, best fighting weapon, working gathering tool),
* the deposit list matches EXACTLY (codes, QUANTITIES and order),
* no deposit eats a kept copy: `held - deposited == keep_in_bag` (the freeze,
  re-cast onto copies — the property the keep-SET could not express).
"""
import random

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.bank_selection import hard_critical_codes, select_bank_deposits
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.inventory_keep import keep_in_bag
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState
from formal.diff.oracle_client import run_oracle

# tasks_coin is the string TASKS_COIN_CODE; we reserve integer code 0 to mean it.
TASKS_COIN_INT = 0


def _code(n: int) -> str:
    """Map an integer code to a string item code (0 == the tasks coin)."""
    return TASKS_COIN_CODE if n == TASKS_COIN_INT else f"item_{n}"


def _int(code: str) -> int:
    return TASKS_COIN_INT if code == TASKS_COIN_CODE else int(code[len("item_"):])


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
    task_total: int = 0,
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
        task_total=task_total,
        bank_items=None,
        bank_gold=None,
        pending_items=None,
        crafting_target=(_code(crafting_target) if crafting_target is not None else None),
    )


def _keep_vector(state: WorldState, gd: GameData) -> list[tuple[int, int]]:
    """`(code, keep_in_bag(code))` over the state's whole code universe, from the
    REAL keep authority. This is what makes the Lean side's opaque `keepInBag`
    the SAME function production uses (see the module docstring)."""
    universe: set[str] = set(state.inventory) | {TASKS_COIN_CODE}
    universe.update(c for c in state.equipment.values() if c)
    if state.task_code:
        universe.add(state.task_code)
    return sorted(
        (_int(code), keep_in_bag(code, state, gd, NO_PROFILE_CONTEXT))
        for code in universe
    )


def _encode_args(
    state: WorldState,
    gd: GameData,
    inventory: dict[int, int],
    equipped: list[int],
    task_code: int | None,
    attrs: dict[int, dict],
    inventory_max: int,
    inventory_slots_max: int | None,
) -> list[int]:
    args: list[int] = [TASKS_COIN_INT]
    args += [1, task_code] if task_code is not None else [0, 0]
    inv_items = list(inventory.items())
    args += [len(inv_items)]
    for code, qty in inv_items:
        args += [code, qty]
    args += [len(equipped)]
    args += list(equipped)
    attr_items = list(attrs.items())
    args += [len(attr_items)]
    for code, a in attr_items:
        is_weapon = 1 if a["type_"] == "weapon" else 0
        args += [code, a["attack"], is_weapon, 1 if a["is_tool"] else 0,
                 a["hp_restore"], a["sell"]]
    keep = _keep_vector(state, gd)
    args += [len(keep)]
    for code, qty in keep:
        args += [code, qty]
    slots_max = inventory_slots_max if inventory_slots_max is not None else inventory_max
    args += [inventory_max, slots_max]
    return args


def _run(inventory, equipped, task_code, task_is_items, crafting_target, recipes, attrs,
         inventory_max=1000, inventory_slots_max=None, task_total=0):
    gd = _build_game_data(recipes, attrs)
    state = _build_state(inventory, equipped, task_code, task_is_items, crafting_target,
                         inventory_max, inventory_slots_max, task_total)

    py_critical = {_int(c) for c in hard_critical_codes(state, gd)}
    py_deposits = [(_int(c), q) for c, q in select_bank_deposits(state, gd)]

    args = _encode_args(state, gd, inventory, equipped, task_code, attrs,
                        inventory_max, inventory_slots_max)
    lean = run_oracle("bank_selection", [args])[0]
    lean_critical = set(lean["critical"])
    lean_deposits = [(cq[0], cq[1]) for cq in lean["deposits"]]
    return state, gd, py_critical, py_deposits, lean_critical, lean_deposits


def _assert_freeze(state: WorldState, gd: GameData, py_deposits) -> None:
    """The freeze, re-cast onto COPIES: whatever is banked, the bag retains exactly
    `keep_in_bag` of that code — never fewer. (On the last-resort branch a protected
    stack IS banked on purpose to free a slot; that branch is checked separately by
    the dedicated last-resort tests, which assert WHICH stack is shed.)"""
    for code_int, qty in py_deposits:
        code = _code(code_int)
        keep = keep_in_bag(code, state, gd, NO_PROFILE_CONTEXT)
        held = state.inventory[code]
        if held > keep:  # the normal (surplus) path
            assert held - qty == keep, (code, held, qty, keep)


def _rand_state(rng: random.Random):
    """Random bank-selection state over integer item codes 1..n (0 = tasks coin)."""
    n = rng.randint(1, 8)
    items = list(range(1, n + 1))
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
    if rng.random() < 0.4:
        inventory[TASKS_COIN_INT] = rng.randint(1, 5)
        attrs[TASKS_COIN_INT] = {"type_": "currency", "attack": 0, "is_tool": False,
                                 "hp_restore": 0, "sell": 0}
    equipped = rng.sample(items, rng.randint(0, min(3, len(items))))
    task_code = rng.choice(items) if rng.random() < 0.6 else None
    task_is_items = task_code is not None and rng.random() < 0.6
    # A REAL task carries a quantity: the ACTIVE_TASK / COMMITTED_RECIPE keep
    # quantities scale with what the task still owes (0 protects nothing).
    task_total = rng.randint(0, 4) if task_code is not None else 0
    crafting_target = rng.choice(items) if rng.random() < 0.6 else None
    return (inventory, equipped, task_code, task_is_items, crafting_target, recipes,
            attrs, 1000, None, task_total)


@settings(max_examples=240, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_python_matches_lean(seed):
    rng = random.Random(seed)
    scenario = _rand_state(rng)
    state, gd, py_crit, py_deposits, lean_crit, lean_deposits = _run(*scenario)
    ctx = f"seed={seed} state={scenario}"
    assert py_crit == lean_crit, f"critical mismatch: {ctx}\n py={py_crit} lean={lean_crit}"
    assert py_deposits == lean_deposits, (
        f"deposits mismatch (quantities AND order matter): {ctx}\n"
        f" py={py_deposits} lean={lean_deposits}"
    )
    _assert_freeze(state, gd, py_deposits)


def test_task_recipe_material_surplus_banks_but_the_demand_stays():
    """The documented FREEZE case, re-cast as a quantity. A recipe material of the
    items-task item is the very input PursueTask must gather/craft: the DEMANDED
    copies are never banked, even at a high sell value. The copies ABOVE the demand
    ARE banked — that is the fix, and the old code-set could not do it.

    Items: task item 1 crafts from 2 (x2) and 3 (x1); 2 crafts from raw 4 (x5).
    Task owes 1 unit → demand: 2 -> 2, 3 -> 1, 4 -> 10."""
    recipes = {1: {2: 2, 3: 1}, 2: {4: 5}}
    attrs = {
        1: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 10},
        2: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 99},
        3: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 88},
        4: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 77},
        5: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 50},
    }
    # Holds MORE than the demand of every material, plus an unrelated item 5.
    inventory = {1: 1, 2: 3, 3: 4, 4: 12, 5: 2}
    state, gd, py_crit, py_deposits, lean_crit, lean_deposits = _run(
        inventory, [], 1, True, None, recipes, attrs, task_total=1,
    )
    assert py_crit == lean_crit
    assert py_deposits == lean_deposits
    _assert_freeze(state, gd, py_deposits)

    banked = dict(py_deposits)
    # The demanded copies STAY: 2 of item 2, 1 of item 3, 10 of item 4, 1 of the
    # task item itself.
    assert inventory[1] - banked.get(1, 0) == 1
    assert inventory[2] - banked.get(2, 0) == 2
    assert inventory[3] - banked.get(3, 0) == 1
    assert inventory[4] - banked.get(4, 0) == 10
    # ...and the surplus above each demand banks, along with all of the unrelated 5.
    assert banked[2] == 1 and banked[3] == 3 and banked[4] == 2 and banked[5] == 2


def test_working_tool_spares_bank_and_the_kit_stays():
    """THE hoard, differentially. 18 copies of the best gathering tool: Python and
    Lean must BOTH select 17 and leave 1."""
    attrs = {
        1: {"type_": "weapon", "attack": 5, "is_tool": True, "hp_restore": 0, "sell": 4},
        2: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 9},
    }
    inventory = {1: 18, 2: 2}
    state, gd, py_crit, py_deposits, lean_crit, lean_deposits = _run(
        inventory, [], None, False, None, {}, attrs,
    )
    assert py_deposits == lean_deposits
    assert dict(py_deposits)[1] == 17
    assert 1 in py_crit  # the working tool is shed LAST by the last-resort
    _assert_freeze(state, gd, py_deposits)


def test_tasks_coin_keep_all_never_banked():
    """`KEEP_ALL` (1e6) at the deposit boundary: no coin deposit, no absurd
    quantity, and Lean agrees on the same clamp."""
    attrs = {
        TASKS_COIN_INT: {"type_": "currency", "attack": 0, "is_tool": False,
                         "hp_restore": 0, "sell": 0},
        1: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 9},
    }
    inventory = {TASKS_COIN_INT: 40, 1: 3}
    state, gd, _pc, py_deposits, _lc, lean_deposits = _run(
        inventory, [], None, False, None, {}, attrs,
    )
    assert py_deposits == lean_deposits
    assert py_deposits == [(1, 3)]  # the coin yields NOTHING, at any quantity


def test_last_resort_at_full_bag_matches_lean():
    """free==0 with NOTHING bankable (every held code at/below its cap): Python and
    Lean both bank ONE least-critical stack, agreeing exactly. This exercises the
    last-resort branch the random states (inventory_max=1000) never reach."""
    recipes = {1: {2: 2, 3: 1}}  # task item 1 <- materials 2, 3
    attrs = {
        1: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 5},
        2: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 0},
        3: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 0},
    }
    # Task owes 4 → demand 8 of item 2 and 4 of item 3: nothing held is surplus.
    inventory = {1: 1, 2: 3, 3: 4}  # used = 8 == inventory_max → free == 0
    _st, _gd, py_crit, py_deposits, lean_crit, lean_deposits = _run(
        inventory, [], 1, True, None, recipes, attrs, inventory_max=8, task_total=4,
    )
    assert py_crit == lean_crit
    assert py_deposits == lean_deposits  # last-resort agreement (codes AND order)
    assert len(py_deposits) == 1  # exactly one stack freed
    code, _ = py_deposits[0]
    # a recipe material (non-critical) is shed before the task item / coins.
    assert code in {2, 3} and code not in {TASKS_COIN_INT, 1}


def test_last_resort_at_slots_full_quantity_headroom_matches_lean():
    """SLOT-AWARE last-resort: every inventory SLOT is occupied (slots_free==0) but
    the quantity cap has headroom (inventory_free>0), and nothing is bankable. Python
    and Lean must BOTH fire the last-resort."""
    recipes = {1: {2: 1, 3: 1}}
    attrs = {
        1: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 5},
        2: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 0},
        3: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 0},
    }
    inventory = {1: 1, 2: 1, 3: 1}  # 3 stacks, total qty 3, all at their cap
    _st, _gd, py_crit, py_deposits, lean_crit, lean_deposits = _run(
        inventory, [], 1, True, None, recipes, attrs,
        inventory_max=100, inventory_slots_max=3, task_total=1,
    )
    assert py_crit == lean_crit
    assert py_deposits == lean_deposits  # slots-full last-resort agreement
    assert len(py_deposits) == 1  # exactly one stack freed to open a slot
    code, _ = py_deposits[0]
    assert code in {2, 3} and code not in {TASKS_COIN_INT, 1}


def test_slots_full_with_bankable_uses_normal_path_matches_lean():
    """slots_free==0 but something IS bankable → the NORMAL surplus path fires (not
    the last-resort), and Python and Lean agree."""
    attrs = {
        1: {"type_": "weapon", "attack": 10, "is_tool": False, "hp_restore": 0, "sell": 5},
        2: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 7},
    }
    inventory = {1: 1, 2: 1}  # 2 stacks; slots_max=2 → slots_free=0, but qty headroom
    _st, _gd, _pc, py_deposits, _lc, lean_deposits = _run(
        inventory, [], None, False, None, {}, attrs,
        inventory_max=100, inventory_slots_max=2,
    )
    assert py_deposits == lean_deposits
    assert py_deposits == [(2, 1)]  # weapon kept (COMBAT_WEAPON=1); resource banked


def test_full_bag_with_bankable_uses_normal_path_matches_lean():
    """free==0 but something IS bankable → the NORMAL path fires, not the
    last-resort, and Python and Lean agree."""
    attrs = {
        1: {"type_": "weapon", "attack": 10, "is_tool": False, "hp_restore": 0, "sell": 5},
        2: {"type_": "resource", "attack": 0, "is_tool": False, "hp_restore": 0, "sell": 7},
    }
    inventory = {1: 1, 2: 5}  # used = 6 == inventory_max → free == 0
    _st, _gd, _pc, py_deposits, _lc, lean_deposits = _run(
        inventory, [], None, False, None, {}, attrs, inventory_max=6,
    )
    assert py_deposits == lean_deposits
    assert py_deposits == [(2, 5)]  # weapon kept; resource banked normally


def test_best_weapon_kept_over_tool_and_worse_weapon():
    """The best fighting weapon (max-attack non-tool over inv+equipped) keeps ONE
    copy; a TOOL is not a fighting-weapon candidate (the argmax tie rule, pinned
    against Lean) but keeps one of its own as the working kit. The WORSE weapon has
    no keep reason at all and banks entirely."""
    attrs = {
        1: {"type_": "weapon", "attack": 30, "is_tool": False, "hp_restore": 0, "sell": 5},
        2: {"type_": "weapon", "attack": 50, "is_tool": True, "hp_restore": 0, "sell": 5},
        3: {"type_": "weapon", "attack": 20, "is_tool": False, "hp_restore": 0, "sell": 5},
    }
    inventory = {1: 1, 2: 1, 3: 1}
    state, gd, py_crit, py_deposits, lean_crit, lean_deposits = _run(
        inventory, [], None, False, None, {}, attrs,
    )
    assert py_crit == lean_crit
    assert py_deposits == lean_deposits
    # best fighting weapon = item 1 (attack 30, non-tool); item 2 is a tool —
    # excluded from the weapon argmax but kept as the working gathering kit.
    assert 1 in py_crit and 2 in py_crit
    assert [c for c, _ in py_deposits] == [3], "only the weaker weapon should deposit"
    _assert_freeze(state, gd, py_deposits)
