"""Tests for the guard ladder (state-pressure interrupts + prerequisite gates)."""

from unittest.mock import patch

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.guards import (
    GUARD_ORDER,
    GuardKind,
    SelectionContext,
    _fires,
    active_guards,
)
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _ctx as driver_ctx


def _ctx(**kw) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None)
    base.update(kw)
    return SelectionContext(**base)


def _combat_gd(monster_hp: int, monster_attack: dict[str, int]) -> GameData:
    gd = GameData()
    gd._monster_hp = {"mob": monster_hp}
    gd._monster_attack = {"mob": monster_attack}
    gd._monster_resistance = {"mob": {}}
    gd._monster_critical_strike = {"mob": 0}
    gd._monster_initiative = {"mob": 10}
    gd._monster_level = {"mob": 1}
    return gd


def test_rest_for_combat_silent_when_already_winnable_at_current_hp():
    """When the player can already win at CURRENT hp (predict_win True), there's
    nothing to rest for — the guard stays inert even though hp < max_hp."""
    # Strong player vs weak mob: wins even while hurt.
    state = make_state(hp=40, max_hp=100, attack={"fire": 50}, initiative=90)
    gd = _combat_gd(monster_hp=5, monster_attack={"fire": 1})
    assert _fires(GuardKind.REST_FOR_COMBAT, state, gd, None,
                  _ctx(combat_monster="mob")) is False


def test_rest_for_combat_fires_when_winnable_only_at_max_hp():
    """Hurt player loses now but would win at full hp -> the guard fires so the
    bot rests before engaging."""
    # At hp=12 the mob's hits kill the player first; at max_hp=100 it survives.
    state = make_state(hp=12, max_hp=100, attack={"fire": 8}, initiative=5)
    gd = _combat_gd(monster_hp=40, monster_attack={"fire": 10})
    assert _fires(GuardKind.REST_FOR_COMBAT, state, gd, None,
                  _ctx(combat_monster="mob")) is True


def test_hp_critical_fires_below_quarter_and_outranks_all():
    state = make_state(hp=10, max_hp=100)            # 10% < 0.25
    guards = active_guards(state, GameData(), None, _ctx())
    assert guards[0] is GuardKind.HP_CRITICAL


def test_no_guards_when_calm():
    state = make_state(hp=100, max_hp=100, inventory={}, inventory_max=20)
    assert active_guards(state, GameData(), None, _ctx(bank_accessible=True)) == []


def test_guard_order_is_ladder_order():
    state = make_state(hp=10, max_hp=100, inventory={"x": 20}, inventory_max=20, bank_items={})
    guards = active_guards(state, GameData(), None, _ctx(bank_accessible=True))
    assert guards == [g for g in GUARD_ORDER if g in guards]


def test_reach_unlock_level_fires_within_gap():
    state = make_state(level=3, hp=100, max_hp=100)
    guards = active_guards(state, GameData(), None, _ctx(bank_required_level=5))
    assert GuardKind.REACH_UNLOCK_LEVEL in guards


def test_reach_unlock_level_silent_beyond_gap():
    state = make_state(level=3, hp=100, max_hp=100)
    guards = active_guards(state, GameData(), None, _ctx(bank_required_level=20))
    assert GuardKind.REACH_UNLOCK_LEVEL not in guards


def test_deposit_full_fires_when_inventory_high_and_depositable_item():
    # inventory_max=10, inventory={"ore": 9} → 90% ≥ 0.90
    # "ore" is not tasks_coin, not task item, not HP item, not a weapon
    # → select_bank_deposits returns [("ore", 9)]
    # bank has room: 0 items < capacity 50
    state = make_state(
        hp=100, max_hp=100,
        inventory={"ore": 9},
        inventory_max=10,
        bank_items={},
    )
    gd = GameData()
    gd._bank_capacity = 50
    guards = active_guards(state, gd, None, _ctx(bank_accessible=True))
    assert GuardKind.DEPOSIT_FULL in guards


def test_used_fraction_zero_when_inventory_max_zero():
    # Covers the inventory_max <= 0 branch in _used_fraction.
    # With inventory_max=0 no guard that checks fraction should fire.
    state = make_state(hp=100, max_hp=100, inventory={}, inventory_max=0)
    guards = active_guards(state, GameData(), None, _ctx(bank_accessible=True))
    assert guards == []


def test_bank_unlock_fires_when_monster_set_and_bank_not_accessible():
    # BANK_UNLOCK guard: bank_unlock_monster set, bank_accessible=False, xp == initial_xp,
    # monster_level unknown (returns 0) → fires (target_level == 0 branch).
    state = make_state(hp=100, max_hp=100, xp=0, level=1)
    guards = active_guards(
        state, GameData(), None,
        _ctx(bank_accessible=False, bank_unlock_monster="goblin", initial_xp=0),
    )
    assert GuardKind.BANK_UNLOCK in guards


def test_bank_unlock_silent_when_xp_earned():
    # BANK_UNLOCK guard: state.xp > initial_xp → does NOT fire.
    state = make_state(hp=100, max_hp=100, xp=50, level=1)
    guards = active_guards(
        state, GameData(), None,
        _ctx(bank_accessible=False, bank_unlock_monster="goblin", initial_xp=0),
    )
    assert GuardKind.BANK_UNLOCK not in guards


def test_bank_unlock_fires_when_level_meets_threshold():
    # BANK_UNLOCK: target_level returned as 5, player level=4 (>= 5-1=4) → fires.
    gd = GameData()
    gd._monster_level["goblin"] = 5
    state = make_state(hp=100, max_hp=100, xp=0, level=4)
    guards = active_guards(
        state, gd, None,
        _ctx(bank_accessible=False, bank_unlock_monster="goblin", initial_xp=0),
    )
    assert GuardKind.BANK_UNLOCK in guards


def test_deposit_full_silent_when_bank_inaccessible():
    state = make_state(hp=100, max_hp=100, inventory={"copper_ore": 9}, inventory_max=10, bank_items={})
    guards = active_guards(state, GameData(), None, _ctx(bank_accessible=False))
    assert GuardKind.DEPOSIT_FULL not in guards


def test_fires_returns_false_for_unknown_guard_kind():
    # Covers the defensive `return False` fallthrough at the end of _fires.
    # Patch GuardKind to inject a value not handled by any if-branch.
    state = make_state(hp=100, max_hp=100)
    ctx = _ctx()
    unknown = object()  # not a GuardKind member
    with patch("artifactsmmo_cli.ai.tiers.guards.GUARD_ORDER", (unknown,)):  # type: ignore[arg-type]
        result = _fires(unknown, state, GameData(), None, ctx)  # type: ignore[arg-type]
    assert result is False


def test_gear_review_in_guard_order_below_survival_above_none():
    # GEAR_REVIEW is the LAST guard (lowest-priority guard, still above all means).
    assert GUARD_ORDER[-1] is GuardKind.GEAR_REVIEW
    assert GuardKind.HP_CRITICAL in GUARD_ORDER[:GUARD_ORDER.index(GuardKind.GEAR_REVIEW)]


def test_gear_review_fires_only_when_ctx_active(make_planner_gd):
    state = make_state(hp=150, max_hp=150)
    active_ctx = driver_ctx(gear_review_active=True)
    inactive_ctx = driver_ctx(gear_review_active=False)
    assert GuardKind.GEAR_REVIEW in active_guards(state, make_planner_gd, None, active_ctx)
    assert GuardKind.GEAR_REVIEW not in active_guards(state, make_planner_gd, None, inactive_ctx)


def test_discard_high_silent_when_step_profile_protects_goal_item():
    """Trace 2026-06-11 22:36 (run-4 cycle 30): DISCARD_HIGH fired and deleted
    a wooden_shield while the active step goal
    GatherMaterials(wooden_shield, {wooden_shield: 3}) was accumulating shields
    for the gearcrafting grind — the step goal's needed map was invisible to
    the discard profile (which only covers crafting_target/gear/tools/task).
    The active step's needed map must join the profile so the guard cannot
    fire on the goal's own target item."""
    gd = GameData()
    gd._crafting_recipes = {"wooden_shield": {"ash_plank": 6},
                            "ash_plank": {"ash_wood": 10}}
    # 51/60 used = 0.85 (at DISCARD_HIGH_FRACTION and the overstock watermark);
    # 1 shield equipped → equipped-code cap 1 < held 2 → 1 shield is overstock.
    # ash_wood cap = max_recipe_demand(10) x BATCH_BUFFER(5) = 50 ≥ held 49.
    state = make_state(
        hp=100, max_hp=100,
        inventory={"wooden_shield": 2, "ash_wood": 49},
        inventory_max=60,
        equipment={"shield_slot": "wooden_shield"},
        bank_items={},
    )
    assert GuardKind.DISCARD_HIGH in active_guards(state, gd, None, _ctx())
    guards = active_guards(state, gd, None, _ctx(),
                           step_profile={"wooden_shield": 3})
    assert GuardKind.DISCARD_HIGH not in guards


def test_deposit_full_quiet_when_bank_full():
    """DEPOSIT_FULL must not fire when the bank cannot accept items (full)."""
    gd = GameData()
    gd._bank_capacity = 2
    # bank used 2 == capacity 2 → no room
    state = make_state(inventory={"junk": 100}, inventory_max=100,
                       bank_items={"x": 1, "y": 1})
    ctx = _ctx()  # bank_accessible=True
    assert _fires(GuardKind.DEPOSIT_FULL, state, gd, None, ctx) is False


def test_deposit_full_fires_when_bank_has_room():
    """DEPOSIT_FULL fires when bank has room, inventory is full, and there is a
    depositable item."""
    gd = GameData()
    gd._bank_capacity = 50
    state = make_state(inventory={"junk": 100}, inventory_max=100,
                       bank_items={"x": 1})
    ctx = _ctx()
    assert _fires(GuardKind.DEPOSIT_FULL, state, gd, None, ctx) is True


def test_discard_quiet_when_bank_has_room():
    """With bank room, overstock is deposited, not discarded — both DISCARD
    guards must be silent even when overstock is present."""
    gd = GameData()
    gd._bank_capacity = 50
    # inventory={"junk": 100}, inventory_max=100 → 100% fill, junk is overstock
    # (empty catalog → cap 0, any quantity is overstock under pressure).
    # bank has room: 1 item < capacity 50.
    state = make_state(inventory={"junk": 100}, inventory_max=100,
                       bank_items={"x": 1})
    ctx = _ctx()  # bank_accessible=True
    assert _fires(GuardKind.DISCARD_CRITICAL, state, gd, None, ctx) is False
    assert _fires(GuardKind.DISCARD_HIGH, state, gd, None, ctx) is False


def test_discard_fires_when_bank_full():
    """Both discard guards fire when overstock is present AND the bank is full."""
    gd = GameData()
    gd._bank_capacity = 1
    # bank has 1 item at capacity 1 → bank is full (no room).
    state = make_state(inventory={"junk": 100}, inventory_max=100,
                       bank_items={"x": 1})
    ctx = _ctx()  # bank_accessible=True
    # Overstock present + bank full → discard guard fires (worthless filtering
    # happens in the goal, not the fire predicate).
    assert _fires(GuardKind.DISCARD_HIGH, state, gd, None, ctx) is True
    assert _fires(GuardKind.DISCARD_CRITICAL, state, gd, None, ctx) is True


def _recycle_gd() -> GameData:
    """GameData with a craftable equippable gear item and a known workshop."""
    gd = GameData()
    gd._item_stats = {
        "copper_helmet": ItemStats(
            code="copper_helmet", level=1, type_="helmet",
            crafting_skill="gearcrafting", crafting_level=1,
        ),
    }
    gd._crafting_recipes = {"copper_helmet": {"copper_bar": 6}}
    gd._workshop_locations = {"gearcrafting": (2, 1)}
    gd._bank_capacity = 1  # bank is full (1 item = capacity 1)
    return gd


def test_recycle_relief_fires_when_bank_full_with_surplus():
    """Recyclable surplus + bank full + bag pressure -> RECYCLE_RELIEF fires."""
    gd = _recycle_gd()
    # bank_items has 1 item and capacity is 1 → bank full
    state = make_state(
        level=5, skills={"gearcrafting": 1},
        inventory={"copper_helmet": 9},
        inventory_max=200,
        bank_items={"some_item": 1},
    )
    ctx = _ctx(bank_accessible=True)
    assert _fires(GuardKind.RECYCLE_RELIEF, state, gd, None, ctx) is True


def test_recycle_relief_quiet_when_bank_has_room():
    """Same surplus but bank has room -> deposit path applies, RECYCLE_RELIEF quiet."""
    gd = _recycle_gd()
    gd._bank_capacity = 50  # bank has room
    state = make_state(
        level=5, skills={"gearcrafting": 1},
        inventory={"copper_helmet": 9},
        inventory_max=200,
        bank_items={"some_item": 1},
    )
    ctx = _ctx(bank_accessible=True)
    assert _fires(GuardKind.RECYCLE_RELIEF, state, gd, None, ctx) is False


def test_recycle_relief_quiet_when_no_surplus():
    """Bank full but no surplus → RECYCLE_RELIEF quiet."""
    gd = _recycle_gd()
    state = make_state(
        level=5, skills={"gearcrafting": 1},
        inventory={"copper_helmet": 1},  # at cap (1), no surplus
        inventory_max=200,
        bank_items={"some_item": 1},
    )
    ctx = _ctx(bank_accessible=True)
    assert _fires(GuardKind.RECYCLE_RELIEF, state, gd, None, ctx) is False


def test_recycle_relief_quiet_when_surplus_is_protected():
    """Bank full, surplus exists but it is the committed objective gear → quiet."""
    gd = _recycle_gd()
    state = make_state(
        level=5, skills={"gearcrafting": 1},
        inventory={"copper_helmet": 9},
        inventory_max=200,
        bank_items={"some_item": 1},
    )
    ctx = _ctx(bank_accessible=True,
               target_gear=frozenset({"copper_helmet"}))
    assert _fires(GuardKind.RECYCLE_RELIEF, state, gd, None, ctx) is False


def _sell_gd() -> GameData:
    """GameData with one NPC buyer for 'copper_ore' (tradeable item)."""
    gd = GameData()
    gd._npc_sell_prices = {"npc_buyer": {"copper_ore": 5}}
    gd._item_stats = {
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource",
                                tradeable=True),
    }
    gd._bank_capacity = 1  # bank is full (1 item = capacity 1)
    return gd


def test_sell_relief_fires_when_bank_full_with_sellable():
    """Bank full + sellable item in inventory -> SELL_RELIEF fires."""
    gd = _sell_gd()
    state = make_state(
        inventory={"copper_ore": 5},
        inventory_max=20,
        bank_items={"some_item": 1},
    )
    ctx = _ctx(bank_accessible=True)
    assert _fires(GuardKind.SELL_RELIEF, state, gd, None, ctx) is True


def test_sell_relief_quiet_when_bank_has_room():
    """Bank has room -> SELL_RELIEF quiet even with sellable items."""
    gd = _sell_gd()
    gd._bank_capacity = 50  # bank has room
    state = make_state(
        inventory={"copper_ore": 5},
        inventory_max=20,
        bank_items={"some_item": 1},
    )
    ctx = _ctx(bank_accessible=True)
    assert _fires(GuardKind.SELL_RELIEF, state, gd, None, ctx) is False


def test_sell_relief_quiet_when_no_sellable():
    """Bank full but no NPC buyer for held items -> SELL_RELIEF quiet."""
    gd = _sell_gd()
    state = make_state(
        inventory={"unsellable_item": 5},
        inventory_max=20,
        bank_items={"some_item": 1},
    )
    ctx = _ctx(bank_accessible=True)
    assert _fires(GuardKind.SELL_RELIEF, state, gd, None, ctx) is False


def test_sell_relief_quiet_when_item_zero_qty():
    """Inventory entry with qty=0 is skipped (no real holding)."""
    gd = _sell_gd()
    state = make_state(
        inventory={"copper_ore": 0},  # held qty is zero
        inventory_max=20,
        bank_items={"some_item": 1},
    )
    ctx = _ctx(bank_accessible=True)
    assert _fires(GuardKind.SELL_RELIEF, state, gd, None, ctx) is False


def test_sell_relief_quiet_when_item_not_tradeable():
    """Bank full + NPC buyer exists but item is not tradeable -> quiet."""
    gd = GameData()
    gd._npc_sell_prices = {"npc_buyer": {"bound_item": 5}}
    gd._item_stats = {
        "bound_item": ItemStats(code="bound_item", level=1, type_="resource",
                                tradeable=False),
    }
    gd._bank_capacity = 1
    state = make_state(
        inventory={"bound_item": 3},
        inventory_max=20,
        bank_items={"some_item": 1},
    )
    ctx = _ctx(bank_accessible=True)
    assert _fires(GuardKind.SELL_RELIEF, state, gd, None, ctx) is False


# ---------------------------------------------------------------------------
# Bank-full cascade ordering: craft > recycle > sell > discard
# ---------------------------------------------------------------------------

def _bank_full_ctx() -> SelectionContext:
    """Context for the bank-full cascade: bank accessible, no active combat."""
    return _ctx(bank_accessible=True)


def _cascade_gd_base() -> GameData:
    """Minimal GameData shared across all cascade sub-cases.

    Bank full: capacity=1, one item already stored.
    No NPC buyers, no recycle-eligible gear, no recipes by default — each
    sub-case adds only what it needs to light up its guard."""
    gd = GameData()
    gd._bank_capacity = 1  # 1 item == capacity → no room
    return gd


def _state_with_craft() -> tuple[GameData, "WorldState"]:
    """CRAFT_RELIEF sub-case: bank full, inventory at 75%, ash_wood craftable
    into ash_plank (10:1 recipe → net 9 units freed per craft).

    Active task = ash_plank(3). At 75 ash_wood / inventory_max=100 the
    CRAFT_RELIEF fraction (0.70) is met; DISCARD thresholds (0.85/0.95) are
    NOT met, so DISCARD_CRITICAL stays quiet and CRAFT_RELIEF is first."""
    gd = _cascade_gd_base()
    gd._crafting_recipes = {"ash_plank": {"ash_wood": 10}}
    gd._item_stats = {
        "ash_plank": ItemStats(
            code="ash_plank", level=1, type_="resource",
            crafting_skill="woodcutting", crafting_level=1,
        ),
    }
    state = make_state(
        skills={"woodcutting": 5},
        inventory={"ash_wood": 75},
        inventory_max=100,
        bank_items={"x": 1},
        task_code="ash_plank",
        task_type="items",
        task_total=3,
        task_progress=0,
    )
    return gd, state


def _state_with_recycle_no_craft() -> tuple[GameData, "WorldState"]:
    """RECYCLE_RELIEF sub-case: bank full, inventory at 75%,
    surplus copper_helmet present (held 9, cap 1), but NO craftable task item
    so CRAFT_RELIEF stays quiet."""
    gd = _cascade_gd_base()
    gd._item_stats = {
        "copper_helmet": ItemStats(
            code="copper_helmet", level=1, type_="helmet",
            crafting_skill="gearcrafting", crafting_level=1,
        ),
    }
    gd._crafting_recipes = {"copper_helmet": {"copper_bar": 6}}
    gd._workshop_locations = {"gearcrafting": (2, 1)}
    state = make_state(
        level=5, skills={"gearcrafting": 5},
        inventory={"copper_helmet": 9},  # surplus above cap-1; 75 < 85 → no discard
        inventory_max=12,
        bank_items={"x": 1},
    )
    return gd, state


def _state_with_sell_no_craft_recycle() -> tuple[GameData, "WorldState"]:
    """SELL_RELIEF sub-case: bank full, inventory at 75%, sellable copper_ore
    present (NPC buyer + tradeable=True), no craft or recycle candidate."""
    gd = _cascade_gd_base()
    gd._npc_sell_prices = {"npc_buyer": {"copper_ore": 5}}
    gd._item_stats = {
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource",
                                tradeable=True),
    }
    state = make_state(
        inventory={"copper_ore": 75},
        inventory_max=100,
        bank_items={"x": 1},
    )
    return gd, state


def _state_with_discard_only() -> tuple[GameData, "WorldState"]:
    """DISCARD_HIGH sub-case: bank full, inventory at 90%,
    only a worthless junk item present — no craft/recycle/sell candidate.
    90% ≥ DISCARD_HIGH_FRACTION (0.85) so DISCARD_HIGH fires.
    DISCARD_CRITICAL requires 0.95 so it is also checked."""
    gd = _cascade_gd_base()
    # "junk" has no recipe, no NPC buyer, no stats → pure overstock
    state = make_state(
        inventory={"junk": 90},
        inventory_max=100,
        bank_items={"x": 1},
    )
    return gd, state


def _state_bank_has_room() -> tuple[GameData, "WorldState"]:
    """Bank-has-room case: bag at 92%, depositable junk present, bank has room.
    DEPOSIT_FULL should fire; RECYCLE/SELL/DISCARD must NOT fire."""
    gd = _cascade_gd_base()
    gd._bank_capacity = 50  # override: plenty of room
    state = make_state(
        inventory={"junk": 92},
        inventory_max=100,
        bank_items={"x": 1},
    )
    return gd, state


def test_bank_full_cascade_order():
    """End-to-end ordering: active_guards returns guards in GUARD_ORDER ladder
    order. Across bank-full sub-cases the cascade priority is:
      CRAFT_RELIEF > RECYCLE_RELIEF > SELL_RELIEF > DISCARD_HIGH
    and DEPOSIT_FULL never appears while bank has no room."""
    ctx = _bank_full_ctx()

    # Sub-case 1: craft candidate present → CRAFT_RELIEF is the first guard.
    gd, state = _state_with_craft()
    fired = active_guards(state, gd, None, ctx)
    assert fired, "expected at least one guard"
    assert fired[0] is GuardKind.CRAFT_RELIEF, f"expected CRAFT_RELIEF first, got {fired}"
    assert GuardKind.DEPOSIT_FULL not in fired, "DEPOSIT_FULL must not fire when bank is full"

    # Sub-case 2: no craft candidate, recyclable surplus → RECYCLE_RELIEF first.
    gd, state = _state_with_recycle_no_craft()
    fired = active_guards(state, gd, None, ctx)
    assert fired, "expected at least one guard"
    assert fired[0] is GuardKind.RECYCLE_RELIEF, f"expected RECYCLE_RELIEF first, got {fired}"
    assert GuardKind.DEPOSIT_FULL not in fired, "DEPOSIT_FULL must not fire when bank is full"

    # Sub-case 3: no craft/recycle, sellable item → SELL_RELIEF first.
    gd, state = _state_with_sell_no_craft_recycle()
    fired = active_guards(state, gd, None, ctx)
    assert fired, "expected at least one guard"
    assert fired[0] is GuardKind.SELL_RELIEF, f"expected SELL_RELIEF first, got {fired}"
    assert GuardKind.DEPOSIT_FULL not in fired, "DEPOSIT_FULL must not fire when bank is full"

    # Sub-case 4: only worthless overstock → DISCARD_HIGH fires (at 90% ≥ 0.85).
    gd, state = _state_with_discard_only()
    fired = active_guards(state, gd, None, ctx)
    assert GuardKind.DISCARD_HIGH in fired or GuardKind.DISCARD_CRITICAL in fired, (
        f"expected DISCARD_HIGH or DISCARD_CRITICAL in {fired}"
    )
    assert GuardKind.DEPOSIT_FULL not in fired, "DEPOSIT_FULL must not fire when bank is full"

    # Sub-case 5: bank has room → DEPOSIT_FULL fires; relief/discard guards silent.
    gd, state = _state_bank_has_room()
    fired = active_guards(state, gd, None, ctx)
    assert GuardKind.DEPOSIT_FULL in fired, f"expected DEPOSIT_FULL in {fired}"
    assert GuardKind.RECYCLE_RELIEF not in fired, "RECYCLE_RELIEF must not fire with room"
    assert GuardKind.SELL_RELIEF not in fired, "SELL_RELIEF must not fire with room"
    assert GuardKind.DISCARD_HIGH not in fired, "DISCARD_HIGH must not fire with room"
    assert GuardKind.DISCARD_CRITICAL not in fired, "DISCARD_CRITICAL must not fire with room"
