"""The cascade's tier-2 source is the band target, not the unbounded projection."""
import artifactsmmo_cli.ai.player as player_mod
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _make_planner_gd


def test_the_cascade_asks_the_band_not_the_unbounded_projection(monkeypatch):
    """`_path_aligned_monster` used `cheapest_path_to_level`, whose candidate
    floor is 1. The cascade must consult `band_combat_target` instead."""
    player = GamePlayer(character="Robby")
    player.state = make_state(level=30)
    player.game_data = _make_planner_gd()

    monkeypatch.setattr(player_mod, "band_combat_target",
                        lambda state, game_data, history: "spider")
    monkeypatch.setattr(GamePlayer, "_task_aligned_monster", lambda self: None)
    monkeypatch.setattr(GamePlayer, "_is_winnable", lambda self, code: True)

    assert player._winnable_farm_target() == "spider"


def test_no_band_target_yields_no_combat_target(monkeypatch):
    """A gear wall must surface as None, not fall through to a lower tier."""
    player = GamePlayer(character="Robby")
    player.state = make_state(level=30)
    player.game_data = _make_planner_gd()

    monkeypatch.setattr(player_mod, "band_combat_target",
                        lambda state, game_data, history: None)
    monkeypatch.setattr(GamePlayer, "_task_aligned_monster", lambda self: None)

    assert player._winnable_farm_target() is None


def test_a_winnable_task_monster_still_wins(monkeypatch):
    """Tier 1 is unchanged: the held task's monster outranks the band when it
    is winnable, because the task is what the character is blocked on."""
    player = GamePlayer(character="Robby")
    player.state = make_state(level=30)
    player.game_data = _make_planner_gd()

    monkeypatch.setattr(GamePlayer, "_task_aligned_monster", lambda self: "pig")
    monkeypatch.setattr(player_mod, "band_combat_target",
                        lambda state, game_data, history: "spider")

    assert player._winnable_farm_target() == "pig"


def test_unseeded_player_yields_no_path_aligned_monster():
    """`_path_aligned_monster` keeps its `state`/`game_data` guard: a player
    that has not yet been seeded must not reach `band_combat_target` (or
    `cheapest_path_to_level`) at all."""
    player = GamePlayer(character="Robby")
    assert player.state is None
    assert player.game_data is None
    assert player._path_aligned_monster() is None
