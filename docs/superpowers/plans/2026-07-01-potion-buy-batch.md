# Batch Potion-Ingredient NPC Buys Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Size `CraftPotionsGoal`'s ingredient `NpcBuyAction`s to the whole-batch shortfall so the bot buys mats in one API call per ingredient instead of `runs × per-run-qty` single buys.

**Architecture:** In `CraftPotionsGoal.relevant_actions`, compute the batch closure demand (`closure_demand(code, runs, …)`) and rebatch each passed-through `NpcBuyAction` to `max(1, demand − held)`. Only the buy branch changes; the proven ladder that picks `runs` is untouched.

**Tech Stack:** Python 3.13, pytest. Run everything with `uv run`.

## Global Constraints

- All Python commands prefixed with `uv run`.
- Imports at top of file only — no inline, no `...` imports, no `if TYPE_CHECKING`. (`dataclasses`, `closure_demand`, `NpcBuyAction` are already imported in craft_potions.py.)
- One behavioral class per file; `CraftPotionsGoal` stays the sole class.
- Never catch `Exception`.
- Sizing: buy `max(1, closure_demand(code, runs)[item] − _held(item, state))`. Never exceed batch need. Membership gate (`a.item_code in chain`) unchanged.
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.

---

### Task 1: Size the ingredient buys to the batch

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/craft_potions.py` — `relevant_actions` (lines ~147-164).
- Test: `tests/test_ai/test_craft_potions.py` — add buy-batch tests.

**Interfaces:**
- Consumes: `closure_demand` (already imported), `self._held` (`craft_potions.py:108-111`), `runs` (already computed at line 138).
- Produces: emitted `NpcBuyAction.quantity` sized to the batch shortfall.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai/test_craft_potions.py`:

```python
def test_buy_quantity_batched_to_run_count():
    """The ingredient buy is sized to the whole batch (recipe_qty x runs - held),
    matching the co-emitted craft's run count, not left at 1."""
    gd = _gd_potion()
    gd._npc_stock = {"alchemist": {_INGREDIENT: 100}}
    gd._npc_locations = {"alchemist": (5, 0)}
    state = make_state(level=1, inventory={}, gold=100000)  # baseline 5, nothing held
    actions = [_craft_action(),
               NpcBuyAction(npc_code="alchemist", item_code=_INGREDIENT, quantity=1,
                            npc_location=(5, 0)),
               MoveAction(x=0, y=0)]
    out = CraftPotionsGoal().relevant_actions(actions, state, gd)
    craft = next(a for a in out if isinstance(a, CraftAction) and a.code == _POTION)
    buy = next(a for a in out if isinstance(a, NpcBuyAction))
    # recipe is {sunflower: 1}, nothing held -> buy == 1 * runs == craft.quantity
    assert craft.quantity > 1            # ladder chose a multi-run batch
    assert buy.quantity == craft.quantity
    assert buy.quantity > 1              # batched, not the old quantity=1


def test_buy_quantity_subtracts_held():
    """Held ingredient reduces the buy to the remaining shortfall."""
    gd = _gd_potion()
    gd._npc_stock = {"alchemist": {_INGREDIENT: 100}}
    gd._npc_locations = {"alchemist": (5, 0)}
    state = make_state(level=1, inventory={_INGREDIENT: 2}, gold=100000)
    actions = [_craft_action(),
               NpcBuyAction(npc_code="alchemist", item_code=_INGREDIENT, quantity=1,
                            npc_location=(5, 0)),
               MoveAction(x=0, y=0)]
    out = CraftPotionsGoal().relevant_actions(actions, state, gd)
    craft = next(a for a in out if isinstance(a, CraftAction) and a.code == _POTION)
    buy = next(a for a in out if isinstance(a, NpcBuyAction))
    # recipe {sunflower:1}; demand = 1*runs; held 2 -> buy == max(1, runs - 2)
    assert buy.quantity == max(1, craft.quantity - 2)
```

Note: if the ladder in `_gd_potion` does not choose a multi-run buy batch at level 1
(e.g. `runs` comes out 1 because of stock/price/gold interplay), adjust the fixture
(raise `_npc_stock`, `gold`, keep `hp_restore`/level so `baseline(1)=5` gives
`deficit=5`) until `craft.quantity > 1`, then keep the `buy == craft.quantity`
relation — that relation is the real invariant and must hold regardless.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_craft_potions.py::test_buy_quantity_batched_to_run_count tests/test_ai/test_craft_potions.py::test_buy_quantity_subtracts_held -v`
Expected: FAIL — the emitted `NpcBuyAction.quantity` is still `1` (the passed-through action), so `buy.quantity == craft.quantity` fails.

- [ ] **Step 3: Implement the batch sizing**

In `src/artifactsmmo_cli/ai/goals/craft_potions.py`, after the existing per-1
`chain` block (lines 147-149), add the batch-demand chain:

```python
        chain: dict[str, int] = {}
        closure_demand(code, 1, game_data, chain, frozenset())
        withdrawable |= set(chain)

        buy_chain: dict[str, int] = {}
        closure_demand(code, runs, game_data, buy_chain, frozenset())
```

Change the `NpcBuyAction` branch (lines 163-164) from:

```python
            elif isinstance(a, NpcBuyAction) and a.item_code in chain:
                result.append(a)
```

to:

```python
            elif isinstance(a, NpcBuyAction) and a.item_code in chain:
                buy_qty = max(1, buy_chain.get(a.item_code, 0)
                              - self._held(a.item_code, state))
                result.append(a if a.quantity == buy_qty
                              else dataclasses.replace(a, quantity=buy_qty))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_craft_potions.py -v`
Expected: PASS (new buy-batch tests + all existing craft_potions tests, incl.
`test_buy_tier_emits_npcbuy` which only asserts presence and stays green).

- [ ] **Step 5: mypy + coverage of the changed goal**

Run: `uv run pytest tests/test_ai/test_craft_potions.py --cov=src/artifactsmmo_cli/ai/goals/craft_potions --cov-report=term-missing && uv run mypy src/artifactsmmo_cli/ai/goals/craft_potions.py`
Expected: 100% of the changed lines covered; mypy clean. If the `max(1, …)` floor branch (held ≥ demand) is uncovered, add a test where held ≥ the batch demand and assert `buy.quantity == 1`.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/craft_potions.py tests/test_ai/test_craft_potions.py
git commit -m "feat(craft_potions): batch ingredient NPC buys to the run count"
```

---

### Task 2: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Full suite with coverage**

Run: `uv run pytest`
Expected: 0 errors, 0 warnings, 0 skipped, 100% coverage. (If the two live-API
audit tests — `test_live_item_effect_coverage`, `test_live_combat_gear_classification`
— flake under contention, re-run once; they pass in isolation and are unrelated.)

- [ ] **Step 2: Type check**

Run: `uv run mypy src/artifactsmmo_cli/ai`
Expected: no errors.

- [ ] **Step 3: If coverage < 100%, add the missing-line test**

Identify the uncovered line, add a targeted `test_craft_potions.py` case (e.g. the
held-covers-demand floor), re-run `uv run pytest`. Do not lower the bar.

---

## Self-Review

- **Spec coverage:** buy-branch rebatch via `buy_chain = closure_demand(code, runs)` and `max(1, demand − held)` (Task 1 Step 3); membership `chain` unchanged; craft/gather/withdraw/equip untouched; tests for batched buy, held-subtraction, and floor (Task 1 Steps 1/5); ladder untouched (no formal change). All spec sections mapped.
- **Placeholder scan:** none — every step has full code/commands.
- **Type consistency:** `buy_chain`/`closure_demand(code, runs, game_data, buy_chain, frozenset())` mirror the existing per-1 `chain` call at line 148; `self._held(code, state)` signature matches `craft_potions.py:108-111`; `dataclasses.replace` matches the target-craft rebatch idiom at line 157-158; all needed names already imported.
- **Robustness note:** the `buy.quantity == craft.quantity` invariant (for the yield-1, recipe-qty-1 fixture) ties the test to the goal's own run count rather than a hardcoded number, so it holds regardless of the exact `runs` the ladder picks.
