"""The shared world's mutation guard (ruling AG): a test that changes the
process-wide bundle `GameData` is caught at the next hand-out, while the
lazy memos filling in and the per-cycle overlay do not trip it."""

from pathlib import Path

import pytest

from tests.test_ai.shared_world import shared_world

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"


def test_a_rebound_catalogue_dict_is_caught_at_the_next_hand_out():
    world = shared_world(BUNDLE)
    original = world.items.stats
    world.items.stats = dict(original)
    try:
        with pytest.raises(AssertionError, match=r"items\.stats"):
            shared_world(BUNDLE)
    finally:
        world.items.stats = original
    assert shared_world(BUNDLE) is world


def test_an_in_place_add_is_caught_at_the_next_hand_out():
    world = shared_world(BUNDLE)
    world.monsters.levels["ag_probe_monster"] = 1
    try:
        with pytest.raises(AssertionError, match=r"monsters\.levels"):
            shared_world(BUNDLE)
    finally:
        del world.monsters.levels["ag_probe_monster"]
    assert shared_world(BUNDLE) is world


def test_overlay_and_lazy_memos_do_not_trip_the_guard():
    world = shared_world(BUNDLE)
    world.active_event_codes = {"ag_probe_event"}
    world.active_raid_codes = {"ag_probe_raid"}
    world.reserved_targets_memo[("ag_probe",)] = {}
    world.world._region_cache[(0, 0, "overworld")] = "ag_probe"
    try:
        again = shared_world(BUNDLE)
    finally:
        del world.reserved_targets_memo[("ag_probe",)]
        del world.world._region_cache[(0, 0, "overworld")]
    assert again is world
    assert again.active_event_codes == set()
    assert again.active_raid_codes == set()
