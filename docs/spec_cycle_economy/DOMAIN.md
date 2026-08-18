# Domain model — the nouns the clauses quantify over

Phase 1's third grid found that the clauses in SPEC.md quantify over entities the
document never introduces: it says the walk "crosses levels" without defining a
level, "the same world state" without an equality relation, and "a condition that
must hold for the bot to continue operating" without naming HP. Twenty-two such
entities were absent entirely — no cell, not even a MISSING one.

This file defines them. **It states what each entity IS and which of its attributes
are observable. It does not state what the decision does with any of them** — that
is SPEC.md's job, and closing a decision here would blind Phase 2 to it.

Every game-mechanical fact below is quoted or derived from
<https://docs.artifactsmmo.com/concepts/>, which is authoritative. Facts about the
bot's own structures (plan, commitment, candidate) are marked **[impl]** and are
properties of the artifact under test, not of the game.

---

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
