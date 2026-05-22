# Goal Tiers — P3a.2: Reachability of Obtain-Leaves

Date: 2026-05-22
Status: Approved (design)

A focused refinement of P3a/P3a.1 (still shadow mode, no behavior change),
fixing the unreachable-gear bug the shadow trace exposed.

## Goal

Stop the strategy engine from selecting gear it can never obtain. A root is a
valid candidate only if its **entire** prerequisite chain bottoms out in
**obtainable** leaves (craftable or gatherable); otherwise it is unreachable and
excluded — exactly like a cyclically-blocked node. Still shadow-only.

## Problem (from the shadow trace)

P2's `prerequisites(ObtainItem)` returns `[]` for an item with no known
production path (no recipe, no resource drop — e.g. a boss/event drop). P3a's
`actionable_step` treats any node with no unmet prerequisites as actionable, so
such items look like a ready, cost-1 "free grab". Observed at L1: the engine
chose `ObtainItem(corrupted_crown)` (cost 1) over the best **craftable** weapon
`hell_reaper` (contribution 0.49, cost 9) — chasing an item it cannot make.
Several targets (`backpack`, `burn_rune`, `corrupted_skull`, …) showed the same
cost-1 phantom-actionable pattern.

## Design

All changes are in `src/artifactsmmo_cli/ai/tiers/strategy.py`.

### `_producible(code, game_data) -> bool`
An item is producible by known means when it is **craftable**
(`game_data.crafting_recipe(code) is not None`) or **gatherable** (some resource
drops it: `code in game_data._resource_drops.values()`). (Buying / monster-drop
sourcing is out of scope — those items read as not-producible for now.)

### `is_reachable(node, state, game_data) -> bool` (cycle-safe, full closure)
- Already satisfied → `True`.
- Cycle (node revisited) → `False` (a cycle can't bottom out).
- `ReachSkillLevel` → `True` (grinding the skill is always an available action).
- `ReachCharLevel` / `ObtainItem` → reachable iff **all** direct prerequisites
  are reachable; for an `ObtainItem` **leaf** (empty prerequisites and unmet),
  reachable iff `_producible(code, game_data)`.

This walks the prerequisite graph (via `prerequisites`) with a visited-set; a
craftable item is reachable only when every material in its chain is ultimately
producible.

### `actionable_step` guard
In the base case, before returning a node with no unmet prerequisites: if it is
an unmet `ObtainItem` that is **not** `_producible`, return `None` instead of the
node. So `actionable_step` never reports an unobtainable leaf as the step, even
when called standalone.

### `decide` candidate filter
In the candidate loop, after skipping satisfied roots, skip roots where `not
is_reachable(root, state, game_data)` (before computing the step/score).
Unreachable gear targets (drop-only endgame items) drop out of `ranking`
entirely; the best **reachable** gear (e.g. `hell_reaper`) wins its slot.

### Unchanged
Cost model (P3a.1 distance + instrumental tiebreak), contribution, HP-interrupt
flag, `desired_state_of`, the shadow wiring, "no behavior change".

## Error handling
Pure, no API. `is_reachable` terminates via the visited-set. An entirely
unreachable objective (no producible gear, all skills are still reachable as
grind leaves, char level reachable if combat-capable) still yields a non-empty
decision from the skill/level roots.

## Testing
Success per project standard: 0 errors, 0 warnings, 0 skipped, 100% on changed code.

- **`_producible`:** craftable → True; gatherable (resource drops it) → True;
  unknown (no recipe, no drop) → False.
- **`is_reachable`:** gatherable item → True; craftable item whose materials are
  all gatherable → True; unknown-source item → False; craftable item with one
  material that is unobtainable → False; `ReachSkillLevel` → True;
  `ReachCharLevel` combat-capable → True; under-equipped with an unobtainable
  best weapon → False; satisfied node → True; cyclic recipe → False.
- **`actionable_step`:** returns `None` for an unmet, non-producible
  `ObtainItem`; still descends to the producible leaf for a craftable chain
  (existing test holds).
- **`decide`:** an unobtainable best-in-slot item is excluded from `ranking`;
  the best craftable item for another slot is chosen over it; skill/level roots
  still present. Reproduce the trace shape: an unobtainable cost-1 gear target
  no longer wins.
- Existing P3a/P3a.1 tests still pass (copper_dagger is craftable → reachable).

## Files
- Modify `src/artifactsmmo_cli/ai/tiers/strategy.py` — `_producible`,
  `is_reachable`, `actionable_step` guard, `decide` filter.
- Modify `tests/test_ai/test_tiers_strategy.py`.

## Out of scope
- Buy-from-NPC / monster-drop sourcing as obtainable paths (a later phase could
  add these; until then those items read as unreachable and are skipped).
- P1 targeting best-*attainable* gear (it still targets best-in-game; the
  strategy simply never pursues the unreachable ones).
- Driving behavior (P3b), economy/tasks (P3c).
