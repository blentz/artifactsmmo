"""Tests for `boost_selection.project_equip`: a state with one utility potion
force-equipped, so `combat_margin` reads the boosted stats through its one
arithmetic path. (`best_boost_potion`, the boost picker, was deleted with the
CRAFT_POTIONS boost arm: docs/PLAN_consumable_utility.md increment 5 stocks
only the chosen loadout's potions.)

Monster fixtures use fill_monster_stat_defaults to satisfy the KeyError-on-unknown
invariant of the production monster catalog.

Math spot-check (fire_mob scenario):
  monster HP=100, attack={"fire":10}, resistance={}, crit=0, initiative=0
  player: attack={"fire":50}, max_hp=100, hp=100, initiative=1

  Baseline (no boost):
    rounds_to_kill = 2, rounds_to_die = 10, margin = 10 - 2 + 1 = 9

  With res_fire_potion (resistance={"fire":20}):
    raw_monster = max(0, 10-2) = 8 -> rounds_to_die = 13 -> margin = 12 (gain +3)

  With dmg_earth_potion (dmg_elements={"earth":30}):
    player has no earth attack -> margin unchanged = 9 (gain 0)
"""

from artifactsmmo_cli.ai.boost_selection import project_equip
from artifactsmmo_cli.ai.combat import combat_margin
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_RES_FIRE = "res_fire_potion"
_DMG_EARTH = "dmg_earth_potion"
_ALLROUND = "allround_potion"


def _gd_fire_mob() -> GameData:
    """GameData: one fire-attacking monster and three utility potions."""
    gd = GameData()
    gd._monster_level = {"fire_mob": 5}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"fire_mob": 100}
    gd._monster_attack = {"fire_mob": {"fire": 10}}
    gd._monster_resistance = {"fire_mob": {}}
    gd._item_stats = {
        _RES_FIRE: ItemStats(code=_RES_FIRE, level=1, type_="utility",
                             resistance={"fire": 20}),
        _DMG_EARTH: ItemStats(code=_DMG_EARTH, level=1, type_="utility",
                              dmg_elements={"earth": 30}),
        _ALLROUND: ItemStats(code=_ALLROUND, level=1, type_="utility",
                             attack={"water": 4}, dmg=7, critical_strike=3,
                             initiative=11, hp_bonus=25),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    return gd


def _state(**overrides):
    base = dict(level=5, hp=100, max_hp=100, attack={"fire": 50}, resistance={},
                initiative=1)
    base.update(overrides)
    return make_state(**base)


def test_projected_resistance_boost_raises_the_margin_by_its_rounds():
    """The worked example: +20% fire resistance turns margin 9 into 12."""
    gd = _gd_fire_mob()
    state = _state()
    projected = project_equip(state, _RES_FIRE, gd)
    assert projected.equipment["utility1_slot"] == _RES_FIRE
    assert projected.resistance["fire"] == 20
    assert combat_margin(state, gd, "fire_mob") == 9
    assert combat_margin(projected, gd, "fire_mob") == 12


def test_a_boost_for_an_element_the_player_lacks_changes_nothing():
    gd = _gd_fire_mob()
    state = _state()
    projected = project_equip(state, _DMG_EARTH, gd)
    assert projected.dmg_elements["earth"] == 30
    assert combat_margin(projected, gd, "fire_mob") == combat_margin(state, gd, "fire_mob")


def test_the_swapped_out_code_loses_its_stats():
    """Projecting over an equipped potion subtracts the old one's stats: the
    old resistance is gone, the new damage bonus is in."""
    gd = _gd_fire_mob()
    worn = _state(equipment={**make_state().equipment, "utility1_slot": _RES_FIRE},
                  resistance={"fire": 20})
    projected = project_equip(worn, _DMG_EARTH, gd)
    assert projected.equipment["utility1_slot"] == _DMG_EARTH
    assert projected.resistance["fire"] == 0
    assert projected.dmg_elements["earth"] == 30


def test_none_empties_the_slot_and_removes_its_stats():
    gd = _gd_fire_mob()
    worn = _state(equipment={**make_state().equipment, "utility1_slot": _RES_FIRE},
                  resistance={"fire": 20})
    projected = project_equip(worn, None, gd)
    assert projected.equipment["utility1_slot"] is None
    assert projected.resistance["fire"] == 0


def test_every_scalar_stat_moves_with_the_projection():
    gd = _gd_fire_mob()
    state = _state(dmg=1, critical_strike=2, initiative=3, max_hp=100)
    projected = project_equip(state, _ALLROUND, gd)
    assert projected.attack["water"] == 4
    assert (projected.dmg, projected.critical_strike, projected.initiative,
            projected.max_hp) == (8, 5, 14, 125)


def test_the_named_slot_is_the_one_projected():
    gd = _gd_fire_mob()
    projected = project_equip(_state(), _RES_FIRE, gd, slot="utility2_slot")
    assert projected.equipment["utility2_slot"] == _RES_FIRE
    assert projected.equipment["utility1_slot"] is None


def test_competing_utility_items_leave_the_bag_and_the_rest_stays():
    """A competing utility in the bag would let the loadout picker inside
    `combat_margin` swap the forced code out, so it is stripped; the projected
    code itself, non-utility items and unknown codes stay."""
    gd = _gd_fire_mob()
    state = _state(inventory={_RES_FIRE: 2, _DMG_EARTH: 3, "copper_ore": 4, "mystery": 1})
    projected = project_equip(state, _RES_FIRE, gd)
    assert projected.inventory == {_RES_FIRE: 2, "copper_ore": 4, "mystery": 1}
