"""Factory layered-content actions (P5b): off-overworld monsters/resources get
region-tagged Fight/Gather actions; overworld layered tiles are NOT re-emitted
(the legacy overworld indexes already cover them).
"""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._monster_level = {"lich": 1}
    gd._monster_locations = {}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"lich": 10}
    gd._resource_skill = {"crystal_rocks": ("mining", 1)}
    gd._resource_drops = {"crystal_rocks": "crystal"}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    gd.world.layered_content = {
        "lich": [(9, 8, "underground")],
        "crystal_rocks": [(4, 4, "underground"), (4, 5, "underground")],
        "chicken": [(0, 1, "overworld")],  # overworld layered tile: skipped
    }
    return gd


def _build(gd: GameData) -> list:
    return build_actions(game_data=gd, state=make_state(), objective=None,
                         bank_accessible=True, task_exchange_min_coins=6)


def test_layered_monster_gets_region_tagged_fight_and_loadout() -> None:
    actions = _build(_gd())
    fights = [a for a in actions if isinstance(a, FightAction) and a.monster_code == "lich"]
    assert len(fights) == 1
    assert fights[0].travel_region == "underground"
    assert fights[0].locations == frozenset({(9, 8)})
    assert any(isinstance(a, OptimizeLoadoutAction) and a.target_monster_code == "lich"
               for a in actions)


def test_layered_resource_gets_region_tagged_gather() -> None:
    actions = _build(_gd())
    gathers = [a for a in actions
               if isinstance(a, GatherAction) and a.resource_code == "crystal_rocks"]
    assert len(gathers) == 1
    assert gathers[0].travel_region == "underground"
    assert gathers[0].locations == frozenset({(4, 4), (4, 5)})


def test_overworld_layered_tiles_are_not_re_emitted() -> None:
    actions = _build(_gd())
    assert not any(isinstance(a, FightAction) and a.monster_code == "chicken"
                   for a in actions)
