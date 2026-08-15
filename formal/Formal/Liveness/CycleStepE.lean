import Formal.Liveness.CycleStepD

/-! # CycleStepE — the GEARED cycle (E-tower, C2b)

`docs/PLAN_c2_composed_liveness.md`. The defer-faithful cycle (`cycleStepD`)
with the combat-outcome gaps closed:

1. **Adequacy-gated arming** (`perceptionRefreshE`): below 50, outside the
   defer window, the combat objective is armed ONLY when `loadoutAdequate`
   (production image: the arbiter emits a fight step when `is_winnable`
   finds a band target for the CURRENT gear). When inadequate it arms the
   GEAR latch instead (`gearReviewFires` — the UpgradeEquipment band): the
   model stops crediting xp for fights the real bot could not win, the
   gap-1 fix the B1/B2 trace phases measured.
2. **Gear progress** (`gearProgress`): a PRODUCTIVE `.gearReview` cycle with
   `gearGap > 0` strictly decrements the gap (an unproductive one moves
   nothing — see `GearCycleMakesProgressAt`); at an exhausted gap the cycle
   RESTORES adequacy (paid at the measure's `inadequacyFlag` slot) —
   the A2 debt pattern at gear scale, grounded offline by the EMPTY
   acquirable frontier (`WitnessAcquirable.acquirableFrontier_empty`: every
   band's witness loadout is closure-obtainable, so the gap is always
   finitely dischargeable).
3. **Rollover gear re-arm** (`rearmE`): a fight that levels up RESETS
   `gearGap := GEAR_CAP` and drops adequacy (new band, new witness target) —
   paid at the measure's slot 1. Non-rollover fights re-arm the chore
   latches as in the D-tower.
4. **Fight hp-loss** (`fightLoss`): every fight dispatch costs
   `FIGHT_LOSS_BOUND` hp, FLOORED AT 1 — production never dies and never
   restores (`ai/actions/combat.py:130-131`, FightAction.apply). Raises only `hpDeficit` —
   dominated by the fight's slot-1/3 descent; the rest row heals as before.
   (Until 2026-07-20 the below-bound case respawned at FULL hp, which made a
   death descend the measure MORE than a survived fight.)

Additive only — the D-tower and every existing theorem are untouched.
Liveness namespace — Mathlib allowed. -/

set_option linter.dupNamespace false

namespace Formal.Liveness.CycleStepE

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.InventoryDynamics
open Formal.Liveness.CycleStepD

/-- Gear re-arm size on a band change: the number of `.gearReview` cycles the
    model allows for rebuilding a band's witness loadout.

    GROUNDED 2026-07-20 (increment 3). This was `8`, self-declared "provisional".
    It was not merely ungrounded — it was WRONG, and wrong in the flattering
    direction: `gearProgress` decrements `gearGap` by one per gear cycle and
    restores adequacy at zero, so `GEAR_CAP` must bound the number of
    acquisition steps for a band's witness loadout. The fixture's 49
    `acquirableWitness` rows carry loadouts of up to **11** items, and **20 of
    49 exceed 8** — so the old constant asserted that a 11-item loadout is
    rebuilt in 8 steps.

    11 is now pinned against the fixture by `WitnessAcquirable.witness_loadout_le_gear_cap`,
    which computes `loadoutCodes.length` IN-KERNEL from the witness rows rather
    than trusting an emitted number.

    STILL RESIDUAL (`GearCycleMakesProgress`, spec increment 4): that ONE gear
    cycle accomplishes ONE acquisition step. The real arbiter may spend a
    `.gearReview` cycle travelling, or lose it to an API failure. This constant
    bounds the STEPS; it does not bound the CYCLES those steps take. -/
def GEAR_CAP : Nat := 11

/-- Worst-case hp loss of one fight. Lemma-agnostic.

    THE BOUND IS OBSERVED, NOT ASSUMED. This was `270`, cited as "B1 trace
    measurement: max observed 270" — measured on a single character's play
    trace back when the 155 committed traces were the corpus. Replayed against
    the learning store (`~/.cache/artifactsmmo/learning.db`, every `FightAction`
    cycle with `outcome = 'ok'`: 10_883 fights, 5 characters, each fight's loss
    read from its OWN `delta_hp` column rather than differenced from
    neighbouring snapshots) that "worst case" is not a worst case at all:

        loss > x       fights    share of 10_883
          0             10_835    99.6%
        100              4_781    43.9%
        200              2_227    20.5%
        270              2_155    19.8%   <-- the OLD bound
        400              1_937    17.8%
        500                 75     0.7%
        541                  0     0.0%   <-- the new bound, attained

    The largest single-fight losses observed: 541 x4, 527 x1, 526 x22, 512 x6,
    511 x42, 497 x17, 496 x83, 483 x1, 482 x54, 481 x124. The old bound was
    exceeded by 2_155 fights — 19.8%, one fight in five. That is not a rare
    tail that a pessimistic constant absorbs; it is the bulk of the upper half
    of the distribution, and every one of those fights was a real trajectory
    the model's `fightLoss` layer could not represent.

    541 is the maximum over the whole corpus and it is ATTAINED (4 fights):
    Robby at level 26, `maxHp = 545`, full pool 545 → 4 hp. Nothing exceeds it.
    (The remaining 48 of the 10_883 rows carry a non-negative `delta_hp` — the
    level-up heal — and are not losses; 10_835 are strict losses.)

    NO FIGHT LOSES THE WHOLE POOL. The largest loss as a fraction of `maxHp` is
    541/545 = 0.9927, and `loss ≥ maxHp` happens ZERO times in 10_883 fights.
    Production's `max(1, hp - cost)` floor (`ai/actions/combat.py:130-131`, FightAction.apply),
    which `fightLoss` mirrors, is therefore not merely a modelling convenience —
    it is what the corpus shows.

    FAITHFULNESS NOTE (restated 2026-08-15). This is a corpus-measured worst
    case, NOT the production planner's projection, which is `max(1, max_hp / 5)`
    (`ai/actions/combat.py:130`). At 541 the model's loss is the larger of the
    two for any `maxHp < 2705` (at 270 the crossover was 1350), so the model
    remains PESSIMISTIC relative to the bot's own projection — the safe
    direction for a descent argument, and now safe by a wider margin. The same
    corpus says the planner's projection is the one that is optimistic: over
    these 10_883 fights `max(1, maxHp / 5)` never exceeds 110 (`maxHp` ranges
    150..550), and 9_302 fights — 85.5% — cost MORE hp than the planner
    projected. The two are not the same quantity, and only one of them is
    measured. -/
def FIGHT_LOSS_BOUND : Nat := 541

/-- **RESIDUAL (G1): the arming observation, at one state.**

    `objectiveStepFires` / `objectiveStepIsFight` are OPAQUE production
    observations (`Measure.lean:161-164`): the arbiter yields a step candidate
    IFF the objective tier produced a plannable one. This says that below the
    cap, outside the defer window, with adequate gear, that observation is in
    fact positive and is a Fight.

    PER-STATE by design. The `∀ s` form is FALSE — states exist with adequate
    gear and no plannable step — and a false hypothesis would make the capstone
    VACUOUS, which is the 2026-06-19 failure this whole line of work exists to
    avoid. Callers quantify it over the trajectory instead.

    It is a RESIDUAL, not a theorem, and it cannot be discharged offline: it
    equates an opaque model Bool with a Python computation over
    `state.equipment`, `monster_spawn_known`, and a `LearningStore`. Known
    production falsifiers, none modelled here: `_marginal_provision_goal`
    returning a non-Fight goal (`strategy_driver.py:782-784`); the objective step
    being `ObtainItem` rather than `ReachCharLevel`; the learned-loss veto
    overriding a positive `predict_win` (`combat.py:367-377`); the 14/58 catalog
    monsters with no map tile.

    HISTORY (2026-07-20). Until this commit `perceptionRefreshE` simply OVERWROTE
    the observation with `true`, so the capstone read as hypothesis-free while
    silently assuming exactly this — the retired `hfightFires` fairness
    obligation, relocated into a definition where `#print axioms` could not see
    it. Naming it is the point. -/
def AdequateArmsFightAt (s : State) : Prop :=
  s.level < 50 → deferGate s = false → s.loadoutAdequate = true →
    s.objectiveStepFires = true ∧ s.objectiveStepIsFight = true

/-- Adequacy-gated arming: gear latch when inadequate; otherwise the state passes
    through UNCHANGED — the fight objective is READ from the production
    observation, never installed (see `AdequateArmsFightAt`). Identity inside the
    defer window and at/above the cap. -/
def perceptionRefreshE (s : State) : State :=
  if s.level < 50 && !(deferGate s) then
    if s.loadoutAdequate then s
    else { s with gearReviewFires := true }
  else s

/-- **RESIDUAL (G2, rate): a gear cycle advances the build, at one state.**

    `GEAR_CAP` bounds the acquisition STEPS for a band's witness loadout — pinned
    against the fixture by `GearedDescent.witness_loadout_le_gear_cap`
    (increment 3). What remained granted is the RATE: that one `.gearReview`
    cycle accomplishes one step.

    Not derivable offline. The arbiter may select `.gearReview` and spend the
    cycle travelling to a workshop, replanning, or absorbing an API failure.
    `GearBuildTermination.grounded_builds_target` gives ∃-a-finite-build-sequence
    over a `Graph`, but `State` carries only an opaque `Nat` here; bridging needs
    the gear graph carried in the state, which is a larger change than this slot
    warrants now that increment 3 has bounded it. -/
def GearCycleMakesProgressAt (s : State) : Prop :=
  s.level < 50 → deferGate s = false → s.loadoutAdequate = false →
    s.gearCycleProductive = true

/-- Gear progress: a PRODUCTIVE gear-review cycle with an open gap closes one
    step and restores adequacy exactly at zero.

    CORRECTED 2026-07-20 (increment 4). This decremented unconditionally,
    granting that every `.gearReview` cycle is productive. An unproductive cycle
    now moves nothing — the honest model of a wasted cycle, and exactly the
    livelock `GearCycleMakesProgressAt` must rule out. -/
def gearProgress (k : MeansKind) (st : State) : State :=
  match k with
  | .gearReview =>
      if !st.gearCycleProductive then st
      else if st.gearGap = 0 then { st with loadoutAdequate := true }
      else { st with gearGap := st.gearGap - 1,
                     loadoutAdequate := decide (st.gearGap - 1 = 0) }
  | _ => st

/-- Fight hp cost, flooring at 1 hp.

    CORRECTED 2026-07-20 (adversarial review). The below-bound case previously
    read `hp := st.maxHp` — "death → respawn at full". That was unfaithful in the
    direction that FLATTERS the proof: `hpDeficit = maxHp - hp` is EMeasure slot
    18, so respawning made a death decrease the measure MORE than surviving a
    fight did. The model priced dying better than winning, and a bot that died to
    every monster still reached 50.

    Production never dies and never restores: `FightAction.apply` computes
    `new_hp = max(1, hp - estimated_hp_cost)` (`ai/actions/combat.py:130-131`, FightAction.apply).
    The floor is now 1, mirroring that. Descent is unaffected — a fight descends
    slot 1 (`levelDeficit`) or slot 4 (`xpDeficit`), both of which lex-dominate
    slot 18 — so the correction costs only the flattering case. -/
def fightLoss (k : MeansKind) (r st : State) : State :=
  if dispatchesFight k r then
    if FIGHT_LOSS_BOUND < st.hp then { st with hp := st.hp - FIGHT_LOSS_BOUND }
    else { st with hp := 1 }
  else st

/-- Fight re-arm: rollover fights reset the gear fields (new band) on top of
    the D-tower's worst-case chore re-arm; the mint re-arms are unchanged. -/
def rearmE (k : MeansKind) (r st : State) : State :=
  if dispatchesFight k r && decide (r.level < st.level) then
    { (rearmOnMint k r st) with gearGap := GEAR_CAP, loadoutAdequate := false }
  else rearmOnMint k r st

/-- One geared cycle. -/
noncomputable def cycleStepE (s : State) : State :=
  match productionLadder (perceptionRefreshE s) with
  | some k =>
      rearmE k (perceptionRefreshE s)
        (gearProgress k
          (fightLoss k (perceptionRefreshE s)
            (partialClear k
              (pressureDeltaD k (perceptionRefreshE s)
                (cycleStep (perceptionRefreshE s))))))
  | none => cycleStep (perceptionRefreshE s)

/-- `n`-fold geared cycle. -/
noncomputable def cycleStepEN : Nat → State → State
  | 0,     s => s
  | n + 1, s => cycleStepEN n (cycleStepE s)

@[simp] theorem cycleStepEN_zero (s : State) : cycleStepEN 0 s = s := rfl

theorem cycleStepEN_succ (n : Nat) (s : State) :
    cycleStepEN (n + 1) s = cycleStepEN n (cycleStepE s) := rfl

theorem cycleStepEN_succ_outer (n : Nat) (s : State) :
    cycleStepEN (n + 1) s = cycleStepE (cycleStepEN n s) := by
  induction n generalizing s with
  | zero => rfl
  | succ n ih =>
      rw [cycleStepEN_succ, ih, cycleStepEN_succ]

/-! ## Field bridges. -/

theorem perceptionRefreshE_level (s : State) :
    (perceptionRefreshE s).level = s.level := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl

theorem perceptionRefreshE_xp (s : State) :
    (perceptionRefreshE s).xp = s.xp := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl

theorem gearProgress_level (k : MeansKind) (st : State) :
    (gearProgress k st).level = st.level := by
  unfold gearProgress
  split
  · split
    · rfl
    · split <;> rfl
  · rfl

theorem gearProgress_xp (k : MeansKind) (st : State) :
    (gearProgress k st).xp = st.xp := by
  unfold gearProgress
  split
  · split
    · rfl
    · split <;> rfl
  · rfl

theorem fightLoss_level (k : MeansKind) (r st : State) :
    (fightLoss k r st).level = st.level := by
  unfold fightLoss
  split
  · split <;> rfl
  · rfl

theorem fightLoss_xp (k : MeansKind) (r st : State) :
    (fightLoss k r st).xp = st.xp := by
  unfold fightLoss
  split
  · split <;> rfl
  · rfl

theorem rearmE_level (k : MeansKind) (r st : State) :
    (rearmE k r st).level = st.level := by
  unfold rearmE
  split
  · exact rearmOnMint_level k r st
  · exact rearmOnMint_level k r st

theorem rearmE_xp (k : MeansKind) (r st : State) :
    (rearmE k r st).xp = st.xp := by
  unfold rearmE
  split
  · exact rearmOnMint_xp k r st
  · exact rearmOnMint_xp k r st

/-- Level bridge to the refreshed-applied state. -/
theorem cycleStepE_level (s : State) :
    (cycleStepE s).level = (cycleStep (perceptionRefreshE s)).level := by
  unfold cycleStepE
  cases productionLadder (perceptionRefreshE s) with
  | none => rfl
  | some k =>
      rw [rearmE_level, gearProgress_level, fightLoss_level,
        partialClear_level, pressureDeltaD_level]

/-- One `cycleStepE` never lowers `level`.

    Bridges `cycleStepE_level` through `CumulativeProgress.cycleStep_level_ge`;
    the refresh is level-invariant (`perceptionRefreshE_level`), and none of the
    E overlays (`rearmE`/`gearProgress`/`fightLoss`) touch `level`. Mirrors
    `CycleStepFIteration.cycleStepF_level_ge`. -/
theorem cycleStepE_level_ge (s : State) : (cycleStepE s).level ≥ s.level := by
  rw [cycleStepE_level]
  have h := Formal.Liveness.CumulativeProgress.cycleStep_level_ge
    (perceptionRefreshE s)
  rw [perceptionRefreshE_level] at h
  exact h

/-- `level` is monotone non-decreasing along the geared trajectory.

    ADDED 2026-07-20. The E-tower had NO level-monotonicity lemma — an absence
    that only shows up when you try to state an E-tower hypothesis honestly,
    because every satisfiability witness in this codebase is the degenerate
    "already ≥ 50" state (`LevelingDescent.fights_below_cap_satisfiable_with_goal`)
    and that witness needs exactly this. Mirrors `cycleStepFN_level_ge`. -/
theorem cycleStepEN_level_ge (s : State) (n : Nat) :
    (cycleStepEN n s).level ≥ s.level := by
  induction n generalizing s with
  | zero => rw [cycleStepEN_zero]
  | succ k ih =>
    rw [cycleStepEN_succ]
    have h1 : (cycleStepE s).level ≥ s.level := cycleStepE_level_ge s
    have h2 : (cycleStepEN k (cycleStepE s)).level ≥ (cycleStepE s).level :=
      ih (cycleStepE s)
    omega

/-- Xp bridge. -/
theorem cycleStepE_xp (s : State) :
    (cycleStepE s).xp = (cycleStep (perceptionRefreshE s)).xp := by
  unfold cycleStepE
  cases productionLadder (perceptionRefreshE s) with
  | none => rfl
  | some k =>
      rw [rearmE_xp, gearProgress_xp, fightLoss_xp,
        partialClear_xp, pressureDeltaD_xp]

end Formal.Liveness.CycleStepE
