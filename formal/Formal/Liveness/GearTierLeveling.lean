import Formal.CombatTargetExistence
import Formal.GearObjectiveWalk
import Formal.LivenessChain
import Mathlib.Tactic

/-! # GearTierLeveling — the combat objective below the cap, over the gear objective

`FightReady` (the bank-independent leveling invariant) needs the perception inputs
`objectiveStepFires` / `objectiveStepIsFight`. In production (spec 2026-10-18 §2.4,
ruling C4-b) the objective tier is the gear objective `(L*, m*)` read by the root
walk's entry `WhichPieceIsNext` and the grind target `farm_target`. The chain has
two halves:

* **`L*` held** — the root is one more character level and the grind target is
  `m*`, so the objective step fights `m*` (`fight_armed_of_held`, composed with
  `LivenessChain.chain_emits_fight_when_target_exists_and_applicable` in
  `held_objective_emits_fight`);
* **`L*` not held** — no fight is chosen for XP (`no_xp_fight_of_not_held`) and
  the root is the step of the first missing piece the cycle serves
  (`piece_root_of_not_held`), or no root when every missing piece is declined
  (`no_root_when_every_piece_declined`).

Both halves are bound to production by `formal/diff/test_gear_objective_arming_diff.py`,
which drives the live `attach_gear_objective` / `farm_target` / `resolve_root` /
`WhichPieceIsNext` / `piece_step` on the scenario bundle.

The catalogue guarantee `WinnableAcrossBand` says a winnable, XP-positive monster
under the suicide guard exists at every band level for the band's WITNESS loadout.
Production's gear objective reads its own predicate instead: a `_candidates` monster
whose `L*` fighter wins at the real state with `R > 0`. `ObjectiveCovers` is the
hypothesis that such a candidate gives production an objective whose `m*` is one
(bound by a bundle differential); `objective_of_winning_candidate` applies it. The
transfer from the catalogue witness to a winning `L*` at a real state is NOT proved
here: it is a named residual of `LevelFiftyReachableP`.

Plan C Task 4 retired the windowed-picker grounding this module used to carry
(`combatTargetExists_of_gearTier`: the deleted picker returned `some` target):
production no longer fights a winnable monster for XP while a piece of `L*` is
missing, so a picker-existence claim was a guarantee about code the bot no
longer runs.

NO new axioms (standard set + LIV-001 via the imports).
-/

namespace Formal.Liveness.GearTierLeveling

open Formal.CombatTargetExistence
open Formal.GearObjectiveWalk
open Formal.LivenessChain
open Formal.ActionApplicability

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
    under the suicide guard — a candidate for the gear objective's `m*`. Discharged over
    the live catalog by `WinnableGrounded.winnableAcrossBand_grounded`. -/
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

/-! ## The held half, end to end -/

/-- **The held half, end to end.** A held objective's grind target is dispatched to
    `GrindCharacterXP` and, the fight being applicable, the chain emits a fight on
    `m*` (`LivenessChain`). -/
theorem held_objective_emits_fight (o : ObjectiveView) (bootstrapLevel : Int)
    (fi : FightInputs) (hheld : o.held = true) (hApp : fightApplicable fi = true) :
    chainEmitsFight { pathTarget := some o.monster, pathHeld := o.held,
                      fightInputs := fi, bootstrapLevel := bootstrapLevel }
      false none = some o.monster :=
  chain_emits_fight_when_target_exists_and_applicable _ o.monster rfl hheld hApp

/-! ## The link: a winning candidate gives production a gear objective

`ObjectiveCovers` is a HYPOTHESIS about production at ONE state (ruling C4-R2), stated
over production's own predicates and monster codes:

* `cands` — `gear_objective._candidates` (real monster codes: the level ceiling,
  positive XP, a reachable spawn, not party-only);
* `fighterWins c` — the `L*(c)` fighter at this state wins against `c`
  (`drop_fight_winnable` on `_targets`' fighter, the gate `_rated` applies);
* `ratePos c` — the candidate's rate `R(c)` (`_rated`) is positive;
* `objective` — production's `gear_objective` at this state.

The hypothesis: if some candidate's fighter wins with `R > 0`, the objective exists,
is well formed, and its `m*` is such a candidate. Production: `gear_objective`
returns None only when no rated candidate has `R > 0`, and `m*` is the max-`R`
rated candidate. Bound by `formal/diff/test_gear_objective_link_diff.py`, which
evaluates exactly these predicates on the scenario bundle.

NOT claimed: that the catalogue's band witness (`WinnableAcrossBand`, a witness
row's own loadout over `catalogAsMonsters`) makes the antecedent true at a real
state. That transfer — catalogue witness to an achievable `L*` — is a named
residual of `LevelFiftyReachableP` (the same gear-progress gap as the not-held
phase): a naked level-41 character has no winning candidate and no objective,
while the band witness exists.

Satisfiable (`objectiveCovers_satisfiable`) and not trivially true
(`not_objectiveCovers_of_none`). -/

/-- The production link at one state (a hypothesis, bound by the differential). -/
def ObjectiveCovers (cands : List Int) (fighterWins ratePos : Int → Bool)
    (objective : Option ObjectiveView) : Prop :=
  (∃ c ∈ cands, fighterWins c = true ∧ ratePos c = true) →
    ∃ o, objective = some o ∧ WellFormed o ∧ o.monster ∈ cands ∧
      fighterWins o.monster = true ∧ ratePos o.monster = true

/-- **Production's objective at a state with a winning candidate.** This is the
    hypothesis `hcov` applied to `hwin`; the last two conjuncts are definitional
    (`grindTarget` is `m*` exactly while `L*` is held), restated so the two halves of
    the root walk read off the same objective. -/
theorem objective_of_winning_candidate
    (cands : List Int) (fighterWins ratePos : Int → Bool)
    (objective : Option ObjectiveView)
    (hcov : ObjectiveCovers cands fighterWins ratePos objective)
    (hwin : ∃ c ∈ cands, fighterWins c = true ∧ ratePos c = true) :
    ∃ o, objective = some o ∧ WellFormed o ∧ o.monster ∈ cands ∧
      fighterWins o.monster = true ∧ ratePos o.monster = true ∧
      (o.held = true → grindTarget o = some o.monster) ∧
      (o.held = false → grindTarget o = none) := by
  obtain ⟨o, hat, hwf, hm, hw, hr⟩ := hcov hwin
  exact ⟨o, hat, hwf, hm, hw, hr, fun hh => (fight_armed_of_held o (fun _ => true) hh).2,
    no_xp_fight_of_not_held o⟩

/-- The link is satisfiable, with its antecedent true. -/
theorem objectiveCovers_satisfiable :
    ∃ (cands : List Int) (fighterWins ratePos : Int → Bool)
      (objective : Option ObjectiveView),
      (∃ c ∈ cands, fighterWins c = true ∧ ratePos c = true) ∧
      ObjectiveCovers cands fighterWins ratePos objective := by
  refine ⟨[5], fun _ => true, fun _ => true, some ⟨5, true, []⟩,
    ⟨5, List.mem_singleton.mpr rfl, rfl, rfl⟩, ?_⟩
  intro _
  exact ⟨⟨5, true, []⟩, rfl, by simp [WellFormed], List.mem_singleton.mpr rfl, rfl, rfl⟩

/-- The link is not trivially true: a winning candidate and no objective violate it. -/
theorem not_objectiveCovers_of_none :
    ¬ ObjectiveCovers [5] (fun _ => true) (fun _ => true) none := by
  intro hcov
  obtain ⟨o, hat, _⟩ := hcov ⟨5, List.mem_singleton.mpr rfl, rfl, rfl⟩
  exact absurd hat (by simp)

/-! ## Non-vacuity of the end-to-end held half -/

/-- The held half's end-to-end hypotheses are jointly satisfiable. -/
theorem held_objective_emits_fight_nonvacuous :
    chainEmitsFight
      { pathTarget := some witnessHeld.monster, pathHeld := witnessHeld.held,
        bootstrapLevel := 6,
        fightInputs := { hasLocations := true, inventoryFree := 1, hp := 100,
                         maxHp := 100, playerLevel := 5, monsterLevel := 5,
                         minFreeSlots := 1, xpPerKill := 10 } }
      false none = some 7 :=
  held_objective_emits_fight witnessHeld 6 _ rfl (by decide)

end Formal.Liveness.GearTierLeveling
