# PLAN: O5.4 SELECT-side differential — bind the Lean ladder to production

## Why (the trust gap)

The whole liveness layer (NoDeadlock, FightFairness, BlockerSelection, B-0
`BootstrapReach`, the level-50 capstone) reasons over
`Formal.Liveness.ProductionLadder.fires` / `productionLadder` and the State's
opaque firing Bools (`objectiveStepFires`, `objectiveStepIsFight`,
`restForCombatReady`, `craftReliefFires`, `gearReviewFires`,
`maintainConsumablesFires`, plus the task-opaque Bools). The 2026-06-18 SELECT
landscape audit found **none of these are bound to production by any differential
test.** The opaque-Bool docstrings ("a diff harness must assert this Bool matches
production") describe a harness that was never built. `test_cycle_step_diff.py`
checks a *Python mirror* (`formal/sim/production_ladder.py`) against another
Python mirror, with the objective tier hardwired OFF — it never reaches the Lean
`fires`/`productionLadder`. So every liveness theorem currently rests on the
UNVALIDATED assumption that the Lean ladder mirrors production. This differential
closes that gap; it is the precondition for honestly extending the model with a
perception-refresh step (PLAN_select_reach.md §"CHOSEN POST-B-0 DIRECTION").

## Prep DONE (2026-06-18)

- `fires` / `productionLadder` / `lowYieldCancelFires` made COMPUTABLE (commit
  62832e3) — they were `noncomputable` on a stale premise (lowYieldSampleThreshold
  is `def := 1`, not an axiom). Now oracle-evaluable. Full build green.

## Production anchors (from the SELECT audit — exact symbols)

- Per-slot firing (the bindable, non-opaque guards/means):
  `_guard_fires` (`src/artifactsmmo_cli/ai/tiers/guards.py`) /
  `_means_fires` (`src/artifactsmmo_cli/ai/tiers/means.py`). ALREADY called by
  the real-import mirror `formal/sim/production_ladder.py` (imports
  `_guard_fires`/`_means_fires`, lines ~29/35).
- Ladder order + candidate build: `StrategyArbiter._build_candidates`
  (`src/artifactsmmo_cli/ai/strategy_driver.py:884-939`).
- `objectiveStepFires` ≡ `_resolve_step_goal` returns non-None AND that goal is
  plannable in `_arbitrate` (`strategy_driver.py:744-745` → `objective_step_goal`
  at `:810/:817/:824`; arbitration at `:778`; candidate inserted at `:915-917`).
- `objectiveStepIsFight` ≡ the `ReachCharLevel` meta-goal → `GrindCharacterXPGoal`
  whose plan leads with `FightAction` (see `Measure.lean:154-169`; chain exercised
  hand-mirrored in `formal/diff/test_liveness_chain.py:86-110`, NO oracle).
- perceive→select loop: `player.py:302` (`decide`) → `:331`
  (`self._arbiter.select`).

## Bricks (smallest-first; each ends build-green + committed)

### Brick 2 — oracle entry `ladder_fires` (Lean side)
New `runLadder` in `Oracle.lean`: parse a flat arg layout into a
`Formal.Liveness.Measure.State` (the ~40 fields the firing predicates READ; rest
get inert defaults), return per-slot `fires k s` (23 Bools, in `allInLadderOrder` — `allInLadderOrder.
length = 23`, proven in MeansKind.lean) + `productionLadder s` (the selected
MeansKind name, or `null`). Mirror the existing
flat-`intArg` entries (e.g. `runBankSelection`, Oracle.lean:606). Wire a
`"ladder_fires"` dispatch key. Verify with a couple of `oracle_client` round-trips.
SIZE: medium (field plumbing). RISK: low (additive).

### Brick 3 — differential for the NUMERIC/structural guards
`formal/diff/test_ladder_fires_diff.py`: Hypothesis-generate State scenarios;
feed to (a) the oracle `ladder_fires`, (b) production `_guard_fires`/`_means_fires`
via the `formal/sim/production_ladder.py` real-import path. Assert per-slot
agreement for the slots whose firing is COMPUTED from concrete state — hpCritical,
restForCombat(numeric clause b), bankUnlock, reachUnlockLevel, depositFull,
discardCritical/High, completeTask, sellPressured, claimPending, taskExchange,
bankExpand, wait — and that `productionLadder` selects the same MeansKind. Skip the
opaque-Bool slots (Brick 4). Add to gate.sh part (d) glob (already globs
`formal/diff/`). SIZE: medium-large. RISK: medium (fixture reconstruction).

### Brick 4 — bind the OPAQUE Bools to production's real computation
The load-bearing perception inputs. Each needs production's actual predicate
reconstructed on a real fixture:
- `objectiveStepFires` / `objectiveStepIsFight` ← `_resolve_step_goal` +
  plannability + "head action is Fight" (the `player.decide`/`_arbitrate` path).
- `restForCombatReady` ← guards.py REST_FOR_COMBAT clauses (a)/(c)/(d) via
  `predict_win`.
- `craftReliefFires` ← `craft_relief_candidates` non-empty.
- `gearReviewFires` ← `ctx.gear_review_active`.
- `maintainConsumablesFires` ← means.py MAINTAIN_CONSUMABLES predicate.
This is the hardest brick (requires standing up real `WorldState`/`SelectionContext`/
`game_data` fixtures and the planner). Decompose per-Bool; each is its own
differential asserting the Lean State's carried Bool equals production's computed
answer on the reconstructed fixture. SIZE: large (multi-session). RISK: high.

### Brick 5 — mutation coverage
Ensure the new differential KILLS mutants of the ladder firing predicates
(perturb a threshold/conjunct in a `*Fires` def → a surviving mutant means the
differential is vacuous). Refresh `formal/diff/mutate.py` anchors for the new
oracle entry.

## After O5.4
With the ladder + opaque Bools differentially bound, the model extension
(perception-refresh `cycleStep` step) becomes honest: its new `objectiveStepFires`
arming is validated against production's perceive. Then discharge the chore-clear +
`hperc` out of the bootstrap window → level-50 completeness modulo only LIV-001.

## Status — COMPLETE (2026-06-18)
All bricks landed on main; the Lean liveness ladder (`fires`/`productionLadder`,
all 23 slots) is differentially bound to production AND mutation-enforced.
- Brick 1 — computable ladder (62832e3).
- Brick 2 — oracle `ladder_fires` entry (7982bbb).
- Brick 3 — numeric-guard differential, 16 slots asserted (4d3988a).
- Brick 4a — craftRelief + recycleSurplus + drive_and_contest scaffold (0117491).
- Brick 4b — restForCombat (idx-1 strong contest) + maintainConsumables (9a214aa).
- Brick 4c — taskCancel + pursueTask + lowYieldCancel via real LearningStore (dda10eb).
- Brick 5 — 20 mutation anchors on the ladder predicates, 20/20 killed; docstring
  refresh (e84799a).
Each brick: implementer + adversarial reviewer (spec PASS, quality APPROVED), full
Python suite green (2371). `formal/diff/test_ladder_fires_diff.py` = 35 tests.

KEY FINDINGS surfaced: (a) recycleSurplus + maintainConsumables can NEVER win Lean
selection (lifecycle slots partition all phases above them) — honest fire-and-lose;
(b) phase-derived slots (taskCancel/pursueTask/lowYieldCancel) are Lean
over-approximations of production's history/task_decision — driven via consistent
scenarios; (c) for opaque-passthrough slots the per-slot check is fed-through
(vacuous) — the teeth are entirely in the `selected` (productionLadder) assertion.

NEXT (post-O5.4): the perception-refresh MODEL EXTENSION is now honest to build
(its objectiveStepFires arming is differentially validated) → discharge chore-clear
+ hperc out of the bootstrap window ([[project_b0_bootstrap_reach]]) → level-50
completeness modulo only LIV-001.
