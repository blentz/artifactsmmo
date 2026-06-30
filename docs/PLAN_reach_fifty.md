# PLAN — Proving the AI reaches level 50

_Status snapshot 2026-06-29 (worktree `liveness-phase23c`). Zero-vacuousness is a hard constraint ([[feedback_zero_vacuousness]])._

## TL;DR

The **pure-Lean reach-50 proof is essentially complete and non-vacuous**, blocked
only by a single obligation that is *provably not closable in the pure model*: the
perception layer must keep a combat objective committed while underleveled. What
remains is **not more pure Lean** — it is the O5.4 faithfulness binding (model ↔
production code differential) plus the LIV-001 server-curve axiom.

## What is PROVEN (non-vacuous, axioms ⊆ {propext, Quot.sound, Classical.choice, LIV-001})

| Theorem | File:line | Statement |
|---|---|---|
| `settledWitness_reaches_fifty` | SettledWitness.lean:43 | `∃k, (cycleStepN k settledWitness).level ≥ 50` — **0 hypotheses**, concrete witness |
| `ai_reaches_level_fifty_of_settled` | BlockerSettled.lean:143 | config-positivity + `Settled s` ⇒ reach 50 |
| `reach_fifty_of_eventually_settled` | SettledReach.lean:41 | config-positivity + `∃K, Settled (cycleStepN K s)` ⇒ reach 50 |
| `cycleStepF_reaches_fifty_of_fights` | LevelingDescent.lean:114 | per-cycle measure descent (NOT i.o.-fairness) ⇒ reach 50 |
| `*_quiet_forever` (≈13 blockers) | BlockerMonotone.lean | each non-task blocker stays quiet forever once its clearing condition holds |

`settledWitness_reaches_fifty` is the headline: **the AI provably reaches level 50**
for a concrete, satisfiable spawn-like state, with no hypotheses beyond LIV-001.
This discharges the vacuity worry — `Settled` / `CombatObjectiveFairlyScheduled` is
inhabited, so the conditional capstones are non-vacuous.

## The honest wall (why pure Lean cannot go further)

`Settled_unreachable_without_perception` (SettledReach.lean:85): in the pure
`cycleStep` model **no action sets `objectiveStepFires := true`** (verified over all
of `applyActionKind`; it is only ever cleared). Therefore:

- `objectiveStepFires` / `objectiveStepIsFight` are **exogenous perception flags** —
  supplied by the production StrategyArbiter (the `ReachCharLevel` combat meta-goal),
  not producible by the transition function.
- From a spawn with `objectiveStepFires = false`, `Settled` is **unreachable in-model**.
- Hence the general "any spawn reaches 50" cannot be a pure-model theorem. The
  correct, satisfiable, honestly-surfaced residual is the runtime hypothesis
  `CombatPersistent` / `hfair : CombatObjectiveFairlyScheduled` (FightFairness.lean).

This is **not vacuity** — the hypothesis is witnessed satisfiable. It is an honest
model boundary: the bot's *goal commitment* is perception-driven.

## The genuine remaining obligation — O5.4 faithfulness binding

To raise confidence that the **real bot** reaches 50, bind the opaque Lean Bools to
the production computation via the differential/mutation gate:

1. **`objectiveStepIsFight`** ≟ "the objective tier's emitted step leads with `Fight`"
   in `tiers/` (StrategyArbiter → `ReachCharLevel` meta-goal). Differential test:
   Lean Bool vs production predicate over fixtures.
2. **`objectiveStepFires`** ≟ "the objective tier yields a plannable step".
3. **`CombatPersistent` grounding** — argue (at the planner level, possibly in Python +
   diff-tested, not pure Lean) that while `state.level < target`, `ReachCharLevel`
   stays committed and its plan head is `Fight` ⇒ the opaque Bools stay true.

Closing (1)+(2) via the gate turns `CombatPersistent` from "assumed" into
"model-faithful to the code that actually computes it" — the real confidence gain.

## Secondary (pure-Lean, optional) tightening

- `hspawn : ∀k, 1 ≤ level` — discharge from `cycleStepFN_level_ge` + spawn level 1
  (runtime-trivial; low value).
- Task-lifecycle quieting (`accept_cancel_loop_bound_proven`, Item 1g-A4): per-step
  bounds exist (TaskPoolTrajectory.lean); the pigeonhole closes the task-loop half of
  blockers-quiet. BUT this only matters for the in-model reach-Settled story, which the
  perception wall already shows cannot complete without (1)/(2). Low marginal value
  until O5.4 is decided.

## Decision needed

The pure-Lean capstone is done up to the perception wall. The real next step is the
O5.4 differential binding (model↔code), which is `formal-development` work (Python +
Lean differential), not theorem-proving. Confirm direction before proceeding.
