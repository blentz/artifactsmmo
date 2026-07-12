# LevelSkill Action — Implementation Plan (Phase 3: full unification)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Retire the tree-level skill-grind machinery (`ReachSkillLevel` meta-goal + its `strategy_driver` dispatch, `LevelSkillGoal`, and the orphaned dispatch cores) so the planner-native `LevelSkill` action (epic P1/P2/P4) is the SINGLE skill-grind mechanism — after first EXTENDING the `LevelSkill` path to cover the two grind paths it does not yet subsume (gear-unlock, task-skill).

**Architecture:** Ordering is safety-critical. The P3-surface map proved `ReachSkillLevel`/`LevelSkillGoal` are LOAD-BEARING: the P2 craft-goal `LevelSkill` path fires only when an under-skill craftable is a MATERIAL inside a `GatherMaterials` closure. Gear-unlock (an equippable routed via `_equippable_goal`) and task-skill (`PURSUE_TASK` skill requirement) have no such path. So P3a EXTENDS coverage and RUNTIME-VERIFIES both grinds route through `LevelSkill`; only then does P3b retire the old machinery and P3c migrate/retire the Lean proofs. No commit removes a grind driver before its replacement is proven live.

**Tech Stack:** Python 3.13, `uv`, GOAP (`GOAPPlanner`/`StrategyArbiter`), Lean 4 (`formal/`).

## Global Constraints

- `uv run` prefix (uv at `/home/blentz/.local/bin/uv`). TDD; 0 errors/warnings/skipped, 100% coverage.
- No inline imports; never `if TYPE_CHECKING`; never catch `Exception`; one behavioral class per file.
- `formal/diff/` + `gate.sh` on any decision-path (`is_applicable`/`apply`/`is_plannable`/`relevant_actions`-of-a-mirrored-goal/`WorldState`) or Lean change — run explicitly, serialized.
- The `LevelSkill` admission into any goal's `relevant_actions` MUST be scoped to the goal's own gated skills (mirror `GatherMaterialsGoal.gated_skill_levels`, `goals/gathering.py`) — an unconditional admission fans ~15 grind actions into every search and times out under load (P2 regression `ff4401ac`).
- Retiring a grind driver requires its replacement RUNTIME-VERIFIED first (`plan <char>` / scenario). Green tests ≠ runtime-active.
- Commit only on clean review; do not push unless asked.
- P1/P2/P4 shipped interfaces: `LevelSkill(skill, target_level, xp_curve=None)` (`actions/level_skill.py`), `tags={"skill_grind"}`, `is_applicable` = under-target AND (`skill_grind_target` ∨ `best_gather_resource_drop`); player hook `_execute_level_skill` + `level_skill_expand.next_grind_goal` (one grind cycle, cycle-guarded); `LevelSkill.execute` raises (player-expanded).

---

## P3a — Extend coverage (SAFETY-CRITICAL, do first)

### Task 1: Gear-unlock grinds through LevelSkill (UpgradeEquipmentGoal)

**Files:** Modify `src/artifactsmmo_cli/ai/goals/progression.py` (`UpgradeEquipmentGoal.is_plannable` + `relevant_actions`); Test `tests/test_ai/test_upgrade_equipment_level_skill.py` (create).

**Interfaces:**
- Consumes: `UpgradeEquipmentGoal.is_plannable` crafting-skill gate at `progression.py:156-168` (returns False under-skill); its `relevant_actions` closure/slot lock (`progression.py:174-266`); `LevelSkill` + its `"skill_grind"` tag; the `gated_skill_levels` scoping pattern (`goals/gathering.py`).
- Produces: an under-skill craftable equippable is now plannable and its plan sequences `LevelSkill(gear_skill) → … → Craft(gear) → Equip(gear)`.

- [ ] **Step 1: Failing test** — build an under-skill craftable-gear fixture (gear crafting_level > char skill, materials gatherable), assert `UpgradeEquipmentGoal(...).is_plannable(state, gd) is True` AND `GOAPPlanner().plan(...)` (with a `LevelSkill(gear_skill, gear_level)` in the action set) sequences a `LevelSkill` before `Craft(gear)`. RED: currently `is_plannable` returns False at the skill gate.
- [ ] **Step 2: Drop the skill gate** — remove `progression.py:166-168` (the `state.skills[...] < crafting_level → return False`). Update the docstring (the gate was the pre-LevelSkill CPU guard; the `LevelSkill` action now makes under-skill plannable). The `min_plan_length ≤ max_depth` check at `:169-172` stays.
- [ ] **Step 3: Admit scoped LevelSkill in relevant_actions** — compute the gated `(skill, level)` of the target's own closure craftables (mirror `gathering.py` `gated_skill_levels`) and admit a `"skill_grind"`-tagged action only when its `(skill, target_level)` is in that set. Duck-typed, no `LevelSkill` import (avoid the closure/slot-lock over-admitting).
- [ ] **Step 4: GREEN + regression** — the test passes; run `pytest tests/test_ai/ -k "upgrade or progression or equip" -q --no-cov` (no slot-lock/closure regression) + ruff/mypy on `progression.py`.
- [ ] **Step 5: gate.sh** — `is_plannable`/`relevant_actions` are decision-path; run `formal/gate.sh` (is `UpgradeEquipmentGoal.is_plannable` Lean-mirrored? if so, update the diff; if not, the gate confirms no break) → ALL PARTS PASSED. Commit.

### Task 2: Task-skill grinds through LevelSkill (retire LevelSkillGoal construction)

**Files:** Create `src/artifactsmmo_cli/ai/goals/reach_skill.py` (`ReachSkillGoal` — a thin goal that aims the `LevelSkill` action); Modify `src/artifactsmmo_cli/ai/strategy_driver.py:435-442` (`map_means` PURSUE_TASK); Modify `goal_serialization.py`; Tests.

**Interfaces:**
- Consumes: the `map_means` PURSUE_TASK skill-req branch (`strategy_driver.py:437-442`, constructs `LevelSkillGoal`); `task_requirement(state, game_data)` → `SkillRequirement(skill, required_level)`; `LevelSkill`.
- Produces: `ReachSkillGoal(skill: str, target_level: int)`: `is_satisfied` = `state.skills.get(skill,1) >= target_level`; `relevant_actions` = the `LevelSkill(skill, target_level)`-tagged actions in the set (scoped to this skill); `desired_state` = `{"skills": {skill: target_level}}`; `value`/`max_depth` mirroring `LevelSkillGoal`'s priority (55.0) so arbiter ordering is unchanged. `map_means` returns `ReachSkillGoal` instead of `LevelSkillGoal`.

- [ ] **Step 1: Failing test** — `ReachSkillGoal("alchemy", 5)`: `is_satisfied` False at alchemy 1 / True at 5; `relevant_actions([LevelSkill("alchemy",5), LevelSkill("mining",3)], …)` returns only the alchemy one; a planner run yields `[LevelSkill("alchemy"→5)]`. RED: module missing.
- [ ] **Step 2: Implement `ReachSkillGoal`** (one behavioral class, its own file). `relevant_actions` admits a `"skill_grind"`-tagged action iff `action.skill == self._skill` (this goal targets exactly one skill).
- [ ] **Step 3: Route map_means to it** — replace the `LevelSkillGoal(...)` at `strategy_driver.py:440-442` with `ReachSkillGoal(skill=req.skill, target_level=target)`. Keep the same `target = min(req.required_level, current + LEVEL_LOOKAHEAD)` bound.
- [ ] **Step 4: Serialization** — `goal_serialization.py`: add a `ReachSkillGoal` branch; add a COMPAT SHIM for a persisted `{"type":"LevelSkillGoal"}` (translate to `ReachSkillGoal` or return a drop-and-replan sentinel) so a rehydrate does not hard-raise (`goal_serialization.py:63`).
- [ ] **Step 5: GREEN + gate.sh + commit.**

### Task 3: Runtime verification (BLOCKS P3b)

- [ ] Runtime-verify BOTH grinds route through `LevelSkill` on live `plan <char>` (or a scenario driving the arbiter): (a) an under-skill gear-upgrade target sequences `LevelSkill → Craft(gear)`; (b) a `PURSUE_TASK` whose item needs an under-leveled craft skill sequences `LevelSkill`. Record both plan outputs. **Do NOT start P3b until both are confirmed live** — this is the guard the map demanded.

---

## P3b — Retire the tree routing (only after P3a Task 3 confirms coverage)

Retire in dependency order; each step keeps the tree/suite green.

- [ ] **Retire `ReachSkillLevel` emission + dispatch:** remove the `strategy_driver.py:782-886` dispatch branch and its sole-caller hoisters `_skill_dispatch_candidates` (254-310) + `_gated_behind_skill` (240-251); remove `ReachSkillLevel` emission in `prerequisite_graph.py:60-71`; remove the `ReachSkillLevel` arms in `tiers/strategy.py` (rank/order/root_cost/is_reachable), `objective_needs.py:70-75`, `equipment_profile.py:59-65`, `plan_tree.py:29`; delete `ReachSkillLevel` from `tiers/meta_goal.py` + `tiers/__init__.py` exports. Verify no `isinstance(_, ReachSkillLevel)` remains.
- [ ] **Retire `LevelSkillGoal`:** delete `goals/level_skill.py`; remove the `strategy_driver.py:42` import; keep the `goal_serialization.py` compat shim (Task 2 Step 4). Reconcile the `PRIORITY_WHEN_FIRING` references in `grind_character_xp.py`/`low_yield_cancel.py` (inline the constant or move it).
- [ ] **Retire orphaned cores:** `skill_step_dispatch.py` (`skill_step_dispatch_pure`, `combine_dispatch_pure`, `dispatch_candidate_flags`, `cannibalize_pure`, `DispatchCandidate`, `FlagInputs`) and `next_tier_cap.py` (`next_tier_cap_pure`, `next_tier_dampened_pure`) — all sole-callers die with the dispatch. KEEP `skill_grind_target`, `build_grind_candidates`, `skill_grind_selection_pure` (live via the P2 hook `next_grind_goal`). Grep-confirm each retired symbol has zero live callers before deleting.
- [ ] Gate.sh + full suite + runtime after each sub-step group.

---

## P3c — Lean proof migration / retirement

- [ ] **Retire orphaned dispatch proofs:** `SkillStepDispatch.lean` + `GrindLadder.lean` model `skill_step_dispatch_pure`/`dispatch_candidate_flags`/`cannibalize_pure` (now retired) — delete the theorem files + every anchor: `Formal.lean` imports, `Manifest.lean:121-131` role-checks, Oracle keys `skill_step_dispatch`/`combine_dispatch`/`candidate_flags`/`cannibalize` (`Oracle.lean:2997-3009`), `formal/diff/test_skill_step_dispatch_diff.py` + `test_grind_ladder_diff.py`, their `mutate.py` groups, README prose. KEEP `SkillGrindSelection.lean` + key `skill_grind_selection` (anchored to live `skill_grind_selection_pure`).
- [ ] **Migrate liveness:** `Liveness/MetaGoalDispatch.lean` (`dispatch_reachSkillLevel`/`applyDispatch_reachSkillLevel`) modeled the retired `ReachSkillLevel` dispatch → retire or re-express as the `LevelSkill`-action grind step. `Liveness/SkillGapClosure.lean` (`skill_prerequisite_reachable`/`skill_gap_then_complete_reachable`) — the reach chain that the items-task liveness (`RecipeChainClosure.lean:48`) documents-on; re-anchor its skill arm to the `LevelSkill` action path (the K gathers still model one grind cycle each). Update `Formal.lean` imports + `LivenessAudit.lean:276-277,511-514` axiom prints. No new axioms; no vacuous theorems.
- [ ] `next_tier_cap`/`SkillTargetCurve` Oracle keys (`skill_target_curve`, `next_tier_cap`, `next_tier_dampened`) — retire if their Python cores were removed in P3b; else keep.
- [ ] Full `gate.sh` ALL PARTS PASSED (Lean builds clean after retirement, mutation groups removed, surviving proofs green) + full suite 100% + runtime. Whole-branch review. Regenerate `PROOF_CONCEPT_INDEX.md` (a Lean-file deletion makes it stale — gate part b'').

---

## Notes
- P3 is full-unification CLEANUP; the epic ACCEPTANCE (census planner_bug 0) is already delivered (P4). If any P3 step reveals unacceptable regression risk, the epic can stop at P4 with two coexisting skill-grind mechanisms.
- The `next_grind_goal` player hook already handles the execution of any `LevelSkill` a goal emits — P3a's new emitters (UpgradeEquipment, ReachSkillGoal) reuse it unchanged.
