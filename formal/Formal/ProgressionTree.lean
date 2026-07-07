-- @concept: progression @property: safety, totality, dominance
/-
Formal model of the progression-tree pure cores extracted from
`src/artifactsmmo_cli/ai/tiers/progression_tree_core.py`
(spec docs/superpowers/specs/2026-07-06-progression-tree-design.md).
The Python cores are bound to these semantics by the
PROGRESSION_TREE_MUTATIONS group (unit-killed, formal/diff/mutate.py).

The tree replaces the flat scalar root ranking:

  * trunk    — L10..L50 milestones: `milestonePure level = min 50 ((level/10+1)*10)`
    (exact Nat division, no floats). Proven: the milestone strictly exceeds the
    level below the cap, never exceeds the cap, is band-aligned (`% 10 = 0`),
    and strictly advances when crossed (the trunk-descent measure).
  * branches — one boolean pivot `branchPick`: gear-first until the band's
    loadout is adequate, xp otherwise; gear also yields when it has no
    reachable target. Proven exhaustively (4-row truth table + gear-iff).
  * potion weights — the closed per-effect-family tuning table
    (health 1, boost/resist/antipoison 1/4, unknown 0). Proven: health is
    maximal, unknown is the floor (an unmodeled consumable never outranks).
  * gear argmax — `gearTargetPick` folds the strict preference
    (gain desc, level desc, code asc, slot asc — the Python
    `min(key=(-gain, -level, code, slot))`). Proven: none iff empty input,
    and the pick is always a member of its input.

Non-vacuity anchors: every hypothesis is satisfiable — `milestone_gt_level`
and `milestone_advances` are witnessed at `level = 0` (see the concrete
`example`s below); the truth-table theorems are hypothesis-free `decide`s.

DEFERRED (Phase-2 bar per task brief): `gearTargetPick_perm`
(permutation invariance of the pick). It requires antisymmetry/totality of
the lexicographic `better` order over `Rat × Nat × String × String`, which
balloons in core-only Lean (String order lemmas). The accepted substitute is
`gearTargetPick_mem` + `gearTargetPick_none_iff` here plus the Python
insertion-order unit tests binding the canonical total order.

Lean core only — no mathlib (mathlib is quarantined to Formal/Liveness/).
`omega` handles the min/div-by-10 milestone arithmetic; `decide` closes the
finite truth tables and concrete `Rat` comparisons; the fold proofs mirror
`Formal/BankSelection.lean`'s `bestWeaponFold` membership shapes.
-/

namespace Formal.ProgressionTree

/-! ### Trunk: level milestones -/

def trunkCap : Nat := 50
def band : Nat := 10

/-- Next trunk milestone: `min 50 ((level / 10 + 1) * 10)` (exact Nat
division). Mirrors Python `milestone_pure`. -/
def milestonePure (level : Nat) : Nat :=
  min trunkCap ((level / band + 1) * band)

/-- The milestone strictly exceeds the level below the cap. -/
theorem milestone_gt_level (level : Nat) (h : level < trunkCap) :
    level < milestonePure level := by
  simp only [milestonePure, trunkCap, band] at h ⊢
  omega

/-- The milestone never exceeds the cap. -/
theorem milestone_le_cap (level : Nat) : milestonePure level ≤ trunkCap :=
  Nat.min_le_left _ _

/-- Milestones are band boundaries: divisible by 10. -/
theorem milestone_band_aligned (level : Nat) : milestonePure level % band = 0 := by
  simp only [milestonePure, trunkCap, band]
  omega

/-- Crossing a milestone strictly advances it (trunk descent): at the cap it
is a fixed point; below, reaching the milestone yields a strictly bigger
one. -/
theorem milestone_advances (level : Nat) (h : milestonePure level < trunkCap) :
    milestonePure level < milestonePure (milestonePure level) := by
  simp only [milestonePure, trunkCap, band] at h ⊢
  omega

/-- Concrete anchors (non-vacuity + spot semantics): L0→10, L12→20, L49→50,
and the L50 capstone is the fixed point. -/
example : milestonePure 0 = 10 := by decide
example : milestonePure 12 = 20 := by decide
example : milestonePure 49 = 50 := by decide
example : milestonePure 50 = 50 := by decide

/-! ### Branch pivot: gear | xp -/

inductive Branch
  | gear
  | xp
deriving DecidableEq, Repr

/-- Gear-first until the band's loadout is adequate; then xp to the next
milestone. One boolean pivot — no scalar competition. Gear also yields when
it has no reachable target. Mirrors Python `branch_pick_pure`. -/
def branchPick (bandAdequate gearTargetExists : Bool) : Branch :=
  if !bandAdequate && gearTargetExists then .gear else .xp

/-- Exhaustive truth table (all 4 input rows). -/
theorem branchPick_table :
    branchPick false true = .gear ∧ branchPick false false = .xp ∧
    branchPick true true = .xp ∧ branchPick true false = .xp := by
  decide

/-- Gear is picked IFF gear work exists and the band is not yet adequate. -/
theorem branchPick_gear_iff (a e : Bool) :
    branchPick a e = .gear ↔ (a = false ∧ e = true) := by
  cases a <;> cases e <;> decide

/-! ### Potion-family weights -/

inductive PotionFamily
  | hpRestore
  | boost
  | resist
  | antipoison
  | unknown
deriving DecidableEq, Repr

/-- Per-effect-family consumable weights — the ONLY potion tuning surface in
the gear branch (user decision 2026-07-06: health maximized now, other
families dialed later). Unknown weighs 0: an unmodeled consumable must never
outrank modeled gear. Mirrors Python `potion_type_weight` incl. the
`.get(family, 0)` default. Literals via `mkRat` so `decide` reduction
terminates (same idiom as `Formal/ActionCostNonneg.lean`). -/
def potionWeight : PotionFamily → Rat
  | .hpRestore => 1
  | .boost => mkRat 1 4
  | .resist => mkRat 1 4
  | .antipoison => mkRat 1 4
  | .unknown => 0

/-- Health dominates every family (the user's tuning decision, pinned). -/
theorem potionWeight_health_maximal (f : PotionFamily) :
    potionWeight f ≤ potionWeight .hpRestore := by
  cases f <;> decide

/-- Unknown families never outrank anything: 0 is the floor. -/
theorem potionWeight_unknown_floor (f : PotionFamily) :
    potionWeight .unknown ≤ potionWeight f := by
  cases f <;> decide

/-! ### Gear-branch argmax -/

/-- One upgrade candidate for the gear branch. `gain` is the WEIGHTED value
gain (potion-family weight already applied by the assembler). Mirrors Python
`GearCandidate`. -/
structure GearCand where
  slot : String
  code : String
  gain : Rat
  level : Nat
deriving DecidableEq, Repr

/-- The strict total preference: bigger weighted gain, then higher item
level, then code and slot ascending as pure disambiguators. Mirrors Python's
`min(key=(-gain, -level, code, slot))` lexicographic order. -/
def better (a b : GearCand) : Bool :=
  if a.gain ≠ b.gain then decide (b.gain < a.gain)
  else if a.level ≠ b.level then decide (b.level < a.level)
  else if a.code ≠ b.code then decide (a.code < b.code)
  else decide (a.slot < b.slot)

/-- Fold step: keep the incumbent unless the challenger is strictly better
(first-wins on exact ties, matching Python `min` stability). -/
def pickFold (best : Option GearCand) (c : GearCand) : Option GearCand :=
  match best with
  | none => some c
  | some b => if better c b then some c else some b

/-- Deterministic argmax over the candidates. Mirrors Python
`gear_target_pick`. -/
def gearTargetPick (cs : List GearCand) : Option GearCand :=
  cs.foldl pickFold none

/-- Auxiliary: folding from a `some` accumulator can never return to
`none` — the fold only ever swaps which candidate is held. -/
theorem foldl_pickFold_some (t : List GearCand) :
    ∀ b : GearCand, ∃ c, t.foldl pickFold (some b) = some c := by
  induction t with
  | nil => intro b; exact ⟨b, rfl⟩
  | cons x t ih =>
    intro b
    simp only [List.foldl_cons, pickFold]
    split
    · exact ih x
    · exact ih b

/-- Empty list picks nothing; non-empty always picks (totality). -/
theorem gearTargetPick_none_iff (cs : List GearCand) :
    gearTargetPick cs = none ↔ cs = [] := by
  cases cs with
  | nil => simp [gearTargetPick]
  | cons x t =>
    simp only [gearTargetPick, List.foldl_cons, pickFold]
    obtain ⟨c, hc⟩ := foldl_pickFold_some t x
    simp [hc]

/-- Auxiliary: whatever the fold returns was either the seed accumulator or
a member of the folded list (mirrors `bestWeaponFold_isFighting`'s shape in
`Formal/BankSelection.lean`). -/
theorem foldl_pickFold_mem (l : List GearCand) :
    ∀ (acc : Option GearCand) (c : GearCand),
      l.foldl pickFold acc = some c → acc = some c ∨ c ∈ l := by
  induction l with
  | nil => intro acc c h; exact Or.inl h
  | cons x t ih =>
    intro acc c h
    simp only [List.foldl_cons] at h
    rcases ih (pickFold acc x) c h with hstep | hmem
    · cases acc with
      | none =>
        simp only [pickFold] at hstep
        obtain rfl : x = c := Option.some.inj hstep
        exact Or.inr (List.Mem.head _)
      | some b =>
        simp only [pickFold] at hstep
        split at hstep
        · obtain rfl : x = c := Option.some.inj hstep
          exact Or.inr (List.Mem.head _)
        · exact Or.inl hstep
    · exact Or.inr (List.Mem.tail _ hmem)

/-- SAFETY: the pick is always a member of its input — the argmax never
invents a candidate. -/
theorem gearTargetPick_mem (cs : List GearCand) (c : GearCand)
    (h : gearTargetPick cs = some c) : c ∈ cs := by
  rcases foldl_pickFold_mem cs none c h with hnone | hmem
  · exact nomatch hnone
  · exact hmem

end Formal.ProgressionTree
