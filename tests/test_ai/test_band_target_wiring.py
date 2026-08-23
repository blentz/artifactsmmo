"""The cascade's tier-2 source is the band target, not the unbounded projection."""
import artifactsmmo_cli.ai.player as player_mod
import artifactsmmo_cli.ai.tiers.band_target as band_target_mod
import artifactsmmo_cli.ai.tiers.tier_progress as tier_progress_mod
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
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


def test_unfightable_band_target_falls_through_to_the_windowed_picker(monkeypatch):
    """GAP-8 / task 5.2 fix round 1: before `band_combat_target` applied
    `FIGHT_LEVEL_GAP_CEILING`, a stat-winnable-but-unfightable target (e.g.
    `highwayman` at char level 10) outranked tier 3 outright — `is_winnable`
    is a pure stat question, so `path_winnable` read True, the windowed
    picker (which HAS the correct `[char_level-1, char_level+2]` window and
    a fallback) never ran, and combat stopped entirely. This exercises the
    REAL `band_combat_target` (not a mock) end-to-end through
    `_winnable_farm_target`, so it would have caught GAP-8 itself: the
    band's only stat-winnable member (`highwayman`, L15) sits outside the
    executor's window at char level 10, so `band_combat_target` must return
    None, and the cascade must fall through to tier 3, which finds
    `mushmush` (L10, in-window, winnable) rather than surfacing None or the
    unfightable `highwayman`."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return c != "pig"  # pig stays unwinnable so tier 15 stays uncleared
    monkeypatch.setattr(band_target_mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tier_progress_mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(player_mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(GamePlayer, "_task_aligned_monster", lambda self: None)

    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon"),
        "steel_sword": ItemStats(code="steel_sword", level=15, type_="weapon"),
    }
    gd._monster_level = {"chicken": 1, "mushmush": 10, "highwayman": 15, "pig": 19}
    gd._monster_type = {"chicken": "normal", "mushmush": "normal",
                        "highwayman": "normal", "pig": "normal"}
    gd._monster_hp = {"chicken": 60, "mushmush": 350, "highwayman": 500, "pig": 600}

    player = GamePlayer(character="Robby")
    player.state = make_state(level=10)
    player.game_data = gd

    assert player._winnable_farm_target() == "mushmush"


def test_unseeded_player_yields_no_path_aligned_monster():
    """`_path_aligned_monster` keeps its `state`/`game_data` guard: a player
    that has not yet been seeded must not reach `band_combat_target` (or
    `cheapest_path_to_level`) at all."""
    player = GamePlayer(character="Robby")
    assert player.state is None
    assert player.game_data is None
    assert player._path_aligned_monster() is None
