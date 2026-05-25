"""UpgradeEquipmentGoal must lock planning to the committed target's slot.

Regression: while gathering ash_plank for a wooden_shield (shield_slot), the
goal kept every CraftAction and OptimizeLoadoutAction, and is_satisfied fired on
any equipped-slot change. The planner therefore crafted a fishing_net (weapon
tool, same ash_plank recipe) and equipped it via OptimizeLoadout, consuming the
shield's materials. Lock to the slot: only the target item, target-slot crafts,
and recipe-chain materials survive.
"""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.unequip import UnequipAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield"),
        "fishing_net": ItemStats(code="fishing_net", level=1, type_="weapon"),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),  # material, no slot
    }
    gd._crafting_recipes = {
        "wooden_shield": {"ash_plank": 6},
        "fishing_net": {"ash_plank": 6},
        "ash_plank": {"ash_wood": 1},
    }
    return gd


def _goal() -> UpgradeEquipmentGoal:
    return UpgradeEquipmentGoal(committed_target=("wooden_shield", "shield_slot"))


def test_relevant_actions_locks_to_target_slot():
    gd = _gd()
    goal = _goal()
    state = make_state(inventory={"ash_plank": 6})
    actions = [
        CraftAction(code="wooden_shield", quantity=1),
        CraftAction(code="fishing_net", quantity=1),     # weapon — different slot
        CraftAction(code="ash_plank", quantity=1),       # material — recipe chain
        EquipAction(code="wooden_shield", slot="shield_slot"),
        EquipAction(code="fishing_net", slot="weapon_slot"),
        OptimizeLoadoutAction(target_monster_code="goblin"),
        GatherAction(resource_code="ash_wood", locations=frozenset({(0, 0)})),
        UnequipAction(slot="shield_slot"),
        RestAction(),  # recovery — always kept
    ]
    kept = {repr(a) for a in goal.relevant_actions(actions, state, gd)}
    assert "Craft(wooden_shield×1)" in kept
    assert "Craft(ash_plank×1)" in kept          # material survives the recipe chain
    assert "Equip(wooden_shield->shield_slot)" in kept
    assert any("Rest" in r for r in kept)        # recovery survives
    # Locked out: other-slot equippable craft, other-slot equip, arbitrary loadout, unequip
    assert "Craft(fishing_net×1)" not in kept
    assert "Equip(fishing_net->weapon_slot)" not in kept
    assert not any("OptimizeLoadout" in r for r in kept)
    assert not any("Unequip" in r for r in kept)


def test_relevant_actions_unfiltered_when_no_target():
    """No upgrade target (nothing to craft/equip) — don't over-filter; the
    planner gets the full action set."""
    gd = GameData()  # empty: find_upgrade_target -> None
    goal = UpgradeEquipmentGoal()  # no commitment
    actions = [GatherAction(resource_code="ash_wood", locations=frozenset({(0, 0)}))]
    assert goal.relevant_actions(actions, make_state(), gd) == actions


def test_is_satisfied_requires_committed_item_in_slot():
    goal = _goal()
    # Wrong item equipped elsewhere does NOT satisfy a shield commitment.
    s_wrong = make_state(equipment={"weapon_slot": "fishing_net", "shield_slot": None})
    assert goal.is_satisfied(s_wrong) is False
    # Target item in its slot satisfies.
    s_ok = make_state(equipment={"shield_slot": "wooden_shield"})
    assert goal.is_satisfied(s_ok) is True


def test_is_satisfied_uncommitted_uses_initial_snapshot():
    """Without a committed target, any slot differing from the initial snapshot
    still counts (preserves the inventory-ready equip path)."""
    goal = UpgradeEquipmentGoal(initial_equipment={"weapon_slot": "copper_axe"})
    changed = make_state(equipment={"weapon_slot": "iron_sword"})
    assert goal.is_satisfied(changed) is True
    unchanged = make_state(equipment={"weapon_slot": "copper_axe"})
    assert goal.is_satisfied(unchanged) is False
