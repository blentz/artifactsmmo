/-
Formal model of `owned_count` from
`src/artifactsmmo_cli/ai/tiers/owned_count.py` (`owned_count_pure`).

`owned_count` answers "how many of item `code` does the character own?" across
three stores:

    owned_count = inventory.get(code, 0)
                + (bank.get(code, 0) if bank present)
                + (1 if code equipped)

Used by `ObtainItem.is_satisfied = owned_count >= quantity`, the satisfaction
predicate for a "have N of item X" progression node.

We model the three stores as count functions `inv bank : String → Nat` and an
`equipped : String → Bool` predicate, and define `ownedCount` to mirror the
Python exactly (the bank-present guard is faithful: an absent bank contributes
its `0` count, identical to the Python `bank is None` short-circuit, since
`bank.get(code, 0) = 0` for an empty/absent bank).

WHY THE SUMMATION IS CORRECT (the true mechanism, NOT a disjointness invariant):
the ArtifactsMMO server stores equipped items in dedicated equipment SLOTS that
are SEPARATE from the `inventory` list. `CharacterSchema` exposes each `<slot>:
str` field independently of `inventory: list[InventorySlot]`, and
`WorldState.from_character_schema` builds `inventory` from `char.inventory` slots
while reading equipment from the slot fields separately (`world_state.py:146-155`).
`EquipAction.apply` DECREMENTS inventory by 1 when equipping (`equip.py:60`; a
displaced old item is returned to inventory at `equip.py:68`), and
`UnequipAction.apply` adds the item back to inventory. So `inventory.get(code)`
counts only the UNEQUIPPED (spare) copies — it NEVER includes the equipped copy.

Therefore `ownedCount = spares + bank + (1 if equipped) = the true total
physically owned`, UNCONDITIONALLY. There is NO disjointness-of-codes invariant:
a character CAN hold spare copies of an item it has equipped (e.g. 1 equipped
sword + 1 spare sword in inventory → count 2, which is CORRECT: two swords owned,
not a double-count). Here `inv` denotes that spare count, matching the server
semantics.

Lean core only — no mathlib. Nat arithmetic via `simp`/`omega`.
-/

namespace Formal.OwnedCount

/-- `owned_count_pure`: spare-inventory count + bank count + (1 if equipped). The
bank-present guard of the Python is faithful here: an absent bank is the zero
count, contributing `0` exactly as the Python short-circuit does. `inv` is the
count of UNEQUIPPED (spare) copies, since the server tracks the equipped copy in
a separate slot and `inventory` never includes it. -/
def ownedCount (inv bank : String → Nat) (equipped : String → Bool) (code : String) : Nat :=
  inv code + bank code + (if equipped code then 1 else 0)

/-! ### Intent theorems. -/

/-- The summation contract: `ownedCount` is EXACTLY the sum of the three stores,
UNCONDITIONALLY (no disjointness hypothesis). `inv` is the spare count, `bank` the
bank count, and the `+1` is the equipped copy held in a separate server slot.
This pins the exact summation `owned_count_pure` computes; any drift in the Python
breaks the differential gate. -/
theorem ownedCount_eq_total (inv bank : String → Nat) (equipped : String → Bool)
    (code : String) :
    ownedCount inv bank equipped code
      = inv code + bank code + (if equipped code then 1 else 0) := rfl

/-- THE load-bearing property: an item you own ONLY by wearing it (zero spares,
zero bank) still counts as owned. So `ObtainItem.is_satisfied` for an
already-equipped item is TRUE and the goal does not loop forever trying to
re-acquire an item the character already wears. -/
theorem ownedCount_counts_equipped (inv bank : String → Nat) (equipped : String → Bool)
    (code : String) (he : equipped code = true) :
    ownedCount inv bank equipped code ≥ 1 := by
  simp [ownedCount, he]

/-- Satisfaction soundness: owned count is non-decreasing in the spare-inventory
store. More owned never UN-satisfies a "have N" goal — gaining spares cannot drop
the count below a threshold it already met. (Monotonicity in `bank`/`equipped`
holds identically.) -/
theorem ownedCount_monotone (inv inv' bank : String → Nat) (equipped : String → Bool)
    (code : String) (h : inv code ≤ inv' code) :
    ownedCount inv bank equipped code ≤ ownedCount inv' bank equipped code := by
  simp only [ownedCount]
  omega

/-- Non-vacuity witness for `ownedCount_counts_equipped`: the spare-less equipped
case — a sword is equipped with ZERO spares in inventory and ZERO in bank, yet the
count is 1 (the equipped copy in its separate slot). -/
example :
    let inv : String → Nat := fun _ => 0
    let bank : String → Nat := fun _ => 0
    let equipped : String → Bool := fun c => decide (c = "sword")
    equipped "sword" = true ∧ ownedCount inv bank equipped "sword" = 1 := by
  refine ⟨by simp, ?_⟩
  simp [ownedCount]

end Formal.OwnedCount
