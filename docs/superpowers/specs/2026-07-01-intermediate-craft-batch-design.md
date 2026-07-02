# Intermediate-Craft Batching

## Problem

Every craft in the live trace runs at `quantity=1` — including crafting
INTERMEDIATES: `Craft(ash_plank×1)` **×56**, `copper_bar` singly. Each craft is a
separate API call + cooldown. When a plan needs N of an intermediate (bars for
gear, planks for a task), the goals emit the intermediate `CraftAction` with the
factory default `quantity=1`, so the GOAP planner chains N single crafts across N
cycles.

The demand N is already computed: every emitting goal builds a `closure_demand`
`chain` for withdraw/membership and then discards the magnitude, appending the
`quantity=1` action. This is item #1 of the quantity=1 audit (consumable-cook and
potion-buys were #2-and-prior, already merged).

Root cause per goal: `relevant_actions` appends intermediate crafts unchanged:
- `gathering.py:181` (GatherMaterials) — the empirical hot spot
- `pursue_task.py:103` (PursueTask)
- `craft_potions.py:159`, `maintain_consumables.py:82`, `level_skill.py:146`,
  `progression.py:233`
- `craft_plan_gen.py:186` (the A*-avoiding fast path)

## Decisions (locked)

- **Reuse the proven core (DRY):** generalize `task_batch_size_pure`
  (`task_batch.py`, mechanically extracted to `Extracted/TaskBatch.lean`, bridged
  to `TaskBatch.lean`) — do not duplicate the inventory-bounded batch math.
- **All emitting goals** get intermediate-craft batching.
- **Sizing:** full closure demand, capped by inventory space (the exact behavior
  the proven core already implements: `min(demand, inventory_fit, BATCH_CAP)`).

## Design

### Component 1 — generalize the proven batch core (formal)

Extract the code-agnostic core from `task_batch_size_pure`:

```python
def craft_batch_size_pure(code, demand, inventory, inventory_free,
                          recipes, drops) -> int:
    """Runs to craft of `code` in one plan: bounded by `demand` (units still
    needed), the inventory space its raw materials require (counting already-held
    closure drops as free-equivalent), and BATCH_CAP. Floors at 1. Pure core."""
    mats_per_unit = _raw_units(len(recipes) + 1, code, recipes, {}, {})
    if mats_per_unit == 0:            # base/leaf item with no raw inputs
        return max(1, min(demand, BATCH_CAP))
    closure = _closure_visited(len(recipes) + 1, code, recipes, {})
    held_recipe = sum(inventory.get(drop, 0)
                      for _res, drop in drops.items() if closure.get(drop, 0) == 1)
    usable = (inventory_free + held_recipe) - _MIN_FREE_SLOTS
    fit = usable // mats_per_unit
    return max(1, min(demand, fit, BATCH_CAP))
```

`task_batch_size_pure` becomes a thin wrapper that keeps its `items`/type/total
guards, computes `remaining = task_total - task_progress`, and returns
`craft_batch_size_pure(task_code, remaining, inventory, inventory_free, recipes,
drops)`. Its public `task_batch_size(state, game_data)` API and both call sites
(`strategy_driver.py:404`, `factory.py:271`) are unchanged.

**Formal (via the formal-development skill):** the generalization changes the
extracted core, so it must stay bridge-equivalent:
- Update `formal/Formal/Extracted/TaskBatch.lean` to the generalized shape and
  `formal/Formal/TaskBatch.lean` (`batchSize`) hand model accordingly (task path =
  the `demand = remaining` specialization).
- Extend `formal/diff/test_task_batch_diff.py` to differentially cover
  `craft_batch_size_pure` over intermediate codes + the `mats_per_unit == 0` and
  cap/fit boundaries.
- Refresh `formal/diff/mutate.py` anchors so a weakened batch (dropped cap,
  dropped `_MIN_FREE_SLOTS`, `min`→`max`, missing `mats_per_unit==0` guard) is
  killed.

The gate must stay green (differential Python==Lean, surviving-mutant = build
fail) per [[feedback_serialize_gate_runs]] / the formal perimeter.

### Component 2 — shared intermediate-craft sizing helper

```python
def size_intermediate_craft(action, chain, state, game_data) -> CraftAction:
    """Rebatch an intermediate CraftAction to its inventory-bounded closure
    demand. net demand = chain[code] - held(code) (don't re-craft what's held);
    returns the action unchanged when the sized quantity already matches."""
```
`held(code) = inventory + bank`. Computes
`qty = craft_batch_size_pure(action.code, max(0, chain[action.code] - held), state.inventory, state.inventory_free, game_data.crafting_recipes, game_data.resource_drops)` and returns `action` or `dataclasses.replace(action, quantity=qty)`. One helper, its own file (pure function module), so all goals share one code path.

### Component 3 — apply in every emitting goal

In each `relevant_actions`, the intermediate-craft branch changes from
`result.append(a)` to `result.append(size_intermediate_craft(a, chain, state,
game_data))`. Each goal already computes (or trivially can compute) a
`closure_demand` `chain` for its target set:
- `gathering.py` — `chain` at lines 134-136 (already built).
- `pursue_task.py`, `craft_potions.py` (`chain` at 147-148),
  `maintain_consumables.py`, `level_skill.py`, `progression.py`,
  `craft_plan_gen.py` — build/reuse the same `chain` and pass it in.

Where a goal lacks a `chain`, add the standard
`closure_demand(target, qty, game_data, chain, frozenset())` accumulation used
elsewhere.

## Behavior

The planner gathers raws (one drop per action — gather is inherently unbatched)
until `Craft(intermediate, quantity=N)` becomes applicable, then crafts once.
`ash_plank×56` collapses to ⌈56/10⌉ ≈ 6 crafts (bounded by `BATCH_CAP=10` and
inventory) — same gathers, ~50 fewer craft cooldowns. `_MIN_FREE_SLOTS=3` keeps
gathering applicable to the end, and the inventory cap guarantees the raw
footprint fits, so batching never makes a plan unaccumulable — the same
guarantees the proven task path already relies on.

## Testing

- **Pure core:** unit tests for `craft_batch_size_pure` — demand-bounded,
  inventory-bounded (`fit < demand`), `BATCH_CAP`-bounded, `mats_per_unit == 0`
  floor, held-drops-count-as-free; plus `task_batch_size_pure` still matches its
  prior outputs (wrapper regression).
- **Formal:** differential + mutation gate green for the generalized core.
- **Helper:** `size_intermediate_craft` batches to net demand, subtracts held,
  leaves matching quantities untouched, floors at 1.
- **Per goal:** each emitting goal's `relevant_actions` emits the intermediate
  craft at the batched quantity (not 1) for a multi-unit demand; existing goal
  tests stay green.
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.

## Phasing (informs the plan)

1. Generalize + prove the core (`craft_batch_size_pure`, wrapper, formal gate).
2. Shared helper + HIGH goals (GatherMaterials, PursueTask, craft_plan_gen).
3. Remaining goals (craft_potions, maintain_consumables, level_skill, progression).
Each phase is independently testable and shippable.

## Out of scope

- Batching the final gear/task TARGET craft beyond current behavior (task target
  already sized by `task_batch_size`; gear target stays 1, correct except the
  known ring gap — separate).
- Craft-yield > 1 (today's data is yield-1; `demand` is in units == runs). Revisit
  jointly with other yield-dependent sizing when yields land.
- Gather batching (one drop per API call — not batchable).
- NpcBuy sizing (item #2, already merged).
