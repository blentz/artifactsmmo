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

## Domain

The entities the clauses quantify over. **These are definitions, not rules**: each
says what an entity IS and which attributes are observable, and none says what the
decision does with it — that is the clauses' job, and closing a decision here would
hide it from adversarial review.

Phase 1 found twenty-two of these absent from this document entirely, which left
several clauses without subject matter. Every game-mechanical fact is quoted or
derived from the published documentation (sources at the end); facts about the
bot's own structures are marked **[impl]**.

## D-01 · Character

An account controls several characters; the fleet in question has five. A character
is the unit that acts: it occupies one tile, holds one inventory, wears one set of
equipment, holds at most the tasks D-11 allows, and issues actions against a budget
it shares with its siblings (D-04).

Observable attributes: name, combat level, XP toward the next combat level, HP,
maximum HP, position (D-08), the eight skill levels and their XP (D-02), inventory
(D-09), equipment (D-10), gold, and the task it holds (D-11).

## D-02 · Level, and which level

There are **nine independent levels** per character, and the spec's use of the bare
word "level" is ambiguous between them:

* the **combat level**, advanced by fighting;
* eight **skill levels** — woodcutting, mining, fishing, alchemy, weaponry,
  gearcrafting, jewelrycrafting, cooking — each advanced by its own actions.

All nine range 1–50 and share one levelling curve. Level 1 requires 150 XP.

A **level-up of the combat level** grants exactly two things: **+5 maximum HP** and
**+2 inventory item capacity**. A skill level-up grants no stats; it unlocks
recipes and resources gated on that skill.

## D-03 · XP, and the grey rule

XP is the quantity that advances a level (D-02). It is earned per action, by the
published formulas:

```
gathering  XP = Round((XP_base + (resource_level / player_level) × 8)
                      × level_penalty × wisdom_bonus)
crafting   XP = Round((XP_base + (item_level / player_level) × coefficient)
                      × skill_multiplier × level_penalty × wisdom_bonus)
```

`level_penalty` encodes the **grey rule**: a character ten or more levels above the
resource or item earns **0 XP**; at or below its level the factor is 1.0. Wisdom
contributes 0.1% more XP per point.

*The implementation's measured constants differ from these published ones in
places, and where they disagree the published formula is authoritative.*

## D-04 · Action, cooldown, and the action-rate budget

An **action** is one request that changes the world: move, fight, gather, craft,
recycle, rest, deposit, withdraw, equip, unequip, use, buy, sell, accept-task,
complete-task, and the rest of the published set. Every action returns a
**cooldown** — a duration during which the character can issue no further action.

Cooldowns are **not uniform**, and this is why S-001 makes cost a pair:

| action | published cooldown |
|---|---|
| movement | 5s per map |
| fight | 2s per turn, reduced by haste (1 point = 1% reduction) |
| rest | 1s per 1% of missing HP, rounded up, minimum 3s |
| gathering | 30s + resource level / 2, reduced by tools |
| crafting | 5s per item |
| recycling | 3s per item |
| deposit / withdraw / give | 3s per *different* item |
| use consumable | 3s flat, regardless of quantity |
| equip / unequip | 3s per entry |
| others | 3s |

Separately from cooldown, the account may issue only so many actions per unit of
wall clock — a limit imposed outside the game rules and shared by every character.
**[impl]** Measured: throughput 47.9 actions/hour against cooldowns that alone
would allow 122.5, so 60.9% of session wall clock is spent neither acting nor on
cooldown.

## D-05 · The no-op

A character that is on cooldown, or that has nothing to do, still exists and is
still asked what to do next. **[impl]** An option that issues no action is
therefore expressible, and is distinct from an option that issues one.

## D-06 · HP, defeat, and its cost

HP is the character's health pool; maximum HP grows +5 per combat level and by worn
equipment. A fight lasts at most **100 turns**; a fight not won by then is **lost**.

On defeat the character **returns to spawn (0,0) with 1 HP**. That is the concrete
event the survival constraint exists to prevent: it costs the HP, the position, and
the travel back.

Resting restores HP **to full**, at the D-04 cooldown.

## D-07 · Stats

Hit points; elemental attack (fire, water, earth, air); elemental damage %;
elemental resistance %; critical strike (1 point = 1% chance of ×1.5 damage);
initiative (turn order); threat (targeting); haste (1 point = 1% cooldown
reduction); wisdom (0.1% more XP per point); prospecting (0.1% more drops per
point).

Damage resolves as
`Round(base_attack × (1 + total_damage_bonus/100))` then
`Round(elemental_attack × (1 - resistance/100))`.

## D-08 · Position, map, and travel

The world is a 2D integer grid `(x, y)` on one of three **layers** — overworld,
underground, interior — so a tile is `(layer, x, y)`. A tile may hold a monster, a
raid, a resource node, a workshop, an NPC, a bank, the Grand Exchange, or a tasks
master.

Movement is an action costing **5s per map**; the **server** runs the pathfinding,
so a move of any distance is a single action. Tiles may be standard, blocked,
conditional (on stats, items, gold or achievements) or restricted.

## D-09 · Inventory, stacks, and capacity

An inventory has **20 slots**; each slot holds one item code with a quantity, so
stacks exist. Total items are capped — **100 at level 1, +2 per combat level** —
and an equipped bag raises it further.

**Two distinct limits therefore exist**: the number of distinct item codes (slots)
and the total item count. Either can bind.

## D-10 · Equipment slots

Sixteen named slots: weapon, shield, helmet, body_armor, leg_armor, boots, ring1,
ring2, amulet, artifact1, artifact2, artifact3, utility1, utility2, bag, rune.

Rings, artifacts and utilities are **duplicate slots** — several slots accept the
same kind of item — but **each artifact slot must hold a different artifact, and
each utility slot a different utility**. A single item occupies exactly one slot.
Utility slots carry a quantity of 1–100; other slots do not.

An item may carry **equip conditions** — comparisons against character stats,
including combat level and skill levels. Unequipping requires inventory room and
enough HP to survive the stat loss.

## D-11 · Task

A task is issued by a tasks master on a tile. Two types: **monsters** (kill N of a
monster) and **items** (deliver N of an item). A task has a code, a total, and a
progress count.

Completion pays gold and **task coins**, by type and character level:

| type | level band | gold | coins |
|---|---|---|---|
| items | 1–14 / 15–29 / 30–40 / 41+ | 150 / 250 / 350 / 300 | 2 / 3 / 4 / 4 |
| monsters | 1–14 / 15–29 / 30+ | 200 / 300 / 500 | 3 / 4 / 5 |

**Cancelling a task costs 1 task coin.** Exchanging **6 task coins** yields a random
reward.

*The documentation states no expiry for a task, and does not state whether a
character may hold more than one. Both are left open here rather than assumed.*

## D-12 · Item, recipe, and route

An item has a code, a type, a level, and stats. An item may be obtainable by
gathering a resource node, by crafting from a recipe at a workshop, by a monster
drop, by purchase from an NPC or the Grand Exchange, by withdrawal from the bank,
or by **recycling** an equipment item back into materials.

A recipe names a skill and a required level of it (D-02), and its inputs.

A **route** is one such way of obtaining one unit, together with what it consumes.

## D-13 · Drop, and the uncontrolled outcome

A monster drop has a rate expressed as a 1-in-N chance, with a minimum and maximum
quantity. Prospecting raises drop chance by 0.1% per point. Whether a given fight
yields the drop is not under the character's control, and neither is whether a
fight is won.

## D-14 · Currency

Gold is held by a character and by the bank. **Task coins** are an item earned by
completing tasks and spent at a tasks master. Other item codes are accepted as
payment by particular NPCs. A currency is therefore an item that some route
consumes as an input.

## D-15 · Bank

One bank, shared by every character on the account: **50 slots** at the start, +20
per expansion. The first expansion costs **3,500 gold** and the price doubles each
time, capped at 448,000. Deposits and withdrawals cost 3s per *different* item.

Because it is shared, one character's withdrawal changes what another can withdraw.

## D-16 · Time-limited content

Events and raids exist only within a window and place content on tiles for its
duration. A route that depends on such content is available only while the window
is open.

## D-17 · Grand Exchange

A player-to-player market. An order has a counterparty, a price and a lifetime, and
may be filled or cancelled by someone other than this character. Its price is set
by other agents rather than by the game.

## D-18 · Plan and commitment **[impl]**

A **plan** is an ordered sequence of actions the bot has decided to execute. A
**commitment** is the plan's remaining, not-yet-executed actions.

## D-19 · Candidate and the generator **[impl]**

A **candidate** is one option offered to the decision: a course of action to be
priced. The **generator** is whatever enumerates them for a given state. Candidates
are offered in some order.

## D-20 · Means, guard, and the band **[impl]**

A **means** is a candidate that advances something the bot wants. A **guard** is a
candidate that must run for the bot to keep operating. The bot's current
implementation places candidates in ordered **bands** — guard, collect, objective
step, fallback step, discretionary — and selects the first that fires.

## D-21 · World state, and its identity **[impl]**

The **world state** is the character's observable attributes (D-01) together with
the bank (D-15), the tiles' contents (D-08), and the live events and raids (D-16).

*What makes two world states "the same" — which attributes participate in the
equality S-004 rests on — is **not** decided here. S-004 is unfalsifiable until it
is, and that is the open question Phase 1 raised.*

## D-22 · Observation store **[impl]**

A durable record of what past actions actually yielded: XP per action, drop rates
per monster, cycles per goal. An observation has a sample count and an age. It may
disagree with the published formula, and it may be absent.

---

---

## Clauses

### S-001 · Cost is the ordered pair (cycles, seconds)

Every cost, benefit and price in this specification is a pair: the count of
executed planner actions, and the wall-clock cooldown those actions incur. A
quantity expressed in any other unit is converted into both components before it
participates in a comparison. Neither component may be dropped: they are not
proportional, because an action's cooldown depends on its type and its arguments.

### S-002 · Comparisons rank on cycles; seconds are a constraint, not a second key

Two options are compared on their cycle counts. The seconds component does not
order options; it bounds them — an option whose seconds exceed a stated budget is
unavailable, and among available options seconds do not break a cycle tie.

*Ranking on seconds as a secondary key would reintroduce the lexicographic
ordering this specification exists to remove. Nothing here fixes what the budget
is, nor which budgets exist.*

### S-003 · The scarce resource is the action rate, and it is named here

The resource that binds the bot's progress is the number of actions it may issue
per unit of wall clock, imposed from outside and shared by every character. That
budget is why cycles rank (S-002). A clause that treats seconds as scarce, or that
prices an option as though issuing an action were free, contradicts this one.

*This states which resource is scarce. It does not fix the budget's value, how it
is measured, or how it is divided among characters.*

### S-004 · The same state yields the same choice

Two evaluations of the same world state return the same choice. Nothing carried
between evaluations — a cache, an accumulated counter, an ordering that depends on
when a candidate was first seen — may change the answer for a state that has not
changed.

*Σ declares idempotence observable. Without this clause nothing forbids the chosen
course flipping every cycle on an unchanged world.*

### S-005 · A candidate is compared only when fully evaluated

The decision has a deadline. When it expires, the choice is the best candidate
whose evaluation COMPLETED; a candidate whose evaluation was cut short is
discarded, never ranked against a complete one.

*A truncated evaluation compared against a complete one is the same defect as
ranking a course the objective declined to price. Because a short deadline may
admit only the candidates evaluated first, the ORDER of evaluation decides which
are seen at all — and this clause does not fix that order.*

### S-006 · Cost is marginal against committed work

The cost of an option is the number of cycles it adds to the cycles already
committed for the current horizon. Cycles that would be spent regardless of whether
the option is taken do not count toward its cost.

### S-007 · The objective is computed for one character; shared stock is a route

`J` is computed for a single character. Stock held by a sibling or by the shared
bank is not that character's holding; it is reachable only through a route with a
capacity, priced like any other route. No clause here computes a value for the
account as a whole.

*What happens when two characters price the same limited stock in the same tick is
not decided here. The coordination protocol is not under test.*

### S-008 · Committed work is the remaining actions of the plan in flight

The committed work that S-006 measures against is the set of actions still to be
executed in the plan the bot is currently carrying out. A commitment comes into
existence when a plan is adopted, and an action discharges its part of the
commitment only by succeeding. An action that executes and fails discharges
nothing, and forces the choice to be made again.

*A course the objective favours but has not planned is therefore NOT committed, and
work overlapping it is not free. This is a deliberate narrowing.*

### S-009 · The objective's value is the cycle total of one projection walk

`J` for a candidate course of action is the total cycles of a single projection walk
from the current state to the horizon under that course. It is not a sum of a
separately-computed cost term and a separately-computed benefit term.

### S-010 · The walk may spend cycles to acquire, and does so when it repays

At each level the projection walk crosses, it may pay a route's cost to obtain and
equip an item; subsequent levels are then projected with that item held. It takes
such an acquisition when the cycles paid are fewer than the cycles thereby saved
over the remainder of the walk.

### S-011 · The route set is re-derived at each level the walk crosses

The routes available to the walk are recomputed at every level it reaches, so a
route whose availability depends on a level the walk is about to cross becomes
available at that level and not before.

### S-012 · An acquisition is re-fitted, never accumulated

After an acquisition the walk re-derives which items the character wears from
everything it now holds. An acquisition that displaces something already worn is
credited only with the difference it makes, and an acquisition the character would
not wear is credited with nothing.

### S-013 · A consumed item is credited as a rate change against a depleting stock

An acquired item that is spent rather than worn is credited with the change it
makes to the projected rate for as long as its stock lasts. The walk debits that
stock as it crosses levels, and the credit ends when the stock does.

*This clause does not fix how much stock a level consumes.*

### S-014 · A route's price is its expected cost

Where a route's cycle cost depends on an outcome the character does not control,
its price is the expected cost over that outcome, taken from observation where
enough has been observed and from the published rate otherwise.

*Nothing here bounds the spread around that expectation, nor decides what "enough"
is.*

### S-015 · Inability to complete is expressed as cost, not as a rank band

Where a course of action cannot be completed from the current state, it is priced
at the cycles required to make it completable. No distinguished value stands in for
"cannot", and no ordering key exists whose purpose is to rank options the objective
declined to price.

*This clause governs courses the state makes unavailable. It does not decide what
is reported for content the game data contains no route to at all.*

### S-016 · A means competes on the same quantity as the objective step

An available means and the objective step are compared on marginal cycles (S-006)
against cycles saved or progress unlocked over the horizon. Neither wins by virtue
of the band or position it occupies.

### S-017 · Survival constraints are not investments and are not compared

A guard — a condition on the state that must hold for the bot to continue
operating — takes precedence over every priced comparison and is not itself priced.

### S-018 · A task's cost is the work it demands that is not already committed

The marginal cost (S-006) of accepting a task is the cycles required by its demanded
work that the bot has not already committed to for other reasons. Its value is the
task's reward together with the value of that demanded work.

### S-019 · A task with no overlap is taken only for its reward

Where a task's demanded work overlaps no committed work, the task is taken only when
its reward is itself required by a course of action the objective has selected.

### S-020 · Earning a task currency is a route, priced at the task's marginal cost

A currency obtainable by completing tasks is a source of that currency, on the same
footing as the other sources. Its per-unit price is derived from the marginal cost
(S-018) of the task that yields it.

### S-021 · One horizon governs every comparison

Every comparison in this specification is evaluated against a single horizon. No
part of the decision logic introduces a second horizon of its own.

### S-022 · The horizon's behaviour at its extremes is stated, not inherited

Whatever quantity bounds the horizon, the specification states what the comparison
does when that bound is near and when it is distant.

*This clause requires the statement; it does not fix which quantity bounds the
horizon, nor what the behaviour at either extreme should be.*

### S-023 · A totality witness is exempt from comparison

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
| S-001 | Cooldowns are not flat, and the game docs say so: gathering `30s + resource level/2`, movement `5s per tile`, fight `2s per turn`, rest `1s per 5 HP (min 3s)`, crafting `5s per item`, others `3s`. Measured over 63,310 cycles the medians span **0.0s to 41.8s** — rest 41.8, gather 29.8, fight 25.8, LevelSkill 13.7, craft 4.8, equip/delete 2.8, withdraw/deposit ~0. A single scalar "cycle" hides a ~50x spread. |
| S-001 | The projection was denominated in seconds until 2026-08-07 and ran ~80x high; four separate defects in this project trace to a unit confusion. Dropping EITHER component has already cost a defect: seconds-as-cycles (the 80x) and cycles-as-seconds (`rest_cost_pure`). |
| S-002 | Seconds are not what binds. Inside sessions: 132.5 h wall clock against 51.8 h of cooldown owed (39.1%); throughput 47.9 cycles/hour where cooldowns alone would allow 122.5. The remaining 60.9% is the per-IP rate budget, planning and idle — a budget denominated in ACTIONS, which is why cycles rank and seconds only bound. |
| S-002 | Rest is where the two components diverge most: 22% of cycles and 39.8% of all cooldown seconds. |
| S-006 | Five iron pieces cost 2,933 cycles priced apart and 936 as one plan — 68% of the total was one shared prerequisite charged five times. |
| S-009, S-015 | `J` finite for no candidate in 10,716 cycles; the ranking was settled every cycle by the fallback key, where the zero-cost trunk won 8,769 of 8,769 ties. |
| S-010, S-022 | With the objective evaluated against the next ten-level milestone, benefit spreads 1,086–1,182 cycles across 11–12 candidates at four levels of headroom. |
| S-015 | Skill-gated crafts priced at `10^6` on every character; after pricing the grind they price at 556–623, and the affected items became rankable. |
| S-016 | An objective step was present in 14,064 of 14,064 traced cycles; the band below it took 133 of 63,310 cycles (0.21%), and 19 goal/action classes are unreachable in consequence. |
| S-018, S-019 | `means_worth._task_need_overlap` already computes a task's overlap with live objective needs, then discards it through a boolean threshold. |
| S-020 | `is_task_earnable('tasks_coin')` returns true while `route_options('tasks_coin')` returns empty and the price walk charges `10^6`; the item that funding targets prices at 1,000,010. |
| S-021 | Four unrelated horizon constants exist in four modules; the objective reads none of them. |
| S-022 | At one level of headroom the benefit spread is exactly 0; at fifty levels nothing arrives at all. |
| S-023 | `Formal.Liveness.NoDeadlockV2.productionLadder_total` is proved via the unconditional last-resort means. |
| Σ dim 8 | A decision costs 6–34 s live against a planning window floored at 15 s. A candidate evaluation costs ~235 ms, the same order as a whole level of the walk; ~27% can be excluded by a cheap static predicate. |

*Cooldown formulas are quoted from the game documentation, which is authoritative
for game mechanics: <https://docs.artifactsmmo.com/concepts/actions/>. The
changelog records rest moving from `1s per 5 missing HP` to `1s per 1% missing HP`
(min 3s); the implementation must read the published figure rather than either
constant.*

## Sources

All game-mechanical facts above:
<https://docs.artifactsmmo.com/concepts/> — specifically
[actions](https://docs.artifactsmmo.com/concepts/actions/),
[stats_and_fights](https://docs.artifactsmmo.com/concepts/stats_and_fights/),
[skills](https://docs.artifactsmmo.com/concepts/skills/),
[equipment](https://docs.artifactsmmo.com/concepts/equipment/),
[tasks](https://docs.artifactsmmo.com/concepts/tasks/),
[inventory_and_bank](https://docs.artifactsmmo.com/concepts/inventory_and_bank/),
[maps_and_movement](https://docs.artifactsmmo.com/concepts/maps_and_movement/),
[resting_and_using_items](https://docs.artifactsmmo.com/concepts/resting_and_using_items/).

**One discrepancy to note:** the actions page's summary table gives rest as
"1s per 5 HP (min 3s)" while the resting page and the changelog give
"1s per 1% of missing HP, rounded up, min 3s". The latter is the current rule and
the table is stale. An implementation must read the cooldown the server returns
rather than either constant.

## Residuals

* Whether the per-decision compute can be brought inside the planning window is
  unproven. If it cannot, S-009/S-010's walk-shaped objective is not affordable and
  the design must change rather than the budget.
* The task-reward table holds no rows, so S-018's reward term has no observations
  behind it yet.
* S-017 exempts guards by assertion. Nobody has measured whether a guard ever fires
  where a priced option would have paid more.
* The deep-fan-out recipe that once caused a search blow-up at this seam is
  currently unpriced, so no cost figure here covers it.
* This document does not decide what is reported for content with no route in the
  game data at all (see S-015's note), nor which quantity bounds the horizon (S-022).
* S-007 leaves the two-characters-one-stock race to the coordination protocol,
  which is not under test. A witness about it belongs there, not here.
* S-008 narrows committed work to the plan in flight, so a course the objective
  favours but has not planned confers no overlap. Chosen deliberately; the cost is
  that a task aligning with a not-yet-planned grind reads as full price.
* S-014 fixes no bound on the spread around an expected cost, and does not define
  how much observation is "enough" to prefer a learned rate to the published one.
* A short deadline can mean only the first candidates are ever evaluated
  (S-005), and no clause fixes the order in which candidates are offered.
* A commitment survives a failed action, so an action that fails forever is
  re-committed forever; nothing here stops retrying.
* The walk holds acquired items with no notion of inventory slot capacity, so a
  walk that acquires several items may project a holding the character cannot
  carry, and the cycles of making room are unpriced.
* Gold and other spendable balances are not modelled as a scarce budget: a route
  with a purchase price is priced like any other even when the character cannot
  pay.
