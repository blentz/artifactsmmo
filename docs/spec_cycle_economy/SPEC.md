# SPEC: the cycle economy — one currency, one comparison

Status: proposed 2026-08-18. Supersedes the separate framings of option C
(`docs/PLAN_bounded_horizon_objective.md`), Group A
(`docs/PLAN_priority_ladder_unification.md`) and the C4 funding pipeline. Every
number cited is measured and reproducible; sources are named at each clause.

---

## The thesis

The bot spends exactly one thing: **cycles** — cooldown-bounded planner actions.
Everything else it can want — levels, skills, gear, materials, coins, HP — is
bought with cycles. Every decision it makes is therefore the same decision:

> what does the next cycle buy, and is that more than what another cycle buys?

The bot currently asks that question in three different vocabularies, and in each
one the answer is decided by a **priority order** whose top key never varies, so
the comparison never happens:

| where | the order | measured |
|---|---|---|
| gear vs XP | `J`'s band, then progress, then cost | finite `J` **0 / 10,716** cycles; the zero-cost trunk wins **8,769 / 8,769** ties |
| what to do this cycle | guards → collect → **step** → discretionary | a step is present **14,064 / 14,064**; the discretionary band takes **133 / 63,310 = 0.21%** |
| how to obtain a thing | six routes, priced; anything else is `10^6` | `tasks_coin` prices at **1,000,000** while `is_task_earnable` says **True** |

Those are not three problems. They are one currency missing in three places.

**This spec replaces all three orders with one comparison in cycles.** It is the
smallest change that stops the pattern rather than moving it — the previous five
repairs (`SUPPLY_BANK`'s promotion, three urgency hoists, S-006's fallback key)
each moved one rung and left the generator intact.

---

## Scope

IN: the objective's benefit term; the means ladder's ordering; the acquisition
model's route set. OUT: the planner's A* search, the loadout picker, the combat
model, the coordination protocol. Those supply inputs to the comparison and are
not changed by it.

---

## Observation alphabet

Everything a clause may quantify over. Anything outside this list is background
and a clause that needs it is under-specified.

* **cycle** — one executed planner action. The unit of every quantity below.
* **state** — the character's `WorldState`: level, xp, skills, hp, inventory,
  equipment, bank, task.
* **rung** — one character level crossed by the projection walk.
* **rate** — XP per cycle achievable from a state, over the best available
  monster (`cheapest_path_to_level`'s inner argmax).
* **route** — a way to obtain one unit of an item, with a per-application action
  count, a venue, and pay-once unlock keys (`acquisition_cost_core.RouteOption`).
* **means** — a discretionary or collect-band action the bot may take instead of
  its objective step.
* **committed work** — the cycles the bot has already decided to spend this
  planning horizon.
* **task** — an accepted server task: a type, a target, a progress counter, and a
  reward in gold and `tasks_coin`.

---

## Clauses

### S-001 · The currency is cycles, and nothing else enters

Every cost, benefit and price in this spec is a count of executed planner actions.
A quantity that is not an action count — a gold price, a level gap, a wall-clock
cooldown, a distance — must be converted before it enters, or it reintroduces the
seconds/actions confusion that has produced four separate defects in this project.

*Inherits `acquisition_cost_core`'s existing contract verbatim. `haste` and travel
distance stay excluded for the same reason.*

### S-002 · Cost is MARGINAL, not additive

The cost of an option is the cycles it adds to what is already committed — not
the cycles it consumes in total. Work that would happen anyway is free.

This is the clause the whole spec turns on. It is what makes a task cheap when it
overlaps a committed grind, and it is why an urgency threshold was the wrong
instrument: urgency measures pressure, and the question is overlap.

### S-003 · The objective is the cycles the walk takes

`J` is the total cycles of one projection walk from the current state to the
horizon. There is no separate benefit term and no separate cost term to add: the
walk spends cycles on whatever it does, including acquiring things, and the total
is the answer.

**Replaces** S-003/S-004/S-005 of `docs/spec_unified_objective/SPEC.md`
("cycles to character level 50" plus a bolted-on `acquire_cost`).

### S-004 · The walk may spend cycles on acquisition

At each rung the walk may pay a route's cost to obtain and equip an item, after
which subsequent rungs are projected with that item held. An acquisition is taken
when the cycles it costs are less than the cycles it saves over the remainder of
the walk.

*This is option C. `cheapest_path_to_level`'s rung loop already re-equips from
inventory ∪ equipped at each rung, charges equip actions when the worn set
changes, and projects `max_hp` growth and rung wisdom. The only missing edge is
that it cannot ACQUIRE, only re-equip.*

### S-005 · Unreachability is a cost, not a band

An option the walk cannot complete is priced at the cycles required to make it
completable, or is absent. No sentinel value stands in for "cannot", and no
ordering key exists to rank options the objective has declined to price.

**Deletes** S-006 and S-014 of the unified-objective spec, the FINITE /
UNREACHABLE / FAILED banding, and with them `branch_objective`'s candidate
construction. *Measured justification: S-014 makes unreachability exactly
`level < 50`, nothing below ~L40 reaches it, so the band was the whole behaviour
and the objective never ran.*

### S-006 · A means is an investment, priced like any other

A discretionary or collect-band means competes on the same quantity as the
objective step: the marginal cycles it costs (S-002) against the cycles it saves
or the progress it unlocks over the horizon. There is no band that wins by
position.

**Deletes** `BAND_DISCRETIONARY`'s unreachability, and with it the four bespoke
urgency hoists (`RECYCLE_HOIST_URGENCY`, `SHED_HOIST_URGENCY`,
`bank_shed_hoist`, `SUPPLY_DEMAND_MIN`) — each of which exists only to undo the
side-effect of a promotion made necessary by the ordering.

**Does NOT delete** `BAND_GUARD`. Survival is not an investment: a guard is a
correctness constraint on the state, not a use of a cycle, and it keeps
precedence. *`GuardKind.RESTORE_HP` and the discard/deposit guards stay exactly
as they are.*

### S-007 · A task is worth accepting when its work overlaps committed work

A task's marginal cost (S-002) is the cycles it demands that are not already
committed. Its value is its rewards plus whatever its demanded work was worth
anyway. Three consequences, and they are the design, not examples:

1. A task aligned with a **skill-XP grind already committed to** costs ~0 — the
   grind happens regardless — so its rewards are pure gain.
2. When **character XP** is the need, a kill-monsters task costs ~0 for the same
   reason: `task reward + xp > xp alone`.
3. A task is pursued **for its own sake only when the rewards are themselves the
   need** — gold or `tasks_coin` required for a specific purchase (S-008).

*`tiers/means_worth._task_need_overlap` ALREADY computes how many of a task's
four output kinds serve a live objective need, then discards the number through
`synergy_pure(overlap, K) > S_MIN` — a ranking quantity used as a boolean gate.
This clause makes it compete. It is the same "computed and thrown away" shape as
`J` itself.*

### S-008 · `tasks_coin` is a route, priced at the task's marginal cycles

Earning a task currency is a seventh `SourceKind`. Its per-unit cost is the
marginal cycles (S-002) of the task that yields it, so a coin earned by a task
the bot was going to do anyway is nearly free, and a coin earned by a task
undertaken solely to fund a purchase costs that task in full.

**This is the whole of C4.** The funding pipeline is not a separate mechanism; it
is the currency route the cost model never had.

*Measured 2026-08-18, and the two walks flatly contradict each other today:*

```
is_task_earnable('tasks_coin')   -> True          (boolean attainability walk)
route_options('tasks_coin')      -> []            (priced route walk)
acquisition_actions('tasks_coin')-> 1,000,000
acquisition_actions('satchel')   -> 1,000,010     (the C4 epic's own target item)
```

*`obtain_sources`' docstring already anticipates this: "a SEVENTH route becomes
one edit to `obtain_sources` and every consumer — including the price — gains it
structurally."*

### S-009 · One horizon, named once

Every clause above is evaluated over the same horizon, and the horizon is stated
in one place. Nothing may introduce a second.

*Today there are four unrelated ones — `RECIPE_SKILL_HORIZON = 2`,
`progression_reserve._HORIZON`, `_CHAR_LEVEL_BOOTSTRAP_HORIZON = 2`,
`strategic_value`'s `horizon` tuple — and the objective reads none of them.
`progression_tree_core.milestone_pure` is Lean-proved and is what the trunk goal
already uses; it is the obvious candidate, subject to S-010.*

### S-010 · The horizon must not degenerate at either end

A horizon measured in levels goes flat at a band edge and unreachable at a
distance. Whatever S-009 names must state its behaviour at both ends.

*Measured: at four levels of headroom the benefit term spreads 1,086–1,182 cycles
across 11–12 candidates; at ONE level of headroom it spreads exactly 0; at level
50 nothing arrives at all. A ten-level milestone is right in the middle of a band
and wrong at its edges.*

### S-011 · Proof witnesses are exempt

A rung whose purpose is to be the ladder's unconditional last resort is not an
investment and is not ranked. It fires when nothing else does, and its never
firing is the guarantee working.

*`MeansKind.WAIT` is the totality witness for
`Formal.Liveness.NoDeadlockV2.productionLadder_total`. This clause exists because
this spec's own first draft proposed deleting it.*

---

## Acceptance criteria

Each is measurable with tooling that already exists (`artifactsmmo objective`,
`scripts/gen_liveness.py`, the learning DB), and each names the number it must
move.

| # | criterion | today | must become |
|---|---|---|---|
| A1 | `J` is finite for a real candidate set | 0 / 10,716 cycles | a majority of cycles |
| A2 | the deciding clause is the objective, not a tiebreak | `S-006 key 2` on every cycle | `S-005 (J)` |
| A3 | a shared prerequisite is paid once across a set | 68% amortised in the pricer, invisible to `J` | visible to `J` |
| A4 | `tasks_coin` has a finite price | 1,000,000 | finite |
| A5 | `satchel` (C4's target) has a finite price | 1,000,010 | finite |
| A6 | a task is ever accepted | 0 / 63,310 cycles | > 0, and only when S-007 justifies it |
| A7 | the discretionary band is not decided by position | 133 / 63,310 = 0.21% | means selected on merit |
| A8 | liveness census `unreachable:` count | 19 | 0 (excluding `witness:`) |
| A9 | per-decision cost inside the planning budget | 6–34 s live, budget floor 15 s | under budget |

A9 is the one that can fail on physics rather than design: measured 2026-08-18,
evaluating one candidate at one rung costs ~235 ms — the same order as a whole
rung — and only ~27% of candidates can be excluded by a cheap static predicate.
The naive shape is `rungs × candidates × 235 ms`. **An incremental evaluation is
a requirement of this spec, not an optimisation**, and if none is found the
horizon must shrink until A9 holds.

---

## What this spec deletes

* `branch_objective`'s candidate construction (`gear_candidate`,
  `trunk_candidate`, `branch_ranking`).
* `progression_choice`'s banding: `candidate_band`, `objective_j`, `sort_key`'s
  band arms, `rank_candidates`.
* Unified-objective clauses S-003, S-004, S-005, S-006, S-014, and their Lean
  mirrors in `Formal.ProgressionChoice`.
* `BAND_DISCRETIONARY` as a position, and the four urgency hoists that exist to
  escape it.
* `UNOBTAINABLE_PER_UNIT` as a ranking value — it survives only as a prune for
  content with no route in the game data at all.

Net: fewer clauses, fewer constants, fewer bands. A spec that adds machinery to
this area has misread the problem.

---

## Residuals, stated

* **A9 is unproven.** See above. It is the one criterion that could force the
  design back to option B (a horizon in cycles rather than a walk that spends).
* **`adventurer_vest`** — whose recipe fan-out once ran 10.1M recursive calls in
  20 s at this exact seam — is currently walled and so has never been priced for
  real. Every cost figure here must be re-taken once the pricing wall is gone.
* **Guards are exempt by assertion** (S-006). Nobody has checked whether a guard
  ever fires when an investment would have paid more; `hp_critical` fires 6,630
  times and `gear_review` 6,021, and neither is priced.
* **The `witness:` category has one member.** If a second appears, the exemption
  needs a rule rather than a list.
* **Task rewards are not yet modelled per task.** S-007 needs the reward a
  specific task pays; `task_reward_observations` exists and holds **0 rows**.
