-- @concept: arbiter, intention, fairness @property: liveness, boundedness
/-
The intention's turn order (Phase 5-2c-iii-a,
`src/artifactsmmo_cli/ai/intention_progress.py`: `rotate`, `record_turn`).

Goal choice takes the FIRST plannable goal of the walk's step/fallback group
after `rotate` orders it: the goals that never spent a budget first, in walk
order, then the served ones, least recently served first. Each spent budget
records the goal's turn as the newest (`record_turn`).

## The model

A group of `n` candidates is positions `0 … n-1` (walk order). `t i` is the
candidate's last turn, `0` for never served (Python: absent from the log), and
`p i` whether it can plan this cycle. `before t i j` is the order `rotate`
produces: an older turn first, a tie (two never-served goals) in walk order.
`pick` is the first plannable candidate in that order — the least element of
the plannable ones. `serve` records a spent budget: the picked goal's turn
becomes one more than every candidate's. (Python's `record_turn` takes one more
than every LOGGED turn, a superset of the group's, so the picked goal lands
after every candidate in both; only that relation is used.)

## What is proved

`rotation_fair`: with the plannable set fixed, a plannable candidate `g` is
picked within `below g` turns, where `below g` — the plannable candidates ahead
of `g` in turn order — is at most `n - 1` (`below_lt`). The potential argument:
a turn that picks some `h ≠ g` picks one AHEAD of `g` (`pick` is the least),
and serving `h` moves it behind `g` while every other candidate keeps its place
relative to `g` (`below_serve_lt`), so `below g` falls by one each turn until
it is zero, when `g` is the least and is picked (`pick_of_below_zero`).

THE DEFECT THIS REPLACES. The one-goal yield (Phase 4-2b) cleared when the next
intention ended, so the root's step came straight back: A, B, A, B, and a third
goal never ran. Under that rule `below` of the third goal does not fall — the
returning root is ahead of it again — which is exactly the property the
potential needs.
-/

namespace Formal.TurnRotation

/-- `i` comes before `j` in turn order: an older last turn, or the same turn
(two never-served goals) and earlier in the walk. -/
def before (t : Nat → Nat) (i j : Nat) : Bool :=
  t i < t j || (t i == t j && i < j)

/-- The least plannable candidate of `l` in turn order (`rotate`'s first
plannable goal). -/
def pickL (t : Nat → Nat) (p : Nat → Bool) : List Nat → Option Nat
  | [] => none
  | i :: rest =>
    match pickL t p rest with
    | none => if p i then some i else none
    | some b => if p i && before t i b then some i else some b

/-- The pick over a group of `n` candidates. -/
def pick (n : Nat) (p : Nat → Bool) (t : Nat → Nat) : Option Nat :=
  pickL t p (List.range n)

/-- The newest turn among `l`. -/
def maxL (t : Nat → Nat) : List Nat → Nat
  | [] => 0
  | i :: rest => max (t i) (maxL t rest)

/-- A spent budget: `g`'s turn becomes newer than every candidate's. -/
def serve (n : Nat) (t : Nat → Nat) (g : Nat) : Nat → Nat :=
  fun i => if i = g then maxL t (List.range n) + 1 else t i

/-- One turn: the picked goal spends its budget (nothing plannable: no turn). -/
def step (n : Nat) (p : Nat → Bool) (t : Nat → Nat) : Nat → Nat :=
  match pick n p t with
  | some g => serve n t g
  | none => t

/-- `m` turns. -/
def run (n : Nat) (p : Nat → Bool) : Nat → (Nat → Nat) → (Nat → Nat)
  | 0, t => t
  | m + 1, t => run n p m (step n p t)

/-- The plannable candidates ahead of `g` in turn order. -/
def below (n : Nat) (p : Nat → Bool) (t : Nat → Nat) (g : Nat) : Nat :=
  ((List.range n).filter (fun j => p j && before t j g)).length

/-! ### `before` is a strict total order on distinct positions -/

theorem before_irrefl (t : Nat → Nat) (i : Nat) : before t i i = false := by
  simp [before]

theorem before_total (t : Nat → Nat) (i j : Nat) (h : i ≠ j) :
    before t i j = true ∨ before t j i = true := by
  simp only [before, Bool.or_eq_true, decide_eq_true_eq, Bool.and_eq_true, beq_iff_eq]
  omega

theorem before_trans (t : Nat → Nat) (i j k : Nat)
    (hij : before t i j = true) (hjk : before t j k = true) : before t i k = true := by
  simp only [before, Bool.or_eq_true, decide_eq_true_eq, Bool.and_eq_true, beq_iff_eq] at *
  omega

theorem before_asymm (t : Nat → Nat) (i j : Nat) (h : before t i j = true) :
    before t j i = false := by
  simp only [before, Bool.or_eq_true, decide_eq_true_eq, Bool.and_eq_true, beq_iff_eq] at h
  simp only [before, Bool.or_eq_false_iff, decide_eq_false_iff_not, Bool.and_eq_false_iff,
    beq_eq_false_iff_ne]
  omega

/-! ### `pickL` is the least plannable element -/

theorem pickL_spec (t : Nat → Nat) (p : Nat → Bool) :
    ∀ (l : List Nat) (h : Nat), pickL t p l = some h →
      h ∈ l ∧ p h = true ∧ ∀ j ∈ l, p j = true → j ≠ h → before t h j = true := by
  intro l
  induction l with
  | nil => intro h hp; simp [pickL] at hp
  | cons i rest ih =>
    intro h hp
    simp only [pickL] at hp
    cases hr : pickL t p rest with
    | none =>
      rw [hr] at hp
      by_cases hpi : p i = true
      · simp [hpi] at hp
        subst hp
        refine ⟨List.mem_cons_self, hpi, ?_⟩
        intro j hj hpj hne
        rcases List.mem_cons.mp hj with rfl | hjr
        · exact absurd rfl hne
        · -- `rest` has no plannable element, but `j` is one
          exfalso
          have : ∀ l : List Nat, pickL t p l = none → ∀ x ∈ l, p x = false := by
            intro l
            induction l with
            | nil => intro _ x hx; simp at hx
            | cons a r ih2 =>
              intro hn x hx
              simp only [pickL] at hn
              cases hr2 : pickL t p r with
              | none =>
                rw [hr2] at hn
                rcases List.mem_cons.mp hx with rfl | hxr
                · by_cases hpa : p x = true
                  · simp [hpa] at hn
                  · simpa using hpa
                · exact ih2 hr2 x hxr
              | some b =>
                rw [hr2] at hn
                by_cases hc : (p a && before t a b) = true <;> simp [hc] at hn
          have := this rest hr j hjr
          simp [this] at hpj
      · simp [hpi] at hp
    | some b =>
      rw [hr] at hp
      obtain ⟨hbmem, hpb, hbleast⟩ := ih b hr
      by_cases hc : (p i && before t i b) = true
      · simp [hc] at hp
        subst hp
        simp only [Bool.and_eq_true] at hc
        refine ⟨List.mem_cons_self, hc.1, ?_⟩
        intro j hj hpj hne
        rcases List.mem_cons.mp hj with rfl | hjr
        · exact absurd rfl hne
        · by_cases hjb : j = b
          · subst hjb; exact hc.2
          · exact before_trans t _ b j hc.2 (hbleast j hjr hpj hjb)
      · simp [hc] at hp
        subst hp
        refine ⟨List.mem_cons_of_mem _ hbmem, hpb, ?_⟩
        intro j hj hpj hne
        rcases List.mem_cons.mp hj with rfl | hjr
        · -- `j = i`, plannable, not before `b`: so `b` is before it
          have hnb : before t j b = false := by
            simp only [Bool.and_eq_true, not_and] at hc
            cases hbt : before t j b
            · rfl
            · exact absurd hbt (hc hpj)
          rcases before_total t j b hne with hb | hb
          · rw [hnb] at hb; exact absurd hb (by decide)
          · exact hb
        · exact hbleast j hjr hpj hne

/-- No plannable element: no pick. A plannable element: some pick. -/
theorem pickL_isSome (t : Nat → Nat) (p : Nat → Bool) :
    ∀ (l : List Nat) (g : Nat), g ∈ l → p g = true → (pickL t p l).isSome := by
  intro l
  induction l with
  | nil => intro g hg; simp at hg
  | cons i rest ih =>
    intro g hg hpg
    simp only [pickL]
    cases hr : pickL t p rest with
    | none =>
      rcases List.mem_cons.mp hg with rfl | hgr
      · simp [hpg]
      · have := ih g hgr hpg
        rw [hr] at this
        simp at this
    | some b =>
      by_cases hc : (p i && before t i b) = true <;> simp [hc]

theorem maxL_ge (t : Nat → Nat) : ∀ (l : List Nat) (g : Nat), g ∈ l → t g ≤ maxL t l := by
  intro l
  induction l with
  | nil => intro g hg; simp at hg
  | cons i rest ih =>
    intro g hg
    simp only [maxL]
    rcases List.mem_cons.mp hg with rfl | hgr
    · exact Nat.le_max_left _ _
    · exact Nat.le_trans (ih g hgr) (Nat.le_max_right _ _)

/-! ### The potential -/

/-- Filtering by a pointwise-smaller predicate that drops one member shortens
the list. -/
theorem filter_length_lt (f f' : Nat → Bool) :
    ∀ (l : List Nat), (∀ j ∈ l, f' j = true → f j = true) →
      (∃ h ∈ l, f h = true ∧ f' h = false) →
      (l.filter f').length < (l.filter f).length := by
  intro l
  induction l with
  | nil => intro _ ⟨h, hh, _⟩; simp at hh
  | cons a r ih =>
    intro himp ⟨h, hh, hf, hf'⟩
    have himp' : ∀ j ∈ r, f' j = true → f j = true :=
      fun j hj => himp j (List.mem_cons_of_mem _ hj)
    have hle : (r.filter f').length ≤ (r.filter f).length := by
      have : ∀ (l : List Nat), (∀ j ∈ l, f' j = true → f j = true) →
          (l.filter f').length ≤ (l.filter f).length := by
        intro l
        induction l with
        | nil => intro _; simp
        | cons x xs ih3 =>
          intro hx
          have hxs : ∀ j ∈ xs, f' j = true → f j = true :=
            fun j hj => hx j (List.mem_cons_of_mem _ hj)
          have := ih3 hxs
          cases hfx : f x <;> cases hf'x : f' x <;>
            simp [hfx, hf'x] <;> try omega
          have := hx x List.mem_cons_self hf'x
          rw [hfx] at this; exact absurd this (by decide)
      exact this r himp'
    rcases List.mem_cons.mp hh with rfl | hhr
    · simp [hf, hf']
      omega
    · have hlt := ih himp' ⟨h, hhr, hf, hf'⟩
      cases hfa : f a <;> cases hf'a : f' a <;>
        simp [hfa, hf'a] <;> try omega
      have := himp a List.mem_cons_self hf'a
      rw [hfa] at this; exact absurd this (by decide)

/-- `below g` counts no more than the other `n - 1` candidates. -/
theorem below_lt (n : Nat) (p : Nat → Bool) (t : Nat → Nat) (g : Nat) (hg : g < n) :
    below n p t g < n := by
  unfold below
  have hlen : (List.range n).length = n := List.length_range
  have := filter_length_lt (fun _ => true) (fun j => p j && before t j g) (List.range n)
    (by intro _ _ _; rfl)
    ⟨g, List.mem_range.mpr hg, rfl, by simp [before_irrefl]⟩
  rw [List.filter_eq_self.mpr (fun _ _ => rfl), hlen] at this
  exact this

/-- Nothing plannable ahead of a plannable `g`: `g` is picked. -/
theorem pick_of_below_zero (n : Nat) (p : Nat → Bool) (t : Nat → Nat) (g : Nat)
    (hg : g < n) (hpg : p g = true) (h0 : below n p t g = 0) :
    pick n p t = some g := by
  unfold pick
  have hsome := pickL_isSome t p (List.range n) g (List.mem_range.mpr hg) hpg
  obtain ⟨h, hh⟩ := Option.isSome_iff_exists.mp hsome
  rw [hh]
  obtain ⟨hmem, hph, hleast⟩ := pickL_spec t p (List.range n) h hh
  by_cases hne : g = h
  · rw [hne]
  · exfalso
    have hbefore := hleast g (List.mem_range.mpr hg) hpg hne
    unfold below at h0
    have : h ∈ (List.range n).filter (fun j => p j && before t j g) := by
      simp [List.mem_filter, hmem, hph, hbefore]
    rw [List.length_eq_zero_iff] at h0
    rw [h0] at this
    simp at this

/-- A turn that picks some other `h` lowers `g`'s potential. -/
theorem below_serve_lt (n : Nat) (p : Nat → Bool) (t : Nat → Nat) (g h : Nat)
    (hg : g < n) (hpg : p g = true) (hpick : pick n p t = some h) (hne : h ≠ g) :
    below n p (serve n t h) g < below n p t g := by
  obtain ⟨hmem, hph, hleast⟩ := pickL_spec t p (List.range n) h hpick
  have hhg : before t h g = true := hleast g (List.mem_range.mpr hg) hpg (Ne.symm hne)
  unfold below
  apply filter_length_lt
  · intro j _ hj
    simp only [Bool.and_eq_true] at hj ⊢
    refine ⟨hj.1, ?_⟩
    by_cases hjh : j = h
    · subst hjh; exact hhg
    · have hb := hj.2
      simp only [serve, before, if_neg hjh, if_neg (Ne.symm hne)] at hb
      simpa [before] using hb
  · refine ⟨h, hmem, by simp [hph, hhg], ?_⟩
    have hmax := maxL_ge t (List.range n) g (List.mem_range.mpr hg)
    simp only [serve, before, if_neg (Ne.symm hne), ite_true]
    simp only [Bool.and_eq_false_iff, Bool.or_eq_false_iff, decide_eq_false_iff_not,
      Bool.and_eq_false_iff, beq_eq_false_iff_ne]
    right
    omega

/-- FAIRNESS: a plannable `g` is picked within `below g` turns, and
`below g < n`, so within `n - 1`. -/
theorem rotation_fair (n : Nat) (p : Nat → Bool) (g : Nat) (hg : g < n)
    (hpg : p g = true) :
    ∀ (t : Nat → Nat), ∃ m, m ≤ below n p t g ∧ pick n p (run n p m t) = some g := by
  suffices key : ∀ (k : Nat) (t : Nat → Nat), below n p t g ≤ k →
      ∃ m, m ≤ below n p t g ∧ pick n p (run n p m t) = some g from
    fun t => key _ t (Nat.le_refl _)
  intro k
  induction k with
  | zero =>
    intro t hb
    exact ⟨0, Nat.zero_le _, pick_of_below_zero n p t g hg hpg (by omega)⟩
  | succ k ih =>
    intro t hb
    obtain ⟨h, hh⟩ := Option.isSome_iff_exists.mp
      (pickL_isSome t p (List.range n) g (List.mem_range.mpr hg) hpg)
    by_cases hhg : h = g
    · subst hhg
      exact ⟨0, Nat.zero_le _, hh⟩
    · have hlt := below_serve_lt n p t g h hg hpg hh hhg
      obtain ⟨m, hm, hpick⟩ := ih (serve n t h) (by omega)
      refine ⟨m + 1, by omega, ?_⟩
      have hstep : step n p t = serve n t h := by
        unfold step; rw [show pick n p t = some h from hh]
      simp only [run, hstep]
      exact hpick

/-- The headline bound: within `n - 1` turns. -/
theorem rotation_fair_bound (n : Nat) (p : Nat → Bool) (g : Nat) (hg : g < n)
    (hpg : p g = true) (t : Nat → Nat) :
    ∃ m, m + 1 ≤ n ∧ pick n p (run n p m t) = some g := by
  obtain ⟨m, hm, hpick⟩ := rotation_fair n p g hg hpg t
  exact ⟨m, by have := below_lt n p t g hg; omega, hpick⟩

/-! ### Non-vacuity at the live defect

Four always-plannable goals, the first two served (A at turn 1, B at turn 2):
the third is picked now, where the one-goal yield picked A or B. -/
example : pick 4 (fun _ => true) (fun i => if i = 0 then 1 else if i = 1 then 2 else 0)
    = some 2 := by decide

/-- Every hypothesis of `rotation_fair_bound` is satisfiable: candidate 3 of 4,
all plannable, from a log where it is the most recently served. -/
example : ∃ m, m + 1 ≤ 4 ∧ pick 4 (fun _ => true)
    (run 4 (fun _ => true) m (fun i => if i = 3 then 9 else 0)) = some 3 :=
  rotation_fair_bound 4 (fun _ => true) 3 (by decide) rfl _

end Formal.TurnRotation
