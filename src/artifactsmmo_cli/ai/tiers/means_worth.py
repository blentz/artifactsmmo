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


def _task_skills(task_code: str | None, game_data: GameData) -> set[str]:
    """ALL skills the task exercises: its item's crafting_skill (if any) plus the
    gathering skills in its production chain. Returning the full set — not just
    one — lets a need on any of them count the task as serving (a mixed-recipe
    task must not be mis-gated because the needed skill is not first alphabetically)."""
    if not task_code:
        return set()
    skills: set[str] = set()
    stats = game_data.item_stats(task_code)
    if stats is not None and stats.crafting_skill:
        skills.add(stats.crafting_skill)
    skills |= game_data.active_gathering_skills(task_code)
    return skills


def means_serves(kind: MeansKind, goal: Goal | None, needs: NeedSet,
                 state: WorldState, game_data: GameData) -> bool:
    """True if this means is worth pursuing toward the committed objective."""
    if kind not in _TASK_KINDS:
        return True
    if needs.is_empty:
        return True
    # A monsters-task is combat — the only source of character XP — so it serves
    # a char-level objective. Items-tasks award no char XP and never serve it.
    if needs.char_xp and state.task_type == "monsters":
        return True
    if _task_skills(state.task_code, game_data) & needs.skill_xp:
        return True
    if state.task_code is not None and state.task_code in needs.materials:
        return True
    return bool(needs.buy_only)
