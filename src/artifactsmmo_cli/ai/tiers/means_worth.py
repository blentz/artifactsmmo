"""The worth gate: does a discretionary means serve the committed objective's
needs? A means that serves no unmet need is a distraction and is suppressed.

Scope: gates PURSUE_TASK / ACCEPT_TASK (the items-task hijackers). All other
means pass through True. See spec Component 3.

Task-output model: an items-task produces (a) the craft/gather skill XP of its
task item, (b) tasks_coin + gold on completion, (c) the task item itself. It
awards NO character XP (verified: all char-XP gain events attribute to Fight).
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.tiers.means import MeansKind
from artifactsmmo_cli.ai.tiers.objective_needs import NeedSet
from artifactsmmo_cli.ai.world_state import WorldState

_TASK_KINDS = frozenset({MeansKind.PURSUE_TASK, MeansKind.ACCEPT_TASK})


def _task_skill(task_code: str | None, game_data: GameData) -> str | None:
    """The craft skill the task exercises (its item's crafting_skill), or the
    first gather skill in its production chain."""
    if not task_code:
        return None
    stats = game_data.item_stats(task_code)
    if stats is not None and stats.crafting_skill:
        return stats.crafting_skill
    gather = game_data.active_gathering_skills(task_code)
    return next(iter(sorted(gather)), None)


def means_serves(kind: MeansKind, goal: Goal | None, needs: NeedSet,
                 state: WorldState, game_data: GameData) -> bool:
    """True if this means is worth pursuing toward the committed objective."""
    if kind not in _TASK_KINDS:
        return True
    if needs.is_empty:
        return True
    skill = _task_skill(state.task_code, game_data)
    if skill is not None and skill in needs.skill_xp:
        return True
    if state.task_code is not None and state.task_code in needs.materials:
        return True
    return bool(needs.buy_only)
