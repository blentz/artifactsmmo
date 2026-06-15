import Formal.Liveness.LevelFiftyReachable
import Formal.Liveness.GameDataInvariance

/-! # Obligation-5 increment: discharge hex / hbe from spawn config-positivity

`ai_reaches_level_fifty` requires `GlobalInvariants s`, a bundle of five
trajectory-quantified hypotheses. TWO of them — `hex` (taskExchange ⇒
taskExchangeMinCoins > 0) and `hbe` (bankExpand ⇒ nextExpansionCost > 0) — are
discharged here from a single SPAWN-LEVEL fact each:

`taskExchangeMinCoins` and `nextExpansionCost` are config fields that `cycleStepN`
never mutates (`GameDataInvariance.hex_propagation` / `hbe_propagation`), so
positive-at-spawn ⇒ positive at every reachable state ⇒ the conditional `hex`/`hbe`
hold unconditionally.

GlobalInvariants thereby reduces from 5 trajectory hypotheses to
{hnowait, hperc, hfightFires} + two simple spawn positivity facts. The remaining
three (the no-productive-wait, perception, and fight-fairness obligations) are the
genuine runtime gaps — see docs/PLAN_obligation5_scope.md (O5.1 / O5.2 / O5.3-hperc).
-/

namespace Formal.Liveness.ReducedReachability

open Formal.Liveness.LevelFiftyReachable
open Formal.Liveness.GameDataInvariance
open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress

/-- **hex/hbe discharged.** Level-50 reachability needing only spawn
config-positivity (`taskExchangeMinCoins > 0`, `nextExpansionCost > 0`) in place
of the trajectory-quantified `hex`/`hbe` fields of `GlobalInvariants`. The other
three obligations (`hnowait`, `hperc`, `hfightFires`) are passed through
unchanged. -/
theorem ai_reaches_level_fifty_config_positive (s : State)
    (htec : s.taskExchangeMinCoins > 0) (hnec : s.nextExpansionCost > 0)
    (hnowait : ∀ k, productionLadder (cycleStepN k s) ≠ some .wait)
    (hperc : ∀ k k', productionLadder (cycleStepN k s) = some k' →
              (k' = .bankUnlock ∨ k' = .reachUnlockLevel) →
              (cycleStepN k s).xp < xpToNextLevel (cycleStepN k s).level
              ∧ (cycleStepN k s).level < 50)
    (hfightFires : ∀ N, ∃ k ≥ N,
        productionLadder (cycleStepN k s) = some .bankUnlock
        ∨ productionLadder (cycleStepN k s) = some .reachUnlockLevel) :
    ∃ k, (cycleStepN k s).level ≥ 50 :=
  ai_reaches_level_fifty s
    { hnowait := hnowait
      hex := fun k _ => hex_propagation s htec k
      hbe := fun k _ => hbe_propagation s hnec k
      hperc := hperc
      hfightFires := hfightFires }

end Formal.Liveness.ReducedReachability
