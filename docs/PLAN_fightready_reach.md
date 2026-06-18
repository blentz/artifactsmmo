# PLAN: reach-FightReady-from-spawn (level-50 todo #2)

Goal: discharge the load-bearing open piece of the level-50 termination proof —
prove `∃ K, FightReady (cycleStepN K s)` from an arbitrary spawn state, so the
capstone `ai_reaches_level_fifty` stops resting on `settledWitness` setting the
combat objective by fiat. Scoped 2026-06-18 (full Liveness module read).

## Strategy

Target **`FightReady`** (NOT `Settled`/`Leveling`) — it omits the `bank` /
`leveled` fields, so the warm-up need NOT wait for the level-44 bank unlock. The
proven half `ai_reaches_level_fifty_of_fightReady` (`FightReady.lean:154`) closes
FightReady → 50, so reaching FightReady finishes the chain.

**FightReady's 10 fields split into two obligation classes:**
- **Model-provable (the warm-up):** `hpFull`, `overstock`, `deposits`, `gear`,
  `pending`, `sellable`, `craft` (7 monotone clears) + `parked : TaskParked`.
- **Perception (NOT model-derivable):** `objFires`/`objFight`. PROVEN
  un-producible in-model by `Settled_unreachable_without_perception` +
  `objectiveStepFires_false_cycleStepN` (`SettledReach.lean`). These enter as an
  explicit HYPOTHESIS `hperc` — this IS the O5.4 SELECT-side obligation (#3 of the
  level-50 todo), kept separate.

## Target theorems (new file `formal/Formal/Liveness/FightReadyReach.lean`)

```lean
theorem fightReady_reachable (s : State)
    (hperc : ∀ k, (cycleStepN k s).objectiveStepFires = true
                ∧ (cycleStepN k s).objectiveStepIsFight = true)
    (hwarm : <per-seed warm-up reach bounds — see sub-lemmas>) :
    ∃ K, FightReady (cycleStepN K s)

theorem ai_reaches_level_fifty_from_spawn_warmup (s : State)
    (htec : s.taskExchangeMinCoins > 0) (hnec : s.nextExpansionCost > 0)
    (hperc : …) (hwarm : …) :
    ∃ k, (cycleStepN k s).level ≥ 50
```

## Proven bricks to compose (do NOT re-derive)

- `ai_reaches_level_fifty_of_fightReady`, `FightReady_cycleStepN`,
  `hfightFires_of_fightReady` (`FightReady.lean`).
- `TaskParked_blockers_quiet`, `TaskParked_fight` (`Leveling.lean:57,105`).
- 13 one-step `*_quiet_after_firing` (`BlockerQuieting.lean`); 11 permanent
  `*_quiet_forever` + the `<flag>_false_cycleStepN` / `hp_eq_maxHp_cycleStepN` /
  `bankAccessible_cycleStepN` monotone halves (`BlockerMonotone.lean`).
- `cycleStepN_add/_succ/_zero` (`CumulativeProgress.lean`); the
  `reach_fifty_of_eventually_settled` pattern (`SettledReach.lean:41`).
- Candidate for phase: `taskComplete_reachable_exists`
  (`TaskCompleteReachable.lean:174`, targets `.complete`).

## Ordered sub-lemmas (smallest-first; prove in this order)

1. **`hpFull_reachable`** — `∃ K, (cycleStepN K s).hp = (cycleStepN K s).maxHp`.
   One rest/hpCritical fire then monotone via `hp_eq_maxHp_cycleStepN`. SMALL.
2. **`<flag>_cleared_reachable`** ×6 (overstock, deposits, gear, pending,
   sellable, craft) — `∃ K, <flag> (cycleStepN K s) = false`. Each: the blocker
   fires, its planFor clears the flag (`*_quiet_after_firing`), then the monotone
   half keeps it false. Six near-identical replays. SMALL each.
3. **`taskParked_reachable`** — `∃ K, TaskParked (cycleStepN K s)`. HARDEST: the
   task lifecycle is non-monotone (the 3 task blockers re-arm); `.none`/
   feasible-`.accepted` stability is coupled to `hperc` (objectiveStep must
   preempt pursueTask/acceptTask). Likely needs `hperc` + a `.complete`→`.none`
   bridge off `taskComplete_reachable_exists`, plus a no-immediate-reaccept-of-
   infeasible argument. LARGE — may spawn its own sub-plan.
4. **`seed_persists_compose`** — seed false at K₁ ⇒ false at any K₂ ≥ K₁
   (corollary of the monotone halves + `cycleStepN_add`). SMALL.
5. **`blockers_simultaneously_quiet`** (THE MISSING COMBINATOR) — from the per-
   seed reach bounds (#1-3) + persistence (#4), `∃ K`, ALL the warm-up seeds hold
   simultaneously at K (take K = max of the individual bounds). No such
   combinator exists today. MEDIUM.
6. **`fightReady_reachable`** — assemble #5 + `hperc` into `∃ K, FightReady …`.
7. **`ai_reaches_level_fifty_from_spawn_warmup`** — compose #6 with
   `ai_reaches_level_fifty_of_fightReady` + config-positivity invariance.

## Discipline (formal-development honesty)

- Core-only (no Mathlib in the Liveness safety tower); no `sorry`/`admit`/
  `native_decide`; axioms ⊆ {propext, Classical.choice, Quot.sound} + LIV-001.
- `hperc`/`hwarm` are HONEST hypotheses, not vacuous: each must have a
  satisfiability witness (extend `settledWitness`-style) so the reach theorem
  isn't `False → P`. Adversarial self-review per [[feedback_proofs_tell_false_stories]].
- New role theorems → Manifest roster + Contracts pin; run `formal/gate.sh`.
- Serialize gate/lake runs; `git diff src` after.

## Refinement (after inspecting the bricks)

The MONOTONE halves all exist (`hp_eq_maxHp_cycleStepN`, `<flag>_false_cycleStepN`
— "once cleared, stays cleared"). But the REACH direction is genuine liveness
DYNAMICS, not bookkeeping: e.g. `hpFull_reachable` must show the trajectory
actually triggers a rest (hp falls below the hpCritical threshold → `.rest`
fires → hp = maxHp), and `taskParked_reachable` must reason about the
non-monotone lifecycle latching to `.none`. So split the work:

- **Phase A (structural, tractable now):** prove `fightReady_reachable_of_seeds`
  — `∃ K, FightReady (cycleStepN K s)` GIVEN, as explicit honest hypotheses,
  (i) per-seed reach bounds `hseed_<flag> : ∃ K, <flag>(cycleStepN K s)=false`,
  (ii) `htask : ∃ K, TaskParked (cycleStepN K s)`, (iii) `hperc`. Plus the
  MISSING COMBINATOR `blockers_simultaneously_quiet` (max-of-bounds over the
  proven monotone persistence). This is pure composition — provable without
  dynamics — and gives the end-to-end `ai_reaches_level_fifty_from_spawn_warmup`
  modulo the seed hypotheses. Anti-vacuity: a `settledWitness`-style witness.
- **Phase B (dynamics, the deep work):** discharge each seed hypothesis. Order:
  the six opaque-flag reaches (each: blocker fires once → clears → monotone),
  then `hpFull_reachable`, then `taskParked_reachable` (hardest — non-monotone
  lifecycle, coupled to `hperc`; may need `taskComplete_reachable_exists` +
  a `.complete`→`.none` bridge + no-reaccept-of-infeasible).

Phase A front-loads the provable structure and names the dynamics as explicit
hypotheses (honest, not vacuous). Phase B retires them one at a time; each
retired hypothesis is a Manifest/Contracts role.

## Status
- 2026-06-18: scoped; plan written; brick reach-vs-monotone split confirmed.
- 2026-06-18: **Phase A DONE** (commit e22b344, gate green, branch
  feat/fightready-reach). `Formal/Liveness/FightReadyReach.lean`: `reach_and`
  combinator + `FightReadyCore` + `fightReady_reachable_of_seeds` +
  `ai_reaches_level_fifty_from_spawn_warmup` (spawn→50 modulo `hwarm`+`hperc`).
  Axioms = standard + LIV-001. Imported into Formal.lean + LivenessAudit.lean.
- 2026-06-18: **Structural reduction COMPLETE** (commit 1dd3530, gate green).
  Added `persist_and` + `fightReadyCore_reachable_of_seeds` (the `reach_and`
  fold). The ENTIRE chain spawn→50 is now proven, conditional only on: the 7
  per-seed reaches (`hhp`..`hcraft`), the TaskParked reach + persistence, and
  `hperc`. The combinator/assembly Phase A is fully done.

  **KEY FINDING (reshapes the roadmap):** the remaining per-seed reach DYNAMICS
  are ENTANGLED with the SELECT side (#3). A flag clears only when
  `productionLadder` SELECTS its blocker, so `∃K, flag false` requires reasoning
  about what the ladder picks along the real `cycleStepN` trajectory — the same
  SELECT-reach machinery `hperc`/O5.4 needs. The existing task-lifecycle reach
  lemmas (`taskComplete_reachable_exists`, etc.) are over `applyPlan`
  (hypothetical action sequences), NOT `cycleStepN`, so they don't bridge the
  selection gap either.
  → Phase B is NOT independent dynamics bookkeeping; the next real step is to
  build the SELECT-side reach model (how `productionLadder` selection drives the
  warm-up), which serves BOTH the per-seed reaches AND #3 (O5.4). Treat Phase B
  + #3 as one sub-project: the SELECT-reach machinery.
