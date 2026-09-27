-- formal/Formal/ObtainModelFeasible.lean
-- @concept: core, planner @property: validity, sufficiency, monotonicity, termination
/-
Unit feasibility of the unified obtain model, mirroring
`src/artifactsmmo_cli/ai/obtain_model/feasible_core.py::feasible_items`.

Phase 1 of docs/PLAN_decision_architecture_redesign.md. "Can I get at least
one unit of X from here?": an item is feasible if it is held, or if some READY
route to it has every input feasible. It is the LEAST such set, so a cycle of
routes never makes an item obtainable by itself.

Items are the naturals below `n` (the Python closure, interned). `held i` is
"a unit is already held"; `routes i` lists the inputs of each ready route to
`i` (an empty list is a route with no inputs: a withdraw, a gather, a drop).

`feasible` iterates the one-step operator `n + 1` times from the empty set.
Python iterates to stability instead; the two agree because both reach the
least fixpoint (`iter_stable`).

Proved (for every graph whose routes only name items below `n`):
- soundness: a feasible item has a finite derivation (`feasible_sound`);
- completeness: every derivable item below `n` is feasible (`feasible_complete`);
- termination bound: `n + 1` rounds reach a fixpoint (`iter_stable`);
- monotonicity: holding more never removes a feasible item (`feasible_mono_held`).

Lean core only — no mathlib.
-/

namespace Formal.ObtainModelFeasible

/-- One feasibility question: items `0 .. n-1`, holdings, ready-route inputs. -/
structure Graph where
  n : Nat
  held : Nat → Bool
  routes : Nat → List (List Nat)

/-- Every input of every ready route of an item below `n` is itself below `n`
(the Python side builds its closure exactly so). -/
def Closed (g : Graph) : Prop :=
  ∀ i, i < g.n → ∀ ins ∈ g.routes i, ∀ x ∈ ins, x < g.n

/-- The one-step operator: keep what is known, add held items, add items with
a ready route whose inputs are all known. -/
def step (g : Graph) (s : Nat → Bool) (i : Nat) : Bool :=
  s i || g.held i || (g.routes i).any (fun ins => ins.all s)

/-- `k` rounds from the empty set. -/
def iter (g : Graph) : Nat → Nat → Bool
  | 0 => fun _ => false
  | k + 1 => step g (iter g k)

/-- `feasible_core.feasible_items`, as a predicate on item indices. -/
def feasible (g : Graph) (i : Nat) : Bool :=
  decide (i < g.n) && iter g (g.n + 1) i

/-- A finite derivation of `i` from holdings through ready routes. -/
inductive Derivable (g : Graph) : Nat → Prop
  | held {i : Nat} : g.held i = true → Derivable g i
  | route {i : Nat} {ins : List Nat} : ins ∈ g.routes i →
      (∀ x ∈ ins, Derivable g x) → Derivable g i

/-! ### Soundness -/

theorem iter_sound (g : Graph) : ∀ k i, iter g k i = true → Derivable g i := by
  intro k
  induction k with
  | zero => intro i h; simp [iter] at h
  | succ k ih =>
    intro i h
    simp only [iter, step, Bool.or_eq_true, List.any_eq_true, List.all_eq_true] at h
    rcases h with (h | h) | ⟨ins, hins, hall⟩
    · exact ih i h
    · exact .held h
    · exact .route hins (fun x hx => ih x (hall x hx))

/-- **SOUNDNESS.** Every feasible item has a derivation from holdings. -/
theorem feasible_sound (g : Graph) (i : Nat) (h : feasible g i = true) : Derivable g i := by
  simp only [feasible, Bool.and_eq_true] at h
  exact iter_sound g _ i h.2

/-! ### Stability after `n + 1` rounds -/

theorem iter_mono (g : Graph) (k i : Nat) (h : iter g k i = true) : iter g (k + 1) i = true := by
  simp [iter, step, h]

/-- The step below `n` reads only values below `n`. -/
theorem step_congr (g : Graph) (hc : Closed g) (s t : Nat → Bool)
    (hst : ∀ j, j < g.n → s j = t j) (i : Nat) (hi : i < g.n) : step g s i = step g t i := by
  have hall : ∀ ins ∈ g.routes i, ins.all s = ins.all t := by
    intro ins hins
    apply Bool.eq_iff_iff.mpr
    simp only [List.all_eq_true]
    constructor
    · intro h x hx; rw [← hst x (hc i hi ins hins x hx)]; exact h x hx
    · intro h x hx; rw [hst x (hc i hi ins hins x hx)]; exact h x hx
  have hany : (g.routes i).any (fun ins => ins.all s) = (g.routes i).any (fun ins => ins.all t) := by
    apply Bool.eq_iff_iff.mpr
    simp only [List.any_eq_true]
    constructor
    · rintro ⟨ins, hins, h⟩; exact ⟨ins, hins, hall ins hins ▸ h⟩
    · rintro ⟨ins, hins, h⟩; exact ⟨ins, hins, (hall ins hins).symm ▸ h⟩
  simp only [step, hst i hi, hany]

theorem countP_le_of_imp (l : List Nat) (p q : Nat → Bool)
    (h : ∀ x ∈ l, p x = true → q x = true) : l.countP p ≤ l.countP q := by
  induction l with
  | nil => simp
  | cons a l ih =>
    have ih' := ih (fun x hx => h x (List.mem_cons_of_mem _ hx))
    have ha := h a List.mem_cons_self
    simp only [List.countP_cons]
    cases hp : p a <;> cases hq : q a <;> simp_all <;> omega

theorem countP_lt_of_imp (l : List Nat) (p q : Nat → Bool)
    (h : ∀ x ∈ l, p x = true → q x = true)
    (hx : ∃ x ∈ l, p x = false ∧ q x = true) : l.countP p < l.countP q := by
  induction l with
  | nil => simp at hx
  | cons a l ih =>
    have hle := countP_le_of_imp l p q (fun x hx => h x (List.mem_cons_of_mem _ hx))
    have ha := h a List.mem_cons_self
    simp only [List.countP_cons]
    rcases hx with ⟨x, hxm, hpx, hqx⟩
    rcases List.mem_cons.mp hxm with rfl | hxl
    · simp [hpx, hqx]; omega
    · have := ih (fun y hy => h y (List.mem_cons_of_mem _ hy)) ⟨x, hxl, hpx, hqx⟩
      cases hp : p a <;> cases hq : q a <;> simp_all <;> omega

/-- The number of items below `n` known after `k` rounds. -/
def known (g : Graph) (k : Nat) : Nat := (List.range g.n).countP (iter g k)

/-- Round `k` is a fixpoint below `n`. -/
def Stable (g : Graph) (k : Nat) : Prop := ∀ i, i < g.n → iter g (k + 1) i = iter g k i

theorem stable_succ (g : Graph) (hc : Closed g) (k : Nat) (h : Stable g k) : Stable g (k + 1) := by
  intro i hi
  exact step_congr g hc _ _ h i hi

/-- Every round is either a fixpoint or has learned at least one more item. -/
theorem stable_or_grows (g : Graph) (hc : Closed g) :
    ∀ k, Stable g k ∨ k ≤ known g k := by
  intro k
  induction k with
  | zero => right; exact Nat.zero_le _
  | succ k ih =>
    rcases ih with hs | hk
    · exact .inl (stable_succ g hc k hs)
    · by_cases hs : Stable g k
      · exact .inl (stable_succ g hc k hs)
      · right
        have hgrow : known g k < known g (k + 1) := by
          apply countP_lt_of_imp
          · intro x _ hx; exact iter_mono g k x hx
          · obtain ⟨i, hi'⟩ := Classical.not_forall.mp hs
            have hi : i < g.n := Classical.byContradiction (fun hn => hi' (fun h => absurd h hn))
            have hne : ¬ iter g (k + 1) i = iter g k i := fun h => hi' (fun _ => h)
            refine ⟨i, List.mem_range.mpr hi, ?_, ?_⟩
            · cases h1 : iter g k i
              · rfl
              · exact absurd (by rw [iter_mono g k i h1, h1]) hne
            · cases h2 : iter g (k + 1) i
              · cases h1 : iter g k i
                · exact absurd (by rw [h2, h1]) hne
                · exact absurd (iter_mono g k i h1) (by simp [h2])
              · rfl
        omega

/-- **TERMINATION BOUND.** After `n + 1` rounds the iteration is at a fixpoint
below `n`, so it equals the least fixpoint Python's run-to-stability reaches. -/
theorem iter_stable (g : Graph) (hc : Closed g) : Stable g (g.n + 1) := by
  rcases stable_or_grows g hc (g.n + 1) with hs | hk
  · exact hs
  · have : known g (g.n + 1) ≤ g.n := by
      have := List.countP_le_length (p := iter g (g.n + 1)) (l := List.range g.n)
      simpa [known] using this
    omega

/-! ### Completeness -/

/-- **COMPLETENESS.** Every derivable item below `n` is feasible. -/
theorem feasible_complete (g : Graph) (hc : Closed g) (i : Nat) (hi : i < g.n)
    (hd : Derivable g i) : feasible g i = true := by
  have hst := iter_stable g hc
  suffices h : ∀ j, Derivable g j → j < g.n → iter g (g.n + 1) j = true by
    simp [feasible, hi, h i hd hi]
  intro j hj
  induction hj with
  | held hh => intro _; simp [iter, step, hh]
  | @route j ins hins _ ih =>
    intro hj
    rw [← hst j hj]
    have hall : ins.all (iter g (g.n + 1)) = true :=
      List.all_eq_true.mpr (fun x hx => ih x hx (hc j hj ins hins x hx))
    simp only [iter, step, Bool.or_eq_true, List.any_eq_true]
    exact .inr ⟨ins, hins, hall⟩

/-! ### Monotonicity -/

theorem derivable_mono_held (g : Graph) (held' : Nat → Bool)
    (hh : ∀ i, g.held i = true → held' i = true) (i : Nat) (hd : Derivable g i) :
    Derivable { g with held := held' } i := by
  induction hd with
  | held h => exact .held (hh _ h)
  | route hins _ ih => exact .route hins ih

/-- **MONOTONICITY.** Holding more never makes a feasible item infeasible. -/
theorem feasible_mono_held (g : Graph) (hc : Closed g) (held' : Nat → Bool)
    (hh : ∀ i, g.held i = true → held' i = true) (i : Nat)
    (h : feasible g i = true) : feasible { g with held := held' } i = true := by
  have hi : i < g.n := by simp only [feasible, Bool.and_eq_true, decide_eq_true_eq] at h; exact h.1
  exact feasible_complete { g with held := held' } hc i hi
    (derivable_mono_held g held' hh i (feasible_sound g i h))

/-! ### Non-vacuity witnesses -/

-- 0 needs 1, 1 needs 0: a cycle is NOT feasible without a way in.
private def cyc : Graph := ⟨2, fun _ => false, fun i => if i = 0 then [[1]] else [[0]]⟩
example : feasible cyc 0 = false := by decide
-- Holding 1 opens the cycle.
private def cycHeld : Graph := ⟨2, fun i => i == 1, fun i => if i = 0 then [[1]] else [[0]]⟩
example : feasible cycHeld 0 = true := by decide
-- A chain 0 <- 1 <- 2 with a free route to 2 (a gather): all feasible.
private def chain : Graph :=
  ⟨3, fun _ => false, fun i => if i = 0 then [[1]] else if i = 1 then [[2]] else [[]]⟩
example : feasible chain 0 = true := by decide
-- A route needs ALL its inputs.
private def both : Graph := ⟨3, fun i => i == 1, fun i => if i = 0 then [[1, 2]] else []⟩
example : feasible both 0 = false := by decide

end Formal.ObtainModelFeasible
