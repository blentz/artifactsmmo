import Formal.Liveness.FightReady
import Formal.Liveness.BlockerMonotone
import Formal.Liveness.CumulativeProgress

/-! # FightReadyReach — reaching `FightReady` from spawn (level-50 #2, Phase A)

The capstone `ai_reaches_level_fifty` rests on one open `GlobalInvariants` field,
`hfightFires`, which `ai_reaches_level_fifty_of_fightReady` discharges once a
`FightReady` state is reached. This module builds the STRUCTURAL backbone of that
reach (Phase A of `docs/PLAN_fightready_reach.md`):

* `reach_and` — the missing max-of-bounds COMBINATOR: if a persistent predicate
  `P` holds at some step and a persistent `Q` holds at some step, both hold
  simultaneously at `max` of the two bounds. The 7 model blocker-clears
  (`hp = maxHp`, the six opaque flags) are persistent (`BlockerMonotone`), so
  this folds their individual reach bounds into one common `K`.

* `FightReadyCore` — `FightReady` minus the two perception fields
  (`objectiveStepFires` / `objectiveStepIsFight`), i.e. exactly the conditions
  the pure `cycleStep` model can establish on its own (`SettledReach` proves the
  perception fields are NOT model-producible).

* `fightReady_reachable_of_seeds` — the assembly: a reached `FightReadyCore` plus
  the perception hypothesis `hperc` yields a reached `FightReady`. The perception
  hypothesis is the O5.4 SELECT-side obligation, kept explicit and separate.

Phase B (the dynamics) discharges the per-seed reaches and `TaskParked`
reach/persistence that build the `FightReadyCore` reach via `reach_and`.

Core only — no mathlib; LIV-001 enters only through imports.
-/

namespace Formal.Liveness.FightReadyReach

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.Liveness.GameDataInvariance
open Formal.Liveness.Leveling
open Formal.Liveness.FightReady
open Formal.Liveness.BlockerMonotone

/-- **The simultaneous-quieting combinator.** For predicates `P`, `Q` that are
PERSISTENT under `cycleStepN` (once true at a state, true at every later state —
the shape of every `BlockerMonotone` lemma), if each is reached from `s` by some
step count, then BOTH hold at the single step `max kP kQ`. This is the
max-of-bounds bookkeeping the warm-up needs to turn per-seed reach bounds into a
common `K`. -/
theorem reach_and {P Q : State → Prop} (s : State)
    (hPpersist : ∀ (n : Nat) (s' : State), P s' → P (cycleStepN n s'))
    (hQpersist : ∀ (n : Nat) (s' : State), Q s' → Q (cycleStepN n s'))
    (hP : ∃ k, P (cycleStepN k s)) (hQ : ∃ k, Q (cycleStepN k s)) :
    ∃ k, P (cycleStepN k s) ∧ Q (cycleStepN k s) := by
  obtain ⟨kP, hkP⟩ := hP
  obtain ⟨kQ, hkQ⟩ := hQ
  refine ⟨max kP kQ, ?_, ?_⟩
  · have hsplit : max kP kQ = kP + (max kP kQ - kP) := by omega
    rw [hsplit, cycleStepN_add]
    exact hPpersist _ _ hkP
  · have hsplit : max kP kQ = kQ + (max kP kQ - kQ) := by omega
    rw [hsplit, cycleStepN_add]
    exact hQpersist _ _ hkQ

/-- `FightReady` minus the two PERCEPTION fields — the conditions the pure
`cycleStep` model can establish itself (the seven model blocker-clears + the
parked task). `SettledReach` proves `objectiveStepFires`/`objectiveStepIsFight`
are NOT model-producible, so they are excluded here and supplied separately. -/
structure FightReadyCore (s : State) : Prop where
  hpFull         : s.hp = s.maxHp
  overstock      : s.hasOverstockItems = false
  deposits       : s.selectBankDepositsNonempty = false
  gear           : s.gearReviewFires = false
  potions        : s.craftPotionsFires = false
  pending        : s.pendingItemsNonempty = false
  sellable       : s.sellableInventoryNonempty = false
  craft          : s.craftReliefFires = false
  recycleNonempty : s.recyclableSurplusNonempty = false
  parked         : TaskParked s

/-- Conjunction of two persistent predicates is persistent. -/
theorem persist_and {P Q : State → Prop}
    (hP : ∀ (n : Nat) (s' : State), P s' → P (cycleStepN n s'))
    (hQ : ∀ (n : Nat) (s' : State), Q s' → Q (cycleStepN n s')) :
    ∀ (n : Nat) (s' : State), (P s' ∧ Q s') →
      (P (cycleStepN n s') ∧ Q (cycleStepN n s')) :=
  fun n s' h => ⟨hP n s' h.1, hQ n s' h.2⟩

/-- **The combinator fold (Phase-A structural #5).** Given that each of the
seven model blocker-clear seeds (`hp = maxHp` and the six opaque flags) is
REACHED from `s`, and that `TaskParked` is both reached (`hpark`) and persistent
(`hparkP` — a Phase-B obligation), `reach_and` folds them into a single step `K`
at which `FightReadyCore` holds. The seven flag/hp persistences are the proven
`BlockerMonotone` halves; only the per-seed REACHES (`hhp`..`hcraft`, `hpark`)
and `TaskParked` persistence remain for Phase B's dynamics. -/
theorem fightReadyCore_reachable_of_seeds (s : State)
    (hhp : ∃ k, (cycleStepN k s).hp = (cycleStepN k s).maxHp)
    (hover : ∃ k, (cycleStepN k s).hasOverstockItems = false)
    (hdep : ∃ k, (cycleStepN k s).selectBankDepositsNonempty = false)
    (hgear : ∃ k, (cycleStepN k s).gearReviewFires = false)
    (hpotions : ∃ k, (cycleStepN k s).craftPotionsFires = false)
    (hpend : ∃ k, (cycleStepN k s).pendingItemsNonempty = false)
    (hsell : ∃ k, (cycleStepN k s).sellableInventoryNonempty = false)
    (hcraft : ∃ k, (cycleStepN k s).craftReliefFires = false)
    (hrecycle : ∃ k, (cycleStepN k s).recyclableSurplusNonempty = false)
    (hpark : ∃ k, TaskParked (cycleStepN k s))
    (hparkP : ∀ (n : Nat) (s' : State), TaskParked s' → TaskParked (cycleStepN n s')) :
    ∃ K, FightReadyCore (cycleStepN K s) := by
  have pHp := hp_eq_maxHp_cycleStepN
  have pOver := hasOverstockItems_false_cycleStepN
  have pDep := selectBankDeposits_false_cycleStepN
  have pGear := gearReviewFires_false_cycleStepN
  have pPend := pendingItems_false_cycleStepN
  have pSell := sellable_false_cycleStepN
  have pCraft := craftReliefFires_false_cycleStepN
  have pRecycle := recyclableSurplusNonempty_false_cycleStepN
  have c1 := reach_and s pHp pOver hhp hover
  have c2 := reach_and s (persist_and pHp pOver) pDep c1 hdep
  have c3 := reach_and s (persist_and (persist_and pHp pOver) pDep) pGear c2 hgear
  have c4 := reach_and s (persist_and (persist_and (persist_and pHp pOver) pDep) pGear)
    pPend c3 hpend
  have c5 := reach_and s
    (persist_and (persist_and (persist_and (persist_and pHp pOver) pDep) pGear) pPend)
    pSell c4 hsell
  have c6 := reach_and s
    (persist_and (persist_and (persist_and (persist_and (persist_and pHp pOver) pDep)
      pGear) pPend) pSell)
    pCraft c5 hcraft
  have c7 := reach_and s
    (persist_and (persist_and (persist_and (persist_and (persist_and (persist_and pHp pOver)
      pDep) pGear) pPend) pSell) pCraft)
    pRecycle c6 hrecycle
  have c8 := reach_and s
    (persist_and (persist_and (persist_and (persist_and (persist_and (persist_and
      (persist_and pHp pOver) pDep) pGear) pPend) pSell) pCraft) pRecycle)
    hparkP c7 hpark
  have pPotions := craftPotionsFires_false_cycleStepN
  have c9 := reach_and s
    (persist_and (persist_and (persist_and (persist_and (persist_and (persist_and
      (persist_and (persist_and pHp pOver) pDep) pGear) pPend) pSell) pCraft) pRecycle) hparkP)
    pPotions c8 hpotions
  obtain ⟨K, ⟨⟨⟨⟨⟨⟨⟨⟨⟨hp, hov⟩, hde⟩, hge⟩, hpe⟩, hse⟩, hcr⟩, hre⟩, hpa⟩, hpo⟩⟩ := c9
  exact ⟨K, { hpFull := hp, overstock := hov, deposits := hde, gear := hge,
              potions := hpo, pending := hpe, sellable := hse, craft := hcr,
              recycleNonempty := hre, parked := hpa }⟩

/-- **The Phase-A assembly.** A reached `FightReadyCore` (the model-provable
warm-up, built in Phase B via `reach_and`) together with the perception
hypothesis `hperc` (the O5.4 SELECT-side obligation: a committed combat objective
holds at every step) yields a reached `FightReady`. Composing this with
`ai_reaches_level_fifty_of_fightReady` closes the spawn → level-50 chain modulo
the warm-up and perception. -/
theorem fightReady_reachable_of_seeds (s : State)
    (hwarm : ∃ K, FightReadyCore (cycleStepN K s))
    (hperc : ∀ k, (cycleStepN k s).objectiveStepFires = true
                ∧ (cycleStepN k s).objectiveStepIsFight = true) :
    ∃ K, FightReady (cycleStepN K s) := by
  obtain ⟨K, hcore⟩ := hwarm
  exact ⟨K, { hpFull := hcore.hpFull, overstock := hcore.overstock,
              deposits := hcore.deposits, gear := hcore.gear,
              potions := hcore.potions,
              pending := hcore.pending, sellable := hcore.sellable,
              craft := hcore.craft, recycleNonempty := hcore.recycleNonempty,
              parked := hcore.parked,
              objFires := (hperc K).1, objFight := (hperc K).2 }⟩

/-- **Spawn → level-50, modulo the warm-up + perception.** Composes the Phase-A
assembly with the proven `ai_reaches_level_fifty_of_fightReady`. Phase B replaces
`hwarm` with a discharged reach; `hperc` remains the O5.4 obligation. -/
theorem ai_reaches_level_fifty_from_spawn_warmup (s : State)
    (htec : s.taskExchangeMinCoins > 0) (hnec : s.nextExpansionCost > 0)
    (hwarm : ∃ K, FightReadyCore (cycleStepN K s))
    (hperc : ∀ k, (cycleStepN k s).objectiveStepFires = true
                ∧ (cycleStepN k s).objectiveStepIsFight = true) :
    ∃ k, (cycleStepN k s).level ≥ 50 := by
  obtain ⟨K, hFR⟩ := fightReady_reachable_of_seeds s hwarm hperc
  obtain ⟨j, hj⟩ := ai_reaches_level_fifty_of_fightReady (cycleStepN K s)
    (by rw [cycleStepN_taskExchangeMinCoins_invariant]; exact htec)
    (by rw [cycleStepN_nextExpansionCost_invariant]; exact hnec) hFR
  exact ⟨K + j, by rw [cycleStepN_add]; exact hj⟩

end Formal.Liveness.FightReadyReach
