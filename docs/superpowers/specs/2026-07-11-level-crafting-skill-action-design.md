# LevelSkill Action — Design Spec

**Date:** 2026-07-11
**Status:** Approved for planning
**Acceptance criteria:** the crafting-completeness census reports **0 PLANNER_BUG
cells** with the `SKILL_PREREQUISITE` workaround **removed** — i.e. every
under-skill craft cell PASSES because the planner genuinely plans `grind-skill →
craft`, not because it was reclassified.

## Problem / root cause

The GOAP planner treats crafting-skill levels as **immutable during search**:
`WorldState.skills` never changes in-plan. `CraftAction.apply`
(`actions/crafting.py:87-98`) advances only `projected_skill_xp_delta`, never the
skill *level*. No action in the GOAP set raises a crafting skill. Therefore
`CraftAction.is_applicable`'s skill gate (`crafting.py:56-58`,
`skill_level < crafting_level → False`) is **unsatisfiable within a single
search**: from an under-skill state the planner either finds nothing or burns the
whole node budget (the feather_coat 97k-node blowup, trace 2026-06-11 18:10).

Every current skill-grind mechanism is a workaround layered over that one gap:

1. `GatherMaterialsGoal.is_plannable` hard fast-fails under-skill
   (`goals/gathering.py:519-543`) to avoid the blowup.
2. The directed generator returns `None` on an unmet skill gate
   (`craft_plan_gen.py:135-136`).
3. The strategy tree bolts on a *separate* grind objective:
   `ReachSkillLevel` meta-goal (`tiers/meta_goal.py:43-49`) emitted by
   `prerequisite_graph.py:60-71`, dispatched in `strategy_driver.py:782-886` via
   `skill_step_dispatch_pure` (craft one in-skill rung, replan); plus
   `LevelSkillGoal` (`goals/level_skill.py`) for the task-skill-requirement path.
4. The proposed `SKILL_PREREQUISITE` census class (this session, not shipped)
   would have papered over it a fourth time.

The planner **should** be able to plan the full `grind-skill → craft` sequence.
This spec makes the skill gate satisfiable inside the planner and retires the
workaround layers.

## Goal

Add a first-class GOAP action `LevelSkill(skill, target_level)` so the
planner natively sequences skill-grinding before a gated craft, and make it the
**single** skill-grind mechanism (full unification): retire the tree routing,
the `is_plannable` fast-fail, the generator skill-gate `None`-return, and the
census `SKILL_PREREQUISITE` class.

## Non-goals

- Re-implementing grind *execution*. Execution reuses the existing proven
  `GatherMaterials(rung, skill_grind=True)` sub-planner (closure gather, bank
  withdraw, batch sizing, loadout re-arm). The planner becomes the single
  *decider* of grinding; execution machinery is reused.
- Changing the gather-skill / resource-skill grind paths beyond what unification
  requires (gatherable skills self-level via ambient gathering; the `no_grind`
  branch behaviour is preserved through the new action where applicable).
- The recursive purchase-edge (PURCHASE_RECURSION) and grey-farm policy
  (GREY_FARM_SUPPRESSED) classes — those are legitimate and stay.

## The action

New file `src/artifactsmmo_cli/ai/actions/level_skill.py`, one behavioral class
`LevelSkill(Action)`. Identity fields: `skill: str`, `target_level: int`.
`repr` = `LevelSkill(<skill>→<target_level>)`.

**Naming / scope decision (flagged for review):** named `LevelSkill` (not
`LevelCraftingSkill`) because full retirement of `ReachSkillLevel` requires it to
cover **both** crafting-skill gates (`CraftAction`) and gather-skill gates
(`GatherAction`, armed today by `prerequisite_graph.py:66-71`). Same immutability
root cause afflicts both: gather skills are also fixed in-search, so a
resource gated above the current gather skill is equally unplannable. The action
generalizes over `skill` (any of the eight skills); its execution picks the
right grind per skill kind (a craftable rung for crafting skills; a lower-level
gatherable for gather skills — the existing `skill_step_dispatch` `grind` vs
`no_grind` branches). The crafting-skill path is what the census acceptance
criteria exercises (`census_state` grants prerequisite gather skills, so gather
gates never surface as census PLANNER_BUG); the gather-skill path exists so P3
can retire `ReachSkillLevel` wholesale without regressing gather-skill grinds.

**Target parameterization.** `build_actions` emits one `LevelSkill(skill, L)` per
distinct `L` that is a `crafting_level` (or gather `resource_skill_level`) of some
obtainable item/resource in that skill — a small, deduped, bounded set per skill.
A* / the generator then select the exact `LevelSkill(skill, recipe.crafting_level)`
that satisfies a given gated `CraftAction(target)`, since that craft needs
`skills[skill] ≥ target.crafting_level`.

- **`is_applicable(state, game_data)`** → `True` iff
  `state.skills.get(skill, 1) < target_level` AND a feasible grind exists now:
  for a crafting skill, `skill_grind_selection_pure` finds an obtainable in-skill
  craftable at `crafting_level ≤ current`; for a gather skill,
  `best_gather_resource_drop` finds a gatherable at level ≤ current. A skill with
  no grind at/below current is not grindable from here → not applicable (the
  planner then has no plan; the census classifies that honestly as
  `SKILL_UNREACHABLE`, which remains a legitimate class).
- **`apply(state, game_data)`** → `dataclasses.replace(state, skills={**skills,
  skill: target_level})`. Optimistic single-step effect: the whole grind is
  assumed complete so a downstream `CraftAction(target)` is applicable *in the
  simulated plan*. All other fields preserved. Mirrors the `FightAction`
  optimistic-apply idiom (mints the end state; execution + replan reconcile).
- **`cost(state, game_data, history=None)`** → the honest grind effort from
  `SkillXpCurve`: `total_xp_to_reach(current, target)` divided by observed
  per-craft yield, times a per-craft cost, floored at the number of grind
  cycles (`≥ (target - current)`). Never free — so A* prefers already-skilled
  routes and never inserts a gratuitous skill jump. When the curve has no
  observations, fall back to a conservative `(target - current) × PER_LEVEL_COST`
  constant so cost stays strictly positive and monotone in the gap.
- **`execute(state, client)`** → see Execution model. Does **one** grind cycle
  and returns the real post-cycle state.

## Execution model (reuse grind sub-planner)

`LevelSkill` is a planner-facing abstraction; at execution it expands to
one cycle of the existing grind sub-planner:

1. The player detects `plan[0]` is a `LevelSkill`.
2. Pick the grind target via the migrated `skill_step_dispatch` cores — a
   craftable rung for a crafting skill (`grind` branch), or a lower-level
   gatherable for a gather skill (`no_grind` → `best_gather_resource_drop`).
3. Plan `GatherMaterials(rung, skill_grind=True)` through the existing GOAP path
   and execute its first leg (for a gather-skill grind the "rung" is the lower
   gatherable, and the leg is the gather itself).
4. Replan next cycle. `is_applicable` stays `True` while `skills[skill] <
   target`, so `plan[0]` re-derives as `LevelSkill` until the skill reaches
   target, then the plan advances to the gated craft/gather.

This keeps every proven grind-execution behaviour (closure gather, bank
withdraw, batch sizing, loadout re-arm) untouched; only the *routing decision*
moves from the tree into the planner.

## What migrates vs. what is retired

**Retired:**
- `ReachSkillLevel` meta-goal (`tiers/meta_goal.py:43-49`) and its
  `strategy_driver.py:782-886` dispatch branch and hoisters
  (`_skill_dispatch_candidates` 254-310, `_gated_behind_skill` 240-251).
- `ReachSkillLevel` emission in `prerequisite_graph.py:60-71`.
- `LevelSkillGoal` (`goals/level_skill.py`) and its two construction sites
  (`strategy_driver.py:440-442`, `goal_serialization.py:48-52`).
- `GatherMaterialsGoal.is_plannable` under-skill fast-fail
  (`goals/gathering.py:519-543` — the currency-leaf affordability arm stays;
  only the crafting-skill-gate arm is removed).
- The directed generator's skill-gate `None`-return (`craft_plan_gen.py:135-136`).
- `SkillGateFastFail.lean` (is_plannable soundness — the premise is gone).
- The `SKILL_PREREQUISITE` census class (`audit/craft_completeness.py`) and its
  tests.

**Migrates (survives, relocated):**
- `skill_grind_selection.py` / `skill_step_dispatch.py` rung-selection cores and
  their proofs (`SkillGrindSelection.lean`, `SkillStepDispatch.lean`,
  `GrindLadder.lean`) — from tree dispatch to the action's execution helper.
  Re-anchor callers; the Oracle keys (`skill_grind_selection`, `combine_dispatch`,
  `skill_step_dispatch`, `candidate_flags`, `cannibalize`) and their diff/mutation
  gates keep guarding the same pure logic.
- `SkillXpCurve` (`learning/skill_xp_curve.py`, `SkillXpCurve.lean`) — now feeds
  `LevelSkill.cost`.
- `projected_skill_xp_delta` apply hooks (`crafting.py`, `gathering.py`) and
  their Lean semantics (`Liveness/SkillXpSemantics.lean`) — unchanged; still model
  in-plan XP projection for other consumers.

## Lean migration

- **Add:** `LevelSkill` applicability + apply to the action mirror
  (alongside `ActionApplicability.lean`), an Oracle run/key, and a diff+mutation
  gate for the new apply/applicability.
- **Re-anchor:** the surviving selection proofs (`SkillStepDispatch`,
  `GrindLadder`, `SkillGrindSelection`) to the action's execution path; update
  `Manifest.lean` role anchors and `LivenessAudit.lean` axiom prints.
- **Migrate liveness:** `MetaGoalDispatch.lean` (`dispatch_reachSkillLevel`,
  `applyDispatch_reachSkillLevel`) and `Liveness/SkillGapClosure.lean`
  (`skill_prerequisite_reachable`, `skill_gap_then_complete_reachable`) become a
  liveness statement about the action: repeated `LevelSkill` execution
  reaches `target_level`, after which the gated craft is applicable. No vacuous
  hypotheses (per the zero-vacuousness rule).
- **Retire:** `SkillGateFastFail.lean` and its Manifest/audit anchors.

## Phase breakdown (four sequenced sub-plans, each gate-green)

**P1 — Action, inert.** Add `LevelSkill` + `apply`/`cost`/
`is_applicable` + Lean applicability/apply mirror + Oracle key + diff/mutation
gate. A unit scenario proves the planner plans `[LevelSkill, Craft(target)]` from
an under-skill state when the action is in the action set. Audit `skills`-immutable
readers (any code assuming skills never change in-plan) and document/guard.
`is_plannable` fast-fail still present, so nothing routes to it live yet. Ships
inert. Gate: full `gate.sh` (Lean + diff + mutation) + suite.

**P2 — Wire + retire fast-fail.** Emit one `LevelSkill` per grindable
skill from `build_actions`; teach the directed generator to emit it before a
gated craft. Retire `GatherMaterialsGoal.is_plannable` under-skill fast-fail and
the generator skill-gate `None`-return; retire `SkillGateFastFail.lean`.
Under-skill craft goals now plan live. Gate: full `gate.sh` + suite + runtime
`plan <char>` shows `LevelSkill → Craft` for an under-skill target.

**P3 — Retire tree routing.** Remove `ReachSkillLevel` (meta-goal, dispatch
branch, prerequisite_graph emission) and `LevelSkillGoal`. Relocate the
selection cores as the action's execution helper; add the player
execution-expansion hook (plan[0]=LevelSkill → one grind cycle via
`GatherMaterials(rung, skill_grind)` → replan). Migrate `MetaGoalDispatch` /
`SkillGapClosure` liveness to the action. Runtime-verify gear-unlock grinds still
fire (previously armed via `prerequisite_graph → ReachSkillLevel`). Gate: full
`gate.sh` + suite + runtime.

**P4 — Census cleanup.** Delete `SKILL_PREREQUISITE` (class + tests), regen
`docs/craft_completeness/*`, `scripts/gen_craft_completeness.py --check` green
(**planner_bug 0**), keeping located-source / grey-farm / purchase-recursion.
Runtime-verify an under-skill gear target sequences `LevelSkill → Craft` on live
`plan`. Gate: audit suite 100% + census `--check` + full suite.

## Testing

- Each phase TDD (failing test first, per repo rules).
- P1: planner-plans-grind→craft unit scenario; cost monotonicity pin; apply/
  applicability Lean diff + mutation.
- P2: is_plannable no-longer-prunes-under-skill test; generator emits grind leg;
  census re-run shows under-skill cells flip PASS.
- P3: tree no longer emits ReachSkillLevel; execution-expansion drives one grind
  cycle; gear-unlock grind still fires (scenario + runtime).
- P4: census `--check` == 0 planner_bug; `SKILL_PREREQUISITE` symbol gone.
- Whole-epic gate: `gate.sh` (mutation + Lean + `formal/diff`) at P1/P2/P3;
  census `--check` at P4; runtime `plan` verification (green tests ≠ runtime-active).

## Risks

1. **`apply` mutating `skills`** breaks any code assuming skills are immutable in
   search. P1 audits every `state.skills` reader in the decision/apply path and
   the baseline-contract fields before enabling.
2. **`cost` mis-tuning** — too cheap and the planner over-skills; too dear and it
   avoids necessary grinds. Pinned by a cost-monotonicity + scenario test and
   runtime observation.
3. **Gear-unlock re-routing (P3)** — grinds currently armed via
   `prerequisite_graph → ReachSkillLevel` must re-route through the planner
   without regressing gear progression. Runtime-verified on a live under-skill
   gear target.
4. **Proof churn** — the selection proofs are re-anchored, not rewritten; the
   liveness migration must stay non-vacuous. Serialize `gate.sh` runs
   (never concurrent with anything importing src, including the bot).

## Out-of-scope follow-ups

- Fold gather-skill / resource-skill grind arming fully into the action if any
  edge remains tree-routed after P3 (verify none does; else a P5).
- Remove the now-unused `produces_skill_xp` tag if P3 leaves it with no reader.
