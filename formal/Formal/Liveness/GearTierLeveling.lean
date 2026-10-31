import Formal.CombatTargetExistence
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

The GEAR-TIER guarantee that the objective has a monster at all is
`WinnableAcrossBand`: at every level the character reaches, a winnable,
XP-positive monster under the suicide guard exists — a candidate for `m*`
(`gear_objective._candidates` asks exactly the level ceiling and positive XP, and
`_rated` the win). `combatObjective_live_below_fifty` composes it with the held half:
at every band level some candidate exists whose held objective arms its fight.

Plan C Task 4 retired the windowed-picker grounding this module used to carry
(`combatTargetExists_of_gearTier`: the deleted picker returned `some` target):
production no longer fights a winnable monster for XP while a piece of `L*` is
missing, so a picker-existence claim was a guarantee about code the bot no
longer runs.

NO new axioms (standard set + LIV-001 via the imports).
-/

namespace Formal.Liveness.GearTierLeveling

open Formal.CombatTargetExistence
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

/-! ## The gear objective and its root walk

`ObjectiveView` is the part of production's `GearObjective` the walk reads: `m*`
(`monster`), whether `L*` is held (`held`), and the missing pieces in pursuit order
(`missing`, piece codes). Production's `GearObjective.held` is `not missing`
(`gear_objective_result.py`), which `WellFormed` states. -/

/-- The gear objective as the root walk reads it. -/
structure ObjectiveView where
  monster : Int
  held    : Bool
  missing : List Int
  deriving Repr, DecidableEq

/-- `held` exactly when no piece is missing (production: `held = not missing`). -/
def WellFormed (o : ObjectiveView) : Prop := o.held = true ↔ o.missing = []

/-- The root `WhichPieceIsNext` resolves to (no fleet pieces). -/
inductive Root
  | levelUp
  | piece (code : Int)
  deriving Repr, DecidableEq

/-- `WhichPieceIsNext.resolve` with no fleet pieces: no objective is the wall
    (`none`); `L*` held is one more level (`none` at the cap, `next_level`); otherwise
    the first missing piece, in `missing`'s order, whose step the cycle serves
    (`RootWalk.serves`), or `none` when every one is declined. -/
def whichPieceIsNext (o : Option ObjectiveView) (serves : Int → Bool) (atCap : Bool) :
    Option Root :=
  match o with
  | none => none
  | some o =>
    if o.held then (if atCap then none else some .levelUp)
    else (o.missing.find? serves).map Root.piece

/-- The grind target `farm_target` names with no task held and no fleet piece
    waiting: the two-arm cascade on `m*`. -/
def grindTarget (o : ObjectiveView) : Option Int :=
  winnableFarmTarget none (some o.monster) o.held

/-! ## Half 1 — `L*` held arms the fight on `m*` -/

/-- **`L*` held ⇒ the fight step is armed.** Below the cap the root is one more
    level, and the grind target is `m*`. -/
theorem fight_armed_of_held (o : ObjectiveView) (serves : Int → Bool)
    (hheld : o.held = true) :
    whichPieceIsNext (some o) serves false = some .levelUp ∧
      grindTarget o = some o.monster := by
  refine ⟨?_, ?_⟩
  · simp [whichPieceIsNext, hheld]
  · simp [grindTarget, hheld, winnableFarmTarget]

/-- **The held half, end to end.** A held objective's grind target is dispatched to
    `GrindCharacterXP` and, the fight being applicable, the chain emits a fight on
    `m*` (`LivenessChain`). -/
theorem held_objective_emits_fight (o : ObjectiveView) (bootstrapLevel : Int)
    (fi : FightInputs) (hheld : o.held = true) (hApp : fightApplicable fi = true) :
    chainEmitsFight { pathTarget := some o.monster, pathHeld := o.held,
                      fightInputs := fi, bootstrapLevel := bootstrapLevel }
      false none = some o.monster :=
  chain_emits_fight_when_target_exists_and_applicable _ o.monster rfl hheld hApp

/-! ## Half 2 — `L*` not held: a missing piece is the root, never an XP fight -/

/-- **`L*` not held ⇒ no fight is chosen for XP.** -/
theorem no_xp_fight_of_not_held (o : ObjectiveView) (hheld : o.held = false) :
    grindTarget o = none := by
  simp [grindTarget, hheld, winnableFarmTarget]

/-- **`L*` not held ⇒ the root is a missing piece's acquisition.** When the cycle
    serves some missing piece, the root is the FIRST served piece of `missing`. -/
theorem piece_root_of_not_held (o : ObjectiveView) (serves : Int → Bool) (atCap : Bool)
    (hheld : o.held = false) (hserved : ∃ p ∈ o.missing, serves p = true) :
    ∃ p, whichPieceIsNext (some o) serves atCap = some (.piece p) ∧
      p ∈ o.missing ∧ serves p = true := by
  obtain ⟨q, hq, hsq⟩ := hserved
  cases hf : o.missing.find? serves with
  | none =>
    exact absurd hsq (by simpa using List.find?_eq_none.mp hf q hq)
  | some p =>
    refine ⟨p, ?_, List.mem_of_find?_eq_some hf, by simpa using List.find?_some hf⟩
    simp [whichPieceIsNext, hheld, hf]

/-- Every missing piece declined: no root (no XP trunk stands in for the pieces). -/
theorem no_root_when_every_piece_declined (o : ObjectiveView) (serves : Int → Bool)
    (atCap : Bool) (hheld : o.held = false) (hdecl : ∀ p ∈ o.missing, serves p = false) :
    whichPieceIsNext (some o) serves atCap = none := by
  have hf : o.missing.find? serves = none :=
    List.find?_eq_none.mpr (fun p hp => by simp [hdecl p hp])
  simp [whichPieceIsNext, hheld, hf]

/-- A well-formed objective that is not held misses at least one piece, so the
    served-piece hypothesis of `piece_root_of_not_held` is about a real list. -/
theorem missing_nonempty_of_not_held (o : ObjectiveView) (hwf : WellFormed o)
    (hheld : o.held = false) : o.missing ≠ [] := by
  intro h
  have := hwf.mpr h
  rw [hheld] at this
  exact absurd this (by decide)

/-! ## The band guarantee, composed with the held half -/

/-- **The combat objective is live at every level below the cap.** At every band
    level some catalogue monster is a candidate for `m*` (winnable, XP-positive, under
    the suicide guard), and an objective holding its `L*` on it arms its fight. -/
theorem combatObjective_live_below_fifty
    (winnable xpPos : WinnableFn) (xs : List Monster)
    (h : WinnableAcrossBand winnable xpPos xs) :
    ∀ L : Int, 1 ≤ L → L < 50 →
      ∃ m ∈ xs, winnable m = true ∧ xpPos m = true ∧ notOverleveled L m = true ∧
        ∀ serves : Int → Bool,
          whichPieceIsNext (some ⟨m.code, true, []⟩) serves false = some .levelUp ∧
            grindTarget ⟨m.code, true, []⟩ = some m.code := by
  intro L hlo hhi
  obtain ⟨m, hm, hw, hx, ho⟩ := h L ⟨hlo, hhi⟩
  exact ⟨m, hm, hw, hx, ho, fun serves => fight_armed_of_held ⟨m.code, true, []⟩ serves rfl⟩

/-! ## Non-vacuity witnesses -/

/-- A held, well-formed objective. -/
def witnessHeld : ObjectiveView := ⟨7, true, []⟩
/-- A not-held, well-formed objective with two missing pieces. -/
def witnessMissing : ObjectiveView := ⟨7, false, [11, 12]⟩

example : WellFormed witnessHeld := by simp [WellFormed, witnessHeld]
example : WellFormed witnessMissing := by simp [WellFormed, witnessMissing]
example : whichPieceIsNext (some witnessHeld) (fun _ => true) false = some .levelUp := rfl
example : grindTarget witnessHeld = some 7 := rfl
example : grindTarget witnessMissing = none := rfl
-- The first piece declined, the second served: the root is the second.
example : whichPieceIsNext (some witnessMissing) (fun p => p == 12) false =
    some (.piece 12) := rfl
-- Every piece declined: no root.
example : whichPieceIsNext (some witnessMissing) (fun _ => false) false = none := rfl
-- No objective: the wall.
example : whichPieceIsNext none (fun _ => true) false = none := rfl
-- At the cap a held objective has no level-up root.
example : whichPieceIsNext (some witnessHeld) (fun _ => true) true = none := rfl

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
