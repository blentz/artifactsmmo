# Design: Eliminate recurring craft-chain re-search (copper_ring churn + plan caching)

**Date:** 2026-06-22
**Status:** DESIGN (build deferred to a focused follow-up — user chose "design now, build next")
**Origin:** C4 follow-up. `GatherMaterials(copper_ring, {copper_ring:3})` re-searched
~52K GOAP nodes 114× in the original trace — re-planned from scratch every cycle.
User question: *"can we cache common plan chains so we don't keep recalculating them?"*

## Problem

The planner executes only `plan[0]` each cycle then re-plans from scratch
(`player.py:522`; the arbiter's `select_pure` calls `try_plan` on the committed
goal every cycle). For a deep craft goal this means re-running the SAME expensive
A* search every cycle just to extract the next action.

`copper_ring×3` closure: `copper_ring → {copper_bar:6} → {copper_ore:10}` =
**180 copper_ore → 18 copper_bar → 3 copper_ring**. The A* explores ~52K nodes
(each node issues a LearningStore SQLite query under `--learn`) to (re)derive a
~200-action sequence — every cycle while committed.

## Key insight (reframes the fix)

A recipe-craft plan is **deterministic from the recipe**. `closure_demand` already
computes the full material demand; the action order is a topological sort of the
recipe DAG (gather/buy raw leaves → craft intermediates bottom-up → craft target).
The A* is **rediscovering structure that the recipe already encodes**. So the
cleanest fix is not to *cache search results* but to **not search at all** for
recipe-craft goals: generate the plan directly from the closure in O(closure),
not O(52K nodes).

This also dissolves the hardest part of naive plan-caching — **invalidation**.
Re-generating a deterministic plan from current state each cycle is cheap
(O(~200) pointer-chasing, no SQLite), so there is no stale-cache to invalidate:
the "cache" is the recipe itself, always current.

## Options

### A. Recipe-directed plan generator (RECOMMENDED core)
For a `GatherMaterialsGoal` whose target is craft-assembled, build the action
sequence directly:
1. `net = closure_demand(needed) - owned(inventory+bank)` per item (skip what's
   already held — fewer actions).
2. Topologically order the closure DAG: leaves (raws) first, then each
   intermediate once its inputs are scheduled, target last.
3. Per leaf, choose a source via the EXISTING proved decisions:
   - gatherable raw → `GatherAction` (×net, batched by per-gather yield);
   - monster-drop → `Fight` (the proved monster-drop selection);
   - currency-buy leaf → `NpcBuy` (affordability already gated by C4
     `currency_afford_plannable_pure`; unaffordable ⇒ is_plannable prunes, so the
     generator is only reached for affordable/owned leaves);
   - craft-from-recipe → `CraftAction` after its inputs.
4. Respect skill gates (skip/prune if a craft's skill < recipe level — the
   existing `gather_plannable_pure` fast-fail already prunes these before we
   generate).
- **O(closure)**, no A*, no SQLite-per-node. Fixes the churn at the root.
- **Provable core:** `generate_craft_plan(closure, owned, sources) -> [Action]`
  is a deterministic function. Theorems: (validity) executing the sequence raises
  each `needed` item to its target; (ordering) no `CraftAction` precedes its
  inputs being available; (no-waste) net-of-owned ⇒ no over-gather. A genuine
  Lean component (mirrors the C1–C4 pattern), differential + mutation gated.
- **Fallback:** goals the generator can't classify (combat targeting, pathing
  choices, multi-source optimization where cost matters) fall back to GOAP A*.
  The generator handles the *deterministic recipe-assembly* majority; A* remains
  for genuinely-search-needing goals.

### B. Plan-following (cache the in-flight plan) — complementary, for NON-recipe goals
Cache the committed plan; execute its actions in sequence; re-plan only when the
plan is exhausted or `plan[0]` is no longer applicable (state diverged). Needed
ONLY for goals where the plan isn't deterministically regenerable (so we can't
use A). Carries the invalidation burden:
- Invalidate on: `plan[0].is_applicable` false, an HP/guard preemption, a fight
  loss / unexpected inventory or cooldown delta, the committed goal changing.
- Guards must still preempt mid-plan: the arbiter's guard-precedence check
  (`select_pure`) runs FIRST every cycle; plan-following only short-circuits the
  committed-goal `try_plan`, never the guard tier.
- Higher risk (a stale plan executes a wrong action). Defer unless A leaves a
  meaningful non-recipe re-search cost.

### C. Macro / pattern caching (the user's idea) — optional optimization LAYER
Cache recurring sub-plan chains keyed by a normalized pattern (e.g.
`make(copper_bar, 1) = [Gather(copper_ore)×10, Craft(copper_bar)]`), reuse across
goals/episodes, persist in the LearningStore. With **A** in place this is a
*minor* win (generation is already cheap), but it helps if generation itself ever
becomes hot, or to share learned monster/source choices. Keep as a follow-on; A
delivers most of the value without the cache-coherence complexity.

## Recommendation
Build **A (recipe-directed generator)** as the core — it fixes copper_ring (and
every deep craft chain) at the root, is the cleanest answer to "don't
recalculate," and is formally gateable. Add **C (pattern cache)** later only if
profiling shows generation is hot. Reach for **B (plan-following)** only for a
measured non-recipe re-search cost. This ordering minimizes the safety-sensitive
invalidation surface.

## Integration points
- `GatherMaterialsGoal` planning / the arbiter's `try_plan` for craft-target
  steps: route to the generator; fall back to `GOAPPlanner` when the generator
  returns "can't generate" (non-recipe / search-needed).
- Reuse existing machinery: `recipe_closure.closure_demand`, the per-leaf source
  decisions in `relevant_actions` / `acquisition_method` / proved monster-drop
  selection, the affordability gate (`currency_afford_plannable_pure`), the
  skill-gate fast-fail (`gather_plannable_pure`).
- `player.py` loop unchanged (still executes `plan[0]` then re-plans) — but the
  re-plan is now O(closure) generation, not O(52K) A*. (B would change this loop;
  A does not.)

## Formal boundary (build-next)
- New proved core `craft_plan_core.py::generate_craft_plan_pure(closure_dag,
  owned, source_choice) -> list[ActionSpec]` + Lean `Formal/CraftPlanGen.lean`:
  - `validity`: post-execution owned ≥ needed for every target/intermediate.
  - `topological`: every CraftAction's inputs are produced earlier in the sequence.
  - `no_surplus`: net-of-owned ⇒ generated quantities never exceed demand
    (ties to the [[project_gear_demand_economy]] no-surplus result).
  - differential (Python generator ≡ Lean) + mutation, ≥100% unit coverage.
- Source-choice (gather vs buy vs fight) reuses ALREADY-proved decisions — the
  generator composes them, it does not re-decide them.

## Risks / open questions (resolve at build time)
1. **Source optimization the A* did for free:** A* implicitly picks cheapest
   sources / shortest paths. The generator needs an explicit source policy
   (prefer gather, then cheapest buy, then winnable fight) — must match or beat
   what the bot currently does. Validate against live traces.
2. **Pathing / movement:** generation produces logical actions; movement is
   folded into each action's apply/execute (as C3 verified for ACTIONS_PER_CYCLE).
   Confirm no separate path-planning is lost.
3. **Where A* must remain:** combat target selection, multi-source tradeoffs,
   anything with a genuine choice the recipe doesn't determine. Keep the fallback
   robust; measure how often it triggers.
4. **Interaction with the two-pass arbiter + DoomedMemo:** a generator-served
   goal should bypass the cheap/full A* budget tiers cleanly.

## Build plan (next session, subagent-driven + formal gate)
1. Extract the recipe-DAG topological-order + net-of-owned demand into a pure
   core; prove validity/topological/no_surplus in Lean; differential + mutation.
2. Implement the per-leaf source assembly reusing existing proved decisions.
3. Route craft-target GatherMaterials planning to the generator with A* fallback;
   wire `try_plan`.
4. Live-trace validation: copper_ring search nodes → ~0 (generation), plan
   correctness unchanged; confirm the bot still makes the rings.
5. (Optional, later) C: pattern cache in LearningStore.

## Out of scope
- Full plan-following (B) unless a measured non-recipe re-search cost remains.
- Pattern cache (C) until generation is shown hot.
