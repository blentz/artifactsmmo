"""Tests for projecting a hypothetical loadout's combat stats."""

from artifactsmmo_cli.ai.equipment.projection import ProjectedStats, project_loadout_stats
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd(items):
    gd = GameData()
    gd._item_stats = items
    return gd


def test_identity_when_loadout_equals_current():
    state = make_state(attack={"fire": 10}, resistance={"earth": 5}, max_hp=120,
                       equipment={"weapon_slot": "wand", "ring1_slot": None})
    gd = _gd({"wand": ItemStats(code="wand", level=1, type_="weapon", attack={"fire": 7})})
    proj = project_loadout_stats(state, dict(state.equipment), gd)
    assert isinstance(proj, ProjectedStats)
    assert proj.attack == {"fire": 10}      # no delta
    assert proj.max_hp == 120


def test_swapping_in_stronger_weapon_raises_attack():
    state = make_state(attack={"fire": 10}, equipment={"weapon_slot": "wand"})
    gd = _gd({
        "wand": ItemStats(code="wand", level=1, type_="weapon", attack={"fire": 7}),
        "staff": ItemStats(code="staff", level=1, type_="weapon", attack={"fire": 12}),
    })
    proj = project_loadout_stats(state, {"weapon_slot": "staff"}, gd)
    assert proj.attack["fire"] == 10 + (12 - 7)


def test_hp_bonus_ring_raises_max_hp():
    state = make_state(max_hp=100, equipment={"ring1_slot": None})
    gd = _gd({"hp_ring": ItemStats(code="hp_ring", level=1, type_="ring", hp_bonus=40)})
    proj = project_loadout_stats(state, {"ring1_slot": "hp_ring"}, gd)
    assert proj.max_hp == 140


def test_unknown_new_item_removes_old_contribution():
    # wand (known, fire 7) is equipped and folded into the fire-10 total. Swapping
    # to an unknown item contributes 0 for the new item but still subtracts wand.
    state = make_state(attack={"fire": 10}, equipment={"weapon_slot": "wand"})
    gd = _gd({"wand": ItemStats(code="wand", level=1, type_="weapon", attack={"fire": 7})})
    proj = project_loadout_stats(state, {"weapon_slot": "ghost"}, gd)
    assert proj.attack["fire"] == 10 - 7   # new=0, old(wand)=7 subtracted


def test_downgrade_keeps_negative_delta():
    # Swapping a strong fire weapon (12) for a weak one (4) lowers projected attack;
    # _drop_zeros retains the negative (predict_win floors per-element at 0 later).
    state = make_state(attack={"fire": 14}, equipment={"weapon_slot": "strong"})
    gd = _gd({
        "strong": ItemStats(code="strong", level=1, type_="weapon", attack={"fire": 12}),
        "weak": ItemStats(code="weak", level=1, type_="weapon", attack={"fire": 4}),
    })
    proj = project_loadout_stats(state, {"weapon_slot": "weak"}, gd)
    assert proj.attack["fire"] == 14 + (4 - 12)   # == 6


def test_resistance_projection():
    state = make_state(resistance={"earth": 5}, equipment={"body_armor_slot": None})
    gd = _gd({"plate": ItemStats(code="plate", level=1, type_="body_armor", resistance={"earth": 12})})
    proj = project_loadout_stats(state, {"body_armor_slot": "plate"}, gd)
    assert proj.resistance["earth"] == 5 + 12


def test_dmg_crit_initiative_project():
    state = make_state(equipment={"ring1_slot": None}, critical_strike=0, initiative=10)
    gd = _gd({"ring": ItemStats(code="ring", level=1, type_="ring",
                                dmg=8, dmg_elements={"fire": 3}, critical_strike=5, initiative=4)})
    proj = project_loadout_stats(state, {"ring1_slot": "ring"}, gd)
    assert proj.dmg == 8
    assert proj.dmg_elements == {"fire": 3}
    assert proj.critical_strike == 5
    assert proj.initiative == 14
