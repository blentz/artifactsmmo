# Ontology grid

**Subjects:** cost_pair: express a quantity as (cycles, seconds), rank candidates on cycles, seconds-budget availability filter, action-rate budget accounting, marginal cost against committed work, committed-work set from the plan in flight, J scope: one character, sibling/bank stock as a route, deadline-bounded candidate evaluation and pick, projection walk that yields J, acquire-during-walk decision, route-set re-derivation at each level crossed, re-fit and credit after an acquisition, consumable credited as a rate change vs a depleting stock, route price as expected cost (learned vs published), pricing a course the state makes uncompletable, guard precedence over the priced comparison, task accept/decline evaluation, task-currency route pricing, horizon selection and behaviour at its extremes, totality-witness (last-resort means) selection, determinism: same state, same choice
**Stimuli:** normal, boundary, degenerate, conflicting, absent, stale / expiry / deadline, retry / duplicate / replay, dependency-failure, concurrent
**Stimulus-waivers:** No stimulus category is waived. The "pure decision core, no I/O" framing might suggest waiving time, dependency-failure and concurrency, but the spec itself defeats that: S-005 puts a WALL-CLOCK deadline inside the decision, S-003 names a rate budget "shared by every character", S-007 names siblings and a shared bank, S-008 names an action that "executes and fails", and S-014 names observations accumulated over time. A pure function whose inputs are supplied still faces supplied inputs that are stale, absent, mutually contradictory, or that changed between two evaluations, and the spec's own residuals concede several of these. Two individual CELLS are carved out as IGNORE (recorded in the grid with justifications), not two categories.

<!-- ABSENT FROM THE SPEC ENTIRELY — the domain has these and the spec never names them,
     so they have no cell at all, not even a MISSING one. Decide whether they belong:
       - THE COOLDOWN IN PROGRESS. The bot is always inside a cooldown when it decides; the decision window IS that cooldown (Evidence Σ dim 8 alludes to a 'planning window floored at 15 s'). No clause names the cooldown remaining at decision time, so S-005's deadline has no stated source and S-001's seconds are never related to the seconds the bot is already owed.
       - A LEVEL, AND WHICH LEVEL. S-009/S-010/S-011/S-013 all say the walk 'crosses levels', but the spec never says what a level is, never distinguishes the combat level from the per-skill levels (a domain with gathering/crafting skills has many), and never names XP or the rate at which levels arrive — the very quantity the walk must project.
       - THE LEVEL-UP EVENT and the XP quantity that produces it. The walk consumes levels as if they were free milestones; nothing names what advances one or what it costs.
       - POSITION AND TRAVEL. Movement cooldown appears only in Evidence for S-001. Where the character IS, and the cycles of getting somewhere, are never an entity — yet every route in S-011/S-014 implies a place.
       - INVENTORY SLOTS / CARRY CAPACITY. Conceded in a residual but named by no clause: the walk may acquire a holding the character cannot carry, and the cycles of making room are unpriced.
       - GOLD AND SPENDABLE BALANCES. Conceded in a residual, clause-less: a purchase route is priced like any other even when the character cannot pay. Also means S-001's 'converted into both components' has no stated conversion for a price in gold.
       - COMBAT LOSS / DEATH / HP. S-017 speaks of 'a condition on the state that must hold for the bot to continue operating' without ever naming HP, damage, a lost fight, or death — so the guard clause has no subject matter.
       - THE DROP OUTCOME. S-014 refers to 'an outcome the character does not control' but never names drops, drop rates, quantities, or the variance the residual admits is unbounded.
       - AN UNKNOWN ACTION OUTCOME. S-008 admits exactly two outcomes, success and failure. A timeout, a 429, an accepted-but-unconfirmed action — the case where the bot does not KNOW whether the commitment discharged — has no name.
       - SERVER / API UNAVAILABILITY and the rate-limit rejection. S-003 names a per-IP-style budget as the scarce resource but never names what happens when an issued action is refused by it.
       - PLAN ABANDONMENT / REPLAN. S-008 creates a commitment on adoption and discharges it only by success. Nothing names ending a commitment any other way, so a plan invalidated by the world has no exit and the residual's 'retrying forever' has no counterpart clause.
       - THE CANDIDATE GENERATOR. S-005 makes evaluation ORDER decisive and then explicitly declines to fix it; the thing that enumerates candidates is never named as an entity at all.
       - STATE IDENTITY. S-004 rests entirely on 'the same world state' with no equality relation named — no clause says which fields are part of the state, so 'same' is undecidable and the clause is unfalsifiable.
       - THE BAND / POSITION structure. S-016 forbids winning 'by virtue of the band or position it occupies' and S-023 speaks of 'a means', but neither the means catalogue nor the band structure is ever defined.
       - A RESERVATION / CLAIM on shared stock. S-007 gives sibling and bank stock a 'capacity' but no entity holds a claim against it, which is exactly what makes the two-characters-one-stock case undecidable.
       - TIME-LIMITED WORLD CONTENT (events, raids, market orders with a lifetime). No clause admits a route that EXPIRES, so the route set of S-011 is implicitly eternal.
       - THE MARKET / EXCHANGE as a route with a counterparty, an order lifetime, and a maker/taker distinction — and NPC vendors with limited stock. S-020 makes a task a source of currency but no clause names any other named source it is 'on the same footing' with.
       - RECYCLING / DESTRUCTION as a route direction. Every route in the spec runs materials → item; a domain that crafts also converts an item back into materials, and that route is never named.
       - EQUIPMENT SLOTS, including duplicate slots. S-012 re-fits 'which items the character wears' with no slot model, so 'displaces something already worn' has no defined resolution.
       - AN ACCEPTED TASK AS STATE, plus task abandonment, task re-roll, and task progress. S-018/S-019/S-020 treat a task as an offer to be priced and never as a thing the character is already holding.
       - STOCK CONSUMPTION RATE. S-013 debits a stock as the walk crosses levels and then disclaims how much a level consumes — the consuming entity is named nowhere.
       - A NO-OP / ZERO-ACTION OPTION. S-001 defines a cycle as an executed planner action; an option that executes none (already satisfied, or the unpriced witness of S-023) has no defined cost and no defined rank.
-->

## Grid

| Subject | Stimulus | Verdict | Clauses | Justification |
|---|---|---|---|---|
| cost_pair: express a quantity as (cycles, seconds) | normal | DEFINED | S-001 |  |
| cost_pair: express a quantity as (cycles, seconds) | boundary | THIN | S-001 |  |
| cost_pair: express a quantity as (cycles, seconds) | degenerate | MISSING |  |  |
| cost_pair: express a quantity as (cycles, seconds) | conflicting | THIN | S-001 |  |
| cost_pair: express a quantity as (cycles, seconds) | absent | MISSING |  |  |
| cost_pair: express a quantity as (cycles, seconds) | stale / expiry / deadline | MISSING |  |  |
| cost_pair: express a quantity as (cycles, seconds) | retry / duplicate / replay | THIN | S-004 |  |
| cost_pair: express a quantity as (cycles, seconds) | dependency-failure | MISSING |  |  |
| cost_pair: express a quantity as (cycles, seconds) | concurrent | IGNORE |  | Converting one supplied quantity into a pair holds no state and reads nothing shared; two conversions in flight cannot interact. Carved out here ONLY for the arithmetic — the concurrency question moves to the subjects that read world state. |
| rank candidates on cycles | normal | DEFINED | S-002, S-016 |  |
| rank candidates on cycles | boundary | THIN | S-002 |  |
| rank candidates on cycles | degenerate | THIN | S-023 |  |
| rank candidates on cycles | conflicting | THIN | S-002, S-016, S-017 |  |
| rank candidates on cycles | absent | MISSING |  |  |
| rank candidates on cycles | stale / expiry / deadline | MISSING |  |  |
| rank candidates on cycles | retry / duplicate / replay | DEFINED | S-004 |  |
| rank candidates on cycles | dependency-failure | MISSING |  |  |
| rank candidates on cycles | concurrent | MISSING |  |  |
| seconds-budget availability filter | normal | THIN | S-002 |  |
| seconds-budget availability filter | boundary | THIN | S-002 |  |
| seconds-budget availability filter | degenerate | MISSING |  |  |
| seconds-budget availability filter | conflicting | MISSING |  |  |
| seconds-budget availability filter | absent | MISSING |  |  |
| seconds-budget availability filter | stale / expiry / deadline | MISSING |  |  |
| seconds-budget availability filter | retry / duplicate / replay | THIN | S-004 |  |
| seconds-budget availability filter | dependency-failure | MISSING |  |  |
| seconds-budget availability filter | concurrent | MISSING |  |  |
| action-rate budget accounting | normal | THIN | S-003 |  |
| action-rate budget accounting | boundary | MISSING |  |  |
| action-rate budget accounting | degenerate | MISSING |  |  |
| action-rate budget accounting | conflicting | THIN | S-003, S-002 |  |
| action-rate budget accounting | absent | MISSING |  |  |
| action-rate budget accounting | stale / expiry / deadline | MISSING |  |  |
| action-rate budget accounting | retry / duplicate / replay | MISSING |  |  |
| action-rate budget accounting | dependency-failure | MISSING |  |  |
| action-rate budget accounting | concurrent | THIN | S-003 |  |
| marginal cost against committed work | normal | DEFINED | S-006, S-008 |  |
| marginal cost against committed work | boundary | THIN | S-006 |  |
| marginal cost against committed work | degenerate | DEFINED | S-006, S-008 |  |
| marginal cost against committed work | conflicting | MISSING |  |  |
| marginal cost against committed work | absent | MISSING |  |  |
| marginal cost against committed work | stale / expiry / deadline | MISSING |  |  |
| marginal cost against committed work | retry / duplicate / replay | DEFINED | S-008 |  |
| marginal cost against committed work | dependency-failure | MISSING |  |  |
| marginal cost against committed work | concurrent | MISSING |  |  |
| committed-work set from the plan in flight | normal | DEFINED | S-008 |  |
| committed-work set from the plan in flight | boundary | THIN | S-008 |  |
| committed-work set from the plan in flight | degenerate | DEFINED | S-008 |  |
| committed-work set from the plan in flight | conflicting | MISSING |  |  |
| committed-work set from the plan in flight | absent | MISSING |  |  |
| committed-work set from the plan in flight | stale / expiry / deadline | MISSING |  |  |
| committed-work set from the plan in flight | retry / duplicate / replay | DEFINED | S-008 |  |
| committed-work set from the plan in flight | dependency-failure | MISSING |  |  |
| committed-work set from the plan in flight | concurrent | MISSING |  |  |
| J scope: one character, sibling/bank stock as a route | normal | DEFINED | S-007 |  |
| J scope: one character, sibling/bank stock as a route | boundary | THIN | S-007 |  |
| J scope: one character, sibling/bank stock as a route | degenerate | THIN | S-007 |  |
| J scope: one character, sibling/bank stock as a route | conflicting | MISSING |  |  |
| J scope: one character, sibling/bank stock as a route | absent | MISSING |  |  |
| J scope: one character, sibling/bank stock as a route | stale / expiry / deadline | MISSING |  |  |
| J scope: one character, sibling/bank stock as a route | retry / duplicate / replay | THIN | S-004 |  |
| J scope: one character, sibling/bank stock as a route | dependency-failure | MISSING |  |  |
| J scope: one character, sibling/bank stock as a route | concurrent | IGNORE |  | S-007's note and the residuals BOTH state on the record that two characters pricing the same limited stock in one tick belongs to the coordination protocol, which the scope statement puts outside the artifact under test. Carved out as written — but the carve-out is only sound if some other document carries the witness; the spec asserts that and does not name the document. |
| deadline-bounded candidate evaluation and pick | normal | DEFINED | S-005 |  |
| deadline-bounded candidate evaluation and pick | boundary | THIN | S-005 |  |
| deadline-bounded candidate evaluation and pick | degenerate | MISSING |  |  |
| deadline-bounded candidate evaluation and pick | conflicting | THIN | S-004, S-005 |  |
| deadline-bounded candidate evaluation and pick | absent | MISSING |  |  |
| deadline-bounded candidate evaluation and pick | stale / expiry / deadline | DEFINED | S-005 |  |
| deadline-bounded candidate evaluation and pick | retry / duplicate / replay | THIN | S-004, S-005 |  |
| deadline-bounded candidate evaluation and pick | dependency-failure | MISSING |  |  |
| deadline-bounded candidate evaluation and pick | concurrent | MISSING |  |  |
| projection walk that yields J | normal | DEFINED | S-009 |  |
| projection walk that yields J | boundary | THIN | S-022, S-021 |  |
| projection walk that yields J | degenerate | MISSING |  |  |
| projection walk that yields J | conflicting | THIN | S-009, S-015 |  |
| projection walk that yields J | absent | MISSING |  |  |
| projection walk that yields J | stale / expiry / deadline | MISSING |  |  |
| projection walk that yields J | retry / duplicate / replay | THIN | S-004 |  |
| projection walk that yields J | dependency-failure | MISSING |  |  |
| projection walk that yields J | concurrent | MISSING |  |  |
| acquire-during-walk decision | normal | DEFINED | S-010 |  |
| acquire-during-walk decision | boundary | DEFINED | S-010 |  |
| acquire-during-walk decision | degenerate | MISSING |  |  |
| acquire-during-walk decision | conflicting | MISSING |  |  |
| acquire-during-walk decision | absent | MISSING |  |  |
| acquire-during-walk decision | stale / expiry / deadline | MISSING |  |  |
| acquire-during-walk decision | retry / duplicate / replay | MISSING |  |  |
| acquire-during-walk decision | dependency-failure | MISSING |  |  |
| acquire-during-walk decision | concurrent | MISSING |  |  |
| route-set re-derivation at each level crossed | normal | DEFINED | S-011 |  |
| route-set re-derivation at each level crossed | boundary | DEFINED | S-011 |  |
| route-set re-derivation at each level crossed | degenerate | MISSING |  |  |
| route-set re-derivation at each level crossed | conflicting | MISSING |  |  |
| route-set re-derivation at each level crossed | absent | MISSING |  |  |
| route-set re-derivation at each level crossed | stale / expiry / deadline | DEFINED | S-011, S-004 |  |
| route-set re-derivation at each level crossed | retry / duplicate / replay | THIN | S-004 |  |
| route-set re-derivation at each level crossed | dependency-failure | MISSING |  |  |
| route-set re-derivation at each level crossed | concurrent | MISSING |  |  |
| re-fit and credit after an acquisition | normal | DEFINED | S-012 |  |
| re-fit and credit after an acquisition | boundary | DEFINED | S-012 |  |
| re-fit and credit after an acquisition | degenerate | DEFINED | S-012 |  |
| re-fit and credit after an acquisition | conflicting | MISSING |  |  |
| re-fit and credit after an acquisition | absent | MISSING |  |  |
| re-fit and credit after an acquisition | stale / expiry / deadline | MISSING |  |  |
| re-fit and credit after an acquisition | retry / duplicate / replay | MISSING |  |  |
| re-fit and credit after an acquisition | dependency-failure | MISSING |  |  |
| re-fit and credit after an acquisition | concurrent | MISSING |  |  |
| consumable credited as a rate change vs a depleting stock | normal | DEFINED | S-013 |  |
| consumable credited as a rate change vs a depleting stock | boundary | THIN | S-013 |  |
| consumable credited as a rate change vs a depleting stock | degenerate | THIN | S-013 |  |
| consumable credited as a rate change vs a depleting stock | conflicting | MISSING |  |  |
| consumable credited as a rate change vs a depleting stock | absent | THIN | S-013 |  |
| consumable credited as a rate change vs a depleting stock | stale / expiry / deadline | MISSING |  |  |
| consumable credited as a rate change vs a depleting stock | retry / duplicate / replay | MISSING |  |  |
| consumable credited as a rate change vs a depleting stock | dependency-failure | MISSING |  |  |
| consumable credited as a rate change vs a depleting stock | concurrent | MISSING |  |  |
| route price as expected cost (learned vs published) | normal | DEFINED | S-014 |  |
| route price as expected cost (learned vs published) | boundary | THIN | S-014 |  |
| route price as expected cost (learned vs published) | degenerate | DEFINED | S-014 |  |
| route price as expected cost (learned vs published) | conflicting | THIN | S-014 |  |
| route price as expected cost (learned vs published) | absent | MISSING |  |  |
| route price as expected cost (learned vs published) | stale / expiry / deadline | MISSING |  |  |
| route price as expected cost (learned vs published) | retry / duplicate / replay | THIN | S-004 |  |
| route price as expected cost (learned vs published) | dependency-failure | MISSING |  |  |
| route price as expected cost (learned vs published) | concurrent | MISSING |  |  |
| pricing a course the state makes uncompletable | normal | DEFINED | S-015 |  |
| pricing a course the state makes uncompletable | boundary | MISSING |  |  |
| pricing a course the state makes uncompletable | degenerate | MISSING |  |  |
| pricing a course the state makes uncompletable | conflicting | THIN | S-005, S-015 |  |
| pricing a course the state makes uncompletable | absent | MISSING |  |  |
| pricing a course the state makes uncompletable | stale / expiry / deadline | MISSING |  |  |
| pricing a course the state makes uncompletable | retry / duplicate / replay | THIN | S-004 |  |
| pricing a course the state makes uncompletable | dependency-failure | MISSING |  |  |
| pricing a course the state makes uncompletable | concurrent | MISSING |  |  |
| guard precedence over the priced comparison | normal | DEFINED | S-017 |  |
| guard precedence over the priced comparison | boundary | MISSING |  |  |
| guard precedence over the priced comparison | degenerate | MISSING |  |  |
| guard precedence over the priced comparison | conflicting | MISSING |  |  |
| guard precedence over the priced comparison | absent | MISSING |  |  |
| guard precedence over the priced comparison | stale / expiry / deadline | MISSING |  |  |
| guard precedence over the priced comparison | retry / duplicate / replay | MISSING |  |  |
| guard precedence over the priced comparison | dependency-failure | MISSING |  |  |
| guard precedence over the priced comparison | concurrent | MISSING |  |  |
| task accept/decline evaluation | normal | DEFINED | S-018, S-019 |  |
| task accept/decline evaluation | boundary | DEFINED | S-019 |  |
| task accept/decline evaluation | degenerate | MISSING |  |  |
| task accept/decline evaluation | conflicting | MISSING |  |  |
| task accept/decline evaluation | absent | THIN | S-018 |  |
| task accept/decline evaluation | stale / expiry / deadline | MISSING |  |  |
| task accept/decline evaluation | retry / duplicate / replay | MISSING |  |  |
| task accept/decline evaluation | dependency-failure | MISSING |  |  |
| task accept/decline evaluation | concurrent | MISSING |  |  |
| task-currency route pricing | normal | DEFINED | S-020, S-018 |  |
| task-currency route pricing | boundary | THIN | S-020 |  |
| task-currency route pricing | degenerate | MISSING |  |  |
| task-currency route pricing | conflicting | MISSING |  |  |
| task-currency route pricing | absent | MISSING |  |  |
| task-currency route pricing | stale / expiry / deadline | MISSING |  |  |
| task-currency route pricing | retry / duplicate / replay | MISSING |  |  |
| task-currency route pricing | dependency-failure | MISSING |  |  |
| task-currency route pricing | concurrent | MISSING |  |  |
| horizon selection and behaviour at its extremes | normal | THIN | S-021, S-022 |  |
| horizon selection and behaviour at its extremes | boundary | THIN | S-022 |  |
| horizon selection and behaviour at its extremes | degenerate | MISSING |  |  |
| horizon selection and behaviour at its extremes | conflicting | DEFINED | S-021 |  |
| horizon selection and behaviour at its extremes | absent | MISSING |  |  |
| horizon selection and behaviour at its extremes | stale / expiry / deadline | MISSING |  |  |
| horizon selection and behaviour at its extremes | retry / duplicate / replay | THIN | S-004 |  |
| horizon selection and behaviour at its extremes | dependency-failure | MISSING |  |  |
| horizon selection and behaviour at its extremes | concurrent | MISSING |  |  |
| totality-witness (last-resort means) selection | normal | DEFINED | S-023 |  |
| totality-witness (last-resort means) selection | boundary | THIN | S-023 |  |
| totality-witness (last-resort means) selection | degenerate | DEFINED | S-023 |  |
| totality-witness (last-resort means) selection | conflicting | MISSING |  |  |
| totality-witness (last-resort means) selection | absent | MISSING |  |  |
| totality-witness (last-resort means) selection | stale / expiry / deadline | MISSING |  |  |
| totality-witness (last-resort means) selection | retry / duplicate / replay | MISSING |  |  |
| totality-witness (last-resort means) selection | dependency-failure | MISSING |  |  |
| totality-witness (last-resort means) selection | concurrent | MISSING |  |  |
| determinism: same state, same choice | normal | DEFINED | S-004 |  |
| determinism: same state, same choice | boundary | THIN | S-004, S-002 |  |
| determinism: same state, same choice | degenerate | MISSING |  |  |
| determinism: same state, same choice | conflicting | THIN | S-004, S-005 |  |
| determinism: same state, same choice | absent | MISSING |  |  |
| determinism: same state, same choice | stale / expiry / deadline | MISSING |  |  |
| determinism: same state, same choice | retry / duplicate / replay | DEFINED | S-004 |  |
| determinism: same state, same choice | dependency-failure | MISSING |  |  |
| determinism: same state, same choice | concurrent | MISSING |  |  |
