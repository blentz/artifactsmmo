# Obligation 5 — scope: global termination (planner reaches level 50)

Scoped 2026-06-15. The "reaches level 50 from any state" theorem.

## TL;DR — it is mostly already proven; one hypothesis is the real gap.

`Formal/Liveness/LevelFiftyReachable.lean` ALREADY proves:
```
theorem ai_reaches_level_fifty (s : State) (h : GlobalInvariants s) :
    ∃ k, (cycleStepN k s).level ≥ 50
```
Axioms: `{propext, Classical.choice, Quot.sound, Measure.xpToNextLevel,
xpToNextLevel_pos}` — i.e. the standard set PLUS the single named **LIV-001**
server axiom (XP-to-next-level is positive; unprovable without server data,
already signed off with openapi citation).

So obligation 5 reduces to **discharging the `GlobalInvariants s` hypothesis for a
real spawn state**. Everything else in the chain is done:
- per-action measure decrease — DONE (FightProgress/GatherProgress/DepositProgress/
  RestProgress/ProgressAction.step_decreases_measure).
- per-firing positivity — DONE (MeansFiring._fires_*_implies_*_positive).
- non-deadlock, `productionLadder s ≠ none` — DONE UNCONDITIONALLY
  (NoDeadlockV2.productionLadder_total), but only via the `.wait` last-resort
  fall-through. So "never deadlocks" is proven; "never WAITS while < 50" is not.

## What `GlobalInvariants` bundles (the gap), and the sub-obligations

`GlobalInvariants s` (LevelFiftyReachable.lean:57) requires, at EVERY state
reachable from `s` via `cycleStepN`:

- **O5.1 — hnowait — DONE 2026-06-15** (`Formal/Liveness/NoWait.lean`,
  `productionLadder_ne_wait`). UNCONDITIONAL, axioms {propext, Quot.sound} (NOT
  even LIV-001). The original worry (needs a combat-existence game-data axiom)
  turned out UNNECESSARY: hnowait holds from the TASK LIFECYCLE alone. The three
  task means are phase-total — `acceptTaskFires = (phase=none)`,
  `pursueTaskFires = (phase ∈ {accepted,inProgress})`,
  `completeTaskFires = (phase=complete)` — so for EVERY state one fires, and all
  three sit before `.wait` in `allInLadderOrder`. The first firing means is
  therefore never `.wait`: the bot always has a task move (accept/pursue/complete)
  and is never idle. This is the HONEST no-deadlock the user demanded, replacing
  the vacuous `productionLadder_total` (which was satisfied by `.wait` itself).
  No game-data axiom needed.

- **O5.2 — hfightFires**: `∀ N, ∃ k ≥ N, productionLadder (cycleStepN k s) ∈
  {bankUnlock, reachUnlockLevel}`. The trajectory drives FIGHTS infinitely often.
  Char XP comes only from fight/completeTask, so level advance REQUIRES unbounded
  fights. This is a FAIRNESS / scheduling-progress property: the planner must not
  loop forever on non-fight productive work (gather→craft→deposit→…) without ever
  fighting. THE HARDEST sub-obligation — it needs an argument that fight-driving
  goals eventually dominate the ranking (or that the lexicographic measure forces
  a fight once non-fight deficits are exhausted). No existing theorem; this is the
  intellectual core of what remains.

- **O5.3 — hperc / hex / hbe**: when bankUnlock/reachUnlockLevel fire,
  `xp < xpToNextLevel level ∧ level < 50`; when taskExchange/bankExpand fire,
  `taskExchangeMinCoins / nextExpansionCost > 0`. Pure state-invariant lemmas,
  dischargeable from the means-firing preconditions without new axioms. CHEAPEST.
  - **hex / hbe — DONE 2026-06-15** (`Formal/Liveness/ReducedReachability.lean`,
    `ai_reaches_level_fifty_config_positive`). `taskExchangeMinCoins` /
    `nextExpansionCost` are `cycleStepN`-invariant (GameDataInvariance), so spawn
    positivity ⇒ trajectory positivity ⇒ the conditional hex/hbe hold. No new
    axioms (standard + LIV-001 only); in the liveness axiom probe.
    GlobalInvariants now reduces to {hnowait, hperc, hfightFires} + 2 spawn facts.
  - **hperc — DONE 2026-06-15 (removed as DEAD).** Investigation showed hperc was
    NEVER consumed: it reached `lifecycle_progress_from_bounds_proven` only as an
    underscore-bound (unused) parameter, and it is not even unconditionally true
    (bankUnlock can fire at level ≥ 50, where `level < 50` is false). So it was a
    spurious hypothesis. Removed from `GlobalInvariants` / `globalInvariants_step`
    / `level_advances_once` / `lifecycle_progress_from_bounds_proven` —
    STRENGTHENING the capstone (one fewer runtime obligation), no proof faked.

## Two further gaps beyond `GlobalInvariants`

- **O5.4 — model faithfulness**: the proof is about the Lean `cycleStep`. The
  cycle-step differential (`formal/diff/test_cycle_step_diff.py`) binds only
  `action.apply` projections to production — it EXPLICITLY does NOT exercise
  `arbiter.select` / `productionLadder` / the perception refresh (self-disclosed).
  So the model's SELECT side is not yet differentially bound to the real loop.
  Strengthening that binding (or recording the residual trust honestly) is needed
  before the theorem can claim to speak about the running bot, not just the model.

- **O5.5 — closed-form K** (optional): the `∃ k` is existential. A computable
  `K ≤ 49 × max_per_cycle_K` could be derived from the LIV-003 small axioms
  (lowYieldSampleThreshold, taskPoolFinite). Nice-to-have, not load-bearing.

## Progress / remaining (updated 2026-06-15)
- **O5.1 hnowait — DONE** (unconditional, task-lifecycle; no axiom). Replaces the
  vacuous `productionLadder_total` (`.wait` fall-through).
- **O5.3 hex/hbe — DONE** (config-positivity invariance).
- **O5.3 hperc — DONE** (removed as a dead/spurious hypothesis; see above).
- `GlobalInvariants` is now {hnowait✓, hex✓, hbe✓, hfightFires};
  `ai_reaches_level_fifty_config_positive` needs only **spawn config-positivity +
  hfightFires**. So `hfightFires` is the SOLE remaining substantive runtime
  obligation.
- **O5.2 hfightFires — open, THE CRUX. Deep-dive 2026-06-15 found the real
  obstacle (it is bigger than a fairness proof):**
  - The model advances level ONLY on `.fight` and `.taskTrade` (Plan.applyActionKind
    rollover branches). `planFor` produces `.fight` ONLY from `bankUnlock` /
    `reachUnlockLevel`, and `.taskTrade` ONLY from `pursueTask`.
  - `bankUnlock` fires only while `¬bankAccessible`; `reachUnlockLevel` only while
    `level < bankRequiredLevel`. Both are BANK-UNLOCK BOOTSTRAP means — they STOP
    firing once the bank is unlocked, far below level 50. So `hfightFires`
    (`bankUnlock ∨ reachUnlockLevel` infinitely often) is **NOT TRUE** of any
    trajectory that unlocks the bank — it is an unprovable hypothesis, and the
    capstone currently leans on it (conditionally vacuous, like the `.wait` issue).
  - The FAITHFUL general leveling path is the TASK LOOP: `acceptTask` (phase=none) →
    `pursueTask` (phase∈{accepted,inProgress}) → `.taskTrade` → level rollover. This
    is the same task lifecycle that discharged hnowait, and it runs to 50.
  - **Required work (multi-session):**
    1. Reformulate the leveling obligation from `hfightFires` to a TASK-LOOP form:
       the trajectory does a level-advancing `.taskTrade` (via pursueTask) infinitely
       often. Prove the task-fairness (phase is active infinitely — extends the
       hnowait task-totality) AND the rollover accumulation (`willLevel` met
       infinitely: task reward XP accrues past `xpToNextLevel`).
    2. Re-route `lifecycle_progress_from_bounds_proven` (currently `.fight`-rollover
       only) to also advance on `.taskTrade`.
    3. The combat-existence catalog derivation (user's choice) feeds the FIGHT side
       (monster tasks → fights → reward), grounding the task-reward XP.
  - This is the genuine intellectual core and overlaps O5.4 (model faithfulness):
    the model's narrow fight path is itself a faithfulness gap.
- **O5.4 model faithfulness — open.**  **O5.5 closed-form K — optional.**

## Decision needed from the user before O5.1
The combat-existence fact (a winnable monster exists at every level < 50) is a
property of the SERVER's monster table, not of our code. Options:
- (a) named server axiom + openapi citation (per existing LIV-001 precedent), or
- (b) derive it as a theorem from the cached monster catalog (`GameDataFixture`-style),
  pinning the specific monsters per level band.
(b) is stronger/honest but more work and ties the proof to a catalog snapshot.

## First concrete increment (recommended)
O5.3 — the three perception/precondition invariant lemmas. Self-contained, no new
axioms, shrinks the headline hypothesis, and warms up the cycleStep/measure
machinery before the hard O5.1/O5.2 work.
