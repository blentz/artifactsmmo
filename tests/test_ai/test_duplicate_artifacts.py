"""Duplicate-slot behavior: `ring` is duplicate-allowed, `artifact` is NOT.

HISTORY, because this module used to assert the opposite. Artifacts were added
to `DUPLICATE_SLOT_TYPES` on 2026-07-03 by ASSERTION — the 2026-06-14 dual-ring
probe (a 2nd identical copper_ring into ring2_slot → HTTP 200) was read as
establishing a per-SLOT equip model, and the spec recorded the trigger "on the
first ≥2-owned artifact, confirm the 2nd-copy equip returns HTTP 200, else
revert artifact".

The trigger fired on 2026-08-22. Character Lor held `lich_race_medal` in
artifact1_slot with a second copy in the bag and artifact2_slot/artifact3_slot
BOTH EMPTY; the server answered the 2nd-copy equip with HTTP 485 "This item is
already equipped". The artifact model is per-CODE. Between the assertion and the
probe, Lor burned 55 zero-progress cycles in 50 minutes across four goals on
that one refused equip.

So this module now pins BOTH halves, and the ring half is load-bearing: it is
what stops the revert from over-correcting into "no type may ever duplicate",
which would silently kill the dual-ring carve-out that a real HTTP 200 supports.

Fixture pattern (`_ALL_SLOTS` / `_make_state`) copied from
`tests/test_ai/test_loadout_picker_purpose.py` — intentional test-support
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
        "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring", hp_bonus=10),
    }
    return gd


def test_artifact_is_not_duplicate_allowed() -> None:
    """The Lor probe's verdict, as a constant. HTTP 485 on a 2nd copy into an
    EMPTY sibling artifact slot means the server keys artifacts by CODE."""
    assert "artifact" not in DUPLICATE_SLOT_TYPES


def test_ring_is_still_duplicate_allowed() -> None:
    """The anti-over-correction pin. Rings have their OWN probe (HTTP 200,
    2026-06-14) and the artifact revert must not take them with it."""
    assert "ring" in DUPLICATE_SLOT_TYPES


def test_pick_loadout_fills_only_one_artifact_slot_when_three_owned() -> None:
    """Three owned copies still buy exactly one worn copy: the per-code cap for
    a non-dup type is 1, whatever ownership says."""
    gd = _gd()
    state = _make_state(level=1, inventory={"perfect_pearl": 3},
                        equipment={"artifact1_slot": None, "artifact2_slot": None,
                                   "artifact3_slot": None})
    result = pick_loadout(Rank, state, gd)
    filled = [s for s in ("artifact1_slot", "artifact2_slot", "artifact3_slot")
              if result[s] == "perfect_pearl"]
    assert len(filled) == 1


def test_pick_loadout_fills_both_ring_slots_when_two_owned() -> None:
    """The dual-ring carve-out, unharmed by the artifact revert."""
    gd = _gd()
    state = _make_state(level=1, inventory={"copper_ring": 2},
                        equipment={"ring1_slot": None, "ring2_slot": None})
    result = pick_loadout(Rank, state, gd)
    assert result["ring1_slot"] == "copper_ring"
    assert result["ring2_slot"] == "copper_ring"


def test_pick_loadout_one_owned_fills_one_slot_only() -> None:
    gd = _gd()
    state = _make_state(level=1, inventory={"perfect_pearl": 1},
                        equipment={"artifact1_slot": None, "artifact2_slot": None,
                                   "artifact3_slot": None})
    result = pick_loadout(Rank, state, gd)
    filled = [s for s in ("artifact1_slot", "artifact2_slot", "artifact3_slot")
              if result[s] == "perfect_pearl"]
    assert len(filled) == 1  # ownership cap: never over-equip


def test_equip_second_artifact_copy_into_empty_sibling_slot_refused() -> None:
    """THE LIVE CASE, exactly as Lor stood: one worn, one spare in the bag, the
    sibling slot EMPTY. The server answers 485, so the planner must never offer
    it — an offered step here is the 55-cycle livelock."""
    gd = _gd()
    state = _make_state(level=1, inventory={"perfect_pearl": 1},
                        equipment={"artifact1_slot": "perfect_pearl", "artifact2_slot": None})
    act = EquipAction(code="perfect_pearl", slot="artifact2_slot")
    assert act.is_applicable(state, gd) is False


def test_equip_second_ring_copy_into_empty_sibling_slot_offered() -> None:
    """Same shape, ring type, opposite verdict — the server returns HTTP 200
    here (probe 2026-06-14) and the planner must keep offering it."""
    gd = _gd()
    state = _make_state(level=1, inventory={"copper_ring": 1},
                        equipment={"ring1_slot": "copper_ring", "ring2_slot": None})
    act = EquipAction(code="copper_ring", slot="ring2_slot")
    assert act.is_applicable(state, gd) is True
