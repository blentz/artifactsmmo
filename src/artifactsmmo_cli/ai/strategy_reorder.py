"""Reposition LevelSkill candidates in the arbiter's ordered candidate list per
the skill-gating policy, swapping a gating LevelSkill's unplannable goal for a
plannable craft-one GatherMaterials goal. Pure — unit-tested in isolation from
the planning loop.

Ordering table (see spec 2026-06-08-levelskill-gating-prioritization-design.md):
  TASK_ITEM gate            -> craft-one, immediately BEFORE the PursueTask candidate
  gear/tool/combat, task    -> craft-one, immediately AFTER  the PursueTask candidate
  gear/tool/combat, no task -> craft-one, immediately AFTER  the AcceptTask candidate
  not gating                -> demote unchanged to just before Wait
  gating but no craft target-> LIV-SKILL-2 violation (caller raises)
"""

from collections.abc import Callable

from artifactsmmo_cli.ai.arbiter_select import Candidate
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.tiers.skill_gates import GateSource, SkillGate
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.world_state import WorldState


def _is_pursue(c: Candidate) -> bool:
    return c.repr_.startswith("PursueTask")


def _is_accept(c: Candidate) -> bool:
    return c.repr_ == "AcceptTask"


def _is_wait(c: Candidate) -> bool:
    return c.repr_ == "Wait"


def _insert_before(lst: list[Candidate], bucket: list[Candidate],
                   anchor: Callable[[Candidate], bool],
                   fallback: Callable[[Candidate], bool] | None) -> list[Candidate]:
    if not bucket:
        return lst
    for i, c in enumerate(lst):
        if anchor(c):
            return lst[:i] + bucket + lst[i:]
    if fallback is not None:
        for i, c in enumerate(lst):
            if fallback(c):
                return lst[:i] + bucket + lst[i:]
    return lst + bucket


def _insert_after(lst: list[Candidate], bucket: list[Candidate],
                  anchor: Callable[[Candidate], bool],
                  fallback: Callable[[Candidate], bool] | None) -> list[Candidate]:
    if not bucket:
        return lst
    for i, c in enumerate(lst):
        if anchor(c):
            return lst[:i + 1] + bucket + lst[i + 1:]
    if fallback is not None:
        for i, c in enumerate(lst):
            if fallback(c):
                return lst[:i] + bucket + lst[i:]
    return lst + bucket


def reorder_skill_candidates(
    candidates: list[Candidate],
    gates: dict[str, SkillGate],
    state: WorldState,
    game_data: GameData,
    has_paying_task: bool,
) -> tuple[list[Candidate], list[str]]:
    """Return (reordered_candidates, liveness_violations).

    liveness_violations: gating craft skills with no craftable item at the
    current level (LIV-SKILL-2). The caller raises SkillProgressionError on a
    non-empty list. When there are no LevelSkill candidates, the input list is
    returned unchanged (identity)."""
    skill_idx = [i for i, c in enumerate(candidates)
                 if isinstance(c.goal, LevelSkillGoal)]
    if not skill_idx:
        return candidates, []

    skill_set = set(skill_idx)
    base = [c for i, c in enumerate(candidates) if i not in skill_set]

    before_pursue: list[Candidate] = []
    after_pursue: list[Candidate] = []
    after_accept: list[Candidate] = []
    demoted: list[Candidate] = []
    violations: list[str] = []

    for i in skill_idx:
        cand = candidates[i]
        goal = cand.goal
        assert isinstance(goal, LevelSkillGoal)
        skill = goal._skill_name
        gate = gates.get(skill)
        if gate is None:
            demoted.append(cand)
            continue
        target = skill_grind_target(skill, state, game_data)
        if target is None:
            violations.append(skill)
            continue
        grind = GatherMaterialsGoal(target_item=target, needed={target: 1})
        grind_cand = Candidate(goal=grind, is_means=True, repr_=repr(grind))
        if gate.source is GateSource.TASK_ITEM:
            before_pursue.append(grind_cand)
        elif has_paying_task:
            after_pursue.append(grind_cand)
        else:
            after_accept.append(grind_cand)

    result = base
    result = _insert_before(result, before_pursue, _is_pursue, _is_wait)
    result = _insert_after(result, after_pursue, _is_pursue, _is_wait)
    result = _insert_after(result, after_accept, _is_accept, _is_wait)
    result = _insert_before(result, demoted, _is_wait, None)
    return result, violations
