-- @concept: inventory, slot-room @property: safety, dominance, liveness
/-
Formal model of the full-bag clear's per-stack route, extracted from
`src/artifactsmmo_cli/ai/bag_clear_core.py` (`ClearRoute`, `clear_route`,
`slots_freed` — the count `ai/bag_clear.clear_actions` returns), Task 13e of
the global gear objective, plan B (USER 2026-10-25: "free up all in-use
inventory slots that aren't related to the current plan, then retry the plan
once the full inventory state is cleared").

A plan whose next stack-creating action finds no free slot (or whose last
action came back HTTP 497) clears the bag first. Each held stack is routed on
three executability-now facts assembled by the impure adapter
(`ai/bag_clear.py`):

    KEEP     iff  related                      (plan I/O, root closure, keep, equipped)
    DEPOSIT  iff  ¬related ∧ bankTakes         (non-destructive first)
    DISPOSE  iff  ¬related ∧ ¬bankTakes ∧ disposable
    KEEP     otherwise                         (nothing can move it this cycle)

and the clear frees one slot per stack that leaves (`freed`). A clear that frees
nothing is the named verdict `bag_full_all_related`, never a silent retry.

Lean core only — no mathlib. The route domain is finite (Bool³), so the route
theorems close by `decide`; the count theorems are by induction on the row list.

NON-VACUITY: every route is reachable (`route_*_witness`), the all-related
hypothesis is satisfiable with a non-empty bag (`all_related_witness`), and the
freeing hypothesis is satisfiable (`frees_witness`).
-/

namespace Formal.BagClear

/-- Where one held stack goes in the clear. Mirrors the Python `ClearRoute`. -/
inductive Route where | keep | deposit | dispose deriving Repr, DecidableEq

/-- Mirrors the Python `clear_route`. -/
def clearRoute (related bankTakes disposable : Bool) : Route :=
  if related then Route.keep
  else if bankTakes then Route.deposit
  else if disposable then Route.dispose
  else Route.keep

/-- One held stack's three facts: `(related, bankTakes, disposable)`. -/
abbrev Row := Bool × Bool × Bool

/-- Whether the stack leaves the bag (its route is not KEEP). -/
def leaves (r : Row) : Bool := clearRoute r.1 r.2.1 r.2.2 != Route.keep

/-- Slots the clear frees: one per stack that leaves. The adapter banks the
    DEPOSIT stacks in one DepositAll and gives each DISPOSE stack its own
    action, so it frees exactly this many. Mirrors `slots_freed`. -/
def freed : List Row → Nat
  | [] => 0
  | r :: rs => (if leaves r then 1 else 0) + freed rs

/-! ### SAFETY: a related stack is never shed. -/

/-- A RELATED stack (plan input/output, root-closure material, kept by the keep
authority, equipped) stays, whatever the bank or the disposal policy says. -/
theorem related_never_shed (bankTakes disposable : Bool) :
    clearRoute true bankTakes disposable = Route.keep := by
  cases bankTakes <;> cases disposable <;> decide

/-- DISPOSE fires only for an unrelated stack the bank refused. -/
theorem dispose_only_when_bank_refuses (related bankTakes disposable : Bool)
    (h : clearRoute related bankTakes disposable = Route.dispose) :
    related = false ∧ bankTakes = false ∧ disposable = true := by
  cases related <;> cases bankTakes <;> cases disposable <;> simp_all [clearRoute]

/-! ### DOMINANCE: non-destructive first. -/

/-- An unrelated stack the bank takes is DEPOSITED — never disposed of. -/
theorem deposit_before_dispose (disposable : Bool) :
    clearRoute false true disposable = Route.deposit := by
  cases disposable <;> decide

/-! ### LIVENESS: the clear frees exactly the stacks that leave. -/

/-- A bag where every stack is related frees NOTHING — the verdict
`bag_full_all_related` fires on exactly this shape. -/
theorem all_related_frees_none (rows : List Row)
    (h : ∀ r ∈ rows, r.1 = true) : freed rows = 0 := by
  induction rows with
  | nil => rfl
  | cons r rs ih =>
    have hr : r.1 = true := h r (List.mem_cons_self ..)
    have hrs : ∀ x ∈ rs, x.1 = true := fun x hx => h x (List.mem_cons_of_mem _ hx)
    obtain ⟨a, b, c⟩ := r
    simp only at hr
    subst hr
    simp [freed, leaves, clearRoute, ih hrs]

/-- One unrelated stack the bank takes is enough to free a slot: the clear
makes room whenever it has anything to bank. -/
theorem unrelated_bankable_frees (rows : List Row) (r : Row) (hr : r ∈ rows)
    (hu : r.1 = false) (hb : r.2.1 = true) : 0 < freed rows := by
  induction rows with
  | nil => cases hr
  | cons x xs ih =>
    cases hr with
    | head =>
      obtain ⟨a, b, c⟩ := r
      simp only at hu hb
      subst hu hb
      simp [freed, leaves, clearRoute]
      omega
    | tail _ hmem =>
      have := ih hmem
      simp [freed]
      omega

/-! ### Non-vacuous witnesses. -/

theorem route_keep_witness : clearRoute true true true = Route.keep := by decide
theorem route_deposit_witness : clearRoute false true false = Route.deposit := by decide
theorem route_dispose_witness : clearRoute false false true = Route.dispose := by decide
theorem route_stuck_witness : clearRoute false false false = Route.keep := by decide

/-- The all-related hypothesis holds on a non-empty bag (R2D2's porkchops). -/
theorem all_related_witness :
    freed [(true, true, true), (true, false, false)] = 0 := by decide

/-- The freeing hypothesis holds: two unrelated stacks, one banked and one
disposed of, beside a related one, free two slots. -/
theorem frees_witness :
    freed [(true, true, true), (false, true, false), (false, false, true)] = 2 := by decide

end Formal.BagClear
