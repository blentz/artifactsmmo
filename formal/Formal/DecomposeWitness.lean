-- formal/Formal/DecomposeWitness.lean
-- @concept: core, planner @property: sufficiency, validity
/-
WITNESS for THE ONE WALK (Phase 2d-L1b of docs/PLAN_decision_architecture_redesign.md).

`Formal.Decompose.can` answers "can `q` of `i` be had" JOINTLY: it threads the
bag and each route's capacity through every question it asks. This module
proves what that answer is worth: a yes is backed by a sequence of legs that,
executed against the world, delivers the goal, and the walk's next step is that
sequence's first leg. This is the fact the grind-as-legs liveness model rests
on (a grind is the legs its decomposition emits).

The legs are `Decompose.Step`s. Extraction (`canP`) runs the walk's own
recursion and records, for every route it takes, its gates to open, the legs of
its inputs in order, then the route itself. Execution (`execStep`) is the
world's side:

* `openGate i k gt` records the gate as opened (opening it is a sub-task: a
  grind, modelled by the liveness proofs, not here);
* `act i k c n` needs the route to exist, every one of its gates opened,
  `c` within its capacity left, `n ≥ ⌈c / yield⌉` runs, and every input
  `n * per` in the bag (consumed in order); it credits exactly `c`. A real
  route can yield more (`n * yield ≥ c`); crediting only `c` under-counts,
  which only makes the theorem harder.

What the model does NOT claim: a route's yield is the adapter's number. A
craft, a withdraw or a recycle delivers it; a gather or a monster drop delivers
it on average, so a real leg of those kinds can come up short. The theorem is
then about the plan the walk commits to, and the loop answers the shortfall by
walking again from the real bag (L1c, loop convergence, is where that is
settled).

Headline theorems:

* `canP_state`: extraction answers exactly as the walk does (same state);
* `witness`: executing the extracted legs from any world at least as full as
  the walk's state succeeds and ends holding what the walk set aside;
* `feasible_witness`: from the whole bag, a yes means the legs deliver `q` of
  `i`;
* `step_is_first_leg`: the walk's next step is the first extracted leg.
-/
import Formal.Decompose

namespace Formal.DecomposeWitness

open Formal.Decompose

/-! ### Execution -/

/-- The world a plan runs in: the walk's state (bag, capacity spent) plus the
gates opened so far. -/
structure World where
  st : St
  opened : List (Nat × Nat × Nat)

/-- Take a route's inputs out of the bag, in order, or fail on the first short
one. -/
def consume (s : St) : List (Nat × Nat) → Nat → Option St
  | [], _ => some s
  | p :: ps, n => if n * p.2 ≤ s.bag p.1 then consume (s.reserve p.1 (n * p.2)) ps n else none

/-- Deliver `c` of `i` by route `k`: the bag gains `c`, the route spends `c`. -/
def credit (s : St) (i k c : Nat) : St :=
  { s.use i k c with bag := fun j => if j = i then s.bag j + c else s.bag j }

/-- One leg against the world. -/
def execStep (g : Graph) (w : World) : Step → Option World
  | .openGate i k gt => some { w with opened := (i, k, gt) :: w.opened }
  | .act i k c n =>
    match (g.routes i)[k]? with
    | none => none
    | some r =>
      if r.gates.all (fun gt => w.opened.contains (i, k, gt)) &&
          decide (w.st.used i k + c ≤ r.cap) && decide (runs c r.yieldPer ≤ n) then
        (consume w.st r.inputs n).map (fun s => { w with st := credit s i k c })
      else none

/-- A plan, leg by leg. -/
def execAll (g : Graph) : List Step → World → Option World
  | [], w => some w
  | a :: l, w =>
    match execStep g w a with
    | none => none
    | some w' => execAll g l w'

/-! ### Extraction: the walk, recording its legs -/

/-- `Decompose.feed`, recording each input's legs in order. -/
def feedP (v : Nat → Nat → St → Option (St × List Step)) :
    List (Nat × Nat) → Nat → St → Option (St × List Step)
  | [], _, s => some (s, [])
  | p :: ps, n, s =>
    match v p.1 (n * p.2) s with
    | none => none
    | some (s', l) =>
      match feedP v ps n s' with
      | none => none
      | some (t, l') => some (t, l ++ l')

/-- `Decompose.useRoute`, recording the route's gates, its inputs' legs, then
the route itself. -/
def useRouteP (v : Nat → Nat → St → Option (St × List Step)) (i k : Nat) (r : Route) (d : Nat)
    (s : St) : Option (St × List Step) :=
  if take s i k r d = 0 then none
  else
    match feedP v r.inputs (runs (take s i k r d) r.yieldPer) (s.use i k (take s i k r d)) with
    | none => none
    | some (t, l) =>
      some (t, r.gates.map (fun gt => Step.openGate i k gt) ++ l ++
        [Step.act i k (take s i k r d) (runs (take s i k r d) r.yieldPer)])

/-- `Decompose.fill`, recording the legs of every contributing route. -/
def fillP (v : Nat → Nat → St → Option (St × List Step)) (i : Nat) :
    List Route → Nat → Nat → St → Option (St × List Step)
  | [], _, d, s => if d = 0 then some (s, []) else none
  | r :: rs, k, d, s =>
    if d = 0 then some (s, [])
    else
      match useRouteP v i k r d s with
      | some (s', l) =>
        match fillP v i rs (k + 1) (d - take s i k r d) s' with
        | none => none
        | some (t, l') => some (t, l ++ l')
      | none => fillP v i rs (k + 1) d s

/-- `Decompose.can`, recording the legs. -/
def canP (g : Graph) : Nat → List Nat → Nat → Nat → St → Option (St × List Step)
  | 0, _, _, _, _ => none
  | fuel + 1, path, i, q, s =>
    if q ≤ s.bag i then some (s.reserve i q, [])
    else if path.contains i then none
    else fillP (canP g fuel (i :: path)) i (g.routes i) 0 (q - s.bag i) (s.reserve i (s.bag i))

/-- The legs behind a yes from the whole bag. -/
def plan (g : Graph) (i q : Nat) : List Step :=
  match canP g (g.n + 1) [] i q (St.init g) with
  | none => []
  | some (_, l) => l

/-! ### Extraction answers exactly as the walk does -/

theorem feedP_state (v : Nat → Nat → St → Option St) (vP : Nat → Nat → St → Option (St × List Step))
    (hv : ∀ j m s, (vP j m s).map Prod.fst = v j m s) :
    ∀ (ps : List (Nat × Nat)) (n : Nat) (s : St), (feedP vP ps n s).map Prod.fst = feed v ps n s := by
  intro ps
  induction ps with
  | nil => intro n s; rfl
  | cons p ps ih =>
    intro n s
    have h1 := hv p.1 (n * p.2) s
    simp only [feedP, feed]
    cases hp : vP p.1 (n * p.2) s with
    | none => rw [hp] at h1; simp only [Option.map_none] at h1; rw [← h1]; rfl
    | some sl =>
      obtain ⟨s', l⟩ := sl
      rw [hp] at h1; simp only [Option.map_some] at h1; rw [← h1]
      simp only
      have h2 := ih n s'
      cases hf : feedP vP ps n s' with
      | none => rw [hf] at h2; simp only [Option.map_none] at h2; rw [← h2]; rfl
      | some tl => rw [hf] at h2; simp only [Option.map_some] at h2; rw [← h2]; rfl

theorem useRouteP_state (v : Nat → Nat → St → Option St) (vP : Nat → Nat → St → Option (St × List Step))
    (hv : ∀ j m s, (vP j m s).map Prod.fst = v j m s) (i k : Nat) (r : Route) (d : Nat) (s : St) :
    (useRouteP vP i k r d s).map Prod.fst = useRoute v i k r d s := by
  unfold useRouteP useRoute
  split
  · rfl
  · have h := feedP_state v vP hv r.inputs (runs (take s i k r d) r.yieldPer) (s.use i k (take s i k r d))
    cases hf : feedP vP r.inputs (runs (take s i k r d) r.yieldPer) (s.use i k (take s i k r d)) with
    | none => rw [hf] at h; simp only [Option.map_none] at h; rw [← h]; rfl
    | some tl => rw [hf] at h; simp only [Option.map_some] at h; rw [← h]; rfl

theorem fillP_state (v : Nat → Nat → St → Option St) (vP : Nat → Nat → St → Option (St × List Step))
    (hv : ∀ j m s, (vP j m s).map Prod.fst = v j m s) (i : Nat) :
    ∀ (rs : List Route) (k d : Nat) (s : St), (fillP vP i rs k d s).map Prod.fst = fill v i rs k d s := by
  intro rs
  induction rs with
  | nil => intro k d s; simp only [fillP, fill]; split <;> rfl
  | cons r rs ih =>
    intro k d s
    simp only [fillP, fill]
    split
    · rfl
    · have hu := useRouteP_state v vP hv i k r d s
      cases hup : useRouteP vP i k r d s with
      | none =>
        rw [hup] at hu; simp only [Option.map_none] at hu; rw [← hu]
        exact ih _ _ _
      | some sl =>
        obtain ⟨s', l⟩ := sl
        rw [hup] at hu; simp only [Option.map_some] at hu; rw [← hu]
        simp only
        have h2 := ih (k + 1) (d - take s i k r d) s'
        cases hf : fillP vP i rs (k + 1) (d - take s i k r d) s' with
        | none => rw [hf] at h2; simp only [Option.map_none] at h2; rw [← h2]; rfl
        | some tl => rw [hf] at h2; simp only [Option.map_some] at h2; rw [← h2]; rfl

/-- **Extraction is the walk.** `canP` reaches exactly the state `can` does:
the legs are recorded, the answer is untouched. -/
theorem canP_state (g : Graph) :
    ∀ fuel path i q (s : St), (canP g fuel path i q s).map Prod.fst = can g fuel path i q s := by
  intro fuel
  induction fuel with
  | zero => intro path i q s; rfl
  | succ fuel ih =>
    intro path i q s
    simp only [canP, can]
    split
    · rfl
    · split
      · rfl
      · exact fillP_state _ _ (fun j m s => ih _ j m s) i _ _ _ _

/-! ### Execution algebra -/

theorem execAll_append (g : Graph) :
    ∀ (l l' : List Step) (w : World), execAll g (l ++ l') w = (execAll g l w).bind (execAll g l') := by
  intro l
  induction l with
  | nil => intro l' w; rfl
  | cons a l ih =>
    intro l' w
    simp only [List.cons_append, execAll]
    cases execStep g w a with
    | none => rfl
    | some w' => exact ih l' w'

theorem execStep_opened (g : Graph) (w w' : World) (a : Step) (h : execStep g w a = some w') :
    ∀ x ∈ w.opened, x ∈ w'.opened := by
  intro x hx
  cases a with
  | openGate i k gt =>
    simp only [execStep, Option.some.injEq] at h
    subst h; exact List.mem_cons_of_mem _ hx
  | act i k c n =>
    simp only [execStep] at h
    split at h
    · simp at h
    · split at h
      · obtain ⟨s, _, rfl⟩ := Option.map_eq_some_iff.mp h
        exact hx
      · simp at h

theorem execAll_opened (g : Graph) :
    ∀ (l : List Step) (w w' : World), execAll g l w = some w' → ∀ x ∈ w.opened, x ∈ w'.opened := by
  intro l
  induction l with
  | nil => intro w w' h x hx; simp only [execAll, Option.some.injEq] at h; subst h; exact hx
  | cons a l ih =>
    intro w w' h x hx
    simp only [execAll] at h
    cases hs : execStep g w a with
    | none => simp [hs] at h
    | some w1 =>
      simp only [hs] at h
      exact ih w1 w' h x (execStep_opened g w w1 a hs x hx)

/-- Opening a route's gates records each of them and changes nothing else. -/
theorem exec_opens (g : Graph) (i k : Nat) :
    ∀ (gates : List Nat) (w : World), ∃ w', execAll g (gates.map (fun gt => Step.openGate i k gt)) w = some w' ∧
      w'.st = w.st ∧ (∀ x ∈ w.opened, x ∈ w'.opened) ∧ ∀ gt ∈ gates, (i, k, gt) ∈ w'.opened := by
  intro gates
  induction gates with
  | nil => intro w; exact ⟨w, rfl, rfl, fun _ h => h, by simp⟩
  | cons gt gates ih =>
    intro w
    obtain ⟨w', h, hst, hmono, hin⟩ := ih { w with opened := (i, k, gt) :: w.opened }
    refine ⟨w', ?_, hst, fun x hx => hmono x (List.mem_cons_of_mem _ hx), ?_⟩
    · simp only [List.map_cons, execAll, execStep]; exact h
    · intro gt' hgt
      rcases List.mem_cons.mp hgt with rfl | hgt
      · exact hmono _ List.mem_cons_self
      · exact hin gt' hgt

/-! ### WITNESS -/

/-- Unit vector: `q` at `i`. -/
def e (i q : Nat) : Nat → Nat := fun j => if j = i then q else 0

/-- What a route's inputs consume, per item. -/
def need : List (Nat × Nat) → Nat → Nat → Nat
  | [], _, _ => 0
  | p :: ps, n, j => (if j = p.1 then n * p.2 else 0) + need ps n j

/-- The world holds at least the walk's bag plus `x`, and has spent at most the
walk's capacity less `y`. -/
def Covers (w : World) (s : St) (x : Nat → Nat) (y : Nat → Nat → Nat) : Prop :=
  (∀ j, s.bag j + x j ≤ w.st.bag j) ∧ (∀ j k, w.st.used j k + y j k ≤ s.used j k)

/-- The walk never spends a route past its capacity. -/
def CapOk (g : Graph) (s : St) : Prop :=
  ∀ j k r, (g.routes j)[k]? = some r → s.used j k ≤ r.cap

theorem consume_covers (t : St) (y : Nat → Nat → Nat) :
    ∀ (ps : List (Nat × Nat)) (n : Nat) (w : World) (x : Nat → Nat),
      Covers w t (fun j => x j + need ps n j) y →
        ∃ s', consume w.st ps n = some s' ∧ Covers { w with st := s' } t x y := by
  intro ps
  induction ps with
  | nil => intro n w x h; exact ⟨w.st, rfl, by simpa [need] using h⟩
  | cons p ps ih =>
    intro n w x h
    obtain ⟨hb, hu⟩ := h
    have hp : n * p.2 ≤ w.st.bag p.1 := by
      have := hb p.1; simp only [need, if_true] at this; omega
    simp only [consume, hp, if_true]
    refine ih n { w with st := w.st.reserve p.1 (n * p.2) } x ⟨fun j => ?_, fun j k => ?_⟩
    · have := hb j
      simp only [need, St.reserve] at this ⊢
      by_cases hj : j = p.1
      · rw [if_pos hj] at this ⊢; omega
      · rw [if_neg hj] at this ⊢; omega
    · simpa [St.reserve] using hu j k

theorem Covers.mono_x {w : World} {s : St} {x x' : Nat → Nat} {y : Nat → Nat → Nat}
    (h : Covers w s x y) (hx : ∀ j, x' j ≤ x j) : Covers w s x' y :=
  ⟨fun j => Nat.le_trans (Nat.add_le_add_left (hx j) _) (h.1 j), h.2⟩

/-- A verdict whose every yes is witnessed by its legs. -/
def Witnessed (g : Graph) (vP : Nat → Nat → St → Option (St × List Step)) : Prop :=
  ∀ j m s t l, vP j m s = some (t, l) → CapOk g s →
    CapOk g t ∧ ∀ w x y, Covers w s x y →
      ∃ w', execAll g l w = some w' ∧ Covers w' t (fun z => x z + e j m z) y

theorem feedP_witness (g : Graph) (vP : Nat → Nat → St → Option (St × List Step)) (hv : Witnessed g vP) :
    ∀ (ps : List (Nat × Nat)) (n : Nat) (s t : St) (l : List Step), feedP vP ps n s = some (t, l) →
      CapOk g s → CapOk g t ∧ ∀ w x y, Covers w s x y →
        ∃ w', execAll g l w = some w' ∧ Covers w' t (fun z => x z + need ps n z) y := by
  intro ps
  induction ps with
  | nil =>
    intro n s t l h hc
    simp only [feedP, Option.some.injEq, Prod.mk.injEq] at h
    obtain ⟨rfl, rfl⟩ := h
    exact ⟨hc, fun w x y hw => ⟨w, rfl, by simpa [need] using hw⟩⟩
  | cons p ps ih =>
    intro n s t l h hc
    simp only [feedP] at h
    cases h1 : vP p.1 (n * p.2) s with
    | none => simp [h1] at h
    | some sl =>
      obtain ⟨s', l1⟩ := sl
      simp only [h1] at h
      cases h2 : feedP vP ps n s' with
      | none => simp [h2] at h
      | some tl =>
        obtain ⟨t', l2⟩ := tl
        simp only [h2, Option.some.injEq, Prod.mk.injEq] at h
        obtain ⟨rfl, rfl⟩ := h
        obtain ⟨hc1, hw1⟩ := hv _ _ _ _ _ h1 hc
        obtain ⟨hc2, hw2⟩ := ih n s' _ l2 h2 hc1
        refine ⟨hc2, fun w x y hw => ?_⟩
        obtain ⟨w1, hx1, hcov1⟩ := hw1 w x y hw
        obtain ⟨w2, hx2, hcov2⟩ := hw2 w1 _ y hcov1
        refine ⟨w2, by rw [execAll_append, hx1]; exact hx2, ?_⟩
        refine Covers.mono_x hcov2 (fun z => ?_)
        simp only [need, e]
        by_cases hz : z = p.1
        · simp only [if_pos hz]; omega
        · simp only [if_neg hz]; omega

/-- Unit vector on a route: `c` at route `k` of `i`. -/
def e2 (i k c : Nat) : Nat → Nat → Nat := fun j l => if j = i ∧ l = k then c else 0

theorem useRouteP_witness (g : Graph) (vP : Nat → Nat → St → Option (St × List Step))
    (hv : Witnessed g vP) (i k : Nat) (r : Route) (hr : (g.routes i)[k]? = some r) (d : Nat) (s t : St)
    (l : List Step) (h : useRouteP vP i k r d s = some (t, l)) (hc : CapOk g s) :
    CapOk g t ∧ ∀ w x y, Covers w s x y →
      ∃ w', execAll g l w = some w' ∧ Covers w' t (fun z => x z + e i (take s i k r d) z) y := by
  unfold useRouteP at h
  split at h
  · simp at h
  rename_i hc0
  generalize hcdef : take s i k r d = c at h hc0 ⊢
  have hcle : c ≤ r.cap - s.used i k := by rw [← hcdef]; unfold take; omega
  cases hf : feedP vP r.inputs (runs c r.yieldPer) (s.use i k c) with
  | none => simp [hf] at h
  | some tl =>
    obtain ⟨t', lf⟩ := tl
    simp only [hf, Option.some.injEq, Prod.mk.injEq] at h
    obtain ⟨rfl, rfl⟩ := h
    have hcu : CapOk g (s.use i k c) := by
      intro j k' r' hr'
      simp only [St.use]
      split
      · rename_i hjk
        obtain ⟨hj, hk⟩ := hjk
        rw [hj, hk] at hr' ⊢
        rw [hr] at hr'; cases hr'
        have := hc i k r hr; omega
      · exact hc j k' r' hr'
    obtain ⟨hct, hwf⟩ := feedP_witness g vP hv r.inputs (runs c r.yieldPer) _ _ _ hf hcu
    refine ⟨hct, fun w x y hw => ?_⟩
    obtain ⟨w0, hx0, hst0, _, hin0⟩ := exec_opens g i k r.gates w
    have hcov0 : Covers w0 (s.use i k c) x (fun j l => y j l + e2 i k c j l) := by
      refine ⟨fun j => ?_, fun j l => ?_⟩
      · rw [hst0]; simpa [St.use] using hw.1 j
      · rw [hst0]
        have := hw.2 j l
        simp only [St.use, e2]
        split <;> omega
    obtain ⟨w1, hx1, hcov1⟩ := hwf w0 x _ hcov0
    have hopen1 := execAll_opened g lf w0 w1 hx1
    obtain ⟨s2, hcons, hcov2⟩ := consume_covers _ _ r.inputs (runs c r.yieldPer) w1 x hcov1
    have hcap : w1.st.used i k + c ≤ r.cap := by
      have := hcov1.2 i k
      have := hct i k r hr
      simp only [e2, and_self, if_true] at *
      omega
    have hgates : r.gates.all (fun gt => w1.opened.contains (i, k, gt)) = true := by
      simp only [List.all_eq_true, List.contains_iff_mem]
      exact fun gt hgt => hopen1 _ (hin0 gt hgt)
    refine ⟨{ w1 with st := credit s2 i k c }, ?_, ?_⟩
    · rw [execAll_append, execAll_append, hx0]
      simp only [Option.bind_some, hx1, execAll, execStep, hr, hgates, hcap, decide_true,
        Nat.le_refl, Bool.and_self, if_true, hcons, Option.map_some]
    · refine ⟨fun j => ?_, fun j l => ?_⟩
      · have := hcov2.1 j
        simp only [credit, e]
        split <;> simp_all <;> omega
      · have := hcov2.2 j l
        simp only [credit, St.use, e2] at this ⊢
        split <;> simp_all <;> omega

theorem fillP_witness (g : Graph) (vP : Nat → Nat → St → Option (St × List Step))
    (hv : Witnessed g vP) (i : Nat) :
    ∀ (rs : List Route) (k d : Nat) (s t : St) (l : List Step),
      (∀ n, (g.routes i)[k + n]? = rs[n]?) → fillP vP i rs k d s = some (t, l) → CapOk g s →
        CapOk g t ∧ ∀ w x y, Covers w s x y →
          ∃ w', execAll g l w = some w' ∧ Covers w' t (fun z => x z + e i d z) y := by
  intro rs
  induction rs with
  | nil =>
    intro k d s t l _ h hc
    simp only [fillP] at h
    split at h
    · rename_i hd
      simp only [Option.some.injEq, Prod.mk.injEq] at h
      obtain ⟨rfl, rfl⟩ := h
      exact ⟨hc, fun w x y hw => ⟨w, rfl, by simpa [e, hd] using hw⟩⟩
    · simp at h
  | cons r rs ih =>
    intro k d s t l hidx h hc
    have hidx' : ∀ n, (g.routes i)[k + 1 + n]? = rs[n]? := by
      intro n; have := hidx (n + 1); rw [show k + (n + 1) = k + 1 + n by omega] at this; simpa using this
    have hr : (g.routes i)[k]? = some r := by simpa using hidx 0
    simp only [fillP] at h
    split at h
    · rename_i hd
      simp only [Option.some.injEq, Prod.mk.injEq] at h
      obtain ⟨rfl, rfl⟩ := h
      exact ⟨hc, fun w x y hw => ⟨w, rfl, by simpa [e, hd] using hw⟩⟩
    · cases hu : useRouteP vP i k r d s with
      | none =>
        simp only [hu] at h
        exact ih (k + 1) d s t l hidx' h hc
      | some sl =>
        obtain ⟨s', l1⟩ := sl
        simp only [hu] at h
        cases hf : fillP vP i rs (k + 1) (d - take s i k r d) s' with
        | none => simp [hf] at h
        | some tl =>
          obtain ⟨t', l2⟩ := tl
          simp only [hf, Option.some.injEq, Prod.mk.injEq] at h
          obtain ⟨rfl, rfl⟩ := h
          obtain ⟨hc1, hw1⟩ := useRouteP_witness g vP hv i k r hr d s s' l1 hu hc
          obtain ⟨hc2, hw2⟩ := ih (k + 1) _ s' _ l2 hidx' hf hc1
          refine ⟨hc2, fun w x y hw => ?_⟩
          obtain ⟨w1, hx1, hcov1⟩ := hw1 w x y hw
          obtain ⟨w2, hx2, hcov2⟩ := hw2 w1 _ y hcov1
          refine ⟨w2, by rw [execAll_append, hx1]; exact hx2, Covers.mono_x hcov2 (fun z => ?_)⟩
          have htd : take s i k r d ≤ d := by unfold take; omega
          simp only [e]
          split <;> omega

theorem canP_witness (g : Graph) : ∀ fuel path, Witnessed g (canP g fuel path) := by
  intro fuel
  induction fuel with
  | zero => intro path j m s t l h; simp [canP] at h
  | succ fuel ih =>
    intro path j m s t l h hc
    simp only [canP] at h
    split at h
    · rename_i hm
      simp only [Option.some.injEq, Prod.mk.injEq] at h
      obtain ⟨rfl, rfl⟩ := h
      refine ⟨fun j' k r hr => hc j' k r hr, fun w x y hw => ⟨w, rfl, fun z => ?_, fun a b => hw.2 a b⟩⟩
      have := hw.1 z
      simp only [St.reserve, e]
      split <;> simp_all <;> omega
    · split at h
      · simp at h
      · have hc0 : CapOk g (s.reserve j (s.bag j)) := fun j' k r hr => hc j' k r hr
        obtain ⟨hct, hw⟩ := fillP_witness g _ (ih (j :: path)) j (g.routes j) 0 _ _ _ _
          (fun n => by simp) h hc0
        refine ⟨hct, fun w x y hcov => ?_⟩
        have hcov0 : Covers w (s.reserve j (s.bag j)) (fun z => x z + e j (s.bag j) z) y := by
          refine ⟨fun z => ?_, fun a b => hcov.2 a b⟩
          have := hcov.1 z
          simp only [St.reserve, e]
          split <;> simp_all <;> omega
        obtain ⟨w', hx, hcov'⟩ := hw w _ y hcov0
        refine ⟨w', hx, Covers.mono_x hcov' (fun z => ?_)⟩
        rename_i hm _
        simp only [e]
        split <;> omega

/-- **WITNESS.** A yes from the walk is backed by the legs it extracts:
executed against any world at least as full as the walk's state, and with at
most its capacity spent, they succeed and leave the world holding what the walk
set aside plus the `q` of `i` it was asked for. -/
theorem witness (g : Graph) (fuel : Nat) (path : List Nat) (i q : Nat) (s t : St)
    (h : can g fuel path i q s = some t) (hc : CapOk g s) :
    ∃ l, canP g fuel path i q s = some (t, l) ∧ ∀ w x y, Covers w s x y →
      ∃ w', execAll g l w = some w' ∧ Covers w' t (fun z => x z + e i q z) y := by
  have hs := canP_state g fuel path i q s
  rw [h] at hs
  cases hp : canP g fuel path i q s with
  | none => rw [hp] at hs; simp at hs
  | some tl =>
    obtain ⟨t', l⟩ := tl
    rw [hp] at hs; simp only [Option.map_some, Option.some.injEq] at hs
    subst hs
    exact ⟨l, rfl, (canP_witness g fuel path i q s t' l hp hc).2⟩

/-- **WITNESS from the whole bag.** When the walk says `q` of `i` can be had,
its legs, executed from the character's real bag with no gate yet opened and
no capacity spent, succeed and deliver at least `q` of `i`. -/
theorem feasible_witness (g : Graph) (i q : Nat) (h : feasible g i q = true) :
    ∃ w', execAll g (plan g i q) ⟨St.init g, []⟩ = some w' ∧ q ≤ w'.st.bag i := by
  unfold feasible at h
  obtain ⟨t, ht⟩ := Option.isSome_iff_exists.mp h
  obtain ⟨l, hl, hw⟩ := witness g (g.n + 1) [] i q (St.init g) t ht (fun _ _ _ _ => Nat.zero_le _)
  obtain ⟨w', hx, hcov⟩ := hw ⟨St.init g, []⟩ (fun _ => 0) (fun _ _ => 0)
    ⟨fun j => by simp, fun j k => by simp [St.init]⟩
  refine ⟨w', by simpa [plan, hl] using hx, ?_⟩
  have := hcov.1 i
  simp only [e, if_true] at this
  omega

/-! ### The step is the first leg -/

theorem canP_present (g : Graph) (fuel : Nat) (P : List Nat) (j m : Nat) (s t : St) (l : List Step)
    (h : canP g fuel P j m s = some (t, l)) (hm : m ≤ s.bag j) : t = s.reserve j m ∧ l = [] := by
  cases fuel with
  | zero => simp [canP] at h
  | succ fuel =>
    simp only [canP, hm, if_true, Option.some.injEq, Prod.mk.injEq] at h
    exact ⟨h.1.symm, h.2.symm⟩

theorem useRouteP_shape (vP : Nat → Nat → St → Option (St × List Step)) (i k : Nat) (r : Route) (d : Nat)
    (s s' : St) (l1 : List Step) (h : useRouteP vP i k r d s = some (s', l1)) :
    ∃ lf, feedP vP r.inputs (runs (take s i k r d) r.yieldPer) (s.use i k (take s i k r d)) = some (s', lf) ∧
      l1 = r.gates.map (fun gt => Step.openGate i k gt) ++ lf ++
        [Step.act i k (take s i k r d) (runs (take s i k r d) r.yieldPer)] := by
  unfold useRouteP at h
  split at h
  · simp at h
  · cases hf : feedP vP r.inputs (runs (take s i k r d) r.yieldPer) (s.use i k (take s i k r d)) with
    | none => simp [hf] at h
    | some tl =>
      obtain ⟨t, lf⟩ := tl
      simp only [hf, Option.some.injEq, Prod.mk.injEq] at h
      obtain ⟨rfl, rfl⟩ := h
      exact ⟨lf, rfl, rfl⟩

theorem fillP_head (v : Nat → Nat → St → Option St) (vP : Nat → Nat → St → Option (St × List Step))
    (hv : ∀ j m s, (vP j m s).map Prod.fst = v j m s) (i d : Nat) (s : St) (hd : 0 < d) :
    ∀ (rs : List Route) (k k0 : Nat) (r : Route) (c : Nat) (t : St) (l : List Step),
      firstTake v i d s rs k = some (k0, r, c) → fillP vP i rs k d s = some (t, l) →
        ∃ s' l1 rest, useRouteP vP i k0 r d s = some (s', l1) ∧ l = l1 ++ rest := by
  have hd0 : ¬ d = 0 := by omega
  intro rs
  induction rs with
  | nil => intro k k0 r c t l h; simp [firstTake] at h
  | cons r0 rs ih =>
    intro k k0 r c t l hft hf
    have hu := useRouteP_state v vP hv i k r0 d s
    simp only [fillP, hd0, if_false] at hf
    by_cases hs : (useRoute v i k r0 d s).isSome = true
    · simp only [firstTake, hs, if_true, Option.some.injEq, Prod.mk.injEq] at hft
      obtain ⟨hk, hr0, _⟩ := hft
      subst hk hr0
      cases hup : useRouteP vP i k r0 d s with
      | none => rw [hup] at hu; simp only [Option.map_none] at hu; rw [← hu] at hs; simp at hs
      | some sl =>
        obtain ⟨s', l1⟩ := sl
        rw [hup] at hf
        simp only at hf
        cases hr : fillP vP i rs (k + 1) (d - take s i k r0 d) s' with
        | none => simp [hr] at hf
        | some tl =>
          simp only [hr, Option.some.injEq, Prod.mk.injEq] at hf
          exact ⟨s', l1, tl.2, rfl, hf.2.symm⟩
    · simp only [firstTake, hs, Bool.false_eq_true, if_false] at hft
      cases hup : useRouteP vP i k r0 d s with
      | some sl =>
        rw [hup] at hu; simp only [Option.map_some] at hu; rw [← hu] at hs; simp at hs
      | none =>
        rw [hup] at hf
        exact ih (k + 1) k0 r c t l hft hf

theorem descend_head (g : Graph) (fuel : Nat) (P : List Nat) (i k c : Nat)
    (ih : ∀ j m (s' : St) a, step g fuel P j m s' = some a →
      ∃ t l, canP g fuel P j m s' = some (t, l) ∧ l.head? = some a) :
    ∀ (ps : List (Nat × Nat)) (n : Nat) (s t : St) (lf : List Step) (a : Step),
      descend (step g fuel P) i k c ps n s = some a → feedP (canP g fuel P) ps n s = some (t, lf) →
        (lf ++ [Step.act i k c n]).head? = some a := by
  intro ps
  induction ps with
  | nil =>
    intro n s t lf a hd hf
    simp only [descend, Option.some.injEq] at hd
    simp only [feedP, Option.some.injEq, Prod.mk.injEq] at hf
    rw [← hf.2, ← hd]; rfl
  | cons p ps ihp =>
    intro n s t lf a hd hf
    simp only [feedP] at hf
    cases h1 : canP g fuel P p.1 (n * p.2) s with
    | none => simp [h1] at hf
    | some sl =>
      obtain ⟨s1, l1⟩ := sl
      simp only [h1] at hf
      cases h2 : feedP (canP g fuel P) ps n s1 with
      | none => simp [h2] at hf
      | some tl =>
        obtain ⟨t2, l2⟩ := tl
        simp only [h2, Option.some.injEq, Prod.mk.injEq] at hf
        rw [← hf.2]
        by_cases hm : n * p.2 ≤ s.bag p.1
        · obtain ⟨hs1, hl1⟩ := canP_present g fuel P _ _ _ _ _ h1 hm
          simp only [descend, hm, if_true] at hd
          rw [hl1, List.nil_append]
          rw [hs1] at h2
          exact ihp n _ _ _ a hd h2
        · simp only [descend, hm, if_false] at hd
          obtain ⟨t', l', hc', hhead⟩ := ih _ _ _ _ hd
          rw [h1] at hc'
          simp only [Option.some.injEq, Prod.mk.injEq] at hc'
          rw [hc'.2]
          cases l' with
          | nil => simp at hhead
          | cons b l' => simpa using hhead

/-- **The step is the first leg.** Whatever the walk's next step is — a gate
to open or a route to run — it is the first of the legs that witness its yes. -/
theorem step_is_first_leg (g : Graph) :
    ∀ fuel path i q (s : St) a, step g fuel path i q s = some a →
      ∃ t l, canP g fuel path i q s = some (t, l) ∧ l.head? = some a := by
  intro fuel
  induction fuel with
  | zero => intro path i q s a h; simp [step] at h
  | succ fuel ih =>
    intro path i q s a h
    have hsome := step_sound g (fuel + 1) path i q s a h
    obtain ⟨hq, k, r, c, hft, hcase⟩ := step_succ_route g fuel path i q s a h
    have hstate := canP_state g (fuel + 1) path i q s
    cases hp : canP g (fuel + 1) path i q s with
    | none => rw [hp] at hstate; simp only [Option.map_none] at hstate; rw [← hstate] at hsome; simp at hsome
    | some tl =>
      obtain ⟨t, l⟩ := tl
      refine ⟨t, l, rfl, ?_⟩
      have hpc : path.contains i = false := by
        cases hc : path.contains i with
        | false => rfl
        | true =>
          have hmem : i ∈ path := by simpa using hc
          simp [canP, hq, hmem] at hp
      simp only [canP, hq, hpc, if_false, Bool.false_eq_true] at hp
      obtain ⟨s', l1, rest, hu, hl⟩ := fillP_head _ _ (fun j m s => canP_state g fuel (i :: path) j m s)
        i _ _ (by omega) _ _ _ _ _ _ _ hft hp
      obtain ⟨_, _, hcv, _, _⟩ := firstTake_spec _ _ _ _ _ _ _ _ _ hft
      obtain ⟨lf, hfeed, hl1⟩ := useRouteP_shape _ _ _ _ _ _ _ _ hu
      rw [hl, hl1]
      rcases hcase with ⟨gt, gs, hg, ha⟩ | ⟨hg, hd⟩
      · rw [hg, ha]; rfl
      · rw [hg, ← hcv]
        rw [← hcv] at hfeed
        simpa using descend_head g fuel (i :: path) i k c (fun j m s' a h => ih _ j m s' a h)
          r.inputs _ _ _ _ a hd hfeed

/-! ### Examples -/

private def none0 : Nat → Nat := fun _ => 0

-- The copper ring: gather 20 ore, craft 2 bar runs (3 bars), craft 3 rings.
private def ring : Graph :=
  ⟨3, none0, fun i =>
    if i = 0 then [⟨10, 1, 1000, [(1, 1)], []⟩]
    else if i = 1 then [⟨11, 2, 1000, [(2, 10)], []⟩]
    else if i = 2 then [⟨12, 1, 1000, [], []⟩] else []⟩
example : plan ring 0 3 = [.act 2 0 20 20, .act 1 0 3 2, .act 0 0 3 3] := by decide
example : ((execAll ring (plan ring 0 3) ⟨St.init ring, []⟩).map (fun w => w.st.bag 0)) = some 3 := by
  decide

-- A gated bar route: the gate leg comes first, and the plan runs once it is recorded.
private def gatedRing : Graph :=
  ⟨3, none0, fun i =>
    if i = 0 then [⟨10, 1, 1000, [(1, 1)], []⟩]
    else if i = 1 then [⟨11, 2, 1000, [(2, 10)], [7]⟩]
    else if i = 2 then [⟨12, 1, 1000, [], []⟩] else []⟩
example : plan gatedRing 0 1 = [.openGate 1 0 7, .act 2 0 10 10, .act 1 0 1 1, .act 0 0 1 1] := by decide
example : ((execAll gatedRing (plan gatedRing 0 1) ⟨St.init gatedRing, []⟩).map (fun w => w.st.bag 0)) =
    some 1 := by decide
-- Skipping the gate leg, the bar cannot be crafted.
example : execAll gatedRing [.act 2 0 10 10, .act 1 0 1 1] ⟨St.init gatedRing, []⟩ = none := by decide

end Formal.DecomposeWitness
