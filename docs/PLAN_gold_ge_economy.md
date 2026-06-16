# PLAN #2: gold / Grand Exchange economy (advanced)

**Priority:** 2 (LAST, per user ordering). **Status:** planned.

## What's ALREADY modeled (better than first feared)

- `craft_vs_buy` (proven): buy a needed item over crafting when strictly fewer
  cooldowns AND affordable above `GOLD_RESERVE=500`.
- `buy_source_venue` / `choose_buy_venue` (proven): buy from NPC vs GE by lower
  realizable cost; GE chosen only when a real sell order exists and is strictly
  cheaper.
- `liquidation_venue` (proven, the dual): sell surplus at the better venue.
- `ge_fill` (sell into a standing buy order) / `ge_fill_sell` (buy by filling a sell
  order) actions; `sell_inventory` goal; monster gold drops + task rewards.

So the bot already buys cheap, sells surplus, and trades cooldowns for gold sensibly.
The remaining gaps are OPTIMIZATIONS, not correctness — hence last.

## Gaps (optimizations)

1. **Passive-only market** — the bot NEVER POSTS a GE order (only fills existing
   ones), by deliberate design ("a posted order may not fill"). It forgoes
   better-than-market prices (post a buy below ask / sell above bid). Adding order
   POSTING means modeling fill-uncertainty + capital tied up in open orders —
   substantial, with modest upside. Likely keep the conservative immediate-fill rule.
2. **No active gold FARMING** — gold is a byproduct (surplus sales, drops). There is
   no objective to farm gold when it GATES progress (craft_vs_buy can't buy below
   reserve ⇒ the bot grinds mats it could have bought if it had gold). A
   `EarnGold`-style objective (grind the most gold-efficient winnable monster /
   sellable resource when gold is the binding constraint on a needed purchase) could
   accelerate gearing. The clearest real win here.
3. **Flat `GOLD_RESERVE=500`** — not goal-adaptive (doesn't save up for a known
   expensive purchase). A target-aware reserve (reserve = base + price of the next
   planned buy) is a small tweak.
4. **No arbitrage / price trend use** — the bot fills at market; no buy-low/sell-high
   speculation. Out of scope (high complexity, gamey).

## Approach
- Verify FIRST whether gold is ACTUALLY a binding constraint in traces (is the bot
  ever gold-blocked on a needed buy?). If not, this whole plan is low-value — confirm
  before building.
- If gold-blocked: build the `EarnGold` objective (#2's only likely-worthwhile piece)
  — pick the highest gold/cooldown winnable income source, gated on
  (gold < reserve + next-needed-buy-price). Reuses combat/gather + the proven
  liquidation venue. The gold/cooldown ranking is a candidate proven core.
- Gap 3 (adaptive reserve) is a cheap follow-on. Gaps 1 and 4 likely permanently
  deferred (complexity ≫ value for a single-character leveling bot).

## Risk / sizing
Mostly LOW-VALUE (the economy works). Only gap 2 (active gold farming when
gold-blocked) is likely worth building, and only IF traces show gold blocking
progress — verify before committing. Appropriately last in the order.
