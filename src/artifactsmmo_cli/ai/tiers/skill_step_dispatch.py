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
    wanted: bool  # the crafted item is a current objective gear/tool target (is_target)


@dataclass(frozen=True)
class FlagInputs:
    """Per-candidate inputs for the reservation-flag computation (the grind
    ladder). `recipe_mats` are the candidate's recipe input codes; `is_target` =
    the candidate is a committed objective gear/tool; `owned` = ≥1 already held."""
    code: str
    recipe_mats: tuple[str, ...]
    craft_level: int
    obtainable: bool
    is_target: bool
    owned: bool


def cannibalize_pure(current_level: int, candidates: list[FlagInputs]) -> bool:
    """LAST-RESORT predicate: every craftable-now, obtainable candidate is already
    owned — no unowned target left to skill up on. In that corner the relaxed pass
    is freed so the grind re-crafts an owned item rather than freezing."""
    feasible = [c for c in candidates
                if c.craft_level <= current_level and c.obtainable]
    return len(feasible) > 0 and not any(not c.owned for c in feasible)


def dispatch_candidate_flags(
    c: FlagInputs, current_level: int,
    reserved_full: frozenset[str], reserved_relaxed: frozenset[str],
    cannibalize: bool,
) -> tuple[bool, bool]:
    """Compute (uses_reserved_full, uses_reserved_relaxed) for one grind
    candidate. An unowned, craftable-now TARGET is exempt (crafting it is
    objective progress — both flags false). Otherwise the flags mark whether the
    recipe touches a reserved material; the relaxed flag additionally clears under
    `cannibalize`. See formal/Formal/GrindLadder.lean."""
    exempt = c.is_target and c.craft_level <= current_level and not c.owned
    uses_full = (not exempt) and any(m in reserved_full for m in c.recipe_mats)
    uses_relaxed = ((not exempt) and (not cannibalize)
                    and any(m in reserved_relaxed for m in c.recipe_mats))
    return (uses_full, uses_relaxed)


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
                          obtainable=c.obtainable, wanted=c.wanted)


def skill_step_dispatch_pure(
    skill: str, current_level: int,
    committed_skill: str, committed_level: int,
    candidates: list[DispatchCandidate],
    dampened: bool = False,
) -> DispatchDecision:
    """Decide the grind action for a `ReachSkillLevel(skill, ...)` step by
    composing the proved selection (`skill_grind_selection_pure`, run over the
    full- then relaxed-reservation candidate lists) with the proved combine core
    (`combine_dispatch_pure`). The composition's safety/liveness are the
    `forward_progress` / `reservation_safety` theorems in
    formal/Formal/SkillStepDispatch.lean.

    When `dampened` (the caller's next-tier throwaway signal) and the combine
    core would GRIND a pick that is NOT a wanted objective target, suppress the
    grind instead: the throwaway would only over-skill a tier the committed root
    already covers. The branch is guarded by `not wanted`, so a committed/wanted
    craft is never blocked — dampening only converts a throwaway grind into a
    SUPPRESS (see `dispatchD_*` theorems in formal/Formal/SkillStepDispatch.lean).
    Behavior is unchanged when `dampened` is False (the default)."""
    full = [_to_grind(c) for c in candidates if not c.uses_reserved_full]
    full_pick = skill_grind_selection_pure(skill, current_level, full)
    if full_pick != "":
        relaxed_pick = ""
    else:
        relaxed = [_to_grind(c) for c in candidates if not c.uses_reserved_relaxed]
        relaxed_pick = skill_grind_selection_pure(skill, current_level, relaxed)
    kind, code = combine_dispatch_pure(skill, current_level, committed_skill,
                                       committed_level, full_pick, relaxed_pick)
    if kind == "grind" and dampened:
        # `code` is always a candidate's code when combine returns "grind"
        # (skill_grind_selection_pure picks from `candidates`), so this lookup
        # cannot miss — fail loud rather than defend an impossible None.
        picked = next(c for c in candidates if c.code == code)
        if not picked.wanted:
            return DispatchDecision(kind="suppress", code="")
    return DispatchDecision(kind=kind, code=code)
