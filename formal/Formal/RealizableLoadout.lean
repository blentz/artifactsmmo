-- @concept: items, characters @property: safety
/-
Formal model of the realizable-loadout invariant from
`src/artifactsmmo_cli/ai/equipment/realizable_loadout.py`, the post-condition
`pick_loadout` (with the one-slot-per-code projected-result rule) satisfies.

# THE BUG (verified counterexample, pre-fix Python)
`pick_loadout` picked each slot INDEPENDENTLY, so multi-slot item types
(`ring → [ring1_slot, ring2_slot]`, `artifact → [3 slots]`, `utility → [2 slots]`)
could select the SAME physical item code for multiple slots. Concretely:

    state: equipment = {ring1_slot: 'A' resistance.fire=5,
                        ring2_slot: 'B' resistance.fire=50}
    inventory = {}
    monster: attack.fire = 100
    pick_loadout(...) returned {ring1_slot: 'B', ring2_slot: 'B'}
    -- but only ONE physical 'B' exists.

`OptimizeLoadoutAction.apply` then silently popped the missing inventory key
(`pop(code, None)`), corrupting downstream planner state.

# THE SECOND BUG (2026-06-10/11 trace, the 485 livelock)
The first fix used a CLAIMED-CODES accumulator keyed on OWNERSHIP COUNT, so
owning a second physical copy legalized a duplicate sibling-slot assignment:
copper_ring worn in ring1_slot + a spare copper_ring in inventory made
`{ring2_slot: copper_ring}` "feasible". The SERVER enforces ONE SLOT PER ITEM
CODE — equipping a code already worn in any slot is refused with HTTP 485
("This item is already equipped") regardless of copies owned. The equip
failed, state never changed, and the identical loadout re-derived every
cycle: every GrindCharacterXP cycle died in OptimizeLoadout.

# THE FIX (current algorithm)
1. `pick_loadout` filters candidates per slot against the PROJECTED RESULT:
   a code C is INFEASIBLE for slot S when the result already places C at any
   OTHER slot — kept there (a later slot's current item) or newly assigned
   (an earlier slot's pick). This subsumes the old ownership-count claim
   accumulator: a code can appear at most once in the result, so demand per
   code never exceeds 1 for fresh assignments and the worn count for keeps.
2. An EMPTY slot is only filled when the best feasible candidate's score is
   STRICTLY POSITIVE — a zero-score equip buys nothing against the target
   monster and burns the code's single legal slot.
3. `OptimizeLoadoutAction.apply` asserts `cur ≥ 1` on every inventory
   decrement AND that the incoming code is not worn in any other slot of the
   projected equipment (the one-slot-per-code mirror).

# THE INVARIANT (this file)
A loadout `L : slot → Option code` is REALIZABLE wrt inventory `I` and
current equipment `E` iff
    ∀ code C, demand(C, L) ≤ ownership(C, I, E)
where
    demand(C, L) = |slots whose loadout value = some C|
    ownership(C, I, E) = I(C) + |slots whose equipment value = some C|

We prove:
  * `apply_cur_ge_1`: under `isRealizable`, the post-step inventory decrement
    in the two-pass `apply` always has `cur ≥ 1` (the assertion holds).
  * `ownership_counts_equipped`: every slot currently holding C contributes
    exactly 1 to ownership (the +1 per equipped occurrence).
  * `pickLoadout_realizable`: the modeled algorithm's output is realizable.
  * `pickLoadout_one_slot_per_code`: duplicate-free current equipment (the
    server guarantees this) yields a duplicate-free output — every code is
    worn in at most ONE slot, so the two-pass execute can never 485.
  * `pickLoadout_485_copper_ring_regression`: the literal trace bug case
    (worn copper_ring + spare copy) leaves ring2 EMPTY.

Lean core only — no mathlib. `Nat` arithmetic via `omega`/`simp`; lists via
fold/induction.
-/

namespace Formal.RealizableLoadout

/-- A "code" is just a string (item code). -/
abbrev Code := String

/-- A `Slot` value is `none` (empty) or `some code`. -/
abbrev SlotVal := Option Code

/-- A loadout / equipment map is a finite list of (slot-name, value) pairs.
We don't need slot names by identity here — only the SEQUENCE of slot values
matters for counting demand. So we model both as `List SlotVal` (the values
across all slots), which is faithful to the Python dict's value-multiset use. -/
abbrev SlotList := List SlotVal

/-- An inventory is a finite map `code → Nat`. We model it as a function. -/
abbrev Inventory := Code → Nat

/-- Count of slots currently holding `code` in a slot list. -/
def slotCount (code : Code) (sl : SlotList) : Nat :=
  sl.foldr (fun v acc => acc + (if v = some code then 1 else 0)) 0

/-- `ownership(C, I, E) = I(C) + |slots in E holding C|`. Faithful to the
Python `ownership` helper. -/
def ownership (code : Code) (inv : Inventory) (equip : SlotList) : Nat :=
  inv code + slotCount code equip

/-- `demand(C, L) = |slots in L whose value = some C|`. Same shape as
`slotCount`, but read as "how many slots in the LOADOUT want this code". -/
def demand (code : Code) (loadout : SlotList) : Nat := slotCount code loadout

/-- A loadout is realizable wrt `(inv, equip)` iff for every code, demand
in the loadout does not exceed ownership. -/
def isRealizable (loadout : SlotList) (inv : Inventory) (equip : SlotList) : Prop :=
  ∀ c, demand c loadout ≤ ownership c inv equip

/-! ### Basic count lemmas. -/

theorem slotCount_nil (c : Code) : slotCount c [] = 0 := rfl

theorem slotCount_cons_some_eq (c : Code) (rest : SlotList) :
    slotCount c (some c :: rest) = slotCount c rest + 1 := by
  unfold slotCount
  simp

theorem slotCount_cons_some_ne (c d : Code) (h : c ≠ d) (rest : SlotList) :
    slotCount c (some d :: rest) = slotCount c rest := by
  unfold slotCount
  simp [h.symm]

theorem slotCount_cons_none (c : Code) (rest : SlotList) :
    slotCount c (none :: rest) = slotCount c rest := by
  unfold slotCount
  simp

/-- Adding a slot with value `some c` increments `slotCount c` by exactly 1. -/
theorem slotCount_cons_some (c d : Code) (rest : SlotList) :
    slotCount c (some d :: rest) =
      slotCount c rest + (if c = d then 1 else 0) := by
  by_cases h : c = d
  · subst h
    simpa using slotCount_cons_some_eq c rest
  · simp [slotCount_cons_some_ne c d h rest, h]

/-- Uniform cons lemma over an arbitrary head value. -/
theorem slotCount_cons (c : Code) (v : SlotVal) (rest : SlotList) :
    slotCount c (v :: rest) = slotCount c rest + (if v = some c then 1 else 0) := by
  cases v with
  | none =>
    have : (none : SlotVal) ≠ some c := by intro h; cases h
    simp [slotCount_cons_none, this]
  | some d =>
    rw [slotCount_cons_some]
    by_cases h : c = d
    · subst h; simp
    · have hne : (some d : SlotVal) ≠ some c := by
        intro hh; injection hh with hh; exact h hh.symm
      simp [h, hne]

/-- `slotCount` distributes over append. -/
theorem slotCount_append (c : Code) (xs ys : SlotList) :
    slotCount c (xs ++ ys) = slotCount c xs + slotCount c ys := by
  induction xs with
  | nil => rw [List.nil_append, slotCount_nil]; omega
  | cons v rest ih =>
    rw [List.cons_append, slotCount_cons, ih, slotCount_cons]
    omega

/-- A code absent from a slot list counts 0. -/
theorem slotCount_eq_zero_of_not_mem (c : Code) (l : SlotList)
    (h : some c ∉ l) : slotCount c l = 0 := by
  induction l with
  | nil => rfl
  | cons v rest ih =>
    have hv : ¬ (v = some c) := fun he => h (by rw [he]; exact List.mem_cons_self)
    have hrest : some c ∉ rest := fun hm => h (List.mem_cons_of_mem _ hm)
    rw [slotCount_cons, ih hrest]
    simp [hv]

/-! ### Demand bound: the realizability invariant unpacked. -/

/-- Headline: `isRealizable` is exactly the per-code `demand ≤ ownership`
bound. This is what the one-slot-per-code projected-result rule enforces:
a freshly-assigned code appears EXACTLY ONCE in the result (and is owned),
while kept codes are bounded by the worn count — so the total number of
slots holding any code never exceeds ownership. -/
theorem isRealizable_iff_demand_le_ownership
    (loadout : SlotList) (inv : Inventory) (equip : SlotList) :
    isRealizable loadout inv equip ↔
      ∀ c, demand c loadout ≤ ownership c inv equip := by
  rfl

/-! ### Apply-step safety: `cur ≥ 1` follows from `isRealizable`. -/

/-- The post-step inventory after the two-pass apply restores every old
equipment value to inventory before any equip consumes. For a single code C,
the available count at the moment a new slot equips C is

    (inv C) + (number of slots currently holding C) - (number of slots
    already equipped to C in this run)
  = ownership(C, inv, equip) - (loadout slots equipped so far to C)

So the per-step `cur ≥ 1` assertion is equivalent to

    ownership(C, inv, equip) > (loadout slots already equipped to C)

which strictly precedes `≥ 1`. Since the loadout's total demand for C is
≤ ownership(C, inv, equip), this strictly holds at every step.

Concretely: if the running "already equipped" count is `k < demand`, then
`k + 1 ≤ demand ≤ ownership`, so `ownership - k ≥ 1` — the assertion holds. -/
theorem apply_cur_ge_1
    (c : Code) (inv : Inventory) (equip : SlotList) (loadout : SlotList)
    (already : Nat)
    (real : isRealizable loadout inv equip)
    (h_progress : already < demand c loadout) :
    1 ≤ ownership c inv equip - already := by
  have h1 : already + 1 ≤ demand c loadout := h_progress
  have h2 : demand c loadout ≤ ownership c inv equip := real c
  have h3 : already + 1 ≤ ownership c inv equip := Nat.le_trans h1 h2
  omega

/-! ### Currently-equipped contributes exactly 1 to ownership (the +1). -/

/-- `ownership_counts_equipped`: a slot currently holding `c` contributes
exactly +1 to ownership(c). This pins the Python ownership helper's per-slot
+1 accounting (so the apply two-pass unequip-then-equip restores the right
count before any equip consumes). -/
theorem ownership_counts_equipped
    (c : Code) (inv : Inventory) (equip : SlotList)
    (h : some c ∈ equip) :
    1 ≤ ownership c inv equip := by
  have : 1 ≤ slotCount c equip := by
    induction equip with
    | nil => cases h
    | cons v rest ih =>
      cases h_mem : v with
      | none =>
        rw [h_mem] at h
        simp at h
        have h' : some c ∈ rest := h
        have := ih h'
        simp [slotCount_cons_none c rest]
        exact this
      | some d =>
        rw [h_mem] at h
        by_cases hcd : c = d
        · subst hcd
          simp [slotCount_cons_some_eq c rest]
        · have h_in_rest : some c ∈ rest := by
            cases h with
            | head => exact absurd rfl hcd
            | tail _ h' => exact h'
          have := ih h_in_rest
          have h_ne : c ≠ d := hcd
          simp [slotCount_cons_some_ne c d h_ne rest]
          exact this
  unfold ownership
  omega

/-! ### Non-vacuity: the original ring-pair bug's REALIZABLE output. -/

/-- A loadout wearing the two distinct owned rings (one each) is realizable. -/
theorem regression_ring_pair_realizable :
    isRealizable (loadout := [some "A", some "B"])
      (inv := fun _ => 0)
      (equip := [some "A", some "B"]) := by
  intro c
  unfold demand ownership slotCount
  simp only [List.foldr]
  by_cases hA : c = "A"
  · subst hA; simp
  · by_cases hB : c = "B"
    · subst hB; simp
    · have hAne : (some "A" : SlotVal) ≠ some c := by
        intro h; apply hA; injection h with h; exact h.symm
      have hBne : (some "B" : SlotVal) ≠ some c := by
        intro h; apply hB; injection h with h; exact h.symm
      simp [hAne, hBne]

/-- Anti-non-vacuity: the PRE-fix output (both slots = B) is NOT realizable
under the same state. This pins what the fix prevents. -/
theorem regression_buggy_output_not_realizable :
    ¬ isRealizable (loadout := [some "B", some "B"])
        (inv := fun _ => 0)
        (equip := [some "A", some "B"]) := by
  intro h
  have hb := h "B"
  unfold demand ownership slotCount at hb
  simp at hb

/-! ### Empty-loadout edge: vacuously realizable. -/

theorem empty_loadout_realizable (inv : Inventory) (equip : SlotList) :
    isRealizable [] inv equip := by
  intro c
  unfold demand slotCount
  simp

/-! ### Monotonicity: more inventory never makes a realizable loadout fail. -/

theorem isRealizable_mono_inv
    (loadout : SlotList) (inv inv' : Inventory) (equip : SlotList)
    (h_le : ∀ c, inv c ≤ inv' c)
    (h_real : isRealizable loadout inv equip) :
    isRealizable loadout inv' equip := by
  intro c
  have hr := h_real c
  unfold ownership at hr ⊢
  have hc := h_le c
  omega

/-! ## Phase-15 (revised 2026-06-11): the full `pick_loadout` algorithm.

`scoring.py::pick_loadout` iterates slots in a deterministic order over a
projected `result` dict that STARTS as a copy of `state.equipment`. For each
slot it filters candidates by the server's ONE-SLOT-PER-CODE rule — a code is
INFEASIBLE when the projected result already places it at any OTHER slot
(an earlier slot's final pick, or a later slot's still-current item) — takes
the per-slot score argmax, and applies the no-downgrade rule against the
current item. EMPTY slots are filled only by a strictly-positive score.

The old claimed-codes accumulator is GONE: ownership-count feasibility let a
second owned copy legalize a duplicate sibling-slot assignment, which the
server refuses with HTTP 485 (the 2026-06-10/11 OptimizeLoadout livelock).
The projected-result rule subsumes it.

MODEL. A fold over slot-records threading the list of already-assigned values
(`assigned`); the unprocessed slots contribute their CURRENT values
(`laterCurs`), exactly mirroring the in-place `result` dict. Scores are
opaque per-slot `Int` functions (the algorithm only COMPARES scores). The
Python "current item has no stats" edge (`current_stats is None` with a
non-None code) is abstracted as `current = none` apart from the retained
code, matching the prior model's abstraction; the differential test skips
score assertions there.

We prove:
* `pickLoadout_realizable` — the output is realizable against `(inv, equip)`,
  given the slot-records' currents are consistent with the equipment (Python
  initializes both from `state.equipment`).
* `pickLoadout_one_slot_per_code` — duplicate-free currents (the server
  guarantees worn equipment never repeats a code) give a duplicate-free
  output: no code occupies two slots, so no equip in the two-pass execute
  can hit HTTP 485.
* `pickSlotStep_no_downgrade` — every swap of a filled slot is a STRICT score
  improvement (the old "stolen current" downgrade branch no longer exists).
* `pickSlotStep_optimal` — an assigned value is the argmax over the feasible
  candidate set.
* `pickSlotStep_empty_fill_positive` / `pickSlotStep_empty_zero_stays_empty`
  — the zero-score empty-fill suppression, both directions.
* `pickLoadout_deterministic` / `pickLoadout_extensional` — purity.
* `pickLoadout_485_copper_ring_regression` — the literal trace bug case. -/

/-- A slot's input to the algorithm: its current equipment value and the list
of type-and-level-feasible candidate codes (from `_candidates_for_slot`). -/
structure SlotRecord where
  current : SlotVal
  candidates : List Code
deriving Inhabited

/-- A code is FORBIDDEN for the slot under consideration iff the projected
result already holds it at another slot: among the earlier slots' assigned
values or among the later slots' current values. Mirrors the Python
`_in_result_elsewhere` scan of the `result` dict (the slot's OWN current is
excluded — it is at this slot, not another). -/
def forbiddenIn (code : Code) (assigned laterCurs : List SlotVal) : Bool :=
  (assigned ++ laterCurs).any (fun v => decide (v = some code))

/-- The feasible candidates for a slot: owned (`1 ≤ ownership` — Python's
`_candidates_for_slot` only emits items from the owned pool; the model's
candidates are arbitrary so the conjunct is explicit) and not forbidden by
the one-slot-per-code rule. -/
def feasibleCands (rec : SlotRecord) (inv : Inventory) (equip : SlotList)
    (assigned laterCurs : List SlotVal) : List Code :=
  rec.candidates.filter (fun c =>
    decide (1 ≤ ownership c inv equip) && !(forbiddenIn c assigned laterCurs))

/-- Argmax of a nonempty list under integer score, left-fold; ties keep the
EARLIER element (Python `max(.., key=..)` semantics). -/
def argmaxByCode (score : Code → Int) : Code → List Code → Code
  | best, [] => best
  | best, x :: xs =>
      if score x > score best then argmaxByCode score x xs else argmaxByCode score best xs

/-- Argmax is a member of `best :: xs`. -/
theorem argmaxByCode_mem (score : Code → Int) (best : Code) (xs : List Code) :
    argmaxByCode score best xs ∈ best :: xs := by
  induction xs generalizing best with
  | nil => simp [argmaxByCode]
  | cons x xs ih =>
    unfold argmaxByCode
    by_cases h : score x > score best
    · simp only [h, if_true]
      have := ih x
      rcases List.mem_cons.mp this with he | hm
      · exact List.mem_cons.mpr (Or.inr (List.mem_cons.mpr (Or.inl he)))
      · exact List.mem_cons.mpr (Or.inr (List.mem_cons.mpr (Or.inr hm)))
    · simp only [h, if_false]
      have := ih best
      rcases List.mem_cons.mp this with he | hm
      · exact List.mem_cons.mpr (Or.inl he)
      · exact List.mem_cons.mpr (Or.inr (List.mem_cons.mpr (Or.inr hm)))

/-- Argmax dominates every element of `best :: xs`. -/
theorem argmaxByCode_ge (score : Code → Int) (best : Code) (xs : List Code) :
    ∀ y ∈ best :: xs, score y ≤ score (argmaxByCode score best xs) := by
  induction xs generalizing best with
  | nil =>
    intro y hy
    simp only [argmaxByCode]
    rcases List.mem_cons.mp hy with he | hm
    · subst he; exact Int.le_refl _
    · exact absurd hm List.not_mem_nil
  | cons x xs ih =>
    intro y hy
    unfold argmaxByCode
    by_cases h : score x > score best
    · simp only [h, if_true]
      rcases List.mem_cons.mp hy with he | hm
      · subst he
        have hx : score x ≤ score (argmaxByCode score x xs) := ih x x List.mem_cons_self
        omega
      · exact ih x y hm
    · simp only [h, if_false]
      have h' : score x ≤ score best := Int.not_lt.mp h
      rcases List.mem_cons.mp hy with he | hm
      · subst he; exact ih y y List.mem_cons_self
      · rcases List.mem_cons.mp hm with hx | hrest
        · subst hx
          have hb : score best ≤ score (argmaxByCode score best xs) :=
            ih best best List.mem_cons_self
          omega
        · exact ih best y (List.mem_cons_of_mem _ hrest)

/-- Membership in the feasible list yields both feasibility conjuncts. -/
theorem mem_feasible_props (rec : SlotRecord) (inv : Inventory) (equip : SlotList)
    (assigned laterCurs : List SlotVal) (c : Code)
    (h : c ∈ feasibleCands rec inv equip assigned laterCurs) :
    1 ≤ ownership c inv equip ∧ forbiddenIn c assigned laterCurs = false := by
  unfold feasibleCands at h
  have hp := (List.mem_filter.mp h).2
  simp only [Bool.and_eq_true, decide_eq_true_eq, Bool.not_eq_true'] at hp
  exact hp

/-- A non-forbidden code is absent from BOTH the assigned prefix and the
later currents — the projected result holds it nowhere else. -/
theorem not_mem_of_not_forbidden (c : Code) (assigned laterCurs : List SlotVal)
    (h : forbiddenIn c assigned laterCurs = false) :
    some c ∉ assigned ∧ some c ∉ laterCurs := by
  constructor
  · intro hm
    have : forbiddenIn c assigned laterCurs = true :=
      List.any_eq_true.mpr ⟨some c, List.mem_append.mpr (Or.inl hm), by simp⟩
    rw [h] at this
    cases this
  · intro hm
    have : forbiddenIn c assigned laterCurs = true :=
      List.any_eq_true.mpr ⟨some c, List.mem_append.mpr (Or.inr hm), by simp⟩
    rw [h] at this
    cases this

/-- One step of the multi-slot fold: choose this slot's result value given the
already-assigned prefix and the later slots' current values. Mirrors the body
of the `for slot in _ordered_slots()` loop in `pick_loadout`:
* no feasible candidate → keep the slot as-is;
* empty slot → fill with the argmax ONLY at a strictly positive score;
* filled slot → swap to the argmax only on a STRICT score improvement. -/
def pickSlotStep (inv : Inventory) (equip : SlotList)
    (rec : SlotRecord) (score : Code → Int)
    (assigned laterCurs : List SlotVal) : SlotVal :=
  match feasibleCands rec inv equip assigned laterCurs with
  | [] => rec.current
  | f :: fs =>
      let best := argmaxByCode score f fs
      match rec.current with
      | none => if 0 < score best then some best else none
      | some cur =>
          if cur = best then some cur
          else if score best > score cur then some best
          else some cur

/-- A `SlotRecord` paired with its per-slot score function. -/
structure ScoredSlot where
  slot : SlotRecord
  scoreFn : Code → Int

/-- The full fold: process slots left-to-right, threading the assigned prefix.
The later slots' currents are recomputed per step from the remaining list,
mirroring the Python `result` dict (assigned prefix + untouched currents). -/
def pickLoadoutAux (inv : Inventory) (equip : SlotList) :
    List ScoredSlot → List SlotVal → List SlotVal
  | [], _ => []
  | sl :: rest, assigned =>
    pickSlotStep inv equip sl.slot sl.scoreFn assigned
        (rest.map (fun s => s.slot.current))
      :: pickLoadoutAux inv equip rest
          (assigned ++ [pickSlotStep inv equip sl.slot sl.scoreFn assigned
              (rest.map (fun s => s.slot.current))])

/-- Top-level pick: deterministic on the input list, no dict iteration anywhere. -/
def pickLoadout (inv : Inventory) (equip : SlotList)
    (slots : List ScoredSlot) : SlotList :=
  pickLoadoutAux inv equip slots []

/-! ### Step case analysis: keep, drop, or a feasible fresh assignment. -/

/-- Every step result is the kept current, `none`, or a FEASIBLE fresh code
(owned and absent from the rest of the projected result). -/
theorem pickSlotStep_cases (inv : Inventory) (equip : SlotList)
    (rec : SlotRecord) (score : Code → Int)
    (assigned laterCurs : List SlotVal) :
    pickSlotStep inv equip rec score assigned laterCurs = rec.current ∨
    pickSlotStep inv equip rec score assigned laterCurs = none ∨
    ∃ c, pickSlotStep inv equip rec score assigned laterCurs = some c ∧
      1 ≤ ownership c inv equip ∧ forbiddenIn c assigned laterCurs = false := by
  unfold pickSlotStep
  cases hfm : feasibleCands rec inv equip assigned laterCurs with
  | nil => left; rfl
  | cons f fs =>
    have h_mem : argmaxByCode score f fs ∈ f :: fs := argmaxByCode_mem score f fs
    have h_in : argmaxByCode score f fs ∈ feasibleCands rec inv equip assigned laterCurs := by
      rw [hfm]; exact h_mem
    have hprops := mem_feasible_props rec inv equip assigned laterCurs _ h_in
    cases hcur : rec.current with
    | none =>
      by_cases hpos : 0 < score (argmaxByCode score f fs)
      · right; right
        exact ⟨argmaxByCode score f fs, by simp [hpos], hprops.1, hprops.2⟩
      · right; left
        simp [hpos]
    | some cur =>
      by_cases heq : cur = argmaxByCode score f fs
      · left; simp [heq]
      · by_cases himp : score (argmaxByCode score f fs) > score cur
        · right; right
          exact ⟨argmaxByCode score f fs, by simp [heq, himp], hprops.1, hprops.2⟩
        · left; simp [heq, himp]

/-! ### The generic demand bound (instantiates to realizability AND 485-safety). -/

/-- Generic fold bound: let `B` be any per-code budget that admits every owned
code (`1 ≤ ownership c → 1 ≤ B c`). If the combined per-code count across the
assigned prefix and the remaining slots' currents respects `B`, then so does
the combined count of the prefix and the fold's output. The two headline
instantiations: `B = ownership` (realizability) and `B = 1` with dup-free
currents (one slot per code / 485-safety). -/
theorem pickLoadoutAux_bound (inv : Inventory) (equip : SlotList) (B : Code → Nat)
    (hB : ∀ c, 1 ≤ ownership c inv equip → 1 ≤ B c) :
    ∀ (slots : List ScoredSlot) (assigned : List SlotVal),
    (∀ c, slotCount c assigned
        + slotCount c (slots.map (fun s => s.slot.current)) ≤ B c) →
    ∀ c, slotCount c assigned
        + slotCount c (pickLoadoutAux inv equip slots assigned) ≤ B c := by
  intro slots
  induction slots with
  | nil =>
    intro assigned h c
    have := h c
    simp only [List.map_nil, slotCount_nil] at this
    simpa [pickLoadoutAux, slotCount_nil] using this
  | cons sl rest ih =>
    intro assigned h c
    simp only [pickLoadoutAux]
    generalize hv : pickSlotStep inv equip sl.slot sl.scoreFn assigned
        (rest.map (fun s => s.slot.current)) = v
    have hstep := pickSlotStep_cases inv equip sl.slot sl.scoreFn assigned
        (rest.map (fun s => s.slot.current))
    rw [hv] at hstep
    -- The shifted hypothesis for the recursive call at `assigned ++ [v]`.
    have h' : ∀ d, slotCount d (assigned ++ [v])
        + slotCount d (rest.map (fun s => s.slot.current)) ≤ B d := by
      intro d
      have hd := h d
      rw [List.map_cons, slotCount_cons] at hd
      rw [slotCount_append, slotCount_cons, slotCount_nil]
      rcases hstep with hkeep | hnone | ⟨e, he, hown, hforb⟩
      · rw [hkeep]
        omega
      · rw [hnone]
        simp only [reduceCtorEq, if_false]
        omega
      · rw [he]
        by_cases hde : e = d
        · subst hde
          have hnm := not_mem_of_not_forbidden e assigned _ hforb
          have h0a : slotCount e assigned = 0 :=
            slotCount_eq_zero_of_not_mem _ _ hnm.1
          have h0l : slotCount e (rest.map (fun s => s.slot.current)) = 0 :=
            slotCount_eq_zero_of_not_mem _ _ hnm.2
          have h1 : 1 ≤ B e := hB e hown
          simp [h0a, h0l, h1]
        · have hne : (some e : SlotVal) ≠ some d := by
            intro hh; injection hh with hh; exact hde hh
          simp only [hne, if_false]
          omega
    have hrec := ih (assigned ++ [v]) h' c
    rw [slotCount_append, slotCount_cons, slotCount_nil] at hrec
    rw [slotCount_cons]
    omega

/-- **HEADLINE Property 1 (Output Realizability)**: the algorithm's output is
realizable, provided the slot-records' current values are consistent with the
equipment (per-code, the records never claim more worn copies than the
equipment holds — Python initializes BOTH from `state.equipment`, where the
records' currents are a per-slot restriction of the equipment values). -/
theorem pickLoadout_realizable (inv : Inventory) (equip : SlotList)
    (slots : List ScoredSlot)
    (hcons : ∀ c, slotCount c (slots.map (fun s => s.slot.current))
        ≤ ownership c inv equip) :
    isRealizable (pickLoadout inv equip slots) inv equip := by
  intro c
  have h0 : ∀ d, slotCount d ([] : SlotList)
      + slotCount d (slots.map (fun s => s.slot.current)) ≤ ownership d inv equip := by
    intro d
    rw [slotCount_nil]
    simpa using hcons d
  have := pickLoadoutAux_bound inv equip (fun d => ownership d inv equip)
      (fun _ hd => hd) slots [] h0 c
  rw [slotCount_nil] at this
  unfold pickLoadout demand
  omega

/-- A slot list is duplicate-free per code: no code occupies two slots. The
SERVER maintains this on worn equipment (one slot per code, HTTP 485). -/
def dupFree (sl : SlotList) : Prop := ∀ c, slotCount c sl ≤ 1

/-- **HEADLINE Property 1b (One Slot Per Code / 485-safety)**: duplicate-free
current equipment yields a duplicate-free output loadout. No code is picked
for two slots — combined with the two-pass execute (unequip all outgoing
first), every equip targets a code worn NOWHERE, so the server's HTTP 485
("This item is already equipped") is unreachable. This is the theorem the
2026-06-10/11 copper_ring livelock was missing: ownership-count feasibility
admitted `{ring1: copper_ring (kept), ring2: copper_ring (spare copy)}`,
which is dup-free-violating and server-rejected. -/
theorem pickLoadout_one_slot_per_code (inv : Inventory) (equip : SlotList)
    (slots : List ScoredSlot)
    (hdup : dupFree (slots.map (fun s => s.slot.current))) :
    dupFree (pickLoadout inv equip slots) := by
  intro c
  have h0 : ∀ d, slotCount d ([] : SlotList)
      + slotCount d (slots.map (fun s => s.slot.current)) ≤ 1 := by
    intro d
    rw [slotCount_nil]
    simpa using hdup d
  have := pickLoadoutAux_bound inv equip (fun _ => 1)
      (fun _ _ => Nat.le_refl 1) slots [] h0 c
  rw [slotCount_nil] at this
  unfold pickLoadout
  omega

/-! ### Property 2 (No-Downgrade, now UNCONDITIONAL). -/

/-- **Property 2 (No-Downgrade)**: a filled slot swaps ONLY on a STRICT score
improvement. The old model allowed a documented "downgrade rather than empty"
branch when a peer slot stole the current code; under the one-slot-per-code
rule no peer slot can ever take a code that is still current here (it is in
the projected result), so the stolen-current branch no longer exists and the
guarantee is strict and unconditional. -/
theorem pickSlotStep_no_downgrade (inv : Inventory) (equip : SlotList)
    (rec : SlotRecord) (score : Code → Int)
    (assigned laterCurs : List SlotVal) (cur r : Code)
    (h_cur : rec.current = some cur)
    (h_res : pickSlotStep inv equip rec score assigned laterCurs = some r)
    (h_ne : cur ≠ r) :
    score cur < score r := by
  unfold pickSlotStep at h_res
  cases hfm : feasibleCands rec inv equip assigned laterCurs with
  | nil =>
    rw [hfm, h_cur] at h_res
    simp at h_res
    exact absurd h_res h_ne
  | cons f fs =>
    rw [hfm, h_cur] at h_res
    by_cases h_eq : cur = argmaxByCode score f fs
    · simp [h_eq] at h_res
      exact absurd (h_eq.trans h_res) h_ne
    · simp [h_eq] at h_res
      by_cases h_imp : score (argmaxByCode score f fs) > score cur
      · simp [h_imp] at h_res
        rw [← h_res]
        omega
      · simp [h_imp] at h_res
        exact absurd h_res h_ne

/-! ### Property 3 (Optimality among feasible candidates). -/

/-- **Property 3 (Optimality)**: when the step assigns a value that is not the
kept current, it is the argmax of the feasible candidate set under the slot's
score. -/
theorem pickSlotStep_optimal (inv : Inventory) (equip : SlotList)
    (rec : SlotRecord) (score : Code → Int)
    (assigned laterCurs : List SlotVal)
    (f : Code) (fs : List Code)
    (h_feas : feasibleCands rec inv equip assigned laterCurs = f :: fs)
    (r : Code)
    (h_res : pickSlotStep inv equip rec score assigned laterCurs = some r)
    (h_not_kept_cur : ∀ cur, rec.current = some cur → cur ≠ r) :
    r = argmaxByCode score f fs := by
  unfold pickSlotStep at h_res
  rw [h_feas] at h_res
  cases hcur : rec.current with
  | none =>
    rw [hcur] at h_res
    by_cases hpos : 0 < score (argmaxByCode score f fs)
    · simp [hpos] at h_res
      exact h_res.symm
    · simp [hpos] at h_res
  | some cur =>
    rw [hcur] at h_res
    have hne : cur ≠ r := h_not_kept_cur cur hcur
    by_cases h_eq : cur = argmaxByCode score f fs
    · simp [h_eq] at h_res
      exact (hne (h_eq.trans h_res)).elim
    · simp [h_eq] at h_res
      by_cases h_imp : score (argmaxByCode score f fs) > score cur
      · simp [h_imp] at h_res
        exact h_res.symm
      · simp [h_imp] at h_res
        exact (hne h_res).elim

/-! ### Property 3b (Zero-score empty-fill suppression, both directions). -/

/-- An empty slot is FILLED only at a strictly positive score: equipping a
zero-score item buys nothing against the target monster and burns the code's
single legal slot. -/
theorem pickSlotStep_empty_fill_positive (inv : Inventory) (equip : SlotList)
    (rec : SlotRecord) (score : Code → Int)
    (assigned laterCurs : List SlotVal) (r : Code)
    (h_cur : rec.current = none)
    (h_res : pickSlotStep inv equip rec score assigned laterCurs = some r) :
    0 < score r := by
  unfold pickSlotStep at h_res
  cases hfm : feasibleCands rec inv equip assigned laterCurs with
  | nil =>
    rw [hfm, h_cur] at h_res
    cases h_res
  | cons f fs =>
    rw [hfm, h_cur] at h_res
    by_cases hpos : 0 < score (argmaxByCode score f fs)
    · simp [hpos] at h_res
      rw [← h_res]
      exact hpos
    · simp [hpos] at h_res

/-- Dual: an empty slot whose best feasible candidate scores ≤ 0 stays empty. -/
theorem pickSlotStep_empty_zero_stays_empty (inv : Inventory) (equip : SlotList)
    (rec : SlotRecord) (score : Code → Int)
    (assigned laterCurs : List SlotVal)
    (h_cur : rec.current = none)
    (h_zero : ∀ f fs, feasibleCands rec inv equip assigned laterCurs = f :: fs →
        score (argmaxByCode score f fs) ≤ 0) :
    pickSlotStep inv equip rec score assigned laterCurs = none := by
  unfold pickSlotStep
  cases hfm : feasibleCands rec inv equip assigned laterCurs with
  | nil => exact h_cur
  | cons f fs =>
    have hz := h_zero f fs hfm
    have hpos : ¬ (0 < score (argmaxByCode score f fs)) := by omega
    rw [h_cur]
    simp [hpos]

/-! ### Property 4 (Determinism). -/

/-- **Property 4 (Determinism)**: `pickLoadout` is a pure function of its
inputs. The fold is deterministic by construction — no dict iteration, no
nondeterministic ordering. The Python `_ordered_slots()` helper produces the
SORTED slot list once; this theorem is the Lean-side guarantee that the
modeled fold ALONE determines the output (no hidden state). -/
theorem pickLoadout_deterministic
    (inv : Inventory) (equip : SlotList)
    (slots : List ScoredSlot) :
    pickLoadout inv equip slots = pickLoadout inv equip slots :=
  rfl

/-- **Determinism corollary**: equal slot-input lists give equal outputs. Pins
that ordering is the ONLY source of nondeterminism, and the Python sort
eliminates it. -/
theorem pickLoadout_extensional
    (inv : Inventory) (equip : SlotList)
    (slots₁ slots₂ : List ScoredSlot)
    (h : slots₁ = slots₂) :
    pickLoadout inv equip slots₁ = pickLoadout inv equip slots₂ := by
  rw [h]

/-! ### Non-vacuity: the literal trace bugs, run through the algorithm. -/

/-- **THE 2026-06-10/11 485 LIVELOCK CASE**: copper_ring worn in ring1_slot,
a SECOND copper_ring in inventory, ring2_slot empty. Ownership-count
feasibility (2 copies owned) would assign ring2 := copper_ring; the server
refuses with HTTP 485 and the identical plan re-derives every cycle. The
fixed algorithm leaves ring2 EMPTY — copper_ring sits in the projected result
at ring1 (kept), so it is infeasible for ring2 even at a positive score. -/
theorem pickLoadout_485_copper_ring_regression :
    pickLoadout (fun c => if c = "copper_ring" then 1 else 0)
      [some "copper_ring", none]
      [{ slot := { current := some "copper_ring", candidates := ["copper_ring"] },
         scoreFn := fun _ => 5 },
       { slot := { current := none, candidates := ["copper_ring"] },
         scoreFn := fun _ => 5 }]
      = [some "copper_ring", none] := by
  decide

/-- **Zero-score empty-fill regression**: an empty slot whose only candidate
scores 0 against the target stays empty (a ring with no relevant resistance
must not be equipped just because the slot is empty). -/
theorem pickLoadout_zero_score_no_fill :
    pickLoadout (fun c => if c = "Z" then 1 else 0)
      [none]
      [{ slot := { current := none, candidates := ["Z"] },
         scoreFn := fun _ => 0 }]
      = [none] := by
  decide

/-- The ring-pair bug attractor (ring1='A', ring2='B', both candidates
everywhere, B scoring higher): under the one-slot-per-code rule the
cross-swap is SUPPRESSED — B is in the projected result at ring2 when ring1
is processed, so ring1 keeps A and ring2 keeps B. The kept loadout wears the
same item multiset as the old `[B, A]` shuffle at ZERO swap cost, and it is
realizable. -/
theorem pickLoadout_ring_pair_regression :
    pickLoadout (fun _ => 0) [some "A", some "B"]
      [{ slot := { current := some "A", candidates := ["A", "B"] },
         scoreFn := fun c => if c = "B" then 100 else 0 },
       { slot := { current := some "B", candidates := ["A", "B"] },
         scoreFn := fun c => if c = "B" then 100 else 0 }]
      = [some "A", some "B"] ∧
    isRealizable [some "A", some "B"] (fun _ => 0) [some "A", some "B"] := by
  constructor
  · decide
  · exact regression_ring_pair_realizable

/-- **Anti-regression**: the pre-fix duplicate output `[B, B]` is impossible:
the concrete run returns `[A, B]`, and `[B, B]` is not even realizable
(`regression_buggy_output_not_realizable`). -/
theorem pickLoadout_cannot_produce_buggy_output :
    pickLoadout (fun _ => 0) [some "A", some "B"]
      [{ slot := { current := some "A", candidates := ["A", "B"] },
         scoreFn := fun c => if c = "B" then 100 else 0 },
       { slot := { current := some "B", candidates := ["A", "B"] },
         scoreFn := fun c => if c = "B" then 100 else 0 }]
      ≠ [some "B", some "B"] := by
  decide

/-- **Empty-slots edge**: `pickLoadout` on no slots yields the empty loadout. -/
theorem pickLoadout_empty
    (inv : Inventory) (equip : SlotList) :
    pickLoadout inv equip [] = [] := rfl

end Formal.RealizableLoadout
