"""Slot-exhaustion livelock regression (spec 2026-07-09-slot-aware-inventory
-room, Task 8): the end-to-end pin for the Robby full-bag livelock.

The bug: at 20/20 inventory SLOTS full but with ample total-QUANTITY headroom
(20 singleton junk stacks in a 124-quantity bag), a pending body-armor upgrade
whose equippable was already held caused the planner to re-emit a doomed
`Equip` every cycle. Equipping the held vest into an OCCUPIED body slot must
return the displaced armor to inventory — but with zero free slots that stack
has nowhere to land, so the server 497s and the bag never drains: a livelock.

The fix (Tasks 4-7): EquipAction.is_applicable now carries the slot-room gate
(inventory_room.has_room over the net displaced stack), so the doomed equip is
no longer applicable and the objective step yields no plan; DepositInventoryGoal
treats zero free slots as maximal pressure and routes a slot-freeing deposit
first. This scenario drives the real offline planner and pins that the FIRST
action is a RELIEF action (deposit/sell/recycle of a junk stack), never the
497-doomed equip.

Deferral-safety: the bag holds genuinely non-keep junk, so
`bank_selection.select_bank_deposits` returns it on the normal path — the
zero-QUANTITY-free last-resort arm (which banks a keep item) is NOT needed and
NOT exercised here (quantity is far from full). This validates that leaving the
last-resort arm gated on quantity-free (not slot-free) is safe: a slot-full bag
with real junk drains through the ordinary deposit selection.
"""

from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.deposit_item import DepositItemAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import (
    ScenarioCharacter,
    load_bundle_game_data,
    scenario_state,
)
from tests.test_ai.scenarios.test_slot_coverage import BUNDLE

RELIEF_ACTIONS = (DepositAllAction, DepositItemAction, NpcSellAction, RecycleAction)

# 19 distinct, non-keep junk resources (+ the 2-stack of adventurer_vest below
# = 20 filled slots). NONE is in the adventurer_vest recipe (wool, cowhide,
# spruce_plank, yellow_slimeball), an HP consumable, a weapon, a tool, or a
# currency, so every one is normally bankable by select_bank_deposits (no
# last-resort keep-item deposit needed — see module docstring).
JUNK_STACKS = {
    "algae": 1, "ash_plank": 1, "ash_wood": 1, "copper_bar": 1, "copper_ore": 1,
    "egg": 1, "feather": 1, "golden_egg": 1, "gudgeon": 1, "raw_chicken": 1,
    "shell": 1, "sunflower": 1, "green_slimeball": 1, "cloth": 1,
    "milk_bucket": 1, "raw_beef": 1, "blue_slimeball": 1, "red_slimeball": 1,
    "hard_leather": 1,
}


def _slot_exhaustion_character() -> ScenarioCharacter:
    """Mirror of the Robby livelock: full SLOTS, quantity headroom, a held
    body-armor upgrade the character cannot equip (occupied slot + zero free
    slots => the displaced armor has nowhere to land), empty bank.

    Two adventurer_vests are held on purpose: equipping one leaves the other
    in inventory, so the vest's stack is NOT freed by the equip while the
    displaced copper_armor still needs a slot — a net new-stack demand of 1
    against zero free slots, exactly the 497 the slot gate now rejects. A held
    single copy would be a slot-neutral swap (executable), which would not
    reproduce the livelock."""
    inventory = {"adventurer_vest": 2, **JUNK_STACKS}
    assert len(inventory) == 20  # 20 distinct stacks -> slots_used == 20
    return ScenarioCharacter(
        name="slot_exhaustion",
        level=12,
        max_hp=260,
        skills={"gearcrafting": 10, "weaponcrafting": 10},
        equipment={
            "weapon_slot": "copper_dagger",
            "body_armor_slot": "copper_armor",  # worse than the held vest
            "helmet_slot": "copper_helmet",
            "leg_armor_slot": "copper_legs_armor",
            "boots_slot": "copper_boots",
            "ring1_slot": "copper_ring",
            "ring2_slot": "copper_ring",
        },
        inventory=inventory,
        inventory_max=124,          # ample QUANTITY headroom (used 21/124)
        inventory_slots_max=20,     # 20/20 SLOTS full -> slots_free == 0
        bank={},                    # empty, accessible bank
        description="20/20 slots full, quantity headroom, held adventurer_vest "
                    "upgrade blocked by the occupied body slot + zero free "
                    "slots — the slot-exhaustion livelock.",
    )


def _report():
    gd = load_bundle_game_data(BUNDLE)
    sc = _slot_exhaustion_character()
    player = GamePlayer(character=sc.name, history=None)
    player.seed_offline(scenario_state(sc, gd), gd)
    return player.plan_from_state()


def test_full_bag_construction_is_slot_exhausted() -> None:
    """Construction sanity: the state really has zero free SLOTS while
    keeping QUANTITY headroom — the exact wedge (slots bind, quantity does
    not) the livelock needs. If either flips, the scenario below is vacuous."""
    gd = load_bundle_game_data(BUNDLE)
    state = scenario_state(_slot_exhaustion_character(), gd)
    assert state.inventory_slots_free == 0        # slots are the binding cap
    assert state.inventory_free > 0               # quantity is NOT the cap
    assert state.inventory.get("adventurer_vest") == 2


def test_held_upgrade_equip_is_slot_gated_off() -> None:
    """The doomed equip is genuinely non-applicable now: equipping the held
    adventurer_vest into the occupied body slot would displace copper_armor
    into a full bag (net one new stack, zero free slots). EquipAction's
    slot-room gate (Task 5) rejects it — so the planner cannot re-emit it."""
    gd = load_bundle_game_data(BUNDLE)
    state = scenario_state(_slot_exhaustion_character(), gd)
    equip = EquipAction(code="adventurer_vest", slot="body_armor_slot")
    assert not equip.is_applicable(state, gd)


def test_full_bag_routes_relief_before_doomed_equip() -> None:
    """20/20 slots, quantity headroom, pending body-armor upgrade: the planner
    must free a slot (deposit/sell junk) before the equip — not re-emit the
    497-doomed equip. Regression pin for the slot-exhaustion livelock."""
    report = _report()
    assert report.plan, (
        "expected a non-empty plan",
        repr(report.selected_goal),
        [g.get("goal") for g in report.goals_tried],
    )
    first = report.plan[0]
    assert not isinstance(first, EquipAction), (repr(first), report.plan)
    assert isinstance(first, RELIEF_ACTIONS), (repr(first), report.plan)
