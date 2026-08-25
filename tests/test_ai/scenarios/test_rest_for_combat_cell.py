"""REST_FOR_COMBAT — coverage-matrix cell 10.

`RestoreHP` is 24.1 % of live cycles and 44.2 % of them sit in the 50-99 % HP
band, and yet `REST_FOR_COMBAT` fired in 0 of 36 scenarios: 29 of 30 were at
full HP and the one that was not was already below `CRITICAL_HP_FRACTION`,
where `HP_CRITICAL` preempts.

**A design correction, recorded rather than papered over.** The design measured
this guard at 0/30 with `active_guards(state, gd, None, NO_PROFILE_CONTEXT)`,
and that context has `combat_monster=None` — the guard's FIRST conjunct. Under
that context it can never fire whatever the character's HP is, so the 0/30 was
partly a property of the measuring instrument. The guard IS reachable: the real
`SelectionContext` the player binds in `plan_from_state` carries
`_winnable_farm_target()`, and this cell fires the guard through it.
`test_the_census_context_can_never_see_this_guard` pins that difference so it
cannot be rediscovered by accident.

The four conjuncts make this a MARGINAL fight, not a scratch: a target must be
selected, HP must be below max, the fight must be LOST at current HP and WON at
max. Measured at this loadout the guard's band is 75-85 % of a 435 max, so 348
(exactly 0.80) sits in the middle of it rather than on an edge.
"""

import dataclasses

import pytest

from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.thresholds import CRITICAL_HP_FRACTION
from artifactsmmo_cli.ai.tiers.guards import GuardKind, active_guards
from artifactsmmo_cli.ai.world_state import WorldState

CELL = "l22_rest_for_combat"
TARGET = "flying_snake"
"""The farm target `_winnable_farm_target()` selects for this loadout — named
so a catalogue or picker change that moves it fails here rather than silently
retargeting the cell at a monster with different margins."""


def _state(game_data: GameData) -> WorldState:
    return scenario_state(SCENARIOS[CELL], game_data)


def _planned(state: WorldState, game_data: GameData):
    """`plan_from_state` AND the context it built, because the guard reads the
    context and the assertion has to be about the same one production used."""
    player = GamePlayer(character=CELL, history=None)
    player.seed_offline(state, game_data)
    report = player.plan_from_state()
    return player, report


@pytest.fixture
def state(bundle_game_data: GameData) -> WorldState:
    return _state(bundle_game_data)


def test_the_hp_band_is_the_one_no_scenario_occupied(
        state: WorldState) -> None:
    """80 % — inside the live 50-99 % bucket and ABOVE the critical rung, which
    is the half of that bucket `HP_CRITICAL` does not already own."""
    assert state.hp < state.max_hp
    assert state.hp_percent >= CRITICAL_HP_FRACTION
    assert state.hp_percent == pytest.approx(0.80, abs=0.005)


def test_the_fight_is_marginal_not_merely_damaged(
        bundle_game_data: GameData, state: WorldState) -> None:
    """Conjuncts (c) and (d): lost at current HP, won at max. Without BOTH the
    guard is answering "this is a gear problem", not "this is an HP problem",
    and the cell would be testing the wrong thing."""
    assert predict_win(state, bundle_game_data, TARGET) is False
    rested = dataclasses.replace(state, hp=state.max_hp)
    assert predict_win(rested, bundle_game_data, TARGET) is True


def test_the_guard_fires_under_the_context_production_builds(
        bundle_game_data: GameData, state: WorldState) -> None:
    """The branch: `_fires(REST_FOR_COMBAT, ...)` reached with a real
    `ctx.combat_monster`, through the context `plan_from_state` binds — and the
    selected goal is the rest, so the flip reaches a DECISION."""
    player, report = _planned(state, bundle_game_data)
    ctx = player._last_ctx
    assert ctx.combat_monster == TARGET
    fired = active_guards(state, bundle_game_data, None, ctx)
    assert GuardKind.REST_FOR_COMBAT in fired
    assert GuardKind.HP_CRITICAL not in fired
    assert repr(report.selected_goal) == "RestoreHP"


def test_the_census_context_can_never_see_this_guard(
        bundle_game_data: GameData, state: WorldState) -> None:
    """The design correction, as a failing-when-false assertion.

    `NO_PROFILE_CONTEXT.combat_monster` is None and that is the guard's first
    conjunct, so the guard-coverage sweep that reported 0/30 could not have
    reported anything else. The day that context gains a combat monster this
    test fails and the sweep's number becomes meaningful — which is the only
    honest way to hold a measurement this one depends on."""
    assert NO_PROFILE_CONTEXT.combat_monster is None
    assert GuardKind.REST_FOR_COMBAT not in active_guards(
        state, bundle_game_data, None, NO_PROFILE_CONTEXT)


def test_resting_to_full_silences_the_guard_and_moves_the_goal(
        bundle_game_data: GameData, state: WorldState) -> None:
    """Proof it bites. ONE field changes — HP to max — and the guard goes
    quiet, the goal stops being RestoreHP and the plan becomes the fight the
    guard was holding back."""
    rested = dataclasses.replace(state, hp=state.max_hp)
    player, report = _planned(rested, bundle_game_data)
    assert player._last_ctx.combat_monster == TARGET
    assert GuardKind.REST_FOR_COMBAT not in active_guards(
        rested, bundle_game_data, None, player._last_ctx)
    assert repr(report.selected_goal) != "RestoreHP"
    assert report.plan and "Fight(" in repr(report.plan[0])


def test_no_other_scenario_reaches_this_guard(
        bundle_game_data: GameData) -> None:
    """The gap the cell closes, measured over the whole set through the SAME
    real-context seam — not through the census context, which cannot see it."""
    holders = set()
    for name in SCENARIOS:
        scenario_gd = bundle_game_data
        scenario_world = scenario_state(SCENARIOS[name], scenario_gd)
        player = GamePlayer(character=name, history=None)
        player.seed_offline(scenario_world, scenario_gd)
        if GuardKind.REST_FOR_COMBAT in active_guards(
                scenario_world, scenario_gd, None,
                player._selection_context(player._winnable_farm_target())):
            holders.add(name)
    assert holders == {CELL}
