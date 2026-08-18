# PLAN — band unification (spec S-016)

**Spec:** `docs/spec_cycle_economy/SPEC.md`, clause S-016: *"An available means and
the objective step are compared on marginal cycles against cycles saved or progress
unlocked over the horizon. Neither wins by virtue of the band or position it
occupies."*

**Status:** blocked on one design question. Everything else is scoped below.

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

## Increments, once the question is answered

0. **Measure.** Instrument each discretionary means with the price it WOULD carry,
   log it for a fleet run, and confirm the ordering the ladder currently imposes
   disagrees with the priced one. If they agree, this epic is unnecessary.
1. **Price a means.** `means_price(kind, state, game_data, ctx) -> int | None`,
   None = unavailable. Same units as the objective step's marginal cycles (S-006).
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
