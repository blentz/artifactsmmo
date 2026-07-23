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
from artifactsmmo_cli.ai.tiers.synergy_core import S_MIN, synergy_pure
from artifactsmmo_cli.ai.world_state import WorldState

_TASK_KINDS = frozenset({MeansKind.PURSUE_TASK, MeansKind.ACCEPT_TASK})

#: The task's output kinds — char XP (monsters only), skill XP, the task item,
#: and funding (gold + coins). The denominator of the means<->objective synergy
#: (spec §2.5/§Phase-1: `means_serves` is the boolean special case of the same
#: synergy the tree uses).
_TASK_OUTPUT_KINDS = 4


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


def _task_need_overlap(state: WorldState, needs: NeedSet,
                       game_data: GameData) -> int:
    """How many of the task's output kinds serve a live objective need — the
    numerator of the means<->objective synergy (spec §Phase-1). Each summand is
    one of the original worth clauses; `synergy_pure(overlap, K) > S_MIN` iff
    `overlap > 0`, so thresholding this at S_MIN is exactly the old
    OR-of-clauses, now expressed as the boolean special case of the tree's
    synergy rather than a parallel predicate."""
    serving = 0
    # Char XP: a monsters-task is combat, the only source of character XP, so it
    # serves a char-level objective; items-tasks award none and never do.
    if needs.char_xp and state.task_type == "monsters":
        serving += 1
    # Skill XP of the task's craft/gather chain.
    if _task_skills(state.task_code, game_data) & needs.skill_xp:
        serving += 1
    # The task item itself, if the objective still lacks it as a material.
    if state.task_code is not None and state.task_code in needs.materials:
        serving += 1
    # Gold + task coins fund a buy-only need.
    if needs.buy_only:
        serving += 1
    return serving


def means_serves(kind: MeansKind, goal: Goal | None, needs: NeedSet,
                 state: WorldState, game_data: GameData) -> bool:
    """True if this means is worth pursuing toward the committed objective — the
    boolean special case of the synergy the progression tree uses (spec §2.5):
    the means serves iff its output overlaps a live need at all, i.e. the
    means<->objective synergy clears the S_MIN floor."""
    if kind not in _TASK_KINDS:
        return True
    if needs.is_empty:
        return True
    overlap = _task_need_overlap(state, needs, game_data)
    return synergy_pure(overlap, _TASK_OUTPUT_KINDS) > S_MIN
