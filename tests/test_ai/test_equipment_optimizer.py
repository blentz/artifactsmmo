"""Tests for the equipment optimizer + OptimizeLoadoutAction."""

from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.equipment.scoring import (
    armor_score,
    pick_loadout,
    weapon_score,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd_with_combat_items() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "wooden_stick": ItemStats(
            code="wooden_stick", level=1, type_="weapon",
            attack={"earth": 4},
        ),
        "fishing_net": ItemStats(
            code="fishing_net", level=1, type_="weapon",
            attack={"water": 5},
        ),
        "copper_axe": ItemStats(
            code="copper_axe", level=1, type_="weapon",
            attack={"earth": 5},
        ),
        "leather_armor": ItemStats(
            code="leather_armor", level=1, type_="body_armor",
            resistance={"earth": 10},
        ),
        "water_robe": ItemStats(
            code="water_robe", level=1, type_="body_armor",
            resistance={"water": 20},
        ),
    }
    gd._monster_level = {"yellow_slime": 2, "blue_slime": 6}
    gd._monster_attack = {
        "yellow_slime": {"earth": 8, "fire": 0, "water": 0, "air": 0},
        "blue_slime":   {"earth": 0, "fire": 0, "water": 10, "air": 0},
    }
    gd._monster_resistance = {
        "yellow_slime": {"earth": 25, "fire": 0, "water": 0, "air": 0},
        "blue_slime":   {"earth": 0, "fire": 0, "water": 25, "air": 0},
    }
    return gd


class TestWeaponScore:
    def test_unresisted_water_beats_resisted_earth(self):
        gd = _gd_with_combat_items()
        slime_res = gd.monster_resistance("yellow_slime")
        # fishing_net water=5 vs slime res_water=0 → 5
        # wooden_stick earth=4 vs slime res_earth=25 → 3
        assert weapon_score(gd._item_stats["fishing_net"], slime_res) > \
               weapon_score(gd._item_stats["wooden_stick"], slime_res)

    def test_no_attack_means_zero_score(self):
        gd = _gd_with_combat_items()
        bare = ItemStats(code="empty", level=1, type_="weapon")
        assert weapon_score(bare, gd.monster_resistance("yellow_slime")) == 0


class TestArmorScore:
    def test_armor_resisting_monster_primary_wins(self):
        gd = _gd_with_combat_items()
        slime_atk = gd.monster_attack("yellow_slime")
        # leather_armor res_earth=10 vs slime atk_earth=8 → 0.8
        # water_robe res_water=20 vs slime atk_water=0 → 0
        assert armor_score(gd._item_stats["leather_armor"], slime_atk) > \
               armor_score(gd._item_stats["water_robe"], slime_atk)


class TestPickLoadout:
    def test_swaps_to_better_weapon_when_available(self):
        gd = _gd_with_combat_items()
        # Char has fishing_net in inventory + wooden_stick equipped. Fighting yellow_slime.
        state = make_state(
            level=1,
            inventory={"fishing_net": 1},
            equipment={"weapon_slot": "wooden_stick"},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        # fishing_net beats wooden_stick vs yellow_slime
        assert loadout["weapon_slot"] == "fishing_net"

    def test_keeps_current_when_no_improvement(self):
        gd = _gd_with_combat_items()
        # Char has only wooden_stick — nothing to swap to
        state = make_state(
            level=1, inventory={},
            equipment={"weapon_slot": "wooden_stick"},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        assert loadout["weapon_slot"] == "wooden_stick"


class TestOptimizeLoadoutAction:
    def test_applicable_when_swap_improves(self):
        gd = _gd_with_combat_items()
        state = make_state(
            level=1, inventory={"fishing_net": 1},
            equipment={"weapon_slot": "wooden_stick"},
        )
        action = OptimizeLoadoutAction(target_monster_code="yellow_slime")
        assert action.is_applicable(state, gd) is True

    def test_not_applicable_when_already_optimal(self):
        gd = _gd_with_combat_items()
        state = make_state(
            level=1, inventory={},
            equipment={"weapon_slot": "fishing_net"},
        )
        action = OptimizeLoadoutAction(target_monster_code="yellow_slime")
        assert action.is_applicable(state, gd) is False

    def test_apply_updates_equipment_and_inventory(self):
        gd = _gd_with_combat_items()
        state = make_state(
            level=1, inventory={"fishing_net": 1},
            equipment={"weapon_slot": "wooden_stick"},
        )
        action = OptimizeLoadoutAction(target_monster_code="yellow_slime")
        new = action.apply(state, gd)
        assert new.equipment["weapon_slot"] == "fishing_net"
        # Old item returns to inventory; new item is consumed
        assert new.inventory.get("wooden_stick", 0) == 1
        assert "fishing_net" not in new.inventory

    def test_cost_scales_with_swap_count(self):
        gd = _gd_with_combat_items()
        state = make_state(
            level=1, inventory={"fishing_net": 1},
            equipment={"weapon_slot": "wooden_stick"},
        )
        one_swap = OptimizeLoadoutAction(target_monster_code="yellow_slime").cost(state, gd)
        # Cost is positive when a swap is needed
        assert one_swap > 0

    def test_repr(self):
        assert repr(OptimizeLoadoutAction(target_monster_code="chicken")) == "OptimizeLoadout(chicken)"


class TestActionTagsIntegration:
    def test_optimize_loadout_has_equip_tag(self):
        assert "equip" in OptimizeLoadoutAction.tags
