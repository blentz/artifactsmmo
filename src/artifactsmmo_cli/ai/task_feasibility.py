"""Decide whether the active task is feasible for the character right now.

Returns the gating skill requirement (or None when already feasible). Pure — no
API calls, no learning. Used by TaskCancelGoal, the LevelSkill prerequisite
wiring, and the cost-analysis decision.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState

# A monster more than this many levels above the character is "too hard" — the
# existing TaskCancel rule, kept for parity.
MONSTER_LEVEL_MARGIN = 2


@dataclass(frozen=True)
class SkillRequirement:
    """A skill the character must raise to do the current task.

    For combat tasks `skill == "combat"` and the levels are character levels.
    """

    skill: str
    required_level: int
    current_level: int


def task_requirement(state: WorldState, game_data: GameData) -> SkillRequirement | None:
    """Gating requirement for the active task, or None if already feasible."""
    if not state.task_code or state.task_total == 0:
        return None
    if state.task_type == "monsters":
        monster_level = game_data.monster_level(state.task_code)
        if monster_level > 0 and monster_level > state.level + MONSTER_LEVEL_MARGIN:
            return SkillRequirement("combat", monster_level, state.level)
        return None
    if state.task_type == "items":
        return _item_skill_gap(state.task_code, state, game_data, seen=set())
    return None


def _gap_rank(entry: tuple[SkillRequirement, int]) -> tuple[int, int, int, str]:
    """Total order over (requirement, closure-depth) — the D4 discharge.

    The old aggregation compared `required_level` with a STRICT `>`, so two
    skills tied at the worst required_level were resolved by recipe
    dict-iteration order: `_item_skill_gap` returned a DIFFERENT skill depending
    on ingredient order. The level was already stable (max is commutative), but
    the skill IDENTITY was not — and that identity DRIVES a decision: it becomes
    the `ReachSkillGoal` grind target (strategy_driver) and the skill whose
    XP-curve `task_decision` runs. So an alphabetical tiebreak would pick the
    grind target by skill name — the forbidden repr-sort-as-decision.

    Keys, all order-independent:
      1. `required_level` — PRIMARY, so the reported level is unchanged. That
         level and its None/non-None boundary are the only things the Lean oracle
         (`TaskFeasibility.lean` models `worstLevel` as a max over the unmet
         closure) and the callers depend on.
      2. the absolute gap `required - current` — the harder grind, a semantic
         bottleneck measure.
      3. `-depth` — prefer the OUTERMOST gate (the task's own skill before an
         ingredient's). This is exactly what the old strict-`>` did implicitly:
         the item's own gap was set first and a tied DEEPER gap never replaced
         it. So it is behaviour-preserving on the common root-vs-ingredient tie
         AND semantic — the outermost skill you are blocked on — never a
         name-based ranking.
      4. `skill` name — the last-resort determinism backstop, reached ONLY when
         two DIFFERENT skills tie on level, gap AND depth (same-depth sibling
         ingredients gating different skills at the same level). Those grind
         targets are provably interchangeable — both must be raised to do the
         task — so a stable arbitrary pick cannot make a wrong or livelock
         decision (unlike a name-tiebreak among DISTINGUISHABLE options, which
         is the forbidden pattern). No bundle recipe reaches it today; it exists
         so D4 is FULLY discharged rather than merely on current data.
    """
    req, depth = entry
    return (req.required_level, req.required_level - req.current_level, -depth, req.skill)


def _item_skill_gap(item_code: str, state: WorldState, game_data: GameData,
                    seen: set[str]) -> SkillRequirement | None:
    """Worst unmet crafting-skill gap to produce item_code, recursing into
    craft ingredients. Returns the requirement with the highest required_level
    among unmet skills (ties broken deterministically by `_gap_rank` toward the
    outermost gate), or None if everything is within reach."""
    entry = _worst_gap(item_code, state, game_data, seen, 0)
    return entry[0] if entry is not None else None


def _worst_gap(item_code: str, state: WorldState, game_data: GameData,
               seen: set[str], depth: int) -> tuple[SkillRequirement, int] | None:
    """`_item_skill_gap`'s cycle-safe recursion, carrying the closure DEPTH of
    each gap so `_gap_rank` can prefer the outermost gate deterministically."""
    if item_code in seen:
        return None
    seen.add(item_code)
    worst: tuple[SkillRequirement, int] | None = None
    stats = game_data.item_stats(item_code)
    if stats is not None and stats.crafting_skill:
        current = state.skills.get(stats.crafting_skill, 0)
        if current < stats.crafting_level:
            worst = (SkillRequirement(stats.crafting_skill, stats.crafting_level, current), depth)
    recipe = game_data.crafting_recipe(item_code) or {}
    for ingredient in recipe:
        sub = _worst_gap(ingredient, state, game_data, seen, depth + 1)
        if sub is not None and (worst is None or _gap_rank(sub) > _gap_rank(worst)):
            worst = sub
    return worst
