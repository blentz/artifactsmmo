"""The roots the walk offers a scenario, driven as a live cycle is.

Was `audit/open_rung_completeness.routed_skills`, deleted with that audit
(ruling X); the scenario suites that still ask the question keep it here. The
walk's context carries the cycle's gear objective, attached by the one
function the player uses (`gear_objective_context.attach_gear_objective`).

The objective costs about a second per scenario, and three suites sweep every
catalogued scenario, so a scenario's resolution is computed once per process.
The cache entry holds the `GameData` it was computed on and is used only for
that same object (an `id()` key alone would be reused by a new object)."""

from artifactsmmo_cli.ai.decisions.root import RootResolution, resolve_root
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective_context import attach_gear_objective
from artifactsmmo_cli.ai.scenario import SCENARIOS, derived_scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState

_RESOLVED: dict[str, tuple[GameData, RootResolution]] = {}


def resolution_of(state: WorldState, game_data: GameData) -> RootResolution:
    """The walk over `state` with its cycle's gear objective attached.
    Offline and deterministic: `history=None`."""
    ctx = attach_gear_objective(state, game_data, NO_PROFILE_CONTEXT, None)
    return resolve_root(state, game_data, CharacterObjective.from_game_data(game_data),
                        ctx, None)


def scenario_resolution(name: str, game_data: GameData) -> RootResolution:
    """`resolution_of` the catalogued scenario `name` (derived combat stats)."""
    cached = _RESOLVED.get(name)
    if cached is not None and cached[0] is game_data:
        return cached[1]
    resolution = resolution_of(derived_scenario_state(SCENARIOS[name], game_data), game_data)
    _RESOLVED[name] = (game_data, resolution)
    return resolution


def skills_offered(resolution: RootResolution) -> frozenset[str]:
    """The skills of every `ReachSkillLevel` the walk offers: the root AND the
    ordered alternatives, because `strategy_driver._resolve_step_goal` walks
    the alternatives whenever the root's step goal comes back None."""
    return frozenset(goal.skill for goal in (resolution.root, *resolution.alternatives)
                     if isinstance(goal, ReachSkillLevel))
