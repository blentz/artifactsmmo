"""The refusal filter must sit where EVERY action passes, not just factory ones.

The first version of this fix filtered in `GamePlayer._build_actions`, and its
design note claimed that was "the ONLY site, so every action inherits the
feedback path". That was false. A goal's `relevant_actions` may SYNTHESISE
actions rather than select from the list it is handed —
`RecycleSurplusGoal.relevant_actions` builds its own `RecycleAction` objects
from `recyclable_surplus`, and `ai/disposal_route.py` does the same.

Measured consequence: the fleet restarted onto the fixed code at 12:43Z on
2026-08-23 and C3P0 resumed sending `Recycle(water_boost_potion x1)` within
seconds, five times in the first eighty. The filter was real and the action
never passed through it.

`GOAPPlanner.plan` at the `goal.relevant_actions(...)` call is the seam that
actually holds: whoever produced an action, the planner sees it there.
"""

from dataclasses import dataclass, field, replace
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient

from artifactsmmo_cli.ai.action_rejection import rejection_key
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state


@dataclass
class _SynthesisedAction(Action):
    """Stands in for `RecycleAction` as a goal SYNTHESISES it — the shape the
    `_build_actions` filter could never see."""

    tags: ClassVar[frozenset[str]] = frozenset()
    code: str = "water_boost_potion"
    quantity: int = 1

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return True

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        """Moves the character, so the goal below becomes SATISFIABLE by it.

        Load-bearing: if applying changed nothing the goal could never be met,
        the planner would return an empty plan for its own reasons, and
        "the refused action is not in the plan" would hold vacuously whether or
        not the filter ran. The first version of this test did exactly that and
        survived deleting the filter."""
        return replace(state, x=state.x + 1)

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        return 1.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        raise AssertionError("not executed in this test")

    def __repr__(self) -> str:
        return f"Synth({self.code}×{self.quantity})"


@dataclass
class _SynthesisingGoal(Goal):
    """A goal that IGNORES the action list it is given and builds its own —
    exactly `RecycleSurplusGoal.relevant_actions`' shape."""

    synthesised: list[Action] = field(default_factory=list)

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return 1.0

    def is_satisfied(self, state: WorldState) -> bool:
        """Satisfied once a synthesised action has been applied — so a plan
        EXISTS when the filter is off, and vanishes when it is on."""
        return state.x != 0

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        return list(self.synthesised)

    def __repr__(self) -> str:
        return "SynthesisingGoal"


def test_the_planner_filters_a_refused_action_a_goal_synthesised():
    """The regression. The planner is handed an EMPTY action list, so the only
    way the action reaches the search is the goal inventing it — which is how
    C3P0's recycle escaped the `_build_actions` filter."""
    refused = _SynthesisedAction(code="water_boost_potion")
    key = rejection_key(refused)
    assert key is not None

    planner = GOAPPlanner()
    planner.set_refusal_filter(lambda action: rejection_key(action) == key)

    goal = _SynthesisingGoal(synthesised=[refused])
    state = make_state(level=20, x=0)

    # Without the filter the goal IS reachable via the synthesised action, so
    # the empty plan below is caused by the filter and nothing else.
    unfiltered = GOAPPlanner().plan(state, goal, [], GameData())
    assert [repr(a) for a in unfiltered] == [repr(refused)], (
        "precondition: unfiltered, the synthesised action solves this goal")

    plan = planner.plan(state, goal, [], GameData())

    assert plan == [], (
        "a refused action must not survive into the plan, whoever produced it")


def test_an_unfiltered_planner_still_sees_every_synthesised_action():
    """No filter wired = previous behaviour exactly. Every existing caller and
    test must be unaffected, which is why the default is None rather than a
    no-op predicate someone could forget to set."""
    offered = _SynthesisedAction(code="copper_ring")
    planner = GOAPPlanner()

    goal = _SynthesisingGoal(synthesised=[offered])
    relevant = goal.relevant_actions([], make_state(level=20), GameData())

    assert planner._surviving_actions(relevant) == relevant


def test_the_filter_spares_actions_it_does_not_name():
    """Poisoning one item must not disturb its neighbours."""
    refused = _SynthesisedAction(code="water_boost_potion")
    kept = _SynthesisedAction(code="copper_ring")
    key = rejection_key(refused)

    planner = GOAPPlanner()
    planner.set_refusal_filter(lambda action: rejection_key(action) == key)

    assert planner._surviving_actions([refused, kept]) == [kept]
