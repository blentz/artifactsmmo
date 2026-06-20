import Formal.Liveness.GameDataFixture
import Formal.CombatTargetExistence
import Formal.Liveness.GearTierLeveling
import Formal.PredictWin
import Mathlib.Tactic

/-! # WinnableGrounded — kernel-prove `WinnableAcrossBand` over the live catalog

`Formal/Liveness/GearTierLeveling.lean` leaves `WinnableAcrossBand` as the
gear-tier winnability HYPOTHESIS that grounds the leveling loop: at every band
level `1 ≤ L < 50` the live monster catalog contains a winnable, XP-positive,
not-overleveled monster. This module DISCHARGES that hypothesis against the
extracted live catalog, kernel-checked.

## What is proven in the kernel vs. pinned by differential

* The combat VERDICT (`Formal.PredictWin.predictWin`, an exact-integer mirror of
  production `predict_win`, itself differential-locked by
  `formal/diff/test_predict_win_diff.py`) is computed IN KERNEL over the witness
  scalars and `decide`d.

* The messy loadout PROJECTION (base stats + summed item stats → the scalar
  inputs `predictWin` takes) is computed in PYTHON by the real production chain
  (`pick_loadout` + `project_loadout_stats`) and emitted into `winnableWitness`
  (`GameDataFixture.lean`). Its fidelity to production is pinned by
  `formal/diff/test_winnable_witness_diff.py`, which re-derives each row's
  projection from `project_loadout_stats` and asserts the verdict equals
  production `is_winnable`. The kernel trusts the projection only as far as that
  differential enforces it — the witness is never hand-massaged.

* Loadout OBTAINABILITY: every witness loadout item has `level ≤ L` (asserted by
  the same differential), and that an obtainable loadout is reachable in the
  planner is Task 3's proven `canonicalPlan` obtainability
  (`gear_obtainable_of_perActionLength_le` in `PlanModel.lean`).

So the witness table is production-faithful by construction+differential, and
THIS module verifies, purely in the kernel, that the witness witnesses
`WinnableAcrossBand` at every band level.

Liveness-tier (imports Mathlib). NO new axioms beyond the standard set + LIV-001
carried by the imports; the band-reduction lemma is `decide`/`omega`, the
per-row verdict is `decide` over integer arithmetic.
-/

set_option maxRecDepth 100000

namespace Formal.Liveness.WinnableGrounded

open Formal.CombatTargetExistence
open Formal.Liveness
open Formal.Liveness.GearTierLeveling
open Formal.Liveness.GameDataFixture
open Formal.PredictWin

/-- The winnability verdict for a witness row: kernel `predictWin` over the
production-projected scalars. -/
def rowWinnable (r : WitnessRow) : Bool :=
  predictWin r.rawPlayer r.pCrit r.monsterHp r.rawMonster r.mCrit r.pMaxHp
    r.pLifesteal r.pAtkSum r.mLifesteal r.mAtkSum r.mPoison r.mBarrier r.mBurn
    r.mHealing r.mReconstitution r.mVoidDrain r.mBerserk r.mFrenzy r.mBubble
    r.pAntipoison r.playerFirst

/-- The witness catalog as abstract `Monster`s: one entry per witness row, the
`code` a stable row index, the `level` the row's winning monster level. Every
entry is a real live-catalog monster (the witness rows come from the production
sweep over `monsterCatalog`). -/
def catalogAsMonsters : List Monster :=
  (winnableWitness.zipIdx).map (fun (r, i) => { code := (i : Int), level := r.monsterLevel })

/-- Winnability predicate over `catalogAsMonsters`: look up the witness row by
the monster's code-index and `decide` the kernel `predictWin` verdict. -/
def winnableConcrete : WinnableFn := fun m =>
  match winnableWitness[m.code.toNat]? with
  | some r => rowWinnable r
  | none => false

/-- XP-positivity over `catalogAsMonsters`. Every witness row is, by
construction, the XP-positive winner the production picker chose (the witness
builder filters on `xp_per_kill > 0`, differential-pinned), so a monster present
in the witness catalog is XP-positive. -/
def xpPosConcrete : WinnableFn := fun m =>
  match winnableWitness[m.code.toNat]? with
  | some _ => true
  | none => false

/-- The abstract monster carried by witness row `i` in `catalogAsMonsters`. -/
def witnessMonster (r : WitnessRow) (i : Nat) : Monster :=
  { code := (i : Int), level := r.monsterLevel }

/-- Per-row band witness, stated over the SAME `winnableConcrete`/`xpPosConcrete`
/`notOverleveled` the theorem uses, so the single `decide` also closes the
witness↔catalog binding. Checks: the rows are in level order (`r.level = i+1`),
and at the row's own level the row's monster is winnable, XP-positive, and not
overleveled. -/
def rowWitnessesBand (r : WitnessRow) (i : Nat) : Bool :=
  decide (r.level = (i : Int) + 1)
    && winnableConcrete (witnessMonster r i)
    && xpPosConcrete (witnessMonster r i)
    && notOverleveled r.level (witnessMonster r i)

/-- Every witness row witnesses its own band condition — the single `decide`
over the 49-row table. The per-row `predictWin` integer arithmetic over the 49
rows is a finite, fully-determined Boolean evaluation (an exact-integer function,
no `Float`, no `Classical`); we discharge it by the kernel `decide` (no
`native_decide`, so the no-sorry gate stays green and no `Lean.ofReduceBool`
axiom is introduced). -/
theorem all_rows_witness_band :
    (winnableWitness.zipIdx.all (fun (r, i) => rowWitnessesBand r i)) = true := by
  decide

/-- Membership-aware extraction: every entry of `winnableWitness.zipIdx` satisfies
`rowWitnessesBand`. -/
theorem rowWitnessesBand_of_mem (r : WitnessRow) (i : Nat)
    (h : (r, i) ∈ winnableWitness.zipIdx) :
    rowWitnessesBand r i = true := by
  have hall := all_rows_witness_band
  rw [List.all_eq_true] at hall
  exact hall (r, i) h

/-! ## The grounded theorem. -/

/-- **`WinnableAcrossBand` discharged over the live catalog.** At every band
level `1 ≤ L < 50` the witness catalog contains a winnable, XP-positive,
not-overleveled monster — the witness row whose `level = L`. The winnability is
the kernel `predictWin` verdict over production-projected scalars
(differential-pinned), so this is a faithful grounding of the gear-tier
hypothesis, not a re-derivation of `pick_loadout`. -/
theorem winnableAcrossBand_grounded :
    WinnableAcrossBand winnableConcrete xpPosConcrete catalogAsMonsters := by
  intro L hL
  -- The witness row witnessing L sits at index L.toNat - 1 (rows in level order).
  obtain ⟨hlo, hhi⟩ := hL
  set i : Nat := L.toNat - 1 with hi
  -- Index i is in range (0 ≤ i < 49 = length).
  have hlen : winnableWitness.length = 49 := by decide
  have hirange : i < winnableWitness.length := by rw [hlen, hi]; omega
  -- The membership of (row, i) in zipIdx.
  have hmem : (winnableWitness[i]'hirange, i) ∈ winnableWitness.zipIdx :=
    List.mem_zipIdx_iff_getElem?.mpr (List.getElem?_eq_getElem hirange)
  have hband := rowWitnessesBand_of_mem _ _ hmem
  -- Unpack the conjunction.
  unfold rowWitnessesBand at hband
  simp only [Bool.and_eq_true, decide_eq_true_eq] at hband
  obtain ⟨⟨⟨hlvl, hwin⟩, hxp⟩, hnotover⟩ := hband
  -- The witness monster is the existential.
  refine ⟨witnessMonster (winnableWitness[i]'hirange) i, ?_, hwin, hxp, ?_⟩
  · -- membership in catalogAsMonsters.
    unfold catalogAsMonsters witnessMonster
    rw [List.mem_map]
    exact ⟨(winnableWitness[i]'hirange, i),
      List.mem_zipIdx_iff_getElem?.mpr (List.getElem?_eq_getElem hirange), rfl⟩
  · -- notOverleveled L m: r.level = i+1 = L, and the row is not overleveled at r.level.
    have hLeq : (i : Int) + 1 = L := by rw [hi]; omega
    unfold notOverleveled witnessMonster at hnotover ⊢
    rw [decide_eq_true_eq] at hnotover ⊢
    -- hnotover : monsterLevel ≤ r.level + 2, hlvl : r.level = i+1, hLeq : i+1 = L.
    rw [hlvl, hLeq] at hnotover
    omega

end Formal.Liveness.WinnableGrounded
