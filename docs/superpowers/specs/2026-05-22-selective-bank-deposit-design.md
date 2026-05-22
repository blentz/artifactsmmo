# Selective, sell-value-ordered bank deposits

Date: 2026-05-22
Status: Approved (design)

## Goal

When the bot banks inventory, deposit only items it doesn't need, ordered by
sell value (most valuable first). Keep in inventory:

- items related to the **current task** (`state.task_code`),
- materials for the **current crafting target** (weapon/gear being built),
- the **current best fighting weapon**,
- **task coins** (`tasks_coin`),
- **HP-restoring consumables**.

## Current state

`DepositAllAction` (actions/bank.py) deposits the **entire** inventory.
`DepositInventoryGoal` (goals/survival.py) drives it, satisfied at ≤30%
inventory used. Sell-back prices live in `GameData._npc_sell_prices`
(`npcs_buying_item(code) -> [(npc, price)]`). `ItemStats.hp_restore` marks
consumables; `ItemStats.attack` (element→value) and `type_=="weapon"` /
`skill_effects` distinguish combat weapons from tools. `WorldState.crafting_target`
already carries the committed crafting/upgrade target.

## Design

### Selector — `src/artifactsmmo_cli/ai/bank_selection.py`

One module-level pure function:

```python
def select_bank_deposits(state: WorldState, game_data: GameData) -> list[tuple[str, int]]:
    """Items to deposit, ordered (sell_value desc, code asc). Excludes the keep-set."""
```

**Keep-set (item codes never deposited):**
1. `state.task_code` if set.
2. `"tasks_coin"`.
3. Every inventory code whose `game_data.item_stats(code).hp_restore > 0`.
4. **Best fighting weapon:** among inventory + equipment codes where
   `stats.type_ == "weapon"` and **not** `stats.skill_effects` (excludes
   tools — pickaxe/axe/net), pick the max `sum(stats.attack.values())`; ties
   broken by `code` ascending. Keep that one code (or none if no weapon).
5. Every material in `crafting_target`'s recipe tree (recursive walk of
   `game_data._crafting_recipes`, same traversal `active_gathering_skills`
   uses). Empty when `crafting_target` is `None`.

**Selection + ordering:** from `state.inventory` (qty > 0), drop keep-set codes.
For each remaining code, `value = max(price for _, price in
game_data.npcs_buying_item(code))`, or `0` if none. Return `[(code, qty)]`
sorted by `(-value, code)` — unknown/zero-value items sort last.

### Action — `DepositAllAction` (actions/bank.py)

- Add field `game_data: GameData | None = None` (the player already builds the
  action per cycle with `game_data` available).
- `is_applicable`: `self.accessible and bool(self._deposits(state))` — where
  `_deposits(state)` returns `select_bank_deposits(state, self.game_data)` (or
  `[]` when `game_data is None`, preserving old no-op-without-data behavior).
- `apply`: deposit **only** the selected codes — move each `(code, qty)` to the
  bank, remove from inventory; keep everything else. Position → bank location.
- `execute`: deposit the selected `(code, qty)` list **in order** via the
  existing per-item `deposit_item` loop (most valuable first, so an interruption
  banks the valuable items first). Unchanged error handling.

### Goal — `DepositInventoryGoal` (goals/survival.py)

- `is_satisfied(state)` → `not select_bank_deposits(state, game_data)` — i.e. no
  bankable items remain. Replaces the fixed ≤30% rule, which would make the goal
  permanently unsatisfiable when the keep-set alone exceeds 30% of the bag.
  (Requires the goal to hold a `game_data` ref — the player constructs it per
  cycle.)
- `value` / `priority` ramp by inventory-used fraction is unchanged, but
  returns 0 when `is_satisfied` (nothing bankable) — never pursue an empty
  deposit.

### Why a pure selector
`select_bank_deposits` is used by both the action (apply + execute) and the goal
(is_satisfied), so they agree exactly on what's bankable — no divergence between
"goal thinks done" and "action deposits". Pure + no API → fully unit-testable.

## Error handling
- Unknown sell price → value 0, item still deposited, ordered last (intended,
  not a silent failure).
- `crafting_target is None` / no weapons in bag → those keep-categories
  contribute nothing; no error.
- `game_data is None` on the action/goal → selection empty → action inapplicable
  / goal satisfied (matches today's "no banking without data" behavior).
- `execute` keeps the current per-item deposit + error handling; bank-full (462)
  is out of scope here.

## Testing
Success per project standard: 0 errors, 0 warnings, 0 skipped, 100% on changed code.

- **Selector keep-set:** each category excluded — task item, `tasks_coin`, an
  hp-consumable, the best weapon, a `crafting_target` material. Non-kept items
  returned.
- **Best weapon:** highest `sum(attack)` kept; lower-attack weapon deposited;
  tools (`skill_effects` set) NOT treated as the fighting weapon; tie broken by
  code; no weapon → nothing kept.
- **Ordering:** higher sell-back value first; unknown/zero-price last;
  deterministic code tiebreak.
- **All-kept → `[]`.**
- **Action:** `apply` removes only selected codes (keep-set remains in
  inventory, lands in bank dict); `is_applicable` False when selection empty or
  `game_data is None`; `execute` deposits in value order (assert call order).
- **Goal:** `is_satisfied` True when selection empty (even if bag > 30% full of
  kept items); False when bankable items remain; `priority`/`value` 0 when
  satisfied.
- **Planner integration:** with a mixed bag (junk + task item + weapon +
  tasks_coin + hp potion + crafting mat), the plan deposits the junk and the
  resulting state keeps every protected item.

## Files
- `src/artifactsmmo_cli/ai/bank_selection.py` (new) — `select_bank_deposits`.
- `src/artifactsmmo_cli/ai/actions/bank.py` — `DepositAllAction` selective apply/execute + `game_data` field.
- `src/artifactsmmo_cli/ai/goals/survival.py` — `DepositInventoryGoal.is_satisfied`/value via selector + `game_data` ref.
- `src/artifactsmmo_cli/ai/player.py` — pass `game_data` into `DepositAllAction` and `DepositInventoryGoal`.
- Tests under `tests/test_ai/`.

## Out of scope
- Bank-full (462) handling / bank expansion.
- Withdrawing items back from the bank.
- Selling items to NPCs (separate SellInventory path).
