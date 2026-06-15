# PLAN: Prove the recent fixes + level-50 planner-liveness roadmap

Status: Phase 0. 2026-06-15. Branch feat/prove-grind-liveness.

## Long-term goal
Prove the AI planner **always progresses to character level 50 from any reachable
state** — no deadlock, every objective eventually plannable. This is a LIVENESS
program: not "the decision is correct" (safety, mostly done — 39 components) but
"a forward action always exists and the measure strictly decreases."

## The liveness obligation chain (roadmap)
Reaching level 50 decomposes into obligations; ✓ = proven, ◐ = partial, ○ = open.

1. ◐ **Combat always has a winnable target** when one exists (WinnableCascade ✓
   safety; the *existence* over the level ladder is partly in LivenessAudit).
2. ◐ **Char-XP grind terminates** — `cheapest_path_to_level` (CheapestPath ✓) bounds
   cycles; the per-cycle measure decrease across the real loop is ○.
3. ◐ **Skill-gated gear never deadlocks the grind** — the skill-step dispatch
   (SkillStepDispatch ✓ safety + forward_progress) yields a grind whenever a
   feasible relaxed candidate exists. THE FIXES below widen this to "never freeze
   while any in-skill craftable exists, even once all targets are owned".
4. ○ **Every needed material is obtainable** — gather (skill-gated), craft
   (recipe closure ✓), monster-drop (THE FIX below makes combat-for-drops
   plannable; the reachability theorem is added here).
5. ○ **The objective measure strictly decreases each committed cycle** (the
   global termination argument) — the big open piece; future work.

This plan closes the proof debt of the 2026-06-15 fixes (obligations 3 & 4) and
records the rest as the roadmap.

## Proof targets (this plan)

### A. Grind-ladder flag computation (closes obligation 3 extension) — DONE 2026-06-15
Component 40 `GrindLadder` shipped: extracted `dispatch_candidate_flags` /
`cannibalize_pure`; proved `flags_exempt`, `flags_cannibalize`,
`grind_when_unowned_target`, `grind_when_all_owned`; Manifest + Contracts pins;
2 differentials (700 examples); 5 mutants killed. The rest of this section is the
record of what was built.

The fixes added the exemption (unowned same-skill craftable-now TARGET is
grindable despite reservation) and last-resort cannibalization (all feasible
owned ⇒ free the relaxed pass) — currently UNPROVEN impure hoisting in
`_skill_dispatch_candidates`.

- **Extract** `dispatch_candidate_flags(recipe_mats, reserved_full,
  reserved_relaxed, craft_level, current_level, is_target, owned, cannibalize)
  -> (uses_reserved_full, uses_reserved_relaxed)` (pure, per-candidate) and
  `cannibalize_pure(candidates) -> Bool` (all feasible owned).
- **Lean** `Formal/GrindLadder.lean`: model `flagsFor` + `dispatchFromRaw`
  (compute flags → `dispatch`). Theorem roles:
  - `flags_exempt` — an unowned, in-level target gets both flags false.
  - `flags_cannibalize` — when `cannibalize`, every candidate's relaxed flag is false.
  - `grind_when_unowned_target` (LIVENESS) — ¬suppressed ∧ ∃ feasible unowned
    target ⇒ dispatch = grind. (Composes with forward_progress.)
  - `grind_when_all_owned` (LIVENESS) — ¬suppressed ∧ feasible nonempty ∧ all
    feasible owned ⇒ dispatch = grind. The "never freeze once you own one of
    everything" guarantee (the cannibalization backstop).
- **HONEST scope**: never-freeze is NOT unconditional — an unowned NON-target
  throwaway whose mats are all relaxed-reserved still freezes. The two theorems
  state exactly the cases the ladder guarantees; the gap is documented, not hidden.

### B. Fight-drop reachability (closes obligation 4, monster drops) — DONE 2026-06-15
Component 41 `MonsterDropApply` shipped: extracted `apply_monster_drops_pure`;
per-key `Inv` model; proved `applyDrops_monotone` + `fight_drop_reachable`;
Manifest + Contracts pins; differential (400 examples); 3 mutants killed.

- **Lean** theorem `fight_apply_increments_drop` (over the gather-core composition):
  fighting a monster that drops item X, with inventory not full, yields
  `count(X)` strictly greater than before — so a `feather:N` goal is reachable by
  N fights (the planner can decrease the remaining-need measure).

## Gate
Per component: Manifest roles, Contracts exact-statement pins, oracle JSON kind,
Hypothesis differential binding the EXTRACTED pure cores to the real Python,
mutation coverage, `formal/gate.sh` green. Serialize the gate run; `git diff src`
after ([[feedback_serialize_gate_runs]]).

## Out of scope (roadmap, future plans)
Obligation 5 (global measure decrease across perceive→select→execute→learn) — the
full planner-termination theorem. Obligations 1-2 liveness completions.
