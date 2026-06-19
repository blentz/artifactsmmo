# Bank-full Space-making Cascade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Lean proof steps are interactive — use the `lean4:prove` / `lean4:proof-repair` skills to discover tactics; this plan gives the exact definitions and the theorem names to re-prove, not the tactic scripts.

**Goal:** When the bag is full and the bank cannot accept items (`¬bank_has_room`), make space via craft → recycle → sell → discard instead of fruitlessly depositing; gate `DEPOSIT_FULL` on bank room (which also fixes the pre-existing `test_ladder_fires_diff` residual) and reserve discard for truly-worthless items at bank-full only.

**Architecture:** Add a pure `bank_has_room` predicate. Gate the existing `DEPOSIT_FULL` guard on it and the existing `DISCARD_*` guards on its negation. Add two new bank-full-gated guards `RECYCLE_RELIEF`/`SELL_RELIEF` mapping to the existing `RecycleSurplusGoal`/`SellInventoryGoal`. Every production guard change lands in lockstep with its Lean `*Fires` mirror (`ProductionLadder.lean`), the differential oracle (`test_ladder_fires_diff.py`), and the mutation gate — so each task ends with `lake build` + the differential green.

**Tech Stack:** Python 3.13, Lean 4 + Mathlib (`formal/`), pytest + Hypothesis, uv, mypy, ruff, `formal/gate.sh`.

## Global Constraints

- ALWAYS prefix Python commands with `uv` at `~/.local/bin/uv` (PATH may lack it): `~/.local/bin/uv run pytest`, `… mypy src`, `… ruff check`. Lean: `cd formal && lake build`.
- All imports at top of file. No inline imports. No `if TYPE_CHECKING`. Never catch `Exception`. One behavioral class per file.
- Python success each task: `~/.local/bin/uv run pytest && ~/.local/bin/uv run mypy src && ~/.local/bin/uv run ruff check src/artifactsmmo_cli/ai/` — 0 errors/warnings/skips, 100% coverage. (`ruff check` has pre-existing import-order/zip findings in some `ai/` files + `formal/`; do not add NEW ones — compare against base.)
- Formal success each task touching `formal/`: `cd formal && lake build` clean (0 `sorry`, 0 errors), then `~/.local/bin/uv run pytest formal/diff/test_ladder_fires_diff.py` green.
- NEVER run `formal/gate.sh`, `formal/diff/mutate.py`, or anything importing `src` concurrently with another such run or the bot (serialize — a poisoned predicate caused an instant SystemExit before). Run `git diff src` after each formal run.
- `bank_has_room` predicate (Python): `ctx.bank_accessible AND state.bank_items is not None AND game_data.bank_capacity is not None AND len(state.bank_items) < game_data.bank_capacity`.
- `bankHasRoom` (Lean): `s.bankAccessible && s.bankItemsKnown && decide (s.bankItemsCount < s.bankCapacity)`.
- The gate is currently RED on OTHER pre-existing baseline defects unrelated to this work; success = the BankSelection/ladder slots green + no NEW failures, not necessarily the whole `gate.sh` green.

## File structure

| File | Responsibility | Tasks |
|------|----------------|-------|
| `src/artifactsmmo_cli/ai/bank_room.py` (NEW) | `bank_has_room` pure predicate | 1 |
| `src/artifactsmmo_cli/ai/tiers/guards.py` | GuardKind enum, GUARD_ORDER, `_fires`, fraction consts | 2,3,4,5 |
| `src/artifactsmmo_cli/ai/strategy_driver.py` | `map_guard` (GuardKind → Goal) | 4,5 |
| `src/artifactsmmo_cli/ai/craft_relief.py` | `craft_relief_candidates` (sole-output extension) | 6 |
| `src/artifactsmmo_cli/ai/goals/discard_overstock.py` | worthless-only delete restriction | 3 |
| `formal/Formal/Liveness/ProductionLadder.lean` | `*Fires` defs, `fires` dispatch | 2,3,4,5 |
| `formal/Formal/Liveness/MeansKind.lean` | `MeansKind` ctors, `allInLadderOrder` | 4,5 |
| `formal/Formal/Liveness/MeansFiring.lean` | per-slot `fires ⇒ value > 0` theorems | 3,4,5 |
| `formal/Formal/Liveness/{NoDeadlockV2,NoWait,PursueTaskSelection}.lean` | ladder totality / order theorems | 4,5 |
| `formal/sim/production_ladder.py` | `LadderMeans`, `ALL_IN_LADDER_ORDER`, `fires` | 4,5 |
| `formal/diff/test_ladder_fires_diff.py` | oracle args, ASSERTED/DEFERRED slots, scenario | 2,3,4,5 |
| `tests/test_ai/test_bank_room.py` (NEW), `test_guards.py`, `test_strategy_driver.py`, `test_craft_relief.py`, `test_discard_overstock.py` | production unit/integration tests | all |

---

### Task 1: `bank_has_room` predicate (production + Lean def, unused)

Adds the predicate to BOTH sides without wiring it into any fires-predicate yet, so the differential stays green (no slot reads it). Establishes the shared definition Tasks 2–5 consume.

**Files:**
- Create: `src/artifactsmmo_cli/ai/bank_room.py`
- Create: `tests/test_ai/test_bank_room.py`
- Modify: `formal/Formal/Liveness/ProductionLadder.lean` (add `bankHasRoom` def near the other fires defs, ~line 156)

**Interfaces:**
- Produces (Python): `bank_has_room(state: WorldState, game_data: GameData, ctx: SelectionContext) -> bool`
- Produces (Lean): `def bankHasRoom (s : State) : Bool`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_bank_room.py`:

```python
"""bank_has_room: the bank can physically accept a deposited item."""

from artifactsmmo_cli.ai.bank_room import bank_has_room
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from tests.test_ai.fixtures import make_state


def _ctx(bank_accessible: bool = True) -> SelectionContext:
    return SelectionContext(
        bank_accessible=bank_accessible, bank_required_level=0,
        bank_unlock_monster=None, initial_xp=0, task_exchange_min_coins=1,
        combat_monster=None)


def _gd(capacity: int | None) -> GameData:
    gd = GameData()
    gd._bank_capacity = capacity
    return gd


def test_room_when_used_below_capacity():
    state = make_state(bank_items={"a": 1, "b": 1})
    assert bank_has_room(state, _gd(50), _ctx()) is True


def test_no_room_when_full():
    state = make_state(bank_items={f"i{n}": 1 for n in range(50)})
    assert bank_has_room(state, _gd(50), _ctx()) is False


def test_no_room_when_capacity_zero():
    state = make_state(bank_items={})
    assert bank_has_room(state, _gd(0), _ctx()) is False


def test_no_room_when_bank_inaccessible():
    state = make_state(bank_items={"a": 1})
    assert bank_has_room(state, _gd(50), _ctx(bank_accessible=False)) is False


def test_no_room_when_capacity_unknown():
    state = make_state(bank_items={"a": 1})
    assert bank_has_room(state, _gd(None), _ctx()) is False


def test_no_room_when_bank_unvisited():
    state = make_state(bank_items=None)
    assert bank_has_room(state, _gd(50), _ctx()) is False
```

- [ ] **Step 2: Run it, verify it fails**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_bank_room.py -v --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.bank_room'`

(If `make_state` does not accept `bank_items=None` / `bank_capacity`, check `tests/test_ai/fixtures.py` for its signature and pass the bank fields it supports; `WorldState.bank_items` defaults to `None` and capacity comes from `game_data.bank_capacity`, so only `bank_items` needs setting on the state.)

- [ ] **Step 3: Create the predicate**

Create `src/artifactsmmo_cli/ai/bank_room.py`:

```python
"""Pure predicate: can the bank physically accept a deposited item?

`bank_capacity is None` = capacity unknown (NOT room); `bank_items is None` =
bank never visited (NOT room). Distinct from the `bank_capacity == 0` divide-
guard in BANK_EXPAND. Mirrors `Formal.Liveness.ProductionLadder.bankHasRoom`."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


def bank_has_room(state: WorldState, game_data: GameData,
                  ctx: SelectionContext) -> bool:
    if not ctx.bank_accessible:
        return False
    if state.bank_items is None or game_data.bank_capacity is None:
        return False
    return len(state.bank_items) < game_data.bank_capacity
```

NOTE: if importing `SelectionContext` from `tiers.guards` into `bank_room.py`
and then `bank_room` into `tiers.guards` (Task 2) creates a cycle, move
`bank_has_room` to take the three primitive args
`(bank_accessible: bool, bank_items: dict|None, bank_capacity: int|None)`
instead of `ctx`/`game_data`, and have callers unpack. Decide at Task 2 wiring.

- [ ] **Step 4: Run it, verify it passes**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_bank_room.py -v --no-cov`
Expected: PASS (6 passed)

- [ ] **Step 5: Add the Lean mirror (unused)**

In `formal/Formal/Liveness/ProductionLadder.lean`, after `depositFullFires`
(~line 162), add:

```lean
/-- The bank can physically accept a deposit: accessible, item-count known,
    and used strictly below capacity. Mirrors `ai/bank_room.bank_has_room`.
    `bankItemsKnown=false` (bank unvisited) and `bankCapacity=0` both read as
    NO room. Not yet wired into any fires-predicate (Tasks 2–5). -/
def bankHasRoom (s : State) : Bool :=
  s.bankAccessible && s.bankItemsKnown && decide (s.bankItemsCount < s.bankCapacity)
```

- [ ] **Step 6: Build Lean + run the differential (must stay green)**

Run: `cd formal && lake build`
Expected: builds clean (the new def is unused — no proof obligations).
Run: `~/.local/bin/uv run pytest formal/diff/test_ladder_fires_diff.py --no-cov`
Expected: SAME pre-existing result as base (still the one known residual failure; no NEW failures — `bankHasRoom` is unused).

- [ ] **Step 7: Full Python gate + commit**

Run: `~/.local/bin/uv run pytest && ~/.local/bin/uv run mypy src && ~/.local/bin/uv run ruff check src/artifactsmmo_cli/ai/bank_room.py tests/test_ai/test_bank_room.py`
Expected: green, 100% coverage.

```bash
git add src/artifactsmmo_cli/ai/bank_room.py tests/test_ai/test_bank_room.py formal/Formal/Liveness/ProductionLadder.lean
git commit -m "feat(ai): bank_has_room predicate + Lean bankHasRoom mirror (unused)"
```

---

### Task 2: Gate `DEPOSIT_FULL` on `bank_has_room` (resolves the ladder_fires residual)

Smallest, highest-value formal change: one extra conjunct on the existing
`DEPOSIT_FULL`/`depositFullFires`. No new slot, no reorder. After this the
`test_ladder_fires_diff` residual is gone (both sides go False when the bank is
full), because `bankHasRoom=False` short-circuits before the
`selectBankDepositsNonempty` disagreement matters.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/guards.py:167-171` (`DEPOSIT_FULL` branch)
- Modify: `formal/Formal/Liveness/ProductionLadder.lean` (`depositFullFires`)
- Modify: `formal/Formal/Liveness/MeansFiring.lean` (`_fires_depositFull_implies_depositInventory_positive` — re-prove)
- Test: `tests/test_ai/test_guards.py`

**Interfaces:**
- Consumes: `bank_has_room` (Task 1); Lean `bankHasRoom` (Task 1).

- [ ] **Step 1: Write the failing production test**

Add to `tests/test_ai/test_guards.py` (use the file's existing `_ctx`/`make_state`
helpers; if it has none, mirror `test_bank_room.py`'s `_ctx`/`_gd`). Import
`_fires`, `GuardKind` from `artifactsmmo_cli.ai.tiers.guards`:

```python
def test_deposit_full_quiet_when_bank_full():
    """DEPOSIT_FULL must not fire when the bank cannot accept items (full)."""
    gd = GameData(); gd._bank_capacity = 2
    state = make_state(inventory={"junk": 100}, inventory_max=100,
                       bank_items={"x": 1, "y": 1})   # bank used 2 == capacity 2
    ctx = _ctx()  # bank_accessible=True
    assert _fires(GuardKind.DEPOSIT_FULL, state, gd, None, ctx) is False


def test_deposit_full_fires_when_bank_has_room():
    gd = GameData(); gd._bank_capacity = 50
    state = make_state(inventory={"junk": 100}, inventory_max=100,
                       bank_items={"x": 1})
    ctx = _ctx()
    assert _fires(GuardKind.DEPOSIT_FULL, state, gd, None, ctx) is True
```

(For the second to fire, `select_bank_deposits` must return a non-kept item:
`junk` is non-kept overstock, so it is a deposit candidate. Confirm `make_state`
gives `inventory_used=100`; if it derives `inventory_used` from the inventory
dict, `{"junk": 100}` yields 100. If not, set `inventory_used=100` explicitly.)

- [ ] **Step 2: Run it, verify it fails**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_guards.py -k deposit_full_quiet -v --no-cov`
Expected: FAIL — currently `_fires(DEPOSIT_FULL)` ignores bank room and returns True.

- [ ] **Step 3: Gate the production guard**

In `src/artifactsmmo_cli/ai/tiers/guards.py`, add the import at top:

```python
from artifactsmmo_cli.ai.bank_room import bank_has_room
```

(If this creates an import cycle — `bank_room` imports `SelectionContext` from
this module — apply the primitive-args fallback from Task 1 Step 3 NOTE: change
`bank_room.bank_has_room` to take `(bank_accessible, bank_items, bank_capacity)`,
update `test_bank_room.py` accordingly, and call it here as
`bank_has_room(ctx.bank_accessible, state.bank_items, game_data.bank_capacity)`.)

Replace the `DEPOSIT_FULL` branch (lines 167-171):

```python
    if kind is GuardKind.DEPOSIT_FULL:
        return (ctx.bank_accessible
                and bank_has_room(state, game_data, ctx)
                and _used_fraction(state) >= DEPOSIT_FULL_FRACTION
                and bool(select_bank_deposits(
                    state, game_data,
                    frozenset(active_profile(state, game_data, ctx, step_profile)))))
```

- [ ] **Step 4: Run the production tests**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_guards.py -k deposit_full -v --no-cov`
Expected: PASS (both).

- [ ] **Step 5: Mirror in Lean + re-prove**

In `ProductionLadder.lean`, edit `depositFullFires` to add the conjunct:

```lean
def depositFullFires (s : State) : Bool :=
  s.bankAccessible
  && bankHasRoom s
  && decide (s.inventoryMax > 0)
  && decide (DEPOSIT_FULL_DEN * s.inventoryUsed
              ≥ DEPOSIT_FULL_NUM * s.inventoryMax)
  && s.selectBankDepositsNonempty
```

Then `cd formal && lake build`. The theorem
`_fires_depositFull_implies_depositInventory_positive` (MeansFiring.lean) will
likely break only if its proof destructured the old `&&` shape; the new conjunct
is strictly stronger (fires ⇒ all old conjuncts still hold), so the
`depositInventoryValue > 0` conclusion is unchanged. Use `lean4:proof-repair` to
fix the destructuring (typically: the hypothesis now yields one extra
`bankHasRoom s = true` that is simply unused). Build until clean.

- [ ] **Step 6: Differential green — the residual is resolved**

The oracle already passes `bankAccessible`/`bankItemsKnown`/`bankItemsCount`/
`bankCapacity` (args 17/30/13/14), so the Lean side computes `bankHasRoom` with
no new arg. The production `production_ladder.py` `depositFull` fires must mirror
the new guard — update `formal/sim/production_ladder.py`'s `DEPOSIT_FULL` fire to
the same `bank_has_room`-gated condition (read its current body and add the
conjunct using the scenario-derived bank fields).

Run: `~/.local/bin/uv run pytest formal/diff/test_ladder_fires_diff.py --no-cov`
Expected: GREEN — `test_ladder_fires_matches_production` now passes (the residual
scenario: bank_capacity small/0 → both sides `depositFull=False`).

- [ ] **Step 7: `git diff src` sanity, full gates, commit**

Run: `git diff --stat src formal/sim` (confirm only intended files changed).
Run: `~/.local/bin/uv run pytest && ~/.local/bin/uv run mypy src && ~/.local/bin/uv run ruff check src/artifactsmmo_cli/ai/`
Run: `cd formal && lake build`

```bash
git add src/artifactsmmo_cli/ai/tiers/guards.py formal/Formal/Liveness/ProductionLadder.lean formal/Formal/Liveness/MeansFiring.lean formal/sim/production_ladder.py tests/test_ai/test_guards.py
git commit -m "fix(ai+formal): gate DEPOSIT_FULL on bank_has_room (resolves ladder_fires residual)"
```

---

### Task 3: Gate `DISCARD_CRITICAL`/`DISCARD_HIGH` on `¬bank_has_room` + worthless-only delete

Discard stops firing on bag-fullness alone (deposits instead when bank has room),
and when it does fire it deletes only truly-worthless items.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/guards.py` (`DISCARD_CRITICAL`, `DISCARD_HIGH` branches)
- Modify: `src/artifactsmmo_cli/ai/goals/discard_overstock.py` (delete-only worthless filter under bank-full)
- Modify: `formal/Formal/Liveness/ProductionLadder.lean` (`discardCriticalFires`, `discardHighFires`)
- Modify: `formal/Formal/Liveness/MeansFiring.lean` (`_fires_discardCritical_…`, `_fires_discardHigh_…`)
- Modify: `formal/sim/production_ladder.py` (DISCARD fires)
- Test: `tests/test_ai/test_guards.py`, `tests/test_ai/test_discard_overstock.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai/test_guards.py`:

```python
def test_discard_quiet_when_bank_has_room():
    """With bank room, overstock is deposited, not discarded."""
    gd = GameData(); gd._bank_capacity = 50
    state = make_state(inventory={"junk": 100}, inventory_max=100,
                       bank_items={"x": 1})
    ctx = _ctx()
    assert _fires(GuardKind.DISCARD_CRITICAL, state, gd, None, ctx) is False
    assert _fires(GuardKind.DISCARD_HIGH, state, gd, None, ctx) is False


def test_discard_fires_when_bank_full():
    gd = GameData(); gd._bank_capacity = 1
    state = make_state(inventory={"junk": 100}, inventory_max=100,
                       bank_items={"x": 1})   # full
    ctx = _ctx()
    # overstock present + bank full -> discard guard fires (worthless filtering
    # happens in the goal, not the fire predicate)
    assert _fires(GuardKind.DISCARD_HIGH, state, gd, None, ctx) is True
```

(The first relies on `overstocked_items` being non-empty for `junk` overstock so
the OLD predicate would have fired; the `¬bank_has_room` gate is what flips it to
False. If `make_state`'s default profile keeps `junk`, use a clearly-overstocked
item the active profile does not protect — check `tests/test_ai/test_overstock.py`
for a known overstock witness and reuse it.)

- [ ] **Step 2: Run, verify fail**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_guards.py -k "discard_quiet or discard_fires_when_bank_full" -v --no-cov`
Expected: FAIL — `discard_quiet_when_bank_has_room` fails (discard currently
ignores bank room).

- [ ] **Step 3: Gate the production guards**

In `guards.py`, replace the `DISCARD_CRITICAL` and `DISCARD_HIGH` branches:

```python
    if kind is GuardKind.DISCARD_CRITICAL:
        return (not bank_has_room(state, game_data, ctx)
                and bool(overstocked_items(state, game_data,
                                           profile=active_profile(state, game_data, ctx,
                                                                  step_profile)))
                and _used_fraction(state) >= DISCARD_CRITICAL_FRACTION)
    ...
    if kind is GuardKind.DISCARD_HIGH:
        return (not bank_has_room(state, game_data, ctx)
                and bool(overstocked_items(state, game_data,
                                           profile=active_profile(state, game_data, ctx,
                                                                  step_profile)))
                and _used_fraction(state) >= DISCARD_HIGH_FRACTION)
```

- [ ] **Step 4: Worthless-only delete in the goal**

Read `src/artifactsmmo_cli/ai/goals/discard_overstock.py:79-117` (the sell-or-
delete batch builder). Add a delete-only-worthless gate: when an overstocked item
HAS a buyer/GE order (sellable) OR is a recipe input on hand (craftable use), it
is NOT deleted here (the SELL/CRAFT rungs handle it). Concretely, in the loop
that emits a delete action, skip the item when `game_data.npcs_buying_item(code)`
is non-empty OR `liquidation_venue` finds a GE order. Add a unit test in
`tests/test_ai/test_discard_overstock.py`:

```python
def test_sellable_overstock_not_deleted():
    """A sellable overstock item is left for the SELL rung, never deleted."""
    # build gd where 'junk' has an NPC buyer; assert no Delete(junk) action,
    # and an unsellable 'rock' (no buyer) IS deleted.
    ...
```

(Fill the test body from the file's existing `_gd`/`make_state` fixture pattern —
set `gd._npcs_by_item = {"junk": [<npc>]}` so `npcs_buying_item("junk")` is
non-empty and leave `rock` with no buyer; assert the produced actions delete
`rock` but not `junk`.)

Implement the skip in `discard_overstock.py` and run the test to green.

- [ ] **Step 5: Mirror in Lean + re-prove**

Edit `discardCriticalFires`/`discardHighFires` to add `&& !(bankHasRoom s)`:

```lean
def discardCriticalFires (s : State) : Bool :=
  !(bankHasRoom s)
  && s.hasOverstockItems
  && decide (s.inventoryMax > 0)
  && decide (DISCARD_CRITICAL_DEN * s.inventoryUsed ≥ DISCARD_CRITICAL_NUM * s.inventoryMax)
-- discardHighFires: identical, with DISCARD_HIGH_DEN/NUM
```

`cd formal && lake build`. Re-prove `_fires_discardCritical_implies_discardOverstock_positive`
and `_fires_discardHigh_…` (the new conjunct is extra; conclusion unchanged) via
`lean4:proof-repair`. Update `formal/sim/production_ladder.py` DISCARD fires to
add the `not bank_has_room` conjunct.

- [ ] **Step 6: Differential green**

Run: `~/.local/bin/uv run pytest formal/diff/test_ladder_fires_diff.py --no-cov`
Expected: GREEN (discardCritical/discardHigh slots now read `bankHasRoom`,
mirrored both sides). If a boundary witness pins discard at a bank-has-room
scenario, update it to assert `False` there.

- [ ] **Step 7: Full gates + commit**

Run the Python gate + `cd formal && lake build`; `git diff --stat`.

```bash
git add src/artifactsmmo_cli/ai/tiers/guards.py src/artifactsmmo_cli/ai/goals/discard_overstock.py formal/Formal/Liveness/ProductionLadder.lean formal/Formal/Liveness/MeansFiring.lean formal/sim/production_ladder.py tests/test_ai/test_guards.py tests/test_ai/test_discard_overstock.py
git commit -m "feat(ai+formal): discard only at bank-full + worthless-only delete"
```

---

### Task 4: New `RECYCLE_RELIEF` guard (recycle under bank-full pressure)

New ladder slot — the heaviest formal task (new `MeansKind`, reorder, totality
re-proof). Maps to the existing `RecycleSurplusGoal`.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/guards.py` (GuardKind, GUARD_ORDER, `_fires`)
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (`map_guard`)
- Modify: `formal/Formal/Liveness/MeansKind.lean` (`MeansKind.recycleRelief`, `allInLadderOrder`, length example 23→24)
- Modify: `formal/Formal/Liveness/ProductionLadder.lean` (`recycleReliefFires` def, `fires` dispatch)
- Modify: `formal/Formal/Liveness/MeansFiring.lean` (NEW `_fires_recycleRelief_implies_recycleSurplus_positive`)
- Modify: `formal/Formal/Liveness/{NoDeadlockV2,NoWait,PursueTaskSelection}.lean` (re-prove order/totality)
- Modify: `formal/sim/production_ladder.py` (`LadderMeans.RECYCLE_RELIEF`, `ALL_IN_LADDER_ORDER`, `fires`)
- Modify: `formal/diff/test_ladder_fires_diff.py` (LadderMeans coverage, oracle arg for recycle candidate, ASSERTED/DEFERRED)
- Test: `tests/test_ai/test_guards.py`, `tests/test_ai/test_strategy_driver.py`

**Interfaces:**
- Consumes: `recyclable_surplus` (means.py import), `RecycleSurplusGoal`, `bank_has_room`.
- Produces: `GuardKind.RECYCLE_RELIEF`; Lean `MeansKind.recycleRelief`, `recycleReliefFires`.

- [ ] **Step 1: Failing production tests**

Add to `tests/test_ai/test_guards.py`:

```python
def test_recycle_relief_fires_when_bank_full_with_surplus():
    """Recyclable surplus + bank full + bag pressure -> RECYCLE_RELIEF fires."""
    # gd with a craftable equippable surplus held above useful cap, workshop
    # known, skill at recipe level; bank full. Reuse the recyclable_surplus
    # fixture from tests/test_ai/test_recycle_surplus.py.
    ...
    assert _fires(GuardKind.RECYCLE_RELIEF, state, gd, None, ctx) is True


def test_recycle_relief_quiet_when_bank_has_room():
    # same surplus, bank has room -> deposit instead, RECYCLE_RELIEF quiet.
    ...
    assert _fires(GuardKind.RECYCLE_RELIEF, state, gd, None, ctx) is False
```

(Build the surplus fixture from `tests/test_ai/test_recycle_surplus.py` — copy its
`_gd`/state setup that makes `recyclable_surplus(...)` non-empty.)

- [ ] **Step 2: Run, verify fail** — `AttributeError: RECYCLE_RELIEF`.

- [ ] **Step 3: Add the GuardKind + fire predicate + ordering**

In `guards.py`: add to `GuardKind` enum:
```python
    RECYCLE_RELIEF = "recycle_relief"
```
Insert into `GUARD_ORDER` after `CRAFT_RELIEF`:
```python
    GuardKind.CRAFT_RELIEF,
    GuardKind.RECYCLE_RELIEF,   # bank-full: recover materials before sell/discard
    GuardKind.SELL_RELIEF,      # added in Task 5
    GuardKind.DEPOSIT_FULL,
```
(Add `SELL_RELIEF` to the order now as a forward reference is NOT possible — add
the `GUARD_ORDER` line for `SELL_RELIEF` in Task 5; here insert only
`RECYCLE_RELIEF`.) Add the `_fires` branch (import `recyclable_surplus` from
`artifactsmmo_cli.ai.recycle_surplus` at top):
```python
    if kind is GuardKind.RECYCLE_RELIEF:
        return (not bank_has_room(state, game_data, ctx)
                and bool(recyclable_surplus(
                    state, game_data, ctx.target_gear | ctx.target_tools)))
```

- [ ] **Step 4: `map_guard` branch**

In `strategy_driver.py` `map_guard`, add (import `RecycleSurplusGoal` at top):
```python
    if kind is GuardKind.RECYCLE_RELIEF:
        return RecycleSurplusGoal(
            protected=frozenset(ctx.target_gear | ctx.target_tools))
```
(Read `RecycleSurplusGoal.__init__` signature first and match it — the explorer
noted `recyclable_surplus(state, game_data, protected_codes)`; pass whatever the
goal constructor expects, mirroring how the `MeansKind.RECYCLE_SURPLUS` mapping at
`strategy_driver.py:334-336` constructs it.)

- [ ] **Step 5: Run production tests + add a map_guard test**

Add to `tests/test_ai/test_strategy_driver.py`:
```python
def test_map_guard_recycle_relief():
    from artifactsmmo_cli.ai.goals.recycle_surplus import RecycleSurplusGoal
    g = map_guard(GuardKind.RECYCLE_RELIEF, _gd_with_surplus(), _ctx(), state=_surplus_state())
    assert isinstance(g, RecycleSurplusGoal)
```
Run the guards + strategy_driver tests to green.

- [ ] **Step 6: Lean — new MeansKind + fires + ordering**

In `MeansKind.lean`: add `| recycleRelief` to the `MeansKind` inductive; insert
`.recycleRelief` into `allInLadderOrder` immediately after `.craftRelief`; bump
the length example to `24` (then `25` after Task 5). In `ProductionLadder.lean`:
```lean
def recycleReliefFires (s : State) : Bool :=
  !(bankHasRoom s) && s.recyclableSurplusNonempty
```
and add the `.recycleRelief => recycleReliefFires s` arm to the `fires` match
(ProductionLadder.lean:299-323).

- [ ] **Step 7: Lean — re-prove totality + order theorems**

`cd formal && lake build`. Expect breaks in `NoDeadlockV2` (`allInLadderOrder`
length / `wait_mem_ladder` / totality — the new ctor must be covered),
`NoWait.ladder_split` (dropLast shape), and `PursueTaskSelection`
(`obtain ⟨h1..h15⟩` destructuring is position-sensitive — inserting a slot before
`pursueTask` shifts indices). Use `lean4:proof-repair` and `lean4:sorry-filler-deep`:
- `NoDeadlockV2.*`: totality holds because `.wait` still terminates the list and
  is unconditional; repair the membership/length lemmas for the +1 ctor.
- `NoWait.*`: update the `dropLast` equation and the `wait_notin_init` proof.
- `PursueTaskSelection.productionLadder_eq_pursueTask`: the new slot is ABOVE
  `pursueTask` and is bank-full-gated; add the new `recycleReliefFires s = false`
  hypothesis to `pursueSelectionConditions` (or derive it from existing
  conditions) and extend the destructuring. This is the hardest repair — budget
  for it.
Add the NEW safety theorem in `MeansFiring.lean`:
```lean
theorem _fires_recycleRelief_implies_recycleSurplus_positive (s : State) :
    recycleReliefFires s = true → recycleSurplusValue s > 0 := by
  ...
```
(Model it on `_fires_sellPressured_implies_sellInventory_positive`; if there is
no `recycleSurplusValue`, recycleRelief is an opaque/passthrough slot like
`recycleSurplus` — then add `RECYCLE_RELIEF` to `DEFERRED_SLOTS` in the diff
instead of asserting it, matching how `RECYCLE_SURPLUS` is deferred, and SKIP the
MeansFiring theorem.) Build until clean, 0 `sorry`.

- [ ] **Step 8: Differential — new slot**

In `formal/sim/production_ladder.py`: add `RECYCLE_RELIEF` to `LadderMeans` and
`ALL_IN_LADDER_ORDER` (same position), and a `fires` arm. In
`test_ladder_fires_diff.py`: the new slot needs an oracle signal — drive
`recyclableSurplusNonempty` (arg[23], currently hardcoded `0`/deferred) from
`prod[LadderMeans.RECYCLE_SURPLUS]`-style real computation in the rich path, OR
keep `RECYCLE_RELIEF` in `DEFERRED_SLOTS` (passthrough) if Step 7 made it opaque.
Ensure `set(ASSERTED_SLOTS) | DEFERRED_SLOTS == set(ALL_IN_LADDER_ORDER)` still
holds (test at line 656).

Run: `~/.local/bin/uv run pytest formal/diff/test_ladder_fires_diff.py --no-cov`
Expected: GREEN.

- [ ] **Step 9: Refresh mutation anchors, full gates, commit**

Run: `~/.local/bin/uv run python formal/diff/mutate.py` (alone — serialize) to
re-anchor; confirm no surviving mutants on the changed predicates. Python gate +
`lake build` + `git diff --stat`.

```bash
git add -A
git commit -m "feat(ai+formal): RECYCLE_RELIEF guard — recycle surplus under bank-full"
```

---

### Task 5: New `SELL_RELIEF` guard (sell under bank-full pressure)

Same shape as Task 4, mapping to `SellInventoryGoal`. Sits between
`RECYCLE_RELIEF` and `DEPOSIT_FULL`.

**Files:** same set as Task 4, plus `SellInventoryGoal`.

**Interfaces:**
- Consumes: `_has_sellable` (means.py), `SellInventoryGoal`, `bank_has_room`.
- Produces: `GuardKind.SELL_RELIEF`; Lean `MeansKind.sellRelief`, `sellReliefFires`.

- [ ] **Step 1: Failing tests** — mirror Task 4 Step 1 with a sellable-item
fixture (an NPC buyer + `tradeable`), asserting `SELL_RELIEF` fires at bank-full
and is quiet at bank-has-room. Add a `map_guard` test asserting
`isinstance(g, SellInventoryGoal)`.

- [ ] **Step 2: Run, verify fail** — `AttributeError: SELL_RELIEF`.

- [ ] **Step 3: GuardKind + ordering + fire predicate.** In `guards.py`: add
`SELL_RELIEF = "sell_relief"`; ensure `GUARD_ORDER` has it between
`RECYCLE_RELIEF` and `DEPOSIT_FULL` (the line was sketched in Task 4 Step 3 —
make it real here). Import `_has_sellable` from `artifactsmmo_cli.ai.tiers.means`
(or replicate its tiny body to avoid a means→guards coupling — prefer importing
if no cycle). Add:
```python
    if kind is GuardKind.SELL_RELIEF:
        return (not bank_has_room(state, game_data, ctx)
                and _has_sellable(state, game_data))
```

- [ ] **Step 4: `map_guard` branch** (import `SellInventoryGoal`):
```python
    if kind is GuardKind.SELL_RELIEF:
        return SellInventoryGoal(bank_accessible=ctx.bank_accessible,
                                 game_data=game_data)
```
(Match the real `SellInventoryGoal.__init__` signature from
`goals/sell_inventory.py` and the `MeansKind.SELL_PRESSURED` mapping at
`strategy_driver.py:332-333`.)

- [ ] **Step 5: Run production tests to green.**

- [ ] **Step 6: Lean** — `MeansKind.sellRelief`; insert into `allInLadderOrder`
after `.recycleRelief`; length example → 25.
```lean
def sellReliefFires (s : State) : Bool :=
  !(bankHasRoom s) && s.sellableInventoryNonempty
```
add the `fires` arm.

- [ ] **Step 7: Lean re-proof** — same theorem set as Task 4 Step 7 (the
destructuring indices shift again by 1). Add
`_fires_sellRelief_implies_sellInventory_positive` (model on
`_fires_sellPressured_implies_sellInventory_positive` — `sellInventoryValue`
exists, so this slot CAN be asserted, not deferred). Build clean.

- [ ] **Step 8: Differential** — `SELL_RELIEF` in `LadderMeans`/`ALL_IN_LADDER_ORDER`/
`fires`; drive its oracle signal from `sellableInventoryNonempty` (arg[22], which
already exists and is driven from `item_sellable && junk_qty>0`). Add to
`ASSERTED_SLOTS` (not deferred). Add a boundary witness: bank-full + sellable →
`SELL_RELIEF` fires; bank-has-room + sellable → quiet. Run the diff green.

- [ ] **Step 9: Mutation refresh, full gates, commit** (as Task 4 Step 9).

```bash
git commit -am "feat(ai+formal): SELL_RELIEF guard — sell surplus under bank-full"
```

---

### Task 6: Sole-output craft extension

Broaden `craft_relief_candidates` to also craft a material whose recipe-output is
unique (e.g. `copper_ore → copper_bar`), net-relief gated. `craft_relief_candidates`
is a DRIVEN/passthrough oracle signal (arg[27], `CRAFT_RELIEF` deferred), so the
differential stays consistent automatically; only production correctness tests are
needed.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/craft_relief.py` (`craft_relief_candidates` / its candidate builder)
- Test: `tests/test_ai/test_craft_relief.py`

- [ ] **Step 1: Failing test**

Add to `tests/test_ai/test_craft_relief.py`:
```python
def test_sole_output_material_is_a_candidate():
    """A held material whose ONLY craftable output is one item (copper_ore ->
    copper_bar) is a relief candidate even off the goal chain."""
    gd = GameData()
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}   # copper_ore's only output
    gd._item_stats = {
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    # workshop + skill so the craft is feasible; 30 ore on hand (3 bars, net relief)
    state = make_state(inventory={"copper_ore": 30}, inventory_max=40,
                       skills={"mining": 5})
    cands = craft_relief_candidates(state, gd, step_items=frozenset())
    assert any(c.item_code == "copper_bar" for c in cands)


def test_multi_output_material_not_sole_output():
    """A material that feeds >1 recipe is NOT a sole-output candidate."""
    gd = GameData()
    gd._crafting_recipes = {"bar_a": {"ore": 5}, "bar_b": {"ore": 5}}
    ...
    cands = craft_relief_candidates(state, gd, step_items=frozenset())
    assert not any(c.item_code in ("bar_a", "bar_b") for c in cands)
```

(Confirm the `GrindCandidate`/candidate dataclass field name — the explorer
showed `craft_relief_candidates` returns objects with `.item_code` and
`.quantity`; match the real attribute names from `craft_relief.py`.)

- [ ] **Step 2: Run, verify fail** — sole-output candidate absent today.

- [ ] **Step 3: Implement**

Read `src/artifactsmmo_cli/ai/craft_relief.py:101-159` (`craft_relief_candidates`)
and its `_net_relief_per_craft`/`_can_craft_qty` helpers. Add a candidate source:
for each held material `m`, compute the set of craftable outputs whose recipe
lists `m` as an input (`outputs = {code for code, rec in
game_data.crafting_recipes.items() if m in rec}`); if `len(outputs) == 1`, that
sole output is a candidate when craftable ≥1 now AND `_net_relief_per_craft > 0`.
Merge with the existing goal-chain candidates (dedupe by output code). Keep the
existing ordering/selection.

- [ ] **Step 4: Run tests to green** + the full `test_craft_relief.py`.

- [ ] **Step 5: Differential unaffected** — `craft_relief_candidates` feeds arg[27]
(deferred/passthrough). Run `~/.local/bin/uv run pytest formal/diff/test_ladder_fires_diff.py --no-cov`; expect still GREEN (no slot semantics changed).

- [ ] **Step 6: Mutation refresh (craft_relief changed), full gates, commit**

```bash
git add src/artifactsmmo_cli/ai/craft_relief.py tests/test_ai/test_craft_relief.py
git commit -m "feat(ai): craft-relief also crafts sole-output materials under pressure"
```

---

### Task 7: Bank-full integration scenario + final gate

End-to-end assertion that the cascade orders correctly, plus the full formal gate.

**Files:**
- Test: `tests/test_ai/test_strategy_driver.py` (or `test_guards.py`) — integration
- Read-only: `formal/gate.sh`

- [ ] **Step 1: Integration test — cascade ordering**

Add a test driving `active_guards(...)` (returns guards in ladder order) over a
bank-full, bag-pressured state and asserting the FIRST fired guard is, in turn:
- with a craft candidate present → `CRAFT_RELIEF` first;
- craft exhausted, recycle surplus present → `RECYCLE_RELIEF` first;
- recycle exhausted, sellable present → `SELL_RELIEF` first;
- only a worthless overstock item left → `DISCARD_CRITICAL`/`DISCARD_HIGH`;
and `DEPOSIT_FULL` never appears while `¬bank_has_room`.
```python
def test_bank_full_cascade_order():
    gd, ctx = _bank_full_gd_ctx()
    # craft candidate present:
    fired = active_guards(_state_with_craft(), gd, None, ctx)
    assert fired and fired[0] is GuardKind.CRAFT_RELIEF
    # ... recycle / sell / discard sub-cases ...
    # bank has room: deposit, no relief-discard:
    fired_room = active_guards(_state_bank_room(), gd, None, ctx)
    assert GuardKind.DEPOSIT_FULL in fired_room
    assert GuardKind.DISCARD_HIGH not in fired_room
    assert GuardKind.RECYCLE_RELIEF not in fired_room
```
Build the `_state_*` fixtures from the per-task fixtures. Run to green.

- [ ] **Step 2: Full formal gate (serialize — nothing else importing src/running)**

Run: `cd formal && bash gate.sh 2>&1 | tail -40`
Expected: the BankSelection / `test_ladder_fires_diff` slot GREEN; new
RECYCLE_RELIEF/SELL_RELIEF slots covered; no NEW failures. (Pre-existing OTHER
baseline defects may remain red — confirm each red is on base via
`git stash && cd formal && bash gate.sh` comparison, and is NOT one of our slots.)

- [ ] **Step 3: `git diff src` audit + memory update**

Run `git diff --stat $(git merge-base main HEAD) HEAD` — confirm only the intended
files. Update auto-memory: mark [[project_inventory_livelock_fix]] /
[[project_zombie_commitment_livelock]]'s BankSelection-residual note RESOLVED;
add a pointer for the bank-full cascade.

- [ ] **Step 4: Finish the branch** — invoke `superpowers:finishing-a-development-branch`.

---

## Self-Review

**Spec coverage:**
- `bank_has_room` predicate (+Lean mirror) → Task 1. ✓
- `DEPOSIT_FULL` bank_has_room gate + residual fix → Task 2. ✓
- `DISCARD_*` ¬bank_has_room gate + worthless-only delete → Task 3. ✓
- `RECYCLE_RELIEF` guard (recycle under bank-full) → Task 4. ✓
- `SELL_RELIEF` guard (sell under bank-full) → Task 5. ✓
- Sole-output craft extension → Task 6. ✓
- Guard ordering craft>recycle>sell>deposit/discard → Tasks 4/5 ordering + Task 7 assertion. ✓
- Lean lockstep + differential + mutation each task; full gate → Task 7. ✓
- `CRAFT_RELIEF` unchanged (bank-agnostic, tier-1) → no task touches its predicate. ✓

**Placeholder scan:** Lean proof TACTICS are intentionally not pre-written (interactive — use lean4 skills); every PRODUCTION code + test step has concrete code or a concrete "read X:lines, mirror pattern Y" instruction with the exact fixture source named. Two test bodies (Task 3 Step 4, Task 4/5 fixtures) say "build from existing fixture file Z" rather than inlining — acceptable because the exact witness lives in a named existing test the implementer reads.

**Type/name consistency:** `bank_has_room(state, game_data, ctx)` / `bankHasRoom (s)` used identically Tasks 1–5. `GuardKind.RECYCLE_RELIEF`/`SELL_RELIEF`, `MeansKind.recycleRelief`/`sellRelief`, `recycleReliefFires`/`sellReliefFires`, `LadderMeans.RECYCLE_RELIEF`/`SELL_RELIEF` consistent across production/Lean/diff. Ordering `CRAFT_RELIEF, RECYCLE_RELIEF, SELL_RELIEF, DEPOSIT_FULL, DISCARD_CRITICAL, DISCARD_HIGH` consistent between guards.py `GUARD_ORDER`, Lean `allInLadderOrder`, and `ALL_IN_LADDER_ORDER`.

**Risk note:** `PursueTaskSelection.lean`'s position-sensitive `obtain ⟨h1..h15⟩` re-proof (Tasks 4 & 5) is the highest-effort, highest-risk step. If it proves intractable in lockstep, fall back to placing RECYCLE_RELIEF/SELL_RELIEF as opaque DEFERRED slots (like RECYCLE_SURPLUS) so the diff asserts production only — record the reduced coverage with `log()`/a comment, do not silently defer.
