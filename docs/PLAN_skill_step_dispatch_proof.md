# PLAN: Prove the skill-step dispatch routing (close the proof gap)

Status: Phase 0. 2026-06-14.

## Motivation
`objective_step_goal`'s `ReachSkillLevel` branch and `skill_grind_target`'s
reservation filter are pure DECISION logic that skipped being proven. The
abstract `StepDispatch.lean` (`reachSkillLevel → levelSkill`) is a documented
over-approximation NOT diff-bound to the concrete routing — proven decoupled by
the fact that the live code already routes `ReachSkillLevel → GatherMaterials`
(via skill_grind_target) without any diff test failing. The cycle-step diff
explicitly discloses it does not exercise `arbiter.select`/`objective_step_goal`.
The recent self-lock fix (relaxed-reservation retry, [[project_skill_gated_self_lock]])
added MORE unproven branching. Prove it.

## Proof boundary — the pure core
Extract `skill_step_dispatch_pure` (mirrors the `skill_grind_selection_pure`
pattern: pure, total, decidable; impure wrapper hoists inputs from GameData +
holdings). Composes the ALREADY-PROVEN `skill_grind_selection_pure` twice.

Inputs (all hoisted):
- `skill: str`, `current_level: int`
- `committed: (craft_skill: str, craft_level: int) | None` — the committed root item
- `candidates: list[DispatchCandidate]` where each carries the selection fields
  (`code, craft_skill, craft_level, mats_missing, obtainable`) PLUS two hoisted
  booleans `uses_reserved_full`, `uses_reserved_relaxed` (does the recipe touch a
  material in the full / relaxed reserved set).

Output: a tagged `Decision`:
- `SUPPRESS` — committed item is same-skill craftable-now (let its own root craft it)
- `GRIND(code)` — craft `code` (one more), replan
- `NO_GRIND` — nothing level-appropriate to grind (caller returns None → arbiter
  advances; for gathering-skill gates, ambient gathering levels the skill —
  skill_gates.py:7. Replaces the explosive full-level LevelSkillGoal fallback.)

Algorithm:
```
if committed and committed.skill == skill and committed.level <= current_level: SUPPRESS
full    = [c for c in candidates if not c.uses_reserved_full]
pick    = skill_grind_selection_pure(skill, current_level, full)
if pick == "":
    relaxed = [c for c in candidates if not c.uses_reserved_relaxed]
    pick    = skill_grind_selection_pure(skill, current_level, relaxed)
GRIND(pick) if pick else NO_GRIND
```

## Theorem roles (∀ inputs, kernel-checked)
- **R1 forward_progress (liveness/anti-deadlock).** If not suppressed and ∃ a
  feasible candidate (same-skill, in-level, obtainable) with
  `uses_reserved_relaxed = false`, then result ≠ NO_GRIND. (The whole point: a
  grindable level-appropriate item is never starved into the dead fallback.)
- **R2 full_preference (reservation honored when possible).** If ∃ a feasible
  candidate with `uses_reserved_full = false`, then the result is `GRIND(code)`
  with that code's candidate having `uses_reserved_full = false` — i.e. the
  relaxed pass is used ONLY when the full pass found nothing.
- **R3 suppression_correct.** result = SUPPRESS �iff committed is same-skill and
  `committed.level ≤ current_level`.
- **R4 grind_valid.** `GRIND(code)` ⇒ code is a same-skill, in-level, obtainable
  candidate (inherited via the proven selection roles).
- **R5 relax_monotone (model invariant).** Any candidate with
  `uses_reserved_relaxed = false` also has the full pass consider a superset —
  `reserved_relaxed ⊆ reserved_full` is enforced at hoist time; the core treats
  the two flags independently but R2+R1 only hold under this discipline, pinned
  by the differential test feeding consistent flags.

## Behavior change (baked into the core)
Retire the explosive `LevelSkillGoal` from the OBJECTIVE-step path: `NO_GRIND →
None`. The PURSUE_TASK path (map_means, separate) keeps LevelSkillGoal for now
(out of scope; note as follow-up). Re-spec the objective-path LevelSkill tests
(test_objective_step_reach_skill_level, TestLevelLookahead skill-step cases,
and the 1792 case) to the new contract.

## Gate parts (Phase 3) — mirror SkillGrindSelection
Manifest role `#check`s, Contracts exact-statement pins, oracle JSON kind
`skill_step_dispatch`, `formal/diff/test_skill_step_dispatch_diff.py` (Hypothesis,
feeds consistent reserved flags), mutation coverage. `formal/gate.sh` green,
serialized, `git diff src` after ([[feedback_serialize_gate_runs]]).

## Risks
- Gathering-skill `ReachSkillLevel` (resource-gather gate, prerequisite_graph.py:72):
  NO_GRIND→None is correct (ambient gathering levels it; cannot deadlock).
- 100% coverage must hold; re-spec not delete the LevelSkill objective tests.
- Differential test must feed `uses_reserved_*` flags consistently
  (`relaxed ⊆ full`) or R2 is testing an unreachable input shape — adversarial
  review item.
