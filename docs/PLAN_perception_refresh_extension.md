# PLAN: perception-refresh model extension (post-O5.4)

## Goal
Convert the "a combat objective is committed below the level cap" obligation from
a runtime ASSUMPTION into an IN-MODEL fact, by adding a `perceptionRefresh` step
to the cycle that arms `objectiveStepFires`/`objectiveStepIsFight` while
`level < 50`. With O5.4 complete (the ladder is differentially bound + mutation-
enforced), this extension is now HONEST to build — the arming's faithfulness is a
differential obligation, not an author claim.

## What the capstone actually needs (from the read, 2026-06-18)
`LevelFiftyReachable.ai_reaches_level_fifty (s) (h : GlobalInvariants s)`.
`GlobalInvariants = { hnowait, hex, hbe, hfightFires }` — the `hperc` field was
already REMOVED (2026-06-15). The binding obligation is:

```
hfightFires : ∀ N, ∃ k ≥ N,
    productionLadder (cycleStepN k s) = some .bankUnlock
  ∨ productionLadder (cycleStepN k s) = some .reachUnlockLevel
  ∨ (productionLadder (cycleStepN k s) = some .objectiveStep
      ∧ (cycleStepN k s).objectiveStepIsFight = true)
```

Two regimes:
- **`level < bankRequiredLevel`**: B-0 (`BootstrapReach`) already gives
  `reachUnlockLevel` SELECTED — the 2nd disjunct. `hfightFires` is FREE here.
- **`bankRequiredLevel ≤ level < 50`** (post-unlock): `bankUnlock`/
  `reachUnlockLevel` retire permanently, so only the 3rd disjunct remains. It
  needs BOTH (a) `objectiveStepFires`/`objectiveStepIsFight` armed AND (b)
  `objectiveStep` (ladder idx 14) SELECTED — i.e. the 14 higher slots quiet.

The perception-refresh closes (a). (b) is `BlockersQuietInfinitelyOften` — a
SEPARATE residual (see below).

## The perception frontier this overturns
`SettledReach.objectiveStepFires_false_cycleStepN`: the pure transition NEVER sets
`objectiveStepFires = true` (only clears/preserves false). Hence
`Settled_unreachable_without_perception`. The refresh is precisely what re-arms it.

## Design

### `perceptionRefresh : State → State` (minimal, faithful)
```
perceptionRefresh s :=
  if s.level < 50 then
    { s with objectiveStepFires := true, objectiveStepIsFight := true }
  else s
```
Rationale: below the cap the `ReachCharLevel` meta-goal is committed and its plan
LEADS WITH A FIGHT — PROVIDED a winnable XP-positive monster exists in the band.
That proviso is exactly `GearTierLeveling.combatObjective_live_below_fifty`
(`WinnableAcrossBand → ∀ L in band, ∃ winnable target`). So arming on `level < 50`
is faithful MODULO `WinnableAcrossBand`.

**Why arm ONLY these two Bools (not the chore flags):** production's `perceive`
recomputes ALL guard flags, but the Lean model ABSTRACTS inventory composition —
it cannot faithfully recompute `hasOverstockItems`/`selectBankDepositsNonempty`/…
So a refresh that re-armed chores would be a fabrication. Arming only
`objectiveStepFires` adds exactly what the model CAN observe faithfully (objective
liveness ↔ `level < 50` ↔ `WinnableAcrossBand`). The chore-transience
(`BlockersQuietInfinitelyOften`) stays the existing documented in-model gap
(FightFairness.lean:106-126), neither helped nor hurt.

### Composition: `cycleStepP s := cycleStep (perceptionRefresh s)`
Do NOT redefine `cycleStep` — that would break ~50 existing proofs. Define a NEW
`cycleStepP` and re-establish reachability for it. The cascade is SMALL because
`perceptionRefresh` is the IDENTITY on every field except the two objective Bools:
- All measure/level/xp/hp/blocker lemmas that don't READ those two Bools transfer
  verbatim (prove `perceptionRefresh_preserves_<field>` bridges, mostly `rfl`).
- B-0's descent transfers: `perceptionRefresh` preserves level/xp/bankRequiredLevel
  and the hp/rest quiet, so `cycleStepP` descends the lex measure exactly as
  `cycleStep` does in the bootstrap window.

### The new in-model fact
`objectiveStepFires (cycleStepP^k s) = true` whenever `level < 50` — because every
cycle begins with `perceptionRefresh` arming it. This OVERTURNS
`objectiveStepFires_false_cycleStepN` for `cycleStepP` and discharges the
objective-committed half of `hfightFires`.

## Honest end-state (NOT "modulo only LIV-001" — be precise)
After the extension, level-50 reachability rests on:
1. **LIV-001** — server xp-curve axiom. Irreducible.
2. **WinnableAcrossBand** — a winnable XP-positive monster exists in every leveling
   band. Currently a satisfiable HYPOTHESIS (gear-tier residual,
   `GearTierLeveling`). REDUCIBLE: bind to the live monster catalog (a data
   obligation, like GameDataFixture) — roadmap #4.
3. **BlockersQuietInfinitelyOften** — the 14 higher ladder slots are quiet
   infinitely often (post-unlock). The transience/fairness core. In-model it holds
   (chores clear, model doesn't re-arm); its faithfulness to the refreshing bot is
   the documented perception-abstraction gap. HARD to discharge fully (needs a net-
   progress argument over chores that the model can't currently express).

The extension's NET WIN: it removes the objective-committed obligation (the old
`hperc`/`CombatPersistent`) from the assumption set, replacing it with an in-model
`perceptionRefresh` whose faithfulness is (i) the O5.4 differential (already built
for the SELECT path; extend to the perceive/arm path) and (ii) `WinnableAcrossBand`.
It does NOT by itself close (3).

## Faithfulness obligation (extends O5.4)
The differential must assert: production's `perceive` (player.py:302 `decide` →
`StrategyArbiter.select`, with `_resolve_step_goal` / `objective_step_goal`) yields
`objectiveStepFires = true ∧ objectiveStepIsFight = true` WHENEVER `level < 50` AND
a winnable target exists. Concretely: extend `test_ladder_fires_diff.py` (or a new
`test_perceive_arm_diff.py`) to drive production's objective-tier on a fixture with
`level < 50` + a winnable monster catalog and assert the perceived
`objective_step_fires`/`is_fight` match `perceptionRefresh`. This is the
`combatObjective_live_below_fifty` ↔ production binding.

## Bricks (smallest-first)
1. **`perceptionRefresh` + preservation bridges** — new `Formal/Liveness/
   PerceptionRefresh.lean`: the def + `perceptionRefresh_<field>` lemmas (rfl) +
   `perceptionRefresh_objectiveStepFires_of_lt_fifty`. SMALL.
2. **`cycleStepP` + descent transfer** — `cycleStepP s := cycleStep
   (perceptionRefresh s)`; transfer B-0's `window_step_decreases_measure` /
   `reaches_bankRequiredLevel` to `cycleStepP` via the bridges. MEDIUM.
3. **`objectiveStepFires` armed i.o.** — `∀ k, level (cycleStepP^k s) < 50 →
   objectiveStepFires (cycleStepP^k s) = true`. Overturns the frontier. SMALL-MED.
4. **`hfightFires` for `cycleStepP`** — combine (3) [3rd disjunct arming] +
   `BlockersQuietInfinitelyOften` (kept as hypothesis) + B-0 [2nd disjunct in
   window] → `hfightFires (cycleStepP) ...`. Discharges the objective half; states
   the residual cleanly. MEDIUM.
5. **Capstone for `cycleStepP`** — `ai_reaches_level_fifty` analog over `cycleStepP`
   trajectories, consuming `GlobalInvariants` with `hfightFires` now built from (4)
   modulo only `BlockersQuietInfinitelyOften` + `WinnableAcrossBand`. MEDIUM-HARD.
6. **Perceive-arm differential** — the O5.4 faithfulness extension (above). MEDIUM.

## Decision needed before building
The plan's earlier aspiration was "level-50 modulo only LIV-001". The read shows
that is NOT achievable by the perception-refresh alone — `WinnableAcrossBand`
(#4, reducible via data binding) and `BlockersQuietInfinitelyOften` (hard
transience) remain. Three honest options:
- **(A) Build bricks 1-6** as scoped: converts the objective-committed obligation
  to in-model + differentially-validated, leaving a CLEAN, named residual set
  {LIV-001, WinnableAcrossBand, BlockersQuietInfinitelyOften}. Highest honesty win.
- **(B) Build 1-4 only**: get `objectiveStepFires` armed in-model + `hfightFires`
  restated; defer the capstone re-derivation and the perceive differential.
- **(C) Also tackle WinnableAcrossBand (#4)** via live-catalog binding in the same
  effort, shrinking the residual to {LIV-001, BlockersQuietInfinitelyOften}.

## Status — COMPLETE (Option A, 2026-06-18)
All 6 bricks landed on main (subagent-driven, implementer + adversarial reviewer
each; full Python suite green throughout). The objective-committed obligation
(old `hperc`/`CombatPersistent`) is now PROVEN in-model + differentially validated.
- Brick 1 — `perceptionRefresh` + preservation bridges (be1685e).
- Brick 2 — `cycleStepP` + B-0 descent transfer (0c09d67).
- Brick 3 — `objectiveStepFires` armed along the refreshed trajectory (2ec241a).
- Brick 4 — `hfightFiresP`, CombatPersistent discharged in-model (ed65764).
- Brick 5 — `ai_reaches_level_fiftyP` capstone, re-derived (engine not reusable)
  (a40a7db).
- Brick 6 — perceive-arm differential, binds `combatObjective_live_below_fifty`
  to production; surfaces the WinnableAcrossBand gap honestly (caff721).

`ai_reaches_level_fiftyP (s) (h : GlobalInvariantsP s) : ∃k, (cycleStepPN k s).level
≥ 50`, axioms = {propext, Classical.choice, Quot.sound, xpToNextLevel,
xpToNextLevel_pos} (identical to the original capstone). NET WIN: CombatPersistent
moved from assumption to in-model fact.

HONEST RESIDUAL (level-50 reachability for the refreshed cycle now rests on):
1. LIV-001 (server xp-curve axiom) — irreducible.
2. WinnableAcrossBand — a winnable in-band monster exists below 50. Satisfiable
   hypothesis; differentially CHARACTERIZED by Brick 6 (production arms iff
   winnable); reducible via live-catalog binding (roadmap #4 / option C).
3. BlockersQuietBelowCapInfinitelyOftenP — the 14 higher ladder slots quiet i.o.
   (the transience/fairness core). The hard residual; faithfulness is the
   documented perception-abstraction gap.

NEXT (toward "modulo only LIV-001"): option C — discharge WinnableAcrossBand by
binding to the live monster catalog; and the BlockersQuietInfinitelyOften
transience (the genuinely hard remaining core).
