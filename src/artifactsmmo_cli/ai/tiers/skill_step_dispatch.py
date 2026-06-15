"""Pure core for dispatching a `ReachSkillLevel` objective step to a concrete
grind decision: SUPPRESS the throwaway grind (let the committed root craft its
own gear), GRIND one level-appropriate in-skill item, or NO_GRIND (nothing
craftable to grind — caller returns None and the arbiter advances; gathering
skills are leveled by ambient gathering, skill_gates.py).

`skill_step_dispatch_pure` is the proved decision core (see
formal/Formal/Extracted/SkillStepDispatch.lean). It composes the already-proved
`skill_grind_selection_pure` twice: a FULL-reservation pass (respect every
reserved material) then, only if that finds nothing, a RELAXED pass that frees
the materials of skill-gated objectives (whose grind is their own bootstrap —
trace 2026-06-14 192617, [[project_skill_gated_self_lock]]). The impure caller
(`objective_step_goal`) hoists the candidates and the two per-candidate
`uses_reserved_*` booleans from GameData + holdings and delegates here.

This replaces the explosive full-level `LevelSkillGoal` fallback: a multi-level
grind planned as one A* chain timed out (60968 nodes / 90s / plan_len 0, 25/25
cycles). "Grind any level-appropriate item, replan" is the whole mechanism.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.tiers.skill_grind_selection import (
    GrindCandidate,
    skill_grind_selection_pure,
)


@dataclass(frozen=True)
class DispatchCandidate:
    """A craftable in-skill item considered for the grind. The selection fields
    (`code, craft_skill, craft_level, mats_missing, obtainable`) mirror
    `GrindCandidate`; `uses_reserved_full` / `uses_reserved_relaxed` are HOISTED
    booleans — whether the recipe consumes a material in the full / relaxed
    reserved set (relaxed ⊆ full, so `uses_reserved_relaxed` ⇒ `uses_reserved_full`)."""
    code: str
    craft_skill: str
    craft_level: int
    mats_missing: int
    obtainable: bool
    uses_reserved_full: bool
    uses_reserved_relaxed: bool


@dataclass(frozen=True)
class DispatchDecision:
    """`kind` ∈ {"suppress", "grind", "no_grind"}; `code` is the grind target
    when `kind == "grind"`, else ""."""
    kind: str
    code: str


def combine_dispatch_pure(
    skill: str, current_level: int,
    committed_skill: str, committed_level: int,
    full_pick: str, relaxed_pick: str,
) -> tuple[str, str]:
    """The PROVED decision core (formal/Formal/Extracted/SkillStepDispatch.lean):
    combine the two reservation-pass selection results into a `(kind, code)`
    decision — kind ∈ {"suppress", "grind", "no_grind"}, code the grind target
    when kind == "grind" else "".

    `full_pick` / `relaxed_pick` are `skill_grind_selection_pure` over the
    full-reservation-respecting / relaxed candidate lists ("" = no pick). When
    the committed item is same-skill and craftable NOW (`committed_level <=
    current_level`), suppress the throwaway grind. Otherwise prefer `full_pick`
    (reservation honored); fall back to `relaxed_pick` only when the full pass
    found nothing; NO_GRIND when neither pass picked anything."""
    if committed_skill == skill and committed_level <= current_level:
        return ("suppress", "")
    pick = full_pick if full_pick != "" else relaxed_pick
    if pick != "":
        return ("grind", pick)
    return ("no_grind", "")


def _to_grind(c: DispatchCandidate) -> GrindCandidate:
    return GrindCandidate(code=c.code, craft_skill=c.craft_skill,
                          craft_level=c.craft_level, mats_missing=c.mats_missing,
                          obtainable=c.obtainable)


def skill_step_dispatch_pure(
    skill: str, current_level: int,
    committed_skill: str, committed_level: int,
    candidates: list[DispatchCandidate],
) -> DispatchDecision:
    """Decide the grind action for a `ReachSkillLevel(skill, ...)` step by
    composing the proved selection (`skill_grind_selection_pure`, run over the
    full- then relaxed-reservation candidate lists) with the proved combine core
    (`combine_dispatch_pure`). The composition's safety/liveness are the
    `forward_progress` / `grind_respects_full_reservation` theorems in
    formal/Formal/SkillStepDispatch.lean."""
    full = [_to_grind(c) for c in candidates if not c.uses_reserved_full]
    full_pick = skill_grind_selection_pure(skill, current_level, full)
    if full_pick != "":
        relaxed_pick = ""
    else:
        relaxed = [_to_grind(c) for c in candidates if not c.uses_reserved_relaxed]
        relaxed_pick = skill_grind_selection_pure(skill, current_level, relaxed)
    kind, code = combine_dispatch_pure(skill, current_level, committed_skill,
                                       committed_level, full_pick, relaxed_pick)
    return DispatchDecision(kind=kind, code=code)
