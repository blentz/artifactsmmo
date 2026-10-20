"""The roots the walk offers a scenario, driven as a live cycle is.

Was `audit/open_rung_completeness.routed_skills`, deleted with that audit
(ruling X); the scenario suites that still ask the question keep it here. The
restored census (`audit/skill_climb_completeness`, ruling AK) drives the same
walk for its own routed set. The
walk's context carries the cycle's gear objective, attached by the one
function the player uses (`gear_objective_context.attach_gear_objective`),
through the harness memo `shared_world.attached`.

Three suites sweep every catalogued scenario, so the sweep runs on the one
process-wide bundle world (`shared_world.shared_world`) and each scenario's
resolution is computed once per process (ruling AD)."""

from pathlib import Path

from artifactsmmo_cli.ai.decisions.root import RootResolution, resolve_root
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import SCENARIOS, derived_scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT
from tests.test_ai.shared_world import attached, shared_world

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

_RESOLVED: dict[str, RootResolution] = {}


def resolution_of(state: WorldState, game_data: GameData) -> RootResolution:
    """The walk over `state` with its cycle's gear objective attached.
    Offline and deterministic: `history=None`."""
    return resolve_root(state, game_data, CharacterObjective.from_game_data(game_data),
                        attached(state, game_data, TIMED_NO_PROFILE_CONTEXT, None), None)


def scenario_resolution(name: str) -> RootResolution:
    """`resolution_of` the catalogued scenario `name` (derived combat stats),
    on the shared bundle world, once per process."""
    resolution = _RESOLVED.get(name)
    if resolution is None:
        world = shared_world(BUNDLE)
        resolution = resolution_of(derived_scenario_state(SCENARIOS[name], world), world)
        _RESOLVED[name] = resolution
    return resolution


def skills_offered(resolution: RootResolution) -> frozenset[str]:
    """The skills of every `ReachSkillLevel` the walk offers: the root AND the
    ordered alternatives, because `strategy_driver._resolve_step_goal` walks
    the alternatives whenever the root's step goal comes back None."""
    return frozenset(goal.skill for goal in (resolution.root, *resolution.alternatives)
                     if isinstance(goal, ReachSkillLevel))
