# PLAN: Total Composition Correctness for the AI

**Goal:** Prove in Lean 4 that the bot's full per-cycle decision pipeline emits the
**optimal** action for any reachable state — not just that each piece is locally
correct.

**Anti-goal:** Whack-a-mole bug fixing on traces. Every bug encountered after this
plan ships must either (a) be a Lean-discharged invariant violation caught by
the differential gate, or (b) require an explicit Lean theorem update first.

---

## What "composition correctness" means here

Existing proofs cover **local** properties: `pickSlot` is argmax, `actionable_step`
is the deepest unmet node, `cap = max-of-five`, etc. None of them say anything
about whether the **right** local function is called at the **right** time on
the **right** inputs. The trace bugs of 2026-06-06 (tool-root locked, hp-myopic
target picker, fishing_net wears combat) are all composition bugs. The kernel
saw the local math; nothing checked the global routing.

The end-state theorem we are building toward:

```
theorem optimal_action_emitted
  (objective : Objective)
  (state     : WorldState)
  (history   : History)
  (gameData  : GameData)
  : let dec := decide objective state history
    let goal := arbiter.select dec state history
    let plan := goap.plan goal state gameData
    plan.head? = some (optimalAction objective state history gameData)
```

`optimalAction` is the externally-specified ground truth: for the current task
purpose (combat / gather / craft / heal / bank), with current equipment, with
current monster threat profile, what is the value-maximizing action under a
total ordering proven exhaustive? The theorem says the bot returns exactly that.

This is decomposable. We do NOT need a single 5000-line monolith.

---

## The composition chain (top-down)

```
optimal_action_emitted
  ├── optimal_goal_selected_by_arbiter
  │     ├── chosen_root_is_value_maximal
  │     │     ├── armor_priority_dominant_when_slot_empty       (GearPolicy)
  │     │     ├── tool_priority_dominant_for_active_task        (GearPolicy)
  │     │     └── bootstrap_priority_dominant_when_combat_unblocked (GearPolicy)
  │     ├── chosen_step_is_deepest_unmet                        (StrategyTraversal ✓)
  │     └── step_goal_dispatch_correct                          (StepDispatch — new)
  ├── goal_planner_emits_value_maximizing_action
  │     ├── action_applicability_complete                       (ActionApplicability — new)
  │     ├── target_selection_winnable_at_max_hp                 (CombatTargetExistence — new)
  │     ├── purpose_dispatch_correct                            (PurposeRouting — new)
  │     └── loadout_pick_optimal                                (EquipmentScoring ✓)
  └── invariants_preserved_under_apply                          (LoadoutProjection ✓)
```

Boxes marked ✓ already exist. Six new modules close the chain.

---

## Phase roadmap (each phase = its own checkpoint commit)

### Phase G1 — GearPolicy.lean (this commit, in progress)

**Theorem set:**

| Theorem | Statement |
|---|---|
| `empty_armor_slot_value_strictly_dominates_unowned_root` | If `slot[s] = None` and a craftable armor for `s` is realizable, the priority of `ObtainItem(armor)` is strictly greater than the priority of any root whose target slot is already filled with a non-trivially-dominated item. |
| `tool_owned_root_is_satisfied` | (mirrors the runtime fix 18576fc) `subtype = tool → ownedCount ≥ 1 → ObtainItem(code)` is satisfied. |
| `armor_score_monotone_over_resistance` | `AScore` is monotone non-decreasing in each resistance element. |
| `armor_strictly_dominates_baseline` | For any armor with `0 < AScore`, replacing `None` in the slot strictly increases `projectedField(defense)`. |

**Deliverable:** `formal/Formal/GearPolicy.lean`, `lake build` clean, axiom check
passes (no new non-mathlib axioms outside the LIV-001 budget),
`formal/Formal/Manifest.lean` references the four theorems, `formal/Formal/Contracts.lean`
binds the Python entry points.

### Phase G2 — PurposeRouting.lean

**Theorem set:**

| Theorem | Statement |
|---|---|
| `gather_task_picks_skill_effect_minimizer` | If `task_kind = gather` with active skill `S`, the chosen weapon among feasible items minimizes `-skill_effects[S]` (ties broken by raw attack). |
| `combat_task_picks_attack_argmax` | If `task_kind = combat` against monster `M`, the chosen weapon maximizes `WScore` against `M.resistance`. |
| `tool_never_chosen_for_combat_when_real_weapon_owned` | If a non-tool weapon (`subtype ≠ tool`) with `WScore ≥` any tool's `WScore` is feasible, the picker returns a non-tool. (Closes "fishing_net for slimes when copper_dagger exists" by construction; the current tie at 5 attack is acceptable, but ANY non-tied edge resolves toward the real weapon.) |

**Deliverable:** `formal/Formal/PurposeRouting.lean`, oracle differential test against
`pick_loadout`.

### Phase G3 — CombatTargetExistence.lean

**Theorem set:**

| Theorem | Statement |
|---|---|
| `winnable_at_max_hp_exists_implies_picker_returns_some` | If `∃ monster, is_winnable(state{hp := max_hp}, monster) = True`, then `_winnable_farm_target ≠ None`. |
| `picker_returns_highest_level_winnable` | The returned monster has the maximum level among winnable candidates (preserves existing semantics). |
| `picker_respects_task_alignment` | When a monsters-task is active and PURSUE, the returned monster equals the task target. |

**Deliverable:** `formal/Formal/CombatTargetExistence.lean` + Python diff test for
the picker cascade.

### Phase G4 — ActionApplicability.lean

**Theorem set:**

| Theorem | Statement |
|---|---|
| `fight_applicable_iff_level_gear_hp` | `FightAction.is_applicable = True ↔ predicate over (level, best_eq, hp_percent, inventory_free)`. |
| `gather_applicable_iff_skill_tool` | Same for `GatherAction` over `(skill, tool, inventory_free)`. |
| `craft_applicable_iff_recipe_skill_workshop` | Same for `CraftAction`. |
| `equip_applicable_iff_owned_slot_compatible` | Same for `EquipAction`. |
| `rest_applicable_iff_subfull_hp` | `RestAction.is_applicable ↔ hp < max_hp`. |

These mirror the Python `is_applicable` bodies exactly (mutation-tested). Without
them, downstream "planner emits FightAction" reasoning is informal.

**Deliverable:** `formal/Formal/ActionApplicability.lean`. Oracle round-trip
covers every action class.

### Phase G5 — StepDispatch.lean

**Theorem set:**

| Theorem | Statement |
|---|---|
| `step_dispatch_total_and_unique` | `objective_step_goal(step, state, gameData)` is total over the inductive `MetaGoal` type and produces exactly one of the documented goal classes. |
| `step_dispatch_obtain_tool_returns_upgrade` | Tools go to `UpgradeEquipmentGoal` (subtype check). |
| `step_dispatch_obtain_gear_returns_upgrade` | Real gear too. |
| `step_dispatch_obtain_material_returns_gather` | Recipe inputs → `GatherMaterialsGoal`. |
| `step_dispatch_reach_skill_returns_level_skill` | Skill roots → `LevelSkillGoal`. |
| `step_dispatch_reach_char_returns_grind` | Char roots → `GrindCharacterXPGoal`. |
| `step_dispatch_safe_under_combat_monster_none` | `combat_monster = None → ReachCharLevel → None` (preserves current safe-fail). |

**Deliverable:** `formal/Formal/StepDispatch.lean` + diff test that exhaustively
constructs each `MetaGoal` variant and pins the dispatched goal class.

### Phase G6 — LivenessChain.lean (capstone)

**Theorem set:**

| Theorem | Statement |
|---|---|
| `bootstrap_step_plannable_when_winnable_exists` | `winnable_at_max_hp_exists(state) ∧ task_does_not_block_step → arbiter.select.head? = FightAction(target)`. This is the headline anti-livelock theorem. |
| `armor_full_set_eventually_equipped` | Given enough cycles, starting from `state.equipment = all_None`, if recipes are realizable from owned materials, the closure of bot decisions reaches `state.equipment = full_armor_set` without violating any guard. (Eventually = bounded by recipe-closure depth + craft cooldown.) |
| `no_starvation_under_any_personality` | For any `BalancedPersonality` weights, the bot cannot have a state where (a) combat is winnable, (b) HP is sufficient, (c) no guard is active, and (d) `goals_tried` does NOT contain `GrindCharacterXP`. |

**Deliverable:** `formal/Formal/LivenessChain.lean`. The `LIV-001` axiom budget
expands to cover the eventual-reachability claims as needed (per-axiom user
signoff).

---

## Differential gate evolution

Each phase adds at least one `formal/diff/test_<module>_diff.py` that:

1. Hypothesis-tests the Python implementation against the Lean oracle on random inputs.
2. Pins 5+ literal examples mirroring the Lean theorem hypotheses.
3. Mutation testing: at least 6 mutants per module survive ≤ 0 (every mutant
   detected by the diff).

Gate enforcement: `formal/gate.sh` extended with new module names; CI fails if
any module loses a previously-proved theorem.

---

## Success criteria for shipping each phase

| Gate | Pass condition |
|---|---|
| `lake build` | 0 errors, 0 warnings |
| Axiom check | No new non-mathlib axioms outside per-module signoff |
| Differential tests | 0 failures, 0 skipped, Hypothesis examples ≥ 200/test |
| Mutation tests | 100% kill rate on the new module's mutation list |
| Python suite | 2623 passing → must grow as new tests added; no regression |
| Pre-commit | mypy strict, ruff bug-finder, full pytest pass |

---

## Out of scope for this plan

- Animation / TUI rendering correctness.
- Network retry / cooldown handling (separately proven by `ActionCostNonneg`).
- Bank capacity formulas (`InventoryCaps` is already proven).
- Multi-character coordination (no current product surface).

---

## Status

| Phase | Status |
|---|---|
| G1 GearPolicy.lean | CLOSED (8a67ad8) |
| G2 PurposeRouting.lean | CLOSED (8efa10b) |
| G3 CombatTargetExistence.lean | CLOSED (11bc90c) |
| G4 ActionApplicability.lean | CLOSED (ca35cbf) |
| G5 StepDispatch.lean | CLOSED (2c01fb7) |
| G6 LivenessChain.lean | CLOSED (this commit) |

## Outstanding work past Phase G6 — CLOSED

| Item | Closed by |
|---|---|
| Python port: `PurposeRouting.combatScore` augmented score | `cd5f6aa` |
| Python gather picker: `pick_gather_loadout` | `4228809` |
| Diff harness for G6 (liveness regression gate) | `c46b9bd` |
| REST_FOR_COMBAT guard (runtime bridge for picker/applicability) | `d2b1aed` |
| Ranking-layer Lean bridge (`RankingComposition.lean`) | this commit |

Composition correctness work for this surface is complete. Future
extensions (a full proof of the arbiter ladder as a Lean inductive,
a kernel-bound diff between the Python `_value` and the Lean `value`
composite, an enrichment of the `LivenessInputs` model to cover
multi-cycle scenarios) live in their own plan when scoped.
