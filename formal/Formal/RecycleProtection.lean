-- @concept: items, crafting @property: safety

/-!
# Formal.RecycleProtection

**What stops the planner dismantling the working copper_axe for parts.**

## The mechanism this module USED to prove is GONE

Commit e74c391 filtered `RecycleAction` construction against
`protected_codes = target_gear ∪ target_tools`, a `frozenset[str]`. The
item-protection-authority epic DELETED that filter (f80ca4e1); `actions/factory`
now emits a Recycle for every craftable equippable with NO code-set exclusion.
The frozenset was not merely redundant, it was the WRONG SHAPE: a code-SET can
only say "keep ALL copies", so `target_tools ∋ copper_axe` hid all 18 copies from
every recycle path (trace 2026-07-12) while leaving the heal stock and the active
task's own item wide open. Proving properties of it today would be a proof about
code that no longer exists — worse than useless, because it advertises "recycle
protection is formally verified" while the property that ACTUALLY runs has no
model. So this module was rewritten, not retired: same concept, same @property,
real mechanism. The old blanket now appears here only as a REFUTATION
(`blanket_would_hide_the_whole_hoard`).

## The mechanism that runs now — TWO independent gates

Protection on the recycle path is a QUANTITY (`ai/inventory_keep`), never a
code-set, and it is enforced twice over, on two different questions:

1. **HOW MANY copies may cease to exist** — the LICENCE.
   `destructive_license.licensed_recycle_quantity`:

       reachable = max(bankable(code), bank_copies(code))
       return min(reachable, destroyable(code))

   Recycle is unlike NpcSell/Delete because it is also an ACQUISITION route
   (`ai/recoverable_materials`): its source may legitimately be a BANK copy, so
   the bag short-circuit `licensed_quantity = min(bankable, destroyable)` is
   wrong here — it returns 0 for a bank-only hoard and makes `Withdraw → Recycle`
   UNPLANNABLE.

2. **WHICH copies the planner may REACH** — the FLOOR. A licensed
   `RecycleAction` is stamped with `bag_floor = keep_in_bag(code)`, and
   `RecycleAction.is_applicable` refuses when
   `inventory[code] - quantity < bag_floor`. The world model does not distinguish
   WHICH copy a recycle consumes — it just decrements the count — so without the
   floor a recycle licensed off a BANK copy could satisfy itself by eating the
   working tool sitting alone in the bag. The floor makes the protected bag
   copies unreachable, FORCING GOAP to stage a `Withdraw` first.

Neither gate implies the other (`licence_and_floor_are_independent`), and the
composition is what stops the bot melting the axe it is holding
(`working_axe_survives_but_the_hoard_is_reachable`).

`bankable` / `destroyable` / the keep quantities themselves are proved in
`Formal.InventoryKeep`; this module models the RECYCLE-path composition on top
of them. Lean core only — no mathlib.
-/

namespace Formal.RecycleProtection

/-! ## The keep-authority quantities (mirroring `ai/inventory_keep`).

`bag` = copies held in the bag, `bank` = copies held in the bank,
`keepBag` = `keep_in_bag(code)` (WORKING_KIT lives here: keep the ONE tool),
`keepOwned` = `keep_owned(code)` (EQUIPPED / GEAR_DEMAND / RECIPE_DEMAND /
ACTIVE_TASK / CURRENCY). Nat subtraction is truncated, exactly matching the
`max(0, ...)` clamp on the Python side. -/

/-- Bag copies the authority permits to LEAVE the bag. -/
def bankable (bag keepBag : Nat) : Nat := bag - keepBag

/-- Copies (bag + bank) the authority permits to CEASE TO EXIST. -/
def destroyable (bag bank keepOwned : Nat) : Nat := (bag + bank) - keepOwned

/-! ## Gate 1 — the LICENCE. -/

/-- `licensedRecycleQuantity` — `destructive_license.licensed_recycle_quantity`.
The BANK route is admitted as a recycle source; `destroyable` still bounds how
many copies may die. -/
def licensedRecycleQuantity (bag bank keepBag keepOwned : Nat) : Nat :=
  min (max (bankable bag keepBag) bank) (destroyable bag bank keepOwned)

/-- `licensedQuantity` — `destructive_license.licensed_quantity`, the BAG-ONLY
licence NpcSell/Delete get (modelled ONLY to state the divergence below; recycle
never uses it). -/
def licensedQuantity (bag bank keepBag keepOwned : Nat) : Nat :=
  if bag = 0 then 0 else min (bankable bag keepBag) (destroyable bag bank keepOwned)

/-! ## Gate 2 — the FLOOR (`RecycleAction.is_applicable`). -/

/-- `recycleApplicable bag qty floor` — the two inventory clauses of
`RecycleAction.is_applicable`: enough copies in the bag, AND the post-state bag
count still at or above `bag_floor = keep_in_bag(code)`. (The workshop / skill /
slot-room clauses are orthogonal and are NOT protection.) -/
def recycleApplicable (bag qty floor : Nat) : Bool :=
  decide (qty ≤ bag) && decide (floor ≤ bag - qty)

/-- The post-state bag count after `RecycleAction.apply` decrements. -/
def bagAfter (bag qty : Nat) : Nat := bag - qty

/-! ## SAFETY: the floor is never breached. -/

/-- `recycle_never_breaches_the_bag_floor`: if a recycle is applicable at all,
then the copies `keep_in_bag` protects SURVIVE it. This is the whole point of the
floor — stated on the POST-state, independently of how it is computed. -/
theorem recycle_never_breaches_the_bag_floor (bag qty floor : Nat)
    (h : recycleApplicable bag qty floor = true) :
    floor ≤ bagAfter bag qty ∧ qty ≤ bag := by
  unfold recycleApplicable at h
  simp only [Bool.and_eq_true, decide_eq_true_eq] at h
  exact ⟨h.2, h.1⟩

/-- `lone_working_tool_is_unreachable`: when the bag holds no more than the floor
protects, NO recycle of any positive quantity is applicable. The last copper_axe
in the bag can never be melted, whatever the licence says. -/
theorem lone_working_tool_is_unreachable (bag qty floor : Nat)
    (hq : 0 < qty) (hbag : bag ≤ floor) :
    recycleApplicable bag qty floor = false := by
  unfold recycleApplicable
  simp only [Bool.and_eq_false_iff, decide_eq_false_iff_not]
  omega

/-- `withdraw_unlocks_the_recycle`: the floor does not FORBID the recycle, it
RE-ROUTES it. Whenever the bag holds at least the floor, ONE `Withdraw` (bag `n`
→ `n+1`) makes a unit recycle applicable — so the planner is forced to spend a
bank copy instead of the working one, and the protected copies still survive
(`recycle_never_breaches_the_bag_floor` applies to the result). The liveness half
of the safety claim: without it, the floor would just be a stall. -/
theorem withdraw_unlocks_the_recycle (bag floor : Nat) (h : floor ≤ bag) :
    recycleApplicable (bag + 1) 1 floor = true := by
  unfold recycleApplicable
  simp only [Bool.and_eq_true, decide_eq_true_eq]
  omega

/-! ## SOUNDNESS of the LICENCE. -/

/-- `licence_bounded_by_destroyable`: the recycle licence NEVER permits more
copies to die than the keep authority allows — the bank route widens WHICH copies
are reachable, never HOW MANY may be destroyed. -/
theorem licence_bounded_by_destroyable (bag bank keepBag keepOwned : Nat) :
    licensedRecycleQuantity bag bank keepBag keepOwned ≤ destroyable bag bank keepOwned := by
  unfold licensedRecycleQuantity
  exact Nat.min_le_right _ _

/-- `fully_protected_code_is_never_recyclable`: when the keep authority protects
every owned copy (`destroyable = 0`), the licence is 0 — no RecycleAction for
that code survives `license_destructive_actions`, so no goal can reach for one. -/
theorem fully_protected_code_is_never_recyclable (bag bank keepBag keepOwned : Nat)
    (h : destroyable bag bank keepOwned = 0) :
    licensedRecycleQuantity bag bank keepBag keepOwned = 0 :=
  Nat.le_zero.mp (h ▸ licence_bounded_by_destroyable bag bank keepBag keepOwned)

/-- `licence_is_monotone_in_bank_copies`: banking MORE surplus never SHRINKS what
recycle may take. Pins the bank route as a genuine widening (a `max → min`
mutation on `reachable` loses this). -/
theorem licence_is_monotone_in_bank_copies (bag bank keepBag keepOwned : Nat) :
    licensedRecycleQuantity bag bank keepBag keepOwned
      ≤ licensedRecycleQuantity bag (bank + 1) keepBag keepOwned := by
  unfold licensedRecycleQuantity bankable destroyable
  omega

/-! ## The two gates are INDEPENDENT — both are load-bearing. -/

/-- `licence_and_floor_are_independent`: a code may be licensed for many copies
while EVERY bag copy is unreachable (so the licence alone would eat the working
tool), and a code may be bag-reachable while licensed for nothing (so the floor
alone would eat a protected hoard). Refutes "one gate suffices". -/
theorem licence_and_floor_are_independent :
    (0 < licensedRecycleQuantity 1 17 1 1 ∧ recycleApplicable 1 1 1 = false) ∧
    (licensedRecycleQuantity 5 0 5 5 = 0 ∧ recycleApplicable 5 1 0 = true) := by
  decide

/-! ## TRACE-MIRROR: the copper_axe hoard (2026-07-12).

18 copper_axe owned — 1 in the bag (the working tool), 17 in the bank.
`keep_in_bag = 1` (WORKING_KIT: keep the ONE tool), `keep_owned = 1`. -/

/-- `bag_licence_would_strand_the_bank_hoard`: the NpcSell/Delete licence
(`min(bankable, destroyable)`) returns 0 here — `bankable = 1 - 1 = 0`. If recycle
used it, the RecycleAction would be dropped from the pool and `Withdraw → Recycle`
would be UNPLANNABLE. This is exactly why `licensed_recycle_quantity` exists, and
it is a strictly different function (17 ≠ 0). -/
theorem bag_licence_would_strand_the_bank_hoard :
    licensedQuantity 1 17 1 1 = 0 ∧ licensedRecycleQuantity 1 17 1 1 = 17 := by
  decide

/-- `working_axe_survives_but_the_hoard_is_reachable`: the composed invariant.
The licence permits 17 copies to die; the bag copy is UNREACHABLE (floor 1 = bag
1); one Withdraw makes the recycle applicable, and it eats the withdrawn copy —
the working axe still stands. Safety AND liveness on the same state. -/
theorem working_axe_survives_but_the_hoard_is_reachable :
    licensedRecycleQuantity 1 17 1 1 = 17
    ∧ recycleApplicable 1 1 1 = false
    ∧ recycleApplicable 2 1 1 = true
    ∧ bagAfter 2 1 = 1 := by
  decide

/-- `blanket_would_hide_the_whole_hoard`: the REFUTATION of the retired
`target_tools` frozenset. A code-SET can only mean "keep ALL copies", so it makes
all 18 axes untouchable — while the quantity floor exposes 17 and protects
exactly 1. The blanket is sound ONLY when the keep quantity already covers every
held copy; here it does not (1 < 18). -/
theorem blanket_would_hide_the_whole_hoard :
    recycleApplicable 18 17 1 = true ∧ recycleApplicable 18 17 18 = false := by
  decide

end Formal.RecycleProtection
