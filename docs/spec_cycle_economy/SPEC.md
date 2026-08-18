# SPEC: the cycle economy — one currency, one comparison

Status: proposed 2026-08-18.

**Artifact under test:** the decision logic that chooses what the bot does next and
prices that choice — the objective's projection walk and its value `J`, the
comparison among available means, and the set of routes by which an item may be
obtained.

**NOT under test**, and therefore never a clause: the A* planner's search; the
loadout picker; the combat model; the coordination protocol; the executor; the
server's rules. They supply inputs. See OBSERVATION.md.

Measured figures supporting these clauses are in **Evidence** at the end, keyed by
clause. No clause body asserts a concrete output — the clauses are rules.

---

## Clauses

### S-001 · The unit of every quantity is the executed planner action

Every cost, benefit, price and budget in this specification is a count of executed
planner actions ("cycles"). A quantity expressed in any other unit is converted
before it participates in a comparison.

### S-002 · Cost is marginal against committed work

The cost of an option is the number of cycles it adds to the cycles already
committed for the current horizon. Cycles that would be spent regardless of whether
the option is taken do not count toward its cost.

### S-003 · The objective's value is the cycle total of one projection walk

`J` for a candidate course of action is the total cycles of a single projection walk
from the current state to the horizon under that course. It is not a sum of a
separately-computed cost term and a separately-computed benefit term.

### S-004 · The walk may spend cycles to acquire, and does so when it repays

At each level the projection walk crosses, it may pay a route's cost to obtain and
equip an item; subsequent levels are then projected with that item held. It takes
such an acquisition when the cycles paid are fewer than the cycles thereby saved
over the remainder of the walk.

### S-005 · Inability to complete is expressed as cost, not as a rank band

Where a course of action cannot be completed from the current state, it is priced
at the cycles required to make it completable. No distinguished value stands in for
"cannot", and no ordering key exists whose purpose is to rank options the objective
declined to price.

*This clause governs courses the state makes unavailable. It does not decide what
is reported for content the game data contains no route to at all.*

### S-006 · A means competes on the same quantity as the objective step

An available means and the objective step are compared on marginal cycles (S-002)
against cycles saved or progress unlocked over the horizon. Neither wins by virtue
of the band or position it occupies.

### S-007 · Survival constraints are not investments and are not compared

A guard — a condition on the state that must hold for the bot to continue
operating — takes precedence over every priced comparison and is not itself priced.

### S-008 · A task's cost is the work it demands that is not already committed

The marginal cost (S-002) of accepting a task is the cycles required by its demanded
work that the bot has not already committed to for other reasons. Its value is the
task's reward together with the value of that demanded work.

### S-009 · A task with no overlap is taken only for its reward

Where a task's demanded work overlaps no committed work, the task is taken only when
its reward is itself required by a course of action the objective has selected.

### S-010 · Earning a task currency is a route, priced at the task's marginal cost

A currency obtainable by completing tasks is a source of that currency, on the same
footing as the other sources. Its per-unit price is derived from the marginal cost
(S-008) of the task that yields it.

### S-011 · One horizon governs every comparison

Every comparison in this specification is evaluated against a single horizon. No
part of the decision logic introduces a second horizon of its own.

### S-012 · The horizon's behaviour at its extremes is stated, not inherited

Whatever quantity bounds the horizon, the specification states what the comparison
does when that bound is near and when it is distant.

*This clause requires the statement; it does not fix which quantity bounds the
horizon, nor what the behaviour at either extreme should be.*

### S-013 · A totality witness is exempt from comparison

A means whose purpose is to be selectable in every state, so that some means is
always selectable, is not priced and does not participate in the comparison. It is
selected only when no other means is.

---

## Evidence

Measured 2026-08-18 unless noted; `learning.db` and live probes with the fleet
stopped. These are observations about the CURRENT implementation, motivating the
clauses above. They are not themselves requirements.

| clause | observation |
|---|---|
| S-001 | The projection was denominated in seconds until 2026-08-07 and ran ~80x high; four separate defects in this project trace to a unit confusion. |
| S-003, S-005 | `J` finite for no candidate in 10,716 cycles; the ranking was settled every cycle by the fallback key, where the zero-cost trunk won 8,769 of 8,769 ties. |
| S-004 | With the objective evaluated against the next ten-level milestone, benefit spreads 1,086–1,182 cycles across 11–12 candidates at four levels of headroom. |
| S-005 | Skill-gated crafts priced at `10^6` on every character; after pricing the grind they price at 556–623, and the affected items became rankable. |
| S-002, S-008 | Five iron pieces cost 2,933 cycles priced apart and 936 as one plan — 68% of the total was one shared prerequisite charged five times. |
| S-006 | An objective step was present in 14,064 of 14,064 traced cycles; the band below it took 133 of 63,310 cycles (0.21%), and 19 goal/action classes are unreachable in consequence. |
| S-008, S-009 | `means_worth._task_need_overlap` already computes a task's overlap with live objective needs, then discards it through a boolean threshold. |
| S-010 | `is_task_earnable('tasks_coin')` returns true while `route_options('tasks_coin')` returns empty and the price walk charges `10^6`; the item that funding targets prices at 1,000,010. |
| S-011 | Four unrelated horizon constants exist in four modules; the objective reads none of them. |
| S-012 | At one level of headroom the benefit spread is exactly 0; at fifty levels nothing arrives at all. |
| S-013 | `Formal.Liveness.NoDeadlockV2.productionLadder_total` is proved via the unconditional last-resort means. |
| Σ dim 8 | A decision costs 6–34 s live against a planning window floored at 15 s. A candidate evaluation costs ~235 ms, the same order as a whole level of the walk; ~27% can be excluded by a cheap static predicate. |

## Residuals

* Whether the per-decision compute can be brought inside the planning window is
  unproven. If it cannot, S-003/S-004's walk-shaped objective is not affordable and
  the design must change rather than the budget.
* The task-reward table holds no rows, so S-008's reward term has no observations
  behind it yet.
* S-007 exempts guards by assertion. Nobody has measured whether a guard ever fires
  where a priced option would have paid more.
* The deep-fan-out recipe that once caused a search blow-up at this seam is
  currently unpriced, so no cost figure here covers it.
* This document does not decide what is reported for content with no route in the
  game data at all (see S-005's note), nor which quantity bounds the horizon (S-012).
