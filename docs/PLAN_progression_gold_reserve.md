# PLAN: progression-driven gold reserve (replaces flat GOLD_RESERVE=500)

Status: SPEC CAPTURED 2026-06-18 (from audit #9 reframe). Needs brainstorming
before implementation. NOT a literal swap — a new calculated model.

## User's vision (verbatim intent)

Reframe the gold reserve from a flat 500 to a CALCULATED per-level target:

> Reserve gold for near-term upgrades of ANY kind. We know the shape of the next
> 1-2 levels' worth of progression in equipment terms (axiom: max equipment
> per-level leads to swift level progression). Therefore calculate a per-level
> gold reserve target. Reserve gold is SPENT on items that accelerate leveling
> progression — including items that accelerate crafting progression or
> combat-odds maximizing, especially boss-fight strategizing.

So: `reserve = projected cost of the items that would best accelerate the next
~1-2 levels of progression` (gear upgrades + crafting-unlock items + combat/boss
odds-maximizers), priced from game data (NPC buy / GE), counting only what is
not already owned or cheaply craftable.

## Why it's a feature, not a swap

- Must enumerate "near-term progression targets": per-slot best gear usable at
  level..level+2 (reuse `find_upgrade_target` / equipment scoring), plus
  crafting-progression items (skill-gate unlockers), plus boss/combat-odds gear.
- Must price each (ge_best_buy_order / npcs_selling_item), net against
  owned/craftable (reuse craft_vs_buy / recipe closure).
- Must decide horizon (1 vs 2 levels), and how boss-fight weighting enters.
- Plugs into the 2-3 reserve consumers (gathering acquisition buy-gate,
  ge_fill_sell buy-gate; expand_bank's gold-safety is a separate question).

## Open design questions (for brainstorming)

1. Horizon: fixed +2 levels, or until the next skill/boss gate?
2. Which item classes count, and how are "boss-fight strategizing" items
   identified from game data (event/boss monster drops + winnability)?
3. Net-of-craftable: subtract items already craftable-now (don't reserve gold
   for what you can make)? Interaction with craft_vs_buy.
4. Does this REPLACE GOLD_RESERVE everywhere, or only the discretionary-buy
   gates (leaving expand_bank's safety check)?
5. Formal-development candidate? The reserve calc is pure decision logic
   (could be a proven core: monotonic in unmet-upgrade cost, etc.).

## Formal-development note

The reserve calculation is pure, total, game-data-derived decision logic — a
good candidate for the formal/ treatment (Lean def + differential) IF it
becomes load-bearing. Decide during brainstorming.

## Entry point
`craft_vs_buy.py:GOLD_RESERVE` (consumers: goals/gathering.py:257,
actions/ge_fill_sell.py:51, goals/expand_bank.py:47). See audit in
docs/PLAN_calculate_not_hardcode.md #9.
