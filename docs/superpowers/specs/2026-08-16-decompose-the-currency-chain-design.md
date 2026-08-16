# Decompose the currency chain — design

**Date:** 2026-08-16
**Branch (proposed):** `fix/decompose-currency-chain`
**Status:** design, pre-implementation

---

## Problem

Robby (level 27) has **two empty artifact slots** and the account holds **243
`event_ticket`** (220 banked, 23 on Robby). Nothing is ever bought.

The bot's target for all three artifact slots is `lich_race_trophy`, and that is
the right call on value — +20% damage against the `lich_race_medal`'s +5%. But:

```
lich_race_trophy   blocked=True   funding_target=None   deficits=()
lich_race_medal    blocked=False  deficits=(('event_ticket', 77))
```

The trophy costs **10 `lich_race_medal`**, each costing **100 `event_ticket`** —
1,000 tickets for one trophy. It is blocked, and the blocked analysis produces
**no funding target**, so it never decomposes into "buy medals first". The medal
is affordable today (the 77 is a correct *withdraw-from-bank* instruction, not a
shortfall) but is never targeted, because the per-slot pick is an argmax with no
fallback when the argmax is unreachable.

So the bot waits for a trophy it cannot afford while two slots sit empty and 220
tickets sit idle.

### Root cause

`ai/goals/currency_demand.py:274-278`:

```python
fundable = [
    (npc, price, currency)
    for npc, price, currency in permanent
    if currency == TASKS_COIN_CODE
]
```

**The funding arm is hard-restricted to one currency.** Any other item currency
yields an empty `fundable`, and `analyze_currency_leaves` then takes the
`if not lf.fundable: continue` branch at `:374` — "blocked but unfundable".

The other arm does not help either: `item_route` (`:264-272`) admits a leaf only
when the character **already holds** enough of the currency. Holding zero medals,
the trophy has no route.

Neither arm ever asks the question that matters: **is the currency itself
obtainable?**

### What is NOT the problem

Worth recording, because the first diagnosis was wrong and cost a round.

Buying gear already works end to end. `tiers/objective.is_attainable` has an
explicit purchase edge with *recursive item-currency support* and a cycle guard;
`NpcBuyAction` has a currency variant wired into `actions/factory`;
`analyze_currency_leaves` credits pocket + bank; and the scenario
`l30_rune_fill` proves the whole chain live for a vendor-only rune.
`goals/progression.find_upgrade_target` does have only inventory/craftable arms,
but it is not the path that selects artifact targets — `near_term_gear` is, and
it already returns vendor-only items.

---

## Goal

Make a multi-hop currency chain decompose, so an item priced in a currency the
character can *obtain* becomes a reachable multi-step objective rather than a
dead end.

### Non-goals

- **Interim fills.** Falling back to the medal when the trophy is blocked was
  considered and deliberately rejected for this design (see *The cost*, and the
  residual below). The user chose decomposition with empty slots as the accepted
  cost.
- **Changing which item a slot targets.** `near_term_gear` picking the trophy is
  correct on value and stays.
- **Grinding `event_ticket`.** `currency_accrues_passively('event_ticket')` is
  True (56 of 58 monsters drop it), and that predicate exists precisely to say
  "no dedicated farm; buy once ordinary play has accrued enough." That judgement
  is unchanged.

---

## The cost, measured before committing to it

At the observed accrual rate this is a **very** long objective, and the number
belongs in the design rather than in a footnote.

Measured over the learning store's 49,355 cycles (2026-08-02 → 2026-08-16):

```
tickets observed in drops : 365
tickets per cycle         : 0.0074
cycles per 1,000 tickets  : ~135,200
```

Against the calibrated throughput of ~52 cycles/hour/character
(`project_multi_character`), five characters pooling into the bank is roughly
**11 days of continuous play per trophy**, and there are three artifact slots.

The slots stay empty for that entire period. That is the trade this design
accepts by choice, but it should be re-read before implementation: one medal is
100 tickets (~13,500 cycles) and is affordable *today* from the bank.

---

## Design

### The funding arm generalises from one currency to any obtainable currency

Replace the `currency == TASKS_COIN_CODE` filter with a predicate asking whether
the currency is obtainable, and carry the decomposition rather than a bool.

**Reuse `tiers/objective.is_attainable`'s recursive buyable path** — do not
write a second currency-reachability walk. That function already recurses
through item currencies with a cycle guard (`leaf_ok`, `_attainable_closure`,
`path | {leaf}`), and a second implementation would be the divergence
`ai/gather_skill_gate.py` exists to document. If its shape does not fit, extract
the shared core rather than mirroring it.

### The chain must be bounded, and the bound must be a real quantity

An unbounded recursion will happily commit the bot to `sonnengott_cloak` at 245
`sonnengott_coin`, or to a chain whose leaf currency accrues at a rate that puts
it years away. The bound is **not** a depth limit — depth is not the thing that
hurts. It is the projected acquisition cost of the leaf currency, which the
codebase already knows how to express in cycles.

A chain is admissible when its total leaf-currency demand is reachable within
the same horizon the rest of the objective layer uses. Where that horizon comes
from — `acquisition_cost`, `strategic_value`'s horizon, or an explicit cap — is
the one open implementation question, and the implementer should propose it from
what exists rather than inventing a constant.

**A chain that fails the bound must stay blocked and say so**, not silently fall
back to a cheaper item; that would be the interim fill this design rejected.

### Emission

`funding_target` already exists and is consumed for the `tasks_coin` case. The
implementer must establish, before writing code, whether that consumer
generalises to an arbitrary currency or assumes task-coin semantics. If it
assumes, extending it is part of this work and the spec's scope grows to name
it — that is a finding to report, not to absorb silently.

The purchase itself needs nothing new: `NpcBuyAction`'s currency variant already
buys with an item currency, and `_currency_deficits` already emits the
withdraw-from-bank quantity.

---

## Testing

- **The acceptance case is Robby's live state**: with 220 tickets banked and 23
  held, `analyze_currency_leaves({'lich_race_trophy': 1}, …)` must stop returning
  `blocked=True, funding_target=None` and instead expose the medal hop. Probe
  real state, not a fixture — a fixture disagreed with live state twice in this
  project's recent history.
- **The bound must be exercised in both directions.** One chain that decomposes
  and one that is correctly refused. A test only showing the success case cannot
  distinguish "bounded" from "unbounded".
- **Cycle safety**: a currency graph containing a cycle must terminate. Build the
  cycle explicitly in a fixture rather than trusting that the real catalog has
  none today.
- **The `tasks_coin` path must not regress** — it is the one currency that works
  now, and generalising its filter is exactly how it could break. Its existing
  tests must pass unmodified.
- **`currency_accrues_passively` must still suppress a ticket grind.** The bot
  should accumulate tickets through ordinary play, not divert to farming them.
- Full gate green, bot stopped.

---

## Residuals

- **The slots stay empty for ~11 days per trophy.** Named as the accepted cost,
  not hidden. If that proves unacceptable in practice, the interim-fill design
  (fall back to the best *attainable-now* item for a blocked slot) is the
  alternative that was rejected here, and the tension it must resolve is that a
  worn medal is not a spendable one — the trophy needs ten.
- **`find_upgrade_target` still has only inventory and craftable arms**
  (`goals/progression.py:518`). It is not the artifact path and is not touched
  here, but it means a buy-only item can never be an *upgrade* target for an
  occupied slot — only a `near_term_gear` fill. Untested territory, recorded.
- **31 equippables are vendor-only** (no craft recipe), spanning levels 10-50 —
  every rune, the voidstone tools, `backpack`, `sonnengott_cloak`. This design
  makes their currency chains decomposable; whether each is *worth* its chain is
  a separate ranking question.
