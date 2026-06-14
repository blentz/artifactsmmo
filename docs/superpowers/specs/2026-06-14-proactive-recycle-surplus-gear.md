# Proactive Recycle of Surplus Gear

**Date:** 2026-06-14
**Status:** Design — approved approach (proactive recycle goal)
**Topic:** Recover crafting materials from surplus/obsolete craftable equipment by recycling it during idle time, instead of letting it pile up and get DELETED under space pressure.

## Problem

Trace `play-trace-Robby-20260614-122022.jsonl` cyc 63: `Delete(copper_helmet×9)` (`DiscardOverstock`). Those 9 helmets = 54 `copper_bar` of recoverable material, **destroyed**. The over-gathering investigation proved the bot re-gathers copper_ore from scratch while sitting on (then discarding) gear that holds the very materials it needs.

Recycle-at-discard-time is infeasible: `DiscardOverstock` only fires when the bag is **near-full** (≥0.85), but recycling *adds* items (9 helmets → ~27 bars, net +18) and `RecycleAction.is_applicable` correctly rejects when `inventory_free < net` (server HTTP 497). So recovery must happen **before** the bag fills.

## Design — `RecycleSurplusGoal` as a discretionary means

A new low-priority discretionary means `MeansKind.RECYCLE_SURPLUS`, sibling to `SELL_IDLE`: when the bot is **not** under space pressure and holds **surplus recyclable gear**, recycle it to recover materials (which then flow to the bank/objective). Fires proactively during idle cycles, so there is room for the recovered materials and the delete-at-full state is never reached.

### Trigger (`means._fires(RECYCLE_SURPLUS)`)
Fires iff ALL:
- `_used_fraction(state) < SELL_PRESSURE_FRACTION` — idle/low-pressure only (recovery needs room; under pressure the existing deposit/discard guards handle it).
- There exists a **recyclable surplus item**: a craftable EQUIPPABLE item (`type_ ∈ ITEM_TYPE_TO_SLOTS`, has a `crafting_recipe` + `crafting_skill`) held **above its useful cap** (the equippable swap-pool floor of 1, via `inventory_caps.useful_quantity_cap`), that is NOT committed objective gear/tools (`ctx.target_gear | ctx.target_tools`), with the crafting skill level met and a known workshop.

### Goal (`RecycleSurplusGoal`)
- `value`: a low discretionary priority (≈ `SELL_IDLE` band — below objective work, above `WAIT`). Housekeeping, never preempts gear/task progress.
- `is_satisfied`: no recyclable surplus remains.
- `relevant_actions`: one batch `RecycleAction(code, qty=fit, workshop)` per recyclable surplus item, where `fit` = largest quantity whose recovered-material net fits `inventory_free` (reuse `RecycleAction.is_applicable` to gate; recover what fits this cycle, the rest next idle cycle after the recovered mats are deposited).
- `desired_state`: `{"surplus_gear_recycled": True}` (planner sentinel, mirrors DiscardOverstock).

### Protection (never recycle)
- Committed objective `target_gear` / `target_tools` (the boots you're building).
- Currently-equipped items.
- The useful floor (keep 1 spare per craftable equippable for the optimizer swap pool — same floor `DiscardOverstock` respects).

### Material accounting
Reuses the existing `RecycleAction` (`apply` mints `max(1, mat_qty*qty//2)` per ingredient — the documented ~half heuristic; the live server returns the actual `details.items`). Recovered materials enter inventory, then existing `DepositInventory`/objective consumption routes them to the bank / the gear chain.

## Integration
- `MeansKind.RECYCLE_SURPLUS` added to `DISCRETIONARY_ORDER` (placed adjacent to `SELL_IDLE`; recycle-for-materials vs sell-for-gold — order TBD by test, default after SELL_IDLE so selling for gold is tried first when both apply).
- `_fires` predicate in `means.py`.
- `map_means(RECYCLE_SURPLUS)` → `RecycleSurplusGoal` in `strategy_driver.py`.
- Factory already builds `RecycleAction`s for equippable craftables excluding objective gear — the goal's `relevant_actions` builds its own batch actions (like `DiscardOverstock`), so no factory change required.

## Error handling (CLAUDE.md)
Pure decision logic + the existing `RecycleAction` (which already maps server errors via `_raise_for_error`). No defaulting over missing game data; a recyclable item with no known workshop/skill simply does not fire. No `except Exception`, no inline imports.

## Testing (0/0/0/100%)
- `_fires`: fires on surplus copper_helmet (idle, skill met, workshop known, not objective); does NOT fire under pressure, when the only surplus is objective gear, when skill too low, or when no workshop.
- `RecycleSurplusGoal.relevant_actions`: emits `RecycleAction` (not `DeleteItem`) for surplus copper_helmet; `fit` quantity respects `inventory_free`; excludes objective gear.
- `value` ranks in the discretionary band (below GATHER_MATERIALS, above WAIT).
- `map_means` wiring + `active_means` includes it when fired.
- Regression: `DiscardOverstock` unchanged (still deletes truly-worthless / non-recyclable surplus).

## Out of scope (YAGNI)
- Recycling non-equipment craftables (consumables/intermediates).
- Deposit-then-recycle chaining under pressure (the proactive trigger avoids the full-bag case).
- Changing the ~half recovery heuristic (verify against live `details.items` separately).
