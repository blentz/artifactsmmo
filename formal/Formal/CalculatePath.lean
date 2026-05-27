/-
Formal model of `calculate_path` from
`src/artifactsmmo_cli/utils/pathfinding.py`.

The Python routine walks one king-step toward the target each iteration
(simultaneously stepping each axis by -1/0/+1 toward the destination).
The Manhattan distance is reported as `total_distance`, and the number of
steps produced equals the Chebyshev distance.

This file gives:
* a Lean model (`pathFrom`) that mirrors the Python loop,
* `pathFrom_valid`     — the produced path is a legal king-walk,
* `pathFrom_cost`      — the path length never exceeds the Manhattan cost (Chebyshev ≤ Manhattan),
* `kingWalk_len_ge_cheb`— every legal king-walk has length ≥ Chebyshev (lower bound),
* `pathFrom_len_eq_cheb`— the produced path has length = Chebyshev (achieved).

Lean core only — no mathlib. Integer arithmetic is handled by `omega`.
-/

namespace Formal.CalculatePath

/-- Integer coordinate on the map. -/
abbrev Coord := Int × Int

/-- Absolute value on `Int` (kept concrete so `omega` can reason after unfolding). -/
def absI (n : Int) : Int := if n < 0 then -n else n

/-- Chebyshev (king) distance. -/
def cheb (a b : Coord) : Int := max (absI (b.1 - a.1)) (absI (b.2 - a.2))

/-- Manhattan distance. -/
def manhattan (a b : Coord) : Int := absI (b.1 - a.1) + absI (b.2 - a.2)

/-- Move one coordinate one unit toward `d` (or stay put if already equal). -/
def stepToward (c d : Int) : Int := if c < d then c + 1 else if c > d then c - 1 else c

/-- One king step: step each axis toward the destination. -/
def kingStep (cur dst : Coord) : Coord := (stepToward cur.1 dst.1, stepToward cur.2 dst.2)

/-- Build a path with an explicit fuel bound (the loop body of the Python code). -/
def pathFromFuel (fuel : Nat) (cur dst : Coord) : List Coord :=
  if cur = dst then []
  else match fuel with
    | 0 => []
    | n + 1 => let nxt := kingStep cur dst; nxt :: pathFromFuel n nxt dst

/-- The path produced by `calculate_path`, fuelled by the Chebyshev distance. -/
def pathFrom (start dst : Coord) : List Coord := pathFromFuel (cheb start dst).toNat start dst

/-- Two coordinates are king-adjacent (within one step on each axis, and distinct). -/
def adjacent (a b : Coord) : Prop := absI (b.1 - a.1) ≤ 1 ∧ absI (b.2 - a.2) ≤ 1 ∧ a ≠ b

/-- A list `p` is a legal king-walk from `start` to `dst`. -/
def ValidKingWalk (start dst : Coord) (p : List Coord) : Prop :=
  (p = [] ∧ start = dst) ∨
  (p ≠ [] ∧ adjacent start p.head! ∧ p.getLast! = dst ∧
    ∀ i, (i + 1 < p.length) → adjacent (p[i]!) (p[i+1]!))

/-! ### Small list helpers (avoid mathlib-only `List.getLast!` lemmas). -/

theorem getLast!_cons_ne (x : Coord) (l : List Coord) (hne : l ≠ []) :
    (x :: l).getLast! = l.getLast! := by
  cases h' : l with
  | nil => exact absurd h' hne
  | cons a as => simp [List.getLast!]

theorem getElem!_zero_eq_head! (l : List Coord) (hne : l ≠ []) :
    l[0]! = l.head! := by
  cases h' : l with
  | nil => exact absurd h' hne
  | cons a as => simp [List.head!]

/-! ### Arithmetic facts about `absI`, `stepToward`, `cheb`. -/

theorem absI_nonneg (n : Int) : 0 ≤ absI n := by unfold absI; split <;> omega

theorem absI_le_one_iff (n : Int) : absI n ≤ 1 ↔ -1 ≤ n ∧ n ≤ 1 := by
  unfold absI; split <;> omega

theorem cheb_nonneg (a b : Coord) : 0 ≤ cheb a b := by
  unfold cheb; have := absI_nonneg (b.1 - a.1); have := absI_nonneg (b.2 - a.2)
  omega

/-- `cheb` of a coordinate with itself is zero. -/
theorem cheb_self (a : Coord) : cheb a a = 0 := by unfold cheb absI; simp

/-- `stepToward` moves at most one unit. -/
theorem absI_stepToward (c d : Int) : absI (stepToward c d - c) ≤ 1 := by
  unfold absI stepToward; split <;> split <;> omega

/-- After a step toward `d`, the absolute gap to `d` drops by exactly one,
unless we were already there. -/
-- (kept for reuse)
theorem absI_stepToward_to (c d : Int) :
    absI (d - stepToward c d) = (if c = d then 0 else absI (d - c) - 1) := by
  unfold absI stepToward; split <;> split <;> split <;> omega

/-- The king step toward `dst` is adjacent to `cur`, provided we are not yet there. -/
theorem adjacent_kingStep (cur dst : Coord) (h : cur ≠ dst) :
    adjacent cur (kingStep cur dst) := by
  refine ⟨?_, ?_, ?_⟩
  · show absI ((kingStep cur dst).1 - cur.1) ≤ 1
    simpa [kingStep] using absI_stepToward cur.1 dst.1
  · show absI ((kingStep cur dst).2 - cur.2) ≤ 1
    simpa [kingStep] using absI_stepToward cur.2 dst.2
  · -- cur ≠ kingStep cur dst : at least one axis differs from cur.
    intro hcontra
    apply h
    have h1 : cur.1 = stepToward cur.1 dst.1 := congrArg Prod.fst hcontra
    have h2 : cur.2 = stepToward cur.2 dst.2 := congrArg Prod.snd hcontra
    unfold stepToward at h1 h2
    refine Prod.ext ?_ ?_
    · (split at h1 <;> try split at h1) <;> omega
    · (split at h2 <;> try split at h2) <;> omega

/-- One king step changes `cheb _ dst` by exactly going down by 1 (when not at dst). -/
theorem cheb_kingStep (cur dst : Coord) (h : cur ≠ dst) :
    cheb (kingStep cur dst) dst = cheb cur dst - 1 := by
  have hne : cur.1 ≠ dst.1 ∨ cur.2 ≠ dst.2 := by
    rcases Decidable.em (cur.1 = dst.1) with h1 | h1
    · rcases Decidable.em (cur.2 = dst.2) with h2 | h2
      · exact absurd (Prod.ext h1 h2) h
      · exact Or.inr h2
    · exact Or.inl h1
  show max (absI (dst.1 - (kingStep cur dst).1)) (absI (dst.2 - (kingStep cur dst).2))
      = max (absI (dst.1 - cur.1)) (absI (dst.2 - cur.2)) - 1
  simp only [kingStep, stepToward, absI]
  -- All four `absI`/`stepToward` ifs are now exposed; case-split and let omega finish.
  rcases hne with hn | hn <;>
    (split <;> split <;> split <;> split <;> split <;> split <;> omega)

/-- Any single king step lowers `cheb _ dst` by at most 1 (general adjacency form). -/
theorem cheb_drop_le_one (a b dst : Coord) (h : adjacent a b) :
    cheb a dst - 1 ≤ cheb b dst := by
  obtain ⟨h1, h2, _⟩ := h
  rw [absI_le_one_iff] at h1 h2
  obtain ⟨h1a, h1b⟩ := h1
  obtain ⟨h2a, h2b⟩ := h2
  show max (absI (dst.1 - a.1)) (absI (dst.2 - a.2)) - 1
      ≤ max (absI (dst.1 - b.1)) (absI (dst.2 - b.2))
  unfold absI
  split <;> split <;> split <;> split <;> omega

/-! ### Length of the produced path equals Chebyshev distance. -/

/-- With enough fuel, `pathFromFuel` has length `(cheb cur dst).toNat`. -/
theorem pathFromFuel_length (fuel : Nat) (cur dst : Coord)
    (hfuel : (cheb cur dst).toNat ≤ fuel) :
    (pathFromFuel fuel cur dst).length = (cheb cur dst).toNat := by
  induction fuel generalizing cur with
  | zero =>
    -- fuel = 0 forces cheb cur dst ≤ 0, i.e. cur = dst.
    have hc0 : (cheb cur dst).toNat = 0 := Nat.le_zero.mp hfuel
    by_cases hcd : cur = dst
    · subst hcd
      rw [cheb_self]
      unfold pathFromFuel
      simp
    · exfalso
      have hpos : 0 < cheb cur dst := by
        have := cheb_nonneg (kingStep cur dst) dst
        rw [cheb_kingStep cur dst hcd] at this; omega
      have : 0 < (cheb cur dst).toNat := by omega
      omega
  | succ n ih =>
    by_cases hcd : cur = dst
    · subst hcd
      rw [cheb_self]
      unfold pathFromFuel
      simp
    · have hpath : pathFromFuel (n + 1) cur dst
          = kingStep cur dst :: pathFromFuel n (kingStep cur dst) dst := by
        show (if cur = dst then [] else
          let nxt := kingStep cur dst; nxt :: pathFromFuel n nxt dst) = _
        rw [if_neg hcd]
      rw [hpath]
      have hstep : cheb (kingStep cur dst) dst = cheb cur dst - 1 :=
        cheb_kingStep cur dst hcd
      have hpos : 0 < cheb cur dst := by
        have := cheb_nonneg (kingStep cur dst) dst; omega
      have hfuel' : (cheb (kingStep cur dst) dst).toNat ≤ n := by
        rw [hstep]; omega
      have := ih (kingStep cur dst) hfuel'
      simp only [List.length_cons, this, hstep]
      omega

-- mirrors pathfinding.py:65-81 (king-step loop)
theorem pathFrom_len_eq_cheb (start dst : Coord) :
    (pathFrom start dst).length = (cheb start dst).toNat := by
  unfold pathFrom
  exact pathFromFuel_length _ start dst (Nat.le_refl _)

/-! ### Validity of the produced path. -/

/-- Helper: structural validity of `pathFromFuel` when fuel suffices. -/
theorem pathFromFuel_valid (fuel : Nat) (cur dst : Coord)
    (hfuel : (cheb cur dst).toNat ≤ fuel) :
    ValidKingWalk cur dst (pathFromFuel fuel cur dst) := by
  induction fuel generalizing cur with
  | zero =>
    have hc0 : (cheb cur dst).toNat = 0 := Nat.le_zero.mp hfuel
    by_cases hcd : cur = dst
    · left; refine ⟨?_, hcd⟩; unfold pathFromFuel; simp [hcd]
    · exfalso
      have hpos : 0 < cheb cur dst := by
        have := cheb_nonneg (kingStep cur dst) dst
        rw [cheb_kingStep cur dst hcd] at this; omega
      have : 0 < (cheb cur dst).toNat := by omega
      omega
  | succ n ih =>
    by_cases hcd : cur = dst
    · left; refine ⟨?_, hcd⟩; unfold pathFromFuel; simp [hcd]
    · right
      have hstep : cheb (kingStep cur dst) dst = cheb cur dst - 1 :=
        cheb_kingStep cur dst hcd
      have hpos : 0 < cheb cur dst := by
        have := cheb_nonneg (kingStep cur dst) dst; omega
      have hfuel' : (cheb (kingStep cur dst) dst).toNat ≤ n := by rw [hstep]; omega
      have ihrec := ih (kingStep cur dst) hfuel'
      have hpath : pathFromFuel (n + 1) cur dst
          = kingStep cur dst :: pathFromFuel n (kingStep cur dst) dst := by
        show (if cur = dst then [] else
          let nxt := kingStep cur dst; nxt :: pathFromFuel n nxt dst) = _
        rw [if_neg hcd]
      rw [hpath]
      have hadj_start : adjacent cur (kingStep cur dst) := adjacent_kingStep cur dst hcd
      refine ⟨by simp, ?_, ?_, ?_⟩
      · -- head! = kingStep cur dst
        rw [show (kingStep cur dst :: pathFromFuel n (kingStep cur dst) dst).head!
              = kingStep cur dst by simp [List.head!]]
        exact hadj_start
      · -- getLast! = dst
        rcases ihrec with ⟨hempty, heq⟩ | ⟨hne, _, hlast, _⟩
        · -- tail empty ⇒ kingStep cur dst = dst
          rw [hempty]
          rw [show (kingStep cur dst :: ([] : List Coord)).getLast!
                = kingStep cur dst by simp [List.getLast!]]
          exact heq
        · -- tail nonempty ⇒ getLast! of the cons is getLast! of tail
          rw [getLast!_cons_ne (kingStep cur dst) _ hne]
          exact hlast
      · -- consecutive adjacency
        intro i hi
        rcases ihrec with ⟨hempty, _⟩ | ⟨hne, hhead, _, hcons⟩
        · -- tail empty ⇒ list = [kingStep cur dst], no consecutive pair
          rw [hempty] at hi ⊢
          simp only [List.length_cons, List.length_nil] at hi
          omega
        · -- list = kingStep cur dst :: tail with tail nonempty
          cases i with
          | zero =>
            simp only [List.getElem!_cons_zero, List.getElem!_cons_succ]
            rw [getElem!_zero_eq_head! _ hne]
            exact hhead
          | succ j =>
            simp only [List.getElem!_cons_succ]
            simp only [List.length_cons] at hi
            exact hcons j (by omega)

-- mirrors pathfinding.py:65-81 (king-step loop)
theorem pathFrom_valid (start dst : Coord) : ValidKingWalk start dst (pathFrom start dst) := by
  unfold pathFrom
  exact pathFromFuel_valid _ start dst (Nat.le_refl _)

/-! ### Cost role: path length bounded by Manhattan (Chebyshev ≤ Manhattan). -/

/-- Chebyshev never exceeds Manhattan: `max(|Δx|,|Δy|) ≤ |Δx| + |Δy|`.
    -- mirrors pathfinding.py:84 (total_distance) -/
theorem cheb_le_manhattan (start dst : Coord) : cheb start dst ≤ manhattan start dst := by
  unfold cheb manhattan absI
  have h1 := absI_nonneg (dst.1 - start.1)
  have h2 := absI_nonneg (dst.2 - start.2)
  unfold absI at h1 h2
  split <;> split <;> omega

/-- Cost role: the produced path's step count never exceeds the reported Manhattan
    cost (Chebyshev ≤ Manhattan). Ties the path length to the cost metric — not a
    definitional restatement. The literal Python `total_distance = |Δx|+|Δy|` equality
    is enforced by the differential test (Oracle vs Python), not asserted here.
    -- mirrors pathfinding.py:84 (total_distance) -/
theorem pathFrom_cost (start dst : Coord) :
    (pathFrom start dst).length ≤ (manhattan start dst).toNat := by
  rw [pathFrom_len_eq_cheb]
  have hcm := cheb_le_manhattan start dst
  have hcn := cheb_nonneg start dst
  omega

/-! ### Optimality lower bound: every legal king-walk is at least Chebyshev long. -/

/-- For a nonempty walk, the number of consecutive adjacent pairs bounds the
total `cheb` reduction.  We prove a generic statement over a list of coordinates
that forms a king-walk ending at `dst`, by induction on the list. -/
theorem cheb_le_length_of_walk (dst : Coord) :
    ∀ (start : Coord) (p : List Coord),
      (p = [] → start = dst) →
      (p ≠ [] → adjacent start p.head!) →
      (p ≠ [] → p.getLast! = dst) →
      (∀ i, (i + 1 < p.length) → adjacent (p[i]!) (p[i+1]!)) →
      cheb start dst ≤ (p.length : Int) := by
  intro start p
  induction p generalizing start with
  | nil =>
    intro hnil _ _ _
    have : start = dst := hnil rfl
    rw [this, cheb_self]; simp
  | cons a as ih =>
    intro _ hhead hlast hcons
    have hcons_ne : (a :: as) ≠ [] := by simp
    have hadj0 : adjacent start a := by
      have := hhead hcons_ne; simpa using this
    -- step from start to a drops cheb by ≤ 1: cheb start dst - 1 ≤ cheb a dst
    have hdrop : cheb start dst - 1 ≤ cheb a dst := cheb_drop_le_one start a dst hadj0
    by_cases hasnil : as = []
    · -- as empty: a = getLast! = dst, so cheb a dst = 0; length = 1
      subst hasnil
      have ha_dst : a = dst := by
        have := hlast hcons_ne; simpa using this
      rw [ha_dst, cheb_self] at hdrop
      simp only [List.length_cons, List.length_nil]
      omega
    · -- as nonempty: apply IH with start := a
      have hhead' : as ≠ [] → adjacent a as.head! := by
        intro _
        have haspos : 0 < as.length := by
          cases as with
          | nil => exact absurd rfl hasnil
          | cons b bs => simp
        have := hcons 0 (by simp only [List.length_cons]; omega)
        -- (a::as)[0]! = a, (a::as)[1]! = as[0]! = as.head!
        simp only [List.getElem!_cons_zero, List.getElem!_cons_succ] at this
        rw [getElem!_zero_eq_head! as hasnil] at this; exact this
      have hlast' : as ≠ [] → as.getLast! = dst := by
        intro _
        have := hlast hcons_ne
        rw [getLast!_cons_ne a as hasnil] at this
        exact this
      have hcons' : ∀ i, (i + 1 < as.length) → adjacent (as[i]!) (as[i+1]!) := by
        intro i hi
        have := hcons (i + 1) (by simp only [List.length_cons]; omega)
        simpa only [List.getElem!_cons_succ] using this
      have hnil' : as = [] → a = dst := fun h => absurd h hasnil
      have ihres := ih a hnil' hhead' hlast' hcons'
      simp only [List.length_cons]
      omega

theorem kingWalk_len_ge_cheb (start dst : Coord) (p : List Coord)
    (h : ValidKingWalk start dst p) : (cheb start dst).toNat ≤ p.length := by
  have hcheble : cheb start dst ≤ (p.length : Int) := by
    rcases h with ⟨hnil, heq⟩ | ⟨hne, hhead, hlast, hcons⟩
    · apply cheb_le_length_of_walk dst start p
      · intro _; exact heq
      · intro hc; exact absurd hnil hc
      · intro hc; exact absurd hnil hc
      · intro i hi; rw [hnil] at hi; simp at hi
    · apply cheb_le_length_of_walk dst start p
      · intro hc; exact absurd hc hne
      · intro _; exact hhead
      · intro _; exact hlast
      · exact hcons
  -- convert to toNat
  have := cheb_nonneg start dst
  omega

end Formal.CalculatePath
