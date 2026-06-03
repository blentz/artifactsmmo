# Perimeter Closure Plan — Items 1-14

**User mandate (2026-06-02)**: "proceed with items 1-14" — the gaps
identified for "AI portion bug-free" claim.

**Status**: PLANNING + Item 1 underway.

## Scope: src/artifactsmmo_cli/ai/

NOT covered (per honest disclosure):
- TUI, CLI, persistence, API client wrappers.
- Concurrency / network temporal model.
- Probabilistic drops.
- Multi-player contention.

## Items (proof-side)

### Item 1 — Discharge 2 fat axioms (multi-phase)
- `accept_cancel_loop_bound` — composition claim about lifecycle iterations.
- `lifecycle_progress_from_bounds` — composition residual under capstone.

**Sub-phases**:
- 1a. Add `taskFeasibleProjected : Bool` to State. Refine `taskCancelFires`
     to require `!taskFeasibleProjected ∨ !taskPursueProjected`. Mirrors
     production's `task_decision == PIVOT` gating (production decides
     PIVOT when learning store indicates infeasibility).
- 1b. Prove: when `taskFeasibleProjected = true`, cycleStep from
     `.accepted` advances to `.complete` in `taskTotal` steps (via
     `.taskTrade` chain). Composes Phase 23d-7's `taskComplete_reachable`.
- 1c. Prove `accept_cancel_loop_bound_conditional`: bounded reach to
     `.complete` under `taskFeasibleProjected` hypothesis.
- 1d. Reduce `lifecycle_progress_from_bounds` to a theorem composing 1c +
     LIV-002 (taskCompleteXpEstimate = 10) + cycleStep semantics of
     `completeTask` + level-rollover math.
- 1e. Drop `accept_cancel_loop_bound` and `lifecycle_progress_from_bounds`
     from the allow-list.

### Item 2 — Prove `GlobalInvariants` discharges at runtime
The capstone (`ai_reaches_level_fifty`, Phase 25) assumes `GlobalInvariants`
holds at the starting state + every reachable state. Currently a hypothesis.

**Sub-phases**:
- 2a. Identify which hypotheses are TRIVIALLY preserved (perceptual invariants
     vs structural invariants).
- 2b. Prove `cycleStep` preserves `GlobalInvariants` for trivial cases.
- 2c. Identify hypotheses requiring runtime check (production invariants
     established by perceive layer).
- 2d. Add Python differential verifying production's `_fetch_world_state`
     output establishes `GlobalInvariants`.

### Item 3 — Discharge `hpursue` trajectory hypothesis (Phase 23d-5)
The hypothesis "ladder picks `.pursueTask` while `.inProgress`" is currently
assumed. Production's actual ladder may pick `.taskCancel` (if PIVOT decided)
or higher-priority means (guards, collect tier).

**Sub-phases**:
- 3a. Add hypothesis bundle for "no higher-priority means fires during
     inProgress trajectory".
- 3b. Prove ladder selection picks `.pursueTask` under bundle.
- 3c. Discharge or thread the bundle through Phase 25 capstone.

## Items (modeling-side)

### Item 4 — Full `applyActionKind` semantics for 26 actions
Currently most actions are counter advances or no-ops. Production semantics:
- `.fight`: xp+10 (modeled) + loot inventory + hp damage + position update + bank-unlock flip (modeled).
- `.gather`: skill XP increment (modeled) + drop into inventory + position.
- `.craft`: counter advance (modeled). Real: ingredient consumption + output production + skill XP + task_progress for crafting tasks.
- `.taskTrade`: progress+1 (modeled). Real: progress+quantity + inventory decrement + reward credit.
- 10+ other actions currently identity.

**Sub-phases**:
- 4a. Inventory composition: `inventoryItems : Item → Nat` field. Update
     `.gather` + `.craft` + `.taskTrade` to mutate it.
- 4b. Equipment composition: `equipment : Slot → Option Item` field. Update
     `.equip` + `.unequip` + `.optimizeLoadout`.
- 4c. Position: `pos : Int × Int`. Update `.move` + `.mapTransition` + every
     action that has a workshop/location.
- 4d. Gold + reward credit: update `.fight` loot + `.completeTask` reward
     (not just XP) + `.npcSell` + `.taskExchange`.
- 4e. Skill XP map (subsumes Item 5).
- 4f. Update all proofs (Phase 19 measure lemmas + Phase 23 reachability)
     against richer applyActionKind.

### Item 5 — Per-skill XP modeling
Replace scalar `projectedSkillXpDelta : Nat` with per-skill map.

**Sub-phases**:
- 5a. Add `Skill` inductive (mining/woodcutting/fishing/alchemy/weaponcrafting/
     gearcrafting/jewelrycrafting/cooking/combat).
- 5b. Add `skillXpDelta : Skill → Nat` to State.
- 5c. Update `.gather` to take Skill parameter; advance `skillXpDelta[skill]`.
- 5d. Update `.craft` to advance `skillXpDelta[r.craftSkill]` per Recipe.
- 5e. Update Phase 19 / 23d-7 / 23d-8 proofs to handle per-skill claim.

### Item 6 — LearningStore semantics
Production's PIVOT/PURSUE decision reads `LearningStore`. Currently opaque
Bools (`pursueTaskFires`, `taskCancelFires`, etc.).

**Sub-phases**:
- 6a. Model `LearningStore` as a structure: `samples : List Yield`,
     `mean_reward : Rat`, etc.
- 6b. Model `task_decision_pure` as a Lean function (already exists in
     `Formal.TaskDecision` from Phase 13; bridge to Liveness).
- 6c. Replace opaque Bool firings with computed predicates over the
     LearningStore + State.
- 6d. Update Phase 23d-3 (LIV-003a feasibility-grounded theorem) to use
     real `taskInfeasible` (not the abstracted version).

### Item 7 — Discharge `.objectiveStep` synthetic
Phase 21d-1 placeholder. Production has StrategyArbiter sub-goal dispatch.

**Sub-phases**:
- 7a. Model `MetaGoal` inductive (ObtainItem / ReachSkillLevel / ReachCharLevel).
- 7b. Model `StrategyArbiter.objective_step_goal` dispatching to sub-goal.
- 7c. Replace synthetic `.objectiveStep` ActionKind with dispatch lemmas
     per MetaGoal type.

### Item 8 — State field gap closure
Add missing WorldState fields:
- `equipment : Slot → Option Item`
- `inventory : Item → Nat`
- `skills : Skill → Nat`
- `npcStock : NpcCode → Item → Nat`
- `bankItems : Item → Nat`
- `bankGold : Nat`
- `eventSpawns : EventCode → Position`
- `pendingItems : List Item`
- Etc.

Each addition triggers Phase 19 lemma re-proof. Highest cascade risk.

## Items (differential / engineering)

### Item 9 — 100% differential coverage of ai/
- 9a. Enumerate Python functions under `src/artifactsmmo_cli/ai/`.
- 9b. Map each to existing diff test + identify uncovered.
- 9c. Add diff tests until 100% function coverage (line coverage via mutation).

### Item 10 — Mutation gate in CI
- 10a. Write `formal/diff/mutate.py` as a GitHub Action.
- 10b. Set scheduled run + leak fail-fast via `git diff src` post-run check.

### Item 11 — Snapshot refresh automation
- 11a. Scheduled GitHub Action runs `snapshot_game_data.py` daily.
- 11b. PR auto-opened when snapshot differs.
- 11c. `generate_lean_fixture.py` rerun + build verified before merge.

### Item 12 — Mutation kill rate audit
- 12a. Per-file mutation enumeration tool.
- 12b. Kill-rate dashboard. Goal: 100%.

## Items (server contract)

### Item 13 — Server-axiom replay harness
- 13a. Capture real fight outcomes (xp gained per fight, monster level).
- 13b. Verify gains match `xpToNextLevel` curve.
- 13c. Same for completeTask reward, drop rates (axiomatized).

### Item 14 — Openapi conformance
- 14a. Parse openapi.json into Lean types.
- 14b. Verify `GameData.load` parser matches schema field-by-field.
- 14c. Replay test asserts live API responses match openapi schema.

## Execution order

Recommended:
1. Item 1 (proof-side, smallest blast radius).
2. Item 10 + 11 (engineering, low blast radius).
3. Item 13 + 14 (server-axiom replay; one-time setup).
4. Item 8 (state field gap — high blast radius, but unblocks 4/5/6/7).
5. Item 4 + 5 + 6 + 7 (modeling work after state extended).
6. Item 9 (differential coverage final pass).
7. Item 12 (mutation kill rate final pass).
8. Item 2 + 3 (capstone closure, depends on above).

## Tracking

Each sub-phase commits independently. PLAN row marked DONE with commit hash.
