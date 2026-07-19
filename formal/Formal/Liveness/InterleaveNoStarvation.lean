/-
  Formal.Liveness.InterleaveNoStarvation

  Bounded d'Hondt no-starvation reachability for the focus-aging arbiter's
  weighted interleave (`interleaveDue`, defined in `Formal.ProgressionTree`).

  This discharges the theorem DEFERRED in `ProgressionTree.lean` (the
  "No-starvation (bounded reachability)" note): every strictly-positive-weight
  key receives a d'Hondt seat within a bounded window
  `interleaveWindow weighted := ⌈W / w_min⌉₊ + 1` where `W` is the total weight
  and `w_min` the least (positive) weight.

  Per the liveness quarantine (`Formal/Liveness/README.md`) this module lives in
  the Mathlib-permitted tier: the safety core `ProgressionTree.lean` stays
  Mathlib-free, so the summation / ceiling argument that the deferral note cites
  as the obstruction is carried out here instead.

  ## Honest hypotheses (all genuinely necessary, all satisfiable)

  On `interleaveDue_reaches`, beyond `(key, w) ∈ weighted` and `0 < w`:
    * `(weighted.map Prod.fst).Nodup` — unique keys (true in the real model:
      one gear candidate per slot). Without it a single seat-bump would touch
      several list entries and the per-key invariant would break.
    * `∀ p ∈ weighted, 0 < p.2` — all weights strictly positive (the scaled
      selection weights `gain * falloff` are positive in the model). Needed so
      the counting sum `w * Σ seats ≤ Σ weights` has a positive floor.

  A concrete non-vacuous witness is given at the end (`example`).
-/
import Mathlib
import Formal.ProgressionTree

namespace Formal.ProgressionTree

open scoped List

/-! ### The seat-allocation state after `n` d'Hondt steps -/

/-- The interleave state (last winner, seat counts) after `n` seat allocations,
starting from empty seats. `interleaveDue weighted c` is the last winner of
`n = c + 1` steps. -/
def dhondtState (weighted : List (String × Rat)) (n : Nat) :
    Option String × (String → Nat) :=
  (List.range n).foldl (fun st _ => dhondtStep weighted st)
    ((none : Option String), (fun _ => 0 : String → Nat))

@[simp] theorem dhondtState_zero (weighted : List (String × Rat)) :
    dhondtState weighted 0 = ((none : Option String), (fun _ => 0 : String → Nat)) := by
  simp [dhondtState]

theorem dhondtState_succ (weighted : List (String × Rat)) (n : Nat) :
    dhondtState weighted (n + 1) = dhondtStep weighted (dhondtState weighted n) := by
  simp [dhondtState, List.range_succ, List.foldl_append]

theorem interleaveDue_eq_state (weighted : List (String × Rat)) (hne : weighted ≠ [])
    (c : Nat) : interleaveDue weighted c = (dhondtState weighted (c + 1)).1 := by
  cases weighted with
  | nil => exact absurd rfl hne
  | cons x t => rfl

/-! ### `selectMax` returns a genuine list member -/

theorem selectMax_mem (weighted : List (String × Rat)) (s : String → Nat)
    (r : String × Rat) (hr : selectMax weighted s = some r) : r ∈ weighted := by
  have key : ∀ (l : List (String × Rat)) (acc : Option (String × Rat)),
      l.foldl
        (fun best kw =>
          match best with
          | none => some kw
          | some b => if selBeats s kw b then some kw else some b)
        acc = some r → r ∈ l ∨ acc = some r := by
    intro l
    induction l with
    | nil => intro acc h; exact Or.inr h
    | cons x t ih =>
      intro acc h
      simp only [List.foldl_cons] at h
      rcases ih _ h with hmem | hacc
      · exact Or.inl (List.mem_cons_of_mem _ hmem)
      · cases acc with
        | none =>
          simp only [] at hacc
          exact Or.inl (List.mem_cons.mpr (Or.inl (Option.some.inj hacc).symm) )
        | some b =>
          by_cases hb : selBeats s x b = true
          · simp only [hb, if_true] at hacc
            exact Or.inl (List.mem_cons.mpr (Or.inl (Option.some.inj hacc).symm))
          · have hbf : selBeats s x b = false := by
              cases hbb : selBeats s x b with
              | true => exact absurd hbb hb
              | false => rfl
            simp only [hbf, Bool.false_eq_true, if_false] at hacc
            exact Or.inr hacc
  rcases key weighted none hr with h | h
  · exact h
  · exact absurd h.symm (by simp)

theorem selectMax_isSome (weighted : List (String × Rat)) (s : String → Nat)
    (hne : weighted ≠ []) : ∃ r, selectMax weighted s = some r := by
  have step : ∀ (l : List (String × Rat)) (a : String × Rat),
      ∃ b, l.foldl
        (fun best kw =>
          match best with
          | none => some kw
          | some b => if selBeats s kw b then some kw else some b)
        (some a) = some b := by
    intro l
    induction l with
    | nil => intro a; exact ⟨a, rfl⟩
    | cons x t ih =>
      intro a
      simp only [List.foldl_cons]
      by_cases hb : selBeats s x a = true
      · simp only [hb, if_true]; exact ih x
      · have hbf : selBeats s x a = false := by
          cases hbb : selBeats s x a with
          | true => exact absurd hbb hb
          | false => rfl
        simp only [hbf, Bool.false_eq_true, if_false]; exact ih a
  cases weighted with
  | nil => exact absurd rfl hne
  | cons x t =>
    simp only [selectMax, List.foldl_cons]
    exact step t x

/-- Unfolding `dhondtStep` on a nonempty list: it selects a genuine winner `r`
and bumps that key's seat count. -/
theorem dhondtStep_spec (weighted : List (String × Rat)) (hne : weighted ≠ [])
    (st : Option String × (String → Nat)) :
    ∃ r, selectMax weighted st.2 = some r ∧
      dhondtStep weighted st = (some r.1, bumpSeats st.2 r.1) ∧ r ∈ weighted := by
  obtain ⟨r, hr⟩ := selectMax_isSome weighted st.2 hne
  refine ⟨r, hr, ?_, selectMax_mem weighted st.2 r hr⟩
  simp [dhondtStep, hr]

/-! ### Key-uniqueness from `Nodup` of the keys -/

theorem nodup_key_inj (l : List (String × Rat))
    (hnd : (l.map Prod.fst).Nodup) {a b : String × Rat}
    (ha : a ∈ l) (hb : b ∈ l) (hab : a.1 = b.1) : a = b := by
  induction l with
  | nil => exact absurd ha (List.not_mem_nil)
  | cons q qs ih =>
    simp only [List.map_cons, List.nodup_cons] at hnd
    rcases List.mem_cons.mp ha with rfl | ha'
    · rcases List.mem_cons.mp hb with rfl | hb'
      · rfl
      · exact absurd (hab ▸ List.mem_map_of_mem hb') hnd.1
    · rcases List.mem_cons.mp hb with rfl | hb'
      · exact absurd (hab.symm ▸ List.mem_map_of_mem ha') hnd.1
      · exact ih hnd.2 ha' hb'

/-! ### The per-key seat invariant (while `key` is unseated) -/

/-- While `key` has received no seat, every key `x` satisfies
`w * seats x ≤ w_x`: preserved because each seat goes to a quotient-maximal
key, and an unseated `key` keeps quotient `w / (0 + 1) = w`. -/
theorem seats_invariant (weighted : List (String × Rat)) (key : String) (w : Rat)
    (hmem : (key, w) ∈ weighted) (hposall : ∀ p ∈ weighted, 0 < p.2)
    (hnd : (weighted.map Prod.fst).Nodup) (hne : weighted ≠ []) :
    ∀ n, (dhondtState weighted n).2 key = 0 →
      ∀ p ∈ weighted, w * ((dhondtState weighted n).2 p.1 : Rat) ≤ p.2 := by
  intro n
  induction n with
  | zero =>
    intro _ p hp
    simp only [dhondtState_zero, Nat.cast_zero, mul_zero]
    exact le_of_lt (hposall p hp)
  | succ n ih =>
    intro hkey0 p hp
    obtain ⟨r, hr, hstep, hrmem⟩ := dhondtStep_spec weighted hne (dhondtState weighted n)
    have hstate : dhondtState weighted (n + 1) = (some r.1, bumpSeats (dhondtState weighted n).2 r.1) := by
      rw [dhondtState_succ]; exact hstep
    -- key still unseated at n ⇒ key ≠ r.1 and seats n key = 0
    have hkeyn : (dhondtState weighted n).2 key = 0 ∧ key ≠ r.1 := by
      rw [hstate] at hkey0
      simp only [bumpSeats] at hkey0
      by_cases hk : key = r.1
      · rw [if_pos hk] at hkey0; exact absurd hkey0 (Nat.succ_ne_zero _)
      · rw [if_neg hk] at hkey0; exact ⟨hkey0, hk⟩
    obtain ⟨hsn0, hkr⟩ := hkeyn
    have IH := ih hsn0
    -- winner optimality applied to (key, w)
    have hopt := selectMax_quot_max weighted (dhondtState weighted n).2 r hr (key, w) hmem
    have hwq : w ≤ dhondtQuot r.2 ((dhondtState weighted n).2 r.1) := by
      have : dhondtQuot w ((dhondtState weighted n).2 key) = w := by
        simp [dhondtQuot, hsn0]
      rw [this] at hopt; exact hopt
    rw [hstate]
    simp only []
    by_cases hpr : p.1 = r.1
    · -- p and r share a key ⇒ p = r by Nodup; the winner gets seats+1
      have hpeq : p = r := nodup_key_inj weighted hnd hp hrmem hpr
      have hbump : bumpSeats (dhondtState weighted n).2 r.1 p.1
          = (dhondtState weighted n).2 r.1 + 1 := by
        simp [bumpSeats, hpr]
      rw [hbump]
      have hden : (0 : Rat) < ((dhondtState weighted n).2 r.1 : Rat) + 1 := by positivity
      have := (le_div_iff₀ hden).mp hwq
      calc w * (((dhondtState weighted n).2 r.1 + 1 : Nat) : Rat)
          = w * (((dhondtState weighted n).2 r.1 : Rat) + 1) := by push_cast; ring
        _ ≤ r.2 := this
        _ = p.2 := by rw [hpeq]
    · -- untouched key: unchanged seats, IH applies
      have hbump : bumpSeats (dhondtState weighted n).2 r.1 p.1
          = (dhondtState weighted n).2 p.1 := by
        simp [bumpSeats, hpr]
      rw [hbump]
      exact IH p hp

/-! ### The seat-count telescope: exactly one seat handed out per step -/

theorem bump_map_eq_of_not_mem (s : String → Nat) (k : String)
    (l : List (String × Rat)) (h : k ∉ l.map Prod.fst) :
    l.map (fun p => bumpSeats s k p.1) = l.map (fun p => s p.1) := by
  apply List.map_congr_left
  intro p hp
  have hpk : p.1 ≠ k := fun hpk => h (hpk ▸ List.mem_map_of_mem hp)
  simp [bumpSeats, hpk]

theorem bump_map_sum (s : String → Nat) (k : String) (l : List (String × Rat))
    (hk : k ∈ l.map Prod.fst) (hnd : (l.map Prod.fst).Nodup) :
    (l.map (fun p => bumpSeats s k p.1)).sum = (l.map (fun p => s p.1)).sum + 1 := by
  induction l with
  | nil => exact absurd hk (by simp)
  | cons q qs ih =>
    simp only [List.map_cons, List.nodup_cons] at hnd
    simp only [List.map_cons, List.sum_cons]
    by_cases hkq : k = q.1
    · have hnotin : k ∉ qs.map Prod.fst := hkq ▸ hnd.1
      have hb : bumpSeats s k q.1 = s q.1 + 1 := by simp [bumpSeats, hkq.symm]
      rw [hb, bump_map_eq_of_not_mem s k qs hnotin]
      ring
    · have hkqs : k ∈ qs.map Prod.fst := by
        rcases List.mem_cons.mp hk with h | h
        · exact absurd h hkq
        · exact h
      have hq1k : q.1 ≠ k := fun h => hkq h.symm
      have hb : bumpSeats s k q.1 = s q.1 := by simp [bumpSeats, hq1k]
      rw [hb, ih hkqs hnd.2]
      ring

theorem seat_sum_eq (weighted : List (String × Rat)) (hne : weighted ≠ [])
    (hnd : (weighted.map Prod.fst).Nodup) (n : Nat) :
    (weighted.map (fun p => (dhondtState weighted n).2 p.1)).sum = n := by
  induction n with
  | zero =>
    simp only [dhondtState_zero]
    induction weighted with
    | nil => simp
    | cons q qs ih => simp [List.sum_cons]
  | succ n ih =>
    obtain ⟨r, hr, hstep, hrmem⟩ := dhondtStep_spec weighted hne (dhondtState weighted n)
    have hstate : (dhondtState weighted (n + 1)).2
        = bumpSeats (dhondtState weighted n).2 r.1 := by
      rw [dhondtState_succ, hstep]
    have hrk : r.1 ∈ weighted.map Prod.fst := List.mem_map_of_mem hrmem
    rw [hstate, bump_map_sum (dhondtState weighted n).2 r.1 weighted hrk hnd, ih]

/-! ### `key` unseated whenever it never wins -/

theorem seats_key_zero (weighted : List (String × Rat)) (hne : weighted ≠ [])
    (key : String) (n : Nat)
    (hno : ∀ m, 1 ≤ m → m ≤ n → (dhondtState weighted m).1 ≠ some key) :
    (dhondtState weighted n).2 key = 0 := by
  induction n with
  | zero => simp
  | succ n ih =>
    have ihz : (dhondtState weighted n).2 key = 0 :=
      ih (fun m hm1 hmn => hno m hm1 (Nat.le_succ_of_le hmn))
    obtain ⟨r, hr, hstep, hrmem⟩ := dhondtStep_spec weighted hne (dhondtState weighted n)
    have hstate : dhondtState weighted (n + 1)
        = (some r.1, bumpSeats (dhondtState weighted n).2 r.1) := by
      rw [dhondtState_succ]; exact hstep
    have hne_key : r.1 ≠ key := by
      intro h
      exact hno (n + 1) (Nat.succ_pos n) (le_refl _) (by rw [hstate, ← h])
    rw [hstate]
    simp only [bumpSeats]
    rw [if_neg (fun h => hne_key h.symm)]
    exact ihz

/-! ### The window and the counting bound -/

/-- Total selection weight. -/
def totalWeight (weighted : List (String × Rat)) : Rat := (weighted.map Prod.snd).sum

/-- Least weight in the list (seeded by `1`; only used on all-positive lists
where it lower-bounds every weight and stays positive). -/
def minWeight : List (String × Rat) → Rat
  | [] => 1
  | p :: ps => min p.2 (minWeight ps)

theorem minWeight_pos (l : List (String × Rat)) (h : ∀ p ∈ l, 0 < p.2) :
    0 < minWeight l := by
  induction l with
  | nil => simp [minWeight]
  | cons q qs ih =>
    simp only [minWeight, lt_min_iff]
    exact ⟨h q List.mem_cons_self, ih (fun p hp => h p (List.mem_cons_of_mem _ hp))⟩

theorem minWeight_le (l : List (String × Rat)) {p : String × Rat} (hp : p ∈ l) :
    minWeight l ≤ p.2 := by
  induction l with
  | nil => exact absurd hp (List.not_mem_nil)
  | cons q qs ih =>
    simp only [minWeight]
    rcases List.mem_cons.mp hp with rfl | h
    · exact min_le_left _ _
    · exact le_trans (min_le_right _ _) (ih h)

/-- No-starvation window: `⌈W / w_min⌉₊ + 1`. -/
def interleaveWindow (weighted : List (String × Rat)) : Nat :=
  ⌈totalWeight weighted / minWeight weighted⌉₊ + 1

/-! ### Main theorem -/

theorem interleaveDue_reaches (weighted : List (String × Rat)) (key : String) (w : Rat)
    (hpos : 0 < w) (hmem : (key, w) ∈ weighted)
    (hnd : (weighted.map Prod.fst).Nodup)
    (hposall : ∀ p ∈ weighted, 0 < p.2) :
    ∃ c, c < interleaveWindow weighted ∧ interleaveDue weighted c = some key := by
  have hne : weighted ≠ [] := List.ne_nil_of_mem hmem
  by_contra hcon
  simp only [not_exists, not_and] at hcon
  -- key never wins in steps 1 .. window
  have hno : ∀ m, 1 ≤ m → m ≤ interleaveWindow weighted →
      (dhondtState weighted m).1 ≠ some key := by
    intro m hm1 hmN
    have hc : m - 1 < interleaveWindow weighted := by omega
    have := hcon (m - 1) hc
    rwa [interleaveDue_eq_state weighted hne, Nat.sub_add_cancel hm1] at this
  -- therefore key has no seat after `window` steps
  have hzero : (dhondtState weighted (interleaveWindow weighted)).2 key = 0 :=
    seats_key_zero weighted hne key _ hno
  -- counting bound: w * window ≤ W
  have hinv := seats_invariant weighted key w hmem hposall hnd hne
    (interleaveWindow weighted) hzero
  have hsum : (weighted.map
      (fun p => (dhondtState weighted (interleaveWindow weighted)).2 p.1)).sum
      = interleaveWindow weighted := seat_sum_eq weighted hne hnd _
  set N := interleaveWindow weighted with hN
  set st := dhondtState weighted N with hst
  -- Σ_p w * seats(p) ≤ Σ_p w_p = W
  have hle : (weighted.map (fun p => w * ((st.2 p.1 : Nat) : Rat))).sum
      ≤ (weighted.map (fun p => p.2)).sum :=
    List.sum_le_sum (fun p hp => hinv p hp)
  -- factor w out, cast the Nat seat-sum
  have hcast : ((weighted.map (fun p => st.2 p.1)).sum : Rat)
      = (weighted.map (fun p => ((st.2 p.1 : Nat) : Rat))).sum := by
    rw [Nat.cast_list_sum, List.map_map]; rfl
  have hfactor : (weighted.map (fun p => w * ((st.2 p.1 : Nat) : Rat))).sum
      = w * (N : Rat) := by
    rw [List.sum_map_mul_left, ← hsum, ← hcast]
  have hW : (weighted.map (fun p => p.2)).sum = totalWeight weighted := rfl
  rw [hfactor, hW] at hle
  -- window strictly exceeds W / w, contradiction
  have hminpos : 0 < minWeight weighted := minWeight_pos weighted hposall
  have hminle : minWeight weighted ≤ w := minWeight_le weighted hmem
  have hWpos : 0 < totalWeight weighted := by
    have : w ≤ totalWeight weighted :=
      List.single_le_sum (fun x hx => le_of_lt (by
        obtain ⟨p, hp, rfl⟩ := List.mem_map.mp hx; exact hposall p hp))
        w (List.mem_map_of_mem hmem)
    exact lt_of_lt_of_le hpos this
  have hdiv : totalWeight weighted / w ≤ totalWeight weighted / minWeight weighted :=
    div_le_div_of_nonneg_left (le_of_lt hWpos) hminpos hminle
  have hceil : totalWeight weighted / minWeight weighted
      ≤ (⌈totalWeight weighted / minWeight weighted⌉₊ : Rat) := Nat.le_ceil _
  have hNcast : (N : Rat) = (⌈totalWeight weighted / minWeight weighted⌉₊ : Rat) + 1 := by
    rw [hN, interleaveWindow]; push_cast; ring
  have hlt : totalWeight weighted / w < (N : Rat) := by
    rw [hNcast]
    exact lt_of_le_of_lt (le_trans hdiv hceil) (lt_add_one _)
  have hlt2 : totalWeight weighted < w * (N : Rat) := by
    rw [mul_comm]
    exact (div_lt_iff₀ hpos).mp hlt
  exact absurd hle (not_le.mpr hlt2)

/-! ### Non-vacuity witness -/

example :
    ∃ (weighted : List (String × Rat)) (key : String) (w : Rat)
      (_ : 0 < w) (_ : (key, w) ∈ weighted)
      (_ : (weighted.map Prod.fst).Nodup) (_ : ∀ p ∈ weighted, 0 < p.2),
      ∃ c, c < interleaveWindow weighted ∧ interleaveDue weighted c = some key := by
  refine ⟨[("a", 3), ("b", 1)], "b", 1, by norm_num, by simp, ?_, ?_, ?_⟩
  · simp
  · intro p hp
    rcases List.mem_cons.mp hp with rfl | hp
    · norm_num
    · rcases List.mem_cons.mp hp with rfl | hp
      · norm_num
      · exact absurd hp (List.not_mem_nil)
  · exact interleaveDue_reaches _ "b" 1 (by norm_num) (by simp)
      (by simp) (by
        intro p hp
        rcases List.mem_cons.mp hp with rfl | hp
        · norm_num
        · rcases List.mem_cons.mp hp with rfl | hp
          · norm_num
          · exact absurd hp (List.not_mem_nil))

end Formal.ProgressionTree
