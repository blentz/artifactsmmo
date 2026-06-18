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

## Status
- 2026-06-18: scoped.
- 2026-06-18: **sub-lemma 1 DONE** (commit 2b3f1f6, gate green) —
  `Formal/Liveness/BlockerSelection.lean`: the 8 `productionLadder_eq_<B>`
  converse selection lemmas (hpCritical, discardCritical, craftRelief,
  depositFull, discardHigh, gearReview, claimPending, sellPressured), each via
  the `findSome?` short-circuit. Axioms = [propext] only.
  NEXT: sub-lemma 2 — the quiet-prefix-persists-one-step lemmas (a blocker's
  `planFor` action doesn't re-arm any HIGHER blocker's flag; extend
  `BlockerMonotone`), then 3 (one-step seed-clear) and 4 (per-seed reach).
