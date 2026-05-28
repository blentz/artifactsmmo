"""Behavior tests closing coverage gaps in UpgradeEquipmentGoal (progression).

Asserts the goal's value tiers, commitment readiness, inventory-pick ranking,
and craftable-upgrade filtering.
"""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.progression import (
    _UPGRADE_EQUIPMENT_BASE,
    _UPGRADE_EQUIPMENT_RELEVANT_TOOL,
    UpgradeEquipmentGoal,
)
from tests.test_ai.fixtures import make_state


def _gd_with_axe_tool() -> GameData:
    """A copper_axe that boosts woodcutting, craftable from ash_plank, and a
    woodcutting resource so a woodcutting task is 'active'."""
    gd = GameData()
    gd._item_stats = {
        "copper_axe": ItemStats(
            code="copper_axe", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
            skill_effects={"woodcutting": -10},
        ),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
        "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
    }
    gd._crafting_recipes = {
        "copper_axe": {"ash_plank": 2},
        "ash_plank": {"ash_wood": 1},
    }
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    return gd


class TestRelevantToolValueTier:
    def test_value_is_relevant_tool_tier_for_active_skill(self):
        """A craftable tool that boosts the active task's gather skill, with
        materials in hand, scores the higher relevant-tool tier."""
        gd = _gd_with_axe_tool()
        goal = UpgradeEquipmentGoal()
        # Woodcutting task active; 2 ash_plank on hand -> copper_axe craftable.
        state = make_state(
            level=5, skills={"weaponcrafting": 1, "woodcutting": 1},
            task_code="ash_plank", task_type="items", task_total=10,
            inventory={"ash_plank": 2},
            equipment={"weapon_slot": None},
        )
        assert goal.value(state, gd) == _UPGRADE_EQUIPMENT_RELEVANT_TOOL

    def test_value_is_base_tier_when_no_active_skill(self):
        """The same tool-bearing upgrade, but with NO active gathering task,
        is not a relevant-tool upgrade (line 56 returns False) -> base tier."""
        gd = _gd_with_axe_tool()
        goal = UpgradeEquipmentGoal()
        state = make_state(
            level=5, skills={"weaponcrafting": 1, "woodcutting": 1},
            task_code=None, task_type=None,
            inventory={"ash_plank": 2},
            equipment={"weapon_slot": None},
        )
        # No task/crafting_target -> active gathering skills empty.
        assert goal.value(state, gd) == _UPGRADE_EQUIPMENT_BASE


class TestCommittedReadiness:
    def _gd(self) -> GameData:
        gd = GameData()
        gd._item_stats = {
            "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                       crafting_skill="gearcrafting", crafting_level=1),
        }
        gd._crafting_recipes = {"wooden_shield": {"ash_plank": 4}}
        return gd

    def test_committed_ready_when_already_crafted_in_inventory(self):
        """No materials left, but the finished item sits in inventory ->
        the committed target is equip-ready (line 177)."""
        gd = self._gd()
        goal = UpgradeEquipmentGoal(committed_target=("wooden_shield", "shield_slot"))
        state = make_state(level=5, inventory={"wooden_shield": 1},
                           equipment={"shield_slot": None})
        # _find_upgrade -> _committed_upgrade_if_ready returns the target.
        assert goal._find_upgrade(state, gd) == ("wooden_shield", "shield_slot")
        assert goal.desired_state(state, gd) == {
            "equipment": {"shield_slot": "wooden_shield"}
        }

    def test_committed_not_ready_when_no_materials_and_not_crafted(self):
        gd = self._gd()
        goal = UpgradeEquipmentGoal(committed_target=("wooden_shield", "shield_slot"))
        state = make_state(level=5, inventory={}, equipment={"shield_slot": None})
        assert goal._find_upgrade(state, gd) is None


class TestValueOf:
    def test_value_of_none_is_negative_infinity(self):
        """A None pick has -inf value so any real pick beats it in
        _best_by_value tie-breaking."""
        goal = UpgradeEquipmentGoal()
        assert goal._value_of(None, GameData()) == -float("inf")


class TestInventoryUpgradeSkipsZeroQty:
    def test_zero_qty_inventory_item_skipped(self):
        """An inventory entry with combined inv+bank qty <= 0 is skipped
        (line 224); a real owned upgrade is still found."""
        gd = GameData()
        gd._item_stats = {
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        }
        gd._crafting_recipes = {}
        goal = UpgradeEquipmentGoal()
        state = make_state(
            level=5,
            inventory={"copper_dagger": 1, "phantom": 0},
            equipment={"weapon_slot": None},
        )
        assert goal._find_inventory_upgrade(state, gd) == ("copper_dagger", "weapon_slot")


class TestCraftableUpgradeSkipsNonUpgrade:
    def test_skips_candidate_that_is_not_an_upgrade(self):
        """A craftable item worse than the currently-equipped gear is not an
        upgrade (line 282 continue), so it is not chosen."""
        gd = GameData()
        gd._item_stats = {
            # Equipped, craftable, high level.
            "steel_sword": ItemStats(code="steel_sword", level=5, type_="weapon",
                                     crafting_skill="weaponcrafting", crafting_level=1,
                                     attack={"fire": 50}),
            # Craftable but strictly worse than the equipped steel_sword.
            "wooden_stick": ItemStats(code="wooden_stick", level=5, type_="weapon",
                                      crafting_skill="weaponcrafting", crafting_level=1,
                                      attack={"fire": 1}),
        }
        gd._crafting_recipes = {
            "steel_sword": {"iron_bar": 6},
            "wooden_stick": {"ash_wood": 1},
        }
        goal = UpgradeEquipmentGoal()
        state = make_state(
            level=5, skills={"weaponcrafting": 5},
            inventory={},
            equipment={"weapon_slot": "steel_sword"},
        )
        # wooden_stick is same-level, lower stats, not relevant tool -> not an
        # upgrade over the equipped steel_sword -> no craftable target.
        assert goal._find_craftable_upgrade_target(state, gd) is None
