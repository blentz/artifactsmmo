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
first leaf of the supply the walk finds, so the two cannot disagree:

* COMPLETE — a feasible goal the bag does not hold always has a next step;
* SOUND    — a step is only ever emitted for a feasible goal;
* VALIDITY — no step ⇔ the bag holds the goal or it is infeasible;
* ORDERING — an action is emitted only for a gate-free route, for a positive
             amount within its capacity, with every input its runs consume in
             the bag;
* GATES    — a route blocked by openable gates yields "open its first gate";
* YIELD    — a route runs `⌈amount / yield⌉` times, each input `per * runs`.

Semantics: the DEFICIT, filled GREEDILY across routes. `q` of `i` can be had
when the bag holds `q`, or when the routes, in priority order, fill the deficit
`q - onHand i`: each usable route takes as much of what is left as its capacity
allows. A WITHDRAW route's capacity is the bank's stock, so a banked copy (of an
input, or of the goal itself) is withdrawn and mixed with production (21 banked,
33 needed ⇒ withdraw 21, gather 12), and a licensed RECYCLE covers what it can
while a gather covers the rest. A CRAFT route's inputs ARE its recipe.

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

/-- `r` can deliver `c` units, given a verdict `v` on each input's need. -/
def usable (v : Nat → Nat → Bool) (c : Nat) (r : Route) : Bool :=
  decide (c ≤ r.cap) && r.inputs.all (fun p => v p.1 (runs c r.yieldPer * p.2))

/-- What route `r` takes of a remaining deficit `d`: all of it, or its capacity. -/
def take (r : Route) (d : Nat) : Nat := min r.cap d

/-- `r` contributes to a remaining deficit `d`. -/
def contributes (v : Nat → Nat → Bool) (d : Nat) (r : Route) : Bool :=
  decide (0 < take r d) && usable v (take r d) r

/-- Greedy fill: the routes, in order, cover `d`; each contributing route takes
`take r d` of it. -/
def fill (v : Nat → Nat → Bool) : List Route → Nat → Bool
  | [], d => decide (d = 0)
  | r :: rs, d => decide (d = 0) || (if contributes v d r then fill v rs (d - take r d) else fill v rs d)

/-- The walk's feasibility (`decompose_core._can`), with fuel. -/
def can (g : Graph) : Nat → List Nat → Nat → Nat → Bool
  | 0, _, _, _ => false
  | fuel + 1, path, i, q =>
    decide (q ≤ g.onHand i) ||
    (!path.contains i && fill (can g fuel (i :: path)) (g.routes i) (q - g.onHand i))

/-- The first contributing route, with its index and amount. -/
def firstTake (v : Nat → Nat → Bool) (d : Nat) : List Route → Nat → Option (Nat × Route × Nat)
  | [], _ => none
  | r :: rs, k => if contributes v d r then some (k, r, take r d) else firstTake v d rs (k + 1)

/-- The next step toward the goal. -/
inductive Step where
  /-- Run route `route` of `item` `runs` times, delivering `amount`. -/
  | act (item route amount runs : Nat)
  /-- Open `gate`, which blocks route `route` of `item` (a sub-task). -/
  | openGate (item route gate : Nat)
  deriving DecidableEq, Repr

/-- The first leaf of the supply the walk finds (`decompose_core._step`). -/
def step (g : Graph) : Nat → List Nat → Nat → Nat → Option Step
  | 0, _, _, _ => none
  | fuel + 1, path, i, q =>
    if q ≤ g.onHand i then none
    else if path.contains i then none
    else if fill (can g fuel (i :: path)) (g.routes i) (q - g.onHand i) = false then none
    else
      match firstTake (can g fuel (i :: path)) (q - g.onHand i) (g.routes i) 0 with
      | none => none
      | some (k, r, c) =>
        match r.gates with
        | gt :: _ => some (.openGate i k gt)
        | [] =>
          match r.inputs.find? (fun p => !decide (runs c r.yieldPer * p.2 ≤ g.onHand p.1)) with
          | none => some (.act i k c (runs c r.yieldPer))
          | some p => step g fuel (i :: path) p.1 (runs c r.yieldPer * p.2)

/-- `decompose_core.next_step`: the entry point, fuel `n + 1`, empty path. -/
def nextStep (g : Graph) (i q : Nat) : Option Step := step g (g.n + 1) [] i q

/-! ### Runs, take, fill, firstTake -/

theorem runs_mono (d d' y : Nat) (h : d' ≤ d) : runs d' y ≤ runs d y :=
  Nat.div_le_div_right (by omega)

theorem take_le_cap (r : Route) (d : Nat) : take r d ≤ r.cap := Nat.min_le_left _ _

/-- A fill of a positive deficit has a first contributor. -/
theorem firstTake_of_fill (v : Nat → Nat → Bool) :
    ∀ (rs : List Route) (d k : Nat), 0 < d → fill v rs d = true →
      (firstTake v d rs k).isSome = true := by
  intro rs
  induction rs with
  | nil => intro d k hd h; simp [fill] at h; omega
  | cons r rs ih =>
    intro d k hd h
    by_cases hc : contributes v d r = true
    · simp [firstTake, hc]
    · have hc' : contributes v d r = false := by simpa using hc
      have hd0 : decide (d = 0) = false := by simp; omega
      simp only [fill, hd0, hc', Bool.false_or, Bool.false_eq_true, if_false] at h
      simp only [firstTake, hc', Bool.false_eq_true, if_false]
      exact ih _ _ hd h

/-- The first contributor is a route of the list, taking a positive amount
within its capacity, usable for that amount. -/
theorem firstTake_spec (v : Nat → Nat → Bool) (d : Nat) :
    ∀ (rs : List Route) (k j : Nat) (r : Route) (c : Nat),
      firstTake v d rs k = some (j, r, c) →
        rs[j - k]? = some r ∧ k ≤ j ∧ c = take r d ∧ 0 < c ∧ usable v c r = true := by
  intro rs
  induction rs with
  | nil => intro k j r c h; simp [firstTake] at h
  | cons r0 rs ih =>
    intro k j r c h
    by_cases hu : contributes v d r0 = true
    · simp only [firstTake, hu, if_true, Option.some.injEq, Prod.mk.injEq] at h
      obtain ⟨rfl, rfl, rfl⟩ := h
      simp only [contributes, Bool.and_eq_true, decide_eq_true_eq] at hu
      exact ⟨by simp, Nat.le_refl _, rfl, hu.1, hu.2⟩
    · have hu' : contributes v d r0 = false := by simpa using hu
      simp only [firstTake, hu', Bool.false_eq_true, if_false] at h
      obtain ⟨hget, hle, hc, hpos, husable⟩ := ih (k + 1) j r c h
      refine ⟨?_, by omega, hc, hpos, husable⟩
      have : j - k = (j - (k + 1)) + 1 := by omega
      rw [this]
      simpa using hget

/-! ### COMPLETE and SOUND -/

/-- **COMPLETE.** A feasible goal the bag does not hold always has a next step:
decomposition never declines what the walk judges feasible. -/
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
    obtain ⟨hpath, hfill⟩ := hc
    have hpc : ¬ path.contains i = true := by simp_all
    have hsome := firstTake_of_fill (can g fuel (i :: path)) (g.routes i) (q - g.onHand i) 0
      (by omega) hfill
    simp only [step, hq, hpc, hfill, if_false, Bool.true_eq_false]
    cases hft : firstTake (can g fuel (i :: path)) (q - g.onHand i) (g.routes i) 0 with
    | none => simp [hft] at hsome
    | some krc =>
      obtain ⟨k, r, c⟩ := krc
      obtain ⟨_, _, _, _, hu⟩ := firstTake_spec _ _ _ _ _ _ _ hft
      simp only
      cases hg : r.gates with
      | cons gt rest => simp
      | nil =>
        simp only
        cases hf : r.inputs.find? (fun p => !decide (runs c r.yieldPer * p.2 ≤ g.onHand p.1)) with
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
    by_cases hq : q ≤ g.onHand i
    · simp [step, hq] at h
    by_cases hp : path.contains i = true
    · have hmem : i ∈ path := by simpa using hp
      simp [step, hq, hmem] at h
    by_cases hfill : fill (can g fuel (i :: path)) (g.routes i) (q - g.onHand i) = true
    · simp only [can, Bool.or_eq_true, decide_eq_true_eq, hq, false_or, Bool.and_eq_true,
        Bool.not_eq_true']
      exact ⟨by simpa using hp, hfill⟩
    · have hf : fill (can g fuel (i :: path)) (g.routes i) (q - g.onHand i) = false := by
        simpa using hfill
      have hpf : path.contains i = false := by simpa using hp
      simp [step, hq, hf] at h

/-- **VALIDITY.** There is no next step exactly when the bag holds the goal or
the walk judges it infeasible. -/
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

/-- The shape every step lemma walks: past the bag, the path guard and the fill,
a step is the first contributor's gate, its action, or a descent into its first
input the bag lacks. -/
theorem step_succ_route (g : Graph) (fuel : Nat) (path : List Nat) (i q : Nat) (s : Step)
    (h : step g (fuel + 1) path i q = some s) (hq : ¬ q ≤ g.onHand i) :
    ∃ k r c, firstTake (can g fuel (i :: path)) (q - g.onHand i) (g.routes i) 0 = some (k, r, c) ∧
      ((∃ gt rest, r.gates = gt :: rest ∧ s = .openGate i k gt) ∨
       (r.gates = [] ∧
        r.inputs.find? (fun p => !decide (runs c r.yieldPer * p.2 ≤ g.onHand p.1)) = none ∧
        s = .act i k c (runs c r.yieldPer)) ∨
       (∃ p, r.gates = [] ∧
        r.inputs.find? (fun p => !decide (runs c r.yieldPer * p.2 ≤ g.onHand p.1)) = some p ∧
        step g fuel (i :: path) p.1 (runs c r.yieldPer * p.2) = some s)) := by
  by_cases hp : path.contains i = true
  · have hmem : i ∈ path := by simpa using hp
    simp [step, hq, hmem] at h
  have hpf : path.contains i = false := by simpa using hp
  by_cases hfill : fill (can g fuel (i :: path)) (g.routes i) (q - g.onHand i) = true
  · simp only [step, hq, hpf, hfill, if_false, Bool.true_eq_false, Bool.false_eq_true] at h
    cases hft : firstTake (can g fuel (i :: path)) (q - g.onHand i) (g.routes i) 0 with
    | none => simp [hft] at h
    | some krc =>
      obtain ⟨k, r, c⟩ := krc
      refine ⟨k, r, c, rfl, ?_⟩
      simp only [hft] at h
      cases hg : r.gates with
      | cons gt rest =>
        simp only [hg, Option.some.injEq] at h
        exact .inl ⟨gt, rest, rfl, h.symm⟩
      | nil =>
        simp only [hg] at h
        cases hf : r.inputs.find? (fun p => !decide (runs c r.yieldPer * p.2 ≤ g.onHand p.1)) with
        | none =>
          simp only [hf, Option.some.injEq] at h
          exact .inr (.inl ⟨rfl, rfl, h.symm⟩)
        | some p =>
          simp only [hf] at h
          exact .inr (.inr ⟨p, rfl, rfl, h⟩)
  · have hf : fill (can g fuel (i :: path)) (g.routes i) (q - g.onHand i) = false := by
      simpa using hfill
    simp [step, hq, hf] at h

/-- **ORDERING.** An action is emitted for a READY route (no blocking gate), for
a positive amount within its capacity (a WITHDRAW never takes more than the bank
holds, a RECYCLE never more than its licence), `runs` is `⌈amount / yield⌉`,
and every input the runs consume is already in the bag. -/
theorem step_act_spec (g : Graph) :
    ∀ fuel path i q j k c rn, step g fuel path i q = some (.act j k c rn) →
      ∃ r, (g.routes j)[k]? = some r ∧ r.gates = [] ∧ 1 ≤ c ∧ c ≤ r.cap ∧
        rn = runs c r.yieldPer ∧ ∀ p ∈ r.inputs, rn * p.2 ≤ g.onHand p.1 := by
  intro fuel
  induction fuel with
  | zero => intro path i q j k c rn h; simp [step] at h
  | succ fuel ih =>
    intro path i q j k c rn h
    by_cases hq : q ≤ g.onHand i
    · simp [step, hq] at h
    obtain ⟨k0, r, c0, hft, hcase⟩ := step_succ_route g fuel path i q _ h hq
    obtain ⟨hget, _, hc, hpos, _⟩ := firstTake_spec _ _ _ _ _ _ _ hft
    rcases hcase with ⟨_, _, _, hs⟩ | ⟨hg, hf, hs⟩ | ⟨p, _, _, hrec⟩
    · simp at hs
    · simp only [Step.act.injEq] at hs
      obtain ⟨rfl, rfl, rfl, rfl⟩ := hs
      refine ⟨r, by simpa using hget, hg, hpos, hc ▸ take_le_cap r _, rfl, ?_⟩
      intro p hp
      have := List.find?_eq_none.mp hf p hp
      simpa using this
    · exact ih _ _ _ _ _ _ _ hrec

/-- **GATES.** "Open a gate" is emitted only for a route that gate blocks (its
first blocking gate). -/
theorem step_open_spec (g : Graph) :
    ∀ fuel path i q j k gt, step g fuel path i q = some (.openGate j k gt) →
      ∃ r, (g.routes j)[k]? = some r ∧ r.gates.head? = some gt := by
  intro fuel
  induction fuel with
  | zero => intro path i q j k gt h; simp [step] at h
  | succ fuel ih =>
    intro path i q j k gt h
    by_cases hq : q ≤ g.onHand i
    · simp [step, hq] at h
    obtain ⟨k0, r, c0, hft, hcase⟩ := step_succ_route g fuel path i q _ h hq
    obtain ⟨hget, _, _, _, _⟩ := firstTake_spec _ _ _ _ _ _ _ hft
    rcases hcase with ⟨g0, rest, hg, hs⟩ | ⟨_, _, hs⟩ | ⟨p, _, _, hrec⟩
    · simp only [Step.openGate.injEq] at hs
      obtain ⟨rfl, rfl, rfl⟩ := hs
      exact ⟨r, by simpa using hget, by simp [hg]⟩
    · simp at hs
    · exact ih _ _ _ _ _ _ hrec

/-! ### Monotonicity -/

/-- The fill is monotone: a verdict that only grows (and never worsens for a
smaller need) fills any smaller deficit the old one filled. -/
theorem fill_mono (v w : Nat → Nat → Bool)
    (hvw : ∀ j n n', n' ≤ n → v j n = true → w j n' = true) :
    ∀ (rs : List Route) (d d' : Nat), d' ≤ d → fill v rs d = true → fill w rs d' = true := by
  intro rs
  induction rs with
  | nil =>
    intro d d' hd h
    simp only [fill, decide_eq_true_eq] at h ⊢
    omega
  | cons r rs ih =>
    intro d d' hd h
    by_cases hd0 : d' = 0
    · simp [fill, hd0]
    have hdpos : 0 < d := by omega
    have hdf : decide (d = 0) = false := by simp; omega
    have hdf' : decide (d' = 0) = false := by simp; omega
    simp only [fill, hdf, Bool.false_or] at h
    simp only [fill, hdf', Bool.false_or]
    have hcw : contributes v d r = true → contributes w d' r = true ∧
        d' - take r d' ≤ d - take r d := by
      intro hc
      simp only [contributes, usable, Bool.and_eq_true, decide_eq_true_eq, List.all_eq_true] at hc ⊢
      obtain ⟨hpos, hcap, hall⟩ := hc
      have hle : take r d' ≤ take r d := by unfold take; omega
      have hpos' : 0 < take r d' := by unfold take at *; omega
      refine ⟨⟨hpos', take_le_cap r d', fun p hp => ?_⟩, by unfold take; omega⟩
      exact hvw _ _ _ (Nat.mul_le_mul_right _ (runs_mono _ _ _ hle)) (hall p hp)
    by_cases hc : contributes v d r = true
    · simp only [hc, if_true] at h
      obtain ⟨hcw', hrem⟩ := hcw hc
      simp only [hcw', if_true]
      exact ih _ _ hrem h
    · have hc' : contributes v d r = false := by simpa using hc
      simp only [hc', Bool.false_eq_true, if_false] at h
      split
      · exact ih _ _ (by omega) h
      · exact ih _ _ hd h

/-- **MONOTONE.** Holding more, or wanting fewer, never turns a yes into a no. -/
theorem can_mono (g : Graph) (h : Nat → Nat) (hle : ∀ i, g.onHand i ≤ h i) :
    ∀ fuel path i q q', q' ≤ q → can g fuel path i q = true →
      can { g with onHand := h } fuel path i q' = true := by
  intro fuel
  induction fuel with
  | zero => intro path i q q' _ hc; simp [can] at hc
  | succ fuel ih =>
    intro path i q q' hq hc
    simp only [can, Bool.or_eq_true, decide_eq_true_eq, Bool.and_eq_true] at hc ⊢
    rcases hc with hc | ⟨hp, hf⟩
    · exact .inl (Nat.le_trans hq (Nat.le_trans hc (hle i)))
    · right
      refine ⟨hp, ?_⟩
      have hd : q' - h i ≤ q - g.onHand i := by have := hle i; omega
      exact fill_mono (can g fuel (i :: path)) (can { g with onHand := h } fuel (i :: path))
        (fun j n n' hn hv => ih (i :: path) j n n' hn hv) _ _ _ hd hf

/-! ### Fuel -/

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

/-- Verdicts that agree on every input of every route give the same
contribution for every amount. -/
theorem contributes_congr (v w : Nat → Nat → Bool) (r : Route)
    (h : ∀ p ∈ r.inputs, ∀ n, v p.1 n = w p.1 n) (d : Nat) :
    contributes v d r = contributes w d r := by
  simp only [contributes, usable]
  congr 2
  exact all_congr_mem _ (fun p hp => h p hp _)

theorem fill_congr (v w : Nat → Nat → Bool) :
    ∀ (rs : List Route), (∀ r ∈ rs, ∀ p ∈ r.inputs, ∀ n, v p.1 n = w p.1 n) →
      ∀ d, fill v rs d = fill w rs d := by
  intro rs
  induction rs with
  | nil => intro _ d; rfl
  | cons r rs ih =>
    intro h d
    have hr := contributes_congr v w r (h r List.mem_cons_self) d
    have ht := ih (fun x hx => h x (List.mem_cons_of_mem _ hx))
    simp only [fill, hr, ht]

theorem firstTake_congr (v w : Nat → Nat → Bool) (d : Nat) :
    ∀ (rs : List Route) (k : Nat), (∀ r ∈ rs, ∀ p ∈ r.inputs, ∀ n, v p.1 n = w p.1 n) →
      firstTake v d rs k = firstTake w d rs k := by
  intro rs
  induction rs with
  | nil => intro _ _; rfl
  | cons r rs ih =>
    intro k h
    have hr := contributes_congr v w r (h r List.mem_cons_self) d
    simp only [firstTake, hr, ih (k + 1) (fun x hx => h x (List.mem_cons_of_mem _ hx))]

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
    · have hstep : ∀ r ∈ g.routes i, ∀ p ∈ r.inputs, ∀ n,
          can g (fuel + 1) (i :: path) p.1 n = can g fuel (i :: path) p.1 n := by
        intro r hr p hp n
        refine ih _ _ _ (List.nodup_cons.mpr ⟨hin, hnd⟩) ?_ (hc i hi r hr p hp) ?_
        · intro x hx
          rcases List.mem_cons.mp hx with rfl | hx
          · exact hi
          · exact hb x hx
        · simp only [List.length_cons]; omega
      have hf := fill_congr _ _ (g.routes i) hstep (q - g.onHand i)
      show (decide (q ≤ g.onHand i) || (!path.contains i && _)) =
        (decide (q ≤ g.onHand i) || (!path.contains i && _))
      rw [hf]

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
    have hv : ∀ r ∈ g.routes i, ∀ p ∈ r.inputs, ∀ n,
        can g (fuel + 1) (i :: path) p.1 n = can g fuel (i :: path) p.1 n :=
      fun r hr p hp n => can_fuel_stable g hc fuel (i :: path) p.1 n hnd' hb' (hc i hi r hr p hp) hlen'
    have hf := fill_congr _ _ (g.routes i) hv (q - g.onHand i)
    have hft := firstTake_congr _ _ (q - g.onHand i) (g.routes i) 0 hv
    have hpc : path.contains i = false := by simpa using hin
    simp only [step, hq, hpc, if_false, Bool.false_eq_true]
    rw [hf, hft]
    split
    · rfl
    · cases hfirst : firstTake (can g fuel (i :: path)) (q - g.onHand i) (g.routes i) 0 with
      | none => rfl
      | some krc =>
        obtain ⟨k, r, c⟩ := krc
        obtain ⟨hget, _, _, _, _⟩ := firstTake_spec _ _ _ _ _ _ _ hfirst
        have hr : r ∈ g.routes i := List.mem_of_getElem? (by simpa using hget)
        simp only
        cases r.gates with
        | cons _ _ => rfl
        | nil =>
          simp only
          cases hfind : r.inputs.find? (fun p => !decide (runs c r.yieldPer * p.2 ≤ g.onHand p.1)) with
          | none => rfl
          | some p =>
            simp only
            exact ih _ _ _ hnd' hb' (hc i hi r hr p (List.mem_of_find?_eq_some hfind)) hlen'

/-! ### Non-vacuity witnesses -/

-- 0 = copper_ring (1 bar), 1 = copper_bar (10 ore, yields 2), 2 = copper_ore (gathered).
private def ring (bag : Nat → Nat) (barGates : List Nat) : Graph :=
  ⟨3, bag, fun i =>
    if i = 0 then [⟨10, 1, 1000, [(1, 1)], []⟩]
    else if i = 1 then [⟨11, 2, 1000, [(2, 10)], barGates⟩]
    else if i = 2 then [⟨12, 1, 1000, [], []⟩] else []⟩

private def none0 : Nat → Nat := fun _ => 0

-- From nothing, three rings: gather 20 ore (2 bar runs × 10), the first leaf.
example : nextStep (ring none0 []) 0 3 = some (.act 2 0 20 20) := by decide
-- 20 ore in the bag: craft 2 bar runs (yield 2 covers 3 bars).
example : nextStep (ring (fun i => if i = 2 then 20 else 0) []) 0 3 = some (.act 1 0 3 2) := by decide
-- DEFICIT: 1 ring held, 3 wanted ⇒ only 2 more; 20 ore ⇒ bars for 2 = 1 run.
example : nextStep (ring (fun i => if i = 0 then 1 else if i = 2 then 20 else 0) []) 0 3 =
    some (.act 1 0 2 1) := by decide
-- A skill gate (gate 7) on the bar route: open it first.
example : nextStep (ring none0 [7]) 0 3 = some (.openGate 1 0 7) := by decide
-- The bag holds the goal ⇒ none.
example : nextStep (ring (fun i => if i = 0 then 3 else 0) []) 0 3 = none := by decide
-- Infeasible (ore has no route) ⇒ none, and `can` agrees.
private def noOre : Graph :=
  ⟨3, none0, fun i => if i = 0 then [⟨10, 1, 1000, [(1, 1)], []⟩]
    else if i = 1 then [⟨11, 1, 1000, [(2, 10)], []⟩] else []⟩
example : nextStep noOre 0 1 = none ∧ can noOre 4 [] 0 1 = false := by decide
-- GREEDY FILL with a bank: 21 algae banked (a WITHDRAW route of capacity 21),
-- 33 needed ⇒ withdraw 21, and once they are in the bag, gather the other 12.
private def potion (bagged : Nat) (banked : Nat) : Graph :=
  ⟨2, fun i => if i = 1 then bagged else 0, fun i =>
    if i = 0 then [⟨30, 1, 1000, [(1, 1)], []⟩]
    else [⟨40, 1, banked, [], []⟩, ⟨41, 1, 1000, [], []⟩]⟩
example : nextStep (potion 0 21) 0 33 = some (.act 1 0 21 21) := by decide
example : nextStep (potion 21 0) 0 33 = some (.act 1 1 12 12) := by decide
-- A banked copy of the GOAL itself is withdrawn (a WITHDRAW route of the goal).
private def bankedGoal : Graph :=
  ⟨1, none0, fun _ => [⟨40, 1, 3, [], []⟩, ⟨41, 1, 1000, [], []⟩]⟩
example : nextStep bankedGoal 0 3 = some (.act 0 0 3 3) := by decide
-- A capped route covers what it can and the next route the rest.
example : nextStep bankedGoal 0 5 = some (.act 0 0 3 3) := by decide
-- A capped route whose share is not enough on its own is still used.
example : can bankedGoal 2 [] 0 5 = true := by decide

end Formal.Decompose
