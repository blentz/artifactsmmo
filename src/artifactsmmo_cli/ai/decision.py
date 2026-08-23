"""`Decision`: a named branch point in the goal graph.

The meta-decisions this bot makes — can I craft this tier, is there a combat
target, is an items task active — have always existed. They lived as control
flow inside `strategy_driver.objective_step_goal`, a 145-line `if`-pile, where
nothing could name them, test them one at a time, or notice that one of them
pointed at the wrong child. Live 2026-08-22: `Can_I_Craft_Current_Tier`'s "no"
branch routed to "gather the materials anyway" instead of "raise the skill", and
weaponcrafting sat frozen at 10 across the whole fleet for six days.

A `Decision` is never planned. It resolves to a `Goal` (which the unchanged
`GOAPPlanner` solves) or to another `Decision`. The GOAP layer, the `Goal` ABC
and every `Action` are untouched by this type.
"""

from abc import ABC, abstractmethod

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

MAX_RESOLVE_DEPTH = 32
"""Bound on one resolution walk.

Not a tuning knob: the graph is a DAG by construction, because every recursive
edge strictly decreases the lexicographic measure (tier, character level, skill
level, materials outstanding). Exceeding this means a cycle was introduced, which
is a programming error, so it raises rather than truncating.
"""


class Decision(ABC):
    """A named predicate over state that selects a child node."""

    name: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Only check concrete subclasses (those that define resolve).
        # Allow intermediate abstract bases.
        is_concrete = (
            'resolve' in cls.__dict__ and
            (not hasattr(cls, '__abstractmethods__') or 'resolve' not in cls.__abstractmethods__)
        )
        if (is_concrete and
                (not hasattr(cls, 'name') or not isinstance(cls.name, str) or not cls.name)):
            raise TypeError(
                f"{cls.__name__} is a concrete Decision subclass but does not define "
                f"a non-empty class attribute 'name'")

    @abstractmethod
    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision | Goal | None":
        """The child this decision selects for `state`. None = no child."""


Node = Decision | Goal


def resolve_node(node: Node | None, state: WorldState, game_data: GameData,
                 ctx: SelectionContext, history: LearningStore | None
                 ) -> Goal | None:
    """Walk `node` down to the Goal it selects, or None."""
    seen: list[str] = []
    current = node
    for _ in range(MAX_RESOLVE_DEPTH):
        if current is None or isinstance(current, Goal):
            return current
        seen.append(current.name)
        current = current.resolve(state, game_data, ctx, history)
    raise RecursionError(
        f"Decision graph did not terminate in {MAX_RESOLVE_DEPTH} steps; "
        f"walk was {' -> '.join(seen)}")
