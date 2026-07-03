# Equip owned gear into empty slots — design

**Date:** 2026-07-03
**Status:** Design — awaiting user review
**Follows:** `2026-07-03-gather-artifact-utility-fill-design.md` (merged 5d81c1c8). That
change made `pick_loadout` propose owned artifacts correctly, but this spec
addresses why the proposal never reaches the character at runtime.

## Problem

Owned gear that would fill an **empty** equipment slot never gets equipped when
the character is on a normal plan (grind/gather/craft), because the loadout
re-arm is never cost-justified.

### Root cause (verified)

The planner sequences `OptimizeLoadoutAction` before a fight/gather only when the
total path cost is strictly lower than acting without it. The economics forbid
that for slot fills:

- `combat.py:30` `LOADOUT_PENALTY = 5.0`, added **once (flat)** to `FightAction.cost`
  when `pick_loadout(Combat)` differs from current equipment in any slot
  (`combat.py:119-125`).
- `gathering.py:27` `GATHER_LOADOUT_PENALTY = 5.0`, same flat pattern
  (`gathering.py:122-132`).
- `optimize_loadout.py:20` `SWAP_COST_PER_SLOT = 5.0`, and
  `OptimizeLoadoutAction.cost = SWAP_COST_PER_SLOT * 2 * n = 10·n`
  (2 API calls per slot).

For a single empty-slot fill (`n = 1`):

- Act without re-arm: `base + 5.0` (eats the flat penalty).
- Re-arm then act: `10.0 + base` (optimize cost, penalty removed).

Re-arming costs **10** to avoid a **5** penalty, so the A* search always prefers
eating the penalty. Confirmed empirically: `artifactsmmo plan Robby` yields
`GrindCharacterXP(red_slime)` → plan `[Fight(red_slime)]` with **no**
`OptimizeLoadout` step, while Robby holds `novice_guide` with three empty
artifact slots.

### Consequence for the merged gather fix

`2026-07-03-gather-artifact-utility-fill` relied on `GATHER_LOADOUT_PENALTY`
self-sequencing `OptimizeLoadout(Gather)`. The identical `5 < 10·n` economics
block it, so **the merged fix is currently inert at runtime** — `pick_loadout`
is correct and proven, but the planner never invokes the re-arm that would
realize it. This spec is what activates it.

## Goal

Equip any owned item with strictly-positive value into an **empty** equipment
slot, promptly and independently of the re-arm cost economics — covering combat,
gather, and pure-craft plans, and finally delivering the merged gather fix.

Non-goal: swapping a **filled** slot for a strictly-better owned item (a real
unequip+equip). That is combat-purpose re-arm and stays governed by the penalty
economics; changing it risks the over-optimization thrash the current cost was
tuned to avoid. See Out of scope.

## Design

### Component: `EquipOwnedGear` goal

A value-banded goal (the codebase expresses tiers as priority-value bands, e.g.
`CraftReliefGoal._GUARD_VALUE = 70.0` = survival floor; `sell_inventory`
`DISCRETIONARY_CEIL = 48.0`). One new file
`src/artifactsmmo_cli/ai/goals/equip_owned_gear.py`.

- **`is_satisfied(state)`** — satisfied unless at least one **empty** slot
  (`state.equipment[slot] is None`) has an owned item the ruler scores strictly
  positive. Computed from `pick_loadout(Rank)` restricted to empty slots:
  `fills = {slot: code for slot, code in pick_loadout(Rank, state, gd).items()
  if state.equipment.get(slot) is None and code is not None}`; satisfied iff
  `fills` is empty.
- **`value`** — `0.0` when satisfied; a fixed constant `EQUIP_GEAR_VALUE` when
  not. Placed **above the step/grind tier and below survival-critical guards**,
  so free gear equips before more grinding but never preempts survival/combat
  handling. Constant pinned in the spec's implementation plan; the exact number
  sits between the top step-goal value and the survival floor (70.0).
- **Plan / relevant actions** — emit the existing `EquipAction(item_code, slot)`
  for each `(slot, code)` in `fills`. No new action type. After execution the
  slots are filled, `is_satisfied` returns true next cycle, and the goal goes
  quiet — one-shot, self-satisfying.

### Ruler: `Rank`, restricted to empty slots

`Rank` (`gear_value_core.Rank`) is the purpose-independent ruler: `rank_value`
folds `combat_raw` (attack, crit, resistance, hp, lifesteal, combat_buff) **and**
utility (wisdom, prospecting, inventory_space, haste). So "strictly-positive
value" credits an always-on artifact (`novice_guide` → utility), a weapon (raw
attack), a pure-resistance armor (via `combat_raw`), and a crit/attack ring — the
full "any owned item worth wearing" set the scope requires. Restricting to
empty slots means the goal never displaces an incumbent, so the no-downgrade and
one-slot-per-code invariants are trivially satisfied and there is no swap cost or
oscillation risk.

Reuses the proven `pick_loadout` realizability / one-slot-per-code machinery
(`equipment/loadout_picker.py`) and the parametric per-slot Rank optimality
`Formal.GearValue.pickSlot_purpose_rank_optimal`.

### Scope guard: empty slots only; respect reservations

- Only slots where `state.equipment[slot] is None` are filled. Filled slots are
  left untouched.
- An item reserved by a committed craft (existing reservation mechanism) is not
  a candidate to equip away — gear items are not normally craft inputs, but the
  goal consults the same reservation view the crafting path uses so a reserved
  item is excluded from `fills`.

### Interplay with the penalty economics

The goal owns the equip decision as a first-class objective, so the
`LOADOUT_PENALTY (5) < OptimizeLoadout (10·n)` disincentive is irrelevant to it.
The `FightAction`/`GatherAction` penalties and `OptimizeLoadoutAction` are
unchanged; they continue to govern filled-slot combat re-arm (out of scope).
This design activates the merged gather-artifact fix, fixes the observed combat
`novice_guide` case, and covers pure-craft plans that run neither fight nor
gather.

## Formal lockstep

- **Structural proofs unaffected.** `pick_loadout`'s realizability /
  one-slot-per-code / no-downgrade / empty-fill-suppression are proven over an
  opaque `Int` scorer (`RealizableLoadout.lean`) — scorer-generic, no change.
- **Primary cost — close the deferred Rank differential binding.** This is the
  first live caller of `pick_loadout(Rank)`. The differential
  (`test_loadout_picker_diff.py`) explicitly defers the Rank binding because "no
  live caller picks with the Rank purpose" and because the oracle `Item` block
  aggregates utility into one `flatUtil` int, losing the breakdown
  `rankValue` needs. Closing it requires extending the oracle `Item` projection
  to carry the `rankValue` inputs (or binding `rankValue` at a level the current
  fields already support) and asserting live `gear_value(stats, Rank)` ≡ oracle
  `rankValue` bit-exact over a random empty-slot pool. Parametric Rank optimality
  (`pickSlot_purpose_rank_optimal`) already exists; this closes its production
  binding.
- **New goal decision logic** — `is_satisfied` / `value` / the empty-slot
  `fills` selection are decision logic: extract the pure core, differential-bind
  it, and add a mutation with an **owned unit test** (per the bag-slot lesson: a
  unit-killed mutant needs its own test group bound to a unit test). The goal's
  value band and the "empty-only" filter each get a mutant.
- **Non-vacuous.** Every liveness/optimality hypothesis must be satisfiable; the
  goal-fires hypothesis is witnessed by the concrete `novice_guide` + empty-slot
  state. Run `formal/gate.sh` serialized.

### Fallback if the Rank binding is intractable

If closing the Rank differential proves too heavy to land in one cycle, ship a
narrowed first cut that fills **artifact slots only** using the already-proven
`armor_score(stats, {})` flat-utility binding (from the merged gather fix) — this
alone rescues the inert merged fix and closes the `novice_guide` case, deferring
weapons / resistance-armor / jewelry to a follow-up Rank-binding cycle. This is a
documented escape hatch, not the primary plan.

## Testing (0 errors / 0 warnings / 0 skipped / 100% coverage)

1. Empty artifact slot + owned `novice_guide` → goal unsatisfied, value in band,
   plan equips it; next cycle satisfied. (Mutation killer for the empty-fill
   selection.)
2. Empty weapon slot + owned weapon (positive raw attack) → equipped.
3. Empty body slot + owned pure-resistance armor → equipped (Rank credits
   `combat_raw`); confirms Rank ≠ `armor_score({})` proxy.
4. All slots full → goal satisfied, value 0, never fires.
5. Filled slot + a strictly-better owned item → goal does NOT swap it (empty-only
   guard; mutation killer for the empty-only filter).
6. Owned item reserved by a committed craft → excluded from `fills`.
7. Goal value sits below the survival/combat guard band and above the step tier
   (arbiter ordering).

## Out of scope

- **Filled-slot combat re-arm** (swap a worse equipped item for a better owned
  one before a fight) — still gated by the `LOADOUT_PENALTY < OptimizeLoadout`
  economics. Fixing that is a separate penalty-economics change (make the flat
  penalty exceed the per-slot swap cost, or make it per-differing-slot) with its
  own thrash-analysis; not addressed here.

## Files touched

- Create: `src/artifactsmmo_cli/ai/goals/equip_owned_gear.py` (the goal).
- Modify: goal registry / arbiter enumeration (wherever goals are registered for
  `StrategyArbiter`) to include `EquipOwnedGear`.
- Modify: `formal/Oracle.lean` (+ `Formal/GearValue*`) — Rank differential binding.
- Modify: `formal/diff/test_loadout_picker_diff.py` — Rank empty-slot binding assertion.
- Modify: `formal/diff/mutate.py` — anchors + empty-fill / empty-only mutants.
- Create/modify: `formal/Formal/Extracted/…` + `Oracle.lean` for the goal's
  extracted decision core (value/selection), if the goal logic is placed in the
  proven subset.
- Tests: `tests/ai/…` goal test module (the 7 tests above).
