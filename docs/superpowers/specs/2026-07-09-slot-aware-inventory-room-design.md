# Slot-Aware Inventory Room — Design

Date: 2026-07-09
Status: approved (design); implementation via phased plan
Relates to: [[project_slot_exhaustion_livelock]], [[project_junk_inventory_livelock]], [[project_inventory_livelock_fix]]

## Problem

The AI player models inventory as a single QUANTITY budget (`inventory_max_items`)
but the game enforces TWO caps: a per-character SLOT count AND a total item
quantity. Confirmed live on character Robby (2026-07-09): 20/20 inventory slots
full, but only 75/124 total quantity. Every "inventory full" trigger and every
stack-creating action guard in the codebase counts quantity, so with ~50
quantity-free the model believes there is room while the server rejects any
action that needs a NEW slot with HTTP 497 "Character inventory is full".

Observed failure (Robby play-trace, 400 cycles): `Equip(adventurer_vest->body_
armor_slot)` ×10, `OptimizeLoadout(gather:woodcutting)` ×14, `Gather(sunflower_
field)` ×10 — all HTTP_497, retried identically, `recovery: null`. The equip
swap returns the old body-armor to inventory as a new distinct stack; with all
slots occupied there is no slot for it → 497. The existing inventory-relief
ladder (last-resort deposit at `inventory_free == 0`, `bank_selection.py:167`)
never fires because quantity-`free` is ~50, not 0. `is_applicable` passes
(item held, quantity room) so the planner re-derives the identical doomed
action every cycle → livelock. `EquipAction` has NO inventory-space guard at
all.

## Root cause (mapped)

- `world_state.py:72-73` `inventory: dict[str,int]` (code→qty); `inventory_max`
  = "max total item quantity (not unique stacks)".
- `world_state.py:182-189` `inventory_used = sum(values)`, `inventory_free =
  inventory_max - inventory_used` — quantity only.
- `world_state.py:216-219` `from_character_schema` iterates the API slot list
  but folds it into the qty dict; `len(char.inventory)` (slot capacity) is
  discarded. The `if slot.code and slot.quantity > 0` filter is evidence the
  API returns empty slots.
- Every relief trigger and space guard is quantity-based
  (`bank_selection.py:167`, `inventory_caps.py`, `deposit_inventory.py`,
  `gathering.py:77`, `withdraw_item.py:40`, `combat.py:62`); `equip.py` and
  `optimize_loadout.py` have no space guard at all.
- Lean `ActionApplicability.lean:66` `hasInventoryRoom(inventoryFree,
  minFreeSlots)` mirrors the quantity gate formally.
- `StuckDetector` REPEATED_ACTION_FAILURE (`recovery.py:104`, threshold 10)
  can suppress an action for a few cycles but never frees a slot, and goal/
  action churn resets its counter → no convergence.

## What "slot-aware" means here

Model BOTH caps and make the "has room" decision depend on whether an action
creates a NEW distinct stack or grows an existing one:

- A stack-CREATING action (gather a resource not yet held; equip-swap whose
  displaced item is not already in inventory; withdraw a new code) needs a free
  SLOT and quantity headroom.
- A stack-GROWING action (gather more of a held resource) needs only quantity
  headroom.

Both the 20-slot and 124-quantity caps stay honest. This is NOT "replace
quantity with slots" — quantity can still bind (20 stacks averaging > 6.2 each).

## Approach (selected: A — slot+quantity room, planner-gated)

Rejected alternatives:
- B (model + relief only, no action gating): the planner still emits doomed
  equips that fail at execute; livelock can recur if relief doesn't reliably
  precede. Weaker.
- C (slot-free replaces quantity-free): drops the real 124 quantity cap;
  regresses. Wrong.

## Components

### 1. Model — `world_state.py`

Add one stored field `inventory_slots_max: int`. Derive the rest:

- `inventory_slots_used` property = `len(self.inventory)` (dict keys = distinct
  stacks).
- `inventory_slots_free` property = `inventory_slots_max - inventory_slots_used`.

`from_character_schema` sets `inventory_slots_max = len(char.inventory)` (the
fixed slot list including empties). Because planner `apply` already adds/removes
dict keys (gather adds a code; `deposit_all.apply` pops codes; equip-swap
re-adds the displaced item), slot usage tracks correctly through planning with
no extra bookkeeping.

CAPACITY-SOURCE VERIFICATION (implementation Task 0, mandatory): confirm the
API returns empty slots so `len(char.inventory)` = capacity. Robby is 20/20
full so this cannot be distinguished from a full read alone. Task 0 = a
reversible live probe (deposit 1 unit of a junk singleton → re-query → confirm
a slot is present-but-empty and `len` unchanged → withdraw the item back to
restore state) plus a fixture with genuinely empty slots. Documented fallback
if the API omits empty slots: derive capacity from the max `slot` index
returned, or a game-constant floor; the fallback is chosen only if Task 0
disproves the len-based source.

### 2. Pure room core — new `ai/inventory_room.py`

One extracted, Lean-mirrored function (mechanical-extraction pattern — exact
integer arithmetic, no float on the decision path):

```
def has_room(new_stacks: int, added_qty: int,
             slots_free: int, qty_free: int) -> bool:
    return new_stacks <= slots_free and added_qty <= qty_free
```

A new-resource gather is `new_stacks=1, added_qty=yield`; growing a held stack
is `new_stacks=0`. This single seam makes both caps honest and is the unit the
Lean model mirrors.

### 3. Action gates

`equip.py`, `optimize_loadout.py`, `gathering.py`, `withdraw_item.py`
`is_applicable` compute their real stack delta and call `has_room`:

- Equip: the equipped item C leaves inventory (−1 qty) and the displaced slot
  item O returns to inventory (+1 qty), so `added_qty = 0` (quantity-neutral).
  The net NEW-SLOT requirement is `new_stacks = max(0, O_needs_slot −
  C_frees_slot)` where `O_needs_slot = 1 if O is not None and O not already a
  held stack else 0`, and `C_frees_slot = 1 if C's inventory quantity is
  exactly 1 (equipping empties C's stack) else 0`. So equipping when the
  displaced item is already held, or when the equipped item's stack empties to
  cover it, needs no new slot; only a genuinely new displaced stack with no
  freed slot requires `slots_free ≥ 1`.
- OptimizeLoadout: sum the per-swap displaced-item deltas.
- Gather: `new_stacks = 1` iff the gathered code is not already held; else 0.
- Withdraw: `new_stacks = 1` iff the withdrawn code is not already held.

A gated action becomes non-applicable when its new stack cannot fit, so the
planner routes a relief action first.

### 4. Relief trigger

The "full" deciders also fire on `inventory_slots_free == 0` (not only
quantity-`free == 0`): `bank_selection.py:167` last-resort deposit, the
`inventory_caps.py` overstock watermark, `deposit_inventory.py`. Relief frees a
WHOLE junk stack (depositing/selling/recycling the entire stack empties its
slot) via the existing `disposal_route` ordering (RECYCLE > DEPOSIT > DELETE)
and keep-set protection. No new disposal policy — only the trigger metric
changes.

### 5. Lean — `ActionApplicability.lean`

`hasInventoryRoom` gains a slot conjunct mirroring `has_room` (a `hasSlotRoom
(slotsFree, newStacks)` term ANDed into the existing applicability predicate),
keeping the proven applicability ladder green. Differential harness + mutation
anchors follow the existing pattern (see [[project_mechanical_extraction]],
[[project_o54_select_differential]]).

## Data flow

```
from_character_schema: inventory_slots_max = len(char.inventory)
  -> WorldState.inventory_slots_free = slots_max - len(inventory)

planner: action.is_applicable(state) calls has_room(new_stacks, added_qty,
         state.inventory_slots_free, state.inventory_free)
  new stack can't fit -> action not applicable
  -> planner inserts relief (deposit_all / npc_sell / recycle) which pops a
     junk stack -> len(inventory) drops -> slots_free rises -> gated action
     now applicable

relief goals fire when inventory_slots_free == 0 (junk stack -> bank/sell)
```

## Error handling

- Use only API data. `inventory_slots_max` comes from `len(char.inventory)`;
  if Task 0 disproves the len-based source, use the documented fallback — never
  a silent default.
- No new exception handling; never catch `Exception`.
- Multiple levels of error handling is a bug: the room check lives in ONE pure
  core consumed by all gates.

## Testing

- Unit: `has_room` truth table (new-stack blocked at slots_free 0 even with
  qty headroom; grow-stack allowed with slots_free 0; both caps). Model:
  `inventory_slots_used/free` over a fixture WITH empty slots.
- Action gates: each gated action rejects a new stack at slots_free 0 and
  accepts a grow-stack; equip-swap new-stack-vs-grow distinction.
- Relief: a slots-full-but-quantity-free scenario where relief deposits a junk
  stack and frees a slot; the gated action then plans.
- Livelock: a scenario mirroring the Robby trace (20/20 slots, equip pending)
  proving the planner routes relief instead of re-emitting the doomed equip —
  no identical-action repeat.
- Lean: `ActionApplicability` builds; slot conjunct proven; mutation anchors
  kill-checked.
- Runtime (mandatory, per [[feedback_verify_runtime_activation]]): on live
  Robby, `plan` / a trace segment shows the 497 loop broken — relief frees a
  slot and the equip/gather succeeds.
- Snapshot regen if the new `WorldState` field ripples to snapshot fixtures
  ([[reference_snapshot_regen]]).

## Scope / non-goals

- NOT changing the disposal policy (which stack to free) — reuse `disposal_
  route` + keep-set. Only the trigger metric becomes slot-aware.
- NOT modeling per-slot stack-size limits (server allows large stacks; the
  binding caps are slot-count and total quantity).
- The cow fight_lost ×6 in the same trace (gear.adequate=true) is a SEPARATE
  issue (likely a gather-loadout leaving Robby weak mid-swap) — out of scope.

## Risks

- Capacity-source: the whole model rests on `len(char.inventory)` = slot
  capacity. Mitigated by the mandatory Task-0 probe + fixture + documented
  fallback.
- Lean ripple: `ActionApplicability` is a proven module; the slot conjunct
  must keep the ladder green (differential + mutation). Follow the extraction
  pattern.
- WorldState field ripple: a new field can shift snapshot fixtures; regen per
  the snapshot-regen reference.
- Over-gating: if the stack-delta computation is wrong (e.g. treating a
  grow-stack as a new stack), the bot could over-relief. Mitigated by the
  new-stack-vs-grow unit tests per gate.
