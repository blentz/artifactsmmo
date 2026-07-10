"""Duplicate-artifact behavior: `artifact` joins `ring` as a duplicate-allowed
slot type, so the same artifact code may occupy multiple artifact slots up to
physical ownership (`min(slot_count, ownership(code))`).

Fixture pattern (`_ALL_SLOTS` / `_make_state`) copied from
`tests/ai/test_loadout_picker_purpose.py` — intentional test-support
duplication (each pick_loadout test module owns its minimal WorldState builder).
"""

from artifactsmmo_cli.ai.actions.equip import DUPLICATE_SLOT_TYPES, EquipAction
from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_value_core import Rank
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


def _make_state(
    level: int = 1,
    inventory: dict[str, int] | None = None,
    equipment: dict[str, str | None] | None = None,
) -> WorldState:
    """Minimal WorldState for pick_loadout tests. `equipment` is merged with all-None defaults."""
    eq = dict(_ALL_SLOTS)
    if equipment:
        eq.update(equipment)
    return WorldState(
        character="testchar", level=level, xp=0, max_xp=100,
        hp=100, max_hp=100, gold=0, skills={}, x=0, y=0,
        inventory=inventory or {}, inventory_max=20,
        inventory_slots_max=len(inventory or {}),
        equipment=eq, cooldown_expires=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=None, bank_gold=None, bank_capacity=None, pending_items=None,
    )


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "perfect_pearl": ItemStats(code="perfect_pearl", level=1, type_="artifact", hp_bonus=10),
    }
    return gd


def test_artifact_is_duplicate_allowed() -> None:
    assert "artifact" in DUPLICATE_SLOT_TYPES


def test_pick_loadout_fills_three_artifact_slots_when_three_owned() -> None:
    gd = _gd()
    state = _make_state(level=1, inventory={"perfect_pearl": 3},
                        equipment={"artifact1_slot": None, "artifact2_slot": None,
                                   "artifact3_slot": None})
    result = pick_loadout(Rank, state, gd)
    assert result["artifact1_slot"] == "perfect_pearl"
    assert result["artifact2_slot"] == "perfect_pearl"
    assert result["artifact3_slot"] == "perfect_pearl"


def test_pick_loadout_one_owned_fills_one_slot_only() -> None:
    gd = _gd()
    state = _make_state(level=1, inventory={"perfect_pearl": 1},
                        equipment={"artifact1_slot": None, "artifact2_slot": None,
                                   "artifact3_slot": None})
    result = pick_loadout(Rank, state, gd)
    filled = [s for s in ("artifact1_slot", "artifact2_slot", "artifact3_slot")
              if result[s] == "perfect_pearl"]
    assert len(filled) == 1  # ownership cap: never over-equip


def test_equip_second_copy_into_sibling_slot_applicable() -> None:
    gd = _gd()
    state = _make_state(level=1, inventory={"perfect_pearl": 1},
                        equipment={"artifact1_slot": "perfect_pearl", "artifact2_slot": None})
    act = EquipAction(code="perfect_pearl", slot="artifact2_slot")
    assert act.is_applicable(state, gd) is True  # dup type: worn-elsewhere does not 485-block
