"""A fight refused with HTTP 598 ("content not found at this location") drops
that tile from the monster's cached spawns. Live 2026-10-08: spawns moved under
a cached map and R2D2's supply fights hit an emptied `(-2, 12)` 40 times."""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._monster_locations = {"rat": [(-3, 12), (-2, 12)], "wolf": [(5, 5)]}
    return gd


def test_the_tile_is_forgotten() -> None:
    gd = _gd()
    gd.forget_monster_tile("rat", (-2, 12))
    assert gd.monster_locations("rat") == [(-3, 12)]


def test_the_last_tile_takes_the_monster_off_the_map() -> None:
    gd = _gd()
    gd.forget_monster_tile("wolf", (5, 5))
    assert "wolf" not in gd.all_monster_locations


def test_an_unlisted_tile_or_monster_changes_nothing() -> None:
    gd = _gd()
    gd.forget_monster_tile("rat", (9, 9))
    gd.forget_monster_tile("lich", (0, 0))
    assert gd.monster_locations("rat") == [(-3, 12), (-2, 12)]


def _player() -> GamePlayer:
    player = GamePlayer(character="hero")
    player.game_data = _gd()
    return player


def test_a_598_fight_forgets_the_tile_it_stood_on() -> None:
    player = _player()
    fight = FightAction(monster_code="rat", locations=frozenset({(-3, 12), (-2, 12)}))
    player._forget_absent_monster(fight, make_state(x=-2, y=12), "error:HTTP_598")
    assert player.game_data.monster_locations("rat") == [(-3, 12)]


def test_other_outcomes_and_actions_forget_nothing() -> None:
    player = _player()
    fight = FightAction(monster_code="rat", locations=frozenset({(-3, 12), (-2, 12)}))
    player._forget_absent_monster(fight, make_state(x=-2, y=12), "error:fight_lost")
    player._forget_absent_monster(RestAction(), make_state(x=-2, y=12), "error:HTTP_598")
    assert player.game_data.monster_locations("rat") == [(-3, 12), (-2, 12)]
