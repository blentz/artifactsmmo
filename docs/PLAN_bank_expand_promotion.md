# PLAN: promote BANK_EXPAND above the objective step

Status: **increments 0-5 DONE**. Next: increment 7 (live confirmation).
Written 2026-09-13.

## Why

`MeansKind.BANK_EXPAND` sits in `DISCRETIONARY_ORDER`, below `.objectiveStep`.
A character essentially always has a step, so the rung has never been selected:
`audit/liveness_completeness.py:142` already declares `ExpandBankGoal` as
`unreachable: MeansKind.BANK_EXPAND is in the discretionary band`.

Measured live 2026-09-13, ~4h after the fleet restarted on `dff7198a`:

* bank 50/50 slots, 12553 banked gold, expansion cost 3500
* `means_fires(BANK_EXPAND)` is **True** for HAL (gold 6657, reserve 100) and
  for Robby — `dff7198a` armed the rung
* **zero** expansion buys and **zero** deposits fleet-wide
* every inventory climbing with no bank sink: HAL 76 -> 109/138, C3P0 37 -> 61,
  R2D2 17 -> 33

So the rung fires and never wins. USER ruling 2026-09-13: *"expanding the bank is
good to do whenever we have the money for it."*

## Prerequisite finding — a divergence `dff7198a` introduced

`dff7198a` changed production's reserve gate to read the ACCOUNT balance and
added a pocket-affordability conjunct. **The Lean ladder model was not updated
and now disagrees with production.**

`ProductionLadder.bankExpandFires` (formal/Formal/Liveness/ProductionLadder.lean:412):

```lean
s.bankAccessible && s.bankItemsKnown && decide (s.bankCapacity > 0)
  && decide (BANK_EXPAND_FILL_DEN * s.bankItemsCount ≥ BANK_EXPAND_FILL_NUM * s.bankCapacity)
  && decide (s.gold ≥ s.nextExpansionCost + s.goldReserve)
```

Production (`ai/bank_expansion_timing.expansion_fires`) is now
`pocket ≥ cost ∧ (pocket + banked) − cost ≥ reserve`.

On Robby's live numbers (pocket 3797, banked 12553, cost 3500, reserve 5100,
50/50): production **True**, Lean model **False**. Verified by direct
evaluation, not by reading.

**The differential cannot see this.** `formal/diff/test_ladder_fires_diff.py:366`
constructs every generated `WorldState` with `bank_gold=None`, so
`account_gold(state) == state.gold` in every example the harness ever draws and
the two readings coincide by construction. Same defect class as
`feedback_scenario_declares_its_world` — the world is pinned so the measurement
cannot fail.

This must be closed BEFORE the promotion. Promoting a rung whose Lean firing
predicate does not match production means every liveness theorem reasoning about
`.bankExpand` above the step is reasoning about the wrong rung.

## Blast radius

* **Lean**: 18 modules reference `bankExpand`. `MeansKind.allInLadderOrder`
  (the band order itself), `DeferFaithful.lean:41` (an `rfl` pin on the exact
  discretionary list), `CycleStepCharacterization`, `CumulativeProgress`,
  `GearedDescent`, `LifecycleBound7`, `UnconditionalDescent`, `PlanExists`,
  `NoDeadlockV2`.
* **Measures**: `FMeasure`, `DMeasure`, `EMeasure` — three separate tuples, lex
  embeddings and per-slot helpers. `FMeasure` is the expensive one.
* **Python**: `means.py` band lists; `audit/liveness_completeness.py:142`
  declaration must flip from `unreachable:` to live.
* **Scenarios**: `scenario.py:348` declares a "bank with NO ROOM" set (exactly
  `bank_capacity` items) used by `test_bag_pressure_cells`; `scenario.py:987`
  (`l30_rune_fill`) carries `bank_gold=50000` + 25000 pocket. Both are prime
  candidates to start electing `ExpandBank` and MASK the routing their goldens
  exist to pin — the trap `project_accept_task_promotion` records.

## The descent obligation (why this is cheap, unlike ACCEPT_TASK)

`project_accept_task_promotion`: every rung promoted above `.objectiveStep`
needs a descent slot in all three measures. `.acceptTask` was expensive because
its apply RAISES `phasePresent`, so it needed a slot ABOVE that.

`.buyBankExpansion`'s apply changes `gold` (down by `nextExpansionCost`) and
`bankCapacity` (up by `bankExpansionSlots = 20`). **Neither is in any measure
tuple**, so it touches no higher slot and can take a fire-and-lose flag at the
BOTTOM of the cascade — exactly like `geCancelFlag`, `supplyDemandSlot` and
`currencyTurnInFlag` already do.

Strictness argument: see **Consequence A** below. The first draft of this plan
claimed the fire-and-lose flag shape (`geCancelFlag`) transfers and that a buy
makes `bankExpandFires` false in one step. At the 75% trigger the USER chose
that is FALSE, so the flag shape is NOT used — a counted slot is. The paragraph
is kept rather than deleted because the wrong version is the instructive one:
the descent shape depends on the trigger ratio, which is easy to miss when the
constant looks proof-inert.

## Increments

Each increment ends green on `bash formal/gate.sh` and is committed separately.

- [x] **0. Close the model divergence.** DONE `c579efeb`. Add banked gold to the Lean `State`;
      make `bankExpandFires` mirror `expansion_fires` (pocket affordability +
      account-scoped reserve). Extend `test_ladder_fires_diff.py` to DRAW
      `bank_gold` instead of pinning it to `None`, and add a non-vacuity witness
      at Robby's live shape. Expect the harness to go RED first — that is the
      point.
      Outcome: `State.bankGold` already existed and `bankExpandFires` simply
      never read it, so no new field was needed. The harness went RED in
      seconds once `bank_gold` was drawn. The pocket conjunct turned out to be
      KERNEL-load-bearing, not just test-load-bearing — see the commit.
- [x] ~~**1. Establish `bankItemsCount ≤ bankCapacity`.**~~ DELETED — the
      counted slot in Consequence A does not need it.
- [x] **2. Move the rung + retrigger.** DONE. `MeansKind.allInLadderOrder` +
      `means.py` band lists + `DeferFaithful` pin + `TRIGGER_FILL_NUM` 95->75 +
      `_SATISFIED_FILL` (Consequence B), with no measure work yet. Ladder proofs go
      RED; that names the exact descent obligation.
- [x] **3. `FMeasure` slot** DONE. — `bankExpandFlag` at the bottom of the cascade,
      below `currencyTurnInFlag`, + descent lemma.
- [x] **4. `DMeasure` slot.** DONE.
- [x] **5. `EMeasure` slot.** DONE.
- [x] **6. Scenario fallout.** NONE — see note below. Re-baseline `test_bag_pressure_cells` and
      `l30_rune_fill` DELIBERATELY — each change must be argued, never
      "corrected" to ExpandBank to make a golden pass.
- [~] **7. Flip `liveness_completeness.py:142`** done (`unreachable:` -> `conditional:`); a live buy not yet observed. off `unreachable:` and confirm
      a live `plan <char>` elects `ExpandBank`.

## Decisions (USER, 2026-09-13)

1. **Position**: `.bankExpand` goes LAST in `COLLECT_REWARD_ORDER`, directly
   after `.acceptTask` and immediately above `.objectiveStep`. Same argument
   `acceptTask`/`supplyBank`/`currencyTurnIn` make for their own slots.
2. **Fill trigger**: **75%**, not 95% and not removed. `TRIGGER_FILL_NUM`
   95 -> 75 in `ai/bank_expansion_timing.py` and `BANK_EXPAND_FILL_NUM` in Lean.
   The theorems are parametric in `triggerNum`/`triggerDen`, so the constant is
   proof-inert — which is exactly why it needs its own behavioural test rather
   than a green build (`feedback_gate_green_does_not_pin_a_constant`).

### Consequence A — the descent measure gets simpler, and increment 1 dies

A 75% gate is NOT self-extinguishing in one buy. At capacity 70 with 70 items:
70/90 = 77.8% still fires, and it takes a second buy to reach 70/110 = 63.6%.
So "the flag goes false after one step" is FALSE at 75% and the fire-and-lose
shape `geCancelFlag` uses does not transfer.

Use a counted slot instead:

```
bankExpandSlot := (FILL_DEN * bankItemsCount + 1) - FILL_NUM * bankCapacity   -- saturating Nat
```

Firing requires `FILL_DEN * items ≥ FILL_NUM * capacity`, so the slot is `≥ 1`
whenever the rung fires. A buy leaves `items` untouched and raises `capacity` by
`bankExpansionSlots = 20`, so the slot drops by `20 * FILL_NUM > 0` — a strict
decrease on every firing step, saturating at 0.

This is better than the flag on three counts: it is **trigger-agnostic** (works
for 75, 95, anything), it **needs no `bankItemsCount ≤ bankCapacity` invariant**
(items is constant across the step, so the inequality never enters), and it has
no vacuity risk. **Increment 1 is deleted.**

### Consequence B — `_SATISFIED_FILL` is coupled to the trigger

`goals/expand_bank.py:18` sets `_SATISFIED_FILL = 0.90` and `value()` returns
`0.0` early when `is_satisfied(state)`. With the trigger at 75% and satisfaction
at 90%, every fill in [75%, 90%) both FIRES and is ALREADY SATISFIED — the goal
would score 0 across the whole new band and the promotion would buy nothing.
`_SATISFIED_FILL` must move below the trigger in the same commit, and a test
must pin the ordering rather than the two numbers independently.

## Rejected

* Raising `WITNESS_BASELINE` as part of this work — unrelated, and it is now
  independently clearable (0 `WaitAction` firings since the restart).


## Outcome notes (2026-09-13)

**Increments 2-5 could not be separated.** Moving the rung turns the ladder
proofs red by construction — that was the plan's intent — but a red kernel must
not be committed, so the band move and all three measure slots land together.

**Scenario fallout was ZERO, and that is not a silent pass.** Every full-bank
scenario on hand elects a GUARD before the collect band is reached
(`l20_relief_full_bank` -> `CraftRelief`; live HAL -> `DiscardOverstock`; live
C3P0 -> `RestoreHP`), and guards outrank the whole collect band. So no scenario
exercises the promotion at selection level, and the goldens were right not to
move. The gap is covered by `tests/test_ai/test_expand_bank_activation.py`,
which drives the REAL arbiter from a calm no-guard state; it fails when the rung
is demoted back to the discretionary band.

**Still unobserved live.** No character has yet been caught in a cycle where no
guard fires AND the bank is over the trigger, so `ExpandBankGoal` has not been
seen winning on the fleet. That is increment 7 and wants a `plan <char>` at the
right moment, or a trace once the fleet restarts on this code.
