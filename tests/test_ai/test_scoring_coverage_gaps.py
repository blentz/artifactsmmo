"""Behavior tests closing coverage gaps in equipment/scoring.pick_loadout.

Covers armor-slot optimization and the empty-slot (no current stats) path.
"""

from artifactsmmo_cli.ai.equipment.scoring import pick_loadout
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "leather_armor": ItemStats(code="leather_armor", level=1, type_="body_armor",
                                   resistance={"earth": 10}),
        "water_robe": ItemStats(code="water_robe", level=1, type_="body_armor",
                                resistance={"water": 20}),
        "iron_armor": ItemStats(code="iron_armor", level=1, type_="body_armor",
                                resistance={"earth": 40}),
    }
    gd._monster_attack = {
        "yellow_slime": {"earth": 8, "fire": 0, "water": 0, "air": 0},
    }
    gd._monster_resistance = {
        "yellow_slime": {"earth": 0, "fire": 0, "water": 0, "air": 0},
    }
    return gd


class TestArmorSlotLoadout:
    def test_equips_armor_into_empty_slot(self):
        """No armor equipped (current_stats is None) -> best owned armor is
        slotted in (lines 88-89)."""
        gd = _gd()
        state = make_state(
            level=1,
            inventory={"leather_armor": 1, "water_robe": 1},
            equipment={"body_armor_slot": None},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        # vs earth-attacking slime, leather (res earth 10) reduces damage;
        # water_robe (res water) does nothing -> leather chosen.
        assert loadout["body_armor_slot"] == "leather_armor"

    def test_swaps_armor_when_candidate_reduces_more_damage(self):
        """Equipped leather is beaten by iron_armor against an earth attacker
        (armor-slot upgrade comparison, lines 81 + 94-95)."""
        gd = _gd()
        state = make_state(
            level=1,
            inventory={"iron_armor": 1},
            equipment={"body_armor_slot": "leather_armor"},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        assert loadout["body_armor_slot"] == "iron_armor"

    def test_keeps_armor_when_no_candidate_improves(self):
        """Equipped iron_armor already best -> no downgrade to leather."""
        gd = _gd()
        state = make_state(
            level=1,
            inventory={"leather_armor": 1},
            equipment={"body_armor_slot": "iron_armor"},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        assert loadout["body_armor_slot"] == "iron_armor"
