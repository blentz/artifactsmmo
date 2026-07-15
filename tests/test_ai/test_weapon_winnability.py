"""Marginal weapon winnability — the predict_win-aware weapon signal.

The bug it fixes: `equip_value` targeted a high-fire-attack weapon over an earth
weapon that beats MORE monsters. The metric is MARGINAL: does OWNING a weapon let
the character beat a monster it cannot beat now?
"""

import dataclasses

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.weapon_winnability import (
    beatable_count,
    marginal_weapon_winnability,
)
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    """Two monsters, both low-HP so damage decides the kill:

    - `earth_mob`: no resistances → an earth weapon beats it.
    - `fire_mob`: fully RESISTS earth (100) → an earth weapon does 0 damage and
      CANNOT beat it; a fire weapon (fire attack, fire not resisted) can.

    Three weapons the character might own:
    - `stone_axe`  : attack earth 20 — beats earth_mob, NOT fire_mob.
    - `flame_rod`  : attack fire 20  — beats fire_mob (the one stone_axe can't).
    - `dull_club`  : attack earth 5  — beats nothing stone_axe does not already.
    """
    gd = GameData()
    gd._item_stats = {
        "stone_axe": ItemStats(code="stone_axe", level=1, type_="weapon",
                               attack={"earth": 20}),
        "flame_rod": ItemStats(code="flame_rod", level=1, type_="weapon",
                               attack={"fire": 20}),
        "dull_club": ItemStats(code="dull_club", level=1, type_="weapon",
                               attack={"earth": 5}),
    }
    gd._monster_level = {"earth_mob": 1, "fire_mob": 1}
    gd._monster_hp = {"earth_mob": 30, "fire_mob": 30}
    gd._monster_attack = {"earth_mob": {}, "fire_mob": {}}
    gd._monster_resistance = {"earth_mob": {}, "fire_mob": {"earth": 100}}
    fill_monster_stat_defaults(gd)
    return gd


def test_beatable_count_uses_per_monster_optimal_weapon():
    """Owning BOTH weapons beats BOTH monsters — pick_loadout uses stone_axe for
    earth_mob and flame_rod for fire_mob. Owning only stone_axe beats just one."""
    gd = _gd()
    axe_only = make_state(inventory={"stone_axe": 1})
    assert beatable_count(axe_only, gd) == 1  # earth_mob only; fire_mob resists earth
    both = make_state(inventory={"stone_axe": 1, "flame_rod": 1})
    assert beatable_count(both, gd) == 2


def test_flame_rod_has_positive_marginal_it_unlocks_fire_mob():
    """A weapon that lets the character beat a monster it could NOT beat scores
    > 0 — proves the metric is real winnability, not an always-zero rule."""
    gd = _gd()
    axe_only = make_state(inventory={"stone_axe": 1})
    assert marginal_weapon_winnability("flame_rod", axe_only, gd) == 1


def test_dull_club_has_zero_marginal_it_unlocks_nothing():
    """A weapon that beats no NEW monster scores 0 — this is the fire_bow case:
    high attack, zero marginal, must not be a grind target."""
    gd = _gd()
    axe_only = make_state(inventory={"stone_axe": 1})
    assert marginal_weapon_winnability("dull_club", axe_only, gd) == 0


def test_owning_a_second_copy_of_the_best_weapon_is_zero_marginal():
    """Redundant copies add no beatable monster (owned_count is not damage)."""
    gd = _gd()
    both = make_state(inventory={"stone_axe": 1, "flame_rod": 1})
    assert marginal_weapon_winnability("flame_rod", both, gd) == 0


def test_marginal_adds_to_a_copy_not_the_live_inventory():
    """The candidate is scored against a COPY — the caller's state is untouched."""
    gd = _gd()
    state = make_state(inventory={"stone_axe": 1})
    before = dict(state.inventory)
    marginal_weapon_winnability("flame_rod", state, gd)
    assert state.inventory == before
