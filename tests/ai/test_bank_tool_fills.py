"""Unit tests for `bank_tool_fills` — the strictly-better bank tool per gathering skill.

Locks the decision conjuncts:
  * strictly-better  (bank tool_value > best owned tool_value for the skill),
  * bank-known       (state.bank_items None -> {}),
  * level-usable     (stats.level <= state.level),
  * reserved-free    (code not in reserved),
  * deterministic    (value desc, then code asc).
"""

from artifactsmmo_cli.ai.equipment.bank_tool_fills import bank_tool_fills
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


def _make_state(inventory=None, equipment=None, bank_items=None,
                level: int = 10) -> WorldState:
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
        bank_items=bank_items, bank_gold=None, bank_capacity=None, pending_items=None,
    )


def _gd(**stats: ItemStats) -> GameData:
    gd = GameData()
    gd._item_stats = dict(stats)
    return gd


_PICKAXE = ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                     attack={"earth": 5}, skill_effects={"mining": -10})
_IRON_PICKAXE = ItemStats(code="iron_pickaxe", level=10, type_="weapon",
                          attack={"earth": 8}, skill_effects={"mining": -20})
_GOLD_PICKAXE = ItemStats(code="gold_pickaxe", level=20, type_="weapon",
                          attack={"earth": 10}, skill_effects={"mining": -40})
_AXE = ItemStats(code="copper_axe", level=1, type_="weapon",
                 attack={"earth": 5}, skill_effects={"woodcutting": -10})
_DAGGER = ItemStats(code="copper_dagger", level=1, type_="weapon",
                    attack={"air": 6}, critical_strike=35)


def test_banked_tool_with_no_owned_tool_is_picked() -> None:
    gd = _gd(copper_pickaxe=_PICKAXE, copper_dagger=_DAGGER)
    state = _make_state(inventory={}, equipment={"weapon_slot": "copper_dagger"},
                        bank_items={"copper_pickaxe": 1})
    assert bank_tool_fills(state, gd, frozenset()) == {"mining": "copper_pickaxe"}


def test_owned_equal_tool_suppresses_fill() -> None:
    gd = _gd(copper_pickaxe=_PICKAXE)
    state = _make_state(inventory={"copper_pickaxe": 1},
                        bank_items={"copper_pickaxe": 1})
    assert bank_tool_fills(state, gd, frozenset()) == {}


def test_equipped_equal_tool_suppresses_fill() -> None:
    gd = _gd(copper_pickaxe=_PICKAXE)
    state = _make_state(equipment={"weapon_slot": "copper_pickaxe"},
                        bank_items={"copper_pickaxe": 1})
    assert bank_tool_fills(state, gd, frozenset()) == {}


def test_strictly_better_banked_tool_beats_owned_tool() -> None:
    gd = _gd(copper_pickaxe=_PICKAXE, iron_pickaxe=_IRON_PICKAXE)
    state = _make_state(equipment={"weapon_slot": "copper_pickaxe"},
                        bank_items={"iron_pickaxe": 1})
    assert bank_tool_fills(state, gd, frozenset()) == {"mining": "iron_pickaxe"}


def test_unknown_bank_returns_empty() -> None:
    gd = _gd(copper_pickaxe=_PICKAXE)
    state = _make_state(bank_items=None)
    assert bank_tool_fills(state, gd, frozenset()) == {}


def test_level_gated_tool_is_skipped() -> None:
    gd = _gd(gold_pickaxe=_GOLD_PICKAXE)
    state = _make_state(bank_items={"gold_pickaxe": 1}, level=10)
    assert bank_tool_fills(state, gd, frozenset()) == {}


def test_reserved_code_is_skipped() -> None:
    gd = _gd(copper_pickaxe=_PICKAXE)
    state = _make_state(bank_items={"copper_pickaxe": 1})
    assert bank_tool_fills(state, gd, frozenset({"copper_pickaxe"})) == {}


def test_zero_quantity_bank_entry_is_skipped() -> None:
    gd = _gd(copper_pickaxe=_PICKAXE)
    state = _make_state(bank_items={"copper_pickaxe": 0})
    assert bank_tool_fills(state, gd, frozenset()) == {}


def test_one_fill_per_skill() -> None:
    gd = _gd(copper_pickaxe=_PICKAXE, copper_axe=_AXE)
    state = _make_state(bank_items={"copper_pickaxe": 1, "copper_axe": 1})
    assert bank_tool_fills(state, gd, frozenset()) == {
        "mining": "copper_pickaxe", "woodcutting": "copper_axe",
    }


def test_tie_breaks_by_smallest_code() -> None:
    twin = ItemStats(code="a_pickaxe", level=1, type_="weapon",
                     attack={"earth": 5}, skill_effects={"mining": -10})
    gd = _gd(copper_pickaxe=_PICKAXE, a_pickaxe=twin)
    state = _make_state(bank_items={"copper_pickaxe": 1, "a_pickaxe": 1})
    assert bank_tool_fills(state, gd, frozenset()) == {"mining": "a_pickaxe"}


def test_non_tool_weapon_in_bank_is_ignored() -> None:
    gd = _gd(copper_dagger=_DAGGER)
    state = _make_state(bank_items={"copper_dagger": 1})
    assert bank_tool_fills(state, gd, frozenset()) == {}
