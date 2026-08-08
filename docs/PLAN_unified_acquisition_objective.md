# PLAN — Unified acquisition objective

Written 2026-08-08 against local `main` @ `5a2d1b8d`.

## Status

| increment | state | commit |
|---|---|---|
| 0 — pin the defect | **DONE**, gate green | `ae96f25f` |
| 1 — cost core (AND/OR walk, six routes) | **DONE, INERT**, gate green | `384a46d3` |
| 1 — pricer over `obtain_sources` | **DONE, INERT**, gate green | `f1ee73c6` |
| 1b — `skill_grind_cycles` pure core | **DONE** | `ce49405f` |
| 1b — gated-craft route in the pricer | **DONE, INERT** | `cfcd8596` |
| 2 — switch `J`'s `acquire_cost` | **DONE, LIVE**, gate green | `b4f21cbb` |
| 3 — project wisdom | **DONE**, gate green | `a1e49432` |
| 4 — prospecting through the drop cost | **DONE**, gate green | `97643db3` |
| 5 — retire `bid_vs_craft`'s duplicate | **DESIGNED, NOT LANDED** — see below | patch in `docs/` |

### Increment 5 — designed, deliberately not landed

**The finding is better than the plan's version of it.** The plan said "convert
to seconds at the boundary if the GE horizon genuinely needs wall-clock". It does
not. Read `ge_order_config`:

```python
TTL_CYCLES = 20
AVG_CYCLE_SECONDS = 30.0
BID_FILL_HORIZON_SECONDS = TTL_CYCLES * AVG_CYCLE_SECONDS
```

The horizon is natively **20 CYCLES**. It was multiplied into seconds only so it
could be compared against `estimate_craft_seconds`, whose own per-kind constants
(fight 10, gather 6, craft 5) were themselves approximating how long an ACTION
takes. Two conversions, in opposite directions, around a comparison that is
really *"is my craft longer than 20 cycles?"*. Both cancel, and `AVG_CYCLE_SECONDS`
— a tuning constant that existed solely to bridge two units neither side wanted —
disappears with them.

So increment 5 is not "unify with a conversion". It is **delete both conversions
and compare in cycles**, with `acquisition_actions` supplying the estimate. That
retires the second acquisition cost model outright.

**Why it is not landed.** The production change is ~40 lines and was written and
type-checked clean (`docs/increment5-bid-vs-craft.patch.txt`). Its two test
modules are the obstacle: `test_bid_vs_craft.py` and `test_goals_post_buy_bid.py`
drive bare `GameData()` stubs with two attributes assigned directly, which the
route-aware model cannot run on — `obtain_sources` needs workshop locations,
resource tiles, monster tiles and winnability, so against a stub every item is
unobtainable and `should_bid` returns True unconditionally. Both suites need
rebuilding on the committed fixture bundle first.

**A behaviour change to check when it does land:** `should_bid` becomes
STATE-AWARE. An item whose routes are all currently unservable prices as
unobtainable, hence "slower than the horizon", hence BID. That is arguably right
— if you cannot make it now, buying it is the point — but it is a new coupling
between the bid gate and world state, and it should be asserted deliberately
rather than discovered.

### Increment 2 is LIVE — what it changed, and what is still unverified

`J` now prices acquisition over all six routes. Measured on
`l12_deep_chain_grind`: `iron_sword` 65 → **96** (venue hops plus the
weaponcrafting gate), `copper_dagger` 62 → **70**, `feather` 2 → **14**.

**The suite passed identically before and after the switch.** Not one test
changed, because nothing in it was sensitive to `acquire_cost` at all. A test now
compares `gear_candidate`'s figure against what `min_plan_length` would have said
and fails if they agree, so the switch cannot silently revert.

**A regression the suite could not see, found by activating and looking.** With
the gate priced but no observed grind rate, the gated route was withheld and the
item read as UNOBTAINABLE — so every jewelry item priced in the millions for a
character who had never crafted jewelry. That is an OVER-estimate, the one
direction the soundness contract forbids, because these bounds PRUNE. An unknown
grind now costs ZERO; the unknown positive term is omitted. Two tests written an
hour earlier had been pinning the wrong behaviour and were rewritten.

**STILL UNVERIFIED ON A LIVE RUN.** Every figure above is from the committed
fixture. Before this drives a real character it needs a `plan <char>` against
live state showing changed `acquire_cost` values in the descent.

### The former blocker — what increment 2 had to check

`cfcd8596` prices the skill gate, so `iron_sword` at weaponcrafting 5 costs the
grind plus the chain rather than reading as unobtainable. Switching `J` is
therefore possible; what remains is to establish it is *safe*, and the honest
list of what could still go wrong is short and specific:

1. **`store=None` callers.** Every existing caller keeps today's behaviour
   because `store` defaults to None — which also means a caller that forgets to
   thread the store gets the WALL back, silently. `J`'s switch must pass it, and
   a test must fail if it stops.
2. **The unobtainable bound is an over-estimate risk.** Every route being
   state-aware means a candidate can price at `UNOBTAINABLE_PER_UNIT` this cycle
   and finitely the next. `J` compares candidates *within* one cycle, so this is
   sound there — but the ranking will be visibly jumpy across cycles, and that
   must not be mistaken for a bug when the trace is read.
3. **No live-run verification exists for any of this.** Green tests are not
   runtime activation. The switch needs a real `plan <char>` showing a changed
   `acquire_cost` in the descent.

### THE ORIGINAL BLOCKER, measured — kept for the record

The pricer works, and running it against the old model on
`l12_deep_chain_grind` says **do not switch `J` yet**:

| item | `min_plan_length` | route-aware | why |
|---|---|---|---|
| `copper_ore` | 2 | 1 | already held; gather route priced |
| `feather` | 2 | **14** | drop farm actually priced |
| `wolf_hair` | 2 | unobtainable | wolf not winnable — correct |
| `backpack` | 2 | unobtainable | every fixture vendor is an EVENT npc — correct |
| `iron_sword` | 65 | **unobtainable** | **weaponcrafting 5 vs gate 10 — WRONG** |

The sword is the blocker. The workshop is known; `_craft_sources` excludes the
route on the skill gate alone. Switching `J` today would price most gear as
unreachable and collapse the ranking — which is exactly why the core and the
pricer both landed INERT rather than wired.

### The seam question 1b must answer explicitly

`obtain_sources` answers **readiness** ("what can the executor serve right
now?"), and a skill-gated craft genuinely is *not* servable right now. The cost
model asks a different question — **what would it cost to obtain this** — whose
answer may include making a route ready. So the gated-craft route belongs in the
pricer, not in `obtain_sources`, and that is a real distinction rather than a
convenient one.

It is also how a second route model creeps back in, which this epic exists to
prevent. So the wiring commit must carry a census asserting the pricer's route
set is a strict SUPERSET of `obtain_sources`', with the gated-craft rows as the
only permitted difference — the same shape as `test_obtain_graph_agreement`,
which already pins `obtain_sources` against `RequirementGraph.leaves`.

## The thesis

> An item whose value `J` cannot price in cycles-to-50 can never justify the GEAR
> branch, regardless of how cheap it is.

The unified objective `J = acquire_cost + cycles_to_fifty` is sound, and its
currency (ACTIONS) is the right one. The problem is that only **two of the eight
quadrants it needs are actually measured.** The rest return plausible numbers.

Each game mechanic — fight, gather, craft, NPC-buy, drop-farm, task, bank,
recycle — was modelled by a separate epic, in its own units, for its own consumer.
`J` sits on top and adds two of those models together as if they covered the
board. They do not. The result is not a wrong weighting that could be tuned; it
is a set of terms that are structurally absent, and absence always reads as zero.

## Measured evidence

Everything below was measured on `5a2d1b8d` against the live game-data cache on
2026-08-08. No claim here is inferred from reading alone.

### Cost side — `min_plan_length` models three routes out of six

`ai/min_plan_length.py` is `ceil_gathers(min_gathers) + min_crafts + (1 if equip)`.
`min_gathers` treats **any item without a recipe as a raw gatherable costing one
gather.** It has no notion of vendors, monsters, currency, or the bank.

| item | real route | `acquire_cost` says |
|---|---|---|
| `copper_ore` | gather | **2** — correct |
| `iron_sword` | 3-deep craft chain | **65** — correct |
| `adventurer_vest` | craft chain | **55** — correct |
| `life_ring` | craft chain | **90** — correct |
| `wolf_hair` | kill wolves until it drops | **2** |
| `lich_race_medal` | buy for **100 `event_ticket`** | **2** |

A 100-event-ticket purchase and an indefinite drop-farm are each priced at two
actions — *cheaper than gathering two copper ore* — because both items lack a
recipe and `min_gathers` calls anything without a recipe raw.

The bias runs in the direction nobody would guess: the cost model does not make
buy-and-drop items look expensive, it makes them look **free**. `J` is not
under-valuing the medal on cost. It cannot see the cost at all.

### There is already a second, incompatible acquisition cost model

`ai/bid_vs_craft.estimate_craft_seconds` prices the same question — how much work
to obtain this item — and it **does** know about drop-farms:

```python
expected_kills = min(_expected_kills(c) for c in candidates)
total += float(expected_kills) * _FIGHT_SECONDS * needed
```

`ai/monster_drop_selection._expected_kills` is `rate / avg_quantity`, exact
`Fraction`, proved in `formal/Formal/MonsterDropSelection.lean`. The knowledge
`min_plan_length` lacks is not missing from the codebase. It is sitting in
another module, **denominated in SECONDS**, feeding a different consumer.

So the bot holds two acquisition cost models:

| | unit | gather | craft | drop | buy | withdraw | recycle |
|---|---|---|---|---|---|---|---|
| `min_plan_length` (feeds `J`) | actions | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `estimate_craft_seconds` (feeds GE bidding) | seconds | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |

Neither is complete, they disagree on coverage, and they cannot be compared
because they are in different units. This is the same unit-error class the
project has now hit four times (`mats_missing`, `DEFAULT_FIGHT_CYCLES`,
`cycles_to_fifty`, `cheapest_path_to_level`), and it is why the fix belongs at
the measure, not at the cases.

Meanwhile `ai/obtain_sources.py` — written by the one-obtain-model epic
explicitly to be *"THE model of how an item can be obtained — the one source of
truth every producer of a plan must consume"* — enumerates all six routes with
yields and capacities, and **no cost model consumes it.** The seam exists. It was
never connected to pricing.

### Benefit side — the projection can see seven gear stats out of twelve

`J`'s entire benefit channel is `cheapest_path_to_level`, which reads gear only
through `is_winnable` and `expected_damage_per_fight`. Both of those go through
`ai/equipment/projection.project_loadout_stats`, whose `ProjectedStats` carries
exactly seven fields:

`attack`, `dmg`, `dmg_elements`, `resistance`, `critical_strike`, `initiative`,
`max_hp`.

`ItemStats` defines five more that gear actually grants, and **none of them
survive projection**:

| stat | what it does | visible to `J`? |
|---|---|---|
| `wisdom` | +1% xp per 10 points | **no** — see below |
| `prospecting` | +1% drop chance per 10 points | no |
| `haste` | −% fight cooldown | no *(correctly — see anti-goals)* |
| `inventory_space` | +bag slots | no |
| `lifesteal` | heal on crit | no |

`wisdom` is the sharpest case, because it is the one efficiency stat that is
**already in the objective's own formula**:

```python
wisdom = state.wisdom                      # projections.py:259
...
xp_per_cycle = game_data.xp_per_kill(code, sim_level, wisdom=wisdom) / monster_cycles
```

`state.wisdom` is the server-authoritative total for gear *currently worn*.
`branch_objective.gear_candidate` projects a candidate by placing it in
`state.inventory` and changes nothing else, and `project_loadout_stats` does not
carry `wisdom` anyway. So a wisdom item projects a benefit of exactly zero. The
channel is wired; the value never reaches it.

Measured directly, scenario `l12_deep_chain_grind` on the committed fixture
bundle, via `branch_objective.gear_candidate`:

| candidate | `reachable_level` | `acquire_cost` | item stats |
|---|---|---|---|
| trunk (baseline) | 17 | 0 | — |
| `wisdom_amulet` | **17** | 50 | `wisdom 60`, `hp_bonus 30` |
| `iron_sword` | **18** | 65 | `attack {earth: 24}` |

`wisdom 60` is **+6% xp on every kill from here to level 50** and it moves the
projection by nothing at all — the candidate is byte-identical to the trunk and
loses to it on `acquire_cost` alone. The sword, whose benefit runs through a
stat `ProjectedStats` happens to carry, moves the ceiling and wins. The
difference between the two is not their value to the character; it is whether
`ProjectedStats` has a field for the stat they grant.

### The artifact case, stated correctly

`lich_race_medal`: `dmg 5`, `initiative 100`, `prospecting 25`. It is **partially**
priceable — `dmg` and `initiative` do reach `ProjectedStats` — but +5% damage
changes actions-per-kill not at all (`FIGHT_ACTIONS_PER_KILL` is the constant
`1.0`) and only matters if it flips an `is_winnable` verdict. Its `prospecting 25`
is invisible, and prospecting's entire value is *reducing kills-per-drop* — a
cost in the DROP wing that `J` does not price in the first place.

So the medal loses to the trunk on `acquire_cost` 2 vs 0 after tying on
`reachable_level`, then `justifying_identities` demotes it. Every step is
behaving as specified. The specification is missing two terms.

## What "unify" means concretely

One acquisition cost function, over `obtain_sources`, in ACTIONS, consumed by
every producer that today rolls its own. One projection that carries every stat
an item grants. Nothing else changes: `J`'s definition, its bands, S-004/S-006/
S-013/S-014, and the proved core in `tiers/progression_choice.py` all stand.

The invariant to hold onto, and the reason this is worth doing carefully:

> **A route that is not priced is priced at zero, and zero always wins.**

## Increments

Each increment lands separately, gate-green, merged to local `main` before the
next starts. Ordered so that every step is independently verifiable on a live run
and none depends on a later one being right.

### 0 — Pin the defect (no behaviour change)

Tests asserting today's measured numbers, so every later increment has a baseline
that fails loudly rather than drifting: `lich_race_medal` = 2, `wolf_hair` = 2,
`iron_sword` = 65; `wisdom_amulet` in inventory changes `cheapest_path_to_level`
by zero cycles. These are **characterisation tests of a bug** and must be labelled
as such, so nobody later reads them as intended behaviour.

Also: an audit census asserting `ProjectedStats` covers every combat-or-efficiency
field of `ItemStats`, currently RED. A census that goes red when someone adds a
stat is the only thing that stops this recurring.

### 1 — `acquire_cost` over `obtain_sources` (the cost half)

New pure core, `ai/acquisition_cost.py`, replacing `min_plan_length` as `J`'s
`acquire_cost` only. The full target model is the table below; increment 1 lands
the shaded-in rows and leaves DROP/BUY at today's behaviour until increment 2,
so each step has a live-trace check that can actually attribute a change.

| route | actions | lands in |
|---|---|---|
| WITHDRAW | 1 move + 1 withdraw | **1** |
| GATHER | 1 move + `ceil(units / max_gather_yield)` (today's `ceil_gathers`) | **1** |
| RECYCLE | 1 move + 1 per unit destroyed | **1** |
| CRAFT | 1 move + 1 per craft node, recursing into inputs | **1** |
| CRAFT, gate unmet | + `cost_to_reach(skill, craft_level)` | **1b** |
| DROP | 1 move + `ceil(expected_kills) × cycles_per_kill` | **2** |
| BUY | 1 move + 1 purchase + cost of the currency, recursively | **2** |

Every route carries its venue hop per decision 2. The hop is a constant **1 per
distinct venue tile the plan must visit, and 0 when the character is already
standing there** — `MoveAction.is_applicable` is false on the current tile, so no
action is emitted and none may be counted. Distance never enters. Counting one
hop per distinct venue (rather than one per route application) keeps this a
sound LOWER bound: a plan that gathers twenty ore pays one move, not twenty.

Choosing the cheapest route per item makes this a **lower bound over a strictly
larger action model** than `min_plan_length`, so
`Formal.PlanModel.min_plan_length_le_plan`'s soundness argument extends rather
than being replaced — the new bound is ≤ the old one wherever both apply, and the
`is_plannable` gates that depend on the bound never over-prune. **This must be
re-proved, not asserted**; it is the load-bearing claim of the increment.

Consumers to migrate in the same increment or explicitly defer with a reason:
`goals/progression.py:187`, `goals/supply_bank.py:214`, `tiers/skill_grind_selection`.
Leaving `J` on a new model while the reachability gates stay on the old one
recreates the two-plan-producer trap this project has already paid for twice.

### 1b — `cost_to_reach(skill, level)`: a skill gate is a price, not a wall

Per decision 3. `obtain_sources._craft_sources` currently returns `[]` when the
crafting-skill gate is unmet, so the whole CRAFT route vanishes and the item
reads as unobtainable-by-craft. Replace the exclusion with a price:

```
cost_to_reach(skill, target) = Σ over levels  xp_to_next(level) / skill_xp_per_cycle(skill)
```

sourced from `LearningStore.skill_xp_per_cycle` (observed; already exists) and
falling back to the per-craft xp formula where there are no observations —
mirroring `cheapest_path_to_level`'s observed/formula split, including its hard
lesson that **both branches must yield the same unit** or the argmax silently
prefers whichever branch has data.

Watch for the grey-band interaction: gather/craft skill xp is zero at a level gap
of 11 (`project_grey_skill_xp_gate`, measured over 2464 gathers). A projection
that ignores it will price an out-of-band grind as free progress.

This is the increment that changes which items are reachable at all, so it needs
its own live-trace check before merge, separate from increment 1's.

### 2 — DROP and BUY: kills and currency are not free

`npc_purchases` returns `(npc, price, currency)`. `currency` is `gold` or an item
code (`event_ticket`, `tasks_coin`, …). The BUY cost is
`hop + 1 + acquisition_cost(currency, price)` — recursive, terminating because
currency chains bottom out at gold or at a gatherable/droppable. Gold prices at
the observed gold-per-cycle rate (decision 1).

DROP prices at `ceil(expected_kills) × cycles_per_kill`, reusing the proved
`_expected_kills` and the same `fight_loop_cost.cycles_per_kill` that
`cycles_to_fifty` uses — so a drop-farm and a level-grind are quoted in
identical whole-loop cycles. This is also what retires `bid_vs_craft`'s
seconds-denominated duplicate (increment 5).

Recursion needs a visited-set: a currency obtainable only by buying something
priced in that currency would otherwise loop. Terminate at a conservatively
LARGE bound, matching `min_gathers`' existing fuel-exhaustion convention, so
unreachability gates stay sound.

### 3 — Project every stat an item grants (the benefit half)

Extend `ProjectedStats` with `wisdom`, `prospecting`, `haste`, `inventory_space`,
`lifesteal`, and have `cheapest_path_to_level` read **projected** wisdom rather
than `state.wisdom`. On its own this makes `wisdom_amulet` pay in `J` — the
smallest possible change that proves the benefit channel now carries a
non-combat stat.

Expect this to change live rankings immediately and to need a trace check before
merge, per `feedback_verify_runtime_activation`.

### 4 — Prospecting pays through the drop cost

Once increment 1 prices DROP in kills and increment 3 projects `prospecting`,
prospecting reduces `expected_kills` and therefore reduces every drop-route
acquisition cost. The two halves meet with no new term: an artifact that makes
farming 2.5% cheaper is worth exactly 2.5% of the farming the plan contains.

This is the increment that makes the medal's own stat line legible to `J`, and it
is deliberately **last**, because it is worthless — and untestable — until both
halves exist.

### 5 — Retire the duplicate

Point `bid_vs_craft` at the unified cost, converting to seconds at the boundary
if the GE horizon genuinely needs wall-clock. One model, one unit, one conversion
site.

## Decisions (resolved by the user, 2026-08-08)

### 1 — Actions-per-gold: build the term, sourced from observation

Gold purchases are IN scope; the BUY route prices its currency rather than
treating it as free. The rate comes from the learning store's observed
gold-per-cycle, on the same principle `cheapest_path_to_level` already follows
for xp: prefer a measured rate, fall back to a derived one only where there are
no observations. `LearningStore` already records gold per cycle.

If a sell-price-derived rate was intended instead, it is one function behind one
call site — noted here so the choice stays visible rather than becoming a buried
constant.

### 2 — Travel is exactly ONE action per move, and distance stays out of `J`

Settled by the API's own semantics
(<https://docs.artifactsmmo.com/concepts/maps_and_movement/>): the **server**
runs the A* pathfind, so a move of any length is a single `/action/move` call.
The documentation's cooldown rule is *"The cooldown is 5 seconds per map."*

So distance is a **duration**, not a count. It scales the seconds a move costs
and never the number of actions a plan contains. `MoveAction.cost` already
encodes exactly this — `static = max(distance * 5.0, 1.0)`, the doc's rule
verbatim — as a Dijkstra edge weight, which is the correct home for it and where
it stays.

`J` therefore counts **+1 action per venue hop** (walk to the vendor, the bank,
the workshop, the monster tile) and is not distance-sensitive. This lands on the
same side of the line as `haste` for the same reason, which is a good sign the
line is in the right place: **seconds-denominated quantities do not enter an
actions-denominated objective.** A future wall-clock objective may consume both;
it would be a second objective with an explicit conversion, never a term folded
into this one.

### 3 — Skill levels are IN, priced as a prerequisite *inside* `acquire_cost`

> *"skill levels gate crafting tiers that unlock better weapons and armor. we
> can't craft iron items until crafting level >= 10. there is a pareto front
> spanning all character stats — there is a reason to level up each stat in
> service of reaching level 50."* — user

Adopted, with one design commitment that follows from that framing: **a skill
level gets no term of its own in `J`.** It is priced as the cost of a gate on the
CRAFT route, and it therefore pays for exactly what it unlocks, automatically.

Today `obtain_sources._craft_sources` returns `[]` when the skill gate is unmet —
the route is *excluded* rather than *priced*. That is the whole bug in one line.
An iron sword is not unobtainable at weaponcrafting 5; it costs a weaponcrafting
grind plus a craft. So:

```
cost(CRAFT item) = cost_to_reach(skill, required_level) + craft-chain actions
```

where `cost_to_reach` is a skill-xp analogue of `cheapest_path_to_level`, built
from `LearningStore.skill_xp_per_cycle(skill)` (the observed rate — it already
exists) over the `LevelSkillAction` mechanism, which is already the sole
skill-grind path.

**Why no per-stat term.** The user names a Pareto front across all character
stats. A single scalar in a single currency is precisely the instrument for
*selecting a point on* a Pareto front — adding a hand-weighted term per stat
would re-encode the front rather than search it, and every weight would be a
tuning surface nobody can calibrate. Pricing each stat's *acquisition* in
actions, against a benefit measured in the same actions, lets the trade-off
emerge from data instead of from constants. This is the same argument that
retired `branch_pick_pure`: a lexicographic pivot returns one extreme point of a
front; a scalar objective finds the interior.

This makes decision 3 a part of increment 1 rather than a separate epic, and it
subsumes the `_craft_sources` skill-gate exclusion as the first thing that has
to change.

## Anti-goals

- **Do not put `haste` in `J`.** Haste reduces cooldown *seconds*. `J` is
  denominated in *actions*. Adding it is precisely the seconds/actions confusion
  that has now cost this project four separate bugs. If wall-clock matters it
  needs its own objective and an explicit conversion, not a term smuggled into
  this one.
- **Do not fold potion resupply into the fight cost.** Already argued and
  deliberately declined in `fight_loop_cost`'s docstring; that reasoning still
  holds.
- **Do not widen `J` to decide *which* gear root.** That is still
  `focus_aging_pick`'s call with its five calibrated factors. This epic changes
  what `J` can *see*, not what it decides.
- **Do not add a route to `obtain_sources` and a price for it in the same
  commit.** The whole point is that the enumeration and the pricing share one
  source of truth; proving that requires changing one at a time.

## Verification obligations

Per `formal-development` and this project's gate, each increment carries: a
computable Lean def, role theorems ∀-quantified, a `Contracts.lean` statement
pin, a differential harness against the live function, mutation anchors that
resolve to exactly one site, and 100% coverage. `bash formal/gate.sh` green
before merge.

Beyond the gate, each increment needs a **live-run check** — green tests are not
runtime activation (`feedback_verify_runtime_activation`). Specifically: increment 1
must show a changed `acquire_cost` in a real `plan` descent; increment 3 must show
a wisdom-carrying root moving in the ranking; increment 4 must show a
prospecting-carrying root doing so.
