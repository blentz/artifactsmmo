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

## O5.2 reformulation — DEFINITIVE finding + model-extension design (2026-06-15)

Deeper than "hfightFires is unprovable": the liveness MODEL is fundamentally
incomplete for general leveling.

- The ONLY level-advancing transition is `Plan.applyActionKind .fight` (+10 xp,
  rollover). `planFor` yields `.fight` ONLY from `bankUnlock` / `reachUnlockLevel`
  (bank-bootstrap; stop firing once the bank is unlocked).
- `completeTask`'s rollover is DEAD: `Measure.taskCompleteXpEstimate := 0` (items
  tasks award no char XP), so `xp + 0 ≥ xpToNextLevel` never holds under the
  perception invariant — the code says so at Measure.lean:400-405.
- `objectiveStep` apply is a no-op (`{ s with objectiveStepFires := false }`).
- There is NO grindCharacterXP / reachCharLevel / combat-farm means in
  `allInLadderOrder` (22 means; none is general combat-leveling).

⇒ Post-bank-bootstrap the model has NO way to gain char XP. `ai_reaches_level_fifty`
is vacuous on `hfightFires` (which cannot hold). For a HONEST level-50 theorem the
model must gain a faithful general combat-leveling means.

### ✗ FIRST design (a new `grindCharacterXP` discretionary means) — INVALID

Rejected 2026-06-16. A new means appended to the discretionary tail (before
`.wait`) would **NEVER be selected**, by the SAME task-totality that discharged
hnowait: `acceptTask` / `pursueTask` / `completeTask` are phase-total (one fires
in EVERY state) and sit at ladder idx 10/15/16, AHEAD of the discretionary tail.
So `productionLadder` always returns a task means (or an earlier-firing guard);
nothing after `acceptTask` is ever the first firing. A grind means at idx 21 is
dead on arrival. Placing it as a high-priority GUARD instead (before the task
means) is unfaithful — production does not preempt all task/productive work to
grind char levels. ⇒ the leveling means cannot be a NEW ladder entry.

### ✓ CORRECTED design — monster-task pursuit fires `.fight` (rides the task loop)

The faithful gap is narrower and routes through the means that DO fire. In the
real game a MONSTER-kill task is pursued BY fighting the monster, which grants
char XP + task progress. The Lean model collapsed `pursueTask` to the ITEMS-task
case only (`planFor .pursueTask = [.taskTrade]`, no char XP). Fix:
1. Add a task-type discriminant to `State` (e.g. `taskIsMonster : Bool := false`;
   default keeps every existing items-task fixture/proof intact — low ripple,
   `{s with …}` updates unaffected; only full literals need the field).
2. `planFor .pursueTask s = if s.taskIsMonster then [.fight] else [.taskTrade]`.
   `.fight` already grants +10 char xp + level rollover (no new apply branch);
   ALSO bump `taskProgress` on a monster-task fight (mirror FightProgress.
   fightApply `monsterMatchesTask`).
3. `acceptTask` sets `taskIsMonster` from the accepted task (model the task pool
   as carrying monster tasks). Leveling then rides the ALREADY-PROVEN-total task
   loop: monster tasks accepted infinitely often → pursued via fights → +10 xp
   each → level 50.
4. Reformulate `hfightFires` to "a level-advancing `.fight` (via monster-task
   `pursueTask`) fires infinitely often" and DISCHARGE from task-totality + the
   xp accumulation accounting; re-route `lifecycle_progress_from_bounds_proven`.

### Remaining FAITHFULNESS obligations (O5.4-adjacent, named honestly)
- **server task pool contains monster tasks** (so `acceptTask` can set
  `taskIsMonster`) — derive from the cached task catalog (user's earlier choice:
  catalog-derived, not an axiom), OR a named server axiom + openapi citation.
- **a winnable monster exists at every level < 50** — supports model FAITHFULNESS
  (the modelled always-succeed `.fight` matches a real win). NOTE: NOT on the
  leveling proof's critical path — the model's `.fight` grants xp
  unconditionally; winnability is the O5.4 binding question, not O5.2.

### Blast radius (measured 2026-06-16)
12 files `cases k` over MeansKind, 5 reference `allInLadderOrder`, 16 reference
`pursueTask`. State is built via `{s with …}` (record update) almost everywhere,
so the new field is low-ripple. The `planFor .pursueTask` change ripples into
`PlanExists.plan_exists_for_pursueTask` (PlanExists.lean:676) + the lifecycle
bound lemmas + the cycle-step diff — bounded and mechanical, but it MUST build
green at each step (kernel-gated), not a fatigued ram-through. This is the
genuine remaining CORE of obligation 5.

### Increment 1 landed (2026-06-16) — keystone + faithful field

- **`State.objectiveStepIsFight : Bool := false`** added (Measure.lean) — the
  discriminant for "the objective tier's emitted step leads with a Fight"
  (production `ReachCharLevel` meta-goal / combat objectives). Default keeps every
  existing proof green (free; full build 6199 jobs).
- **`Formal/Liveness/PerceptionInvariant.lean` (NEW, PROVEN)** — the keystone.
  `XpInBand s := s.level < 50 → s.xp < xpToNextLevel s.level` is `cycleStep`- and
  `cycleStepN`-PRESERVED (`applyActionKind_preserves_XpInBand` over all action
  kinds; `.fight`/`.completeTask` rollover both preserve via LIV-001 positivity),
  and holds at spawn (`spawn_XpInBand`). This discharges the fight-progress
  perception invariant `hperc` as a from-spawn consequence — mirroring how
  `GameDataInvariance` discharged hex/hbe — instead of a threaded `hperc'`
  hypothesis. Axioms {propext, Quot.sound, xpToNextLevel(_pos)}; liveness axiom
  check OK; wired into Formal.lean + LivenessAudit.
- **Why keystone:** the `objectiveStep`-fight measure-decrease (the actual routing,
  Increment 2) needs exactly `xp < xpToNextLevel level` to show `+10` xp shrinks the
  xp-distance. With the invariant free-from-spawn, Increment 2 replicates the
  existing `reachUnlockLevel` argument with NO new runtime obligation.
### Increment 2 landed (2026-06-16) — the routing + measure-decrease

- **`planFor .objectiveStep s = if s.objectiveStepIsFight then [.fight] else
  [.objectiveStep]`** (CycleStep.lean) — the model now FIGHTS for a combat
  objective. Fixed the dependent proofs: `planFor_ne_nil`,
  `cycleStep_progress_or_waits` (objectiveStep-fight ≠ s via xp+10 / rollover),
  `CycleStep.cycleStep_level_ge`, and `CycleStepCharacterization` (audited; added
  an explicit `objectiveStep ⇒ ¬isFight` guard since a combat objective now
  genuinely advances level/xp).
- **`progressMeans_decreases_extMeasure_or_advances_level`** — objectiveStep-fight
  case proven: either level advances (rollover) OR xpDeficit strictly decreases,
  IDENTICAL to the `reachUnlockLevel` fight argument. `hperc` extended to the
  3-way disjunction `{bankUnlock, reachUnlockLevel, objectiveStep∧isFight}` and
  threaded through `cumulative_progress_under_no_wait_restricted` (signature +
  WF-induction motive + `hperc_succ`). Both are leaf theorems (audited only), so
  the signature change ripples nowhere else. Full build 6199 jobs green; liveness
  axiom check OK.
- ⇒ the model is now genuinely CAPABLE of general char leveling (objectiveStep at
  ladder idx 14 fires while level<50; the cumulative-progress measure proves it
  advances level). The perception invariant the fight needs is available free
  from spawn via Increment 1's `cycleStepN_preserves_XpInBand`.

### Increment 3 landed (2026-06-16) — capstone vacuity KILLED

- **`GlobalInvariants.hfightFires` reformulated to the 3-way disjunction**
  `{bankUnlock, reachUnlockLevel, objectiveStep∧objectiveStepIsFight}`
  (LevelFiftyReachable.lean). The third disjunct is the combat objective — it
  FIRES while `level < 50` (idx 14, before the discretionary task means; `.fight`
  does not clear `objectiveStepFires`, so it can recur), making `hfightFires`
  **SATISFIABLE**. The capstone `ai_reaches_level_fifty` is no longer vacuous: it
  is honest conditional reachability — IF the planner fights via a combat
  objective infinitely often THEN it reaches 50. Disclosure rewritten accordingly
  (field comment + module docstring).
- **Fight characterization extended** (CycleStepCharacterization.lean):
  `cycleStep_eq_fight_when_objectiveStepFight` + the combined
  `cycleStep_eq_fight_when_fightCycleFires` (3-way). `LifecycleBound7`
  (`xp_accumulates_when_level_constant`, `lifecycle_progress_from_bounds_proven`)
  and `ReducedReachability.ai_reaches_level_fifty_config_positive` all widened to
  the 3-way `hfightFires` and re-routed through the combined lemma.
- **No keystone needed on the capstone path:** LifecycleBound7's argument is
  xp-accumulation-by-contradiction (drive xp past `xpToNextLevel` via fights, then
  rollover), which needs only `hlvl` + `hfightFires` — NOT the perception
  invariant. Increment 1's `cycleStepN_preserves_XpInBand` remains a valid proven
  invariant that discharges `hperc` for the alternate cumulative-progress leaf
  path (Increment 2); it is simply not on the capstone's critical path.
- Capstone axioms {propext, Classical.choice, Quot.sound, xpToNextLevel(_pos)} =
  standard + LIV-001; full build 6199 jobs green; liveness axiom check OK.

### Increment 4 landed (2026-06-16) — fairness REDUCTION + end-to-end capstone

`Formal/Liveness/FightFairness.lean` (NEW, proven) reduces `hfightFires` to ONE
precise runtime Prop and proves the reduction + an end-to-end theorem:
- **`productionLadder_eq_objectiveStep_of_unblocked`** — selection mechanics: a
  firing combat objective with all 14 higher-priority means (`objectiveStepBlockers`,
  idx 0–13) quiet ⇒ the ladder SELECTS `objectiveStep` (so the cycle fights). Pure
  `findSome?`-over-`allInLadderOrder` proof (`ladder_split_objectiveStep` by decide).
- **`CombatObjectiveFairlyScheduled s`** — the EXACT remaining obligation as a Lean
  Prop: ∀N ∃k≥N the combat objective fires, is combat-typed (`objectiveStepIsFight`),
  and is unblocked at `cycleStepN k s`.
- **`hfightFires_of_combat_scheduled`** — discharges the capstone's 3-way
  `hfightFires` from `CombatObjectiveFairlyScheduled`.
- **`ai_reaches_level_fifty_from_fair_combat`** — END-TO-END: spawn config-positivity
  (`taskExchangeMinCoins`, `nextExpansionCost` > 0) + `CombatObjectiveFairlyScheduled`
  ⇒ `∃ k, level ≥ 50`. Composes the reduction with
  `ai_reaches_level_fifty_config_positive`. Axioms standard + LIV-001; in the
  liveness audit; full build 6201 jobs green; axiom check OK.

⇒ Every `GlobalInvariants` component is now discharged or named precisely:
hnowait (unconditional), hex/hbe (config-invariant), and `hfightFires` reduced to
the single satisfiable Prop `CombatObjectiveFairlyScheduled`. The capstone is honest
conditional reachability on exactly ONE runtime property — "the planner keeps
fighting via a combat objective."

### Increment 5 landed (2026-06-16) — transience DECOMPOSITION (reduction proven)

`FightFairness.lean` extended: `CombatObjectiveFairlyScheduled` split into its two
genuine atoms, with the reduction + a cleaner end-to-end proven:
- **`CombatPersistent s`** — the PLANNER atom: `objectiveStepFires ∧
  objectiveStepIsFight` at every trajectory state (the `ReachCharLevel`-driven
  combat goal stays active). Opaque to `cycleStep` mechanics ⇒ an honest runtime
  hypothesis.
- **`BlockersQuietInfinitelyOften s`** — the pure SCHEDULING atom: ∀N ∃k≥N no
  `objectiveStepBlocker` fires.
- **`combat_scheduled_of_persistent_and_quiet`** — proven: the two atoms ⇒
  `CombatObjectiveFairlyScheduled`.
- **`ai_reaches_level_fifty_from_persistent_combat`** — proven end-to-end: spawn
  config-positivity + `CombatPersistent` + `BlockersQuietInfinitelyOften` ⇒
  `∃ k, level ≥ 50`. In the audit; full build 6201 jobs green; axiom check OK.

HONEST: this is the transience REDUCTION, not the transience itself. The deep
core `BlockersQuietInfinitelyOften`-from-spawn is NOT proven — see below. Not
faked.

### Increment 6 landed (2026-06-16) — blocker one-step quieting (mechanism proven)

`Formal/Liveness/BlockerQuieting.lean` (NEW, proven): each blocker's `planFor`
action CLEARS its own firing condition, so it cannot fire two cycles running.
`<blocker>_quiet_after_firing : productionLadder s = some b ⇒ fires b (cycleStep s)
= false` for 13 of 14 blockers (all but `reachUnlockLevel`, which is gap-bounded):
- flag-clearing: discardCritical/discardHigh (deleteItem→¬overstock), craftRelief
  (craft), depositFull (depositAll), gearReview (optimizeLoadout), claimPending,
  sellPressured (npcSell);
- phase-reset: completeTask, taskCancel, lowYieldCancel (→ phase .none);
- hp-restore: hpCritical, restForCombat (rest→hp=maxHp);
- bootstrap: bankUnlock (fight flips bankAccessible:=true).
Axioms standard + LIV-001; in the audit; full build 6203 jobs green; check OK.
These are the building blocks: combined with flag/field MONOTONICITY (no
`applyActionKind` re-arms the opaque flags / hp / level / bankAccessible) they bound
total blocker firings.

### Increment 7 landed (2026-06-16) — PERMANENT quieting via flag monotonicity

`Formal/Liveness/BlockerMonotone.lean` (NEW, proven): the 6 opaque blocker flags
are only ever cleared (never re-armed) by `applyActionKind` — verified against
`Plan.lean` — so once `false` they stay `false` along `cycleStepN`
(`<flag>_false_cycleStepN`, uniform `cases`-over-actions like the `XpInBand`
keystone). Hence `<blocker>_quiet_forever`: once the flag clears, the blocker NEVER
fires again — for **7 of 14** blockers (discardCritical, discardHigh, depositFull,
gearReview, claimPending, sellPressured, craftRelief). Axioms standard + LIV-001; in
the audit; full build 6205 jobs green; check OK.

### Increment 8 landed (2026-06-16) — hp + bootstrap permanent quieting (10/14)

`BlockerMonotone.lean` extended: `hp = maxHp` is `cycleStep`-monotone (`hp` only
restored by rest, never reduced) ⇒ `hpCritical_quiet_forever`,
`restForCombat_quiet_forever`; `bankAccessible = true` is monotone (fight flips it
true, nothing flips back) ⇒ `bankUnlock_quiet_forever`. Now **10 of 14** blockers
have permanent quieting. Full build 6205 jobs green; axiom check OK.

### Increment 9 landed (2026-06-16) — reachUnlockLevel permanent quieting (11/14)

`reachUnlockLevel_quiet_forever` (BlockerMonotone): `level` is `cycleStepN`-monotone
(`LifecycleBound6.cycleStepN_level_ge`) and `bankRequiredLevel` is invariant (no
`applyActionKind` assigns it — proved `bankRequiredLevel_cycleStepN`), so once
`level ≥ bankRequiredLevel` the `level < bankRequiredLevel` conjunct fails forever.
**11 of 14** blockers permanently quieted. Full build 6205 jobs green; check OK.

### Increment 10 landed (2026-06-16) — the COUPLING RESOLVED via a `Settled` state

`Formal/Liveness/BlockerSettled.lean` (NEW, proven) breaks the task-phase /
composition circularity with a SELF-PRESERVING `Settled` state bundling all 14
clearing conditions (6 flags false, hp=maxHp, bankAccessible, level≥bankRequiredLevel,
phase=.none, objectiveStepFires, objectiveStepIsFight):
- **`Settled_blockers_quiet`** — at a `Settled` state ALL 14 blockers are quiet
  (`fin_cases` over `objectiveStepBlockers`, each from the matching field).
- **`Settled_productionLadder`** — therefore `objectiveStep` is SELECTED (combat
  objective fires + all blockers quiet → the increment-4 selection lemma).
- **`Settled_cycleStep`** — so the cycle is a `.fight`, which preserves EVERY
  `Settled` field (fight touches only level/xp/bankAccessible/actionsAttempted;
  level≥bankRequiredLevel survives as level is non-decreasing; bankAccessible stays
  true; phase untouched). `Settled` is `cycleStep`-invariant.
- **`combatScheduled_of_settled`** — a single `Settled` state ⇒
  `CombatObjectiveFairlyScheduled` (invariance ⇒ combat fires+unblocked at every k).
- **`ai_reaches_level_fifty_of_settled`** — config-positivity + `Settled` ⇒
  `∃ k, level ≥ 50`. The ENTIRE hfightFires/blocker-transience tower collapses to
  ONE hypothesis: the trajectory reaches a `Settled` state.
Axioms standard + LIV-001; in the audit; full build 6207 jobs green; check OK.

### Increment 11 landed (2026-06-16) — `Settled` satisfiable + a GROUNDED capstone

`Formal/Liveness/SettledWitness.lean` (NEW, proven): `settledWitness` = the live
`fixtureFreshState` with the task parked at `.none` and a combat objective committed.
- **`settledWitness_isSettled`** — `Settled` is SATISFIABLE (anti-vacuity: the
  `Settled`-gated capstone is a genuine implication, not vacuously true on `False`).
- **`settledWitness_reaches_fifty : ∃ k, (cycleStepN k settledWitness).level ≥ 50`** —
  the witness ALSO discharges spawn config-positivity (`taskExchangeMinCoins = 1`,
  `nextExpansionCost = 1`), so `ai_reaches_level_fifty_of_settled` closes with NO
  remaining hypotheses. A CONCRETE, hypothesis-free (modulo only LIV-001) proof that
  the planner iterates `cycleStep` to level 50 from a real state — the honest,
  non-vacuous payoff of the whole O5.2 arc. Axioms standard + LIV-001; in the audit;
  full build 6209 jobs green; check OK.

### Increment 12 landed (2026-06-16) — the reach frontier + the O5.4 perception proof

`Formal/Liveness/SettledReach.lean` (NEW, proven):
- **`reach_fifty_of_eventually_settled`** — config-positivity is `cycleStepN`-
  invariant, so if the trajectory EVER reaches `Settled`, level 50 follows. The whole
  obligation collapses to the single fact `∃K, Settled (cycleStepN K s)`.
- **`Settled_unreachable_without_perception`** — PROVEN: in the pure model
  `objectiveStepFires` is never set `true` by any action (only cleared — verified vs
  Plan.lean), so if it is `false` at spawn it stays `false` and `Settled` is
  UNREACHABLE. ⇒ reaching `Settled` REQUIRES perception to commit the combat
  objective; the model cannot fabricate the planner's goal. The O5.4 select/perception
  obligation, now a THEOREM not an assertion. Axioms standard + LIV-001; full build
  6211 jobs green; check OK.

### Remaining — REACH a Settled state from an ARBITRARY spawn (the transient) + O5.4
- **Reach `Settled`** — `∃K, Settled (cycleStepN K s)` from spawn. This IS the
  transient (drive each clearing condition true once: discard overstock, deposit,
  sell, claim, rest, unlock bank, reach unlock level, park the task at .none) PLUS the
  perception input objectiveStepFires/IsFight (incr 12 proved this REQUIRES perception
  — not model-producible). The per-blocker one-step quieting (incr 6) + monotonicity
  (incr 7–9) show each condition, once true, STAYS true; reaching them is the
  bounded warm-up. Now a clean self-contained goal (no circularity).
- **O5.4 diff binding** — bind `objectiveStepIsFight` (and the opaque flags) to
  production + the `productionLadder` select + the perception-refresh faithfulness.
  In-model each of the 14 `objectiveStepBlockers` clears its own firing flag on its
  `planFor` action (deleteItem→¬overstock, depositAll→¬deposits, npcSell→¬sellable,
  completeTask→task cleared, bootstrap fights retire on unlock) and nothing re-arms
  it, so blocker firings are in-model finite ⇒ eventually-quiet ⇒ quiet ∞-often.
  But: (a) it is a 14-blocker termination — 9 are in `progressMeans` (decrease
  `extMeasure`) but 5 are NOT (restForCombat, gearReview, completeTask,
  lowYieldCancel, taskCancel) and need separate bounding; (b) "nothing re-arms the
  flag" leans on the model abstracting away the PERCEPTION REFRESH (which in the
  real bot re-arms guards) — so even the in-model result is an O5.4 faithfulness
  question. A real multi-session proof; not attempted half-baked.
- **O5.4 diff binding** — bind `objectiveStepIsFight` to production ("the
  objective-tier plan's head action is Fight") + `productionLadder` select +
  the perception-refresh faithfulness above.

### Status surfaced in code (2026-06-16)
`LevelFiftyReachable.lean` now carries a ⚠ HONEST SCOPE DISCLOSURE at the
`hfightFires` field AND in the module docstring: the capstone is currently
VACUOUS on `hfightFires` (unsatisfiable post-bootstrap for realistic configs).
The green build is explicitly NOT yet an honest level-50 guarantee until the
corrected design lands. No proof faked; the gap is named exactly at the site.
