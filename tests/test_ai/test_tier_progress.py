"""A rung is cleared when every NORMAL monster in its band is winnable; the gear
target is the rung being cleared, capped by character level."""
import dataclasses

import artifactsmmo_cli.ai.tiers.tier_progress as mod
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
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


def test_bundle_backed_progress_uses_real_combat_prediction(bundle_game_data):
    """I3: every OTHER test in this module monkeypatches `is_winnable`, so
    nothing exercises `tier_progress` against the real combat predictor —
    the asymmetry (`tier_ladder` has bundle census tests; this module had
    none) is what let C1 survive six reviews. `l1_fresh` (level 1, no
    combat stats) cannot clear even tier 1's easiest normal monsters, so its
    rung is stuck at 1; `l10_gearcrafting_gap` (level 10, real derived
    combat stats) has cleared tier 1 and progressed all the way to tier 10,
    the rung its own level caps it at."""
    gd = bundle_game_data
    fresh = scenario_state(SCENARIOS["l1_fresh"], gd)
    geared = scenario_state(SCENARIOS["l10_gearcrafting_gap"], gd)

    assert tier_cleared(fresh, gd, 1, None) is False
    assert next_uncleared_tier(fresh, gd, None) == 1
    assert gear_target_tier(fresh, gd, None) == 1

    assert tier_cleared(geared, gd, 1, None) is True
    assert next_uncleared_tier(geared, gd, None) == 10
    assert gear_target_tier(geared, gd, None) == 10


def test_gear_target_tier_is_independent_of_current_hp(bundle_game_data):
    """C1: route existence must not depend on incidental damage. Controller-
    reproduced against `l10_gearcrafting_gap` (level 10, max_hp 345):
    `gear_target_tier` swung 10 -> 5 -> 5 as hp dropped from 345 to 172 to
    103, because `tier_cleared` asked `is_winnable` at CURRENT hp although
    its module docstring promises restorable hp. Pins that the tier is
    IDENTICAL at full and reduced hp for the same scenario state — this test
    is the fix's whole point and must fail without the `max_hp` replace in
    `tier_cleared`."""
    gd = bundle_game_data
    full_hp = scenario_state(SCENARIOS["l10_gearcrafting_gap"], gd)
    assert full_hp.hp == full_hp.max_hp
    damaged = dataclasses.replace(full_hp, hp=max(1, full_hp.max_hp // 3))
    assert damaged.hp != damaged.max_hp

    tier_full = gear_target_tier(full_hp, gd, None)
    tier_damaged = gear_target_tier(damaged, gd, None)

    assert tier_full == tier_damaged, (
        f"gear_target_tier depends on current hp: {tier_full} at full hp vs "
        f"{tier_damaged} damaged")


def test_gear_target_follows_an_uncleared_lower_band_below_the_level_rung(monkeypatch):
    """The case where min(level_rung, clearing) is load-bearing.

    Level 30 gives level_rung=20, but mushmush (normal, level 10) is unwinnable
    while spider (normal, level 20) is winnable. So clearing=10. The min() must
    return 10, not 20. Exists to kill the `return tier_of_level(...)` mutant."""
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: c != "mushmush")
    assert gear_target_tier(make_state(level=30), _gd(), None) == 10
