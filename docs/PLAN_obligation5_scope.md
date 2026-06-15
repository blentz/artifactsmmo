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

- **O5.1 — hnowait**: `productionLadder (cycleStepN k s) ≠ some .wait` ∀k. The
  planner never falls through to WAIT while < 50 — a PRODUCTIVE means always
  fires. The conditional form `productionLadder_total_under_invariants` exists;
  discharging the condition is the work. DEPENDS ON: a winnable monster (or a
  productive gather/craft) is available at every level-<50 state.
  `CombatTargetExistence.pickWinnable_some_of_exists` is proved CONDITIONALLY on
  "∃ winnable monster" — so this needs a GAME-DATA fact: *at every level < 50 the
  monster table contains a stat-winnable monster*. Per the liveness axiom policy
  ([[project_liveness_axiom_split]]) that is a new named server axiom needing
  user signoff + an openapi-spec citation, OR a derivation from the cached
  monster table. **This is a decision point, not just a proof.**

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

## Recommended sequence
1. **O5.3** (cheap, no new axioms) — discharge hperc/hex/hbe; shrinks
   `GlobalInvariants` to {hnowait, hfightFires}. Good warm-up, immediate win.
2. **O5.1** (foundational) — FIRST a DECISION on the game-data combat-existence
   axiom (introduce named `winnableMonsterExistsBelow50` with openapi citation, or
   derive from the monster table). Then discharge hnowait.
3. **O5.2** (the crux) — the fight-fairness theorem. Largest effort.
4. **O5.4** — extend the cycle-step diff to bind the select side.
5. **O5.5** — optional closed-form K.

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
