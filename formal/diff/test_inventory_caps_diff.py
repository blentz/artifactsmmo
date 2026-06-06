"""Differential test: real Python `useful_quantity_cap` / `overstocked_items` must
agree with the proved Lean `cap` / `overstock`.

`useful_quantity_cap` reads four game-data/state inputs:
* `recipe_max` = `game_data.max_recipe_demand(code)`  -> recipe component
* the active items-task demand (`task_type == "items" ∧ task_code == code`)
* `ACTION_CONSUMABLES_CAP.get(code, 0)`  (9 for tasks_coin, else 0)
* equippable: `ITEM_TYPE_TO_SLOTS.get(stats.type_)` truthy
plus the equipped floor (`code in state.equipment.values()`).

We control all of them exactly to isolate the max/floor clamp against Lean:
* `max_recipe_demand` is monkeypatched to return the chosen `recipe_demand`.
* `item_stats` is monkeypatched to return a stub whose `type_` is equippable
  ("weapon") or not ("resource"), matching the chosen `equippable` flag.
* The item code is chosen as `tasks_coin` (action_cap 9) or `"X"` (action_cap 0).
* The WorldState carries the items-task demand and the equipment so the Python
  task_cap and equipped floor match the Lean inputs.

For the OVERSTOCK side, the inventory holds `qty` of the code; the Python
`overstocked_items` excess (or absence) must equal the Lean `overstock`.
"""
from hypothesis import given, settings, strategies as st
from pytest import MonkeyPatch

import artifactsmmo_cli.ai.inventory_caps as ic_mod
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState
from formal.diff.oracle_client import run_oracle


def _make_state(code: str, task_remaining: int, equipped: bool, qty: int) -> WorldState:
    if task_remaining > 0:
        task_type = "items"
        task_code = code
        task_total = task_remaining
        task_progress = 0
    else:
        # Not an active items-task for this code -> task_cap == 0.
        task_type = "monsters"
        task_code = "OTHER"
        task_total = 5
        task_progress = 5
    equipment = {"weapon": code} if equipped else {}
    inventory = {code: qty} if qty != 0 else {}
    return WorldState(
        character="c", level=1, xp=0, max_xp=100, hp=10, max_hp=10, gold=0,
        skills={}, x=0, y=0, inventory=inventory, inventory_max=1000,
        equipment=equipment, cooldown_expires=None, task_code=task_code,
        task_type=task_type, task_progress=task_progress, task_total=task_total,
        bank_items=None, bank_gold=None, pending_items=None,
    )


class _FakeGameData:
    pass


@settings(max_examples=300)
@given(
    recipe_demand=st.integers(min_value=0, max_value=12),
    equippable=st.booleans(),
    use_coin=st.booleans(),
    is_healing=st.booleans(),
    task_remaining=st.integers(min_value=0, max_value=30),
    equipped=st.booleans(),
    qty=st.integers(min_value=0, max_value=80),
    # vary batch_buffer (incl. small values) so the SAFETY_FLOOR clamp is
    # actually exercised: with buffer 1 and demand 1, recipe_cap=1 < floor 3.
    batch_buffer=st.integers(min_value=1, max_value=5),
    safety_floor=st.integers(min_value=1, max_value=5),
)
def test_python_matches_lean(recipe_demand, equippable, use_coin, is_healing,
                             task_remaining, equipped, qty, batch_buffer,
                             safety_floor):
    code = TASKS_COIN_CODE if use_coin else "X"
    # Read action_cap from the actual Python constant (raised to 999 by
    # 602f7b4 because tasks_coin stacks). The Lean model takes actionCap
    # as a parameter, so the model stays correct; pass the same value the
    # Python code uses.
    action_cap = ic_mod.ACTION_CONSUMABLES_CAP.get(code, 0)
    item_type = "weapon" if equippable else "resource"
    # hp_restore activates the consumable cap (f1f8941, c3b8dfa). Generate
    # both branches: hp_restore=0 (cap inert) AND hp_restore>0 (cap kicks in).
    hp_restore_val = 20 if is_healing else 0
    stats = ItemStats(code=code, level=1, type_=item_type,
                       hp_restore=hp_restore_val)

    with MonkeyPatch.context() as mp:
        mp.setattr(_FakeGameData, "max_recipe_demand",
                   lambda self, c: recipe_demand, raising=False)
        mp.setattr(_FakeGameData, "item_stats",
                   lambda self, c: stats, raising=False)
        game_data = _FakeGameData()
        state = _make_state(code, task_remaining, equipped, qty)
        py_cap = ic_mod.useful_quantity_cap(code, state, game_data,
                                            batch_buffer, safety_floor)
        py_over = ic_mod.overstocked_items(state, game_data,
                                           batch_buffer, safety_floor)

        # Compute the per-component values Python would feed to the Lean
        # model: equippable_cap and consumable_cap come from the same
        # predicates Python applies in `useful_quantity_cap_excl_equipped`.
        # ITEM_TYPE_TO_SLOTS check matches the production wrapper.
        from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
        equippable_cap = (
            ic_mod.EQUIPPABLE_KEEP
            if (stats.type_ and ITEM_TYPE_TO_SLOTS.get(stats.type_)
                and not ic_mod._is_equippable_dominated(code, state, game_data))
            else 0
        )
        consumable_cap = (
            ic_mod.CONSUMABLE_KEEP if stats.hp_restore > 0 else 0
        )

    lean = run_oracle(
        "inventory_caps",
        [[batch_buffer, safety_floor, recipe_demand,
          equippable_cap, consumable_cap,
          action_cap, task_remaining,
          1 if equipped else 0, qty]],
    )[0]

    assert py_cap == lean["cap"], (
        f"cap mismatch: py={py_cap} lean={lean['cap']} "
        f"recipe={recipe_demand} equippable_cap={equippable_cap} "
        f"consumable_cap={consumable_cap} action={action_cap} "
        f"task_rem={task_remaining} equipped={equipped}"
    )
    # overstocked_items records excess only when qty > 0 and qty > cap.
    py_excess = py_over.get(code, 0)
    assert py_excess == lean["overstock"], (
        f"overstock mismatch: py={py_excess} lean={lean['overstock']}"
    )


def test_safety_floor_binds_against_lean():
    """Deterministic case where the recipe component is below the safety floor
    and is the binding maximum, so the floor clamp is the only thing keeping
    `cap` at SAFETY_FLOOR. Pins the floor against Lean (kills "drop floor"
    mutants the random search may miss)."""
    code = "X"
    # recipe_demand=1, batch_buffer=1 -> raw recipe_cap=1; safety_floor=3 floors it to 3.
    # No task/action/equippable/equipped components -> cap == recipe_cap == 3.
    stats = ItemStats(code=code, level=1, type_="resource")
    with MonkeyPatch.context() as mp:
        mp.setattr(_FakeGameData, "max_recipe_demand", lambda self, c: 1, raising=False)
        mp.setattr(_FakeGameData, "item_stats", lambda self, c: stats, raising=False)
        game_data = _FakeGameData()
        # qty=2 sits between raw recipe_cap (1) and the floored cap (3): with the
        # floor, qty 2 <= cap 3 -> NOT overstocked; without it, cap 1 -> overstock 1.
        state = _make_state(code, task_remaining=0, equipped=False, qty=2)
        py_cap = ic_mod.useful_quantity_cap(code, state, game_data, 1, 3)
        py_over = ic_mod.overstocked_items(state, game_data, 1, 3)

    lean = run_oracle("inventory_caps", [[1, 3, 1, 0, 0, 0, 0, 0, 2]])[0]
    assert py_cap == 3
    assert py_cap == lean["cap"]
    assert py_over.get(code, 0) == lean["overstock"] == 0


def test_equipped_floor_binds_against_lean():
    """Deterministic case where every component is 0 but the item is equipped,
    so the equipped floor is the only thing keeping `cap` at 1. Pins the floor
    against Lean (kills "drop equipped floor" mutants the random search may
    miss)."""
    code = "X"
    stats = ItemStats(code=code, level=1, type_="resource")  # not equippable
    with MonkeyPatch.context() as mp:
        mp.setattr(_FakeGameData, "max_recipe_demand", lambda self, c: 0, raising=False)
        mp.setattr(_FakeGameData, "item_stats", lambda self, c: stats, raising=False)
        game_data = _FakeGameData()
        # equipped, no recipe/task/action/equippable demand, qty=1:
        # with the floor, cap=1 -> qty 1 <= 1 -> NOT overstocked;
        # without it, cap=0 -> overstock 1.
        state = _make_state(code, task_remaining=0, equipped=True, qty=1)
        py_cap = ic_mod.useful_quantity_cap(code, state, game_data)
        py_over = ic_mod.overstocked_items(state, game_data)

    lean = run_oracle("inventory_caps", [[5, 3, 0, 0, 0, 0, 0, 1, 1]])[0]
    assert py_cap == 1
    assert py_cap == lean["cap"]
    assert py_over.get(code, 0) == lean["overstock"] == 0


# -----------------------------------------------------------------------------
# Predicate-level differential: the new equipCapValue / consumableCapValue /
# equipCapFromPeers models prove the Python predicates compose into the Lean-
# modeled component values. Without these tests the Lean predicates exist but
# their Python<->Lean parity isn't checked.
# -----------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    is_equippable=st.booleans(),
    is_dominated=st.booleans(),
)
def test_equip_cap_value_matches_lean(is_equippable, is_dominated):
    """Lean's `equipCapValue` proves: cap=EQUIPPABLE_KEEP iff equippable AND
    NOT dominated; cap=0 otherwise. Python's `useful_quantity_cap_excl_equipped`
    composes the same two predicates inline. Cross-check the composition."""
    py_cap = (
        ic_mod.EQUIPPABLE_KEEP
        if (is_equippable and not is_dominated) else 0
    )
    lean = run_oracle(
        "equip_cap_value",
        [[1 if is_equippable else 0, 1 if is_dominated else 0]],
    )[0]
    assert py_cap == lean["equippable_cap"]


@settings(max_examples=200)
@given(hp_restore=st.integers(min_value=-50, max_value=100))
def test_consumable_cap_value_matches_lean(hp_restore):
    """Lean's `consumableCapValue` proves: cap=CONSUMABLE_KEEP iff hp_restore
    > 0; cap=0 otherwise. The negative-hp_restore branch is also covered
    (sanity — hp_restore is an Int in the API but is meant to be non-negative)."""
    py_cap = ic_mod.CONSUMABLE_KEEP if hp_restore > 0 else 0
    lean = run_oracle("consumable_cap_value", [[hp_restore]])[0]
    assert py_cap == lean["consumable_cap"]


@settings(max_examples=200)
@given(
    is_equippable=st.booleans(),
    slot_count=st.integers(min_value=1, max_value=4),
    peers=st.lists(
        st.tuples(
            st.booleans(),  # fitsAllSlots
            st.booleans(),  # strictlyHigher
            st.booleans(),  # coversSkillEffects
            st.integers(min_value=0, max_value=5),  # ownedCount
        ),
        min_size=0, max_size=6,
    ),
)
def test_equip_cap_from_peers_matches_lean(is_equippable, slot_count, peers):
    """Lean's `equipCapFromPeers` proves the dominance algorithm: a candidate
    is dominated when qualifying-peer owned count meets/exceeds slotCount.
    Replicate the algorithm in Python, then compare cap outputs."""
    # Python mirror of dominatorOwned + isDominatedBy + equipCapValue.
    dominator_owned = 0
    for fits, higher, covers, owned in peers:
        if fits and higher and covers:
            dominator_owned += owned
    is_dominated = dominator_owned >= slot_count
    py_cap = (
        ic_mod.EQUIPPABLE_KEEP
        if (is_equippable and not is_dominated) else 0
    )

    args = [1 if is_equippable else 0, slot_count, len(peers)]
    for fits, higher, covers, owned in peers:
        args.extend([
            1 if fits else 0,
            1 if higher else 0,
            1 if covers else 0,
            owned,
        ])
    lean = run_oracle("equip_cap_from_peers", [args])[0]
    assert py_cap == lean["equippable_cap"]


def test_equip_cap_from_peers_nil_undominated():
    """Pin the empty-peer-list theorem (`isDominatedBy_nil_of_positive_slot`):
    no peers + any positive slotCount → not dominated → cap = EQUIPPABLE_KEEP
    when equippable."""
    for slot_count in (1, 2, 3, 4):
        lean = run_oracle(
            "equip_cap_from_peers",
            [[1, slot_count, 0]],  # equippable=1, no peers
        )[0]
        assert lean["equippable_cap"] == ic_mod.EQUIPPABLE_KEEP


def test_equip_cap_from_peers_dominated_zero():
    """Pin the dominance-supersedes theorem
    (`equipCapFromPeers_dominated`): even if equippable=true, when
    qualifying-peer owned count meets slotCount, cap = 0."""
    # 1 fully-qualifying peer with ownedCount=2 vs slotCount=2 → dominated.
    args = [1, 2, 1,
            1, 1, 1, 2]  # peer: fits, higher, covers, owned=2
    lean = run_oracle("equip_cap_from_peers", [args])[0]
    assert lean["equippable_cap"] == 0
