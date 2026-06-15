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
  - **hperc — open.** Needs the maintained perception invariant
    `xp < xpToNextLevel level` (ApplyXpLevelPreservation has the per-step piece)
    inducted across the trajectory, plus `level < 50` / `bankRequiredLevel ≤ 50`.

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
- `GlobalInvariants` now reduces to just **{hperc, hfightFires}** + 2 spawn facts.
- **O5.3 hperc — open** — perception invariant `xp < xpToNextLevel level` inducted
  across the trajectory + `level < 50 / bankRequiredLevel ≤ 50`.
- **O5.2 hfightFires — open, the crux** — fight-fairness: now that a productive
  means ALWAYS fires (hnowait), the remaining gap is that it is INFINITELY OFTEN a
  fight (the only char-XP source), not endless accept/pursue/gather. The
  combat-existence catalog derivation (user's choice) plugs in HERE, not at hnowait.
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
