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


class TestValueCandidate:
    def test_none_pick_yields_no_candidate(self):
        """P4a (exact arithmetic): the float ``-inf`` sentinel is gone.
        A None pick yields no candidate, so `best_by_value` treats it as
        the always-loses side — same verdict the -inf value produced."""
        goal = UpgradeEquipmentGoal()
        assert goal._value_candidate(None, GameData()) is None

    def test_missing_stats_pick_yields_no_candidate(self):
        """P4a: a pick whose item_stats are missing also yields no candidate
        (previously a -inf-valued candidate). Production-unreachable: both
        finders only emit picks whose stats resolved."""
        goal = UpgradeEquipmentGoal()
        assert goal._value_candidate(("ghost_item", "weapon_slot"), GameData()) is None


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


class TestSiblingSlotTargeting:
    def test_second_ring_is_a_craft_target_when_same_ring_worn(self):
        """DUAL-RING (live probe 2026-06-14, HTTP 200): a copper_ring worn in
        ring1 DOES make ring2 a craft target for a SECOND copper_ring — the
        server allows the same code in both ring slots up to ownership. This is
        Robby's level-3 stall (2026-06-29): the upgrade selector wrongly applied
        the one-slot-per-code (HTTP 485) rule to rings (a stale pre-dual-ring
        assumption in `_worn_in_other_slot`), dropped the ring2 target, and the
        bot ground throwaway wooden_shields instead of crafting the 2nd ring.
        `_worn_in_other_slot` now carves out DUPLICATE_SLOT_TYPES."""
        gd = GameData()
        gd._item_stats = {
            "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                     crafting_skill="jewelrycrafting", crafting_level=1),
        }
        gd._crafting_recipes = {"copper_ring": {"copper_bar": 6}}
        goal = UpgradeEquipmentGoal()
        state = make_state(
            level=5, skills={"jewelrycrafting": 1},
            inventory={},
            equipment={"ring1_slot": "copper_ring", "ring2_slot": None},
        )
        assert goal._find_craftable_upgrade_target(state, gd) == ("copper_ring", "ring2_slot")

    def test_different_code_still_targets_the_sibling_slot(self):
        """One-slot-per-code only forbids the SAME code: a different craftable
        ring remains a valid target for the empty ring2."""
        gd = GameData()
        gd._item_stats = {
            "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                     crafting_skill="jewelrycrafting", crafting_level=1),
            "iron_ring": ItemStats(code="iron_ring", level=1, type_="ring",
                                   crafting_skill="jewelrycrafting", crafting_level=1),
        }
        gd._crafting_recipes = {
            "copper_ring": {"copper_bar": 6},
            "iron_ring": {"iron_bar": 6},
        }
        goal = UpgradeEquipmentGoal()
        state = make_state(
            level=5, skills={"jewelrycrafting": 1},
            inventory={},
            equipment={"ring1_slot": "copper_ring", "ring2_slot": None},
        )
        assert goal._find_craftable_upgrade_target(state, gd) == ("iron_ring", "ring2_slot")

    def test_inventory_spare_ring_is_an_upgrade_into_sibling_slot(self):
        """Dual-ring: a spare copy of the worn copper_ring in inventory IS an
        upgrade target for the empty ring2 — it can be equipped there (HTTP 200,
        capped at ownership). (Previously this path also mis-applied the
        one-slot-per-code rule to rings and derived no target.)"""
        gd = GameData()
        gd._item_stats = {
            "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                     crafting_skill="jewelrycrafting", crafting_level=1),
        }
        gd._crafting_recipes = {}
        goal = UpgradeEquipmentGoal()
        state = make_state(
            level=5,
            inventory={"copper_ring": 1},
            equipment={"ring1_slot": "copper_ring", "ring2_slot": None},
        )
        assert goal._find_inventory_upgrade(state, gd) == ("copper_ring", "ring2_slot")

    def test_no_recraft_when_both_multi_slots_filled(self):
        """When both ring slots already hold the item, there is no empty slot to
        fill and the same item is not an upgrade over itself -> no target."""
        gd = GameData()
        gd._item_stats = {
            "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                     crafting_skill="jewelrycrafting", crafting_level=1),
        }
        gd._crafting_recipes = {"copper_ring": {"copper_bar": 6}}
        goal = UpgradeEquipmentGoal()
        state = make_state(
            level=5, skills={"jewelrycrafting": 1},
            inventory={},
            equipment={"ring1_slot": "copper_ring", "ring2_slot": "copper_ring"},
        )
        assert goal._find_craftable_upgrade_target(state, gd) is None

    def test_no_recraft_when_copy_waiting_in_inventory(self):
        """A copy already in inventory is equip-ready; don't craft a duplicate
        (the inventory-upgrade path equips it into the empty ring2)."""
        gd = GameData()
        gd._item_stats = {
            "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                     crafting_skill="jewelrycrafting", crafting_level=1),
        }
        gd._crafting_recipes = {"copper_ring": {"copper_bar": 6}}
        goal = UpgradeEquipmentGoal()
        state = make_state(
            level=5, skills={"jewelrycrafting": 1},
            inventory={"copper_ring": 1},
            equipment={"ring1_slot": "copper_ring", "ring2_slot": None},
        )
        assert goal._find_craftable_upgrade_target(state, gd) is None

    def test_worn_NON_dup_type_still_blocks_sibling_slot_craft(self):
        """The dual-ring carve is RING-SPECIFIC: a NON-duplicate multi-slot type
        (artifact) worn in artifact1 still can't fill artifact2 (server HTTP 485
        one-slot-per-code), so it is not a craft target — `_worn_in_other_slot`
        returns True for non-dup types and the per-slot candidate is dropped."""
        gd = GameData()
        gd._item_stats = {
            "novice_guide": ItemStats(code="novice_guide", level=1, type_="artifact",
                                      crafting_skill="jewelrycrafting", crafting_level=1,
                                      hp_bonus=25),
        }
        gd._crafting_recipes = {"novice_guide": {"copper_bar": 6}}
        goal = UpgradeEquipmentGoal()
        state = make_state(
            level=5, skills={"jewelrycrafting": 1},
            inventory={},
            equipment={"artifact1_slot": "novice_guide", "artifact2_slot": None,
                       "artifact3_slot": None},
        )
        assert goal._find_craftable_upgrade_target(state, gd) is None

    def test_worn_NON_dup_type_still_blocks_sibling_slot_inventory(self):
        """Same for the inventory path: a spare artifact in inventory while one is
        worn can NOT go into a sibling artifact slot (non-dup one-slot-per-code)."""
        gd = GameData()
        gd._item_stats = {
            "novice_guide": ItemStats(code="novice_guide", level=1, type_="artifact",
                                      hp_bonus=25),
        }
        gd._crafting_recipes = {}
        goal = UpgradeEquipmentGoal()
        state = make_state(
            level=5,
            inventory={"novice_guide": 1},
            equipment={"artifact1_slot": "novice_guide", "artifact2_slot": None,
                       "artifact3_slot": None},
        )
        assert goal._find_inventory_upgrade(state, gd) is None


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
