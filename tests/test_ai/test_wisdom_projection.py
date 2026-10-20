"""Wisdom reaches the level projection (unified-acquisition increment 3).

This file used to open with a characterisation of `ai/min_plan_length`, the
three-action cost model that priced any recipe-less item as one gather. That
model and its tests were retired with the `is_plannable` gate it served (Phase
3-2 of docs/PLAN_decision_architecture_redesign.md); the two wisdom tests below
never depended on it and stay.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.equipment.loadout_cache import pick_loadout_cached
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.gear_value_core import Rank
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state

TIMING = committed_timing()[0]
"""The committed live capture's fight-seconds fit (spec 2026-10-18 §2.9)."""

_BUNDLE = (Path(__file__).resolve().parent / "scenarios" / "fixtures"
           / "gamedata_bundle.json")


@pytest.fixture(scope="module")
def game_data():  # type: ignore[no-untyped-def]
    return load_bundle_game_data(_BUNDLE)


def test_a_wisdom_ITEM_NOW_REACHES_THE_PROJECTION(game_data) -> None:
    """INCREMENT 3, and a CORRECTION to how it was first demonstrated.

    The original version of this test used `wisdom_amulet` and concluded that
    its wisdom 60 projected as zero because `ProjectedStats` had no `wisdom`
    field. The code claim was true — `cheapest_path_to_level` read
    `state.wisdom`, the total for gear already WORN — but the DEMONSTRATION was
    confounded: `wisdom_amulet` carries `conditions [('level', 14)]` and the
    scenario character is level 12, so `pick_loadout_cached` correctly refused to
    wear it. It would have projected zero whatever `ProjectedStats` contained.

    A measurement that cannot distinguish two explanations is not evidence for
    either. This version uses `adventurer_vest` — level 10, wisdom 20, actually
    wearable — so the only thing under test is whether the stat reaches the
    projection.

    Before increment 3 this was 0. It is now 20.

    RE-DERIVED 2026-10-18 (ruling R): the scenario's sheet now carries its
    worn gear's wisdom too (`copper_boots`, 10), so the projection reads the
    worn 10 plus the vest's 20 (it replaces copper_armor, which has none)."""
    state = scenario_state(SCENARIOS["l12_deep_chain_grind"], game_data)
    vest = game_data.item_stats("adventurer_vest")
    assert vest.wisdom == 20
    assert vest.level <= state.level, "fixture drift: the vest must be wearable"

    holding = replace(state, inventory={**state.inventory, "adventurer_vest": 1},
                      hp=state.max_hp)
    projected = project_loadout_stats(
        holding, pick_loadout_cached(Rank(), holding, game_data), game_data)
    assert state.wisdom == 10
    assert projected.wisdom == 30


def test_wisdom_makes_a_COMPLETING_walk_cheaper(game_data) -> None:
    """The payoff, in the only band where `J` can see it.

    Below the top band every candidate is UNREACHABLE and S-006 ranks by
    furthest progress, then cost — the `J` sum never consults `cycles_to_fifty`
    there, so a wisdom item changes the ranking by nothing however well it is
    projected. That is a real limit of the projection (it models no acquisitions
    along the way), not of this increment, and it is why the level-12 scenario
    shows `reach=17` with and without the vest.

    Given a walk that COMPLETES, wisdom pays: 236.71 cycles -> 231.30.

    WHY LEVEL 12, AND WHAT THIS FIXTURE DEPENDS ON. The vest's `wisdom = 20`
    is a 2% factor on the award, so it only changes anything where 2% survives
    the formula's integer rounding. At char 12 it does, on exactly the monster
    that matters: `blue_slime` (L6) pays 10 without the vest and 11 with it. The
    walk ranks by xp-per-cycle, so that single point flips the SELECTION —

        bare:  red_slime   12 xp / 2.8405 cyc = 4.2246/cyc   <- wins
               blue_slime  10 xp / 2.5430 cyc = 3.9323/cyc
        wise:  red_slime   12 xp / 2.8405 cyc = 4.2246/cyc
               blue_slime  11 xp / 2.5430 cyc = 4.3256/cyc   <- wins

    — and `cycles_per_kill` is IDENTICAL in both arms for both monsters, so
    here the improvement is attributable to the wisdom bonus and to nothing
    else. (The vest also carries dmg and hp, which can move
    `rest_actions_per_fight` and the fight's learned seconds; at this pairing
    they move neither.) The level moved from 14 to 12 with spec 2026-10-18
    §2.9: a fight's rests are priced in fights of its own learned length, and
    at 14 `blue_slime` now wins in both arms, so the vest flips nothing there.

    THE PRECONDITIONS BELOW ARE LOAD-BEARING, NOT DECORATION. This test spent
    an earlier life at char 16 asserting the same direction while quietly
    exercising nothing: the walk picked the same monster in both arms and the
    only remaining difference was the cost `equip_cost` charges to put the
    vest on. If a future change makes the selected monster's award
    wisdom-insensitive again, or stops the vest flipping the selection, the
    preconditions fail LOUDLY
    instead of the direction assertion passing for an unrelated reason."""
    # PRECONDITION: the vest's +20 wisdom must actually move the award of the
    # monster the wise arm selects, or this fixture is not testing wisdom.
    assert game_data.xp_per_kill("blue_slime", 12, wisdom=10) == 10
    assert game_data.xp_per_kill("blue_slime", 12, wisdom=30) == 11
    state = scenario_state(SCENARIOS["l12_deep_chain_grind"], game_data)
    store = LearningStore(db_path=":memory:", character="wisdom_probe")
    store.start_session()
    try:
        near = replace(state, level=12, xp=0, max_xp=1000, inventory={})
        bare = cheapest_path_to_level(13, near, store, game_data, TIMING)
        wise = cheapest_path_to_level(
            13, replace(near, inventory={"adventurer_vest": 1}), store, game_data, TIMING)
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    assert not bare.blocked and not wise.blocked
    # PRECONDITION: the wisdom bonus is what flipped the selection, and it did
    # so without moving the fight loop — same cycles_per_kill on both sides.
    assert bare.segments[0].monster_code == "red_slime"
    assert wise.segments[0].monster_code == "blue_slime"
    assert bare.segments[0].cycles_per_kill == pytest.approx(2.8404746, rel=1e-6)
    assert wise.segments[0].cycles_per_kill == pytest.approx(2.5430241, rel=1e-6)
    assert bare.total_cycles == pytest.approx(236.706215, rel=1e-6)
    assert wise.total_cycles == pytest.approx(231.295557, rel=1e-6)
    assert wise.total_cycles < bare.total_cycles
