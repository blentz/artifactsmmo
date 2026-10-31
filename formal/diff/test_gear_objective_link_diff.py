"""Differential: the production link `GearTierLeveling.ObjectiveCovers` (ruling C4-R2).

The Lean hypothesis, at one state, over production's own predicates and codes:

    (∃ c ∈ cands, fighterWins c ∧ ratePos c) →
      ∃ o, objective = some o ∧ WellFormed o ∧ o.monster ∈ cands ∧
        fighterWins o.monster ∧ ratePos o.monster

Each name is bound here to the live function it abstracts, with real monster codes:

* `cands` — `gear_objective._candidates(state, game_data)`;
* `fighterWins c` — `drop_fight_winnable` on `_targets`' `L*(c)` fighter (the gate
  `_rated` applies);
* `ratePos c` — `R(c) > 0`, with `R` the objective's own rate (`_rate` on the
  `L*(c)` fighter, the XP purpose `xp_rate`), computed for every winning candidate
  (not only those `_rated`'s early stop reaches);
* `objective` — `gear_objective(state, game_data, ctx, None)`, which
  `attach_gear_objective` carries;
* `WellFormed o` — `o.held == (not o.missing)`.

The antecedent is evaluated, not assumed: every bundle state (plain and with its
`L*` carried) is checked, and the sweep must contain states where it holds.
The state where the antecedent FAILS (a naked level-41 character: no winning
candidate) is checked too: the implication holds vacuously there, and production
names no objective — the converse the hypothesis does not claim.

What is NOT bound: that the catalogue's band witness (`WinnableAcrossBand`) makes
the antecedent true at a state. It does not at the naked level-41 character; that
transfer is the named catalogue→`L*` residual of `LevelFiftyReachableP`.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
from fractions import Fraction

import pytest

import artifactsmmo_cli.ai.gear_objective as go
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective import gear_objective
from artifactsmmo_cli.ai.gear_objective_result import GearObjective
from artifactsmmo_cli.ai.obtain_model.drop_routes import drop_fight_winnable
from artifactsmmo_cli.ai.scenario import SCENARIOS, ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.world_state import WorldState
from formal.diff.test_gear_objective_arming_diff import BUNDLE
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT
from tests.test_ai.shared_world import attached, shared_world

CTX = TIMED_NO_PROFILE_CONTEXT


def _predicates(state: WorldState, gd: GameData
                ) -> tuple[list[str], dict[str, bool], dict[str, Fraction]]:
    """`cands`, `fighterWins` and the rates behind `ratePos`, as `gear_objective`
    computes them for this state."""
    depth, food, loop = go._inputs(state, gd, CTX, None)
    targets = go._targets(state, gd, frozenset(depth))
    cands = go._candidates(state, gd)
    wins = {code: drop_fight_winnable(targets[code][0], gd, code) for code in cands}
    rates = {code: go._rate(targets[code][0], gd, code, food, loop, go.xp_rate)
             for code in cands if wins[code]}
    return cands, wins, rates


def _covers(cands: list[str], wins: dict[str, bool], rates: dict[str, Fraction],
            objective: GearObjective | None) -> tuple[bool, bool]:
    """(antecedent, consequent) of `ObjectiveCovers` on production's values."""
    def rate_pos(code: str) -> bool:
        return rates.get(code, Fraction(0)) > 0

    antecedent = any(wins[c] and rate_pos(c) for c in cands)
    consequent = (objective is not None
                  and objective.held == (not objective.missing)
                  and objective.monster in cands
                  and wins[objective.monster] and rate_pos(objective.monster))
    return antecedent, consequent


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
def test_production_satisfies_the_link(name: str, carried: bool) -> None:
    gd = shared_world(BUNDLE)
    state = scenario_state(SCENARIOS[name], gd)
    if carried:
        state = _carrying(state, gd)
    objective = gear_objective(state, gd, CTX, None)
    antecedent, consequent = _covers(*_predicates(state, gd), objective)
    assert (not antecedent) or consequent, (name, carried, objective)
    # The context the cycle builds carries the same objective.
    assert attached(state, gd, CTX, None).gear_objective == objective


def test_the_antecedent_holds_in_the_sweep() -> None:
    """The implication is exercised, not vacuous over the bundle."""
    gd = shared_world(BUNDLE)
    for name in sorted(SCENARIOS):
        state = scenario_state(SCENARIOS[name], gd)
        antecedent, consequent = _covers(*_predicates(state, gd),
                                         gear_objective(state, gd, CTX, None))
        if antecedent:
            assert consequent, name
            return
    pytest.fail("no bundle state has a winning candidate with R > 0")


def test_no_winning_candidate_and_no_objective() -> None:
    """The antecedent fails at a naked level-41 character (no candidate's fighter
    wins); production names no objective there. The band witness still exists at
    level 41 — the catalogue→`L*` transfer the link does not claim."""
    gd = shared_world(BUNDLE)
    state = scenario_state(ScenarioCharacter(name="novice", level=41, derive_combat_stats=True,
                                             equipment={}, inventory={}), gd)
    cands, wins, rates = _predicates(state, gd)
    objective = gear_objective(state, gd, CTX, None)
    antecedent, _ = _covers(cands, wins, rates, objective)
    assert not antecedent
    assert not any(wins.values())
    assert objective is None
    assert attached(state, gd, CTX, None).gear_objective is None
