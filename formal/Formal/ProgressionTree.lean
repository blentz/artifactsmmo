-- @concept: progression @property: safety, totality, dominance
/-
Formal model of the progression-tree pure cores extracted from
`src/artifactsmmo_cli/ai/tiers/progression_tree_core.py`
(spec docs/superpowers/specs/2026-07-06-progression-tree-design.md).
The Python cores are bound to these semantics by the
PROGRESSION_TREE_MUTATIONS group (unit-killed, formal/diff/mutate.py).

The tree replaced the flat scalar root ranking. WAVE 3a replaced the tree's own
scored/branching layer with the five-node resolution walk in
`ai/decisions/root.py`, and WAVE 3b deleted what that left with no Python
mirror: `branchPick` (the boolean gear|xp pivot and its 4-row truth table),
`inductive Branch`, and `gearTargetPick`/`focusAgingPick` (the gear argmax and
its aging composition). What is modelled here is what the walk actually runs:

  * trunk    — L10..L50 milestones: `milestonePure level = min 50 ((level/10+1)*10)`
    (exact Nat division, no floats). Proven: the milestone strictly exceeds the
    level below the cap, never exceeds the cap, is band-aligned (`% 10 = 0`),
    and strictly advances when crossed (the trunk-descent measure).
  * potion weights — the closed per-effect-family tuning table
    (health 1, boost/resist/antipoison 1/4, unknown 0). Proven: health is
    maximal, unknown is the floor (an unmodeled consumable never outranks).

PHASE 4-2b-ii deleted the focus-aging half: `falloff`, the d'Hondt step
(`dhondtStep`/`dhondtStepKey`/`selectMax`), its fold `interleaveDue` and the
liveness-tier no-starvation proof over it (`Formal/Liveness/
InterleaveNoStarvation.lean`). The walk holds no history now; the intention's
cycle budget and one-turn yield (`ai/intention_progress.py`,
`GamePlayer._track_intention`) answer the starvation the interleave scheduled.

Non-vacuity anchors: every hypothesis is satisfiable — `milestone_gt_level`
and `milestone_advances` are witnessed at `level = 0` (see the concrete
`example`s below); the truth-table theorems are hypothesis-free `decide`s.

Lean core only — no mathlib (mathlib is quarantined to Formal/Liveness/).
`omega` handles the min/div-by-10 milestone arithmetic; `decide` closes the
finite truth tables.
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

end Formal.ProgressionTree
