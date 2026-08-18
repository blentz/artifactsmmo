# Ontology grid

**Subjects:** cost_pair: express every cost/benefit/price as (cycles, seconds), compare_options: rank on cycles, seconds as availability bound, marginal_cost: cycles an option adds beyond committed work, committed_work: the remaining actions of the plan in flight, J: total cycles of one projection walk to the horizon, walk_acquisition: pay a route to obtain+equip at a level, refit: re-derive the worn set and credit the difference, route_set: the routes by which an item may be obtained (incl. sibling/bank stock with capacity), route_price: expected cost over an uncontrolled outcome, price_uncompletable: cost to make a course completable, guard_precedence: unpriced survival constraint outranks comparison, compare_means_vs_objective_step: same quantity, no band privilege, task_decision: accept/decline a task on marginal cost and reward, horizon: the single horizon and its extremes, totality_witness: the always-selectable last-resort means, task_currency_price: per-unit price of a currency earned by tasks
**Stimuli:** normal, boundary, degenerate, conflicting, absent, stale/expired input (TTL), retry/duplicate/replay, dependency failure, concurrent stimulus
**Stimulus-waivers:** NO category is waived. Purity waives only INTERNAL data races: the core mutates nothing shared, so two simultaneous calls cannot corrupt its own state — exactly two cells are marked IGNORE on that narrow ground (cost_pair/concurrent, refit/concurrent), and both name where the contention is charged instead. The four categories themselves are live for this artifact and must not be silently dropped: (a) TIMING — S-001's second component IS wall clock, the character sits on a cooldown while the decision runs, and the Evidence row "Σ dim 8" records a 6–34 s decision against a planning window floored at 15 s; the decision therefore has a deadline that no clause states, and a candidate evaluation at ~235 ms means the walk can be cut off mid-flight. (b) STALENESS — S-009's learned rates, S-005's plan in flight, and the sibling/bank stock snapshot behind S-004 are all inputs produced in one tick and consumed in a later one; the Evidence footnote even records the published rest formula CHANGING (1s/5HP → 1s/1% missing HP), i.e. a constant that expires. (c) DEPENDENCY FAILURE — the spec's own preamble names five components (A* planner, loadout picker, combat model, coordination protocol, executor) that "supply inputs"; a supplier that returns nothing, errors, or is nondeterministic is a stimulus to this core, not an impossibility, and declaring those components out of test does not make their failure modes out of scope for the consumer. (d) CONCURRENCY — S-004 explicitly names two characters pricing the same limited stock in the same tick and declines to decide it; that is a THIN cell (the spec gestures and defers), never a waiver, because the deferral target (the coordination protocol) is declared not under test, so no document decides it.

<!-- ABSENT FROM THE SPEC ENTIRELY — the domain has these and the spec never names them,
     so they have no cell at all, not even a MISSING one. Decide whether they belong:
       - The decision's own compute cost and deadline. Evidence 'Σ dim 8' measures a 6–34 s decision against a 15 s planning window, and a Residual admits the walk may not be affordable — yet no clause names the planning window, what the decision returns when the window expires mid-walk (partial J? previous choice? the totality witness?), or whether a partial walk may be compared against a complete one.
       - The cooldown clock the character is currently on. Every decision is made while an action's cooldown is running; the remaining cooldown is the actual planning budget and the reason seconds exist in S-001, but no clause names elapsed/remaining cooldown as an input to any comparison.
       - Inventory slot capacity. S-007 acquires and holds items across levels with no notion that holdings are slot-limited; a walk that acquires four items may be unrealizable, and the cycles of depositing/withdrawing to make room are never priced.
       - Gold and other spendable balances as a scarce budget. S-015 prices EARNING a currency but no clause names a balance constraint: a route with a purchase price is 'priced like any other route' even when the character cannot pay, which S-010 would have to turn into a remedy cost that nothing defines.
       - Action failure and server rejection at execution time — a fight lost, an item gone before the withdraw, a 499 cooldown collision. S-005 has commitments discharged 'as its actions execute' with no branch for an action that executes and FAILS, so the in-flight plan's fate after a failure is nowhere in the model.
       - Risk of loss as a priced quantity. The combat model is out of scope, but the PROBABILITY of losing a fight is precisely 'an outcome the character does not control' (S-009) and a loss costs cycles and HP; no clause names risk, variance, or ruin, and S-009 explicitly declines to bound the spread.
       - Time-limited world content — events, raids, spawn windows. The world can present a route that exists only for an interval; nothing in the clause set has a notion of a route that expires, nor of an opportunity cost for missing one.
       - Market / Grand-Exchange prices set by other agents. A route whose price moves between the tick it was read and the tick it is executed, and whose orders can be cancelled or filled by someone else, is a route with no stable price — S-009's expectation is over the character's own outcomes, not over other agents.
       - Consumables. Potions, food and any item CONSUMED rather than worn: S-008 re-derives what the character WEARS, so an acquisition that is drunk has no place in the credit rule and is silently credited with nothing.
       - Skill gates and level-legality re-derivation inside the walk. S-007 crosses levels with items held, but nothing says the ROUTE SET is re-derived at each level; a route illegal now and legal two levels on, or vice versa, has no defined treatment.
       - Whoever holds a reservation on shared stock. S-004 gives the sibling/bank route 'a capacity' but no entity in this document produces that number, and the component that would (coordination) is declared not under test — the capacity input has no author.
       - The per-IP action rate budget. Evidence S-002 says 60.9% of wall clock is rate budget, planning and idle, and that this is why cycles rank — the binding resource in the whole system is named only in Evidence, and Evidence is declared non-normative.
       - A plan QUEUE, or more than one plan in flight. S-005 speaks of 'the plan' in the singular; adopting a new plan while one is carried, or holding two, is not an error and is not a state.
       - The no-op / idle outcome. Nothing says whether 'do nothing this cycle' is a selectable result, what it costs, or whether it is distinct from the totality witness.
       - Persistent state between decisions — memo caches, the learning store's writes, and any hysteresis. Two consecutive decisions on an unchanged world are never required to agree, so nothing forbids a course flip every cycle.
       - Task expiry, abandonment and its penalty. S-013/S-014 decide acceptance; nothing models a task that ages out, is cancelled, or costs something to drop once accepted.
-->

## Grid

| Subject | Stimulus | Verdict | Clauses | Justification |
|---|---|---|---|---|
| cost_pair: express every cost/benefit/price as (cycles, seconds) | normal | DEFINED | S-001 |  |
| cost_pair: express every cost/benefit/price as (cycles, seconds) | boundary | MISSING |  |  |
| cost_pair: express every cost/benefit/price as (cycles, seconds) | degenerate | MISSING |  |  |
| cost_pair: express every cost/benefit/price as (cycles, seconds) | conflicting | MISSING |  |  |
| cost_pair: express every cost/benefit/price as (cycles, seconds) | absent | MISSING |  |  |
| cost_pair: express every cost/benefit/price as (cycles, seconds) | stale/expired input (TTL) | MISSING |  |  |
| cost_pair: express every cost/benefit/price as (cycles, seconds) | retry/duplicate/replay | MISSING |  |  |
| cost_pair: express every cost/benefit/price as (cycles, seconds) | dependency failure | MISSING |  |  |
| cost_pair: express every cost/benefit/price as (cycles, seconds) | concurrent stimulus | IGNORE |  | Unit conversion is a pure function of its arguments and the published cooldown table, in a core the spec declares has no I/O; two conversions at once share no mutable state and produce no observable in Σ. The table's own refresh between decisions is charged to this subject's stale-input cell instead, where it is a live MISSING. |
| compare_options: rank on cycles, seconds as availability bound | normal | DEFINED | S-002 |  |
| compare_options: rank on cycles, seconds as availability bound | boundary | THIN | S-002 |  |
| compare_options: rank on cycles, seconds as availability bound | degenerate | MISSING |  |  |
| compare_options: rank on cycles, seconds as availability bound | conflicting | DEFINED | S-002 |  |
| compare_options: rank on cycles, seconds as availability bound | absent | THIN | S-002 |  |
| compare_options: rank on cycles, seconds as availability bound | stale/expired input (TTL) | MISSING |  |  |
| compare_options: rank on cycles, seconds as availability bound | retry/duplicate/replay | MISSING |  |  |
| compare_options: rank on cycles, seconds as availability bound | dependency failure | MISSING |  |  |
| compare_options: rank on cycles, seconds as availability bound | concurrent stimulus | MISSING |  |  |
| marginal_cost: cycles an option adds beyond committed work | normal | DEFINED | S-003, S-005 |  |
| marginal_cost: cycles an option adds beyond committed work | boundary | DEFINED | S-003 |  |
| marginal_cost: cycles an option adds beyond committed work | degenerate | THIN | S-005 |  |
| marginal_cost: cycles an option adds beyond committed work | conflicting | THIN | S-003, S-005 |  |
| marginal_cost: cycles an option adds beyond committed work | absent | MISSING |  |  |
| marginal_cost: cycles an option adds beyond committed work | stale/expired input (TTL) | THIN | S-005 |  |
| marginal_cost: cycles an option adds beyond committed work | retry/duplicate/replay | MISSING |  |  |
| marginal_cost: cycles an option adds beyond committed work | dependency failure | THIN | S-005 |  |
| marginal_cost: cycles an option adds beyond committed work | concurrent stimulus | THIN | S-004 |  |
| committed_work: the remaining actions of the plan in flight | normal | DEFINED | S-005 |  |
| committed_work: the remaining actions of the plan in flight | boundary | DEFINED | S-005 |  |
| committed_work: the remaining actions of the plan in flight | degenerate | THIN | S-005 |  |
| committed_work: the remaining actions of the plan in flight | conflicting | MISSING |  |  |
| committed_work: the remaining actions of the plan in flight | absent | MISSING |  |  |
| committed_work: the remaining actions of the plan in flight | stale/expired input (TTL) | MISSING |  |  |
| committed_work: the remaining actions of the plan in flight | retry/duplicate/replay | MISSING |  |  |
| committed_work: the remaining actions of the plan in flight | dependency failure | MISSING |  |  |
| committed_work: the remaining actions of the plan in flight | concurrent stimulus | MISSING |  |  |
| J: total cycles of one projection walk to the horizon | normal | DEFINED | S-006 |  |
| J: total cycles of one projection walk to the horizon | boundary | MISSING |  |  |
| J: total cycles of one projection walk to the horizon | degenerate | MISSING |  |  |
| J: total cycles of one projection walk to the horizon | conflicting | THIN | S-002, S-006 |  |
| J: total cycles of one projection walk to the horizon | absent | MISSING |  |  |
| J: total cycles of one projection walk to the horizon | stale/expired input (TTL) | MISSING |  |  |
| J: total cycles of one projection walk to the horizon | retry/duplicate/replay | MISSING |  |  |
| J: total cycles of one projection walk to the horizon | dependency failure | MISSING |  |  |
| J: total cycles of one projection walk to the horizon | concurrent stimulus | THIN | S-004 |  |
| walk_acquisition: pay a route to obtain+equip at a level | normal | DEFINED | S-007 |  |
| walk_acquisition: pay a route to obtain+equip at a level | boundary | DEFINED | S-007 |  |
| walk_acquisition: pay a route to obtain+equip at a level | degenerate | MISSING |  |  |
| walk_acquisition: pay a route to obtain+equip at a level | conflicting | THIN | S-007, S-008 |  |
| walk_acquisition: pay a route to obtain+equip at a level | absent | THIN | S-010 |  |
| walk_acquisition: pay a route to obtain+equip at a level | stale/expired input (TTL) | THIN | S-017 |  |
| walk_acquisition: pay a route to obtain+equip at a level | retry/duplicate/replay | MISSING |  |  |
| walk_acquisition: pay a route to obtain+equip at a level | dependency failure | MISSING |  |  |
| walk_acquisition: pay a route to obtain+equip at a level | concurrent stimulus | THIN | S-004 |  |
| refit: re-derive the worn set and credit the difference | normal | DEFINED | S-008 |  |
| refit: re-derive the worn set and credit the difference | boundary | THIN | S-008 |  |
| refit: re-derive the worn set and credit the difference | degenerate | MISSING |  |  |
| refit: re-derive the worn set and credit the difference | conflicting | MISSING |  |  |
| refit: re-derive the worn set and credit the difference | absent | MISSING |  |  |
| refit: re-derive the worn set and credit the difference | stale/expired input (TTL) | MISSING |  |  |
| refit: re-derive the worn set and credit the difference | retry/duplicate/replay | MISSING |  |  |
| refit: re-derive the worn set and credit the difference | dependency failure | MISSING |  |  |
| refit: re-derive the worn set and credit the difference | concurrent stimulus | IGNORE |  | Re-fit is a within-walk re-derivation over ONE character's holdings, and S-004 makes another character's stock not this character's holding; there is no shared mutable state for a simultaneous stimulus to touch. Contention over shared STOCK is a real gap and is charged to route_set/concurrent and walk_acquisition/concurrent instead, not waived here. |
| route_set: the routes by which an item may be obtained (incl. sibling/bank stock with capacity) | normal | THIN | S-004 |  |
| route_set: the routes by which an item may be obtained (incl. sibling/bank stock with capacity) | boundary | MISSING |  |  |
| route_set: the routes by which an item may be obtained (incl. sibling/bank stock with capacity) | degenerate | THIN | S-010 |  |
| route_set: the routes by which an item may be obtained (incl. sibling/bank stock with capacity) | conflicting | MISSING |  |  |
| route_set: the routes by which an item may be obtained (incl. sibling/bank stock with capacity) | absent | MISSING |  |  |
| route_set: the routes by which an item may be obtained (incl. sibling/bank stock with capacity) | stale/expired input (TTL) | MISSING |  |  |
| route_set: the routes by which an item may be obtained (incl. sibling/bank stock with capacity) | retry/duplicate/replay | MISSING |  |  |
| route_set: the routes by which an item may be obtained (incl. sibling/bank stock with capacity) | dependency failure | MISSING |  |  |
| route_set: the routes by which an item may be obtained (incl. sibling/bank stock with capacity) | concurrent stimulus | THIN | S-004 |  |
| route_price: expected cost over an uncontrolled outcome | normal | DEFINED | S-009 |  |
| route_price: expected cost over an uncontrolled outcome | boundary | THIN | S-009 |  |
| route_price: expected cost over an uncontrolled outcome | degenerate | DEFINED | S-009 |  |
| route_price: expected cost over an uncontrolled outcome | conflicting | DEFINED | S-009 |  |
| route_price: expected cost over an uncontrolled outcome | absent | MISSING |  |  |
| route_price: expected cost over an uncontrolled outcome | stale/expired input (TTL) | MISSING |  |  |
| route_price: expected cost over an uncontrolled outcome | retry/duplicate/replay | MISSING |  |  |
| route_price: expected cost over an uncontrolled outcome | dependency failure | THIN | S-009 |  |
| route_price: expected cost over an uncontrolled outcome | concurrent stimulus | MISSING |  |  |
| price_uncompletable: cost to make a course completable | normal | DEFINED | S-010 |  |
| price_uncompletable: cost to make a course completable | boundary | THIN | S-010 |  |
| price_uncompletable: cost to make a course completable | degenerate | DEFINED | S-010 |  |
| price_uncompletable: cost to make a course completable | conflicting | THIN | S-010 |  |
| price_uncompletable: cost to make a course completable | absent | THIN | S-010 |  |
| price_uncompletable: cost to make a course completable | stale/expired input (TTL) | MISSING |  |  |
| price_uncompletable: cost to make a course completable | retry/duplicate/replay | MISSING |  |  |
| price_uncompletable: cost to make a course completable | dependency failure | MISSING |  |  |
| price_uncompletable: cost to make a course completable | concurrent stimulus | MISSING |  |  |
| guard_precedence: unpriced survival constraint outranks comparison | normal | DEFINED | S-012 |  |
| guard_precedence: unpriced survival constraint outranks comparison | boundary | MISSING |  |  |
| guard_precedence: unpriced survival constraint outranks comparison | degenerate | DEFINED | S-012 |  |
| guard_precedence: unpriced survival constraint outranks comparison | conflicting | MISSING |  |  |
| guard_precedence: unpriced survival constraint outranks comparison | absent | MISSING |  |  |
| guard_precedence: unpriced survival constraint outranks comparison | stale/expired input (TTL) | MISSING |  |  |
| guard_precedence: unpriced survival constraint outranks comparison | retry/duplicate/replay | MISSING |  |  |
| guard_precedence: unpriced survival constraint outranks comparison | dependency failure | MISSING |  |  |
| guard_precedence: unpriced survival constraint outranks comparison | concurrent stimulus | MISSING |  |  |
| compare_means_vs_objective_step: same quantity, no band privilege | normal | DEFINED | S-011 |  |
| compare_means_vs_objective_step: same quantity, no band privilege | boundary | THIN | S-011, S-002 |  |
| compare_means_vs_objective_step: same quantity, no band privilege | degenerate | DEFINED | S-018 |  |
| compare_means_vs_objective_step: same quantity, no band privilege | conflicting | THIN | S-011 |  |
| compare_means_vs_objective_step: same quantity, no band privilege | absent | MISSING |  |  |
| compare_means_vs_objective_step: same quantity, no band privilege | stale/expired input (TTL) | MISSING |  |  |
| compare_means_vs_objective_step: same quantity, no band privilege | retry/duplicate/replay | MISSING |  |  |
| compare_means_vs_objective_step: same quantity, no band privilege | dependency failure | MISSING |  |  |
| compare_means_vs_objective_step: same quantity, no band privilege | concurrent stimulus | MISSING |  |  |
| task_decision: accept/decline a task on marginal cost and reward | normal | DEFINED | S-013, S-014 |  |
| task_decision: accept/decline a task on marginal cost and reward | boundary | DEFINED | S-014 |  |
| task_decision: accept/decline a task on marginal cost and reward | degenerate | MISSING |  |  |
| task_decision: accept/decline a task on marginal cost and reward | conflicting | THIN | S-013, S-014 |  |
| task_decision: accept/decline a task on marginal cost and reward | absent | THIN | S-013 |  |
| task_decision: accept/decline a task on marginal cost and reward | stale/expired input (TTL) | MISSING |  |  |
| task_decision: accept/decline a task on marginal cost and reward | retry/duplicate/replay | MISSING |  |  |
| task_decision: accept/decline a task on marginal cost and reward | dependency failure | MISSING |  |  |
| task_decision: accept/decline a task on marginal cost and reward | concurrent stimulus | MISSING |  |  |
| horizon: the single horizon and its extremes | normal | THIN | S-016, S-017 |  |
| horizon: the single horizon and its extremes | boundary | THIN | S-017 |  |
| horizon: the single horizon and its extremes | degenerate | THIN | S-017 |  |
| horizon: the single horizon and its extremes | conflicting | DEFINED | S-016 |  |
| horizon: the single horizon and its extremes | absent | MISSING |  |  |
| horizon: the single horizon and its extremes | stale/expired input (TTL) | MISSING |  |  |
| horizon: the single horizon and its extremes | retry/duplicate/replay | MISSING |  |  |
| horizon: the single horizon and its extremes | dependency failure | MISSING |  |  |
| horizon: the single horizon and its extremes | concurrent stimulus | MISSING |  |  |
| totality_witness: the always-selectable last-resort means | normal | DEFINED | S-018 |  |
| totality_witness: the always-selectable last-resort means | boundary | DEFINED | S-018 |  |
| totality_witness: the always-selectable last-resort means | degenerate | MISSING |  |  |
| totality_witness: the always-selectable last-resort means | conflicting | MISSING |  |  |
| totality_witness: the always-selectable last-resort means | absent | MISSING |  |  |
| totality_witness: the always-selectable last-resort means | stale/expired input (TTL) | MISSING |  |  |
| totality_witness: the always-selectable last-resort means | retry/duplicate/replay | MISSING |  |  |
| totality_witness: the always-selectable last-resort means | dependency failure | MISSING |  |  |
| totality_witness: the always-selectable last-resort means | concurrent stimulus | MISSING |  |  |
| task_currency_price: per-unit price of a currency earned by tasks | normal | THIN | S-015 |  |
| task_currency_price: per-unit price of a currency earned by tasks | boundary | MISSING |  |  |
| task_currency_price: per-unit price of a currency earned by tasks | degenerate | MISSING |  |  |
| task_currency_price: per-unit price of a currency earned by tasks | conflicting | DEFINED | S-015, S-002 |  |
| task_currency_price: per-unit price of a currency earned by tasks | absent | THIN | S-010 |  |
| task_currency_price: per-unit price of a currency earned by tasks | stale/expired input (TTL) | MISSING |  |  |
| task_currency_price: per-unit price of a currency earned by tasks | retry/duplicate/replay | MISSING |  |  |
| task_currency_price: per-unit price of a currency earned by tasks | dependency failure | MISSING |  |  |
| task_currency_price: per-unit price of a currency earned by tasks | concurrent stimulus | MISSING |  |  |
