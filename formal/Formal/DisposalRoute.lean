-- @concept: inventory @property: dominance, safety, totality
/-
Formal model of the pure overstock disposal-route decision extracted from
`src/artifactsmmo_cli/ai/disposal_route.py` (`Route`, `disposal_route`).

When `DiscardOverstockGoal` cannot liquidate an overstocked item (no fillable
GE order, no executable NPC sell), the item is routed instead of blindly
deleted (live Robby trace 2026-07-04: copper_helmet×33, copper_ring×14,
wooden_shield×8 recyclable gear plus 40 bankable gems destroyed):

    RECYCLE  iff  recyclable                       (materials recovery first)
    DEPOSIT  iff  ¬recyclable ∧ bankOk ∧ futureValue
    DELETE   otherwise                             (true junk only)

Inputs are EXECUTABILITY-NOW facts assembled by the impure adapter:
`recyclable` = an applicable RecycleAction exists this cycle (workshop known,
skill met, minted materials fit the bag); `bankOk` = bank accessible AND has
room AND location known; `futureValue` = some recipe consumes the item OR it
is equippable. Executability-now preserves the 2026-06-24 liveness fix: every
route yields an action executable this cycle, so overstock always clears (no
Withdraw↔Deposit livelock regression).

The Python core mirrors this exactly:
`Route.RECYCLE if recyclable else Route.DEPOSIT if (bank_ok and future_value)
else Route.DELETE`; we model it over `Bool` — the domain is finite (Bool³) so
every theorem is closed by `decide` and the differential harness enumerates
ALL 8 inputs exhaustively (no sampling gap; lesson: xpPositiveGate band edges).

Lean core only — no mathlib.

NON-VACUITY: all three routes are reachable and exhibited below
(`route_branch_recycle`, `route_branch_deposit`, `route_branch_delete`); the
safety theorem's hypothesis (route = delete) is satisfiable by the same
witness.
-/

namespace Formal.DisposalRoute

/-- Disposal route for one overstocked item. Mirrors the Python `Route` enum. -/
inductive Route where | recycle | deposit | delete deriving Repr, DecidableEq

/-- Recycle when executable now; else deposit when the bank can take it AND the
item has future value; else delete. Mirrors the Python `disposal_route`. -/
def disposalRoute (recyclable bankOk futureValue : Bool) : Route :=
  if recyclable then Route.recycle
  else if bankOk && futureValue then Route.deposit
  else Route.delete

/-! ### PRIORITY. -/

/-- PRIORITY: an executable recycle ALWAYS wins — materials recovery beats
banking and deletion regardless of bank state or item value. -/
theorem recycle_first (bankOk futureValue : Bool) :
    disposalRoute true bankOk futureValue = Route.recycle := by
  cases bankOk <;> cases futureValue <;> decide

/-- PRIORITY: with no executable recycle, a bankable item with future value is
deposited — never deleted, never a stuck no-op. -/
theorem deposit_when_bankable :
    disposalRoute false true true = Route.deposit := by decide

/-! ### SAFETY (never destroy recoverable value). -/

/-- SAFETY: DELETE is chosen ONLY for true junk — no executable recycle AND
(bank unavailable OR no future value). The goal can never destroy an item it
could recycle or usefully bank. This is the theorem the copper_helmet×33
deletion violated. -/
theorem delete_only_when_worthless (recyclable bankOk futureValue : Bool)
    (h : disposalRoute recyclable bankOk futureValue = Route.delete) :
    recyclable = false ∧ (bankOk = false ∨ futureValue = false) := by
  cases recyclable <;> cases bankOk <;> cases futureValue <;> simp_all [disposalRoute]

/-- SAFETY (converse direction, exact firing condition): DELETE fires EXACTLY
on the worthless configurations — no over- or under-deleting. -/
theorem delete_iff_worthless (recyclable bankOk futureValue : Bool) :
    disposalRoute recyclable bankOk futureValue = Route.delete ↔
      recyclable = false ∧ (bankOk = false ∨ futureValue = false) := by
  cases recyclable <;> cases bankOk <;> cases futureValue <;> simp_all [disposalRoute]

/-! ### TOTALITY (liveness shape: some action is always chosen). -/

/-- TOTALITY: the route is always one of the three actions — no fourth outcome,
no stuck state, for ANY input configuration. Preserves the 2026-06-24
overstock-always-clears liveness fix. -/
theorem route_total (recyclable bankOk futureValue : Bool) :
    disposalRoute recyclable bankOk futureValue = Route.recycle
    ∨ disposalRoute recyclable bankOk futureValue = Route.deposit
    ∨ disposalRoute recyclable bankOk futureValue = Route.delete := by
  cases recyclable <;> cases bankOk <;> cases futureValue <;> decide

/-! ### NON-VACUITY witnesses (all three routes reachable). -/

/-- Reachable route 1: executable recycle ⇒ RECYCLE (even with the bank open —
recovery beats banking). -/
theorem route_branch_recycle : disposalRoute true true true = Route.recycle := by
  decide

/-- Reachable route 2: no recycle, bank open, item has future value ⇒ DEPOSIT. -/
theorem route_branch_deposit : disposalRoute false true true = Route.deposit := by
  decide

/-- Reachable route 3: no recycle, no future value ⇒ DELETE (true junk; the
sap-overstock case that must keep clearing the bag). -/
theorem route_branch_delete : disposalRoute false true false = Route.delete := by
  decide

/-- Concrete witness: bank closed + no recycle ⇒ DELETE even for a valuable
item (nothing else is executable — liveness over hoarding). -/
example : disposalRoute false false true = Route.delete := by decide

end Formal.DisposalRoute
