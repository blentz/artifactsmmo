"""Differential: the production link `GearTierLeveling.ObjectiveCoversBand` (ruling C4-R).

The Lean hypothesis: where a winnable, XP-positive monster under the suicide
guard exists, production's gear objective exists, is well formed (`held` exactly
when nothing is missing) and its `m*` is such a monster.

Production's own words for each part, all live functions:

* "a winnable candidate exists" — some `gear_objective._candidates` monster (the
  level ceiling `FIGHT_LEVEL_GAP_CEILING`, positive XP, a reachable spawn, not
  party-only) whose `L*` fighter wins (`drop_fight_winnable`, the gate `_rated`
  applies);
* "production's objective" — `gear_objective`, and the context
  `attach_gear_objective` builds from it;
* "`m*` is such a monster" — `objective.monster` is one of those winning
  candidates.

Both polarities are required: every bundle scenario (plain and with its `L*`
carried) has a winning candidate and must have an objective whose `m*` is one;
and a character with no candidate that wins (level 41, nothing worn, nothing
held, as `test_gear_objective` builds it) must have no objective. The negative
pole is also the converse the hypothesis does not claim but production keeps:
no winning candidate, no objective.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest

import artifactsmmo_cli.ai.gear_objective as go
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective import gear_objective
from artifactsmmo_cli.ai.obtain_model.drop_routes import drop_fight_winnable
from artifactsmmo_cli.ai.scenario import SCENARIOS, ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.world_state import WorldState
from formal.diff.test_gear_objective_arming_diff import BUNDLE
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT
from tests.test_ai.shared_world import attached, shared_world

CTX = TIMED_NO_PROFILE_CONTEXT


def _winning_candidates(state: WorldState, gd: GameData) -> list[str]:
    """`_candidates` whose `L*` fighter wins, as `gear_objective` reads them."""
    depth, _food, _loop = go._inputs(state, gd, CTX, None)
    targets = go._targets(state, gd, frozenset(depth))
    return [code for code in go._candidates(state, gd)
            if drop_fight_winnable(targets[code][0], gd, code)]


def _carrying(state: WorldState, gd: GameData) -> WorldState:
    objective = gear_objective(state, gd, CTX, None)
    if objective is None:
        return state
    bag = Counter(state.inventory)
    bag.update(piece.code for piece in objective.missing)
    return replace(state, inventory=dict(bag))


def _states() -> list[tuple[str, bool]]:
    return [(name, carried) for name in sorted(SCENARIOS) for carried in (False, True)]


@pytest.mark.parametrize(("name", "carried"), _states())
def test_a_winning_candidate_gives_an_objective_on_one(name: str, carried: bool) -> None:
    """The positive pole, at every bundle state."""
    gd = shared_world(BUNDLE)
    state = scenario_state(SCENARIOS[name], gd)
    if carried:
        state = _carrying(state, gd)
    winning = _winning_candidates(state, gd)
    assert winning, (name, carried, "every bundle state has a winning candidate")
    objective = gear_objective(state, gd, CTX, None)
    assert objective is not None, (name, carried)
    assert objective.monster in winning, (name, carried, objective.monster, winning)
    # WellFormed: held exactly when nothing is missing.
    assert objective.held == (not objective.missing), (name, carried)
    # The context the cycle builds carries the same objective.
    assert attached(state, gd, CTX, None).gear_objective == objective


def test_no_winning_candidate_gives_no_objective() -> None:
    """The negative pole: level 41, nothing worn and nothing held — no candidate
    wins on any achievable fighter, and production names no objective."""
    gd = shared_world(BUNDLE)
    state = scenario_state(ScenarioCharacter(name="novice", level=41, derive_combat_stats=True,
                                             equipment={}, inventory={}), gd)
    assert _winning_candidates(state, gd) == []
    assert gear_objective(state, gd, CTX, None) is None
    assert attached(state, gd, CTX, None).gear_objective is None
