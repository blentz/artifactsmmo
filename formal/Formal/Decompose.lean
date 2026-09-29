-- formal/Formal/Decompose.lean
-- @concept: core, planner @property: validity, sufficiency, safety, monotonicity, termination
/-
THE ONE WALK: feasibility and the next action are one computation (Phase 2c-2 of
docs/PLAN_decision_architecture_redesign.md), mirrored by
`src/artifactsmmo_cli/ai/decompose_core.py`.

Before it, "can I get `q` of `i`" (`ObtainModelSupply.can`) and "what do I do
next" (`NextCraftAction` + `CraftPlanDriver`, over a separate recipe map and a
lossy source projection) were separate models that disagreed: the model said yes,
decomposition declined, the search timed out (craft yield, a secondary-drop
gather, a banked copy of the target: 2026-09-28/29). Here the next action is the
first leaf of the supply tree `can` finds, so the two cannot disagree:

* COMPLETE — a feasible, unmet goal always has a next step (`step_complete`);
* SOUND    — a step is only ever emitted for a feasible goal (`step_sound`);
* VALIDITY — at the top level, no step ⇔ satisfied or infeasible (`step_none_iff`);
* ORDERING — an action is emitted only with every input of its route on hand,
             and only for a route that can deliver the deficit (`step_act_spec`);
* GATES    — a route blocked by openable gates yields "open the first gate"
             before anything else on it (`step_open_spec`);
* YIELD    — a route runs `⌈deficit / yield⌉` times (`runs`), each input is
             needed `per * runs`.

Semantics: DEFICIT, not all-or-nothing. `q` of `i` can be had when `q` are on
hand, or when some route can deliver the DEFICIT `q - onHand i` (its capacity
allows it) and every input can be had in the amount its runs consume. A CRAFT
route's inputs ARE its recipe (no separate recipe map); a WITHDRAW route is an
ordinary route whose capacity is the bank's stock, and `onHand` is the bag.
Routes are tried in list order; the adapter lists ready routes before
gate-blocked ones, so a gate is opened only when nothing ready serves.

Items and gates are naturals (the caller interns them); a route's `tag` names the
concrete action that serves it and is opaque to the walk. Lean core only.
-/

namespace Formal.Decompose

/-- One route to an item, as the walk sees it (`decompose_core.Route`). -/
structure Route where
  tag : Nat
  yieldPer : Nat
  cap : Nat
  inputs : List (Nat × Nat)
  gates : List Nat
  deriving DecidableEq, Repr

/-- One question: items, the bag, and each item's routes in priority order. -/
structure Graph where
  n : Nat
  onHand : Nat → Nat
  routes : Nat → List Route

/-- Applications of a route that deliver `d` units at `y` per application
(Python `-(-d // max(1, y))`); a yield of 0 in the data reads as 1. -/
def runs (d y : Nat) : Nat := (d + max 1 y - 1) / max 1 y

/-- `r` can deliver deficit `d` given a verdict `c` on each input's need. -/
def usable (c : Nat → Nat → Bool) (d : Nat) (r : Route) : Bool :=
  decide (d ≤ r.cap) && r.inputs.all (fun p => c p.1 (runs d r.yieldPer * p.2))

/-- The walk's feasibility (`decompose_core._can`), with fuel. -/
def can (g : Graph) : Nat → List Nat → Nat → Nat → Bool
  | 0, _, _, _ => false
  | fuel + 1, path, i, q =>
    decide (q ≤ g.onHand i) ||
    (!path.contains i &&
      (g.routes i).any (usable (can g fuel (i :: path)) (q - g.onHand i)))

/-- The first route satisfying `u`, with its index. -/
def firstUsable (u : Route → Bool) : List Route → Nat → Option (Nat × Route)
  | [], _ => none
  | r :: rs, k => if u r then some (k, r) else firstUsable u rs (k + 1)

/-- The next step toward the goal. -/
inductive Step where
  /-- Run route `route` of `item` `runs` times, serving deficit `need`. -/
  | act (item route need runs : Nat)
  /-- Open `gate`, which blocks route `route` of `item` (a sub-task). -/
  | openGate (item route gate : Nat)
  deriving DecidableEq, Repr

/-- The first leaf of the supply tree `can` finds (`decompose_core._step`). -/
def step (g : Graph) : Nat → List Nat → Nat → Nat → Option Step
  | 0, _, _, _ => none
  | fuel + 1, path, i, q =>
    if q ≤ g.onHand i then none
    else if path.contains i then none
    else
      let d := q - g.onHand i
      match firstUsable (usable (can g fuel (i :: path)) d) (g.routes i) 0 with
      | none => none
      | some (k, r) =>
        match r.gates with
        | gt :: _ => some (.openGate i k gt)
        | [] =>
          match r.inputs.find? (fun p => !decide (runs d r.yieldPer * p.2 ≤ g.onHand p.1)) with
          | none => some (.act i k d (runs d r.yieldPer))
          | some p => step g fuel (i :: path) p.1 (runs d r.yieldPer * p.2)

/-- `decompose_core.next_step`: the entry point, fuel `n + 1`, empty path. -/
def nextStep (g : Graph) (i q : Nat) : Option Step := step g (g.n + 1) [] i q

/-! ### firstUsable lemmas -/

theorem firstUsable_isSome_iff (u : Route → Bool) :
    ∀ (rs : List Route) (k : Nat), (firstUsable u rs k).isSome = rs.any u := by
  intro rs
  induction rs with
  | nil => intro k; simp [firstUsable]
  | cons r rs ih =>
    intro k
    by_cases h : u r = true
    · simp [firstUsable, h]
    · simp [firstUsable, h, ih]

theorem firstUsable_spec (u : Route → Bool) :
    ∀ (rs : List Route) (k j : Nat) (r : Route),
      firstUsable u rs k = some (j, r) → u r = true ∧ rs[j - k]? = some r ∧ k ≤ j := by
  intro rs
  induction rs with
  | nil => intro k j r h; simp [firstUsable] at h
  | cons r0 rs ih =>
    intro k j r h
    by_cases hu : u r0 = true
    · simp only [firstUsable, hu, if_true, Option.some.injEq, Prod.mk.injEq] at h
      obtain ⟨rfl, rfl⟩ := h
      simp [hu]
    · simp only [firstUsable, hu] at h
      obtain ⟨hu', hget, hle⟩ := ih (k + 1) j r h
      refine ⟨hu', ?_, by omega⟩
      have : j - k = (j - (k + 1)) + 1 := by omega
      rw [this]
      simpa using hget

/-! ### Runs -/

theorem runs_pos (d y : Nat) (h : 1 ≤ d) : 1 ≤ runs d y := by
  unfold runs
  have hy : 1 ≤ max 1 y := Nat.le_max_left _ _
  exact (Nat.le_div_iff_mul_le (by omega)).mpr (by omega)

theorem runs_mono (d d' y : Nat) (h : d' ≤ d) : runs d' y ≤ runs d y :=
  Nat.div_le_div_right (by omega)

/-! ### COMPLETE and SOUND -/

/-- **COMPLETE.** A feasible, unmet goal always has a next step: decomposition
never declines what the walk judges feasible. -/
theorem step_complete (g : Graph) :
    ∀ fuel path i q, can g fuel path i q = true → ¬ q ≤ g.onHand i →
      (step g fuel path i q).isSome = true := by
  intro fuel
  induction fuel with
  | zero => intro path i q h; simp [can] at h
  | succ fuel ih =>
    intro path i q hc hq
    simp only [can, Bool.or_eq_true, decide_eq_true_eq, hq, false_or, Bool.and_eq_true,
      Bool.not_eq_true'] at hc
    obtain ⟨hpath, hany⟩ := hc
    have hsome := (firstUsable_isSome_iff (usable (can g fuel (i :: path)) (q - g.onHand i))
      (g.routes i) 0).trans hany
    simp only [step, hq, if_false]
    have hpc : ¬ path.contains i = true := by simp_all
    simp only [hpc]
    cases hfu : firstUsable (usable (can g fuel (i :: path)) (q - g.onHand i)) (g.routes i) 0 with
    | none => simp [hfu] at hsome
    | some kr =>
      obtain ⟨k, r⟩ := kr
      obtain ⟨hu, _, _⟩ := firstUsable_spec _ _ _ _ _ hfu
      simp only
      cases hg : r.gates with
      | cons gt rest => simp
      | nil =>
        simp only
        cases hf : r.inputs.find?
            (fun p => !decide (runs (q - g.onHand i) r.yieldPer * p.2 ≤ g.onHand p.1)) with
        | none => simp
        | some p =>
          simp only
          have hmem := List.mem_of_find?_eq_some hf
          have hshort := List.find?_some hf
          simp only [Bool.not_eq_true', decide_eq_false_iff_not] at hshort
          simp only [usable, Bool.and_eq_true, decide_eq_true_eq, List.all_eq_true] at hu
          exact ih _ _ _ (hu.2 p hmem) hshort

/-- **SOUND.** A step is only ever emitted for a feasible goal. -/
theorem step_sound (g : Graph) :
    ∀ fuel path i q s, step g fuel path i q = some s → can g fuel path i q = true := by
  intro fuel
  induction fuel with
  | zero => intro path i q s h; simp [step] at h
  | succ fuel _ =>
    intro path i q s h
    simp only [step] at h
    by_cases hq : q ≤ g.onHand i
    · simp [hq] at h
    · simp only [hq, if_false] at h
      by_cases hp : path.contains i = true
      · have hmem : i ∈ path := by simpa using hp
        simp [hmem] at h
      · simp only [hp] at h
        cases hfu : firstUsable (usable (can g fuel (i :: path)) (q - g.onHand i)) (g.routes i) 0 with
        | none => simp [hfu] at h
        | some kr =>
          have hany : (g.routes i).any (usable (can g fuel (i :: path)) (q - g.onHand i)) = true := by
            rw [← firstUsable_isSome_iff _ _ 0, hfu]; rfl
          simp only [can, Bool.or_eq_true, decide_eq_true_eq, hq, false_or, Bool.and_eq_true,
            Bool.not_eq_true']
          exact ⟨by simpa using hp, hany⟩

/-- **VALIDITY.** At the top level, there is no next step exactly when the goal
is satisfied or the walk judges it infeasible. -/
theorem step_none_iff (g : Graph) (fuel : Nat) (path : List Nat) (i q : Nat) :
    step g fuel path i q = none ↔ (q ≤ g.onHand i ∨ can g fuel path i q = false) := by
  constructor
  · intro h
    by_cases hq : q ≤ g.onHand i
    · exact .inl hq
    · right
      cases hc : can g fuel path i q
      · rfl
      · have := step_complete g fuel path i q hc hq
        rw [h] at this; simp at this
  · rintro (hq | hc)
    · cases fuel with
      | zero => rfl
      | succ fuel => simp [step, hq]
    · cases hs : step g fuel path i q with
      | none => rfl
      | some s => rw [step_sound g fuel path i q s hs] at hc; simp at hc

/-! ### ORDERING and GATES -/

/-- **ORDERING.** An action is emitted for a READY route (no blocking gate) that
can deliver the deficit it serves, `runs` is `⌈need / yield⌉` and at least one,
and every input the runs consume is already on hand. -/
theorem step_act_spec (g : Graph) :
    ∀ fuel path i q j k d rn, step g fuel path i q = some (.act j k d rn) →
      ∃ r, (g.routes j)[k]? = some r ∧ r.gates = [] ∧ d ≤ r.cap ∧ 1 ≤ d ∧
        rn = runs d r.yieldPer ∧ ∀ p ∈ r.inputs, rn * p.2 ≤ g.onHand p.1 := by
  intro fuel
  induction fuel with
  | zero => intro path i q j k d rn h; simp [step] at h
  | succ fuel ih =>
    intro path i q j k d rn h
    simp only [step] at h
    by_cases hq : q ≤ g.onHand i
    · simp [hq] at h
    · simp only [hq, if_false] at h
      by_cases hp : path.contains i = true
      · have hmem : i ∈ path := by simpa using hp
        simp [hmem] at h
      · simp only [hp] at h
        cases hfu : firstUsable (usable (can g fuel (i :: path)) (q - g.onHand i)) (g.routes i) 0 with
        | none => simp [hfu] at h
        | some kr =>
          obtain ⟨k0, r⟩ := kr
          obtain ⟨hu, hget, _⟩ := firstUsable_spec _ _ _ _ _ hfu
          simp only [hfu] at h
          cases hg : r.gates with
          | cons gt rest => simp [hg] at h
          | nil =>
            simp only [hg] at h
            cases hf : r.inputs.find?
                (fun p => !decide (runs (q - g.onHand i) r.yieldPer * p.2 ≤ g.onHand p.1)) with
            | none =>
              simp only [hf] at h
              obtain ⟨rfl, rfl, rfl, rfl⟩ := h
              simp only [usable, Bool.and_eq_true, decide_eq_true_eq] at hu
              refine ⟨r, by simpa using hget, hg, hu.1, by omega, rfl, ?_⟩
              intro p hp
              have := List.find?_eq_none.mp hf p hp
              simpa using this
            | some p =>
              simp only [hf] at h
              exact ih _ _ _ _ _ _ _ h

/-- **GATES.** "Open a gate" is emitted only for a route that gate blocks (its
first blocking gate), and only when that route can otherwise deliver. -/
theorem step_open_spec (g : Graph) :
    ∀ fuel path i q j k gt, step g fuel path i q = some (.openGate j k gt) →
      ∃ r, (g.routes j)[k]? = some r ∧ r.gates.head? = some gt := by
  intro fuel
  induction fuel with
  | zero => intro path i q j k gt h; simp [step] at h
  | succ fuel ih =>
    intro path i q j k gt h
    simp only [step] at h
    by_cases hq : q ≤ g.onHand i
    · simp [hq] at h
    · simp only [hq, if_false] at h
      by_cases hp : path.contains i = true
      · have hmem : i ∈ path := by simpa using hp
        simp [hmem] at h
      · simp only [hp] at h
        cases hfu : firstUsable (usable (can g fuel (i :: path)) (q - g.onHand i)) (g.routes i) 0 with
        | none => simp [hfu] at h
        | some kr =>
          obtain ⟨k0, r⟩ := kr
          obtain ⟨_, hget, _⟩ := firstUsable_spec _ _ _ _ _ hfu
          simp only [hfu] at h
          cases hg : r.gates with
          | cons g0 rest =>
            simp only [hg] at h
            obtain ⟨rfl, rfl, rfl⟩ := h
            exact ⟨r, by simpa using hget, by simp [hg]⟩
          | nil =>
            simp only [hg] at h
            cases hf : r.inputs.find?
                (fun p => !decide (runs (q - g.onHand i) r.yieldPer * p.2 ≤ g.onHand p.1)) with
            | none => simp [hf] at h
            | some p =>
              simp only [hf] at h
              exact ih _ _ _ _ _ _ h

/-! ### Supply trees, monotonicity, fuel -/

/-- A finite supply tree for `q` units of `i` (deficit semantics). -/
inductive Supplied (g : Graph) : Nat → Nat → Prop
  | stock {i q : Nat} : q ≤ g.onHand i → Supplied g i q
  | route {i q : Nat} (r : Route) : r ∈ g.routes i → q - g.onHand i ≤ r.cap →
      (∀ p ∈ r.inputs, Supplied g p.1 (runs (q - g.onHand i) r.yieldPer * p.2)) →
      Supplied g i q

/-- **TREE-SOUND.** A yes has a finite supply tree. -/
theorem can_sound (g : Graph) :
    ∀ fuel path i q, can g fuel path i q = true → Supplied g i q := by
  intro fuel
  induction fuel with
  | zero => intro path i q h; simp [can] at h
  | succ fuel ih =>
    intro path i q h
    simp only [can, Bool.or_eq_true, decide_eq_true_eq, Bool.and_eq_true,
      List.any_eq_true] at h
    rcases h with h | ⟨_, r, hr, hu⟩
    · exact .stock h
    · simp only [usable, Bool.and_eq_true, decide_eq_true_eq, List.all_eq_true] at hu
      exact .route r hr hu.1 (fun p hp => ih _ _ _ (hu.2 p hp))

/-- **MONOTONE.** Holding more, or wanting fewer, never turns a yes into a no. -/
theorem can_mono (g : Graph) (h : Nat → Nat) (hle : ∀ i, g.onHand i ≤ h i) :
    ∀ fuel path i q q', q' ≤ q → can g fuel path i q = true →
      can { g with onHand := h } fuel path i q' = true := by
  intro fuel
  induction fuel with
  | zero => intro path i q q' _ hc; simp [can] at hc
  | succ fuel ih =>
    intro path i q q' hq hc
    simp only [can, Bool.or_eq_true, decide_eq_true_eq, Bool.and_eq_true,
      List.any_eq_true] at hc ⊢
    rcases hc with hc | ⟨hp, r, hr, hu⟩
    · exact .inl (Nat.le_trans hq (Nat.le_trans hc (hle i)))
    · right
      refine ⟨hp, r, hr, ?_⟩
      simp only [usable, Bool.and_eq_true, decide_eq_true_eq, List.all_eq_true] at hu ⊢
      have hd : q' - h i ≤ q - g.onHand i := by have := hle i; omega
      refine ⟨Nat.le_trans hd hu.1, fun p hmem => ?_⟩
      exact ih _ _ _ _ (Nat.mul_le_mul_right _ (runs_mono _ _ _ hd)) (hu.2 p hmem)

/-- Every input of every route of an item below `n` is below `n`. -/
def Closed (g : Graph) : Prop :=
  ∀ i, i < g.n → ∀ r ∈ g.routes i, ∀ p ∈ r.inputs, p.1 < g.n

/-- A duplicate-free list of naturals below `n` has at most `n` elements. -/
theorem nodup_length_le : ∀ (n : Nat) (l : List Nat), l.Nodup → (∀ x ∈ l, x < n) → l.length ≤ n := by
  intro n
  induction n with
  | zero =>
    intro l _ hb
    cases l with
    | nil => simp
    | cons a _ => exact absurd (hb a List.mem_cons_self) (Nat.not_lt_zero _)
  | succ n ih =>
    intro l hnd hb
    by_cases hn : n ∈ l
    · have hlen := List.length_erase_of_mem hn
      have := ih (l.erase n) (hnd.erase n) (by
        intro x hx
        have ⟨hne, hxl⟩ := (List.Nodup.mem_erase_iff hnd).mp hx
        have := hb x hxl
        omega)
      have hpos : 0 < l.length := List.length_pos_of_mem hn
      omega
    · have := ih l hnd (by
        intro x hx
        have := hb x hx
        have hne : x ≠ n := fun h => hn (h ▸ hx)
        omega)
      omega

theorem all_congr_mem {α : Type} {p q : α → Bool} :
    ∀ (l : List α), (∀ a ∈ l, p a = q a) → l.all p = l.all q := by
  intro l
  induction l with
  | nil => intro _; rfl
  | cons a l ih =>
    intro h
    simp only [List.all_cons, h a List.mem_cons_self, ih (fun x hx => h x (List.mem_cons_of_mem _ hx))]

theorem any_congr_mem {α : Type} {p q : α → Bool} :
    ∀ (l : List α), (∀ a ∈ l, p a = q a) → l.any p = l.any q := by
  intro l
  induction l with
  | nil => intro _; rfl
  | cons a l ih =>
    intro h
    simp only [List.any_cons, h a List.mem_cons_self, ih (fun x hx => h x (List.mem_cons_of_mem _ hx))]

/-- **FUEL BOUND (feasibility).** For a closed graph, once the fuel exceeds the
number of items the path leaves out, one more unit changes nothing: `n + 1`
from the empty path is exactly the unbounded recursion Python runs. -/
theorem can_fuel_stable (g : Graph) (hc : Closed g) :
    ∀ fuel path i q, path.Nodup → (∀ x ∈ path, x < g.n) → i < g.n →
      g.n + 1 ≤ fuel + path.length → can g (fuel + 1) path i q = can g fuel path i q := by
  intro fuel
  induction fuel with
  | zero =>
    intro path i q hnd hb _ hlen
    have := nodup_length_le g.n path hnd hb
    omega
  | succ fuel ih =>
    intro path i q hnd hb hi hlen
    by_cases hin : i ∈ path
    · simp [can, hin]
    · have hstep : ∀ r ∈ g.routes i,
          usable (can g (fuel + 1) (i :: path)) (q - g.onHand i) r =
          usable (can g fuel (i :: path)) (q - g.onHand i) r := by
        intro r hr
        simp only [usable]
        congr 1
        apply all_congr_mem
        intro p hp
        refine ih _ _ _ (List.nodup_cons.mpr ⟨hin, hnd⟩) ?_ (hc i hi r hr p hp) ?_
        · intro x hx
          rcases List.mem_cons.mp hx with rfl | hx
          · exact hi
          · exact hb x hx
        · simp only [List.length_cons]; omega
      have hany : (g.routes i).any (usable (can g (fuel + 1) (i :: path)) (q - g.onHand i)) =
          (g.routes i).any (usable (can g fuel (i :: path)) (q - g.onHand i)) :=
        any_congr_mem _ hstep
      show (decide (q ≤ g.onHand i) || (!path.contains i && _)) =
        (decide (q ≤ g.onHand i) || (!path.contains i && _))
      rw [hany]

theorem firstUsable_congr (u v : Route → Bool) :
    ∀ (rs : List Route) (k : Nat), (∀ r ∈ rs, u r = v r) → firstUsable u rs k = firstUsable v rs k := by
  intro rs
  induction rs with
  | nil => intro k _; rfl
  | cons r rs ih =>
    intro k h
    simp only [firstUsable, h r List.mem_cons_self]
    rw [ih (k + 1) (fun x hx => h x (List.mem_cons_of_mem _ hx))]

/-- **FUEL BOUND (next step).** The same bound for the step: the Lean walk at
`n + 1` fuel is the unbounded Python walk. -/
theorem step_fuel_stable (g : Graph) (hc : Closed g) :
    ∀ fuel path i q, path.Nodup → (∀ x ∈ path, x < g.n) → i < g.n →
      g.n + 1 ≤ fuel + path.length → step g (fuel + 1) path i q = step g fuel path i q := by
  intro fuel
  induction fuel with
  | zero =>
    intro path i q hnd hb _ hlen
    have := nodup_length_le g.n path hnd hb
    omega
  | succ fuel ih =>
    intro path i q hnd hb hi hlen
    by_cases hq : q ≤ g.onHand i
    · simp [step, hq]
    by_cases hin : i ∈ path
    · simp [step, hq, hin]
    have hnd' : (i :: path).Nodup := List.nodup_cons.mpr ⟨hin, hnd⟩
    have hb' : ∀ x ∈ i :: path, x < g.n := by
      intro x hx
      rcases List.mem_cons.mp hx with rfl | hx
      · exact hi
      · exact hb x hx
    have hlen' : g.n + 1 ≤ fuel + (i :: path).length := by simp only [List.length_cons]; omega
    have hu : ∀ r ∈ g.routes i,
        usable (can g (fuel + 1) (i :: path)) (q - g.onHand i) r =
        usable (can g fuel (i :: path)) (q - g.onHand i) r := by
      intro r hr
      simp only [usable]
      congr 1
      apply all_congr_mem
      intro p hp
      exact can_fuel_stable g hc fuel (i :: path) p.1 _ hnd' hb' (hc i hi r hr p hp) hlen'
    have hfu := firstUsable_congr _ _ (g.routes i) 0 hu
    have hpc : ¬ path.contains i = true := by simpa using hin
    simp only [step, hq, if_false, hpc]
    rw [hfu]
    cases hf : firstUsable (usable (can g fuel (i :: path)) (q - g.onHand i)) (g.routes i) 0 with
    | none => rfl
    | some kr =>
      obtain ⟨k, r⟩ := kr
      obtain ⟨_, hget, _⟩ := firstUsable_spec _ _ _ _ _ hf
      have hr : r ∈ g.routes i := List.mem_of_getElem? (by simpa using hget)
      simp only
      cases r.gates with
      | cons _ _ => rfl
      | nil =>
        simp only
        cases hfind : r.inputs.find?
            (fun p => !decide (runs (q - g.onHand i) r.yieldPer * p.2 ≤ g.onHand p.1)) with
        | none => rfl
        | some p =>
          simp only
          exact ih _ _ _ hnd' hb' (hc i hi r hr p (List.mem_of_find?_eq_some hfind)) hlen'

/-! ### Non-vacuity witnesses -/

-- 0 = copper_ring (1 bar), 1 = copper_bar (10 ore, yields 2), 2 = copper_ore (gathered).
private def ring (onHand : Nat → Nat) (barGates : List Nat) : Graph :=
  ⟨3, onHand, fun i =>
    if i = 0 then [⟨10, 1, 1000, [(1, 1)], []⟩]
    else if i = 1 then [⟨11, 2, 1000, [(2, 10)], barGates⟩]
    else if i = 2 then [⟨12, 1, 1000, [], []⟩] else []⟩

-- From nothing, three rings: gather 20 ore (2 bar runs × 10), the first leaf.
example : nextStep (ring (fun _ => 0) []) 0 3 = some (.act 2 0 20 20) := by decide
-- 20 ore on hand: craft 2 bar runs (yield 2 covers 3 bars).
example : nextStep (ring (fun i => if i = 2 then 20 else 0) []) 0 3 = some (.act 1 0 3 2) := by decide
-- DEFICIT: 1 ring held, 3 wanted ⇒ only 2 more; 20 ore ⇒ bars for 2 = 1 run.
example : nextStep (ring (fun i => if i = 0 then 1 else if i = 2 then 20 else 0) []) 0 3 =
    some (.act 1 0 2 1) := by decide
-- A skill gate (gate 7) on the bar route: open it first.
example : nextStep (ring (fun _ => 0) [7]) 0 3 = some (.openGate 1 0 7) := by decide
-- Satisfied ⇒ none.
example : nextStep (ring (fun i => if i = 0 then 3 else 0) []) 0 3 = none := by decide
-- Infeasible (ore has no route) ⇒ none, and `can` agrees.
private def noOre : Graph :=
  ⟨3, fun _ => 0, fun i => if i = 0 then [⟨10, 1, 1000, [(1, 1)], []⟩]
    else if i = 1 then [⟨11, 1, 1000, [(2, 10)], []⟩] else []⟩
example : nextStep noOre 0 1 = none ∧ can noOre 4 [] 0 1 = false := by decide
-- Capacity: a withdraw of 4 banked copies cannot serve a deficit of 5; the next
-- route (gather) does.
private def banked : Graph :=
  ⟨1, fun _ => 0, fun _ => [⟨20, 1, 4, [], []⟩, ⟨21, 1, 1000, [], []⟩]⟩
example : nextStep banked 0 4 = some (.act 0 0 4 4) := by decide
example : nextStep banked 0 5 = some (.act 0 1 5 5) := by decide

end Formal.Decompose
