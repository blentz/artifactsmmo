# One defect, three instances: priority ladders where the top rung never moves

Measured 2026-08-18 with the fleet stopped. This is the holistic account the
iron-gear investigation kept circling: the epicycles are not independent, and the
generator is a single architectural habit.

## The habit

The bot chooses among **incommensurable** options by a **strict priority order**
rather than a common currency. In every instance measured, the top key does not
vary, so every lower key is decoration — and every instance has been repaired by a
*bespoke promotion or fallback* for one option at a time, never by making the
options comparable.

| instance | the order | the key that never varies | the bespoke patch | measured |
|---|---|---|---|---|
| gear vs XP | `branch_pick_pure`, lexicographic on `band_adequate` | second conjunct never true against a 50-level catalogue | replaced wholesale by `J` | GEAR **2950 / 2950** cycles, zero levels gained in 13 h |
| `J`'s own bands | S-006, lexicographic (band, progress, cost) | nothing reaches L50 below ~L40 | S-006's fallback key | finite `J` **0 / 10,716**; trunk wins **8,769 / 8,769** ties |
| the means ladder | guards → collect → **objective step** → discretionary | a step is present **100%** of cycles | promote one rung at a time (`SUPPLY_BANK`) | discretionary band **133 / 63,310 = 0.21%** |

A fourth, smaller instance of the same non-unification: four unrelated horizon
constants in four modules — `inventory_caps.RECIPE_SKILL_HORIZON = 2`,
`progression_reserve._HORIZON`,
`prerequisite_graph._CHAR_LEVEL_BOOTSTRAP_HORIZON = 2`, and `strategic_value`'s
`horizon: tuple[int, int]` — none of them the objective's, which reads none of
them.

## Instance 3, measured: the discretionary band is structurally unreachable

The means ladder is a strict priority order. Anything below the objective step
fires only when no step exists. Over 14,064 traced cycles carrying a `fires`
record:

```
step_present TRUE : 14064  (100.00%)
step_present FALSE:     0  ( 0.00%)
```

There has never been a cycle without an objective step. And the band below it is
consulted every cycle and loses every cycle:

```
means OFFERED (available) per cycle          selected, all 63,310 cycles
  accept_task           14064   (100.0%)         0
  wait                  14064   (100.0%)         0
  drain_bank_junk       13762   ( 97.9%)        80
  maintain_consumables  12461   ( 88.6%)         0
  recycle_surplus       11873   ( 84.4%)        39
  sell_idle              9744   ( 69.3%)        14
```

`accept_task` is **available in every single cycle** and has been selected in
**none**. I first assumed its own gate was the blocker — the
"defer while any target gear is craftable" clause, which has the exact shape of
the `band_adequate` defect — and measured it live on all five characters:
`deferred_by_owned = 0`, `deferred_by_craftable = 0`. The gate is open. The band
it sits in is what is closed.

Band totals over the whole 63,310-cycle history:

```
guards + objective step        59,906   94.62%
COLLECT_REWARD_ORDER            3,285    5.19%   (3,269 of it SUPPLY_BANK alone)
DISCRETIONARY_ORDER               133    0.21%
```

**The repo already knows this, in its own voice.** `means.py`'s comment on the
`SUPPLY_BANK` promotion:

> DISCRETIONARY_ORDER (below the objective step, **where it never won a single
> cycle of the traced four-character run**) […] in the traced runs SUPPLY_BANK was
> selected zero times from the discretionary band, **because the objective step
> outranked it on every cycle a step existed.**

So the diagnosis was made, correctly, for one rung — and the fix was to move that
one rung. Nine remain behind the same closed gate. `CURRENCY_TURNIN` was added
straight into `COLLECT_REWARD_ORDER` on 2026-08-16 (avoiding the trap) and still
has **0** selections, which is a separate question this document does not answer.

## What that costs: the task economy is dead in a chain

18 of 34 `Goal` classes and 17 of 36 `Action` classes have never fired in 63,310
cycles. Not one of the 18 appears in a `plan_body_log` body either, so they are
absent as sub-steps too. Most importantly:

**No character has ever held a task.** `task_code` is non-null in 0 of 63,310
cycles, across 16 days and five characters.

That is one root cause with six dependent victims:

```
accept_task unreachable (discretionary, step present 100%)
   └─ no task is ever held
        ├─ PursueTaskGoal        (needs task_type == "items")
        ├─ CompleteTaskGoal      (needs a task to complete)
        ├─ TaskCancelGoal        (needs a task to cancel)
        ├─ LowYieldCancelGoal    (needs a task to judge)
        └─ TaskExchangeGoal      (needs tasks_coin, earned by completing tasks)
```

Also behind the same closed band: `MaintainConsumablesGoal`, `ExpandBankGoal`
(`bank_expand`), `PostBuyBidGoal` (`ge_bid`), `WaitGoal`.

This matters beyond tidiness. Tasks are the game's route to `tasks_coin`, which
buys the vendor-only items the gear chain otherwise cannot reach — and
`docs/…task_funding_activation` records an entire epic (the C4 funding pipeline,
grey-mob drop farm, vendor-only equippables) built on a subsystem that has never
executed a single cycle. The same is true of the currency turn-in work
(`CurrencyTurnInGoal`, `SurrenderCurrencyGoal`): both never fire.

Not every never-fired goal is a defect — `ParticipateRaidGoal` legitimately needs
a live raid, and `UnlockBankGoal`/`ReachUnlockLevelGoal`/`ReachSkillGoal`/
`ReachCurrencyGoal`/`ProvisionMarginalFightGoal` are unclassified here and want
their own check. But the task family's six are one blocked rung, and that is
established.

## Why the pattern keeps regenerating

Each instance is locally reasonable. A priority ladder is the obvious way to say
"survival before opportunism". The failure is that the ladder's top rung is
**always satisfiable**: there is always a step to take, there is always gear that
is not yet perfect, there is always a level below 50. So the ladder degenerates
into its first rung, and the lower rungs become documentation of intent rather
than behaviour.

The repair that suggests itself each time — promote this one rung, add a fallback
key, add a threshold to stop the promoted rung firing too often — preserves the
ladder and therefore preserves the defect. `SUPPLY_DEMAND_MIN = 10` is a carefully
derived, genuinely load-bearing constant whose entire job is to undo the
side-effect of a promotion that was only needed because the ladder does not
compare. That is an epicycle in the precise sense: a correction whose necessity is
an artefact of the model's shape.

## The unified fix, and its scope

The same one the objective needs, applied one layer up: **put the options in one
currency and compare them, rather than ordering them.**

For the objective that is option C — the rung walk spends cycles on acquisition,
and `J` is the cycles the walk took (`docs/PLAN_bounded_horizon_objective.md`).
For the means ladder it is the same move: a means is worth taking when the cycles
it costs are repaid by the cycles it saves or the progress it unlocks, judged
against the same horizon. `accept_task` then competes on merit — an items task
that yields skill XP the objective needs and `tasks_coin` the gear chain needs is
either worth its cycles or it is not, and today the question is never asked.

This is strictly larger than increment 3 as scoped, and it should not be smuggled
into it. Two honest options:

* **Sequence them.** Land C on the objective first (it is specced, measured, and
  the pricing wall is already fixed), then apply the same treatment to the means
  ladder as a second epic with its own measurements.
* **Unify the model first.** Define the one currency and the one comparison, then
  migrate both the branch pivot and the means ladder onto it. Larger and riskier,
  but it is the only version that stops the pattern rather than moving it.

## Cheap wins available immediately, independent of either

1. **Promote or delete.** Nine means sit behind a gate that has never opened. Each
   is either worth competing (promote, as `SUPPLY_BANK` was) or it is not (delete
   it and its goal). Leaving them is the third option and it is the one that has
   produced two dead epics.
2. **A liveness census as a gate step.** The query behind this document — goals and
   actions defined but never selected, plus band totals — is ~30 lines over
   `learning.db` and would have caught the task subsystem, `CURRENCY_TURNIN`, and
   `J` itself. This repo already gates on six censuses; it has none for *did this
   ever run*.
3. **One horizon.** Four constants, four scopes, none shared with the objective.

## Residuals

* Band totals come from `selected_goal`, which records the arbiter's pick. A means
  whose goal shares a repr prefix with another could be mis-attributed; the
  mapping used is in this document's query and `SellInventory` is genuinely
  ambiguous between `sell_pressured` and `sell_idle` (14 total, split unknown).
* `step_present` is trace-derived (14,064 cycles, 2 days). It is not in
  `learning.db`, which is why item 2 above matters. The 63,310-cycle band totals
  ARE from `learning.db`.
* `CURRENCY_TURNIN`'s zero, sitting above the step where the ladder cannot be
  blamed, is unexplained and is the next thing to measure.

---

# Disposition of the 21 unreachable rows (2026-08-18)

`unreachable:` is now 21 of 70 classes. They are NOT one fix. Grouped by what
would actually make each reachable, because the answer differs and three of the
four groups need a product decision rather than a code change.

## The mechanism, stated once

`strategy_driver._build_candidates` assigns every candidate a band:

```
BAND_GUARD 0  <  BAND_COLLECT 1  <  BAND_STEP 2  <  BAND_FALLBACK_STEP 3  <  BAND_DISCRETIONARY 4
```

A step is present in 14,064 of 14,064 traced cycles, so band 4 is unreachable.
The repo's existing answer is the **urgency hoist**: materialise the goal in
BAND_COLLECT when a stated threshold is crossed. It has been applied four times,
each with its own bespoke threshold and no shared concept:

| rung | hoist condition | constant |
|---|---|---|
| `RECYCLE_SURPLUS` | `shed_urgency(surplus) >= …` | `RECYCLE_HOIST_URGENCY` |
| `SELL_IDLE` | `shed_urgency(bag) >= …` or `bank_shed_hoist(…)` | `SHED_HOIST_URGENCY` |
| `DRAIN_BANK_JUNK` | `bank_shed_hoist(excess, inventory_max)` | — |
| `SUPPLY_BANK` | moved out of the band entirely | `SUPPLY_DEMAND_MIN = 10` |

Those four work, and they are why `RecycleSurplus`/`SellInventory`/`DrainBankJunk`
fire at all. All four measure **inventory or demand pressure** — a local,
observable quantity. That is why the pattern was available to them, and it is
exactly what the remaining rungs do not have.

## Group A — the task economy (8 classes). Needs a value comparison.

`AcceptTaskGoal`, `AcceptTaskAction`, `PursueTaskGoal`, `CompleteTaskGoal`,
`CompleteTaskAction`, `TaskCancelGoal`, `TaskCancelAction`, `LowYieldCancelGoal`,
`TaskExchangeGoal`, `TaskExchangeAction`, `TaskTradeAction`, `ReachSkillGoal`,
`ReachCurrencyGoal` — all downstream of `accept_task`.

There is no urgency analogue here. "Should I accept a task instead of advancing
my objective step" is a genuine comparison of two productive uses of a cycle, and
it is the same question option C asks about gear-versus-XP. An urgency hoist would
be an invented threshold — precisely the epicycle this document is about.

**DECIDED 2026-08-18: activate, alongside option C, together with the C4 epic.**

And the user supplied the design principle the code was missing — tasks are
**synergistic** goals, not standalone ones:

* Accept a task that **aligns with a skill-XP grind already committed to**. The
  grind happens anyway, so the task's marginal cost is near zero and its rewards
  are pure gain.
* When character XP is what is needed, accept a **kill-monsters** task: the
  fighting happens anyway, and `task reward + xp > xp alone`.
* Pursue a task **for its own sake only when the rewards themselves are the
  need** — gold or `tasks_coin` required to purchase something specific.

That is exactly the one-currency framing, and it is why an urgency hoist was the
wrong instrument: a task is worth accepting when the work it demands OVERLAPS
work already committed, so its cost is marginal rather than additive.

**Half of it already exists and is discarded.** `tiers/means_worth.py` computes
`_task_need_overlap` — how many of a task's output kinds (char XP, skill XP, the
task item, funding) serve a live objective need — and thresholds it through
`synergy_pure(overlap, K) > S_MIN`. The overlap is a RANKING quantity being used
as a boolean gate. The activation work is to let that number compete rather than
merely veto, on the same cycle currency as everything else.

## Group B — raids (1 class). A design contradiction, and it has an urgency.

`ParticipateRaidGoal` is appended at BAND_DISCRETIONARY, and its docstring calls
that "the right priority for a timed bonus". A timed bonus that yields to a
permanent step expires unused, so the stated rationale defeats itself.

Unlike group A this one DOES have a principled urgency: the raid window is
closing, which is local and observable, and the existing hoist pattern applies
directly. **This is the one rung where the repo's own established mechanism is
both available and clearly correct.** Not implemented here because no raid has
been open while the fleet ran, so the change could not be verified live — and
shipping an unobservable behaviour change into the selector is how this codebase
acquired several of the defects above.

## Group C — real features with no pressure signal (4 classes)

`MaintainConsumablesGoal`, `ExpandBankGoal`, `BuyBankExpansionAction`,
`PostBuyBidGoal`, `GePostBuyOrderAction`. Each is a genuine capability behind the
closed band. `MAINTAIN_CONSUMABLES` arguably has an urgency (about to fight
without heals) and is the best candidate for the existing pattern; `BANK_EXPAND`
and `GE_BID` are value comparisons like group A.

## Group D — NOT deletable. A proof witness. (2 classes)

`WaitGoal`, `WaitAction`. This document first called them "probably delete —
nothing is lost by removing them". **That was wrong, and checking the blast
radius is what caught it.**

`MeansKind.WAIT` is the liveness tower's totality witness.
`Formal.Liveness.NoDeadlockV2.productionLadder_total` — the headline theorem that
the bot always has something to do — is proved *via* `wait_mem_ladder` and
`waitFires s = true`:

```lean
theorem productionLadder_total (s : State) : productionLadder s ≠ none := by
  refine productionLadder_ne_none_of_fires wait_mem_ladder ?_
  change waitFires s = true
```

So `wait` fires unconditionally and sits last: **anything above it winning
instead is the guarantee being redundant, which is the point.** Its zero
selections are the proof working, not dead code. Deleting it breaks
`NoDeadlockV2` and 12 other Lean files.

This is a distinct reason class, now recorded as `witness:` in the census. It is
the one case where "never fired" carries no obligation at all — and without the
category, a liveness census is an invitation to delete the very thing that proves
the ladder cannot stall.

## What this document is NOT proposing

A fifth bespoke hoist. Adding one for `accept_task` would move that rung and
leave the pattern intact for the next one, which is what happened after
`SUPPLY_BANK`, `RECYCLE_SURPLUS`, `SELL_IDLE` and `DRAIN_BANK_JUNK`. The
generalisation worth making — one `hoist(means) -> urgency` rule replacing four
ad-hoc booleans — is a refactor with no behaviour change and should ride along
with whichever group is activated first, not before.
