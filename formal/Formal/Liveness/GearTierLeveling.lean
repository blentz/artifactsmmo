import Formal.CombatTargetExistence
import Formal.Liveness.FightReady
import Mathlib.Tactic

/-! # GearTierLeveling — grounding the combat objective in gear-tier winnability (O5.2 part 2)

`FightReady` (the bank-independent leveling invariant) needs the perception inputs
`objectiveStepFires` / `objectiveStepIsFight` true: the objective tier emits a Fight
step. In production that holds exactly when the combat picker finds a target — and the
picker finds one iff a WINNABLE, XP-positive monster exists under the suicide guard
(`CombatTargetExistence.pickWinnableWindowed_some_of_winnable_xp_positive`).

The GEAR-TIER guarantee is that such a monster exists AT EVERY LEVEL: as the bot
gathers/crafts up the gear tiers, its winnability window always contains a beatable
XP-positive monster (gear targets "self-unlock as gear/level improve" — objective.py).
This module states that guarantee (`WinnableAtEveryLevel`) and proves it grounds
combat-target existence at every level, reusing the existing picker machinery.

The residual is the O5.4 BINDING: the liveness `State.objectiveStepFires` /
`objectiveStepIsFight` opaque bools equal "the objective tier's picker returns a Fight
target." That binding (and the catalog/recipe derivation of `WinnableAtEveryLevel`
itself) is the cycle-step SELECT differential — stated here as the named obligation.

NO new axioms (standard set + LIV-001 via the imports).
-/

namespace Formal.Liveness.GearTierLeveling

open Formal.CombatTargetExistence

/-- **The gear-tier winnability guarantee.** At every player level, the monster
    catalog `xs` contains a winnable, XP-positive monster under the suicide guard.
    Faithfully: the bot's gear (crafted up the tiers) always makes some window monster
    beatable. (The derivation of this from the catalog + crafting recipes — or its
    statement as a named server axiom — is the gear-tier modeling residual; here it is
    the hypothesis that grounds the leveling loop.) -/
def WinnableAtEveryLevel (winnable xpPos : WinnableFn) (xs : List Monster) : Prop :=
  ∀ L : Int, ∃ m ∈ xs, winnable m = true ∧ xpPos m = true
                        ∧ notOverleveled L m = true

/-- **Gear-tier winnability ⇒ a combat target exists at every level.** Direct from the
    picker's anti-livelock headline: a winnable XP-positive monster forces a `some`
    target. So the objective tier always has a Fight to emit — the grounding for
    `objectiveStepFires`/`objectiveStepIsFight`. -/
theorem combatTargetExists_of_gearTier
    (winnable xpPos : WinnableFn) (xs : List Monster)
    (h : WinnableAtEveryLevel winnable xpPos xs) (L : Int) :
    ∃ target, pickWinnableWindowed L winnable xpPos xs = some target :=
  pickWinnableWindowed_some_of_winnable_xp_positive L winnable xpPos xs (h L)

/-- The combat objective is live at every level below the cap — restated for the
    leveling range `1 ≤ L < 50`. -/
theorem combatObjective_live_below_fifty
    (winnable xpPos : WinnableFn) (xs : List Monster)
    (h : WinnableAtEveryLevel winnable xpPos xs) :
    ∀ L : Int, 1 ≤ L → L < 50 →
      ∃ target, pickWinnableWindowed L winnable xpPos xs = some target := by
  intro L _ _
  exact combatTargetExists_of_gearTier winnable xpPos xs h L

end Formal.Liveness.GearTierLeveling
