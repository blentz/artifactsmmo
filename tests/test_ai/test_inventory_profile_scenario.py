"""Scenario regression for the GatherMaterials(fishing_net) livelock.

Live trace (Robby cyc 20-38): GatherMaterials(fishing_net) withdrew ash_wood
repeatedly while DepositInventory->DepositAll dumped it every ~6 cycles — zero
progress for 18+ cycles. Root cause: the bank keep-set protected task_code +
crafting_target but NOT the active gather goal's materials, and deposit/discard
were space-blind (fired at 50% used / per-item cap).

This test pins the fix (spec 2026-06-07): with ash_wood in the active goal's
profile + free slots, ash_wood is NEVER deposited or discarded, held accumulates
toward the target, and there is no withdraw<->deposit oscillation.

Pre-fix this FAILS:
  * select_bank_deposits had no profile_codes param -> ash_wood (not the
    crafting_target/task chain) was banked.
  * DepositInventoryGoal._RAMP_START=0.5 -> deposit fired at 50% used.
  * overstocked_items was space-blind -> ash_wood over its per-item cap was
    discard-eligible regardless of free slots.
"""

from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.deposit_inventory import DepositInventoryGoal
from artifactsmmo_cli.ai.goals.discard_overstock import DiscardOverstockGoal
from artifactsmmo_cli.ai.inventory_caps import overstocked_items
from artifactsmmo_cli.ai.inventory_profile import inventory_profile
from artifactsmmo_cli.ai.tiers.guards import (
    GuardKind,
    SelectionContext,
    active_guards,
)
from tests.test_ai.fixtures import make_state


def _fishing_net_gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "fishing_net": ItemStats(code="fishing_net", level=1, type_="utility"),
        "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    # fishing_net needs 10 ash_wood; ash_wood is NOT in the copper task chain.
    gd._crafting_recipes = {"fishing_net": {"ash_wood": 10}}
    # ash_wood has an NPC buy-back so it would be a deposit/sell candidate.
    gd._npc_sell_prices = {"merchant": {"ash_wood": 2}}
    gd._npc_locations = {"merchant": (1, 1)}
    return gd


def _ctx() -> SelectionContext:
    # fishing_net is a target TOOL of the long-term objective.
    return SelectionContext(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=6, combat_monster=None,
        target_tools=frozenset({"fishing_net"}),
    )


def test_ash_wood_in_profile_for_target_tool():
    gd = _fishing_net_gd()
    state = make_state(inventory={"ash_wood": 8}, inventory_max=20,
                       task_code="copper_ore", task_type="items",
                       task_total=20, task_progress=5)
    # Task 5 migration (spec 2026-06-28-gear-loadout-profiles): gear/tool roots
    # are the active-profile gear set passed via `gear_codes` (replaces the
    # `target_gear`/`target_tools` kwargs); closure behavior is unchanged.
    profile = inventory_profile(state, gd, gear_codes=frozenset({"fishing_net"}))
    assert profile.get("ash_wood", 0) == 10  # fishing_net needs 10


def test_ash_wood_not_deposited_when_in_profile():
    """The livelock's deposit side: ash_wood (active tool material, NOT the
    task chain) must NOT be banked once it joins the keep-set via the profile.
    Pre-fix select_bank_deposits had no profile awareness and banked it."""
    gd = _fishing_net_gd()
    state = make_state(inventory={"ash_wood": 8}, inventory_max=20,
                       task_code="copper_ore", task_type="items",
                       task_total=20, task_progress=5)
    profile_codes = frozenset(inventory_profile(
        state, gd, gear_codes=frozenset({"fishing_net"})))
    deposits = select_bank_deposits(state, gd, profile_codes)
    codes = {c for c, _ in deposits}
    assert "ash_wood" not in codes, (
        "ash_wood is an active-profile material; depositing it undoes the "
        "withdraw and livelocks the gather"
    )

    # And the deposit GUARD does not fire on ash_wood alone with free slots
    # (8/20 = 40% used, well below the 0.85 watermark).
    guards = active_guards(state, gd, None, _ctx())
    assert GuardKind.DEPOSIT_FULL not in guards


def test_ash_wood_not_discarded_with_free_slots():
    """The livelock's discard side: with free slots ash_wood is never overstock,
    and even under pressure it is protected up to its profile target."""
    gd = _fishing_net_gd()
    profile = inventory_profile(make_state(), gd,
                                gear_codes=frozenset({"fishing_net"}))
    # Free slots: 8 ash_wood in a 20-slot bag -> nothing overstock.
    state = make_state(inventory={"ash_wood": 8}, inventory_max=20)
    assert overstocked_items(state, gd, profile=profile) == {}

    # Even near-full, ash_wood up to its profile target (10) is protected.
    full = make_state(inventory={"ash_wood": 10, "junk": 9}, inventory_max=20)
    over = overstocked_items(full, gd, profile=profile)
    assert "ash_wood" not in over, "ash_wood at/below its target is never overstock"

    goal = DiscardOverstockGoal(game_data=gd, profile=profile)
    relevant = goal.relevant_actions([], full, gd)
    codes = {a.code if hasattr(a, "code") else a.item_code for a in relevant}
    assert "ash_wood" not in codes


def test_deposit_all_action_honors_profile_codes():
    """Run-5 trace 2026-06-11 23:05 (cycle 10): DepositAll banked all ~59
    ash_wood the active wooden_shield grind needed, forcing a 14-cycle
    withdraw round-trip. The goal's profile_codes never reached the ACTION —
    DepositAllAction._deposits called select_bank_deposits without them. The
    action must honor the same keep-set the goal used to plan."""
    gd = _fishing_net_gd()
    state = make_state(inventory={"ash_wood": 8, "junk": 9}, inventory_max=20)
    unprotected = DepositAllAction(bank_location=(4, 0), game_data=gd)
    assert "ash_wood" in {c for c, _ in unprotected._deposits(state)}
    protected = DepositAllAction(bank_location=(4, 0), game_data=gd,
                                 profile_codes=frozenset({"ash_wood"}))
    codes = {c for c, _ in protected._deposits(state)}
    assert "ash_wood" not in codes
    assert "junk" in codes


def test_deposit_goal_injects_profile_into_action():
    """DepositInventoryGoal must hand its profile_codes to the deposit actions
    it offers the planner — otherwise the goal plans with the keep-set but the
    executed DepositAll ignores it (run-5 cycle-10 incoherence)."""
    gd = _fishing_net_gd()
    state = make_state(inventory={"ash_wood": 8, "junk": 9}, inventory_max=20)
    goal = DepositInventoryGoal(game_data=gd,
                                profile_codes=frozenset({"ash_wood"}))
    actions = goal.relevant_actions(
        [DepositAllAction(bank_location=(4, 0), game_data=gd)], state, gd)
    assert actions, "deposit-tagged action must survive the filter"
    for act in actions:
        codes = {c for c, _ in act._deposits(state)}
        assert "ash_wood" not in codes, (
            "the goal's profile_codes must reach the executed action"
        )


def test_ash_wood_accumulates_no_oscillation():
    """End-to-end: across the withdraw/accumulate cycles ash_wood held only
    grows toward the target; deposit/discard never strip it. Simulate held
    rising 8 -> 9 -> 10 with the profile in place; at each step neither
    deposit nor discard targets ash_wood."""
    gd = _fishing_net_gd()
    profile = inventory_profile(make_state(), gd,
                                gear_codes=frozenset({"fishing_net"}))
    profile_codes = frozenset(profile)
    deposit_goal = DepositInventoryGoal(game_data=gd, profile_codes=profile_codes)
    discard_goal = DiscardOverstockGoal(game_data=gd, profile=profile)
    for held in (8, 9, 10):
        state = make_state(inventory={"ash_wood": held}, inventory_max=20)
        deposits = select_bank_deposits(state, gd, profile_codes)
        assert "ash_wood" not in {c for c, _ in deposits}
        # Deposit goal sees nothing to bank (ash_wood is the only item) -> satisfied.
        assert deposit_goal.is_satisfied(state) is True
        assert overstocked_items(state, gd, profile=profile).get("ash_wood", 0) == 0
        assert discard_goal.is_satisfied(state) is True
