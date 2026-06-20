-- @concept: liveness, planner @property: liveness
import Formal.Liveness.StickySelect

/-! # GatedArming — derive `objectiveStepIsFight` from the progress-gated selection

The reach-50 capstone (`LevelingDescent.ai_reaches_fifty_grounded`) consumes
`(perceptionRefresh s).objectiveStepIsFight = true`, which `PerceptionRefresh`
currently sets UNCONDITIONALLY below the cap. That set value is OPTIMISTIC: in
production the objective tier's emitted step is a Fight only when the objective
tier's `chosen_root` is fight-bearing (a `ReachCharLevel` / combat objective), and
NOT when a zombie commitment pins a non-fight gather/grind root (the 1028-cycle
weaponcrafting hold).

This module replaces the *fiat* with a *derivation*: the arming is the fight-bearing
status of the progress-gated sticky selection (`StickySelect.stickyChoose`). The
headline `no_infinite_zombie_suppression` then CONSUMES
`StickySelect.no_infinite_sticky_hold` to prove the one thing the optimism quietly
assumed away: **a non-fight root cannot suppress the fight arming forever.**

## What this proves (honest scope)

* `gatedArming` — the arming as a function of the selection inputs: fight-bearing
  status of `stickyChoose`'s pick (or `false` when no candidate).
* `gatedArming_eq_top_of_released` — once the anchor is released
  (`lastChosen = none`), the arming is the fight-bearing status of the TOP-scored
  root. So a released zombie hands the arming to the highest-value root; if the
  leveling objective is top, the cycle is armed for a fight.
* `gatedArming_true_of_progressing_fight` — a progressing fight-bearing sticky root
  keeps the arming true.
* `no_infinite_zombie_suppression` — **the no-zombie payoff for the arming**: there is
  no trajectory in which a fixed NON-fight root `c` is the sticky-held (non-top)
  selection at every cycle (which would force the arming false every cycle). Direct
  instance of `StickySelect.no_infinite_sticky_hold` with `fightBearing c = false`;
  the production trust boundary is the same named `hprogFaithful` (the `progressed`
  Bool witnesses a strict measure descent), discharged by the differential, not here.

## What this does NOT yet do

It does NOT splice the derived arming into `perceptionRefresh` / the
`ai_reaches_fifty_grounded` proof term. That splice requires the cycle dynamics
(`cycleStep` / `applyActionKind` / every means' `planFor`) to thread the selection
state, AND it requires moving the capstone's descent argument from "fights every
below-50 cycle" to "descends the measure every below-50 cycle" (healthy gear
bootstrap gathers — descending the skill-xp slot — without fighting). That general
measure-descent re-architecture is the documented out-of-scope `ProgressAction`
fuel-bounding work (`LevelingDescent.lean:29-33`). This module is the proven bridge
that work will consume; see `docs/PLAN_zombie_progress_gate.md`.

Liveness namespace — Mathlib permitted.
-/

namespace Formal.Liveness.GatedArming

open Formal.Liveness.StickySelect

/-- The objective-tier fight arming, DERIVED from the progress-gated selection: the
    fight-bearing status of the root `stickyChoose` picks (`false` when the candidate
    list is empty). `fightBearing` classifies a root repr as leading with a Fight
    (production: `ReachCharLevel` / combat-typed objectives, whose plan head is
    `FightAction`). Replaces `PerceptionRefresh`'s unconditional `:= true`. -/
def gatedArming (cands : List Cand) (lastChosen : Option String) (ratio : Rat)
    (fightBearing : String → Bool) : Bool :=
  match stickyChoose cands lastChosen ratio with
  | some c => fightBearing c.repr
  | none   => false

/-- Once released (`lastChosen = none`), the arming equals the fight-bearing status of
    the TOP-scored root. So a released zombie hands the arming decision to the
    highest-value candidate — if that is the leveling objective, the cycle is armed. -/
theorem gatedArming_eq_top_of_released {cands : List Cand} {ratio : Rat} {top : Cand}
    {fightBearing : String → Bool} (hhead : cands.head? = some top) :
    gatedArming cands none ratio fightBearing = fightBearing top.repr := by
  unfold gatedArming
  rw [released_picks_top hhead]

/-- A progressing, fight-bearing sticky root keeps the arming true: if `stickyChoose`
    picks `c` and `c` is fight-bearing, the arming is true. -/
theorem gatedArming_true_of_fight {cands : List Cand} {lastChosen : Option String}
    {ratio : Rat} {fightBearing : String → Bool} {c : Cand}
    (hpick : stickyChoose cands lastChosen ratio = some c)
    (hfight : fightBearing c.repr = true) :
    gatedArming cands lastChosen ratio fightBearing = true := by
  unfold gatedArming; rw [hpick]; exact hfight

/-- A non-fight root makes the arming false exactly when it is the pick. -/
theorem gatedArming_false_of_nonfight_pick {cands : List Cand} {lastChosen : Option String}
    {ratio : Rat} {fightBearing : String → Bool} {c : Cand}
    (hpick : stickyChoose cands lastChosen ratio = some c)
    (hnofight : fightBearing c.repr = false) :
    gatedArming cands lastChosen ratio fightBearing = false := by
  unfold gatedArming; rw [hpick]; exact hnofight

/-- A non-fight root that is sticky-HELD necessarily suppresses the arming (false).
    This makes the link from "held zombie" to "arming false" explicit and load-bearing
    — the suppression is a CONSEQUENCE of the hold, never an extra assumption. -/
theorem arming_false_of_held_nonfight {cands : List Cand} {lastChosen : Option String}
    {ratio : Rat} {fightBearing : String → Bool} {c : Cand}
    (hheld : stickyChoose cands lastChosen ratio = some c)
    (hcnofight : fightBearing c.repr = false) :
    gatedArming cands lastChosen ratio fightBearing = false :=
  gatedArming_false_of_nonfight_pick hheld hcnofight

/-- **The no-zombie payoff for the fight arming.** There is NO trajectory in which a
    fixed non-fight root `c` is the sticky-held (non-top) objective selection at every
    cycle. By `arming_false_of_held_nonfight` such a trajectory would hold the derived
    arming `false` forever (a zombie of the arming); this theorem proves the
    trajectory itself is impossible. Direct instance of
    `StickySelect.no_infinite_sticky_hold`: `sticky_requires_progress` forces progress
    on every sustained-hold step, and a well-founded measure forbids the resulting
    infinite descent.

    `hprogFaithful` is the production trust boundary (the `progressed` Bool witnesses a
    strict measure descent), discharged by the differential harness (Phase 3), not
    assumed here. -/
theorem no_infinite_zombie_suppression
    {σ β : Type} (r : β → β → Prop) (wf : WellFounded r) (μ : σ → β)
    (st : Nat → σ) (cands : Nat → List Cand) (ratio : Rat) (c : Cand) (prog : Nat → Bool)
    (hprogFaithful : ∀ k, prog k = true → r (μ (st (k + 1))) (μ (st k)))
    (hheld : ∀ k, stickyChoose (cands (k + 1)) (nextLast (some c) (prog k)) ratio = some c)
    (hnottop : ∀ k, (cands (k + 1)).head? ≠ some c) :
    False :=
  no_infinite_sticky_hold r wf μ st cands ratio c prog hprogFaithful hheld hnottop

end Formal.Liveness.GatedArming
