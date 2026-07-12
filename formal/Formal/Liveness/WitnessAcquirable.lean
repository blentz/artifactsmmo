import Formal.Liveness.WinnableGrounded

/-! # WitnessAcquirable — C1b: the witness gear is provably OBTAINABLE

`docs/PLAN_c2_composed_liveness.md` Phase C1. `WinnableGrounded` proved a
winnable target exists at every band level — under `pick_loadout` over the
OPTIMISTIC pool (`obtainable_inventory_for_level`: every equippable with
`level ≤ L`; its docstring names acquirability as the open Task-3/corner-3
residual). This module discharges that residual against the live fixture:

* `acquirableCert` (generated) is a Python-computed code set; `certClosed`
  kernel-VERIFIES its defining property — every cert code is a source leaf
  (resource drop or catalog-monster drop) or has a recipe whose ingredients
  are all in the cert. A wrong cert cannot prove (certificate pattern).
* `acquirableWitness` (generated) is the SAME production sweep as
  `winnableWitness`, restricted to the cert pool: every row's loadout is
  closure-obtainable by the gather/fight/craft loop, and the row's kernel
  `predictWin` verdict still holds (`acquirable_rows_winnable`).
* `acquirableFrontier = []` — EMPTY since the P1 multi-drop closure
  (docs/PLAN_engagement_expansion.md): gem stones are gatherable secondary
  drops of ordinary rocks, which closes the jewelry/obsidian/gold recipe
  families and with them every band. The historical frontier ([38] before
  P1) is preserved in git history; `acquirableFrontier_empty` pins the
  closure so any regeneration that REOPENS a frontier is a visible,
  theorem-breaking change.

Skill gates (gather/craft levels) are deliberately outside the closure: the
proven skill-grind liveness (the LevelSkill action path, `SkillGapClosure`)
makes any skill level eventually reachable, so they gate TIME, not
acquirability. Drop RATES
likewise (eventual acquirability; `MonsterDropApply` covers the loop's drop
application).

Differential: `formal/diff/test_witness_acquirable_diff.py` recomputes the
cert, the filtered sweep, and the frontier from the snapshot and pins all
three emitted tables. Liveness namespace — Mathlib allowed; no new axioms. -/

set_option maxRecDepth 8192

namespace Formal.Liveness.WitnessAcquirable

open Formal.Liveness.GameDataFixture
open Formal.Liveness.RecipeChainClosure
open Formal.Liveness.WinnableGrounded

/-- A code is a SOURCE leaf: dropped by a gatherable resource or a catalog
    monster. -/
def sourceLeaf (c : String) : Bool :=
  gatherableItems.contains c || monsterDropItems.contains c

/-- One cert entry is justified: a source leaf, or crafted from cert codes. -/
def certEntryOk (c : String) : Bool :=
  sourceLeaf c ||
    match allRecipes.find? (fun r => r.output == c) with
    | some r => r.ingredients.all (fun p => acquirableCert.contains p.1)
    | none => false

set_option maxHeartbeats 4000000 in
/-- **Certificate soundness** — the kernel verifies the closure property of
    the generated cert: every entry is a source leaf or crafted entirely from
    cert entries. -/
theorem certClosed : acquirableCert.all certEntryOk = true := by decide

/-- Every acquirable-witness loadout item is in the (kernel-verified) cert. -/
theorem acquirable_loadouts_in_cert :
    acquirableWitness.all
      (fun r => r.loadoutCodes.all (fun c => acquirableCert.contains c)) = true := by
  decide

/-- Every acquirable-witness row still WINS: the kernel `predictWin` verdict
    holds over the restricted-pool projection scalars (same `rowWinnable` as
    the optimistic table). -/
theorem acquirable_rows_winnable :
    acquirableWitness.all rowWinnable = true := by decide

/-- **Band coverage modulo the named frontier**: every band level in [1, 49]
    is covered by an acquirable-witness row, or is in `acquirableFrontier`
    (= [38], the event-gated band). -/
theorem acquirable_covers_band :
    (List.range 49).all (fun i =>
      acquirableWitness.any (fun r => r.level == (i : Int) + 1)
      || acquirableFrontier.contains ((i : Int) + 1)) = true := by
  decide

/-- The frontier is EMPTY — every band level has a provably-acquirable winning
    loadout. Stated explicitly so a regeneration that reopens a frontier is a
    VISIBLE, theorem-breaking change, not a silent one. -/
theorem acquirableFrontier_empty : acquirableFrontier = [] := by decide

end Formal.Liveness.WitnessAcquirable
