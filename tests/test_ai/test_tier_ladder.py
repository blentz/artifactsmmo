"""The tier ladder is DERIVED from item levels, never hardcoded, and its
monster bands partition the whole monster table."""
import itertools

import pytest

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.tier_ladder import (
    band,
    ladder,
    normal_band,
    tier_of_level,
)


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon"),
        "battlestaff": ItemStats(code="battlestaff", level=20, type_="weapon"),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
    }
    gd._monster_level = {"chicken": 1, "mushmush": 10, "skeleton": 18,
                         "spider": 20, "king_slime": 15}
    gd._monster_type = {"chicken": "normal", "mushmush": "normal",
                        "skeleton": "normal", "spider": "normal",
                        "king_slime": "boss"}
    return gd


def test_ladder_is_the_distinct_equippable_levels():
    assert ladder(_gd()) == (1, 10, 20)


def test_ladder_ignores_non_equippable_items():
    """ash_plank is level 1 but is a resource, not gear — it must not create
    or confirm a rung on its own."""
    gd = _gd()
    gd._item_stats = {"ash_plank": ItemStats(code="ash_plank", level=7,
                                             type_="resource")}
    assert ladder(gd) == ()


def test_tier_of_level_floors_to_the_rung():
    gd = _gd()
    assert tier_of_level(gd, 1) == 1
    assert tier_of_level(gd, 9) == 1
    assert tier_of_level(gd, 10) == 10
    assert tier_of_level(gd, 25) == 20


def test_tier_of_level_below_the_first_rung_is_the_first_rung():
    assert tier_of_level(_gd(), 0) == 1


def test_tier_of_level_raises_on_empty_ladder():
    """When no equippable items exist, tier_of_level must raise ValueError."""
    gd = GameData()
    gd._item_stats = {"ash_plank": ItemStats(code="ash_plank", level=7,
                                             type_="resource")}
    gd._monster_level = {}
    gd._monster_type = {}
    with pytest.raises(ValueError, match="no equippable items"):
        tier_of_level(gd, 1)


def test_band_holds_monsters_from_the_rung_up_to_the_next():
    gd = _gd()
    assert band(gd, 1) == ("chicken",)
    assert band(gd, 10) == ("king_slime", "mushmush", "skeleton")
    assert band(gd, 20) == ("spider",)


def test_normal_band_drops_boss_elite_and_raid_boss():
    """king_slime is a level-15 boss with 1000 hp and 20 resist on every
    element; leaving it in band(10) would stall that rung forever."""
    assert normal_band(_gd(), 10) == ("mushmush", "skeleton")


def test_the_bands_partition_every_monster_exactly_once():
    gd = _gd()
    seen = [code for tier in ladder(gd) for code in band(gd, tier)]
    assert sorted(seen) == sorted(gd.monster_levels)
    assert len(seen) == len(set(seen))


def test_the_live_catalogue_partitions_without_gaps(bundle_game_data):
    """Census: against the committed game-data bundle every monster is binned
    exactly once and no band is empty. This is the check that would have caught
    `cheapest_path_to_level`'s floor of 1 — a band with no lower edge."""
    gd = bundle_game_data
    rungs = ladder(gd)
    assert rungs, "ladder must be non-empty"
    assert rungs == tuple(sorted(set(rungs))), "ladder must be ascending and distinct"
    binned = [code for tier in rungs for code in band(gd, tier)]
    assert sorted(binned) == sorted(gd.monster_levels), "every monster binned once"
    assert len(binned) == len(set(binned)), "no monster in two bands"
    for tier in rungs:
        assert band(gd, tier), f"band T{tier} is empty"


def test_the_live_ladder_is_not_the_audit_ten_level_banding(bundle_game_data):
    """Pins the distinction from `audit/content_tiers.py`, so a later reader
    cannot 'unify' them by accident. The derived ladder is uneven."""
    rungs = ladder(bundle_game_data)
    steps = {b - a for a, b in itertools.pairwise(rungs)}
    assert steps != {10}, "derived ladder must not be a uniform 10-level banding"
