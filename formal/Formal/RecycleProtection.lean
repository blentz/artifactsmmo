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

/-! ## Gate 3 — the OWNERSHIP FLOOR, and the COMPOSED invariant.

EVERYTHING ABOVE IS ABOUT ONE ACTION. `licence_bounded_by_destroyable` bounds the
quantity of a SINGLE `RecycleAction`, and every composed theorem above instantiates
`keepBag = keepOwned` — the one regime in which the single-action bound accidentally
composes. THE INVARIANT THE EPIC CLAIMS IS NOT ABOUT ONE ACTION: it is "`destroyable`
bounds HOW MANY copies may cease to exist", i.e. a bound on the TOTAL over a PLAN.

And the licence cannot enforce it. `license_destructive_actions` is a POOL-ADMISSION
filter: it asks ONCE, of a `quantity=1` action, whether `quantity ≤ licence`, and then
a plan may APPLY that one admitted action any number of times (in A*, in
`craft_plan_gen._recycle_prefix`, or by replaying a cached plan — `should_replan`
re-validates `step.is_applicable` and never re-derives the licence). The only
per-application guard the epic shipped was `bag_floor = keepBag`, and

    keepBag = 0 < 1 = keepOwned

for EVERY spare, unequipped, non-dominated equippable (ring, amulet, helmet, boots,
artifact, rune) — `IN_BAG_REASONS` carries no gear-keep reason at all. So with 2 spare
copper_rings and `destroyable = 1`, the licensed unit recycle was applicable TWICE and
BOTH rings died (`bag_floor_alone_over_destroys` — reproduced against production code).

`RecycleAction.owned_floor = keep_owned(code)` is the missing gate, and it is the ONE
quantity that survives composition: `owned = bag + bank` is INVARIANT under
Withdraw/Deposit and decreases by exactly `qty` under a recycle, so a floor on it binds
every application of every recycle in any sequence. That is
`total_destroyed_le_destroyable` below — the epic's actual safety claim, stated over a
RUN, and it is FALSE without gate 3. -/

/-- Bag + bank holdings of one code. -/
structure St where
  bag : Nat
  bank : Nat
deriving DecidableEq, Repr

/-- Copies OWNED — the dimension `destroyable` and `keep_owned` answer to. -/
def owned (s : St) : Nat := s.bag + s.bank

/-- The three plan steps that touch a code's holdings. Withdraw and Deposit are here
because they are exactly what a plan interleaves with recycles (`_recycle_prefix`
stages a bank copy before it melts one), and because they are what makes `bag` — and
so `bag_floor` — an unsound basis for a destruction bound: they MOVE copies, and a
bound that a mere move can restore bounds nothing. -/
inductive Step where
  | recycle (qty : Nat)
  | withdraw (n : Nat)
  | deposit (n : Nat)
deriving DecidableEq, Repr

/-- `RecycleAction.is_applicable`'s protection clauses, BOTH floors — the production
predicate: `qty ≤ inventory[code]`, `bag_floor ≤ inventory[code] - qty`, and
`owned_floor ≤ owned - qty` (written `floorOwned + qty ≤ owned` to match Python's
integer arithmetic exactly: `owned - quantity < owned_floor` refuses). -/
def recycleApplicableOwned (s : St) (qty floorBag floorOwned : Nat) : Bool :=
  decide (qty ≤ s.bag) && decide (floorBag ≤ s.bag - qty)
    && decide (floorOwned + qty ≤ owned s)

/-- Applicability of any step. Withdraw/Deposit carry no destruction gate — they are
reversible and retain ownership (`keep_in_bag` is what governs them). -/
def stepApplicable (s : St) (floorBag floorOwned : Nat) : Step → Bool
  | .recycle qty => recycleApplicableOwned s qty floorBag floorOwned
  | .withdraw n => decide (n ≤ s.bank)
  | .deposit n => decide (n ≤ s.bag)

/-- The world-model transition of each step (mirrors `apply` on each Action). -/
def stepApply (s : St) : Step → St
  | .recycle qty => ⟨s.bag - qty, s.bank⟩
  | .withdraw n => ⟨s.bag + n, s.bank - n⟩
  | .deposit n => ⟨s.bag - n, s.bank + n⟩

/-- Copies this step causes to CEASE TO EXIST. Only a recycle destroys. -/
def destroyedBy : Step → Nat
  | .recycle qty => qty
  | .withdraw _ => 0
  | .deposit _ => 0

/-- A PLAN is valid when every step is applicable IN SEQUENCE — exactly what GOAP
(and the plan cache's per-step `is_applicable` re-check) enforces. -/
def runValid (s : St) (floorBag floorOwned : Nat) : List Step → Bool
  | [] => true
  | st :: rest =>
      stepApplicable s floorBag floorOwned st
        && runValid (stepApply s st) floorBag floorOwned rest

/-- Total copies the plan destroys. -/
def totalDestroyed : List Step → Nat
  | [] => 0
  | st :: rest => destroyedBy st + totalDestroyed rest

/-- `owned_is_invariant_under_moves`: Withdraw and Deposit do not change what is
OWNED. This is why `owned_floor` composes and `bag_floor` cannot: a plan can restore
any bag count with a Withdraw, but it can never restore an owned count. -/
theorem owned_is_invariant_under_moves (s : St) (n : Nat) :
    (n ≤ s.bank → owned (stepApply s (.withdraw n)) = owned s)
    ∧ (n ≤ s.bag → owned (stepApply s (.deposit n)) = owned s) := by
  constructor <;> intro h <;> simp [owned, stepApply] <;> omega

/-- **`total_destroyed_le_destroyable`** — THE SAFETY INVARIANT THE EPIC CLAIMS, over a
RUN rather than a single action: for ANY sequence of steps each applicable in turn, the
TOTAL number of copies destroyed is at most `destroyable = owned - keep_owned`. No
bound on the pool's admission decision appears anywhere in it: the per-application
`floorOwned` gate is what carries it, and the theorem is FALSE if that gate is dropped
(`bag_floor_alone_over_destroys`). -/
theorem total_destroyed_le_destroyable (floorBag floorOwned : Nat) :
    ∀ (steps : List Step) (s : St),
      runValid s floorBag floorOwned steps = true →
        totalDestroyed steps ≤ destroyable s.bag s.bank floorOwned := by
  intro steps
  induction steps with
  | nil => intro s _; exact Nat.zero_le _
  | cons st rest ih =>
    intro s h
    simp only [runValid, Bool.and_eq_true] at h
    have hIH := ih (stepApply s st) h.2
    have happ := h.1
    cases st with
    | recycle qty =>
      simp only [stepApplicable, recycleApplicableOwned, owned, Bool.and_eq_true,
        decide_eq_true_eq] at happ
      simp only [stepApply, destroyable] at hIH
      simp only [totalDestroyed, destroyedBy, destroyable]
      omega
    | withdraw n =>
      simp only [stepApplicable, decide_eq_true_eq] at happ
      simp only [stepApply, destroyable] at hIH
      simp only [totalDestroyed, destroyedBy, destroyable]
      omega
    | deposit n =>
      simp only [stepApplicable, decide_eq_true_eq] at happ
      simp only [stepApply, destroyable] at hIH
      simp only [totalDestroyed, destroyedBy, destroyable]
      omega

/-- `bag_floor_alone_over_destroys`: THE BUG, as a theorem. Two spare copper_rings in
the bag, bank empty; `keep_in_bag = 0` (no gear-keep reason is in `IN_BAG_REASONS`) and
`keep_owned = 1`, so `destroyable = 1` — ONE ring may die. Under the bag floor ALONE
the unit recycle is applicable at 2 copies AND again at 1, so the run
`[recycle 1, recycle 1]` destroys 2 > 1. With the ownership floor the second recycle is
refused, and the run is not valid. The composed theorem above is exactly what this
refutes for the un-fixed predicate. -/
theorem bag_floor_alone_over_destroys :
    destroyable 2 0 1 = 1
    ∧ recycleApplicable 2 1 0 = true
    ∧ recycleApplicable 1 1 0 = true
    ∧ recycleApplicableOwned ⟨2, 0⟩ 1 0 1 = true
    ∧ recycleApplicableOwned ⟨1, 0⟩ 1 0 1 = false
    ∧ runValid ⟨2, 0⟩ 0 1 [.recycle 1, .recycle 1] = false
    ∧ runValid ⟨2, 0⟩ 0 1 [.recycle 1] = true := by
  decide

/-- `the_bank_route_still_composes`: the ownership floor does not re-break the bank
route the epic exists to open. 1 working axe in the bag (`keep_in_bag = 1`), 17 in the
bank, `keep_owned = 1`: `Withdraw → Recycle` is a VALID run that destroys a copy, while
recycling the bag copy outright is not applicable at all. Safety without stalling. -/
theorem the_bank_route_still_composes :
    runValid ⟨1, 17⟩ 1 1 [.withdraw 1, .recycle 1] = true
    ∧ totalDestroyed [Step.withdraw 1, Step.recycle 1] = 1
    ∧ runValid ⟨1, 17⟩ 1 1 [.recycle 1] = false := by
  decide

end Formal.RecycleProtection
