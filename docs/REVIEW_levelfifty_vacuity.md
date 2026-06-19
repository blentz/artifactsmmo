# The level-50 capstones are vacuous (kernel-proven)

**Date:** 2026-06-19. **Prompted by:** "are we circling vacuous proofs because we've
not accurately modeled the game or the AI?" — yes. This is the proof and the diagnosis.

> **RESOLVED 2026-06-19.** The vacuous capstones and the whole i.o.-fairness transience
> tower were REMOVED (the `cycleStepF` tower: `LevelFiftyReachableF`/`FightFairnessF`/
> `EffectiveDrainTransience`/`PressureTransience`/`PressureDrain`/`BurstStep`/
> `PressureBurst`/`Drainability`/`CycleStepFLeveling`; the `cycleStepP` capstone gutted
> from `LevelFiftyReachableP`, keeping its reusable helpers; `FightFairnessP` deleted;
> the `ResidualVacuity` demonstration module deleted now that its subjects are gone).
> The NON-VACUOUS replacement is `Formal.Liveness.LevelingDescent.
> cycleStepF_reaches_fifty_of_fights` (reach 50 from a per-cycle measure DESCENT via
> `Formal.Liveness.MeasureDescent`). The kernel proofs of vacuity below are the
> historical record of WHY the removal happened.

## The finding

`Formal/Liveness/ResidualVacuity.lean` proves, with standard axioms only:

- `capstone_hypotheses_unsatisfiable` — the faithful `cycleStepF` capstone
  `EffectiveDrainTransience.ai_reaches_level_fiftyF_of_effectiveDrain` has hypotheses
  that imply `False`.
- `levelFiftyP_hypotheses_unsatisfiable` — the predecessor `cycleStepP` capstone
  `LevelFiftyReachableP.ai_reaches_level_fiftyP_of_blockers_quiet` too.

So both `H → ∃k level ≥ 50` theorems are **vacuously true**: they hold because `H` is
never satisfiable, not because the bot reaches level 50. They say nothing about the
real bot.

## Root cause: i.o.-fairness vs monotone progress to a cap

Every fairness residual in the chain (`TenQuietPairsBelowCapInfinitelyOften`,
`BlockersQuietBelowCapInfinitelyOftenP`, and `hfightFires*` upstream) is an
`∀N ∃k≥N, … ∧ (cycleStepFN k s).level < 50` — it asserts a property holds for
INFINITELY MANY steps while still below level 50.

But `level` is monotone non-decreasing along the trajectory (`cycleStepFN_level_ge`,
`cycleStepPN_level_ge`). So:

> "level < 50 infinitely often"  ⟺  "level NEVER reaches 50".

That is the exact negation of the goal `∃k, level ≥ 50`. Residual and conclusion cannot
both hold, so the hypotheses are unsatisfiable. The residual docstrings called the
`level < 50` conjunct a "harmless self-restriction"; it is in fact the vacuity — it
makes the residual satisfiable ONLY on trajectories where the goal FAILS.

## Why this kept happening — the modeling gap the question identified

The hard content — *the bot actually fights/progresses enough to level up* — was never
DERIVED from the model. It was repeatedly deferred into an i.o.-fairness residual
("blockers quiet i.o.", "fights fire i.o."). Each deferral looked like progress (the
capstone compiled green) but moved the difficulty into a hypothesis that is vacuous at
the top. The faithfulness work (modeling inventory pressure, drains, the dichotomy) was
real and correct as far as it went, but it served a residual that was vacuous all along.

The "conditional" patch (make the residual `(∀k level<50) → fairness`, true vacuously
once 50 is reached) does NOT help: it then becomes equivalent to the conclusion
(fairness holds iff the trajectory reaches 50), i.e. circular — it assumes what it
should prove.

## The non-vacuous path: per-cycle well-founded measure decrease

The only honest route is the one the i.o.-fairness detour abandoned: a **well-founded
measure that strictly decreases on every below-50 cycle**, UNCONDITIONALLY (no i.o.
residual). `Formal/Liveness/Measure.lean` already builds the lex measure and proves
`measureLt_wellFounded`; the per-action decrease lemmas (`LifecycleBound*`,
`CumulativeProgress`) were heading this way before the engine switched to
xp-accumulation + fairness.

Target statement (satisfiable for reaching-50 trajectories, non-circular):

> `(∀k, level(cycleStepFN k s) < 50 → measure(cycleStepF (cycleStepFN k s)) <ₗ
>  measure(cycleStepFN k s))  →  ∃k, level(cycleStepFN k s) ≥ 50`

- **Satisfiable**: a reaching-50 trajectory decreases the measure each step until 50,
  then the `level < 50` guard is false for later steps — no constraint. Satisfiable.
- **Non-circular**: the hypothesis is a conjunction of LOCAL per-step facts, each
  independently satisfiable, NOT a statement about the trajectory's limit.
- **Drives termination**: by `measureLt_wellFounded`, no infinite strictly-decreasing
  chain, so the below-50 region is exited — level 50 reached.
- **Surfaces the livelock honestly**: the per-cycle decrease FAILS exactly at a
  livelock state (no progress — e.g. the full-of-useful-items pressure livelock). So
  the honest theorem is "reaches 50 unless it hits a no-progress (livelock) cycle", and
  the hypothesis names that precondition locally and checkably.

This re-centers the level-50 proof on proving **every below-50 cycle makes measure
progress** — which is real, hard, falsifiable modeling work (a fight decreases the
xp-deficit; a chore decreases its measure slot; the livelock is where it fails), rather
than an i.o. residual that is vacuous by construction.

## Status of prior claims (corrected)

Memories/plans that said "level-50 termination is PROVEN modulo {GlobalInvariants,
LIV-001, WinnableAcrossBand, BlockersQuiet}" are now known to mean "proven from an
UNSATISFIABLE hypothesis set" — i.e. vacuous. The faithfulness modules
(`PressureBurst`/`PressureDrain`/`PressureTransience`/`EffectiveDrainTransience`/
`CycleStepF*`/`LevelFiftyReachableF`) remain kernel-valid as conditional statements,
but their top-level capstones prove nothing until the residual is reformulated as a
per-cycle measure decrease. The local lemmas (the dichotomy, the drain crux, the
level-advance engine) are reusable toward the measure reformulation.
