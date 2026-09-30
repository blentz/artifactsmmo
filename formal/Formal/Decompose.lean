-- formal/Formal/Decompose.lean
-- @concept: core, planner @property: validity, sufficiency, safety, termination
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

Semantics: the DEFICIT, filled GREEDILY across routes, JOINTLY (Phase 2d-L1).
`q` of `i` can be had when the bag holds `q`, or when the routes, in priority
order, fill the deficit `q - bag i`: each usable route takes as much of what is
left as its remaining capacity allows. A WITHDRAW route's capacity is the bank's
stock, so a banked copy is withdrawn and mixed with production (21 banked, 33
needed ⇒ withdraw 21, gather 12), and a licensed RECYCLE covers what it can while
a gather covers the rest. A CRAFT route's inputs ARE its recipe.

JOINT: the walk threads a state — what is left in the bag, and how much of each
route's capacity is spent — through every question it asks. Asking for `q` of
`i` reserves what the bag holds; a route spends its capacity and asks for its
inputs in order, each from the state the previous one left; a route that fails
leaves the state as it was. So sibling inputs that share a material cannot both
count the same stock. The walk it replaces asked each input against the whole
bag, and said yes to "2 A and a B made of 2 A" from a bag of 2 A with no other
route to A (then declined after crafting the B).

GREEDY, not exhaustive: a route that is usable is taken, even when a later
sibling then goes short of a material it spent. A yes is therefore sound, but
holding more can turn a yes into a no (an extra item makes a route usable that
spends what a sibling needed). The walk is not monotone in holdings; the choice
was decided on 2026-09-30 (exact answers need a search exponential in fan-out).

Items, routes and gates are naturals (the caller interns them); a route's `tag`
names the concrete action that serves it and is opaque to the walk. Lean core
only.
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

/-- What the walk has left: the bag, and the capacity spent on route `k` of
item `i` (`used i k`). -/
structure St where
  bag : Nat → Nat
  used : Nat → Nat → Nat

/-- The state a question starts from: the whole bag, no capacity spent. -/
def St.init (g : Graph) : St := ⟨g.onHand, fun _ _ => 0⟩

/-- Take `q` of `i` out of the bag. -/
def St.reserve (s : St) (i q : Nat) : St :=
  { s with bag := fun j => if j = i then s.bag j - q else s.bag j }

/-- Spend `c` of the capacity of route `k` of `i`. -/
def St.use (s : St) (i k c : Nat) : St :=
  { s with used := fun j l => if j = i ∧ l = k then s.used j l + c else s.used j l }

/-- Applications of a route that deliver `d` units at `y` per application
(Python `-(-d // max(1, y))`); a yield of 0 in the data reads as 1. -/
def runs (d y : Nat) : Nat := (d + max 1 y - 1) / max 1 y

/-- What route `k` of `i` takes of a remaining deficit `d`: all of it, or the
capacity it has left. -/
def take (s : St) (i k : Nat) (r : Route) (d : Nat) : Nat := min (r.cap - s.used i k) d

/-- A route's inputs, asked in order, each from the state the previous left. -/
def feed (v : Nat → Nat → St → Option St) : List (Nat × Nat) → Nat → St → Option St
  | [], _, s => some s
  | p :: ps, n, s =>
    match v p.1 (n * p.2) s with
    | none => none
    | some s' => feed v ps n s'

/-- Route `k` of `i` delivers its share of a deficit `d`: the state after its
capacity and inputs are spent, or none when it takes nothing or an input fails. -/
def useRoute (v : Nat → Nat → St → Option St) (i k : Nat) (r : Route) (d : Nat) (s : St) :
    Option St :=
  if take s i k r d = 0 then none
  else feed v r.inputs (runs (take s i k r d) r.yieldPer) (s.use i k (take s i k r d))

/-- Greedy fill: the routes of `i` (the first has index `k`), in order, cover
`d`; each contributing route takes its share, a failing one changes nothing. -/
def fill (v : Nat → Nat → St → Option St) (i : Nat) : List Route → Nat → Nat → St → Option St
  | [], _, d, s => if d = 0 then some s else none
  | r :: rs, k, d, s =>
    if d = 0 then some s
    else
      match useRoute v i k r d s with
      | some s' => fill v i rs (k + 1) (d - take s i k r d) s'
      | none => fill v i rs (k + 1) d s

/-- The walk's feasibility (`decompose_core._can`), with fuel: the state left
once `q` of `i` is had, or none. -/
def can (g : Graph) : Nat → List Nat → Nat → Nat → St → Option St
  | 0, _, _, _, _ => none
  | fuel + 1, path, i, q, s =>
    if q ≤ s.bag i then some (s.reserve i q)
    else if path.contains i then none
    else fill (can g fuel (i :: path)) i (g.routes i) 0 (q - s.bag i) (s.reserve i (s.bag i))

/-- The first contributing route, with its index and amount. -/
def firstTake (v : Nat → Nat → St → Option St) (i d : Nat) (s : St) :
    List Route → Nat → Option (Nat × Route × Nat)
  | [], _ => none
  | r :: rs, k =>
    if (useRoute v i k r d s).isSome then some (k, r, take s i k r d)
    else firstTake v i d s rs (k + 1)

/-- The next step toward the goal. -/
inductive Step where
  /-- Run route `route` of `item` `runs` times, delivering `amount`. -/
  | act (item route amount runs : Nat)
  /-- Open `gate`, which blocks route `route` of `item` (a sub-task). -/
  | openGate (item route gate : Nat)
  deriving DecidableEq, Repr

/-- The first leaf under a ready route's inputs: the route itself when every
input is in the bag (reserving each), else the step toward the first input the
bag lacks, asked from the state the inputs before it left. -/
def descend (w : Nat → Nat → St → Option Step) (i k c : Nat) :
    List (Nat × Nat) → Nat → St → Option Step
  | [], n, _ => some (.act i k c n)
  | p :: ps, n, s =>
    if n * p.2 ≤ s.bag p.1 then descend w i k c ps n (s.reserve p.1 (n * p.2))
    else w p.1 (n * p.2) s

/-- The first leaf of the supply the walk finds (`decompose_core._step`). -/
def step (g : Graph) : Nat → List Nat → Nat → Nat → St → Option Step
  | 0, _, _, _, _ => none
  | fuel + 1, path, i, q, s =>
    if q ≤ s.bag i then none
    else if path.contains i then none
    else
      let s0 := s.reserve i (s.bag i)
      let d := q - s.bag i
      if (fill (can g fuel (i :: path)) i (g.routes i) 0 d s0).isNone then none
      else
        match firstTake (can g fuel (i :: path)) i d s0 (g.routes i) 0 with
        | none => none
        | some (k, r, c) =>
          match r.gates with
          | gt :: _ => some (.openGate i k gt)
          | [] => descend (step g fuel (i :: path)) i k c r.inputs (runs c r.yieldPer) (s0.use i k c)

/-- `decompose_core.can_obtain`: fuel `n + 1`, empty path, the whole bag. -/
def feasible (g : Graph) (i q : Nat) : Bool := (can g (g.n + 1) [] i q (St.init g)).isSome

/-- `decompose_core.next_step`: the entry point, fuel `n + 1`, empty path. -/
def nextStep (g : Graph) (i q : Nat) : Option Step := step g (g.n + 1) [] i q (St.init g)

/-! ### Runs, take, reserve -/

theorem runs_mono (d d' y : Nat) (h : d' ≤ d) : runs d' y ≤ runs d y :=
  Nat.div_le_div_right (by omega)

theorem take_le_cap (s : St) (i k : Nat) (r : Route) (d : Nat) : take s i k r d ≤ r.cap := by
  unfold take; omega

theorem reserve_bag_le (s : St) (i q j : Nat) : (s.reserve i q).bag j ≤ s.bag j := by
  simp only [St.reserve]; split <;> omega

@[simp] theorem use_bag (s : St) (i k c : Nat) : (s.use i k c).bag = s.bag := rfl

/-! ### The bag only shrinks -/

/-- A verdict that never grows the bag. -/
def Shrinks (v : Nat → Nat → St → Option St) : Prop :=
  ∀ j m s t, v j m s = some t → ∀ x, t.bag x ≤ s.bag x

theorem feed_shrinks (v : Nat → Nat → St → Option St) (hv : Shrinks v) :
    ∀ (ps : List (Nat × Nat)) (n : Nat) (s t : St), feed v ps n s = some t → ∀ x, t.bag x ≤ s.bag x := by
  intro ps
  induction ps with
  | nil => intro n s t h x; simp only [feed, Option.some.injEq] at h; subst h; exact Nat.le_refl _
  | cons p ps ih =>
    intro n s t h x
    simp only [feed] at h
    cases hvp : v p.1 (n * p.2) s with
    | none => simp [hvp] at h
    | some s' =>
      simp only [hvp] at h
      exact Nat.le_trans (ih n s' t h x) (hv _ _ _ _ hvp x)

theorem useRoute_shrinks (v : Nat → Nat → St → Option St) (hv : Shrinks v) (i k : Nat) (r : Route)
    (d : Nat) (s t : St) (h : useRoute v i k r d s = some t) : ∀ x, t.bag x ≤ s.bag x := by
  intro x
  unfold useRoute at h
  split at h
  · simp at h
  · have := feed_shrinks v hv _ _ _ _ h x
    simpa using this

theorem fill_shrinks (v : Nat → Nat → St → Option St) (hv : Shrinks v) (i : Nat) :
    ∀ (rs : List Route) (k d : Nat) (s t : St), fill v i rs k d s = some t → ∀ x, t.bag x ≤ s.bag x := by
  intro rs
  induction rs with
  | nil =>
    intro k d s t h x
    simp only [fill] at h
    split at h
    · simp only [Option.some.injEq] at h; subst h; exact Nat.le_refl _
    · simp at h
  | cons r rs ih =>
    intro k d s t h x
    simp only [fill] at h
    split at h
    · simp only [Option.some.injEq] at h; subst h; exact Nat.le_refl _
    · cases hu : useRoute v i k r d s with
      | none => simp only [hu] at h; exact ih _ _ _ _ h x
      | some s' =>
        simp only [hu] at h
        exact Nat.le_trans (ih _ _ _ _ h x) (useRoute_shrinks v hv i k r d s s' hu x)

theorem can_shrinks (g : Graph) : ∀ fuel path, Shrinks (can g fuel path) := by
  intro fuel
  induction fuel with
  | zero => intro path j m s t h; simp [can] at h
  | succ fuel ih =>
    intro path j m s t h x
    simp only [can] at h
    split at h
    · simp only [Option.some.injEq] at h; subst h; exact reserve_bag_le _ _ _ _
    · split at h
      · simp at h
      · exact Nat.le_trans (fill_shrinks _ (ih _) _ _ _ _ _ _ h x) (reserve_bag_le _ _ _ _)

/-- A bag-held need is answered by reserving it. -/
theorem can_present (g : Graph) (fuel : Nat) (path : List Nat) (j m : Nat) (s t : St)
    (h : can g fuel path j m s = some t) (hm : m ≤ s.bag j) : t = s.reserve j m := by
  cases fuel with
  | zero => simp [can] at h
  | succ fuel => simp only [can, hm, if_true, Option.some.injEq] at h; exact h.symm

/-! ### fill and firstTake -/

/-- A fill of a positive deficit has a first contributor. -/
theorem firstTake_of_fill (v : Nat → Nat → St → Option St) (i : Nat) :
    ∀ (rs : List Route) (k d : Nat) (s t : St), 0 < d → fill v i rs k d s = some t →
      (firstTake v i d s rs k).isSome = true := by
  intro rs
  induction rs with
  | nil => intro k d s t hd h; simp only [fill] at h; split at h <;> simp_all
  | cons r rs ih =>
    intro k d s t hd h
    have hd0 : ¬ d = 0 := by omega
    simp only [fill, hd0, if_false] at h
    cases hu : useRoute v i k r d s with
    | some s' => simp [firstTake, hu]
    | none =>
      simp only [hu] at h
      simp only [firstTake, hu, Option.isSome_none, Bool.false_eq_true, if_false]
      exact ih _ _ _ _ hd h

/-- The first contributor is a route of the list, taking a positive amount
within the capacity it has left, and usable for that amount. -/
theorem firstTake_spec (v : Nat → Nat → St → Option St) (i d : Nat) (s : St) :
    ∀ (rs : List Route) (k j : Nat) (r : Route) (c : Nat),
      firstTake v i d s rs k = some (j, r, c) →
        rs[j - k]? = some r ∧ k ≤ j ∧ c = take s i j r d ∧ 0 < c ∧
          (useRoute v i j r d s).isSome = true := by
  intro rs
  induction rs with
  | nil => intro k j r c h; simp [firstTake] at h
  | cons r0 rs ih =>
    intro k j r c h
    by_cases hu : (useRoute v i k r0 d s).isSome = true
    · simp only [firstTake, hu, if_true, Option.some.injEq, Prod.mk.injEq] at h
      obtain ⟨rfl, rfl, rfl⟩ := h
      refine ⟨by simp, Nat.le_refl _, rfl, ?_, hu⟩
      unfold useRoute at hu
      split at hu
      · simp at hu
      · omega
    · simp only [firstTake, hu, Bool.false_eq_true, if_false] at h
      obtain ⟨hget, hle, hc, hpos, husable⟩ := ih (k + 1) j r c h
      refine ⟨?_, by omega, hc, hpos, husable⟩
      have : j - k = (j - (k + 1)) + 1 := by omega
      rw [this]
      simpa using hget

/-- A usable route is its inputs fed from the state with its share spent. -/
theorem useRoute_feed (v : Nat → Nat → St → Option St) (i k : Nat) (r : Route) (d : Nat) (s : St)
    (h : (useRoute v i k r d s).isSome = true) :
    ∃ t, feed v r.inputs (runs (take s i k r d) r.yieldPer) (s.use i k (take s i k r d)) = some t := by
  unfold useRoute at h
  split at h
  · simp at h
  · exact Option.isSome_iff_exists.mp h

/-! ### COMPLETE and SOUND -/

/-- Descending into a ready route's inputs finds a step whenever the inputs,
fed in order, can all be had. -/
theorem descend_complete (g : Graph) (fuel : Nat) (P : List Nat) (i k c : Nat)
    (hw : ∀ j m s' t, can g fuel P j m s' = some t → ¬ m ≤ s'.bag j →
      (step g fuel P j m s').isSome = true) :
    ∀ (ps : List (Nat × Nat)) (n : Nat) (s t : St), feed (can g fuel P) ps n s = some t →
      (descend (step g fuel P) i k c ps n s).isSome = true := by
  intro ps
  induction ps with
  | nil => intro n s t _; simp [descend]
  | cons p ps ih =>
    intro n s t h
    simp only [feed] at h
    cases hvp : can g fuel P p.1 (n * p.2) s with
    | none => simp [hvp] at h
    | some s' =>
      simp only [hvp] at h
      by_cases hm : n * p.2 ≤ s.bag p.1
      · simp only [descend, hm, if_true]
        rw [← can_present g fuel P _ _ _ _ hvp hm]
        exact ih _ _ _ h
      · simp only [descend, hm, if_false]
        exact hw _ _ _ _ hvp hm

/-- **COMPLETE.** A feasible goal the bag does not hold always has a next step:
decomposition never declines what the walk judges feasible. -/
theorem step_complete (g : Graph) :
    ∀ fuel path i q (s t : St), can g fuel path i q s = some t → ¬ q ≤ s.bag i →
      (step g fuel path i q s).isSome = true := by
  intro fuel
  induction fuel with
  | zero => intro path i q s t h; simp [can] at h
  | succ fuel ih =>
    intro path i q s t hc hq
    have hpc : path.contains i = false := by
      cases hp : path.contains i with
      | false => rfl
      | true =>
        have hmem : i ∈ path := by simpa using hp
        simp [can, hq, hmem] at hc
    simp only [can, hq, hpc, if_false, Bool.false_eq_true] at hc
    have hsome := firstTake_of_fill _ _ _ _ _ _ _ (by omega) hc
    simp only [step, hq, hpc, if_false, hc, Option.isNone_some, Bool.false_eq_true]
    cases hft : firstTake (can g fuel (i :: path)) i (q - s.bag i) (s.reserve i (s.bag i)) (g.routes i) 0 with
    | none => simp [hft] at hsome
    | some krc =>
      obtain ⟨k, r, c⟩ := krc
      obtain ⟨_, _, hcv, _, hu⟩ := firstTake_spec _ _ _ _ _ _ _ _ _ hft
      simp only
      cases hg : r.gates with
      | cons gt rest => simp
      | nil =>
        simp only
        obtain ⟨t', hfeed⟩ := useRoute_feed _ _ _ _ _ _ hu
        rw [← hcv] at hfeed
        exact descend_complete g fuel (i :: path) i k c (fun j m s' t h hm => ih _ _ _ _ _ h hm)
          _ _ _ _ hfeed

/-- **SOUND.** A step is only ever emitted for a feasible goal. -/
theorem step_sound (g : Graph) :
    ∀ fuel path i q (s : St) x, step g fuel path i q s = some x →
      (can g fuel path i q s).isSome = true := by
  intro fuel
  cases fuel with
  | zero => intro path i q s x h; simp [step] at h
  | succ fuel =>
    intro path i q s x h
    by_cases hq : q ≤ s.bag i
    · simp [step, hq] at h
    by_cases hp : path.contains i = true
    · have hmem : i ∈ path := by simpa using hp
      simp [step, hq, hmem] at h
    have hpf : path.contains i = false := by simpa using hp
    simp only [step, hq, hpf, if_false, Bool.false_eq_true] at h
    simp only [can, hq, hpf, if_false, Bool.false_eq_true]
    split at h
    · simp at h
    · rename_i hn
      cases hf : fill (can g fuel (i :: path)) i (g.routes i) 0 (q - s.bag i) (s.reserve i (s.bag i)) with
      | none => simp [hf] at hn
      | some _ => rfl

/-- **VALIDITY.** There is no next step exactly when the bag holds the goal or
the walk judges it infeasible. -/
theorem step_none_iff (g : Graph) (fuel : Nat) (path : List Nat) (i q : Nat) (s : St) :
    step g fuel path i q s = none ↔ (q ≤ s.bag i ∨ can g fuel path i q s = none) := by
  constructor
  · intro h
    by_cases hq : q ≤ s.bag i
    · exact .inl hq
    · right
      cases hc : can g fuel path i q s with
      | none => rfl
      | some t =>
        have := step_complete g fuel path i q s t hc hq
        rw [h] at this; simp at this
  · rintro (hq | hc)
    · cases fuel with
      | zero => rfl
      | succ fuel => simp [step, hq]
    · cases hs : step g fuel path i q s with
      | none => rfl
      | some x =>
        have := step_sound g fuel path i q s x hs
        rw [hc] at this; simp at this

/-! ### ORDERING and GATES -/

/-- The shape every step lemma walks: past the bag, the path guard and the fill,
a step is the first contributor's gate, or the descent into its inputs from the
state with its share spent. -/
theorem step_succ_route (g : Graph) (fuel : Nat) (path : List Nat) (i q : Nat) (s : St) (x : Step)
    (h : step g (fuel + 1) path i q s = some x) :
    ¬ q ≤ s.bag i ∧ ∃ k r c,
      firstTake (can g fuel (i :: path)) i (q - s.bag i) (s.reserve i (s.bag i)) (g.routes i) 0 =
        some (k, r, c) ∧
      ((∃ gt rest, r.gates = gt :: rest ∧ x = .openGate i k gt) ∨
       (r.gates = [] ∧ descend (step g fuel (i :: path)) i k c r.inputs (runs c r.yieldPer)
          ((s.reserve i (s.bag i)).use i k c) = some x)) := by
  by_cases hq : q ≤ s.bag i
  · simp [step, hq] at h
  refine ⟨hq, ?_⟩
  by_cases hp : path.contains i = true
  · have hmem : i ∈ path := by simpa using hp
    simp [step, hq, hmem] at h
  have hpf : path.contains i = false := by simpa using hp
  simp only [step, hq, hpf, if_false, Bool.false_eq_true] at h
  split at h
  · simp at h
  · cases hft : firstTake (can g fuel (i :: path)) i (q - s.bag i) (s.reserve i (s.bag i)) (g.routes i) 0 with
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
        exact .inr ⟨rfl, h⟩

/-- A descent ends in the route itself, with every input in the bag it started
from, or in a step asked from a state whose bag is no fuller. -/
theorem descend_cases (w : Nat → Nat → St → Option Step) (i k c : Nat) :
    ∀ (ps : List (Nat × Nat)) (n : Nat) (s : St) (x : Step), descend w i k c ps n s = some x →
      (x = .act i k c n ∧ ∀ p ∈ ps, n * p.2 ≤ s.bag p.1) ∨
      (∃ j m s', w j m s' = some x ∧ ∀ y, s'.bag y ≤ s.bag y) := by
  intro ps
  induction ps with
  | nil =>
    intro n s x h
    simp only [descend, Option.some.injEq] at h
    exact .inl ⟨h.symm, by simp⟩
  | cons p ps ih =>
    intro n s x h
    by_cases hm : n * p.2 ≤ s.bag p.1
    · simp only [descend, hm, if_true] at h
      rcases ih n _ x h with ⟨hx, hall⟩ | ⟨j, m, s', hw, hle⟩
      · refine .inl ⟨hx, ?_⟩
        intro p' hp'
        rcases List.mem_cons.mp hp' with rfl | hp'
        · exact hm
        · exact Nat.le_trans (hall p' hp') (reserve_bag_le _ _ _ _)
      · exact .inr ⟨j, m, s', hw, fun y => Nat.le_trans (hle y) (reserve_bag_le _ _ _ _)⟩
    · simp only [descend, hm, if_false] at h
      exact .inr ⟨_, _, s, h, fun _ => Nat.le_refl _⟩

/-- **ORDERING.** An action is emitted for a READY route (no blocking gate), for
a positive amount within its capacity (a WITHDRAW never takes more than the bank
holds, a RECYCLE never more than its licence), `runs` is `⌈amount / yield⌉`,
and every input the runs consume is already in the bag. -/
theorem step_act_spec (g : Graph) :
    ∀ fuel path i q (s : St) j k c rn, step g fuel path i q s = some (.act j k c rn) →
      ∃ r, (g.routes j)[k]? = some r ∧ r.gates = [] ∧ 1 ≤ c ∧ c ≤ r.cap ∧
        rn = runs c r.yieldPer ∧ ∀ p ∈ r.inputs, rn * p.2 ≤ s.bag p.1 := by
  intro fuel
  induction fuel with
  | zero => intro path i q s j k c rn h; simp [step] at h
  | succ fuel ih =>
    intro path i q s j k c rn h
    obtain ⟨_, k0, r, c0, hft, hcase⟩ := step_succ_route g fuel path i q s _ h
    obtain ⟨hget, _, hc, hpos, _⟩ := firstTake_spec _ _ _ _ _ _ _ _ _ hft
    rcases hcase with ⟨_, _, _, hx⟩ | ⟨hg, hd⟩
    · simp at hx
    · rcases descend_cases _ _ _ _ _ _ _ _ hd with ⟨hx, hall⟩ | ⟨j', m, s', hw, hle⟩
      · simp only [Step.act.injEq] at hx
        obtain ⟨rfl, rfl, rfl, rfl⟩ := hx
        refine ⟨r, by simpa using hget, hg, hpos, hc ▸ take_le_cap _ _ _ _ _, rfl, ?_⟩
        intro p hp
        exact Nat.le_trans (by simpa using hall p hp) (reserve_bag_le _ _ _ _)
      · obtain ⟨r', hr', hg', hpos', hcap', hrn', hin'⟩ := ih _ _ _ _ _ _ _ _ hw
        refine ⟨r', hr', hg', hpos', hcap', hrn', ?_⟩
        intro p hp
        exact Nat.le_trans (hin' p hp)
          (Nat.le_trans (by simpa using hle p.1) (reserve_bag_le _ _ _ _))

/-- **GATES.** "Open a gate" is emitted only for a route that gate blocks (its
first blocking gate). -/
theorem step_open_spec (g : Graph) :
    ∀ fuel path i q (s : St) j k gt, step g fuel path i q s = some (.openGate j k gt) →
      ∃ r, (g.routes j)[k]? = some r ∧ r.gates.head? = some gt := by
  intro fuel
  induction fuel with
  | zero => intro path i q s j k gt h; simp [step] at h
  | succ fuel ih =>
    intro path i q s j k gt h
    obtain ⟨_, k0, r, c0, hft, hcase⟩ := step_succ_route g fuel path i q s _ h
    obtain ⟨hget, _, _, _, _⟩ := firstTake_spec _ _ _ _ _ _ _ _ _ hft
    rcases hcase with ⟨g0, rest, hg, hx⟩ | ⟨_, hd⟩
    · simp only [Step.openGate.injEq] at hx
      obtain ⟨rfl, rfl, rfl⟩ := hx
      exact ⟨r, by simpa using hget, by simp [hg]⟩
    · rcases descend_cases _ _ _ _ _ _ _ _ hd with ⟨hx, _⟩ | ⟨j', m, s', hw, _⟩
      · simp at hx
      · exact ih _ _ _ _ _ _ _ hw

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

theorem feed_congr (v w : Nat → Nat → St → Option St) :
    ∀ (ps : List (Nat × Nat)), (∀ p ∈ ps, ∀ m s, v p.1 m s = w p.1 m s) →
      ∀ n s, feed v ps n s = feed w ps n s := by
  intro ps
  induction ps with
  | nil => intro _ _ _; rfl
  | cons p ps ih =>
    intro h n s
    simp only [feed, h p List.mem_cons_self]
    cases w p.1 (n * p.2) s with
    | none => rfl
    | some s' => exact ih (fun x hx => h x (List.mem_cons_of_mem _ hx)) n s'

theorem useRoute_congr (v w : Nat → Nat → St → Option St) (i k : Nat) (r : Route)
    (h : ∀ p ∈ r.inputs, ∀ m s, v p.1 m s = w p.1 m s) (d : Nat) (s : St) :
    useRoute v i k r d s = useRoute w i k r d s := by
  unfold useRoute
  split
  · rfl
  · exact feed_congr v w _ h _ _

theorem fill_congr (v w : Nat → Nat → St → Option St) (i : Nat) :
    ∀ (rs : List Route), (∀ r ∈ rs, ∀ p ∈ r.inputs, ∀ m s, v p.1 m s = w p.1 m s) →
      ∀ k d s, fill v i rs k d s = fill w i rs k d s := by
  intro rs
  induction rs with
  | nil => intro _ _ _ _; rfl
  | cons r rs ih =>
    intro h k d s
    have ht := ih (fun x hx => h x (List.mem_cons_of_mem _ hx))
    simp only [fill, useRoute_congr v w i k r (h r List.mem_cons_self) d s]
    split
    · rfl
    · cases useRoute w i k r d s with
      | none => exact ht _ _ _
      | some s' => exact ht _ _ _

theorem firstTake_congr (v w : Nat → Nat → St → Option St) (i d : Nat) (s : St) :
    ∀ (rs : List Route) (k : Nat), (∀ r ∈ rs, ∀ p ∈ r.inputs, ∀ m s, v p.1 m s = w p.1 m s) →
      firstTake v i d s rs k = firstTake w i d s rs k := by
  intro rs
  induction rs with
  | nil => intro _ _; rfl
  | cons r rs ih =>
    intro k h
    simp only [firstTake, useRoute_congr v w i k r (h r List.mem_cons_self) d s,
      ih (k + 1) (fun x hx => h x (List.mem_cons_of_mem _ hx))]

theorem descend_congr (v w : Nat → Nat → St → Option Step) (i k c : Nat) :
    ∀ (ps : List (Nat × Nat)), (∀ p ∈ ps, ∀ m s, v p.1 m s = w p.1 m s) →
      ∀ n s, descend v i k c ps n s = descend w i k c ps n s := by
  intro ps
  induction ps with
  | nil => intro _ _ _; rfl
  | cons p ps ih =>
    intro h n s
    simp only [descend, h p List.mem_cons_self _ s,
      ih (fun x hx => h x (List.mem_cons_of_mem _ hx))]

/-- **FUEL BOUND (feasibility).** For a closed graph, once the fuel exceeds the
number of items the path leaves out, one more unit changes nothing: `n + 1`
from the empty path is exactly the unbounded recursion Python runs. -/
theorem can_fuel_stable (g : Graph) (hc : Closed g) :
    ∀ fuel path i q (s : St), path.Nodup → (∀ x ∈ path, x < g.n) → i < g.n →
      g.n + 1 ≤ fuel + path.length → can g (fuel + 1) path i q s = can g fuel path i q s := by
  intro fuel
  induction fuel with
  | zero =>
    intro path i q s hnd hb _ hlen
    have := nodup_length_le g.n path hnd hb
    omega
  | succ fuel ih =>
    intro path i q s hnd hb hi hlen
    by_cases hin : i ∈ path
    · simp [can, hin]
    · have hstep : ∀ r ∈ g.routes i, ∀ p ∈ r.inputs, ∀ m s',
          can g (fuel + 1) (i :: path) p.1 m s' = can g fuel (i :: path) p.1 m s' := by
        intro r hr p hp m s'
        refine ih _ _ _ _ (List.nodup_cons.mpr ⟨hin, hnd⟩) ?_ (hc i hi r hr p hp) ?_
        · intro x hx
          rcases List.mem_cons.mp hx with rfl | hx
          · exact hi
          · exact hb x hx
        · simp only [List.length_cons]; omega
      have hf := fill_congr _ _ i (g.routes i) hstep
      rw [can.eq_2, can.eq_2, hf]

/-- **FUEL BOUND (next step).** The same bound for the step: the Lean walk at
`n + 1` fuel is the unbounded Python walk. -/
theorem step_fuel_stable (g : Graph) (hc : Closed g) :
    ∀ fuel path i q (s : St), path.Nodup → (∀ x ∈ path, x < g.n) → i < g.n →
      g.n + 1 ≤ fuel + path.length → step g (fuel + 1) path i q s = step g fuel path i q s := by
  intro fuel
  induction fuel with
  | zero =>
    intro path i q s hnd hb _ hlen
    have := nodup_length_le g.n path hnd hb
    omega
  | succ fuel ih =>
    intro path i q s hnd hb hi hlen
    by_cases hq : q ≤ s.bag i
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
    have hv : ∀ r ∈ g.routes i, ∀ p ∈ r.inputs, ∀ m s',
        can g (fuel + 1) (i :: path) p.1 m s' = can g fuel (i :: path) p.1 m s' :=
      fun r hr p hp m s' => can_fuel_stable g hc fuel (i :: path) p.1 m s' hnd' hb' (hc i hi r hr p hp) hlen'
    have hw : ∀ r ∈ g.routes i, ∀ p ∈ r.inputs, ∀ m s',
        step g (fuel + 1) (i :: path) p.1 m s' = step g fuel (i :: path) p.1 m s' :=
      fun r hr p hp m s' => ih (i :: path) p.1 m s' hnd' hb' (hc i hi r hr p hp) hlen'
    have hf := fill_congr _ _ i (g.routes i) hv 0 (q - s.bag i) (s.reserve i (s.bag i))
    have hft := firstTake_congr _ _ i (q - s.bag i) (s.reserve i (s.bag i)) (g.routes i) 0 hv
    have hpc : path.contains i = false := by simpa using hin
    simp only [step, hq, hpc, if_false, Bool.false_eq_true]
    rw [hf, hft]
    split
    · rfl
    · cases hfirst : firstTake (can g fuel (i :: path)) i (q - s.bag i) (s.reserve i (s.bag i)) (g.routes i) 0 with
      | none => rfl
      | some krc =>
        obtain ⟨k, r, c⟩ := krc
        obtain ⟨hget, _, _, _, _⟩ := firstTake_spec _ _ _ _ _ _ _ _ _ hfirst
        have hr : r ∈ g.routes i := List.mem_of_getElem? (by simpa using hget)
        simp only
        cases r.gates with
        | cons _ _ => rfl
        | nil =>
          simp only
          exact descend_congr _ _ i k c r.inputs (hw r hr) _ _

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
-- Infeasible (ore has no route) ⇒ none, and `feasible` agrees.
private def noOre : Graph :=
  ⟨3, none0, fun i => if i = 0 then [⟨10, 1, 1000, [(1, 1)], []⟩]
    else if i = 1 then [⟨11, 1, 1000, [(2, 10)], []⟩] else []⟩
example : nextStep noOre 0 1 = none ∧ feasible noOre 0 1 = false := by decide
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
example : feasible bankedGoal 0 5 = true := by decide

-- JOINT: 0 = X (2 A + 1 B), 1 = B (2 A), 2 = A (no route). Two A in the bag
-- cover the B or the X's own two, not both: infeasible. Four A cover both, and
-- the first leaf is the B.
private def shared (a : Nat) : Graph :=
  ⟨3, fun i => if i = 2 then a else 0, fun i =>
    if i = 0 then [⟨50, 1, 1000, [(2, 2), (1, 1)], []⟩]
    else if i = 1 then [⟨51, 1, 1000, [(2, 2)], []⟩] else []⟩
example : feasible (shared 2) 0 1 = false ∧ nextStep (shared 2) 0 1 = none := by decide
example : feasible (shared 4) 0 1 = true ∧ nextStep (shared 4) 0 1 = some (.act 1 0 1 1) := by decide
-- A bank's capacity is shared too: two siblings each want 2 of a material only
-- a bank of 3 holds.
private def sharedBank : Graph :=
  ⟨2, none0, fun i =>
    if i = 0 then [⟨60, 1, 1000, [(1, 2), (1, 2)], []⟩] else [⟨61, 1, 3, [], []⟩]⟩
example : feasible sharedBank 0 1 = false := by decide

-- NOT MONOTONE (the greedy contract): 0 = root (X + Y), 1 = X (route 1: M + Z;
-- route 2: free), 2 = Y (M), 3 = M, 4 = Z. With one M and no Z the walk
-- gathers X and gives M to Y; with a Z as well, X's first route spends the M.
private def greedy (z : Nat) : Graph :=
  ⟨5, fun i => if i = 3 then 1 else if i = 4 then z else 0, fun i =>
    if i = 0 then [⟨70, 1, 1000, [(1, 1), (2, 1)], []⟩]
    else if i = 1 then [⟨71, 1, 1000, [(3, 1), (4, 1)], []⟩, ⟨72, 1, 1000, [], []⟩]
    else if i = 2 then [⟨73, 1, 1000, [(3, 1)], []⟩] else []⟩
example : feasible (greedy 0) 0 1 = true ∧ feasible (greedy 1) 0 1 = false := by decide

end Formal.Decompose
