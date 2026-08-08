# PLAN — Unified acquisition objective

Status: **DRAFT, nothing built.** Written 2026-08-08 against local `main` @ `5a2d1b8d`.

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
`acquire_cost` only. Per-route action counts:

| route | actions |
|---|---|
| WITHDRAW | 1 (+ travel, if travel is counted — see open decisions) |
| CRAFT | 1 per craft node, recursing into inputs (today's `min_crafts`) |
| GATHER | `ceil(units / max_gather_yield)` (today's `ceil_gathers`) |
| DROP | `ceil(expected_kills) × cycles_per_kill` — reuse `_expected_kills` *and* `fight_loop_cost.cycles_per_kill`, so a drop-farm is priced in the same whole-loop cycles `cycles_to_fifty` uses |
| BUY | 1 purchase **+ the cost of obtaining the currency**, recursively |
| RECYCLE | 1 per unit destroyed |

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

### 2 — Currency is not free (the BUY term's teeth)

`npc_purchases` returns `(npc, price, currency)`. `currency` is `gold` or an item
code (`event_ticket`, `tasks_coin`, …). The BUY cost is `1 + acquisition_cost(currency, price)`
— recursive, which terminates because currency chains bottom out at gold or at a
gatherable/droppable.

Gold itself needs an actions-per-gold rate. This is the increment's one genuinely
open modelling question and it is listed under open decisions below.

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

## Open decisions (for the user — these change the design, not the code)

1. **Actions-per-gold.** The BUY term needs gold priced in actions. Candidates:
   the learning store's observed gold-per-cycle; a sell-price-derived rate; or
   declaring gold purchases out of scope for `J` in this epic. This is a real
   modelling choice with no obviously right answer, and it decides whether
   increment 2 is small or large.

2. **Is travel an action?** Today nothing in `J` counts movement. `WITHDRAW` is
   "1 action" only if walking to the bank is free. Counting travel would make
   `J` distance-sensitive across the board — a large, coherent change, or a
   deliberate documented omission. It should not be decided per-route by
   whoever writes each term.

3. **Does `J` want skill levels?** `cycles_to_fifty` is character level only.
   A gathering/crafting skill level is a hard gate on entire recipe trees, and
   nothing in `J` values reaching it. In scope, or a separate epic?

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
