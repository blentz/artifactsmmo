# PLAN — band unification (spec S-016)

**Spec:** `docs/spec_cycle_economy/SPEC.md`, clause S-016: *"An available means and
the objective step are compared on marginal cycles against cycles saved or progress
unlocked over the horizon. Neither wins by virtue of the band or position it
occupies."*

**Status: STOPPED at increment 2, deliberately, on the measurement's evidence.**
Increments 0 and 1 are done. Increment 2 — collapsing the bands — is NOT justified:
priced, the ladder's answer is already the right one wherever the price exists at
all. See "Increment 2 — the verdict" below. Reopen if the evidence changes.

## What is there today

`arbiter_select.select_pure` walks candidates in a strict band order — guards 0,
collect 1, objective step 2, fallback steps 3, discretionary 4 — and returns the
FIRST plannable one. An objective step was present in 14,064 of 14,064 traced
cycles, so band 4 has been selected 133 times in 63,310 cycles (0.21%). Twenty-one
rungs are declared unreachable in the liveness census for exactly this reason.

`tiers/means_worth.py` exposes one function, `means_serves(...) -> bool`. **There is
no price for a means anywhere.** S-016 needs one, and it does not exist yet.

## The blocking question: what is gold worth in cycles?

S-001 denominates the objective in (cycles, seconds). S-045, just landed, says gold
is protected by REFUSAL and never by a penalty added to a cost — which is what
removing the four `gold / N` terms was about.

Run that forward and a means whose only output is gold prices at **zero**:

| means | output | price in cycles |
|---|---|---|
| `SELL_IDLE` | gold | 0 — never selected |
| `TASK_EXCHANGE` | random reward | governed by S-032, bounded not valued |
| `DRAIN_BANK_JUNK` | bank slots | expressible: deposits it unblocks |
| `RECYCLE_SURPLUS` | materials | expressible: acquisition cost avoided |
| `BANK_EXPAND` | bank slots | expressible, and gated by `should_expand_bank` |
| `ACCEPT_TASK` | reward + overlap | S-018 defines it |
| `GE_BID` | materials, later | expressible |

So five of seven price naturally and two do not. The two that do not are the two
that produce gold, and gold has no cycle value under the current model.

Three ways out, and choosing between them is a modelling decision, not a coding one:

1. **Gold is worth the cycles it saves.** One gold buys progress at some rate — the
   cheapest acquisition it unlocks. Principled and self-consistent, and it is
   S-027's rule read backwards. Costs: it needs a live "cheapest thing gold buys"
   query per decision, and it makes gold's value state-dependent.
2. **Gold is a constraint, never a value.** Selling exists only to clear a REFUSAL —
   the bot sells when a chosen course is blocked for want of gold, and never
   otherwise. Simplest, and it removes SELL_IDLE as a standing means entirely. It
   also means the bot never builds a reserve speculatively.
3. **A fixed gold-per-cycle rate.** Rejected on sight. That is a hand-tuned
   denomination constant, the fifth instance of the family the previous increment
   deleted four members of.

## Increment 0 — the measurement, and what it found

`scripts/measure_means_suppression.py` drives the REAL decision path
(`plan_from_state`) and reads the snapshot the driver already takes for the trace
(`StrategyArbiter.last_fires`), so there is no second producer of the fired-kinds
list. The bound `SelectionContext` — which nothing exposes after the driver binds
`step_profile` — is observed by wrapping the production function that receives it.

**Finding 1: the suppression is real, and it is not small.** WAIT excluded, since
S-023 exempts the totality witness from comparison.

| | priceable means fired while a step was present |
|---|---|
| live characters | **5 of 5** |
| scenarios | **25 of 30** |

Fired kinds, live: `accept_task` 5/5, `maintain_consumables` 4/5,
`recycle_surplus` 4/5. Each lost to the step by POSITION. The epic is not
cancellable.

**Corrected after the fact.** The first run of this measurement also reported
`sell_idle` 3/5, and that was an over-count caused by the very hazard it was
measuring: the sell rungs asked a predicate blind to whether any buyer's window
was open, so they fired while their goal was already satisfied. A
fired-but-unselectable rung is indistinguishable in this table from one the band
suppressed. Fixed, and re-measured: `sell_idle` is now 0/5, and the spurious
guard fires went with it. The headline 5/5 is unchanged because `accept_task`
carries it.

**Finding 2: the epic cannot be justified by measured harm, because there is no
common scale — and that is S-016's entire content.** Of the two sides S-016
compares, only one exists:

| | scenarios | live |
|---|---|---|
| step priced on the acquisition scale | 14/30 | 1/5 |
| step **unpriceable** (walls at 10^6) | 8/30 | 0/5 |
| step **off-scale** (`ReachCharLevel`) | 7/30 | 4/5 |

And of the four means that fire, exactly ONE (`recycle_surplus`) can be priced at
all today. `sell_idle` needs S-046, `maintain_consumables` needs a survivability
value, `accept_task` needs S-018's reward term and the reward table holds no rows.

**Finding 3, and it is a warning about this instrument.** Its first version
declared a winner by testing `recycle_benefit > step_cost` and reported *"the
priced answer differs from the ladder's in 0 of 23 comparable pairs"* — a
confident number from an arithmetic that meant nothing, because a BENEFIT and a
COST are not on one scale. The same units error the epic exists to remove,
committed by the tool measuring it. It now prints the halves and refuses a verdict.

**What increment 0 therefore settles:** the ladder suppresses 3–4 fired options per
live character every cycle, and NOTHING can currently say whether that is right,
because the step's benefit — its contribution to cycles-to-the-horizon — is not
computed anywhere per-step. Increment 1 is not optional, and it is bigger than
"price a means": it has to price BOTH sides.

## Increment 1 — the price, and what measuring it exposed

`horizon_contribution` supplies the missing half. `cycles_to_horizon(state)` is one
`cheapest_path_to_level` walk; `contribution(before, after)` is the difference; and
a course's post-state is its own PLAN applied, so a means needs no bespoke
projection and adding one later costs nothing. `branch_objective._outcome` now
delegates its cycles half to the same walk, so `J` and the worth of a course cannot
drift onto different scales. Unreachable is `None`, never 0 — the 0 filler stays in
`_outcome`, where the band that ignores it lives.

Measured live, at S-041's horizon (the next ten-level milestone; a fifty-horizon
reports None for every live character and measures nothing):

| character | horizon | cycles to it | this cycle's plan | worth |
|---|---|---|---|---|
| Robby | L29 → L30 | 791 | 1 action | 0 |
| R2D2 | L20 → L30 | **UNREACHABLE** | 1 action | — |
| C3P0 | L19 → L20 | **UNREACHABLE** | 3 actions | — |
| HAL | L17 → L20 | 1,727 | 1 action | 0 |
| Lor | L17 → L20 | 2,443 | 1 action | 2 |

**Finding 1: the two sides of S-016 are not the same length, and that is a defect in
the comparison rather than in the price.** A step's plan is ONE LEG of a long chain —
the planner emits a single action per cycle — while a means' plan is its whole
course (sell the hoard, recycle the surplus). Pricing "the plan" therefore charges a
means for everything it does and credits a step with one action's worth of progress,
which is why every step above scores 0 or 2 against a horizon hundreds of cycles
away. Increment 2 must compare a step's WHOLE course, which is the root's
acquisition, against the means' whole course. Comparing this cycle's legs would
hand the ranking to whichever candidate happens to finish in one action.

**Finding 2, unrelated to the band: two of five live characters cannot reach their
own next milestone — and the cause is a COMBAT WALL, not an empty map.**

`cheapest_path_to_level`'s docstring said `blocked` means "no beatable monster
exists". Measured: C3P0 has SEVEN winnable monsters and R2D2 ELEVEN, and both
block. The exit that actually fires is the second one, `best_xp_per_cycle <= 0` —
every beatable monster is GREY.

| character | best winnable | gap | XP | nearest that pays |
|---|---|---|---|---|
| C3P0 L19 | `cow` L8 | 11 | **0** | `pig` 19, `spider` 20, `ogre` 20 — all unwinnable |
| R2D2 L26 | `highwayman`/`wolf` L15 | 11 | **0** | `vampire` 24, `cyclops` 25 — unwinnable |
| Lor L17 | `cow` L8 | 9 | 14 | inside the band, fine |

Lor pins the boundary from the other side: gap 9 pays 14 and gap 10 pays 9, so the
zero band starts at gap 11 exactly. This is the situation this whole epic opened
with — grind to the level where fights start being lost, then face a skill-grind
for gear that can win them.

**The bot's response is correct, and that is worth recording too.** The objective
ranks `greater_wooden_staff` as the ONLY candidate reaching L26 while every other
sits at 19, decided by S-006 key 1 (furthest progress) — the right key when `J` is
void. C3P0's live cycle pursues exactly that: `GatherMaterials(ash_plank)`, a
three-action plan opening `Recycle(water_bow x2)`. Nothing to fix in the decision.

**Two real defects fell out of the diagnosis, both fixed:**

* The walk's docstring named one of its two blocked exits, so a blocked walk read
  as "the map has nothing to fight" when it means "everything I can beat is grey".
  That misdiagnoses a character needing GEAR as one needing a MONSTER.
* `objective` without `--learn` uses a cold `:memory:` store, and a skill-gated
  craft cannot be priced without an observed grind rate. Cold, the staff reads
  1,000,001 — indistinguishable from a real wall. Against the live learning DB it
  costs 733. The header now says so.

**And a defect in the measurement harness itself, found by disagreeing with the
CLI.** `_live_players` seeded states from `WorldState.from_character_schema`, which
carries no BANK CONTENTS, so the gear step could not plan (its first legs are
`Withdraw`) and the walk fell through to housekeeping. The table above briefly
recorded `RecycleSurplus` as three characters' chosen course. It now seeds through
`_initialize`, the same path the `plan` CLI uses. The suppression figures in
increment 0 were re-measured after the fix and are unchanged.

0. **Measure.** ✅ DONE — `scripts/measure_means_suppression.py`, verdict below.
1. **Price a means.** ✅ DONE, and it turned out to be "price a COURSE", which is
   what makes it work for a step and a means alike —
   `ai/tiers/horizon_contribution`. Findings below.
2. **One comparison.** Collapse bands 1–4 into a single priced ranking. `BAND_GUARD`
   stays a hard precedence — S-017 exempts guards from pricing, and that exemption
   is deliberate, not an oversight.
3. **Sticky commitment as a cost.** Today it is a band rule. Under S-006 it is
   already marginal cost: committed work is cheaper because part is paid. Re-express
   it so the arbiter has one mechanism, not two.
4. **Re-run the liveness census.** The 21 `unreachable:` declarations should collapse
   to whatever is genuinely conditional. Any that do not are a finding.

## What NOT to do

Do not open the band by reordering `DISCRETIONARY_ORDER` or by promoting specific
means into band 2. That is another priority ladder, and the whole point of S-016 is
that position must stop deciding.
