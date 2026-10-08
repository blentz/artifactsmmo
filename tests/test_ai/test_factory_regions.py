"""The factory emits one fight/gather per access REGION of its tiles, carrying
that region (2026-10-08). An island is overworld-LAYER but a separate region:
palm_tree's legacy gather sat on Sandwhisper Isle (`overworld:-4,17`, reached
by a 1000-gold boat) labelled "overworld", so the walk planned it from the
mainland with no crossing."""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd.world.walkable_tiles = {(0, 0, "overworld"), (1, 0, "overworld"),
                               (5, 5, "overworld"), (5, 6, "overworld")}
    gd.world.bank_tile = (0, 0)
    gd._taskmaster_location = (1, 0)
    gd._monster_level = {"crab": 5}
    gd._monster_locations = {"crab": [(1, 0), (5, 5)]}
    gd._resource_locations = {"palm_tree": [(5, 6), (1, 0)]}
    return gd


def _regions(actions, kind, code):  # type: ignore[no-untyped-def]
    return sorted((a.travel_region, tuple(sorted(a.locations))) for a in actions
                  if isinstance(a, kind) and (getattr(a, "monster_code", None) == code
                                              or getattr(a, "resource_code", None) == code))


def test_a_fight_per_region() -> None:
    actions = build_actions(_gd(), make_state(), None, bank_accessible=True,
                            task_exchange_min_coins=1)
    assert _regions(actions, FightAction, "crab") == [("overworld", ((1, 0),)),
                                                      ("overworld:5,5", ((5, 5),))]


def test_a_gather_per_region() -> None:
    actions = build_actions(_gd(), make_state(), None, bank_accessible=True,
                            task_exchange_min_coins=1)
    got = [r for r in _regions(actions, GatherAction, "palm_tree")]
    assert got == [("overworld", ((1, 0),)), ("overworld:5,5", ((5, 6),))]


def test_the_layered_path_adds_no_second_copy() -> None:
    gd = _gd()
    gd.world.layered_content = {"crab": [(5, 5, "overworld")]}
    actions = build_actions(gd, make_state(), None, bank_accessible=True,
                            task_exchange_min_coins=1)
    assert len([a for a in actions if isinstance(a, FightAction) and a.monster_code == "crab"
                and a.travel_region == "overworld:5,5"]) == 1
