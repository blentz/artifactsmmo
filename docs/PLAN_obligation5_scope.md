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

### Status surfaced in code (2026-06-16)
`LevelFiftyReachable.lean` now carries a ⚠ HONEST SCOPE DISCLOSURE at the
`hfightFires` field AND in the module docstring: the capstone is currently
VACUOUS on `hfightFires` (unsatisfiable post-bootstrap for realistic configs).
The green build is explicitly NOT yet an honest level-50 guarantee until the
corrected design lands. No proof faked; the gap is named exactly at the site.
