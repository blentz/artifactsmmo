# PLAN: SELECT-reach machinery (level-50 #2-PhaseB ∪ #3)

The structural reduction is done (`FightReadyReach.lean`): spawn→50 holds given
the 7 per-seed reaches, `TaskParked` reach+persistence, and `hperc`. Scoping
(2026-06-18) shows ALL of those collapse into one body of work — the SELECT-reach
machinery — EXCEPT `hperc`, which is provably irreducible in-model.

## What SELECT-reach IS

`productionLadder s = allInLadderOrder.findSome? (fun k => if fires k s then some k
else none)` — first-firing-wins over a fixed 23-slot priority list. "Blocker B is
selected" ⟺ `fires B s = true` AND every higher slot is quiet. The clear half is
already proven (`BlockerQuieting.<B>_quiet_after_firing` assumes B selected). What
is missing is the **converse + persistence**: prove `productionLadder` actually
SELECTS B from a state where B's flag is set (all higher slots quiet), and that
the quiet prefix PERSISTS step-to-step. Every outstanding piece reduces to this:
the 6 opaque-flag reaches + `hp=maxHp` need B selected so its clear-action runs;
`TaskParked` reach + #3's `applyPlan→cycleStepN` bridge are the SAME statement
specialized to `.pursueTask` (per-step form already exists,
`PursueTaskSelection.hpursue_under_conditions` — it just needs iterating).

## The split

### In-model (Lean, BUILDABLE — discharges `hwarm`)
Only TWO selection lemmas exist today — `productionLadder_eq_pursueTask`
(PursueTaskSelection) and `productionLadder_eq_objectiveStep_of_unblocked`
(FightFairness). The 8 for the opaque-flag/hp blockers are the gap.

### Irreducible external (`hperc` / O5.4 differential — NOT a Lean proof)
`SettledReach.objectiveStepFires_false_cycleStepN` PROVES the pure transition
never SETS `objectiveStepFires` true (only clears). So `hperc` (the combat
objective stays/­fairly-fires) CANNOT be discharged in-model. It stays an external
hypothesis whose FAITHFULNESS is an O5.4 SELECT-side DIFFERENTIAL: bind the Lean
`productionLadder` (and the opaque flag VALUES) to production's
`StrategyArbiter.select` + `perceive`. Today `formal/diff/test_cycle_step_diff.py`
binds only `applyActionKind`↔`Action.apply` (TRACKED_FIELDS = level/xp/task/gold);
it does NOT bind `select`/perception. NOTE: `hperc` as currently stated (`∀ k …`)
is stronger than needed — reaching FightReady ONCE wants the combat objective fair
(infinitely often, `CombatObjectiveFairlyScheduled`) or simply true at the reached
K; weaken it when wiring Phase B so the assumption is minimal.

## Ordered sub-lemmas (smallest-first)

1. **`productionLadder_eq_<B>`** for B ∈ {hpCritical, discardCritical, depositFull,
   discardHigh, claimPending, sellPressured, gearReview, craftRelief} — *fires B
   ∧ all higher slots quiet ⇒ productionLadder = some B.* 8 mechanical copies of
   the proven `productionLadder_eq_objectiveStep_of_unblocked` (`findSome?_append`
   pattern). SMALL — the tractable entry point.
2. **Quiet-prefix-persists-one-step**: each blocker's `planFor` action does not
   re-arm any HIGHER blocker's flag (extend `BlockerMonotone`). MEDIUM.
3. **One-step seed-clear**: glue (1) + `BlockerQuieting.<B>_quiet_after_firing`
   → `fires B s ⇒ fires B (cycleStep s) = false`. SMALL.
4. **Per-seed REACH** `∃K, F (cycleStepN K s) = false` from (2)+(3): flag set ⇒ B
   selected ⇒ cleared next step; else already false. MEDIUM.
5. **`pursueSelectionConditions`-persistence** under `.taskTrade` (reuse the
   LifecycleBound2/3/4 `applyPlan` invariants). HARD.
6. **`cycleStepN_eq_applyPlan_taskTrade`** bridge: under invariant
   `pursueSelectionConditions`, `cycleStepN K s = applyPlan (replicate K .taskTrade)
   s` — induction over `hpursue_under_conditions` + (5). Closes #3's bridge and
   `TaskParked` reach. HARD.
7. **Fold** the (4) reaches + the (6) TaskParked reach into
   `fightReadyCore_reachable_of_seeds` (already wired to consume them).

## Hardest piece
The PERSISTENCE/invariance lemmas (2, 4, 5) — proving the quiet prefix STAYS quiet
across the whole trajectory (a lower action never re-arms a higher flag). This is
the `BlockersQuietInfinitelyOoften` transience core that `FightFairness.lean:106-
126` flags as leaning on the abstracted perception refresh.

## `hperc` verdict
**Irreducible in-model.** Dischargeable only by CHANGING the model (add a
`perceptionRefresh : State → State` re-arming `objectiveStepFires` when the
planner's head action is a Fight) — which then needs the O5.4 SELECT-side
differential to prove faithful. So: build the in-model SELECT-reach (1-7) to
discharge `hwarm`, leaving level-50 conditional ONLY on `hperc`; then `hperc` is
either accepted as a documented server/perception assumption (like LIV-001) or
discharged by the perception-refresh model + O5.4 differential.

## Recommended start
Sub-lemma (1): the 8 `productionLadder_eq_<B>` selection lemmas — mechanical
copies of the existing template, the entry that unblocks the per-seed reaches.
New file `Formal/Liveness/BlockerSelection.lean`.

## TRANSIENCE-CORE FINDING (2026-06-18) — reshapes the whole approach

Scoping the per-seed reaches surfaced a hard truth: **the universal per-seed
reach is FALSE.**

- `reachUnlockLevelFires = decide(bankRequiredLevel>0) ∧ decide(level <
  bankRequiredLevel) ∧ decide(bankRequiredLevel - level ≤ 5)` has NO quieting
  conjunct — it fires EVERY cycle while `level < bankRequiredLevel`, sits at
  ladder idx 3 ABOVE all chore blockers, and its `.fight` action clears NONE of
  the six chore flags. So a chore flag set at a low-level spawn CANNOT clear
  until `level` reaches `bankRequiredLevel` — the chore blocker is never selected
  (a fight-means preempts it continuously). NO GAPS.
- Counterexample to `∃k, hasOverstockItems (cycleStepN k s) = false`: spawn with
  overstock set + `bankRequiredLevel = level+5`. The cycle fights forever (until
  level climbs); `deleteItem` is never dispatched; overstock stays true the whole
  window. The existential fails at every k in it.

**Consequence:** `fightReadyCore_reachable_of_seeds`'s per-seed hypotheses are NOT
universally dischargeable. My `FightReadyCore` decoupling (omitting bank/leveled
to "skip the level-44 wait") DOESN'T actually buy an earlier reach — the chores
can't clear before `bankRequiredLevel` ANYWAY. `fightReadyCore_reachable_of_seeds`
stays a VALID honest conditional theorem; it just has no easier discharge than
`Settled`-reach.

**The chore-clear is NOT a clean induction.** It bottoms out at the SAME honest
hypothesis the repo already documents — `BlockersQuietInfinitelyOften` /
"nothing re-arms the flags" leans on the model abstracting away the perception
refresh (`FightFairness.lean:106-126`). There is no well-founded ranking over
chore-flag count, and no proof that a set chore flag FORCES its blocker selected
when `objectiveStep` also fires.

### Revised honest path
1. **B-0 (PROVABLE, bounded — the real next theorem):** `∃k, level ≥
   bankRequiredLevel ∧ bankAccessible` via the existing lex measure — while
   `reachUnlockLevel`/`bankUnlock` fire, the cycle fights and
   `fight_decreases_measure` strictly drops xp/level deficit; gap ≤ 5 bounds it.
   Then `reachUnlockLevel_quiet_forever` / `bankUnlock_quiet_forever` retire idx
   2-3 permanently. Reuses `Measure.lean` + `FightProgress`.
2. **B-1 (chore-clear) = an honest FAIRNESS hypothesis**, not a theorem — the
   `BlockersQuietInfinitelyOoften` obligation. Like `hperc` and LIV-001, this is
   an irreducible documented assumption (the perception-refresh abstraction).
3. **Target `Settled`-reach** (`ai_reaches_level_fifty_of_settled`, the repo's
   honest capstone) rather than the universal per-seed reaches: B-0 + the
   chore-fairness/perception hypotheses → Settled → 50.

### Net level-50 end-state (honest)
Provably reaches 50 given: (i) **B-0** [provable, build next], (ii) a
**chore-scheduling fairness** assumption, (iii) **`hperc`** perception. (ii)+(iii)
are the "model abstracts perception" hypotheses — they could be documented like
LIV-001, BUT see the chosen direction below.

## CHOSEN POST-B-0 DIRECTION (decision 2026-06-18): EXTEND MODEL + O5.4 DIFFERENTIAL

Rather than accept (ii)+(iii) as LIV-001-class assumptions, DISCHARGE them
in-model:

1. **Model extension — perception refresh.** Add a `perceptionRefresh : State →
   State` step (folded into `cycleStep`, or a pre-pass) that, when the committed
   objective's planner head action is a Fight, SETS `objectiveStepFires = true` /
   `objectiveStepIsFight = true` (and recomputes the chore flags from the perceived
   state). This makes the perception fields PRODUCIBLE in-model — overturning
   `Settled_unreachable_without_perception`'s premise (which holds only because the
   current pure transition never sets them) — so `hperc` and the
   chore-scheduling fairness become provable, not assumed. CAUTION: the extension
   must not let the model "cheat" (e.g. unconditionally set the fight flag); it
   must mirror EXACTLY when production's perceive would arm the guard.
2. **O5.4 SELECT-side differential — faithfulness.** The extension is only honest
   if the Lean `perceptionRefresh` + `productionLadder` MIRROR production's
   `perceive` + `StrategyArbiter.select`. Build the differential that feeds
   reconstructed real fixtures (equipped gear, monster locations, learning
   history, perception state) into production's `perceive`/`select` and asserts
   the Lean model computes the SAME flag values + selects the SAME `MeansKind`.
   `formal/diff/test_cycle_step_diff.py` today binds ONLY `applyActionKind`↔
   `Action.apply` (TRACKED_FIELDS = level/xp/task/gold) and bypasses select +
   perception — this differential extends it to the SELECT + perceive path.

Net after this: level-50 is fully kernel-checked + differentially-guaranteed
modulo only LIV-001 (the server xp-curve axiom) — no perception/fairness
assumption left.

## Status
- 2026-06-18: scoped.
- 2026-06-18: **sub-lemma 1 DONE** (commit 2b3f1f6, gate green) —
  `Formal/Liveness/BlockerSelection.lean`: the 8 `productionLadder_eq_<B>`
  converse selection lemmas (hpCritical, discardCritical, craftRelief,
  depositFull, discardHigh, gearReview, claimPending, sellPressured), each via
  the `findSome?` short-circuit. Axioms = [propext] only.
- 2026-06-18: **B-0 inductive step DONE** (`Formal/Liveness/BootstrapReach.lean`,
  axioms = {propext, Quot.sound, xpToNextLevel}). The bootstrap window's
  per-cycle measure descent is fully proven:
  * `reachUnlockLevel_fires_in_window` + `reachUnlockLevel_selected_in_window` +
    `cycleStep_fights_of_reachUnlockLevel` — in the window, once the higher slots
    are quiet, `cycleStep` runs `.fight`.
  * `fightKind_decreases_measure` — KEY FINDING: `applyActionKind .fight` differs
    from `FightProgress.fightApply` (the ladder's `.fight` MODELS the level-up
    rollover; `fightApply` does not and decrements hp). So the ladder's fight
    descends the lex measure with ONLY `level < 50` — NO perception invariant
    `xp < xpToNextLevel` needed (the rollover handles the `xp ≥ threshold` case).
  * `window_step_decreases_measure` — one `cycleStep` in the window strictly
    decreases the measure. The `bankRequiredLevel ≤ 50` hypothesis is the honest
    server fact bridging `level < bankRequiredLevel` to `level < 50`.
  Also cleaned the `unusedSimpArgs` (`List.findSome?_cons`) warnings in
  BlockerSelection.lean.
- 2026-06-18: **B-0 COMPLETE.** `reaches_bankRequiredLevel` proven (axioms =
  {propext, Quot.sound, xpToNextLevel}): from the combat-rest interrupts
  initially quiet + window bounds (bankRequiredLevel>0, ≤50, gap≤5),
  `∃k, (cycleStepN k s).level ≥ bankRequiredLevel`, by well-founded recursion on
  the lex `Measure` (`measureLt_wellFounded`). Supporting bricks:
  * `cycleStep_fights_in_window` — robust to bankUnlock RE-ARMING: a level-up can
    re-arm bankUnlock (it reads `level`), but bankUnlock also dispatches `.fight`,
    so the cycle fights whether bankUnlock or reachUnlockLevel is selected. Only
    hpCritical/restForCombat must stay quiet. Added `productionLadder_eq_bankUnlock`
    to BlockerSelection.lean.
  * `fightKind_preserves_hpCriticalFires` / `_restForCombatFires` (both `rfl`) +
    `fightKind_level_ge` — the persistence + monotone-level facts; `.fight`
    preserves hp/maxHp/restForCombatReady, and `bankRequiredLevel_cycleStep`
    (existing) gives bankRequiredLevel invariance.
  NO perception/fairness hypothesis needed in the bootstrap window — the
  transience-core silver lining realized. NEXT: post-B-0 — the MODEL EXTENSION
  (perception-refresh) + O5.4 SELECT-side DIFFERENTIAL to discharge the chore-clear
  + `hperc` out of the window (the §"CHOSEN POST-B-0 DIRECTION" plan above).
