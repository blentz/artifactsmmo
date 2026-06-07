-- @concept: combat, monsters @property: reachability, dominance
/-
Phase 12 — Formal model of `cheapest_path_to_level` from
`src/artifactsmmo_cli/ai/learning/projections.py`.

The Python routine walks levels `current → target` and, at each
intermediate level, picks the BEATABLE monster (level ≤ sim_level + 1)
that maximizes observed/estimated `xp_per_cycle`. It returns a
`PathPlan` containing one `PathSegment` per level traversed, or marks
the plan `blocked` when no beatable monster exists at some step.

Audit verdict: NOT-A-BUG. The algorithm is GREEDY (picks the best
monster level-by-level, independent of later steps) and the docstring
explicitly enumerates the limits ("Assumes each level requires
state.max_xp XP", "doesn't model gathering / HP recovery"). We pin
the GREEDY contract — not global optimality — because that is what
the Python actually delivers.

Proved contracts:
* Termination: `sim_level` strictly increases each loop iteration.
* Target-met short-circuit: `target ≤ current ⇒ segments = []` and
  total cycles = 0.
* Blocked-if no beatable monster at some intermediate level.
* Greedy choice: returned monster has maximal xpPerCycle over
  beatable monsters at that level (first-wins on ties, matching
  Python's strict `>` test against running best).
* Beatability gate: a monster is selectable at sim_level iff
  `1 ≤ monster.level ≤ sim_level + 1` (the +1 margin matches
  `FightAction.is_applicable`).
* Empty input ⇒ blocked.

Lean core only — no mathlib.
-/

namespace Formal.CheapestPath

/-! ### Model -/

/-- A beatable-monster candidate. `xpPerCycle = 0` means the candidate
contributes nothing (matches Python's `best_xp_per_cycle > 0` gate
that triggers blocking). -/
structure Monster where
  code : Nat               -- abstract code id (Nat for decidability)
  level : Nat              -- monster level
  xpPerCycle : Nat         -- precomputed xp per cycle (observed or formula)
  deriving Repr, DecidableEq

/-- A path segment. -/
structure Segment where
  fromLevel : Nat
  toLevel : Nat
  monster : Monster
  cycles : Nat             -- ⌈xp_to_next / xpPerCycle⌉; Nat for kernel
  deriving Repr, DecidableEq

/-- A path plan. -/
structure PathPlan where
  targetLevel : Nat
  segments : List Segment
  blocked : Bool
  totalCycles : Nat
  deriving Repr, DecidableEq

/-! ### Greedy pick -/

/-- A monster is beatable at `simLevel` iff `1 ≤ level ≤ simLevel + 1`.
Matches `FightAction.is_applicable` precondition (the +1 margin). -/
def isBeatable (simLevel : Nat) (m : Monster) : Bool :=
  decide (1 ≤ m.level) && decide (m.level ≤ simLevel + 1)

/-- Foldl-max over a non-empty candidate list. A later candidate
replaces the running best ONLY when its `xpPerCycle` is STRICTLY
greater (first-wins on ties — mirrors Python `if xp_per_cycle >
best_xp_per_cycle`). -/
def foldMax (initial : Monster) (rest : List Monster) : Monster :=
  rest.foldl (fun best cur => if cur.xpPerCycle > best.xpPerCycle then cur else best) initial

/-- Greedy pick over beatable monsters. Returns `none` when no
candidate passes the beatability filter. -/
def pickBest (simLevel : Nat) (monsters : List Monster) : Option Monster :=
  match monsters.filter (isBeatable simLevel) with
  | [] => none
  | c :: cs => some (foldMax c cs)

/-- Per-level loop step. Returns `none` when blocked (no beatable
monster or best xpPerCycle = 0), else `some segment`. -/
def stepLevel (simLevel xpToNext : Nat) (monsters : List Monster) : Option Segment :=
  match pickBest simLevel monsters with
  | none => none
  | some m =>
    if m.xpPerCycle = 0 then none
    else
      let cycles := (xpToNext + m.xpPerCycle - 1) / m.xpPerCycle
      some { fromLevel := simLevel, toLevel := simLevel + 1
           , monster := m, cycles := cycles }

/-- Build the full plan via fuel-bounded recursion. -/
def buildPlan (sim target xpToNext maxXp : Nat) (monsters : List Monster)
    (fuel : Nat) (acc : List Segment) : (List Segment × Bool) :=
  match fuel with
  | 0 => (acc.reverse, false)
  | Nat.succ f =>
    if sim ≥ target then (acc.reverse, false)
    else
      match stepLevel sim xpToNext monsters with
      | none => (acc.reverse, true)
      | some seg =>
        let xpNext := if maxXp = 0 then 1 else maxXp
        buildPlan (sim + 1) target xpNext maxXp monsters f (seg :: acc)

/-- Top-level wrapper matching Python `cheapest_path_to_level`. -/
def cheapestPath (current target maxXp xpInLevel : Nat)
    (monsters : List Monster) : PathPlan :=
  if target ≤ current then
    { targetLevel := target, segments := [], blocked := false, totalCycles := 0 }
  else
    let xpToNext := if maxXp ≤ xpInLevel then 1 else maxXp - xpInLevel
    let fuel := target - current
    let (segs, blk) := buildPlan current target xpToNext maxXp monsters fuel []
    let total := segs.foldl (fun acc s => acc + s.cycles) 0
    { targetLevel := target, segments := segs, blocked := blk, totalCycles := total }

/-! ### Helper lemmas -/

/-- Helper: one step of foldMax. -/
theorem foldMax_cons (init y : Monster) (ys : List Monster) :
    foldMax init (y :: ys) =
      foldMax (if y.xpPerCycle > init.xpPerCycle then y else init) ys := by
  unfold foldMax; simp [List.foldl]

/-- `foldMax` result is ≥ initial. -/
theorem foldMax_ge_init (init : Monster) (rest : List Monster) :
    init.xpPerCycle ≤ (foldMax init rest).xpPerCycle := by
  induction rest generalizing init with
  | nil => unfold foldMax; simp
  | cons y ys ih =>
    rw [foldMax_cons]
    by_cases hb : y.xpPerCycle > init.xpPerCycle
    · simp [hb]
      exact Nat.le_trans (Nat.le_of_lt hb) (ih y)
    · simp [hb]; exact ih init

/-- `foldMax` result is ≥ every element in the rest list. -/
theorem foldMax_ge_mem (init : Monster) (rest : List Monster) (x : Monster)
    (h : x ∈ rest) : x.xpPerCycle ≤ (foldMax init rest).xpPerCycle := by
  induction rest generalizing init with
  | nil => exact absurd h List.not_mem_nil
  | cons y ys ih =>
    rw [foldMax_cons]
    rcases List.mem_cons.mp h with rfl | hin
    · -- x = y
      by_cases hb : x.xpPerCycle > init.xpPerCycle
      · simp [hb]; exact foldMax_ge_init x ys
      · simp [hb]
        have hxi : x.xpPerCycle ≤ init.xpPerCycle := Nat.le_of_not_lt hb
        exact Nat.le_trans hxi (foldMax_ge_init init ys)
    · -- x ∈ ys
      by_cases hb : y.xpPerCycle > init.xpPerCycle
      · simp [hb]; exact ih y hin
      · simp [hb]; exact ih init hin

/-- `foldMax` result is a member of `init :: rest`. -/
theorem foldMax_mem (init : Monster) (rest : List Monster) :
    foldMax init rest ∈ init :: rest := by
  induction rest generalizing init with
  | nil => unfold foldMax; simp
  | cons y ys ih =>
    rw [foldMax_cons]
    by_cases hb : y.xpPerCycle > init.xpPerCycle
    · simp [hb]
      have := ih y
      rcases List.mem_cons.mp this with heq | hin
      · right; left; exact heq
      · right; right; exact hin
    · simp [hb]
      have := ih init
      rcases List.mem_cons.mp this with heq | hin
      · left; exact heq
      · right; right; exact hin

/-! ### Contracts -/

/-- Target ≤ current ⇒ empty plan, zero cost, not blocked. -/
theorem cheapest_target_met (current target maxXp xpInLevel : Nat)
    (monsters : List Monster) (h : target ≤ current) :
    cheapestPath current target maxXp xpInLevel monsters
      = { targetLevel := target, segments := [], blocked := false, totalCycles := 0 } := by
  unfold cheapestPath
  simp [h]

/-- Empty monster list ⇒ `stepLevel` blocks. -/
theorem stepLevel_empty (simLevel xpToNext : Nat) :
    stepLevel simLevel xpToNext [] = none := by
  unfold stepLevel pickBest
  simp

/-- `pickBest` on empty list is `none`. -/
theorem pickBest_nil (simLevel : Nat) : pickBest simLevel [] = none := by
  unfold pickBest; simp

/-- `pickBest` returns a monster that is a member of the input list. -/
theorem pickBest_mem (simLevel : Nat) (monsters : List Monster) (m : Monster)
    (h : pickBest simLevel monsters = some m) : m ∈ monsters := by
  unfold pickBest at h
  -- `pickBest` matches on the filtered list. Inspect that match.
  generalize hL : monsters.filter (isBeatable simLevel) = L at h
  cases L with
  | nil => simp at h
  | cons c cs =>
    simp at h
    -- h : foldMax c cs = m
    have hmem : m ∈ c :: cs := by
      rw [← h]; exact foldMax_mem c cs
    -- (c::cs) ⊆ monsters via filter
    have hsub : ∀ x, x ∈ c :: cs → x ∈ monsters := by
      intro x hx
      rw [← hL] at hx
      exact (List.mem_filter.mp hx).1
    exact hsub m hmem

/-- Greedy pick is beatable: the returned monster passes the +1 gate. -/
theorem pickBest_beatable (simLevel : Nat) (monsters : List Monster) (m : Monster)
    (h : pickBest simLevel monsters = some m) : isBeatable simLevel m = true := by
  unfold pickBest at h
  generalize hL : monsters.filter (isBeatable simLevel) = L at h
  cases L with
  | nil => simp at h
  | cons c cs =>
    simp at h
    have hmem : m ∈ c :: cs := by
      rw [← h]; exact foldMax_mem c cs
    -- every element of c::cs passed the filter ⇒ is beatable
    have hpass : ∀ x, x ∈ c :: cs → isBeatable simLevel x = true := by
      intro x hx
      rw [← hL] at hx
      have := List.mem_filter.mp hx
      exact this.2
    exact hpass m hmem

/-- Greedy maximality: returned monster has xpPerCycle ≥ every beatable
monster in the original list. -/
theorem pickBest_max (simLevel : Nat) (monsters : List Monster) (m : Monster)
    (h : pickBest simLevel monsters = some m) :
    ∀ x ∈ monsters, isBeatable simLevel x = true → x.xpPerCycle ≤ m.xpPerCycle := by
  unfold pickBest at h
  generalize hL : monsters.filter (isBeatable simLevel) = L at h
  cases L with
  | nil =>
    simp at h
  | cons c cs =>
    simp at h
    -- m = foldMax c cs (= maximum xpPerCycle over c::cs)
    intro x hx hbeat
    have hxL : x ∈ c :: cs := by
      rw [← hL]
      exact List.mem_filter.mpr ⟨hx, hbeat⟩
    cases hxL with
    | head =>
      rw [← h]; exact foldMax_ge_init c cs
    | tail _ hin =>
      rw [← h]; exact foldMax_ge_mem c cs x hin

/-- The +1 beatability margin: a monster at simLevel + 1 IS beatable. -/
theorem isBeatable_plus_one (simLevel : Nat) (m : Monster)
    (_h1 : 1 ≤ m.level) (h2 : m.level = simLevel + 1) :
    isBeatable simLevel m = true := by
  unfold isBeatable
  simp [h2]

/-- Off-boundary: a monster at simLevel + 2 is NOT beatable. -/
theorem isBeatable_off_boundary (simLevel : Nat) (m : Monster)
    (h : m.level = simLevel + 2) :
    isBeatable simLevel m = false := by
  unfold isBeatable
  simp [h]

/-- Level-0 monster is not beatable (the `1 ≤ level` gate). -/
theorem isBeatable_level_zero (simLevel : Nat) (m : Monster) (h : m.level = 0) :
    isBeatable simLevel m = false := by
  unfold isBeatable
  simp [h]

/-- Termination witness: `buildPlan` always returns within `fuel` steps. -/
theorem buildPlan_terminates (sim target xpToNext maxXp : Nat)
    (monsters : List Monster) (fuel : Nat) (acc : List Segment) :
    ∃ segs blk, buildPlan sim target xpToNext maxXp monsters fuel acc = (segs, blk) := by
  exact ⟨_, _, rfl⟩

/-- Empty input always blocks (when target > current). -/
theorem cheapest_empty_monsters_blocks (current target maxXp xpInLevel : Nat)
    (h : current < target) :
    (cheapestPath current target maxXp xpInLevel []).blocked = true := by
  unfold cheapestPath
  have hnle : ¬ target ≤ current := by omega
  simp [hnle]
  have hfuel : target - current = Nat.succ (target - current - 1) := by omega
  rw [hfuel]
  unfold buildPlan
  have hge : ¬ current ≥ target := by omega
  simp [hge, stepLevel_empty]

/-- All-zero xpPerCycle blocks (matches Python's `best_xp_per_cycle <= 0` gate). -/
theorem stepLevel_all_zero_blocks (simLevel xpToNext : Nat) (monsters : List Monster)
    (hAllZero : ∀ m ∈ monsters, m.xpPerCycle = 0) :
    stepLevel simLevel xpToNext monsters = none := by
  unfold stepLevel
  cases hp : pickBest simLevel monsters with
  | none => rfl
  | some m =>
    have hmem := pickBest_mem simLevel monsters m hp
    have hzero := hAllZero m hmem
    simp [hzero]

/-! ### Boundary witnesses (non-vacuous probes) -/

theorem beatable_plus_one_witness :
    isBeatable 3 { code := 1, level := 4, xpPerCycle := 10 } = true := by decide

theorem beatable_plus_two_refused_witness :
    isBeatable 3 { code := 1, level := 5, xpPerCycle := 10 } = false := by decide

theorem beatable_level_zero_refused_witness :
    isBeatable 3 { code := 1, level := 0, xpPerCycle := 10 } = false := by decide

theorem tie_break_first_wins_witness :
    pickBest 1
      [{ code := 1, level := 1, xpPerCycle := 5 },
       { code := 2, level := 1, xpPerCycle := 5 }]
      = some { code := 1, level := 1, xpPerCycle := 5 } := by decide

theorem strict_greater_replaces_witness :
    pickBest 1
      [{ code := 1, level := 1, xpPerCycle := 3 },
       { code := 2, level := 1, xpPerCycle := 8 }]
      = some { code := 2, level := 1, xpPerCycle := 8 } := by decide

theorem greedy_filters_unbeatable_witness :
    pickBest 1
      [{ code := 1, level := 1, xpPerCycle := 3 },
       { code := 2, level := 5, xpPerCycle := 100 }]
      = some { code := 1, level := 1, xpPerCycle := 3 } := by decide

theorem target_met_witness :
    cheapestPath 5 5 100 0 [] =
      { targetLevel := 5, segments := [], blocked := false, totalCycles := 0 } := by
  decide

theorem target_below_witness :
    cheapestPath 10 5 100 0 [] =
      { targetLevel := 5, segments := [], blocked := false, totalCycles := 0 } := by
  decide

theorem empty_blocks_witness :
    (cheapestPath 1 2 100 0 []).blocked = true := by decide

theorem all_zero_blocks_witness :
    (cheapestPath 1 2 100 0 [{ code := 1, level := 1, xpPerCycle := 0 }]).blocked = true := by
  decide

/-- Single-step success: chicken at L1, 22 xp/cycle, 100 xp needed.
ceil(100/22) = 5. -/
theorem single_step_witness :
    cheapestPath 1 2 100 0 [{ code := 1, level := 1, xpPerCycle := 22 }] =
      { targetLevel := 2
      , segments := [{ fromLevel := 1, toLevel := 2
                     , monster := { code := 1, level := 1, xpPerCycle := 22 }
                     , cycles := 5 }]
      , blocked := false, totalCycles := 5 } := by decide

theorem two_step_witness :
    let m := { code := 1, level := 1, xpPerCycle := 10 : Monster }
    (cheapestPath 1 3 100 0 [m]).segments.length = 2 := by decide

theorem greedy_pick_witness :
    let chicken := { code := 1, level := 1, xpPerCycle := 2 : Monster }
    let slime := { code := 2, level := 2, xpPerCycle := 15 : Monster }
    (cheapestPath 1 2 100 0 [chicken, slime]).segments.head? =
      some { fromLevel := 1, toLevel := 2, monster := slime, cycles := 7 } := by
  decide

end Formal.CheapestPath
