"""Unit tests for `empty_slot_rank_fills` — the best owned item per empty slot.

Locks the three decision conjuncts the mutation gate perturbs:
  * empty-only     (`state.equipment.get(slot) is None`),
  * present        (`code is not None`),
  * reserved-free  (`code not in reserved`).
"""

from artifactsmmo_cli.ai.equipment.empty_slot_fills import empty_slot_rank_fills
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_taxonomy import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


def _make_state(inventory=None, equipment=None, level: int = 10) -> WorldState:
    eq = dict(_ALL_SLOTS)
    if equipment:
        eq.update(equipment)
    return WorldState(
        character="c", level=level, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        skills={}, x=0, y=0, inventory=inventory or {}, inventory_max=20,
        inventory_slots_max=len(inventory or {}),
        equipment=eq, cooldown_expires=None, task_code=None, task_type=None,
        task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=None, bank_gold=None, bank_capacity=None, pending_items=None,
    )


def _gd(**stats: ItemStats) -> GameData:
    gd = GameData()
    gd._item_stats = dict(stats)
    return gd


_NOVICE = ItemStats(code="novice_guide", level=1, type_="artifact",
                    hp_bonus=30, wisdom=10, prospecting=5)
_STRONG_AMULET = ItemStats(code="strong_amulet", level=1, type_="amulet", hp_bonus=30)
_WEAK_AMULET = ItemStats(code="weak_amulet", level=1, type_="amulet", hp_bonus=1)
_RING = ItemStats(code="copper_ring", level=1, type_="ring", hp_bonus=5)


def test_empty_artifact_slot_filled_by_owned_positive_item() -> None:
    gd = _gd(novice_guide=_NOVICE)
    state = _make_state(inventory={"novice_guide": 1})
    assert empty_slot_rank_fills(state, gd, frozenset()) == {"artifact1_slot": "novice_guide"}


def test_all_slots_full_yields_no_fills() -> None:
    gd = _gd(novice_guide=_NOVICE)
    full = {slot: "novice_guide" for slot in _ALL_SLOTS}
    state = _make_state(equipment=full)
    assert empty_slot_rank_fills(state, gd, frozenset()) == {}


def test_filled_slot_with_better_owned_item_is_not_displaced() -> None:
    # The single amulet slot already holds a weaker amulet; a strictly-better
    # one is owned. pick_loadout would SWAP it in, but empty_slot_rank_fills is
    # empty-only: the incumbent slot must never appear (and there is no other
    # amulet slot for the displaced item to land in).
    gd = _gd(strong_amulet=_STRONG_AMULET, weak_amulet=_WEAK_AMULET)
    state = _make_state(inventory={"strong_amulet": 1},
                        equipment={"amulet_slot": "weak_amulet"})
    fills = empty_slot_rank_fills(state, gd, frozenset())
    assert "amulet_slot" not in fills
    assert fills == {}


def test_reserved_item_is_excluded() -> None:
    gd = _gd(novice_guide=_NOVICE)
    state = _make_state(inventory={"novice_guide": 1})
    assert empty_slot_rank_fills(state, gd, frozenset({"novice_guide"})) == {}


def test_two_empty_ring_slots_one_owned_ring_fills_exactly_one() -> None:
    gd = _gd(copper_ring=_RING)
    state = _make_state(inventory={"copper_ring": 1})
    fills = empty_slot_rank_fills(state, gd, frozenset())
    assert list(fills.values()) == ["copper_ring"]
    (slot,) = fills.keys()
    assert slot in ITEM_TYPE_TO_SLOTS["ring"]
