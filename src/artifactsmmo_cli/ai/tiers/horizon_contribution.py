"""What a course of action is WORTH, on the objective's own scale.

S-016 says an available means and the objective step are compared on marginal
cycles against cycles saved over the horizon, and that neither wins by the band it
occupies. Increment 0 of `docs/PLAN_band_unification.md` measured that only ONE
side of that comparison exists: the step's COST is priced (`acquisition_actions`)
and its BENEFIT is not. Nothing anywhere answers "how many cycles closer to the
horizon does doing this leave me".

The answer was already half-built and private. `branch_objective._outcome` runs one
`cheapest_path_to_level` walk and returns `(reachable_level, cycles_to_target)` —
that IS the cycles-to-horizon of a state. `J` then reads it for a gear candidate's
POST-acquisition state, which makes `J` a difference already: the trunk is the same
walk on the unchanged state, and a gear root beats the trunk exactly when it saves
more cycles than it costs.

So the benefit of ANY change is one subtraction between two walks, and this module
names it. Two consequences worth stating, because they are what make the band epic
tractable:

* A MEANS gets a benefit the same way a gear root does. Its post-state is its PLAN
  applied — the arbiter already builds that plan to decide whether the candidate is
  plannable at all — so no means needs a bespoke projection, and adding a means
  later costs nothing here.
* The figure is a DIFFERENCE, so the shared baseline cancels. Comparing two courses
  by contribution is the same ordering as comparing them by `J`, which is why this
  does not introduce a second objective alongside the one S-006 already fixed.

UNREACHABLE IS `None`, NEVER ZERO. A blocked walk means the horizon cannot be
reached from that state at all, and `_outcome` fills its cycles with 0 for exactly
the band where `J` never reads them. Reading that 0 here would report "this change
saves nothing" for a state that cannot finish, which is the sentinel confusion
S-042 exists to forbid — what the objective cannot price is reported on the other
scale, never as a number that means something else.
"""

from collections.abc import Iterable
from math import ceil

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.progression_choice import TARGET_LEVEL
from artifactsmmo_cli.ai.world_state import WorldState


def horizon_outcome(state: WorldState, store: LearningStore, game_data: GameData,
                    target: int = TARGET_LEVEL) -> tuple[int, int | None]:
    """`(reachable_level, cycles_to_target)` from ONE `cheapest_path_to_level`
    walk, with the cycles None when the walk is blocked.

    THE SINGLE WALK, and the reason this returns a pair nobody wants whole.
    `branch_objective._outcome` needs both halves and `cycles_to_horizon` needs
    one, and the walk is the expensive thing in the whole ranking — a live ranking
    was measured at 33.9 seconds. Two entry points that each ran their own would
    double that, so the walk happens here and both callers read the result.

    Rounded UP: a fractional cycle is still an action the character has to spend,
    and the objective is an integer one (S-013).
    """
    plan = cheapest_path_to_level(target, state, store, game_data)
    reachable_level = state.level + len(plan.segments)
    return reachable_level, None if plan.blocked else ceil(plan.total_cycles)


def cycles_to_horizon(state: WorldState, store: LearningStore,
                      game_data: GameData,
                      target: int = TARGET_LEVEL) -> int | None:
    """Projected actions from `state` to `target`, or None when it cannot be
    reached — the half a caller with no candidate to hang it on needs."""
    return horizon_outcome(state, store, game_data, target)[1]


def contribution(before: WorldState, after: WorldState, store: LearningStore,
                 game_data: GameData,
                 target: int = TARGET_LEVEL) -> int | None:
    """Cycles to the horizon that the change from `before` to `after` REMOVES.

    Positive means the change leaves the character closer to the horizon; negative
    means it leaves them further away, which is a real answer and not an error — a
    course that spends a material the objective needed does set progress back.

    None whenever either side is unreachable, and the two unreachable cases are
    deliberately NOT distinguished here. A change that opens a blocked horizon is
    worth more than any number this function could return, and a change that closes
    one is worse than any; collapsing both to "not on this scale" hands that
    judgement to the caller instead of inventing a magnitude for it. That is the
    same discipline S-042 applies to a candidate the objective cannot price.
    """
    start = cycles_to_horizon(before, store, game_data, target)
    end = cycles_to_horizon(after, store, game_data, target)
    if start is None or end is None:
        return None
    return start - end


def project(state: WorldState, plan: Iterable[Action],
            game_data: GameData) -> WorldState:
    """The state a plan leaves behind, by applying its actions in order.

    THE POST-STATE OF A MEANS, and the reason this module needs no per-means
    knowledge. Every `Action.apply` is the planner's own model of that action's
    effect — the same model the search used to find the plan — so folding it over
    the plan asks the means what it does using the answer it already gave.

    An action whose `apply` asserts its precondition will raise here on a plan that
    was not built for this state. That is intended: a caller who hands over a plan
    from a different state has a bug, and a silently skipped action would price the
    course as cheaper than it is.
    """
    for action in plan:
        state = action.apply(state, game_data)
    return state


def plan_contribution(state: WorldState, plan: Iterable[Action],
                      store: LearningStore, game_data: GameData,
                      target: int = TARGET_LEVEL) -> int | None:
    """`contribution` from `state` to the state `plan` leaves behind.

    The one call a caller comparing courses needs: give it the plan the arbiter
    already built for a candidate and it answers what that candidate is worth,
    whether the candidate is an objective step or a discretionary means.
    """
    return contribution(state, project(state, plan, game_data), store, game_data,
                        target)
