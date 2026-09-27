-- formal/Formal/ObtainModelSupply.lean
-- @concept: core, planner @property: validity, monotonicity, termination
/-
Quantity feasibility of the unified obtain model, mirroring
`src/artifactsmmo_cli/ai/obtain_model/supply_core.py::can_supply`.

Phase 1 of docs/PLAN_decision_architecture_redesign.md. "Can I get `q` units
of item `i` from here?": yes when `q` are on hand, or when some ready supply
can deliver `q` (its capacity allows it) and every input can be had in the
amount `runs q yield * per_application` its applications consume. An item
already on the path is not obtainable through itself.

Items are the naturals below `n` (the Python closure, interned). `can` carries
explicit fuel; Python recurses without it (and memoises, reusing an answer only
where the path would not change it). `can_fuel_stable` shows `n + 1` fuel is
enough for a closed graph: past it, more fuel never changes the answer.

Proved:
- soundness: a yes has a finite supply tree (`can_sound`);
- monotonicity in holdings (`can_mono_onHand`);
- antitonicity in quantity: fewer units are never harder (`can_anti_qty`);
- fuel bound (`can_fuel_stable`).

Lean core only — no mathlib.
-/

namespace Formal.ObtainModelSupply

/-- One ready route as the walk sees it (`supply_core.Supply`). -/
structure Supply where
  yieldPer : Nat
  cap : Nat
  inputs : List (Nat × Nat)

/-- One quantity question: items `0 .. n-1`, holdings, ready supplies. -/
structure Graph where
  n : Nat
  onHand : Nat → Nat
  supplies : Nat → List Supply

/-- Applications needed for `q` units at `y` per application (`-(-q // y)`). -/
def runs (q y : Nat) : Nat := (q + y - 1) / y

/-- `supply_core._can`, with fuel. -/
def can (g : Graph) : Nat → List Nat → Nat → Nat → Bool
  | 0, _, _, _ => false
  | fuel + 1, path, i, q =>
    decide (q ≤ g.onHand i) ||
    (!path.contains i && (g.supplies i).any (fun s =>
      decide (q ≤ s.cap) &&
      s.inputs.all (fun p => can g fuel (i :: path) p.1 (runs q s.yieldPer * p.2))))

/-- `supply_core.can_supply`. -/
def canSupply (g : Graph) (i q : Nat) : Bool := can g (g.n + 1) [] i q

/-- A finite supply tree for `q` units of `i`. -/
inductive Supplied (g : Graph) : Nat → Nat → Prop
  | stock {i q : Nat} : q ≤ g.onHand i → Supplied g i q
  | route {i q : Nat} (s : Supply) : s ∈ g.supplies i → q ≤ s.cap →
      (∀ p ∈ s.inputs, Supplied g p.1 (runs q s.yieldPer * p.2)) → Supplied g i q

/-! ### Soundness -/

/-- **SOUNDNESS.** A yes has a finite supply tree. -/
theorem can_sound (g : Graph) :
    ∀ fuel path i q, can g fuel path i q = true → Supplied g i q := by
  intro fuel
  induction fuel with
  | zero => intro path i q h; simp [can] at h
  | succ fuel ih =>
    intro path i q h
    simp only [can, Bool.or_eq_true, decide_eq_true_eq, Bool.and_eq_true,
      List.any_eq_true, List.all_eq_true] at h
    rcases h with h | ⟨_, s, hs, hcap, hall⟩
    · exact .stock h
    · exact .route s hs hcap (fun p hp => ih _ _ _ (hall p hp))

/-! ### Monotonicity -/

/-- **MONOTONE IN HOLDINGS.** Holding more never turns a yes into a no. -/
theorem can_mono_onHand (g : Graph) (h : Nat → Nat) (hle : ∀ i, g.onHand i ≤ h i) :
    ∀ fuel path i q, can g fuel path i q = true →
      can { g with onHand := h } fuel path i q = true := by
  intro fuel
  induction fuel with
  | zero => intro path i q hc; simp [can] at hc
  | succ fuel ih =>
    intro path i q hc
    simp only [can, Bool.or_eq_true, decide_eq_true_eq, Bool.and_eq_true,
      List.any_eq_true, List.all_eq_true] at hc ⊢
    rcases hc with hc | ⟨hp, s, hs, hcap, hall⟩
    · exact .inl (Nat.le_trans hc (hle i))
    · exact .inr ⟨hp, s, hs, hcap, fun p hmem => ih _ _ _ (hall p hmem)⟩

theorem runs_mono (q q' y : Nat) (h : q' ≤ q) : runs q' y ≤ runs q y :=
  Nat.div_le_div_right (by omega)

/-- **ANTITONE IN QUANTITY.** If `q` units can be had, so can any fewer. -/
theorem can_anti_qty (g : Graph) :
    ∀ fuel path i q q', q' ≤ q → can g fuel path i q = true → can g fuel path i q' = true := by
  intro fuel
  induction fuel with
  | zero => intro path i q q' _ hc; simp [can] at hc
  | succ fuel ih =>
    intro path i q q' hq hc
    simp only [can, Bool.or_eq_true, decide_eq_true_eq, Bool.and_eq_true,
      List.any_eq_true, List.all_eq_true] at hc ⊢
    rcases hc with hc | ⟨hp, s, hs, hcap, hall⟩
    · exact .inl (Nat.le_trans hq hc)
    · refine .inr ⟨hp, s, hs, Nat.le_trans hq hcap, fun p hmem => ?_⟩
      exact ih _ _ _ _ (Nat.mul_le_mul_right _ (runs_mono q q' s.yieldPer hq)) (hall p hmem)

/-! ### Fuel bound -/

/-- Every input of every supply of an item below `n` is below `n`. -/
def Closed (g : Graph) : Prop :=
  ∀ i, i < g.n → ∀ s ∈ g.supplies i, ∀ p ∈ s.inputs, p.1 < g.n

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

/-- **FUEL BOUND.** For a closed graph, once the fuel exceeds the number of
items the path leaves out, one more unit changes nothing: `n + 1` from the
empty path is exactly the unbounded recursion Python runs. -/
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
    · have step : ∀ s ∈ g.supplies i, ∀ p ∈ s.inputs,
          can g (fuel + 1) (i :: path) p.1 (runs q s.yieldPer * p.2) =
          can g fuel (i :: path) p.1 (runs q s.yieldPer * p.2) := by
        intro s hs p hp
        refine ih _ _ _ (List.nodup_cons.mpr ⟨hin, hnd⟩) ?_ (hc i hi s hs p hp) ?_
        · intro x hx
          rcases List.mem_cons.mp hx with rfl | hx
          · exact hi
          · exact hb x hx
        · simp only [List.length_cons]; omega
      have hany : (g.supplies i).any (fun s => decide (q ≤ s.cap) &&
            s.inputs.all (fun p => can g (fuel + 1) (i :: path) p.1 (runs q s.yieldPer * p.2))) =
          (g.supplies i).any (fun s => decide (q ≤ s.cap) &&
            s.inputs.all (fun p => can g fuel (i :: path) p.1 (runs q s.yieldPer * p.2))) := by
        apply Bool.eq_iff_iff.mpr
        simp only [List.any_eq_true, Bool.and_eq_true, List.all_eq_true]
        constructor
        · rintro ⟨s, hs, hcap, hall⟩
          exact ⟨s, hs, hcap, fun p hp => (step s hs p hp) ▸ hall p hp⟩
        · rintro ⟨s, hs, hcap, hall⟩
          exact ⟨s, hs, hcap, fun p hp => (step s hs p hp).symm ▸ hall p hp⟩
      show (decide (q ≤ g.onHand i) || (!path.contains i && _)) =
        (decide (q ≤ g.onHand i) || (!path.contains i && _))
      rw [hany]

/-! ### Non-vacuity witnesses -/

-- 0 needs two of 1 per application; 1 is gathered (no inputs, unbounded).
private def chain : Graph :=
  ⟨2, fun _ => 0, fun i => if i = 0 then [⟨1, 1000, [(1, 2)]⟩] else [⟨1, 1000, []⟩]⟩
example : canSupply chain 0 5 = true := by decide
-- The same, but 1 comes only from a bank of 3: two units of 0 need 4 of 1.
private def banked : Graph :=
  ⟨2, fun i => if i = 1 then 3 else 0, fun i => if i = 0 then [⟨1, 1000, [(1, 2)]⟩] else []⟩
example : canSupply banked 0 1 = true := by decide
example : canSupply banked 0 2 = false := by decide
-- A capacity-limited route (a GE order of 4) cannot deliver 5.
private def order : Graph := ⟨1, fun _ => 0, fun _ => [⟨1, 4, []⟩]⟩
example : canSupply order 0 4 = true := by decide
example : canSupply order 0 5 = false := by decide
-- A cycle is not its own way in.
private def cyc : Graph :=
  ⟨2, fun _ => 0, fun i => if i = 0 then [⟨1, 1000, [(1, 1)]⟩] else [⟨1, 1000, [(0, 1)]⟩]⟩
example : canSupply cyc 0 1 = false := by decide
-- Yield rounds up the applications: 5 units at 2 per craft need 3 crafts, 3 inputs.
private def yielded : Graph :=
  ⟨2, fun i => if i = 1 then 3 else 0, fun i => if i = 0 then [⟨2, 1000, [(1, 1)]⟩] else []⟩
example : canSupply yielded 0 5 = true := by decide
example : canSupply yielded 0 7 = false := by decide

end Formal.ObtainModelSupply
