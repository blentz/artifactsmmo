# Stop at the achievable step — design

**Date:** 2026-08-14
**Branch (proposed):** `fix/route-to-achievable-step`
**Status:** approved design, pre-implementation

**Follows:** `2026-08-13-planner-batching-and-macro-edges-design.md`, which
caused the regression this repairs.

---

## Problem

The planner has a mechanism for exactly the situation it keeps failing in:
when a goal is too big to plan, plan the deepest *achievable* prerequisite
instead and let the macro chain emerge across cycles. It is
`_gather_goal_for_unreachable_equippable` (`ai/strategy_driver.py:457`), built
on the proved cores `actionable_step`
(`formal/Formal/StrategyTraversal.lean` `actStep`) and `gather_step_target`
(`formal/Formal/StepDispatch.lean` `gatherTarget_*`).

**The gather-batching branch disabled one of its two triggers.**

`_equippable_goal` (`:589`) routes to that helper only when
`UpgradeEquipmentGoal.is_plannable` is False. That predicate compares
`min_plan_length` against `max_depth = 32`. Task 3 of the previous branch
switched `min_plan_length`'s mint term from raw units to batched steps, and the
whole-branch review then measured the consequence over all 321 recipes in
`formal/sim/game_data_snapshot.json`: **maximum 15, zero exceeding 32.**

So `is_plannable` can never return False on real data, and this routing site is
unreachable in production. The previous branch recorded this as a residual but
did not connect it to the live symptom.

### Measured evidence

From the from-scratch `greater_wooden_staff` state (no `spruce_plank` banked):

```
actionable_step(ObtainItem('greater_wooden_staff', 1))
    -> ObtainItem(code='spruce_wood', quantity=10)
is_plannable(...)  -> True
```

The traversal already computes the right answer. "Gather 10 `spruce_wood`" is
the achievable interim step. But because `is_plannable` is True, the arbiter
plans `UpgradeEquipment(greater_wooden_staff)` instead — a 100,080-node search
taking ~49.5 s against a 15 s budget, which times out, emits
`objective_unplannable`, and falls through to a combat grind.

### Why only one site broke

Two call sites route to the helper. `:347` (the `GEAR_REVIEW` guard) triggers on
**materials not in hand**, which still fires correctly. Only `:589` uses the
depth bound. That asymmetry is why gathering still happens live on some paths
while the objective-step path times out.

---

## Goal

Restore stop-at-the-achievable-step on a trigger that actually fires, by asking
the traversal directly instead of asking a proxy for it.

### Non-goals

- **An acquisition-aware admissible heuristic.** Designed and costed during this
  investigation: `h` would sum minimum edge costs (Gather `6.0`/unit, Craft
  `5.0`/run, Withdraw `2.0` flat) over the remaining closure, raising the staff
  root's `h` from a flat 50.0 to ~447. Admissible and consistent by
  construction, because every term is the floor of the exact edge that
  discharges it. **Deferred:** it makes a search cheaper that this design stops
  performing at all. Reconsider only if a single interim step is itself
  expensive.
- **Differential heuristics** (landmark precomputation plus the triangle
  inequality, per redblobgames). A good fit in principle — items like `iron_bar`
  and `spruce_plank` recur across many recipes, so `|d(L, goal) − d(L, state)|`
  would be genuinely informative. Same reason for deferral, plus it needs a
  landmark-selection policy and a precomputation store. Recorded as the
  strongest option if the heuristic work is ever revived.
- **Changing `min_plan_length` or `max_depth`.** The bound is sound; it is
  simply loose. Tightening it would restore the old trigger by accident rather
  than by design, and `min_crafts`' inventory-blindness (a residual of the
  previous branch) would still make it a proxy rather than an answer.

---

## Design

### The trigger becomes the step itself

In `_equippable_goal`, replace the `is_plannable` gate with a direct question:
**is the deepest achievable node the goal itself?**

```python
step = actionable_step(ObtainItem(code=code, quantity=1), state, game_data, ctx)
routable = (step is not None and isinstance(step, ObtainItem)
            and step.code != code)
if not routable:
    return upgrade                      # the root IS the actionable step
return _gather_goal_for_unreachable_equippable(code, state, game_data,
                                               upgrade.max_depth, ctx, step=step)
```

The helper already applies precisely this test internally (`:498`). It gains an
optional `step=` parameter so the traversal runs once per decision rather than
twice; passing nothing preserves today's behaviour for the `:347` caller.

`is_plannable` is **not** removed. It remains a waste-avoidance filter over a
lower bound, which is what its docstring now says it is. It simply stops being
the routing trigger.

### Why this self-corrects where the depth bound could not

The old trigger was a proxy for "too big to plan". The step is the direct
answer, and it moves with the state in all three cases:

| State | `actionable_step` | Routes to |
|---|---|---|
| Materials missing | `spruce_wood×10` | `GatherMaterials` — plans in ~2 nodes |
| Materials banked | root (a ready WITHDRAW source leafs the node) | `UpgradeEquipment` — withdraw, craft, equip |
| Materials carried | root (`is_satisfied`) | `UpgradeEquipment` — craft, equip |

No threshold to tune and no bound to rot. **The craft cannot be starved:** the
moment every direct prerequisite is satisfied — from inventory *or* bank — the
traversal returns the root and `UpgradeEquipment` is planned.

### Degenerate cases are already handled

`actionable_step` returns `None` when the chain is cyclically blocked or every
branch dead-ends, and may return a non-`ObtainItem` node. The helper already
falls back to `GatherMaterials(code, direct recipe)` for both (`:504-508`). The
new call site must route on the same predicate the helper uses, so the two
cannot disagree — a mirrored-predicate split is the failure `ai/gather_skill_gate.py`
exists to document.

---

## Formal

**No new proof obligations.** The helper's admissibility argument already exists
at `:489-493` and is unchanged: the routed step is a genuine prerequisite on the
root's recipe path and never harder than the declined root, so a reachable root
is never abandoned. This design changes *when* that argument is invoked, not
what it claims.

`select_pure` and `ArbiterSelect.lean` are untouched — the change is upstream of
goal selection, in how a chosen step maps to a goal.

The six gate scripts and the new `check_proof_citations.sh` must pass. Any
citation added by this work must name a declaration or module that exists.

---

## Testing

**Acceptance (the epic's actual target).** From the from-scratch staff state,
`_equippable_goal` must return exactly

```
GatherMaterials(spruce_wood, {spruce_wood:10})
```

— measured by running the helper against that state during design — and that
goal must plan within the 15 s budget without timing out. Today the same state
yields `UpgradeEquipment` and 100,080 nodes / ~49.5 s.

Assert the goal's `target_item` and `needed` rather than its class alone: a
class-only assertion would pass against a routing that picked the wrong step,
and `gather_step_target` is free to transform what `actionable_step` returned.

**The test must discriminate**, proven both ways: with the trigger reverted to
`is_plannable`, it must fail. This branch's predecessor shipped a fix whose test
stayed green with the defect reinstated, and a whole-branch sweep found the
acceptance test itself passed identically before and after the work. Prove the
ablation and paste both outputs.

**Also pinned:**

- materials banked → `UpgradeEquipment`, not a gather (the anti-starvation case)
- materials carried → `UpgradeEquipment`
- cyclically-blocked chain → direct-recipe fallback, not a crash
- the `:347` `GEAR_REVIEW` caller is unaffected by the trigger swap — it never
  used `is_plannable` to decide routing — but it IS changed by the root-by-name
  guard: `map_guard` now falls through to `committed` when
  `_gather_goal_for_unreachable_equippable` returns `None` for a root-by-name
  result (`test_gear_review_root_by_name_falls_through_to_committed`)
- `actionable_step` is evaluated once per decision, not twice

**Runtime activation.** Green tests are not enough here. A live `plan` on a
character whose gear target lacks materials must show a batched gather leg
rather than `objective_unplannable` naming the equippable.

---

## Residuals

- **`is_plannable` remains live-dead as a rejector** (max 15 vs threshold 32,
  0 of 321 recipes). This design stops depending on it, but does not repair it.
  Fixing it means an inventory-aware `min_crafts` — carried from the previous
  branch, with the `steel_boots` 3-tier chain as its reproducer.
- **The from-scratch search is still slow if anything ever plans it directly.**
  This design routes around it rather than fixing it. The deferred heuristic
  work above is the lever if that changes.
- **Cross-cycle latency.** Reaching a deep target now takes one decide cycle per
  chain level. That is the intended macro/micro split documented at `:485-487`,
  but it is slower in wall-clock than a single correct plan would be — the
  trade this design accepts in exchange for never timing out.
- **Two of the three root-by-name equippables remain unsolved.** Measured on the
  real 321-recipe bundle with an empty bank, `wooden_staff` is fixed (5,839
  nodes / 0.50 s, restored from 102,286 / 11.0 s), but `feather_coat` (81,690
  nodes / 15.3 s) and `leather_gloves` (47,288 / 15.2 s) exceed the budget with
  `plan_len 0` **with or without** the `_gather_step_target_is_root` guard.
  The guard is NEUTRAL for those two — it is not a fix for them, and saying so
  is the point: only `wooden_staff` is actually faster direct.
- **A bank-only recipe-less equippable can reach the direct-recipe fallback.**
  `map_guard`'s GEAR_REVIEW branch makes none of the guarantees `_equippable_goal`'s
  `if recipe:` guard does: `find_upgrade_target` can surface a BANK-ONLY item via
  `_find_inventory_upgrade`, the GEAR_REVIEW gate checks `state.inventory` but not
  the bank, and `_materials_in_hand` requires `bool(recipe)`. Such an item reaches
  the fallback with `recipe = {}`, yielding `GatherMaterialsGoal(code, {})`.
  Harmless — that goal's `is_satisfied` short-circuits True for a target held in
  inventory or bank when the target is not itself a key of `needed`, so it fires
  zero actions rather than a wrong one — but it is a path the fallback was not
  written for, and 46 of the real equippables have no recipe.
- **`step == root` does not imply the root is plannable inside the budget.** The
  design premises the fall-through arm on a satisfied root being cheap to plan.
  Live on R2D2 (level 16), `actionable_step` returned
  `greater_wooden_staff` itself, so this design routed to `UpgradeEquipment`
  directly — and that search still ran out the budget:
  `nodes=2312 depth=8 plan_len=0 TIMED_OUT`. The same target on C3P0 planned in
  7 nodes and on HAL in 4. This is NOT a regression — the trigger it replaced
  returned `upgrade` unconditionally, so the pre-branch tree took the identical
  branch — and the arbiter recovered on the next-ranked root rather than falling
  through to a grind. But the premise is not universal, and the from-scratch
  search residual above is the lever.
- **The gather arm is not reachable on any current live character without a
  diagnostic injection.** On all five live characters the top-ranked gear root's
  `actionable_step` IS the root itself, so an undoomed live run exercises only
  the anti-starvation arm. Reaching the routed gather required seeding the arbiter's
  doomed-memo (`plan --doom`) to reproduce the in-memory suppression that occurs
  live only after those goals have already failed once. The runtime evidence for
  the routed arm is therefore a suppression-reproduced live run, not a
  spontaneous one — weaker than the anti-starvation half, and named as such.
