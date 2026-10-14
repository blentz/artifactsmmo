"""Whether the held items task pays enough to defer the level step (spec
2026-10-14 items-task-pays §2, USER "Price it by useful XP").

A task pays when `task_worth` says its gold or drops are worth having (today's
verdicts), or when it pays skill XP the goal-action DAG demands FASTER than the
grind pays character XP. The task's rate is learned (`LearningStore.
task_work_xp_per_second`, this character's work first, then the fleet's); the
grind's is the modelled loop the loadout chooser ranks by (`best_loadout`).
With no learned rate the XP verdict alone decides: a task never worked is
worked once and measured, so the price cannot forbid its own evidence."""

from fractions import Fraction

from artifactsmmo_cli.ai.best_loadout import best_loadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.task_worth import task_worth_for
from artifactsmmo_cli.ai.world_state import WorldState


def held_task_pays(state: WorldState, game_data: GameData, ctx: SelectionContext,
                   monster: str, history: LearningStore | None) -> bool:
    """Whether the held task (`state.task_code`, which must be set) pays
    enough to defer a grind against `monster`."""
    assert state.task_code is not None
    worth = task_worth_for(state.task_code, state.task_type,
                           state.task_total - state.task_progress,
                           state, game_data, ctx, history)
    if worth.gold or worth.drops:
        return True
    if not worth.xp:
        return False
    rate = _task_rate(state.task_code, ctx.skill_demand, history)
    if rate is None:
        return True
    grind = best_loadout(state, game_data, ctx, monster, history).rate.xp_per_second
    return Fraction(rate) > grind


def _task_rate(code: str, skills: frozenset[str],
               history: LearningStore | None) -> float | None:
    """The task's demanded skill XP per second: this character's, else the
    fleet's; None without a store or any work on record."""
    if history is None:
        return None
    own = history.task_work_xp_per_second(code, skills)
    return own if own is not None else history.fleet_task_work_xp_per_second(code, skills)
