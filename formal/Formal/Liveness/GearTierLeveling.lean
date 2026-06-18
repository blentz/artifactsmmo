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

/-! ## The leveling band — why `∀ Int` is the wrong quantifier

A first cut stated the guarantee as `∀ L : Int, ∃ winnable XP-positive m`. That
quantifier is a VACUITY TRAP: `notOverleveled L m = (m.level ≤ L + 2)` is trivial at
large `L`, but `xpPos m` FADES to `false` once the player vastly outlevels a fixed
monster (a level-1 chicken yields 0 XP at player level 1000). So no finite catalog
satisfies the `∀ Int` form — the downstream grounding would be `False → P`, vacuously
inapplicable to every real run.

The char only ever traverses `1 ≤ L < 50` (spawn level ≥ 1, cap 50). Restricting the
hypothesis to that BAND is what makes it both faithful (the gear tiers cover exactly
those levels) and SATISFIABLE — proven by `winnableAcrossBand_satisfiable` below. -/

/-- The level band the char actually traverses: `1 ≤ L < 50`. -/
def InLevelingBand (L : Int) : Prop := 1 ≤ L ∧ L < 50

/-- **The gear-tier winnability guarantee (band-restricted).** At every level the char
    actually reaches, the monster catalog `xs` contains a winnable, XP-positive monster
    under the suicide guard. Faithfully: the bot's gear (crafted up the tiers) always
    makes some window monster beatable across the whole leveling range. (The derivation
    of this from the catalog + crafting recipes — or its statement as a named server
    axiom — is the gear-tier modeling residual; here it is the hypothesis that grounds
    the leveling loop, and it is satisfiable — see `winnableAcrossBand_satisfiable`.) -/
def WinnableAcrossBand (winnable xpPos : WinnableFn) (xs : List Monster) : Prop :=
  ∀ L : Int, InLevelingBand L →
    ∃ m ∈ xs, winnable m = true ∧ xpPos m = true ∧ notOverleveled L m = true

/-- **Anti-vacuity witness.** The band-restricted guarantee is SATISFIABLE: a one-monster
    catalog at level 1 (always winnable, always XP-positive) sits under the suicide guard
    for every band level (`1 ≤ m.level ≤ L + 2` since `L ≥ 1`). This rules out the
    `False → P` reading — the hypothesis the leveling loop leans on is real. -/
theorem winnableAcrossBand_satisfiable :
    ∃ (winnable xpPos : WinnableFn) (xs : List Monster),
      WinnableAcrossBand winnable xpPos xs := by
  refine ⟨fun _ => true, fun _ => true, [{ code := 0, level := 1 }], ?_⟩
  intro L hL
  refine ⟨{ code := 0, level := 1 }, List.mem_singleton.mpr rfl, rfl, rfl, ?_⟩
  obtain ⟨h1, _⟩ := hL
  simp only [notOverleveled, decide_eq_true_eq]
  omega

/-- **Gear-tier winnability ⇒ a combat target exists at every band level.** Direct from
    the picker's anti-livelock headline: a winnable XP-positive monster forces a `some`
    target. So the objective tier always has a Fight to emit — the grounding for
    `objectiveStepFires`/`objectiveStepIsFight`. -/
theorem combatTargetExists_of_gearTier
    (winnable xpPos : WinnableFn) (xs : List Monster)
    (h : WinnableAcrossBand winnable xpPos xs) (L : Int) (hL : InLevelingBand L) :
    ∃ target, pickWinnableWindowed L winnable xpPos xs = some target :=
  pickWinnableWindowed_some_of_winnable_xp_positive L winnable xpPos xs (h L hL)

/-- The combat objective is live at every level below the cap — the leveling range
    `1 ≤ L < 50` is exactly the band, so the grounding holds throughout the trajectory. -/
theorem combatObjective_live_below_fifty
    (winnable xpPos : WinnableFn) (xs : List Monster)
    (h : WinnableAcrossBand winnable xpPos xs) :
    ∀ L : Int, 1 ≤ L → L < 50 →
      ∃ target, pickWinnableWindowed L winnable xpPos xs = some target := by
  intro L hlo hhi
  exact combatTargetExists_of_gearTier winnable xpPos xs h L ⟨hlo, hhi⟩

end Formal.Liveness.GearTierLeveling
