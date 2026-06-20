import Formal.Liveness.StickySelect
import Formal.Liveness.Measure

/-! # ZombieFreedom — no infinite zombie hold against the REAL reach-50 measure

`StickySelect.no_infinite_sticky_hold` is abstract over any well-founded relation.
This module instantiates it at the actual reach-50 lexicographic measure
(`Measure.measure` / `Measure.measureLt`, well-founded by
`Measure.measureLt_wellFounded`), turning the abstract no-zombie result into a
concrete statement about the planner's own progress measure:

> Under the progress-gated sticky release, no objective root can be the sticky-held
> (non-top) `chosen_root` at every cycle — i.e. the 1028-cycle weaponcrafting hold
> is impossible — PROVIDED the production `progressed` Bool faithfully witnesses a
> strict descent of the reach-50 measure (`hprogFaithful`).

`hprogFaithful` is the single remaining obligation: the model↔code trust boundary
that production's per-cycle `progressed` signal equals "the reach-50 measure
strictly descended this cycle." It is discharged by the differential harness
(Phase 3, `formal/diff/test_sticky_select_diff.py`), NOT assumed here — mirroring the
`objectiveStepIsFight` arming-differential pattern (`PerceptionRefresh.lean`).

This is the zombie-specific half of the `LevelingDescent.hquiet` arming-optimism
gap: where the model sets `objectiveStepIsFight := true` unconditionally, a zombie
commitment makes production's objectiveStep a gather/grind (not a fight) below 50.
The progress-gate forbids that hold; this theorem is its measure-level witness.

Liveness namespace — Mathlib permitted.
-/

namespace Formal.Liveness.ZombieFreedom

open Formal.Liveness.StickySelect
open Formal.Liveness.Measure

/-- **No infinite zombie hold, against the reach-50 measure.** Concrete instance of
    `StickySelect.no_infinite_sticky_hold` at `r := measureLt`, `μ := measure`. If a
    root `c` is the sticky-held non-top `chosen_root` at every cycle, and the
    `progressed` signal faithfully witnesses a strict `measureLt` descent on each
    progressing cycle, then `False` — the hold cannot persist. The weaponcrafting
    zombie (1028 cycles, frozen sub-measure) is ruled out. -/
theorem no_infinite_zombie_below_fifty
    (st : Nat → State) (cands : Nat → List Cand) (ratio : Rat) (c : Cand)
    (prog : Nat → Bool)
    (hprogFaithful : ∀ k, prog k = true →
      measureLt (measure (st (k + 1))) (measure (st k)))
    (hchosen : ∀ k,
      stickyChoose (cands (k + 1)) (nextLast (some c) (prog k)) ratio = some c)
    (hnottop : ∀ k, (cands (k + 1)).head? ≠ some c) :
    False :=
  no_infinite_sticky_hold measureLt measureLt_wellFounded measure
    st cands ratio c prog hprogFaithful hchosen hnottop

end Formal.Liveness.ZombieFreedom
