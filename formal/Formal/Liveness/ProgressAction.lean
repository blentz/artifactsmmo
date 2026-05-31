/-
  Formal.Liveness.ProgressAction

  Phase-19c headline. Packages the four Tier-1 progress actions —
  Fight, Gather, Deposit, Rest — into a single sum type
  `ProgressAction` and proves a uniform measure-decrease theorem
  `step_decreases_measure` by case analysis, delegating to the per-action
  lemmas in `FightProgress`, `GatherProgress`, `DepositProgress`,
  `RestProgress`.

  ## Scope (HONEST disclosure)

  Out-of-scope actions for Tier 1: Move, Equip, Withdraw, Craft, NpcBuy,
  NpcSell, TaskAccept, TaskCancel, TaskTrade, ClaimPending, and any other
  action whose `apply` PRESERVES the measure (does not strictly decrease
  it). These are not deadlock-inducing — Phase 20 will prove that — but
  they are not Tier-1 progress witnesses.

  ## `validInvariants` — honest disclosure

  `validInvariants s a` packages the per-action load-bearing hypotheses
  beyond raw applicability. Each branch is a NON-VACUOUS proposition with
  a documented discharge plan:

    * `fight ml be matchesTask`:
        `s.level < 50 ∧ s.xp < xpToNextLevel s.level`
      — the perception invariant disclosed in `FightProgress`. Discharge:
        Phase 22 cycle model.
    * `gather skillReq minFree drop skill`:
        `s.targetSkillXp > s.projectedSkillXpDelta ∧ skill.isSome`
      — productivity guard. Discharge: planner-side (a LevelSkillGoal is
        active and a skill-bearing resource was selected).
    * `deposit accessible nonempty depositCount`:
        `depositCount > 0 ∧ s.inventoryUsed ≥ depositCount ∧
         s.inventoryUsed > bankPressureThreshold s.inventoryMax`
      — productivity guards. Discharge: production invariant
        (`select_bank_deposits` returns held items only; Deposit is
        selected as a guard at the 80 % pressure threshold).
    * `rest`:
        `True` — `restIsApplicable` alone suffices.

  Liveness namespace — Mathlib axioms allowed.
-/
import Formal.Liveness.Measure
import Formal.Liveness.FightProgress
import Formal.Liveness.GatherProgress
import Formal.Liveness.DepositProgress
import Formal.Liveness.RestProgress

set_option linter.dupNamespace false

namespace Formal.Liveness.ProgressAction

open Formal.Liveness.Measure
open Formal.Liveness.FightProgress
open Formal.Liveness.GatherProgress
open Formal.Liveness.DepositProgress
open Formal.Liveness.RestProgress

/-! ## Sum type over Tier-1 progress actions -/

/-- A Tier-1 progress action. Constructor parameters mirror the per-action
    lemma signatures. -/
inductive ProgressAction where
  | fight   (monsterLevel bestEquip : Nat) (matchesTask : Bool)
  | gather  (skillReq : Option (String × Nat)) (minFree : Nat)
            (drop : String) (skill : Option String)
  | deposit (accessible nonempty : Bool) (depositCount : Nat)
  | rest

/-- Dispatch `apply` to the per-action model. -/
def applyAction (s : State) : ProgressAction → State
  | .fight _ _ m         => fightApply s m
  | .gather _ _ d sk     => gatherApply s d sk
  | .deposit _ _ n       => depositApply s n
  | .rest                => restApply s

/-- Dispatch `is_applicable` to the per-action guard. -/
def actionIsApplicable (s : State) : ProgressAction → Bool
  | .fight ml be _       => fightIsApplicable s ml be
  | .gather req mf _ _   => gatherIsApplicable s req mf
  | .deposit a n _       => depositIsApplicable s a n
  | .rest                => restIsApplicable s

/-- Per-action load-bearing hypotheses (NON-VACUOUS — see module
    docstring). The constructor `vi_*` is the witness; each demands a
    concrete proposition whose discharge is documented above. -/
def validInvariants (s : State) : ProgressAction → Prop
  | .fight _ _ _         => s.level < 50 ∧ s.xp < xpToNextLevel s.level
  | .gather _ _ _ skill  => s.targetSkillXp > s.projectedSkillXpDelta
                            ∧ skill.isSome
  | .deposit _ _ n       => n > 0 ∧ s.inventoryUsed ≥ n
                            ∧ s.inventoryUsed > bankPressureThreshold s.inventoryMax
  | .rest                => True

/-! ## Headline theorem -/

/--
  **Every applicable Tier-1 action with its productivity invariants
  satisfied strictly decreases the lex measure.**

  Case analysis delegates to the per-action lemmas (`fight_decreases_measure`,
  `gather_decreases_measure`, `deposit_decreases_measure`,
  `rest_decreases_measure`).

  Honest disclosure:
    * `validInvariants` is not vacuous — each branch carries the
      productivity hypotheses load-bearing in the corresponding
      per-action lemma. See module docstring for the discharge plan
      per case.
    * Actions outside `ProgressAction` (Move, Equip, ...) are out of
      scope here. They preserve the measure; their non-decrease is not
      a deadlock — Phase 20 must show the planner cannot select them
      indefinitely.
-/
theorem step_decreases_measure
    (s : State) (a : ProgressAction)
    (happ : actionIsApplicable s a = true)
    (hinv : validInvariants s a) :
    measureLt (Measure.measure (applyAction s a)) (Measure.measure s) := by
  cases a with
  | fight ml be matchesTask =>
    -- hinv : s.level < 50 ∧ s.xp < xpToNextLevel s.level
    obtain ⟨hlvl, hxpInv⟩ := hinv
    exact fight_decreases_measure s ml be matchesTask happ hlvl hxpInv
  | gather skillReq minFree drop skill =>
    -- hinv : s.targetSkillXp > s.projectedSkillXpDelta ∧ skill.isSome
    obtain ⟨hprog, hskill⟩ := hinv
    exact gather_decreases_measure s skillReq minFree drop skill
            happ hprog hskill
  | deposit accessible nonempty depositCount =>
    -- hinv : depositCount > 0 ∧ s.inventoryUsed ≥ depositCount
    --        ∧ s.inventoryUsed > bankPressureThreshold s.inventoryMax
    obtain ⟨hcount, hbound, hpressure⟩ := hinv
    exact deposit_decreases_measure s accessible nonempty depositCount
            happ hcount hbound hpressure
  | rest =>
    exact rest_decreases_measure s happ

end Formal.Liveness.ProgressAction
