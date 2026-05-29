/-
Formal model of the **Action.apply baseline-preservation** contract.

# Bug fixed (REAL BUG #5)

Pre-fix, 21+ of the 26 concrete `Action.apply` methods constructed a NEW
`WorldState(field=…, field=…, …)` listing only the fields the action mutates.
The dataclass-based `WorldState` carries eight server-snapshot stat-baseline
fields with `field(default_factory=…)` defaults; the explicit constructor calls
**silently dropped** them, so the planner saw `attack={}`, `skill_xp={}`,
`resistance={}`, `dmg=0`, `wisdom=0`, `critical_strike=0`, `initiative=0`,
`dmg_elements={}` after Move/Equip/Fight/…  Probe-verified for Move and Equip
in the pre-fix tree.

The baseline fields are SERVER-COMPUTED snapshots (post-equipment); the bot's
GOAP planner has no authority to recompute them locally. Hypothetical loadout
projections for combat planning go through the separate `project_loadout_stats`
mechanism (`equipment/projection.py`) which returns a `ProjectedStats`
dataclass — not a `WorldState`. Therefore the correct contract is:

  ∀ s. ∀ action. apply(s) preserves the 8 baseline fields of s.

# Lean model

We model a minimal `WorldState` carrying ONLY the 8 baseline stat fields
(dicts represented as association lists `List (String × Nat)`; scalars as
`Nat`/`Int`) plus a handful of "mutable" fields used by representative actions
(`x`, `y`, `gold`, `hp`, `inventory`).

Three representative apply functions cover the structural buckets:
* `moveApply` — pure-mutable: only `x`, `y` change.
* `equipApply` — inventory + equipment rearrangement (modeled as `inventory`).
* `claimApply` — inventory grows (a pending item materialized).

Each is implemented as a record `with`-update touching ONLY its mutable
fields; the baseline fields are untouched syntactically. The preservation
property is then trivial by `rfl` per-field.

Lean core only — no mathlib. Axioms ⊆ {propext, Classical.choice, Quot.sound}.
-/

namespace Formal.ApplyBaseline

/-- Minimal Python-faithful `WorldState` carrying the 8 baseline stat fields
    plus the representative mutable fields used by the modeled actions. -/
structure WorldState where
  -- mutable (action-touched) fields
  x         : Int
  y         : Int
  gold      : Int
  hp        : Nat
  inventory : List (String × Nat)
  -- the 8 baseline stat fields (server-snapshot, must be preserved)
  attack          : List (String × Nat)
  dmg             : Int
  dmg_elements    : List (String × Nat)
  resistance      : List (String × Nat)
  critical_strike : Nat
  initiative      : Nat
  wisdom          : Nat
  skill_xp        : List (String × Nat)
  deriving Repr, DecidableEq

/-! ## Baseline-preservation predicate

The 8-conjunct property: post-apply state's baseline fields are pointwise
equal to pre-apply state's baseline fields. -/

def preservesBaseline (s s' : WorldState) : Prop :=
  s.attack          = s'.attack          ∧
  s.dmg             = s'.dmg             ∧
  s.dmg_elements    = s'.dmg_elements    ∧
  s.resistance      = s'.resistance      ∧
  s.critical_strike = s'.critical_strike ∧
  s.initiative      = s'.initiative      ∧
  s.wisdom          = s'.wisdom          ∧
  s.skill_xp        = s'.skill_xp

/-- Reflexivity: every state preserves its own baseline. -/
theorem preservesBaseline_refl (s : WorldState) : preservesBaseline s s := by
  unfold preservesBaseline
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-- Transitivity. -/
theorem preservesBaseline_trans {a b c : WorldState}
    (hab : preservesBaseline a b) (hbc : preservesBaseline b c) :
    preservesBaseline a c := by
  unfold preservesBaseline at *
  refine ⟨?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_⟩
  · exact hab.1.trans hbc.1
  · exact hab.2.1.trans hbc.2.1
  · exact hab.2.2.1.trans hbc.2.2.1
  · exact hab.2.2.2.1.trans hbc.2.2.2.1
  · exact hab.2.2.2.2.1.trans hbc.2.2.2.2.1
  · exact hab.2.2.2.2.2.1.trans hbc.2.2.2.2.2.1
  · exact hab.2.2.2.2.2.2.1.trans hbc.2.2.2.2.2.2.1
  · exact hab.2.2.2.2.2.2.2.trans hbc.2.2.2.2.2.2.2

/-! ## Representative `apply` functions

Each modeled as a record `with`-update touching ONLY its declared mutable
fields. Compare against the Python refactor target:
`dataclasses.replace(state, <only-the-fields-this-action-mutates>)`. -/

/-- `MoveAction.apply` model: only `x` and `y` change. -/
def moveApply (s : WorldState) (newX newY : Int) : WorldState :=
  { s with x := newX, y := newY }

/-- `EquipAction.apply` model: only `inventory` changes (equipment field
    elided in this minimal model — the contract is the same: baseline fields
    untouched). -/
def equipApply (s : WorldState) (newInv : List (String × Nat)) : WorldState :=
  { s with inventory := newInv }

/-- `ClaimPendingItemAction.apply` model: inventory grows by one item. -/
def claimApply (s : WorldState) (newInv : List (String × Nat)) : WorldState :=
  { s with inventory := newInv }

/-! ## Per-action preservation theorems -/

theorem moveApply_preserves_baseline (s : WorldState) (newX newY : Int) :
    preservesBaseline s (moveApply s newX newY) := by
  unfold preservesBaseline moveApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem equipApply_preserves_baseline (s : WorldState) (newInv : List (String × Nat)) :
    preservesBaseline s (equipApply s newInv) := by
  unfold preservesBaseline equipApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem claimApply_preserves_baseline (s : WorldState) (newInv : List (String × Nat)) :
    preservesBaseline s (claimApply s newInv) := by
  unfold preservesBaseline claimApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-! ## Headline: the uniform contract holds across all modeled actions.

Quantifies over a finite enumeration of the modeled `apply` functions so a
single statement seals the property for every modeled action. -/

/-- Enumeration of the modeled apply functions, parametrized over their inputs.
    Each constructor packs the action + its arguments. -/
inductive ModeledApply where
  | move  (newX newY : Int) : ModeledApply
  | equip (newInv : List (String × Nat)) : ModeledApply
  | claim (newInv : List (String × Nat)) : ModeledApply

/-- Dispatch: run the action on a state. -/
def ModeledApply.run (a : ModeledApply) (s : WorldState) : WorldState :=
  match a with
  | .move  x y     => moveApply s x y
  | .equip inv     => equipApply s inv
  | .claim inv     => claimApply s inv

/-- **Headline**: every modeled apply preserves the baseline. -/
theorem headline_preserves_baseline (s : WorldState) (a : ModeledApply) :
    preservesBaseline s (a.run s) := by
  cases a with
  | move  x y   => exact moveApply_preserves_baseline s x y
  | equip inv   => exact equipApply_preserves_baseline s inv
  | claim inv   => exact claimApply_preserves_baseline s inv

/-! ## Non-vacuity witnesses

Concrete states + apply → result with the 8 fields preserved. These pin the
property is real, not vacuously true via an unsatisfiable hypothesis. -/

/-- Sample state with NON-ZERO baseline fields (mirrors the probe-witness
    state from the differential test). -/
def witnessState : WorldState :=
  { x := 0, y := 0, gold := 100, hp := 50, inventory := [("sword", 1)]
  , attack          := [("fire", 30)]
  , dmg             := 15
  , dmg_elements    := [("fire", 10)]
  , resistance      := [("fire", 5)]
  , critical_strike := 10
  , initiative      := 5
  , wisdom          := 12
  , skill_xp        := [("alchemy", 4500)] }

/-- Witness: Move from (0,0) to (1,0) preserves the baseline of `witnessState`. -/
example :
    preservesBaseline witnessState (moveApply witnessState 1 0) := by
  exact moveApply_preserves_baseline witnessState 1 0

/-- Witness: an Equip update preserves the baseline of `witnessState`. -/
example :
    preservesBaseline witnessState (equipApply witnessState []) := by
  exact equipApply_preserves_baseline witnessState []

/-- Witness: a Claim update preserves the baseline of `witnessState`. -/
example :
    preservesBaseline witnessState (claimApply witnessState [("sword", 1), ("gold_ring", 1)]) := by
  exact claimApply_preserves_baseline witnessState [("sword", 1), ("gold_ring", 1)]

/-- Witness: the mutable fields ACTUALLY change (so the theorem is not vacuous
    by `s = s'`). -/
example : (moveApply witnessState 1 0).x ≠ witnessState.x := by decide

end Formal.ApplyBaseline
