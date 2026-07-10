# Slot-Aware Inventory Room Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the planner model the game's per-slot inventory cap (not just total quantity) so the bot stops livelocking on HTTP 497 when its 20 slots are full but quantity has headroom.

**Architecture:** Add `inventory_slots_max` to `WorldState` (from `len(char.inventory)`), derive `inventory_slots_used/free` from the stack dict; extract a pure `has_room(new_stacks, added_qty, slots_free, qty_free)` core (Lean-mirrored); gate stack-creating actions (equip/optimize/gather/withdraw) on it; and fire the existing relief ladder on `slots_free == 0`. Both the 20-slot and 124-quantity caps stay honest.

**Tech Stack:** Python 3.13, `uv`, pytest (100% coverage on `src/`), mypy strict, Lean 4 (`formal/`). Reuses the proven-core pattern (`gather_apply_core.py` + `GatherApply.lean`, `ActionApplicability.lean`).

## Global Constraints

- `uv run` prefix on ALL python/pytest/mypy/lake commands.
- No inline imports (top-of-file). NEVER catch `Exception`. No `if TYPE_CHECKING`. No `...` imports. ONE behavioral class per file (pure-data dataclasses may share a module).
- Use only API/bundle data or fail with an error — no silent defaulting. Multiple levels of error handling is a bug.
- 100% coverage + mypy-strict clean on everything under `src/artifactsmmo_cli/`. TDD: failing test first, watch fail, minimal code, watch pass, commit.
- Decision-path arithmetic is EXACT integers — no float (mechanical-extraction rule). New pure cores ship extracted + Lean-mirrored + differential + mutation-anchored (the repo pattern: see `gather_apply_core.py`↔`GatherApply.lean`, `ActionApplicability.lean`).
- `formal/diff` is NOT in the default pytest path — after ANY change to a pure core's arithmetic/signature, run `uv run pytest formal/diff` explicitly AND `cd formal && lake build`.
- Commit `--no-verify` acceptable when the full pre-commit suite exceeds the tool budget; document it; targeted `uv run pytest <files>` + module-100% + `uv run mypy src/...` are the evidence.
- The bot is LIVE-capable: never run gate.sh/mutate.py concurrent with anything importing `src` including the bot; serialize (see [[feedback_serialize_gate_runs]]).
- Runtime activation is MANDATORY: the fix must FIRE on a live `plan Robby` / trace (the 497 loop breaks) before "done" — green tests ≠ runtime-active ([[feedback_verify_runtime_activation]]).

## Key existing interfaces (read before starting)

- `WorldState` (`src/artifactsmmo_cli/ai/world_state.py:58`): frozen dataclass; `inventory: dict[str,int]` (code→qty, line 72); `inventory_max: int` (line 73, = total-quantity cap); `inventory_used` property `sum(values)` (line 182); `inventory_free` property (line 187). Built by `from_character_schema` (line ~204), which folds `char.inventory` (the API slot list) into the qty dict at line 216-219 (`if slot.code and slot.quantity > 0`), and passes `inventory_max=char.inventory_max_items` at line 268.
- `GatherInv` + `gather_is_applicable_pure(inv, min_free)` (`src/artifactsmmo_cli/ai/actions/gather_apply_core.py`): `GatherInv(used, cap, item_count)`; `gather_is_applicable_pure` returns `(cap-used) >= min_free`. Proven in `formal/Formal/GatherApply.lean`.
- `GatherAction.is_applicable` (`gathering.py:74`), `EquipAction.is_applicable` (`equip.py:45`, NO space guard), `WithdrawItemAction.is_applicable` (`withdraw_item.py:31`, `inventory_free >= quantity`), `OptimizeLoadoutAction.is_applicable` (`optimize_loadout.py:82`, no space guard).
- Relief: `bank_selection.py:~180` returns non-keep deposits + a last-resort keep item gated on `inventory_free == 0`. The deposit GOAL trigger is `deposit_inventory.py:45` (`used_fraction = inventory_used / inventory_max`) and the `inventory_caps.py` overstock watermark (`inventory_used/inventory_max >= 17/20`) — both quantity-based.
- Lean applicability gate: `formal/Formal/ActionApplicability.lean:66` `hasInventoryRoom(inventoryFree, minFreeSlots)`.

---

### Task 0: Confirm capacity source (live probe) + empty-slot fixture

**Files:**
- Create: `tests/test_ai/fixtures/character_with_empty_slots.json` (a `CharacterSchema` JSON whose `inventory` list has BOTH filled and empty-code slots).
- Test: `tests/test_ai/test_world_state_slots.py` (new).

**Why:** the whole model rests on `len(char.inventory)` = slot capacity, which requires the API to return empty slots. Robby is 20/20 full so a live read alone can't confirm it. This task proves it with a reversible probe, then encodes an empty-slot fixture so the rest of the plan is testable offline.

- [ ] **Step 1: Reversible live probe (manual, record the result in the Task-0 report)**

Run (deposits 1 unit of a junk singleton, re-reads, then restores):
```bash
export PATH="$HOME/.local/bin:$PATH"
uv run python - <<'PY'
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config
from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_char
ClientManager().initialize(Config.from_token_file(None))
cl = ClientManager().client
def snap():
    inv = get_char(client=cl, name="Robby").data.inventory
    return len(inv), sum(1 for s in inv if s.code), sum(1 for s in inv if not s.code)
print("before:", snap())  # (len, filled, empty)
PY
```
Record `(len, filled, empty)`. Interpretation:
- If `len == 20, empty == 0` at 20/20 full → consistent with capacity 20, but does NOT prove empties are returned. Proceed to the deposit-probe below.
- Deposit-probe (only if Robby is full and you cannot otherwise observe an empty slot): deposit 1 unit of the LOWEST-value singleton (e.g. `topaz_stone`) to the bank, re-read `snap()`, then WITHDRAW it back. If after the deposit `len == 20, empty == 1` → API returns empty slots, `len` = capacity (CONFIRMED). If `len == 19, empty == 0` → API returns only filled slots (len = USED, not capacity) → STOP and escalate: the plan's capacity source is wrong and Task 1 must use the fallback (max `slot` index or a game constant). Restore by withdrawing the deposited unit; verify `snap()` returns to the original.

DO NOT proceed to Task 1 until the probe result is recorded in `.superpowers/sdd/task-0-report.md`. If CONFIRMED, the plan proceeds as written. If DISPROVEN, escalate to the controller for a capacity-source revision.

- [ ] **Step 2: Build the empty-slot fixture**

Create `tests/test_ai/fixtures/character_with_empty_slots.json` — a minimal `CharacterSchema` with `inventory_max_items` set and an `inventory` array containing (for example) 3 filled slots and 2 empty-code slots (`{"slot": N, "code": "", "quantity": 0}`), plus the other required CharacterSchema fields. Copy the structure of an existing character fixture if one exists (`grep -rl inventory_max_items tests/ --include=*.json`); if none has a raw slot list, build it from `CharacterSchema`'s required fields (see `artifactsmmo-api-client/.../models/character_schema.py`). The fixture must round-trip through `CharacterSchema.from_dict`.

- [ ] **Step 3: Write the failing test proving len=capacity, filled=used**

```python
# tests/test_ai/test_world_state_slots.py
import json
from pathlib import Path

from artifactsmmo_api_client.models.character_schema import CharacterSchema
from artifactsmmo_cli.ai.world_state import WorldState

FIXTURE = Path("tests/test_ai/fixtures/character_with_empty_slots.json")


def test_from_character_schema_captures_slot_capacity() -> None:
    """slots_max = total slot count (filled + empty); slots_used = filled
    stacks; slots_free = empty slots. Proves the model reads the slot cap the
    server enforces, not the quantity cap."""
    char = CharacterSchema.from_dict(json.loads(FIXTURE.read_text()))
    total = len(char.inventory)
    filled = sum(1 for s in char.inventory if s.code and s.quantity > 0)
    state = WorldState.from_character_schema(char)
    assert state.inventory_slots_max == total
    assert state.inventory_slots_used == filled
    assert state.inventory_slots_free == total - filled
```

- [ ] **Step 4: Run it — verify it fails**

Run: `uv run pytest tests/test_ai/test_world_state_slots.py -v --no-cov`
Expected: FAIL — `AttributeError: 'WorldState' object has no attribute 'inventory_slots_max'` (Task 1 adds it).

- [ ] **Step 5: Commit the fixture + failing test**

```bash
git add tests/test_ai/fixtures/character_with_empty_slots.json tests/test_ai/test_world_state_slots.py
git commit --no-verify -m "test(inventory): empty-slot fixture + slot-capacity probe (Task 0)"
```
(The test is RED until Task 1; that is intended — the commit records the verification artifact. Note in the Task-0 report that this test goes green in Task 1.)

---

### Task 1: WorldState slot dimension

**Files:**
- Modify: `src/artifactsmmo_cli/ai/world_state.py` (add field + properties + `from_character_schema` wiring)
- Test: `tests/test_ai/test_world_state_slots.py` (the Task-0 test goes green; add derived-property tests)

**Interfaces:**
- Produces: `WorldState.inventory_slots_max: int` (stored field, default matching `inventory_max`-adjacent placement), `WorldState.inventory_slots_used` (property = `len(self.inventory)`), `WorldState.inventory_slots_free` (property = `inventory_slots_max - inventory_slots_used`).

- [ ] **Step 1: Write the failing derived-property test**

```python
# add to tests/test_ai/test_world_state_slots.py
from datetime import datetime, timezone

def _bare_state(inventory: dict[str, int], slots_max: int) -> WorldState:
    return WorldState(
        character="t", level=1, xp=0, max_xp=100, hp=10, max_hp=10, gold=0,
        skills={}, x=0, y=0, inventory=inventory, inventory_max=124,
        inventory_slots_max=slots_max, equipment={}, cooldown_expires=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        bank_items=None, bank_gold=None, pending_items=None,
    )


def test_slots_used_is_distinct_stack_count() -> None:
    """slots_used counts DISTINCT stacks (dict keys), not total quantity."""
    s = _bare_state({"copper_ore": 50, "feather": 3}, slots_max=20)
    assert s.inventory_slots_used == 2       # two stacks
    assert s.inventory_used == 53            # quantity unchanged
    assert s.inventory_slots_free == 18


def test_slots_free_zero_when_all_stacks_occupy_capacity() -> None:
    """20 distinct stacks at slots_max 20 -> 0 free, regardless of quantity."""
    inv = {f"item_{i}": 1 for i in range(20)}
    s = _bare_state(inv, slots_max=20)
    assert s.inventory_slots_used == 20
    assert s.inventory_slots_free == 0
    assert s.inventory_free > 0              # quantity has headroom (124-20)
```

- [ ] **Step 2: Run it — verify it fails**

Run: `uv run pytest tests/test_ai/test_world_state_slots.py -v --no-cov`
Expected: FAIL — `WorldState.__init__() got an unexpected keyword argument 'inventory_slots_max'`.

- [ ] **Step 3: Add the field + properties**

In `world_state.py`, add the stored field immediately after `inventory_max` (line 73) so it sits with the other inventory fields:

```python
    inventory_max: int               # max total item quantity (not unique stacks)
    inventory_slots_max: int         # number of inventory SLOTS (distinct-stack cap)
```

Add the two properties next to `inventory_free` (after line 189):

```python
    @property
    def inventory_slots_used(self) -> int:
        """Number of occupied inventory SLOTS = distinct stacks held."""
        return len(self.inventory)

    @property
    def inventory_slots_free(self) -> int:
        """Remaining inventory SLOTS (slot cap minus distinct stacks held)."""
        return self.inventory_slots_max - self.inventory_slots_used
```

NOTE: `inventory_slots_max` is a REQUIRED positional field (no default) placed among the other required fields (before the first defaulted field `bank_capacity` at line 86). This forces every `WorldState(...)` construction to supply it — surfacing all call sites at once (mypy will list them). Update every direct `WorldState(...)` construction in `src/` and `tests/` to pass `inventory_slots_max=...` (mypy strict + the test suite enumerate them). For non-schema/test constructions with no natural slot cap, pass `inventory_slots_max=len(inventory)` (i.e. "exactly full", the conservative default that keeps existing quantity-only behavior unless a test sets more).

- [ ] **Step 4: Wire `from_character_schema`**

In `from_character_schema`, capture the slot count where `inventory` is folded (line 216-219) and pass it to the constructor (near line 268):

```python
        inventory: dict[str, int] = {}
        slots_max = 0
        if not isinstance(char.inventory, Unset) and char.inventory:
            slots_max = len(char.inventory)
            for slot in char.inventory:
                if slot.code and slot.quantity > 0:
                    inventory[slot.code] = inventory.get(slot.code, 0) + slot.quantity
```
and in the `cls(...)` call add:
```python
            inventory_max=char.inventory_max_items,
            inventory_slots_max=slots_max,
```
(If `char.inventory` is Unset/empty, `slots_max = 0`; that only happens for a schema with no inventory list — acceptable, matches "no known slots".)

- [ ] **Step 5: Run tests — Task 0 test + new tests green**

Run: `uv run pytest tests/test_ai/test_world_state_slots.py -v --no-cov`
Expected: all PASS (including `test_from_character_schema_captures_slot_capacity` from Task 0).

- [ ] **Step 6: Fix all broken constructions, then full targeted run**

Run `uv run mypy src/artifactsmmo_cli/ai/world_state.py` and `uv run pytest tests/ -x -q --no-cov 2>&1 | head -40` to surface every `WorldState(...)` missing the new arg; add `inventory_slots_max=len(inventory)` (or the intended cap) to each. Repeat until green. Then:
- `uv run pytest tests/test_ai/ -q --no-cov` → green
- `uv run mypy src/artifactsmmo_cli/ai/world_state.py` → Success

- [ ] **Step 7: Snapshot regen check**

If any snapshot/fixture JSON encodes a serialized `WorldState`, regen per [[reference_snapshot_regen]] (`grep -rl inventory_max tests/ formal/ --include=*.json`). If a `formal/` snapshot mirrors WorldState fields, add `inventory_slots_max` and rebuild the fixture. Record what was regenerated.

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/ai/world_state.py tests/test_ai/test_world_state_slots.py
# + any construction-site files and regenerated snapshots
git commit --no-verify -m "feat(inventory): WorldState slot dimension (slots_max/used/free)"
```

---

### Task 2: Pure `has_room` core

**Files:**
- Create: `src/artifactsmmo_cli/ai/inventory_room.py`
- Test: `tests/test_ai/test_inventory_room.py`

**Interfaces:**
- Produces: `has_room(new_stacks: int, added_qty: int, slots_free: int, qty_free: int) -> bool`.

- [ ] **Step 1: Write the failing truth-table test**

```python
# tests/test_ai/test_inventory_room.py
from artifactsmmo_cli.ai.inventory_room import has_room


def test_new_stack_blocked_when_no_free_slot_even_with_qty_room() -> None:
    """A stack-CREATING action needs a free slot even if quantity has headroom
    — the slot-exhaustion bug. slots_free 0, qty_free 50 -> blocked."""
    assert has_room(new_stacks=1, added_qty=1, slots_free=0, qty_free=50) is False


def test_grow_stack_allowed_when_no_free_slot() -> None:
    """Growing a HELD stack needs no new slot — only quantity headroom."""
    assert has_room(new_stacks=0, added_qty=1, slots_free=0, qty_free=50) is True


def test_blocked_when_qty_full_even_with_free_slot() -> None:
    """The quantity cap still binds: no quantity headroom -> blocked."""
    assert has_room(new_stacks=1, added_qty=1, slots_free=5, qty_free=0) is False


def test_allowed_when_both_caps_have_room() -> None:
    assert has_room(new_stacks=1, added_qty=3, slots_free=2, qty_free=10) is True


def test_multi_new_stacks_need_enough_free_slots() -> None:
    """new_stacks may exceed 1 (a swap displacing two distinct items)."""
    assert has_room(new_stacks=2, added_qty=2, slots_free=1, qty_free=10) is False
    assert has_room(new_stacks=2, added_qty=2, slots_free=2, qty_free=10) is True
```

- [ ] **Step 2: Run — verify it fails** (`ModuleNotFoundError`).

Run: `uv run pytest tests/test_ai/test_inventory_room.py -v --no-cov`

- [ ] **Step 3: Implement**

```python
# src/artifactsmmo_cli/ai/inventory_room.py
"""Pure slot+quantity inventory-room core (spec 2026-07-09-slot-aware-inventory
-room). The single decision seam behind every stack-creating action's space
guard: the game enforces BOTH a per-slot cap and a total-quantity cap, so a
NEW distinct stack needs a free slot AND quantity headroom, while GROWING a
held stack needs only quantity headroom. Exact integer arithmetic — mirrored
in formal/Formal/InventoryRoom.lean."""


def has_room(new_stacks: int, added_qty: int,
             slots_free: int, qty_free: int) -> bool:
    """True iff an action adding `new_stacks` distinct stacks and `added_qty`
    total items fits: `new_stacks <= slots_free AND added_qty <= qty_free`.
    `new_stacks=0` (grow a held stack) ignores the slot cap; `added_qty` may be
    0 (quantity-neutral swap) which the qty term trivially passes."""
    return new_stacks <= slots_free and added_qty <= qty_free
```

- [ ] **Step 4: Run — verify green + 100%**

Run:
```
uv run pytest tests/test_ai/test_inventory_room.py -v --no-cov
uv run pytest tests/test_ai/test_inventory_room.py --cov=artifactsmmo_cli.ai.inventory_room --cov-report=term-missing -q 2>&1 | grep -i "inventory_room\|TOTAL"
uv run mypy src/artifactsmmo_cli/ai/inventory_room.py
```
Expected: all pass, module 100%, mypy Success.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/inventory_room.py tests/test_ai/test_inventory_room.py
git commit --no-verify -m "feat(inventory): has_room slot+quantity pure core"
```

---

### Task 3: Lean mirror of `has_room` + differential

**Files:**
- Create: `formal/Formal/InventoryRoom.lean`
- Modify: `formal/diff/` differential harness for the new core (follow an existing `formal/diff/*` mirror, e.g. the GatherApply or ActionApplicability differential); `formal/gate` manifest if new modules are indexed.
- Modify (Task 6 will consume): none here.

**Interfaces:**
- Produces: `InventoryRoom.hasRoom (newStacks addedQty slotsFree qtyFree : Int) : Bool` proven equivalent to the Python `has_room`.

- [ ] **Step 1: Write the Lean core + independence theorems**

Mirror `has_room` exactly:
```lean
-- formal/Formal/InventoryRoom.lean
-- @concept: inventory, slot-room @property: safety
namespace InventoryRoom

/-- A stack-creating action fits iff it has a free slot per new stack AND
    quantity headroom. Mirrors Python `has_room`. -/
def hasRoom (newStacks addedQty slotsFree qtyFree : Int) : Bool :=
  decide (newStacks ≤ slotsFree) && decide (addedQty ≤ qtyFree)

/-- No free slot for a new stack -> blocked, regardless of quantity room. -/
theorem hasRoom_false_of_no_slot (newStacks addedQty slotsFree qtyFree : Int)
    (h : newStacks > slotsFree) : hasRoom newStacks addedQty slotsFree qtyFree = false := by
  unfold hasRoom; simp; omega

/-- No quantity room -> blocked, regardless of slots. -/
theorem hasRoom_false_of_no_qty (newStacks addedQty slotsFree qtyFree : Int)
    (h : addedQty > qtyFree) : hasRoom newStacks addedQty slotsFree qtyFree = false := by
  unfold hasRoom; simp; omega

/-- Grow-stack (newStacks = 0) ignores the slot cap. -/
theorem hasRoom_grow_ignores_slots (addedQty qtyFree : Int)
    (hq : addedQty ≤ qtyFree) (hs : (0:Int) ≤ slotsFree) :
    hasRoom 0 addedQty slotsFree qtyFree = true := by
  unfold hasRoom; simp [hq]; omega

end InventoryRoom
```
(Exact tactic bodies may need adjustment for the repo's Lean/Mathlib — use the `lean4` proof-repair agent if a proof does not close; the CONTRACT is the three independence theorems + the definitional mirror.)

- [ ] **Step 2: Build**

Run: `cd formal && lake build 2>&1 | tail -20`
Expected: builds clean, no `sorry`, no new axioms (`uv run` the repo's axiom-lint if present).

- [ ] **Step 3: Differential lockstep**

Add a `formal/diff` case that evaluates `hasRoom` and the Python `has_room` over a shared input table (mirror the nearest existing differential, e.g. the one for `gather_is_applicable_pure`). The table MUST include: new-stack-no-slot (blocked), grow-stack-no-slot (allowed), qty-full (blocked), both-room (allowed), multi-new-stack boundary. Run `uv run pytest formal/diff -q` and confirm Python↔Lean agree on every row.

- [ ] **Step 4: Mutation anchors**

Add the new core to the mutation harness so a flipped `≤`/`&&` is caught (follow the existing anchor pattern; see [[project_o54_select_differential]]). Do NOT run the full `mutate.py` here if the bot is live — record the anchors and let the gate run serialize them.

- [ ] **Step 5: Commit**

```bash
git add formal/Formal/InventoryRoom.lean formal/diff/ formal/gate/
git commit --no-verify -m "feat(formal): InventoryRoom.hasRoom mirror + differential"
```

---

### Task 4: Gate `GatherAction` on slot room

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/gather_apply_core.py` (extend `GatherInv` + `gather_is_applicable_pure` with slot awareness)
- Modify: `src/artifactsmmo_cli/ai/actions/gathering.py` (pass slot info)
- Modify: `formal/Formal/GatherApply.lean` (the applicability contract gains the slot term)
- Test: `tests/test_ai/test_gather_apply_core.py` (or the existing gather test module)

**Interfaces:**
- Consumes: `has_room` (Task 2). `GatherInv` gains `slots_used: int`, `slots_max: int`.
- Produces: `gather_is_applicable_pure(inv, min_free)` now returns False when gathering a NEW drop stack has no free slot.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_gather_apply_core.py (add)
from artifactsmmo_cli.ai.actions.gather_apply_core import (
    GatherInv, gather_is_applicable_pure,
)


def test_gather_blocked_when_new_drop_needs_slot_but_none_free() -> None:
    """Gathering a NOT-yet-held drop with 0 free slots is blocked even though
    quantity has room (the slot-exhaustion case)."""
    inv = GatherInv(used=20, cap=124, item_count={f"i{n}": 1 for n in range(20)},
                    slots_used=20, slots_max=20)
    # drop_item is a NEW code (not in item_count): needs a slot -> blocked
    assert gather_is_applicable_pure(inv, min_free=1, drop_item="copper_ore") is False


def test_gather_allowed_when_drop_grows_held_stack_with_no_free_slot() -> None:
    """Gathering MORE of a held drop needs no slot -> allowed at 0 free slots
    (quantity permitting)."""
    inv = GatherInv(used=20, cap=124,
                    item_count={"copper_ore": 5, **{f"i{n}": 1 for n in range(19)}},
                    slots_used=20, slots_max=20)
    assert gather_is_applicable_pure(inv, min_free=1, drop_item="copper_ore") is True
```

- [ ] **Step 2: Run — verify it fails** (signature mismatch: `drop_item`/`slots_*` not accepted).

- [ ] **Step 3: Extend the pure core**

In `gather_apply_core.py`, add slot fields to `GatherInv` and thread `has_room` into applicability:

```python
from artifactsmmo_cli.ai.inventory_room import has_room


@dataclass(frozen=True)
class GatherInv:
    """Minimal projection of `WorldState` that `GatherAction` reads."""

    used: int
    cap: int
    item_count: Mapping[str, int]
    slots_used: int = 0
    slots_max: int = 0


def gather_is_applicable_pure(inv: GatherInv, min_free: int,
                              drop_item: str | None = None) -> bool:
    """Gathering is applicable iff there is room for the yielded drop under BOTH
    the quantity floor (`min_free`) and the slot cap. A gather yields the ore
    plus possible bonus drops; `min_free` remains the quantity floor. When
    `drop_item` is known, gathering a NEW code (not in `item_count`) also needs
    a free slot; gathering more of a held code does not."""
    if (inv.cap - inv.used) < min_free:
        return False
    if drop_item is None:
        return True
    new_stacks = 0 if drop_item in inv.item_count else 1
    slots_free = inv.slots_max - inv.slots_used
    qty_free = inv.cap - inv.used
    return has_room(new_stacks, added_qty=1, slots_free=slots_free, qty_free=qty_free)
```
(Keep the `min_free` quantity floor — it is the existing chain-safety guard; the slot term is additive. `drop_item=None` preserves the old behavior for callers that don't pass it.)

- [ ] **Step 4: Wire `GatherAction.is_applicable`**

In `gathering.py:74-84`, build `GatherInv` with slot fields and pass the resolved drop item:

```python
    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.locations:
            return False
        drop_item = (self.drop_item_override
                     or game_data.resource_drop_item(self.resource_code)
                     or self.resource_code)
        inv = GatherInv(used=state.inventory_used, cap=state.inventory_max,
                        item_count=state.inventory,
                        slots_used=state.inventory_slots_used,
                        slots_max=state.inventory_slots_max)
        skill_req = game_data.resource_skill_level(self.resource_code)
        if skill_req is None:
            return gather_is_applicable_pure(inv, self._MIN_FREE_SLOTS, drop_item)
        skill, level = skill_req
        return (state.skills.get(skill, 1) >= level
                and gather_is_applicable_pure(inv, self._MIN_FREE_SLOTS, drop_item))
```

- [ ] **Step 5: Update `GatherApply.lean`**

The Lean applicability contract (`formal/Formal/GatherApply.lean`) gains the slot term mirroring the extended `gather_is_applicable_pure`: applicability = `(cap-used ≥ minFree) ∧ hasRoom(newStack, 1, slotsFree, qtyFree)`. Reuse `InventoryRoom.hasRoom` (Task 3). Prove the existing safety corollary still holds (a passing gather cannot mint past cap AND cannot create a stack past slot cap). Use the `lean4` proof-repair agent if needed. `cd formal && lake build`.

- [ ] **Step 6: Run — green + coverage + differential**

Run:
```
uv run pytest tests/test_ai/test_gather_apply_core.py tests/test_ai/ -q --no-cov 2>&1 | tail -20
uv run pytest tests/test_ai/test_gather_apply_core.py --cov=artifactsmmo_cli.ai.actions.gather_apply_core --cov-report=term-missing -q 2>&1 | grep -i "gather_apply_core\|TOTAL"
uv run mypy src/artifactsmmo_cli/ai/actions/gather_apply_core.py src/artifactsmmo_cli/ai/actions/gathering.py
uv run pytest formal/diff -q
```
Expected: green; gather_apply_core 100%; mypy Success; formal/diff green. Fix any gather scenario tests whose expected applicability changes (a gather at a full bag for a NEW drop is now correctly non-applicable) — verify each change is a genuine slot-correctness shift, not a regression.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/gather_apply_core.py src/artifactsmmo_cli/ai/actions/gathering.py formal/Formal/GatherApply.lean formal/diff/ tests/test_ai/test_gather_apply_core.py
git commit --no-verify -m "feat(inventory): gate GatherAction on slot room"
```

---

### Task 5: Gate `EquipAction` on net-slot room

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/equip.py` (`is_applicable`)
- Test: `tests/test_ai/test_equip_action.py` (or the existing equip test module)

**Interfaces:**
- Consumes: `has_room` (Task 2), `WorldState.inventory_slots_free`.

The net-slot arithmetic (spec §Components.3): equipping code `C` into `slot` displaces the current item `O`. Quantity is neutral (`added_qty=0`: −1 `C`, +1 `O`). New-slot need = `max(0, O_needs_slot − C_frees_slot)`:
- `O_needs_slot = 1` iff `O is not None` and `O not in state.inventory` (a genuinely new displaced stack).
- `C_frees_slot = 1` iff `state.inventory.get(C, 0) == 1` (equipping empties `C`'s stack, freeing its slot).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai/test_equip_action.py (add)
def test_equip_blocked_when_displaced_item_needs_slot_and_bag_full(make_state):
    """Full bag (0 slots free), equipping C displaces a NEW item O not held and
    C's stack does NOT empty (qty>1) -> needs a slot -> not applicable."""
    # bag: C has qty 2 (won't free a slot), 19 other singleton stacks -> 20/20
    inv = {"C": 2, **{f"j{n}": 1 for n in range(19)}}
    state = make_state(inventory=inv, slots_max=20,
                       equipment={"body_armor_slot": "O"})  # O currently worn, not in inv
    action = EquipAction(code="C", slot="body_armor_slot")
    # C is body armor, level ok, held; but displaced O needs a slot, none free
    assert action.is_applicable(state, game_data) is False


def test_equip_allowed_when_equipped_stack_frees_slot_for_displaced(make_state):
    """C has qty 1 -> equipping empties C's slot, which absorbs displaced O ->
    net zero new slots -> applicable even at 0 free slots."""
    inv = {"C": 1, **{f"j{n}": 1 for n in range(19)}}
    state = make_state(inventory=inv, slots_max=20,
                       equipment={"body_armor_slot": "O"})
    action = EquipAction(code="C", slot="body_armor_slot")
    assert action.is_applicable(state, game_data) is True


def test_equip_allowed_when_displaced_item_already_held(make_state):
    """Displaced O already a held stack -> returning it grows that stack, no new
    slot -> applicable at 0 free slots."""
    inv = {"C": 2, "O": 3, **{f"j{n}": 1 for n in range(18)}}
    state = make_state(inventory=inv, slots_max=20,
                       equipment={"body_armor_slot": "O"})
    action = EquipAction(code="C", slot="body_armor_slot")
    assert action.is_applicable(state, game_data) is True
```
(Adapt `make_state`/`game_data` to the existing equip test fixtures. If the equip test module builds `WorldState` directly, pass `inventory_slots_max=slots_max`.)

- [ ] **Step 2: Run — verify the first fails** (no space guard today → currently returns True, test expects False).

- [ ] **Step 3: Add the net-slot guard to `is_applicable`**

Append to `EquipAction.is_applicable` (after the existing checks, before the final `return state.level >= stats.level`):

```python
from artifactsmmo_cli.ai.inventory_room import has_room
```
(top-of-file import), and inside `is_applicable`:
```python
        displaced = state.equipment.get(self.slot)
        o_needs_slot = 1 if (displaced is not None
                             and displaced not in state.inventory) else 0
        c_frees_slot = 1 if state.inventory.get(self.code, 0) == self.quantity else 0
        new_stacks = max(0, o_needs_slot - c_frees_slot)
        if not has_room(new_stacks, added_qty=0,
                        slots_free=state.inventory_slots_free,
                        qty_free=state.inventory_free):
            return False
        return state.level >= stats.level
```
(Note `c_frees_slot` uses `== self.quantity`: equipping the whole held stack of `C` empties its slot. `added_qty=0` because quantity is conserved by the swap.)

- [ ] **Step 4: Run — green + coverage + mypy**

Run:
```
uv run pytest tests/test_ai/test_equip_action.py tests/test_ai/ -q --no-cov 2>&1 | tail -20
uv run pytest tests/test_ai/test_equip_action.py --cov=artifactsmmo_cli.ai.actions.equip --cov-report=term-missing -q 2>&1 | grep -i "equip\|TOTAL"
uv run mypy src/artifactsmmo_cli/ai/actions/equip.py
```
Expected: green; equip.py 100%; mypy Success. Reconcile any equip scenario test whose applicability legitimately changed.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/equip.py tests/test_ai/test_equip_action.py
git commit --no-verify -m "feat(inventory): gate EquipAction on net-slot room"
```

---

### Task 6: Gate `WithdrawItemAction` + `OptimizeLoadoutAction` on slot room

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/withdraw_item.py` (`is_applicable`)
- Modify: `src/artifactsmmo_cli/ai/actions/optimize_loadout.py` (`is_applicable`)
- Test: the existing withdraw + optimize_loadout test modules.

**Interfaces:**
- Consumes: `has_room` (Task 2), `WorldState.inventory_slots_free`.

- [ ] **Step 1: Write the failing withdraw test**

```python
def test_withdraw_new_code_blocked_when_no_free_slot(make_state):
    """Withdrawing a code NOT held into a full bag needs a slot -> blocked,
    even with quantity headroom."""
    state = make_state(
        inventory={f"j{n}": 1 for n in range(20)}, slots_max=20,
        bank_items={"iron_ore": 10})
    action = WithdrawItemAction(code="iron_ore", quantity=3, ...)  # existing ctor args
    assert action.is_applicable(state, game_data) is False


def test_withdraw_held_code_allowed_when_no_free_slot(make_state):
    """Withdrawing MORE of a held code grows its stack -> no slot needed."""
    inv = {"iron_ore": 2, **{f"j{n}": 1 for n in range(19)}}
    state = make_state(inventory=inv, slots_max=20, bank_items={"iron_ore": 10})
    action = WithdrawItemAction(code="iron_ore", quantity=3, ...)
    assert action.is_applicable(state, game_data) is True  # qty_free permitting
```

- [ ] **Step 2: Run — verify first fails** (current guard is quantity-only → returns True).

- [ ] **Step 3: Add slot term to `WithdrawItemAction.is_applicable`**

```python
from artifactsmmo_cli.ai.inventory_room import has_room
```
and replace the return:
```python
        if state.bank_items.get(self.code, 0) < self.quantity:
            return False
        new_stacks = 0 if self.code in state.inventory else 1
        return has_room(new_stacks, added_qty=self.quantity,
                        slots_free=state.inventory_slots_free,
                        qty_free=state.inventory_free)
```
(This subsumes the old `inventory_free >= quantity` check — `added_qty=self.quantity` against `qty_free` is exactly that, plus the slot term. Keep the `apply` assert consistent: update its assertion to also cover the slot case, or keep the quantity assert and rely on `is_applicable` for the slot gate — match the existing defense-in-depth comment; if you tighten `apply`, mirror the new_stacks condition.)

- [ ] **Step 4: Write the failing OptimizeLoadout test + implement**

`OptimizeLoadoutAction` performs one or more slot swaps; each displaced gear item returns to inventory. Compute total net new stacks across the swap set (sum of per-slot `max(0, O_needs_slot − C_frees_slot)` using the same arithmetic as Task 5, over the loadout's planned equips). Gate `is_applicable` on `has_room(total_new_stacks, added_qty=0, slots_free, qty_free)`. Read `optimize_loadout.py`'s `apply` (the swap plan) to get the exact per-swap displaced/equipped items, and mirror that set in `is_applicable`. Add a test: a full-bag optimize whose swaps displace new gear stacks is non-applicable; one whose displaced items are all already held (or covered by freed slots) is applicable.

```python
def test_optimize_loadout_blocked_when_swaps_need_slots_on_full_bag(make_state):
    ...  # build a full-bag state + a loadout whose swap displaces a new stack
    assert action.is_applicable(state, game_data) is False
```

- [ ] **Step 5: Run — green + coverage + mypy for both files**

Run:
```
uv run pytest tests/test_ai/ -q --no-cov 2>&1 | tail -20
uv run pytest tests/test_ai/ --cov=artifactsmmo_cli.ai.actions.withdraw_item --cov=artifactsmmo_cli.ai.actions.optimize_loadout --cov-report=term-missing -q 2>&1 | grep -iE "withdraw_item|optimize_loadout|TOTAL"
uv run mypy src/artifactsmmo_cli/ai/actions/withdraw_item.py src/artifactsmmo_cli/ai/actions/optimize_loadout.py
```
Expected: green; both modules 100%; mypy Success.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/withdraw_item.py src/artifactsmmo_cli/ai/actions/optimize_loadout.py tests/test_ai/
git commit --no-verify -m "feat(inventory): gate Withdraw + OptimizeLoadout on slot room"
```

---

### Task 7: Fire relief on slots-full

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/deposit_inventory.py` (trigger)
- Modify: `src/artifactsmmo_cli/ai/inventory_caps.py` (overstock watermark)
- Modify: `src/artifactsmmo_cli/ai/bank_selection.py` (last-resort gate)
- Test: the existing deposit/inventory-caps/bank-selection test modules.

**Interfaces:**
- Consumes: `WorldState.inventory_slots_free`.

The relief GOAL must activate when slots are full so `bank_selection`'s non-keep deposits (already correct) actually get banked, freeing slots.

- [ ] **Step 1: Write the failing deposit-trigger test**

```python
def test_deposit_goal_triggers_when_slots_full_though_quantity_low(make_state):
    """20/20 slots full but 74/124 quantity: the deposit goal must activate so
    junk gets banked and a slot frees (the slot-exhaustion livelock)."""
    inv = {f"j{n}": 1 for n in range(20)}  # 20 stacks, qty 20/124
    state = make_state(inventory=inv, slots_max=20, bank_items={})
    goal = DepositInventoryGoal(...)  # existing ctor
    assert goal.is_relevant(state, game_data) is True   # or the module's trigger predicate
```
(Match the module's actual trigger method name — `is_relevant`/`is_satisfied`/`_should_deposit`. Read `deposit_inventory.py:45`.)

- [ ] **Step 2: Run — verify it fails** (quantity watermark 74/124=0.60 below threshold → currently False).

- [ ] **Step 3: Add slot-full to the trigger**

In `deposit_inventory.py` (~line 45), OR the slot-full condition into the existing quantity watermark:
```python
        used_fraction = state.inventory_used / state.inventory_max
        slots_full = state.inventory_slots_free == 0
        should_deposit = used_fraction >= DEPOSIT_WATERMARK or slots_full
```
(Use the module's real constant/return shape. The intent: a full-slot bag triggers relief regardless of quantity fraction.)

- [ ] **Step 4: Slot-aware overstock watermark + last-resort gate**

- `inventory_caps.py`: where the overstock watermark is `inventory_used/inventory_max >= 17/20`, add a slot-full OR (`inventory_slots_free == 0`) so overstock disposal also engages when slots are the binding cap. Read the exact site (`inventory_caps.py:69,76,109`) and mirror its return shape.
- `bank_selection.py:~180`: change the last-resort gate from `state.inventory_free == 0` to `state.inventory_slots_free == 0` (the last-resort keep-item deposit must fire when SLOTS are exhausted, which is the real "cannot act" condition; quantity-free==0 is neither necessary nor the binding case). Keep the "deposits non-empty → return them first" path unchanged.

- [ ] **Step 5: Run — green + coverage + mypy**

Run:
```
uv run pytest tests/test_ai/ -q --no-cov 2>&1 | tail -20
uv run pytest tests/test_ai/ --cov=artifactsmmo_cli.ai.goals.deposit_inventory --cov=artifactsmmo_cli.ai.inventory_caps --cov=artifactsmmo_cli.ai.bank_selection --cov-report=term-missing -q 2>&1 | grep -iE "deposit_inventory|inventory_caps|bank_selection|TOTAL"
uv run mypy src/artifactsmmo_cli/ai/goals/deposit_inventory.py src/artifactsmmo_cli/ai/inventory_caps.py src/artifactsmmo_cli/ai/bank_selection.py
```
Expected: green; modules 100%; mypy Success. Verify no existing relief test regressed (quantity-watermark behavior must still hold — the change is additive OR).

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/deposit_inventory.py src/artifactsmmo_cli/ai/inventory_caps.py src/artifactsmmo_cli/ai/bank_selection.py tests/test_ai/
git commit --no-verify -m "feat(inventory): fire relief ladder on slots-full"
```

---

### Task 8: End-to-end livelock scenario + Lean applicability + runtime verification

**Files:**
- Modify: `formal/Formal/ActionApplicability.lean` (slot conjunct on the shared applicability gate, if any gated action is modeled there)
- Test: `tests/test_ai/scenarios/test_slot_exhaustion.py` (new scenario, offline planner)
- Runtime: live `plan Robby` / trace check.

- [ ] **Step 1: Write the failing end-to-end scenario**

Build a `scenario_state` mirroring the Robby livelock (20/20 slots full of mixed junk + a held equippable `adventurer_vest`, a pending body-armor upgrade, bank empty, ample quantity headroom). Drive the planner and assert the FIRST action is a RELIEF action (deposit/sell/recycle of a junk stack) — NOT the doomed `Equip(adventurer_vest)` that would 497:

```python
# tests/test_ai/scenarios/test_slot_exhaustion.py
def test_full_bag_routes_relief_before_doomed_equip() -> None:
    """20/20 slots, quantity headroom, pending body-armor upgrade: the planner
    must free a slot (deposit/sell junk) before the equip — not re-emit the
    497-doomed equip. Regression pin for the slot-exhaustion livelock."""
    state = ...  # scenario_state: full slots, adventurer_vest held, bank empty
    plan = plan_for(state, ...)  # the planner entry the scenario harness uses
    assert plan, "expected a non-empty plan"
    first = plan[0]
    assert not (isinstance(first, EquipAction)), repr(first)
    assert isinstance(first, (DepositAllAction, DepositItemAction,
                              NpcSellAction, RecycleAction)), repr(first)
```
(Use the scenario harness the repo already has — `tests/test_ai/scenarios/`. Mirror an existing scenario's `plan_for`/`scenario_state` usage.)

- [ ] **Step 2: Run — verify it fails** (pre-fix: planner emits the equip / a doomed action).

- [ ] **Step 3: Confirm the fix already makes it pass** (Tasks 4-7 supply the behavior)

Run: `uv run pytest tests/test_ai/scenarios/test_slot_exhaustion.py -v --no-cov`
Expected: PASS. If it does not pass, the gates/relief are not composing — debug (likely the relief action's own `is_applicable` or cost ordering); do NOT weaken the assertion.

- [ ] **Step 4: `ActionApplicability.lean` slot conjunct**

If a gated action's applicability is modeled in `ActionApplicability.lean` (the Fight gate is; equip/gather are modeled in their own Lean files), add a `hasSlotRoom` conjunct referencing `InventoryRoom.hasRoom` to keep the composite predicate honest, and prove the independence theorem (`slotsFree < newStacks → predicate false`) in the existing style (lines 108-115). `cd formal && lake build`; `uv run pytest formal/diff -q`. Use the `lean4` proof-repair agent if a proof does not close.

- [ ] **Step 5: RUNTIME VERIFICATION (mandatory)**

With NO gate/mutate/bot running, on live Robby (currently 20/20 full):
```bash
uv run artifactsmmo plan Robby 2>&1 | head -40
```
Confirm the plan's first action is a relief/deposit that frees a slot (NOT a 497-doomed equip/gather). If Robby has since drained, reproduce the full-bag condition from a trace segment or a scenario snapshot. Record the observed plan in the Task-8 report. This is the "green tests ≠ runtime-active" gate — the fix is not done until the live planner routes relief.

- [ ] **Step 6: Commit**

```bash
git add tests/test_ai/scenarios/test_slot_exhaustion.py formal/Formal/ActionApplicability.lean formal/diff/
git commit --no-verify -m "test(inventory): slot-exhaustion livelock scenario + Lean slot conjunct"
```

---

## Notes for the executor

- Task 0 is a HARD GATE: if the live probe DISPROVES `len(char.inventory)` = capacity, STOP and escalate — the entire model changes.
- The `inventory_slots_max` field is REQUIRED (no default) deliberately, to surface every construction site. Expect a wide first-diff across tests; `inventory_slots_max=len(inventory)` is the safe default for constructions that don't care about slots.
- Lean tasks (3, 4-step5, 8-step4) state the CONTRACT; exact tactic bodies may need the `lean4` proof-repair/sorry-filler agents. The obligation is: definitional mirror + independence theorems + differential lockstep + mutation anchors, matching the repo pattern. Run `uv run pytest formal/diff` explicitly on every core-arithmetic change (it is NOT in the default pytest path).
- Full gate (`gate.sh` + `mutate.py`) runs ONCE at the end, serialized (bot down). The per-task evidence is targeted pytest + module-100% + mypy + `formal/diff` + `lake build`.
- Runtime activation (Task 8 Step 5) is the real completion bar, not green tests.
- Out of scope (do NOT fix here): the cow `fight_lost` ×6 (separate issue); per-slot stack-size limits; changing WHICH junk stack relief frees (reuse `disposal_route`).
