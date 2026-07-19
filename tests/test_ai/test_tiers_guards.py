"""Tests for the guard ladder (state-pressure interrupts + prerequisite gates)."""

from unittest.mock import patch

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.thresholds import DEPOSIT_FULL_FRACTION
from artifactsmmo_cli.ai.tiers.guards import (
    GUARD_ORDER,
    GuardKind,
    SelectionContext,
    _fires,
    _quantity_fraction,
    _used_fraction,
    active_guards,
)
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
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


def test_space_pressure_is_slot_aware_but_delete_stays_quantity_only():
    """The SPACE-pressure metric (drives DEPOSIT_FULL / CRAFT_RELIEF) counts SLOT
    fullness, so it crosses the deposit threshold at 20/20 slots even when
    quantity is low — the live Robby 2026-07-10 loop (76/124 quantity but 20/20
    SLOTS, doomed Craft(iron_bar) 497'd every cycle because a quantity-only metric
    never fired the relief guards). The DELETE metric stays QUANTITY-only, so slot
    pressure alone never deletes an item that banking would have saved (regression
    caught 2026-07-11: DISCARD_CRITICAL deleting golden_egg ahead of DEPOSIT_FULL).
    End-to-end firing is covered by the slot_exhaustion scenario + live plan."""
    inv: dict[str, int] = {"ore": 40, "wood": 20}
    for i in range(18):
        inv[f"j{i}"] = 1
    state = make_state(inventory=inv, inventory_max=124, inventory_slots_max=20)
    assert state.inventory_slots_free == 0            # slot-full
    assert _used_fraction(state) == 1.0               # space pressure is slot-driven
    assert _used_fraction(state) >= DEPOSIT_FULL_FRACTION  # crosses the deposit gate
    assert _quantity_fraction(state) < 0.85           # delete metric stays low → no delete


def test_space_pressure_uses_quantity_when_slots_have_headroom():
    """With slot headroom the space metric falls back to quantity pressure (both
    metrics agree), so the deposit/craft-relief guards are unchanged for a bag
    that is quantity-full but not slot-full."""
    state = make_state(inventory={"ore": 90}, inventory_max=100, inventory_slots_max=20)
    assert state.inventory_slots_free > 0
    assert _used_fraction(state) == _quantity_fraction(state) == 0.9


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
    fill_monster_stat_defaults(gd)  # craft_potions_fires → unlock_boost_target → predict_win needs full stats
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
    # GEAR_REVIEW is below all survival guards and above CRAFT_POTIONS.
    assert GuardKind.HP_CRITICAL in GUARD_ORDER[:GUARD_ORDER.index(GuardKind.GEAR_REVIEW)]
    assert GUARD_ORDER.index(GuardKind.GEAR_REVIEW) < GUARD_ORDER.index(GuardKind.CRAFT_POTIONS)


def test_craft_potions_is_last_guard():
    # CRAFT_POTIONS is the LAST (lowest-priority) guard — still preempts all means.
    assert GUARD_ORDER[-1] is GuardKind.CRAFT_POTIONS


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


def test_discard_fires_on_overstock_even_with_bank_room():
    """2026-06-24: genuine overstock (above the need/value cap) is shed REGARDLESS
    of bank room — banking far-future junk just hoards it and, when the bag is
    full, lets the deposit thrash on the active craft input. Both DISCARD guards
    fire on overstock at their watermark even when the bank has free slots."""
    gd = GameData()
    gd._bank_capacity = 50
    # inventory={"junk": 100}, inventory_max=100 → 100% fill, junk is overstock
    # (empty catalog → cap 0, any quantity is overstock under pressure).
    # bank has room: 1 item < capacity 50 — discard no longer waits for bank-full.
    state = make_state(inventory={"junk": 100}, inventory_max=100,
                       bank_items={"x": 1})
    ctx = _ctx()  # bank_accessible=True
    assert _fires(GuardKind.DISCARD_CRITICAL, state, gd, None, ctx) is True
    assert _fires(GuardKind.DISCARD_HIGH, state, gd, None, ctx) is True


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


def test_recycle_relief_quiet_when_the_keep_authority_licenses_nothing():
    """Bank full, 9 helmets held — but the active gear profile DEMANDS all 9
    (KeepReason.GEAR_DEMAND), so nothing is destroyable → quiet.

    The protection is a QUANTITY, not a code-set: a `target_gear` membership no
    longer shields the code (that blanket hid 18 copper_axe from every recycle
    path). Raise the held count above the demand and the guard fires."""
    gd = _recycle_gd()
    state = make_state(
        level=5, skills={"gearcrafting": 1},
        inventory={"copper_helmet": 9},
        inventory_max=200,
        bank_items={"some_item": 1},
    )
    ctx = _ctx(bank_accessible=True, gear_keep={"copper_helmet": 9})
    assert _fires(GuardKind.RECYCLE_RELIEF, state, gd, None, ctx) is False
    # A BiS pursuit target is not a hoard licence: the same 9 helmets with only
    # the legacy code-set "protection" ARE recyclable surplus (keep 1).
    bis = _ctx(bank_accessible=True, target_gear=frozenset({"copper_helmet"}))
    assert _fires(GuardKind.RECYCLE_RELIEF, state, gd, None, bis) is True


def _sell_gd() -> GameData:
    """GameData with one reachable NPC buyer for 'copper_ore' (tradeable item)."""
    gd = GameData()
    gd._npc_sell_prices = {"npc_buyer": {"copper_ore": 5}}
    gd._npc_locations = {"npc_buyer": (1, 2)}  # reachable now
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


def test_sell_relief_quiet_when_only_buyer_is_dormant_event_merchant():
    """Bank full + the ONLY NPC buyer has npc_location()==None (dormant event
    merchant, spawn window closed) -> SELL_RELIEF must NOT fire.

    Pre-branch behaviour: SELL_RELIEF fired because _has_sellable only checked
    npcs_buying_item (price table), not reachability.  NpcSellAction.is_applicable
    then rejected the unreachable NPC → empty plan → permanent livelock.
    The fix: _has_sellable requires at least one buyer with a non-None location."""
    gd = GameData()
    # NPC is in the price table but has NO entry in _npc_locations → npc_location returns None.
    gd._npc_sell_prices = {"event_merchant": {"festival_token": 10}}
    gd._item_stats = {
        "festival_token": ItemStats(code="festival_token", level=1, type_="resource",
                                    tradeable=True),
    }
    gd._bank_capacity = 1  # bank full
    state = make_state(
        inventory={"festival_token": 5},
        inventory_max=20,
        bank_items={"some_item": 1},
    )
    ctx = _ctx(bank_accessible=True)
    assert _fires(GuardKind.SELL_RELIEF, state, gd, None, ctx) is False


def test_sell_relief_fires_when_buyer_has_reachable_location():
    """Sanity: bank full + buyer IS reachable (npc_location returns a tile)
    -> SELL_RELIEF fires (reachable-buyer path)."""
    gd = GameData()
    gd._npc_sell_prices = {"merchant": {"festival_token": 10}}
    gd._item_stats = {
        "festival_token": ItemStats(code="festival_token", level=1, type_="resource",
                                    tradeable=True),
    }
    gd._npc_locations = {"merchant": (3, 4)}
    gd._bank_capacity = 1  # bank full
    state = make_state(
        inventory={"festival_token": 5},
        inventory_max=20,
        bank_items={"some_item": 1},
    )
    ctx = _ctx(bank_accessible=True)
    assert _fires(GuardKind.SELL_RELIEF, state, gd, None, ctx) is True


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

    Active task = ash_plank(3), so the batch is capped at 3 crafts — and 30
    ash_wood is exactly what those 3 crafts consume, which makes the craft
    SLOT-HONEST (the ash_wood stack is cleared and the plank takes its slot;
    a remainder would ADD a stack and would not be relief at all). The 45 junk
    units carry the pressure: at 75/100 the CRAFT_RELIEF fraction (0.70) is
    met while the DISCARD thresholds (0.85/0.95) are NOT, so DISCARD_CRITICAL
    stays quiet and CRAFT_RELIEF is first."""
    gd = _cascade_gd_base()
    gd._crafting_recipes = {"ash_plank": {"ash_wood": 10}}
    gd._item_stats = {
        "ash_plank": ItemStats(
            code="ash_plank", level=1, type_="resource",
            crafting_skill="woodcutting", crafting_level=1,
        ),
    }
    state = make_state(
        hp=150, max_hp=150,
        skills={"woodcutting": 5},
        inventory={"ash_wood": 30, "junk": 45},
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
        hp=150, max_hp=150,
        level=5, skills={"gearcrafting": 5},
        inventory={"copper_helmet": 9},  # surplus above cap-1; 75 < 85 → no discard
        inventory_max=12,
        bank_items={"x": 1},
    )
    return gd, state


def _state_with_sell_no_craft_recycle() -> tuple[GameData, "WorldState"]:
    """SELL_RELIEF sub-case: bank full, inventory at 75%, sellable copper_ore
    present (NPC buyer reachable + tradeable=True), no craft or recycle candidate."""
    gd = _cascade_gd_base()
    gd._npc_sell_prices = {"npc_buyer": {"copper_ore": 5}}
    gd._npc_locations = {"npc_buyer": (1, 2)}  # reachable now
    gd._item_stats = {
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource",
                                tradeable=True),
    }
    state = make_state(
        hp=150, max_hp=150,
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
        hp=150, max_hp=150,
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

    # Sub-case 5: bank has room → DEPOSIT_FULL fires (the retrievable buffer) and
    # precedes any DISCARD_HIGH; the bank-full-only relief guards stay silent.
    # 2026-06-24: DISCARD_HIGH may now ALSO fire on overstock with bank room
    # (junk is shed, not hoarded) — but it ranks BELOW DEPOSIT_FULL, so the buffer
    # deposits first and only the residual junk overstock discards.
    gd, state = _state_bank_has_room()
    fired = active_guards(state, gd, None, ctx)
    assert GuardKind.DEPOSIT_FULL in fired, f"expected DEPOSIT_FULL in {fired}"
    assert GuardKind.RECYCLE_RELIEF not in fired, "RECYCLE_RELIEF must not fire with room"
    assert GuardKind.SELL_RELIEF not in fired, "SELL_RELIEF must not fire with room"
    if GuardKind.DISCARD_HIGH in fired:
        assert fired.index(GuardKind.DEPOSIT_FULL) < fired.index(GuardKind.DISCARD_HIGH), (
            f"DEPOSIT_FULL (buffer) must precede DISCARD_HIGH, got {fired}")
    assert GuardKind.DISCARD_CRITICAL not in fired, "DISCARD_CRITICAL must not fire with room"


# ---------------------------------------------------------------------------
# CRAFT_POTIONS guard
# ---------------------------------------------------------------------------

def _potion_gd() -> GameData:
    """GameData with one alchemy-craftable utility potion (ingredient gatherable)."""
    gd = GameData()
    gd._item_stats = {
        "health_potion": ItemStats(code="health_potion", level=1, type_="utility",
                                   hp_restore=50, crafting_skill="alchemy", crafting_level=1),
        "red_slimeball": ItemStats(code="red_slimeball", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"health_potion": {"red_slimeball": 2}}
    gd._resource_drops = {"red_slime": "red_slimeball"}  # ingredient is gatherable
    # Combat pressure. Potion stocking is combat-justified (2026-07-19): the target
    # is projected IN-COMBAT consumption, so a catalog with no winnable monster
    # projects zero need and the guard correctly stays silent. This monster is
    # winnable but leaves the character at/below the marginal-fight HP fraction,
    # which is what makes stocking the right call rather than resting it off.
    gd._monster_level = {"red_slime": 3}
    gd._monster_hp = {"red_slime": 60}
    gd._monster_attack = {"red_slime": {"fire": 40}}
    gd._monster_resistance = {"red_slime": {}}
    gd._monster_locations = {"red_slime": [(1, 0)]}
    fill_monster_stat_defaults(gd)
    return gd


def _understocked_producible(level: int = 3, equipped: int = 0):
    """Level 3: baseline = POTION_LOW_QTY = 5; equipped=0 < 5; potion gatherable."""
    state = make_state(level=level, skills={"alchemy": 1},
                       utility1_slot_quantity=equipped, attack={"fire": 20})
    return state, _potion_gd(), _ctx()


def _understocked_but_no_alchemy(level: int = 3, equipped: int = 0):
    """Level 3, understocked, but no alchemy-craftable utility potion exists."""
    gd = GameData()  # empty catalog — no potions
    state = make_state(level=level, skills={"alchemy": 1},
                       utility1_slot_quantity=equipped)
    return state, gd, _ctx()


def _stocked_to_baseline(level: int = 3, equipped: int = 5):
    """Level 3: baseline=5; equipped=5 == baseline → guard quiet."""
    eq = {
        "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
        "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
        "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
        "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
        "utility1_slot": "health_potion", "utility2_slot": None,
        "bag_slot": None, "rune_slot": None,
    }
    state = make_state(level=level, skills={"alchemy": 1},
                       equipment=eq, utility1_slot_quantity=equipped)
    return state, _potion_gd(), _ctx()


def test_craft_potions_guard_fires_when_understocked_and_producible():
    """Understocked (equipped=0 < baseline=5) and potion gatherable → fires."""
    state, gd, ctx = _understocked_producible(level=3, equipped=0)
    assert _fires(GuardKind.CRAFT_POTIONS, state, gd, None, ctx, None) is True


def test_craft_potions_guard_quiet_when_not_producible():
    """Understocked but no alchemy-craftable utility potion in catalog → quiet."""
    state, gd, ctx = _understocked_but_no_alchemy(level=3, equipped=0)
    assert _fires(GuardKind.CRAFT_POTIONS, state, gd, None, ctx, None) is False


def test_craft_potions_guard_quiet_when_stocked_to_level_baseline():
    """equipped == baseline(3) = 5 → guard quiet even though potion exists."""
    state, gd, ctx = _stocked_to_baseline(level=3, equipped=5)
    assert _fires(GuardKind.CRAFT_POTIONS, state, gd, None, ctx, None) is False


def test_craft_potions_guard_fires_when_ingredients_held():
    """Understocked with all ingredients already in inventory → craft-from-held
    producibility fires (potion_supply.py:74)."""
    state = make_state(level=3, skills={"alchemy": 1}, utility1_slot_quantity=0,
                       inventory={"red_slimeball": 2}, attack={"fire": 20})
    assert _fires(GuardKind.CRAFT_POTIONS, state, _potion_gd(), None, _ctx(), None) is True


def test_craft_potions_guard_fires_when_ingredients_buyable_for_gold():
    """Understocked, none held, but every ingredient is NPC-buyable for gold →
    buy-mix producibility fires (potion_supply.py:80)."""
    gd = _potion_gd()
    gd._resource_drops = {}  # not gatherable — force the buyable path
    gd._npc_stock = {"alchemist": {"red_slimeball": 3}}  # gold currency by default
    state = make_state(level=3, skills={"alchemy": 1}, utility1_slot_quantity=0,
                       inventory={}, attack={"fire": 20})
    assert _fires(GuardKind.CRAFT_POTIONS, state, gd, None, _ctx(), None) is True


def test_craft_potions_guard_quiet_when_recipe_is_empty():
    """A target utility potion whose crafting recipe is empty has no ingredient
    path → guard stays quiet (potion_supply.py:69)."""
    gd = GameData()
    gd._item_stats = {
        "health_potion": ItemStats(code="health_potion", level=1, type_="utility",
                                   hp_restore=50, crafting_skill="alchemy", crafting_level=1),
    }
    gd._crafting_recipes = {"health_potion": {}}  # selected as target, but no ingredients
    state = make_state(level=3, skills={"alchemy": 1}, utility1_slot_quantity=0)
    assert _fires(GuardKind.CRAFT_POTIONS, state, gd, None, _ctx(), None) is False
