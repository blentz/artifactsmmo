"""A rung is cleared when every NORMAL monster in its band is winnable; the gear
target is the rung being cleared, capped by character level."""
import artifactsmmo_cli.ai.tiers.tier_progress as mod
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.tier_progress import (
    gear_target_tier,
    next_uncleared_tier,
    tier_cleared,
)
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon"),
        "battlestaff": ItemStats(code="battlestaff", level=20, type_="weapon"),
    }
    gd._monster_level = {"chicken": 1, "mushmush": 10, "king_slime": 15,
                         "spider": 20}
    gd._monster_type = {"chicken": "normal", "mushmush": "normal",
                        "king_slime": "boss", "spider": "normal"}
    return gd


def test_a_rung_is_cleared_when_every_normal_monster_is_winnable(monkeypatch):
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: True)
    assert tier_cleared(make_state(level=30), _gd(), 10, None) is True


def test_an_unwinnable_normal_monster_leaves_the_rung_uncleared(monkeypatch):
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: c != "mushmush")
    assert tier_cleared(make_state(level=30), _gd(), 10, None) is False


def test_an_unwinnable_boss_does_not_block_the_rung(monkeypatch):
    """king_slime sits in band(10) and is a boss. Live, it blocked a level-30
    character out of the level-15 rung forever."""
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: c != "king_slime")
    assert tier_cleared(make_state(level=30), _gd(), 10, None) is True


def test_next_uncleared_is_the_lowest_rung_with_an_unwinnable_normal(monkeypatch):
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: c != "spider")
    assert next_uncleared_tier(make_state(level=30), _gd(), None) == 20


def test_next_uncleared_is_none_when_everything_is_winnable(monkeypatch):
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: True)
    assert next_uncleared_tier(make_state(level=30), _gd(), None) is None


def test_gear_target_is_the_rung_being_cleared_not_the_character_level(monkeypatch):
    """Robby's live case: level 30 with the level-20 rung uncleared. Targeting
    T30 gear demands materials from monsters he cannot beat; T20 gear crafts
    from content he has already cleared."""
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: c != "spider")
    assert gear_target_tier(make_state(level=30), _gd(), None) == 20


def test_gear_target_is_capped_by_character_level(monkeypatch):
    """A level-5 character clearing the level-20 rung still cannot wear T20."""
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: c != "spider")
    assert gear_target_tier(make_state(level=5), _gd(), None) == 1


def test_gear_target_with_nothing_left_to_clear_is_the_level_rung(monkeypatch):
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: True)
    assert gear_target_tier(make_state(level=30), _gd(), None) == 20
