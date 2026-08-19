"""What a course is worth, on the objective's own scale.

The module under test supplies the half of S-016 that increment 0 measured as
missing: a step's COST was priced and its BENEFIT was not. These tests pin the
three things that make the figure usable — that it is one walk, that unreachable
is None rather than a number, and that a means' post-state comes from applying its
own plan.
"""

from dataclasses import replace

import pytest

from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.tiers.branch_objective import _outcome
from artifactsmmo_cli.ai.tiers.horizon_contribution import (
    contribution,
    cycles_to_horizon,
    horizon_outcome,
    plan_contribution,
    project,
)
from tests.test_ai.test_acquisition_cost_wrapper import _BUNDLE


@pytest.fixture
def game_data():
    return load_bundle_game_data(_BUNDLE)


@pytest.fixture
def store():
    return LearningStore(db_path=":memory:", character="probe")


@pytest.fixture
def state(game_data):
    return scenario_state(SCENARIOS["l12_deep_chain_grind"], game_data)


def test_a_reachable_state_has_a_positive_figure(state, store, game_data):
    cycles = cycles_to_horizon(state, store, game_data, target=state.level + 1)
    assert cycles is not None and cycles > 0


def test_the_horizon_is_further_from_a_lower_level(state, store, game_data):
    """Sanity that the figure MEASURES something: the same character one level
    down needs more cycles to reach the same target."""
    target = state.level + 2
    near = cycles_to_horizon(state, store, game_data, target)
    far = cycles_to_horizon(replace(state, level=state.level - 1, xp=0),
                            store, game_data, target)
    assert near is not None and far is not None
    assert far > near


def test_an_unreachable_horizon_is_none_and_not_zero(state, store, game_data):
    """The distinction the whole module rests on. Level 50 is out of reach for
    this character, and a 0 would read as "already there" — the sentinel
    confusion S-042 forbids."""
    assert cycles_to_horizon(state, store, game_data, target=50) is None


def test_outcome_and_horizon_outcome_agree_on_the_reachable_level(
        state, store, game_data):
    """One walk, one answer. `branch_objective._outcome` delegates here, so a
    drift between them would put `J` and the worth of a course on different
    scales — the exact defect S-016 is about."""
    target = state.level + 1
    level, cycles = horizon_outcome(state, store, game_data, target)
    o_level, o_cycles = _outcome(state, store, game_data, target)
    assert (level, cycles) == (o_level, o_cycles)


def test_outcome_fills_an_unreachable_walk_with_zero_and_this_module_does_not(
        state, store, game_data):
    """The 0 filler lives in `_outcome`, where the band that ignores it lives.
    Reading it here would be a claim that reaching the horizon is free."""
    _level, filled = _outcome(state, store, game_data, target=50)
    assert filled == 0
    assert horizon_outcome(state, store, game_data, target=50)[1] is None


def test_contribution_of_no_change_is_zero(state, store, game_data):
    assert contribution(state, state, store, game_data,
                        target=state.level + 1) == 0


def test_contribution_is_positive_for_a_state_nearer_the_horizon(
        state, store, game_data):
    """XP already earned is progress the walk does not have to repeat."""
    target = state.level + 2
    ahead = replace(state, level=state.level + 1, xp=0)
    worth = contribution(state, ahead, store, game_data, target)
    assert worth is not None and worth > 0


def test_contribution_is_negative_when_the_change_sets_progress_back(
        state, store, game_data):
    """A real answer, not an error: a course that costs progress is worth less
    than nothing and the caller has to see that rather than a clamped zero."""
    target = state.level + 2
    behind = replace(state, level=state.level - 1, xp=0)
    worth = contribution(state, behind, store, game_data, target)
    assert worth is not None and worth < 0


def test_contribution_is_none_when_either_side_is_unreachable(
        state, store, game_data):
    """Both directions collapse to None on purpose. Opening a blocked horizon is
    worth more than any number this can return and closing one is worse, so the
    magnitude is the caller's judgement to make, not this function's."""
    assert contribution(state, state, store, game_data, target=50) is None


class _Bump:
    """A stand-in action whose `apply` is the only thing under test here."""

    def __init__(self, levels: int) -> None:
        self._levels = levels

    def apply(self, state, game_data):
        return replace(state, level=state.level + self._levels, xp=0)


def test_project_folds_the_plan_in_order(state, game_data):
    assert project(state, [_Bump(1), _Bump(2)], game_data).level == state.level + 3


def test_project_of_an_empty_plan_is_the_state_itself(state, game_data):
    assert project(state, [], game_data) is state


def test_plan_contribution_prices_the_state_the_plan_leaves_behind(
        state, store, game_data):
    """The one call a caller comparing courses needs — and it must agree with
    doing the two steps by hand, or a means and a step would be priced by
    different routes to the same number."""
    target = state.level + 3
    plan = [_Bump(1)]
    assert plan_contribution(state, plan, store, game_data, target) == \
        contribution(state, project(state, plan, game_data), store, game_data,
                     target)
