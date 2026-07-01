# Consumable Batch-Cook at Execution

## Problem

Robby cooks raw chicken one at a time. Trace (`play-trace-Robby.jsonl`) shows
`Craft(cooked_chicken×1)` 12× under goal `RestoreHP`, and `Delete(raw_chicken×1)`
discarding surplus raws. He holds a pile of `raw_chicken` but cooks singly and
throws the rest away.

Root cause (verified): the one-by-one cooking is the `RestoreHP` heal path, not
`MaintainConsumablesGoal`. `RestoreHPGoal` is a pure desired-state goal
(`{"hp": max_hp}`, restore_hp.py:39); the GOAP planner satisfies it by cooking
one `cooked_chicken` and eating it. The `CraftAction` it plans carries the
default `quantity=1` (crafting.py:27). The craft API already accepts a batch
quantity — `execute` sends `CraftingSchema(code, quantity=self.quantity)`
(crafting.py:104) — but nothing sets that quantity above 1 on this path.

This is an **action-execution** gap, not a planner-sizing gap: the fix is to
issue the craft API call with a batched quantity for consumables, leaving GOAP
search untouched.

## Decisions (locked)

- **Locus:** rewrite the craft quantity at execution (`GamePlayer._execute`), not
  in any goal/planner chain.
- **Ingredient source:** held only — batch from raws already in inventory; no
  gather detour. If none held, quantity is unchanged.
- **Predicate:** `stats.type_ in ("consumable", "utility")` — eaten food
  (`cooked_chicken`, `type_=="consumable"`, `subtype=="food"`) AND utility
  consumables (potions, `type_=="utility"`). NOT gated on `hp_restore` — the field
  is not reliably populated for food, and the intent is consumables broadly.
  `CraftPotionsGoal` still sizes its own plan; this execution rewrite only ever
  *expands* a potion craft to the held-ingredient max (never shrinks), so it does
  not fight the guard's deficit sizing.
- **Never shrinks:** `max(planned_qty, batch)` — a task-craft asking for exactly N
  is never reduced.
- **No cap beyond held ingredients:** cooking raws→food is ~net-neutral on
  inventory slots (a raw stack becomes a food stack), so no overflow cap.

## Design

### New pure helper

Add to `src/artifactsmmo_cli/ai/consumable_supply.py` (alongside the other pure
heal helpers — a pure function, no new class):

```python
def consumable_craft_quantity(code: str, planned_qty: int,
                              state: WorldState, game_data: GameData) -> int:
    """Runs to craft for a consumable, batched to the held ingredient pile.

    For a consumable or utility item (`stats.type_ in ("consumable","utility")`)
    with a recipe, return max(planned_qty, runs producible from held ingredients)
    — one batched API craft cooks the whole pile of held raws. For anything else,
    or when no raws are held, return planned_qty unchanged. Held only: never
    gathers."""
```

Implementation:
- `stats = game_data.item_stats(code)`; if `stats is None` or
  `stats.type_ not in ("consumable", "utility")` → return `planned_qty`.
- `recipe = game_data.crafting_recipe(code)`; if `None` → return `planned_qty`.
- `needs = [qty for _c, qty in recipe.items()]`,
  `held = [state.inventory.get(c, 0) for c, _qty in recipe.items()]`.
- `runs = max_batch_from_held_pure(needs, held, 1)`. The `CraftAction.quantity`
  field is the run count, and runs = `min(held[i]//needs[i])` is independent of
  per-run yield — so calling the proven helper with `yield=1` returns runs
  directly. No `craft_yield` call, no division, no `y==0` guard (which would be
  untestable defensive code).
- return `max(planned_qty, runs)`.

`max_batch_from_held_pure(needs, held, yield_per_craft)` already exists
(`ai/max_batch_from_held.py`, proven by `MaxBatchFromHeld.lean`, returns
`min(held[i]//needs[i]) * yield`).

### Wiring in `_execute`

`GamePlayer._execute` (player.py:748) already special-cases `CraftAction`
(`action.history = self.history`). Add the quantity rewrite immediately after,
guarded on `self.game_data` being loaded:

```python
if isinstance(action, CraftAction):
    action.history = self.history
    if self.game_data is not None:
        batched = consumable_craft_quantity(
            action.code, action.quantity, self.state, self.game_data)
        if batched != action.quantity:
            action = dataclasses.replace(action, quantity=batched)
```

`self.state` is asserted non-None at the top of `_execute`. The rewritten action
then flows into the existing `action.execute(self.state, client)` (one batched
`CraftingSchema`). `dataclasses.replace` preserves `history`/`workshop_location`.

### Why zero planner impact

`CraftAction.is_applicable` / `cost` / `apply` run at plan time with the original
`quantity=1`, so GOAP search, plan cost, and reservations are unchanged. The
batch quantity exists only in the object handed to `execute`. The rewrite is
sound: `runs` comes from held ingredients, so
`inventory[mat] >= mat_qty * runs` holds — the batched craft is always
executable.

## Testing

Unit tests in `tests/test_ai/test_consumable_supply.py` for
`consumable_craft_quantity`:
- Held pile of `raw_chicken` (e.g. 9) + `cooked_chicken` recipe `{raw_chicken:1}`,
  yield 1, planned 1 → returns 9 (cook the pile).
- No raws held → returns planned_qty (1).
- Utility potion (`type_=="utility"`) with held ingredients → batches (proves
  utility is included alongside consumable).
- Non-consumable/non-utility code (e.g. a `weapon`/`resource` craft) → returns
  planned_qty unchanged even with ingredients held.
- Recipe yield > 1 → runs = produced // yield (e.g. need 2 raw → 4 held, yield 2
  → produced 4, runs 2).
- `planned_qty` larger than the held batch (task-craft) → returns planned_qty
  (never shrinks).

Execution wiring test in `tests/test_ai/test_player*.py` (existing player-test
module): a stubbed `GamePlayer` with `game_data` + a held raw pile, dispatching a
`Craft(cooked_chicken, quantity=1)` through `_execute`, asserts the CraftAction
reaching the client stub carries the batched quantity. Follow the existing
player-test fakes; do not mock the unit under test.

Success criteria unchanged: 0 errors, 0 warnings, 0 skipped, 100% coverage.

## Formal scope

`max_batch_from_held_pure` is already proven (`MaxBatchFromHeld.lean`) and
differentially gated. `consumable_craft_quantity` is a thin
execution-layer wrapper (type gate + recipe lookup + the proven batch call), not
a decision-ranking core — unit tests only, no new perimeter, matching how the
other `consumable_supply.py` helpers are covered. Out of scope to add a new Lean
core here.

## Out of scope

- No change to `RestoreHPGoal`, `MaintainConsumablesGoal`, or any goal/planner
  sizing (the "not about planning chains" direction).
- No gathering to reach a batch target (held-only).
- No change to the craft API client or `CraftAction.execute` itself.
- No change to `CraftPotionsGoal`'s own plan sizing — the execution rewrite only
  expands potion crafts to the held-ingredient max (never shrinks).
- Inventory-overflow capping (raws→food is net-neutral on slots).
