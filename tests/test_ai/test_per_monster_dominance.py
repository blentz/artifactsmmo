"""Tests for per-monster pareto dominance in _is_equippable_dominated (Task 3)."""

import artifactsmmo_cli.ai.combat_targets as ct
from artifactsmmo_cli.ai.combat_targets import _clear_cache
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.inventory_caps import _is_equippable_dominated
from tests.test_ai.fixtures import make_state


def _wstate(inv):
    return make_state(level=10, inventory=inv)


def test_both_weapons_kept_when_each_best_vs_a_different_monster(monkeypatch):
    _clear_cache()
    gd = GameData()
    gd._item_stats = {
        "fire_staff": ItemStats(code="fire_staff", level=5, type_="weapon",
                                attack={"fire": 16}, critical_strike=5),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                attack={"earth": 24}, critical_strike=5),
    }
    # TWO monsters: ember is fire-weak/earth-tanky (fire_staff wins), golem is
    # earth-weak/fire-tanky (iron_sword wins) → NEITHER pareto-dominates → both kept.
    gd._monster_level = {"ember": 8, "golem": 9}
    gd._monster_resistance = {"ember": {"fire": -50, "earth": 80},
                               "golem": {"fire": 80, "earth": -20}}
    monkeypatch.setattr(ct, "is_winnable", lambda s, g, c, h=None: True)
    state = _wstate({"fire_staff": 1, "iron_sword": 1})
    assert _is_equippable_dominated("fire_staff", state, gd) is False
    assert _is_equippable_dominated("iron_sword", state, gd) is False


def test_strictly_outclassed_weapon_is_dominated(monkeypatch):
    _clear_cache()
    gd = GameData()
    gd._item_stats = {
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                  attack={"earth": 4}, critical_strike=5),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                attack={"earth": 24}, critical_strike=5),
    }
    gd._monster_level = {"slime": 8}
    gd._monster_resistance = {"slime": {"earth": 0}}
    monkeypatch.setattr(ct, "is_winnable", lambda s, g, c, h=None: True)
    state = make_state(level=10, inventory={"wooden_stick": 1, "iron_sword": 1})
    # same element, lower attack → iron_sword pareto-dominates everywhere → sold.
    assert _is_equippable_dominated("wooden_stick", state, gd) is True


def test_dominated_armor_is_dominated(monkeypatch):
    """Armor path: iron_helmet with more resistance pareto-dominates leather_cap."""
    _clear_cache()
    gd = GameData()
    gd._item_stats = {
        "leather_cap": ItemStats(code="leather_cap", level=1, type_="helmet",
                                 resistance={"earth": 5}),
        "iron_helmet": ItemStats(code="iron_helmet", level=10, type_="helmet",
                                 resistance={"earth": 20}),
    }
    gd._monster_level = {"goblin": 8}
    gd._monster_attack = {"goblin": {"earth": 30}}
    monkeypatch.setattr(ct, "is_winnable", lambda s, g, c, h=None: True)
    state = make_state(level=10, inventory={"leather_cap": 1, "iron_helmet": 1})
    # iron_helmet scores higher vs goblin's earth attack → pareto-dominates leather_cap.
    assert _is_equippable_dominated("leather_cap", state, gd) is True


def test_empty_monster_set_falls_back_to_flat_equip_value(monkeypatch):
    _clear_cache()
    gd = GameData()
    gd._item_stats = {
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                  attack={"earth": 4}),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                attack={"earth": 24}),
    }
    gd._monster_level = {"slime": 1}
    monkeypatch.setattr(ct, "is_winnable", lambda s, g, c, h=None: False)  # nothing winnable
    state = make_state(level=30, inventory={"wooden_stick": 1, "iron_sword": 1})
    # empty set → flat equip_value path: iron_sword (higher attack) dominates wooden_stick.
    assert _is_equippable_dominated("wooden_stick", state, gd) is True
