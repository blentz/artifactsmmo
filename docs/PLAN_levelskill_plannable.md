# PLAN: Make LevelSkillGoal plannable (no 90s timeout footgun)

Status: investigation complete, awaiting approach decision. 2026-06-14.

## Findings

### Role
The skill-gate liveness mechanism's PRIMARY forward action is
`skill_grind_target(skill) -> GatherMaterials(craft_one, held+1)` ("craft one
more in-skill item, replan"). `LevelSkillGoal` is the SECONDARY fallback in
`objective_step_goal`, reached only when `skill_grind_target` returns None.
The 2026-06-14 192617 trace showed `LevelSkill(gearcrafting->5)` timing out
25/25 cycles (60968 nodes, depth 22, 90s, plan_len 0), then silent fallthrough
to GrindCharacterXP — skills frozen. The reservation self-lock that *forced* the
fallthrough is already fixed (relaxed-reservation retry in `objective_step_goal`,
[[project_skill_gated_self_lock]]). This plan addresses the LATENT footgun.

### Why LevelSkillGoal is un-plannable / explosive
`LevelSkillGoal.is_satisfied` (goals/level_skill.py:66) satisfies only when the
per-plan-path `projected_skill_xp_delta` crosses the FULL current-level
threshold:
1. server-snapshot path `skills[skill] >= target_level` — FROZEN during planning
   (`Craft.apply` bumps `projected_skill_xp_delta`, never `state.skills`), so it
   can never trip mid-plan.
2. projection path `skill_xp + projected >= required_xp(current_level)` — needs
   enough projected XP to cross one full level. That is MANY crafts (each
   copper_helmet = 6 copper_bar = 6 ore-gather+smelt chains), so the A* plan is
   dozens of actions deep → 60k-node blow-up.
   - `required_xp` comes from a LEARNED `SkillXpCurve`; when the curve lacks the
     current level it returns 0 → projection DISABLED → goal unsatisfiable
     in-plan → guaranteed 90s timeout. (Note: the API already provides
     `{skill}_max_xp` ground-truth per level — the learned curve is redundant
     here and its gaps are the failure mode.)

### Secondary defect: reservation backdoor
`LevelSkillGoal.relevant_actions` does NOT honor the material reservation that
`skill_grind_target` enforces. When the arbiter falls to LevelSkillGoal while a
committed gear root reserves a shared material (e.g. copper_boots' copper_bar),
LevelSkillGoal's plan can still craft copper_helmet and cannibalize those bars —
the reservation is illusory once the fallback fires.

## Options

- **A — one-craft satisfaction.** `is_satisfied` trips on any positive
  `projected_skill_xp_delta[skill]` (one craft of forward progress); drop the
  `SkillXpCurve` dependency. Plannable in <100 nodes; matches the stated
  "deadlock-breaker, not a grind engine" intent; per-cycle replan continues the
  grind. Formal coupling: `value()` calls `is_satisfied` → `test_goal_system_value_diff.py`
  must stay green (Lean model of value/satisfaction may need a lockstep edit).

- **B — retire the fallback.** When `skill_grind_target` returns None, return
  None (arbiter picks the next-best root) instead of an un-plannable
  LevelSkillGoal. Smallest surface; removes both the timeout and the backdoor.
  Risk: a gating skill with a level GAP (no recipe at-or-below current level)
  loses its only fallback — but that case can't make crafting progress anyway.
  Breaks `test_objective_step_reach_skill_level` (asserts LevelSkillGoal is
  returned) — would be re-specced.

- **C — A + close the backdoor (recommended).** One-craft satisfaction AND make
  `LevelSkillGoal.relevant_actions` honor the reservation. Keeps LevelSkill as a
  real, plannable, honest fallback for level-gap skills while killing the
  timeout and the cannibalization path.

## Recommendation
C. Keeps a working fallback (B's None can strand non-monotone skills), makes it
plannable from cycle 1 without learning warmup, and closes the reservation
backdoor. TDD + `formal/gate.sh` lockstep (serialize the gate run, git diff src
after — [[feedback_serialize_gate_runs]]).
