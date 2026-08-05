-- @concept: inventory @property: dominance, safety, totality, liveness
/-
Formal model of the pure overstock disposal-route decision extracted from
`src/artifactsmmo_cli/ai/disposal_route.py` (`Route`, `disposal_route`), and of
the quantity-typed keep valuation that feeds its DEPOSIT gate
(`src/artifactsmmo_cli/ai/keep_valuation.py`).

When `DiscardOverstockGoal` cannot liquidate an overstocked item (no fillable
GE order, no executable NPC sell), the item is routed instead of blindly
deleted (live Robby trace 2026-07-04: copper_helmet×33, copper_ring×14,
wooden_shield×8 recyclable gear plus 40 bankable gems destroyed):

    RECYCLE  iff  recyclable                       (materials recovery first)
    DEPOSIT  iff  ¬recyclable ∧ bankOk ∧ bankUnderCap
    DELETE   otherwise                             (true junk only)

Inputs are EXECUTABILITY-NOW facts assembled by the impure adapter:
`recyclable` = an applicable RecycleAction exists this cycle (workshop known,
skill met, minted materials fit the bag); `bankOk` = bank accessible AND has
room AND location known; `bankUnderCap` = the bank holds FEWER copies than the
keep valuation wants kept. Executability-now preserves the 2026-06-24 liveness
fix: every route yields an action executable this cycle, so overstock always
clears (no Withdraw↔Deposit livelock regression).

The Python core mirrors this exactly:
`Route.RECYCLE if recyclable else Route.DEPOSIT if (bank_ok and bank_under_cap)
else Route.DELETE`; we model it over `Bool` — the domain is finite (Bool³) so
every theorem is closed by `decide` and the differential harness enumerates
ALL 8 inputs exhaustively (no sampling gap; lesson: xpPositiveGate band edges).

THE ANTI-LIVELOCK INVARIANT (2026-08-05). `bankUnderCap` replaced a boolean
`futureValue` ("some recipe consumes this item, or it is equippable"). That
boolean was true for nearly every gatherable, so `ai/disposal_route` deposited
the very piles `ai/bank_drain` was licensing for withdrawal — a withdraw↔deposit
cycle that the drain module's docstring explicitly (and falsely) denied. Both
sides now read ONE quantity, `bankSurplus keep bankQty`, and this file proves
what that buys:

    drained > 0  ⇒  route ≠ DEPOSIT           (`drained_is_never_deposited`)

and, in the state the withdrawal actually produces,

    the withdrawn copies can never be re-banked (`withdrawn_is_never_redeposited`)

which is the honest statement of "the bank holding monotonically decreases".

Lean core only — no mathlib.

NON-VACUITY: all three routes are reachable and exhibited below
(`route_branch_recycle`, `route_branch_deposit`, `route_branch_delete`); the
safety theorem's hypothesis (route = delete) is satisfiable by the same
witness. The two liveness theorems' hypothesis (`0 < drainLicensed …`) is
satisfiable too, and exhibited by `drain_fires_witness`; the complementary
DEPOSIT-eligible configuration is exhibited by `bank_under_cap_witness`.
-/

namespace Formal.DisposalRoute

/-- Disposal route for one overstocked item. Mirrors the Python `Route` enum. -/
inductive Route where | recycle | deposit | delete deriving Repr, DecidableEq

/-- Recycle when executable now; else deposit when the bank can take it AND is
still under this code's keep quantity; else delete. Mirrors the Python
`disposal_route`. -/
def disposalRoute (recyclable bankOk bankUnderCap : Bool) : Route :=
  if recyclable then Route.recycle
  else if bankOk && bankUnderCap then Route.deposit
  else Route.delete

/-! ### PRIORITY. -/

/-- PRIORITY: an executable recycle ALWAYS wins — materials recovery beats
banking and deletion regardless of bank state or item value. -/
theorem recycle_first (bankOk bankUnderCap : Bool) :
    disposalRoute true bankOk bankUnderCap = Route.recycle := by
  cases bankOk <;> cases bankUnderCap <;> decide

/-- PRIORITY: with no executable recycle, an item the bank is still under cap
for is deposited — never deleted, never a stuck no-op. -/
theorem deposit_when_bankable :
    disposalRoute false true true = Route.deposit := by decide

/-! ### SAFETY (never destroy recoverable value). -/

/-- SAFETY: DELETE is chosen ONLY for true junk — no executable recycle AND
(bank unavailable OR the bank already holds every copy worth keeping). The
goal can never destroy an item it
could recycle or usefully bank. This is the theorem the copper_helmet×33
deletion violated. -/
theorem delete_only_when_worthless (recyclable bankOk bankUnderCap : Bool)
    (h : disposalRoute recyclable bankOk bankUnderCap = Route.delete) :
    recyclable = false ∧ (bankOk = false ∨ bankUnderCap = false) := by
  cases recyclable <;> cases bankOk <;> cases bankUnderCap <;> simp_all [disposalRoute]

/-- SAFETY (converse direction, exact firing condition): DELETE fires EXACTLY
on the worthless configurations — no over- or under-deleting. -/
theorem delete_iff_worthless (recyclable bankOk bankUnderCap : Bool) :
    disposalRoute recyclable bankOk bankUnderCap = Route.delete ↔
      recyclable = false ∧ (bankOk = false ∨ bankUnderCap = false) := by
  cases recyclable <;> cases bankOk <;> cases bankUnderCap <;> simp_all [disposalRoute]

/-! ### TOTALITY (liveness shape: some action is always chosen). -/

/-- TOTALITY: the route is always one of the three actions — no fourth outcome,
no stuck state, for ANY input configuration. Preserves the 2026-06-24
overstock-always-clears liveness fix. -/
theorem route_total (recyclable bankOk bankUnderCap : Bool) :
    disposalRoute recyclable bankOk bankUnderCap = Route.recycle
    ∨ disposalRoute recyclable bankOk bankUnderCap = Route.deposit
    ∨ disposalRoute recyclable bankOk bankUnderCap = Route.delete := by
  cases recyclable <;> cases bankOk <;> cases bankUnderCap <;> decide

/-! ### NON-VACUITY witnesses (all three routes reachable). -/

/-- Reachable route 1: executable recycle ⇒ RECYCLE (even with the bank open —
recovery beats banking). -/
theorem route_branch_recycle : disposalRoute true true true = Route.recycle := by
  decide

/-- Reachable route 2: no recycle, bank open, bank under this code's cap ⇒
DEPOSIT. -/
theorem route_branch_deposit : disposalRoute false true true = Route.deposit := by
  decide

/-- Reachable route 3: no recycle, bank already at/over cap ⇒ DELETE (the
703-sap overstock case that must keep clearing the bag). -/
theorem route_branch_delete : disposalRoute false true false = Route.delete := by
  decide

/-- Concrete witness: bank closed + no recycle ⇒ DELETE even for a valuable
item (nothing else is executable — liveness over hoarding). -/
example : disposalRoute false false true = Route.delete := by decide

/-! ### THE ONE KEEP VALUATION (quantity layer feeding `bankUnderCap`).

Mirrors `src/artifactsmmo_cli/ai/keep_valuation.py`. `keep` is
`worth_keeping code` — the impure part (recipe demand, task chain, profile
gear keep, requirement-graph reachability) is assembled by the adapter and
arrives here as one integer, exactly as `recyclable`/`bankOk` do. -/

/-- Bank copies beyond the keep quantity. THE shared number: `> 0` is banked
junk the drain may withdraw, `< 0` means the bank is still under cap.
Mirrors `bank_surplus_pure`. -/
def bankSurplus (keep bankQty : Int) : Int := bankQty - keep

/-- How many BANK copies the drain may withdraw: the surplus, bounded by the
keep authority's ownership licence. Mirrors `drain_licensed_pure`. -/
def drainLicensed (destroyable keep bankQty : Int) : Int :=
  if bankSurplus keep bankQty < destroyable then bankSurplus keep bankQty
  else destroyable

/-- The route's DEPOSIT gate, reading the SAME `bankSurplus`. Mirrors
`bank_under_cap_pure`. -/
def bankUnderCap (keep bankQty : Int) : Bool := bankSurplus keep bankQty < 0

/-! ### LIVENESS (anti-livelock: the drain is monotone). -/

/-- LIVENESS (the invariant part 2 of the epic depends on): anything the drain
licenses withdrawing is NEVER routed back to the bank.

    drained(code) > 0  ⇒  route(code) ≠ DEPOSIT

This is what the boolean `futureValue` broke: `bank_drain_excess` licensed all
703 banked sap while `disposal_route` sent every withdrawn copy straight back,
burning a cooldown per cycle forever. Holds for ANY `recyclable`/`bankOk`, so
no adapter state can reintroduce the cycle. -/
theorem drained_is_never_deposited (recyclable bankOk : Bool)
    (destroyable keep bankQty : Int)
    (h : 0 < drainLicensed destroyable keep bankQty) :
    disposalRoute recyclable bankOk (bankUnderCap keep bankQty) ≠ Route.deposit := by
  have hs : 0 < bankSurplus keep bankQty := by
    unfold drainLicensed at h
    split at h <;> omega
  have hcap : bankUnderCap keep bankQty = false := by
    unfold bankUnderCap
    simp only [decide_eq_false_iff_not, Int.not_lt]
    omega
  rw [hcap]
  cases recyclable <;> cases bankOk <;> simp [disposalRoute]

/-- LIVENESS (the honest monotonicity statement): in the state the withdrawal
ACTUALLY produces — `bankQty` reduced by the withdrawn `n` — the route still
refuses DEPOSIT, for EVERY `n` the drain licenses (`DrainBankJunkGoal` emits a
resized withdraw, so the quantity is not always the full licence).
`drained_is_never_deposited` speaks about the pre-withdraw state; this one
closes the loop, because the post-withdraw state is what the `DiscardOverstock`
guard routes from on the NEXT cycle. Together they are what makes
`ai/bank_drain`'s "the bank holding monotonically decreases — no
withdraw/redeposit cycle" a true claim rather than an assertion.

No positivity hypothesis is needed and none is asserted: the bound `n ≤
drainLicensed` alone forces the post-withdraw bank to sit at or above the keep
quantity. Stating it with a `0 < n` it does not use would be a false story
about what the proof needs. -/
theorem withdrawn_is_never_redeposited (recyclable bankOk : Bool)
    (destroyable keep bankQty n : Int)
    (hlic : n ≤ drainLicensed destroyable keep bankQty) :
    disposalRoute recyclable bankOk (bankUnderCap keep (bankQty - n))
      ≠ Route.deposit := by
  have hn : drainLicensed destroyable keep bankQty ≤ bankSurplus keep bankQty := by
    unfold drainLicensed; split <;> omega
  have hcap : bankUnderCap keep (bankQty - n) = false := by
    unfold bankUnderCap bankSurplus
    simp only [decide_eq_false_iff_not, Int.not_lt]
    unfold bankSurplus at hn
    omega
  rw [hcap]
  cases recyclable <;> cases bankOk <;> simp [disposalRoute]

/-! ### NON-VACUITY of the liveness hypothesis + its complement. -/

/-- The liveness hypothesis is SATISFIABLE: 704 banked sap against a keep of 1,
with the ownership authority licensing all of it, drains 703 — the live figure
this epic came from. -/
theorem drain_fires_witness : drainLicensed 704 1 704 = 703 := by decide

/-- …and the complementary configuration is reachable too: 130 banked iron_ore
against a keep of 400 (a reachable consumer's full demand) drains NOTHING and
IS deposit-eligible, so the invariant is not held by making DEPOSIT dead. -/
theorem bank_under_cap_witness :
    drainLicensed 130 400 130 = -270 ∧ bankUnderCap 400 130 = true := by decide

end Formal.DisposalRoute
