# PLAN: currency value-normalization + arbitrage detection (#15)

The bot treats all NPC prices as GOLD. With #12/#13 the world has multiple
currencies (gold, sandwhisper_coin, small_pearls, elemental_page, codex_page,
monster-drop currencies like cowhide/wool/rat_hide). This task makes
cross-currency reasoning sound and (optionally) surfaces arbitrage.

## Findings (2026-06-21 code audit)

* **Latent bug — `acquisition_method` / `cheaper_acquisition`
  (ai/craft_vs_buy.py):** picks the cheapest seller via
  `min(npcs_selling_item(item), key=price)` and checks affordability as
  `gold - total_price >= reserve` — treating EVERY seller's price as gold,
  whatever its currency. `npcs_selling_item` returns `(npc, price)` (currency
  dropped); the currency-aware `npc_purchases` → `(npc, price, currency)` exists
  but isn't used here. A non-gold-priced MATERIAL would be mis-compared and
  mis-affordability-checked. (Equipment bought with special currencies —
  rune/bag/artifact — goes through the objective buy-edge, not this path, so the
  bug is latent until a non-gold-sold crafting material appears; closing it is
  defensive + future-proofs the event-content path, PLAN #4.)
* **Numeraire source:** `ge_best_sell_order(item_code)` / `ge_best_buy_order`
  give a gold price for any GE-tradeable item. So a currency that is itself a
  tradeable item (cowhide, wool, …) HAS a derivable gold-equivalent = its GE
  price. Soulbound / event currencies (sandwhisper_coin, pages, pearls) are NOT
  GE-tradeable → NO honest gold-equivalent ("use API data or fail" → leave them
  un-normalized; only compare within the same currency).

## Three phases (increasing scope/risk)

1. **Bug fix (bounded, high-value):** make `acquisition_method` currency-aware.
   Simplest sound fix — the gold-reserve affordability only makes sense for gold
   purchases, so consider only GOLD-currency sellers for the craft-vs-buy gold
   comparison (non-gold purchases already route through the objective buy-edge /
   currency-earning sub-goal). Closes the mis-compare. craft_vs_buy already has a
   proved core (`cheaper_acquisition`) + differential — extend the gate.
2. **Value-normalization (feature):** a `currency_gold_value(code, game_data)`
   numeraire — `gold` → 1; a GE-tradeable currency → its `ge_best_sell_order`
   gold price; non-tradeable → None (undefined, not faked). Enables cross-currency
   cost comparison WHERE DATA EXISTS. New pure-ish core + proofs (nonneg; gold=1;
   monotone in price) + differential.
3. **Arbitrage detection (exploit, largest/most speculative):** find profitable
   loops — buy item with currency A from NPC, sell for gold/currency B (NPC or
   GE) at a net gold-equivalent gain. Needs the numeraire (phase 2) + NPC
   buy/sell + GE order book. New machinery; surface opportunities (a goal or a
   report). Highest uncertainty (depends on whether the live economy actually has
   exploitable spreads; many currencies are soulbound → no loop).

## Proof boundary

* `cheaper_acquisition` is already a proved core — phase 1 keeps it; the currency
  filter is in the impure `acquisition_method` assembly (unit + differential).
* `currency_gold_value` (phase 2): pure core, extracted, proved nonneg + gold=1.
* Arbitrage profit (phase 3): a pure `arbitrage_profit(buy_cost_gold,
  sell_revenue_gold)` core if pursued; the loop discovery is impure I/O.

## Status
* Phase 1 (bug fix) DONE + MERGED (206cb00): npcs_selling_item gold-only;
  gathering non-craftable path uses currency-aware npc_purchases. Latent
  gold-assumption closed; full gate green.
* Phase 2 (numeraire) + Phase 3 (cross-currency arbitrage) ABANDONED as moot.
  Live probe (scripts/probe_currency_arbitrage.py, 2026-06-21) found:
  - 14 non-gold currencies, 10 GE-tradeable, 4 soulbound (sandwhisper_coin,
    tasks_coin, corrupted_gem, malefic_shard).
  - CROSS-CURRENCY arbitrage: **0 spreads** — no tradeable-currency item resells
    above its gold-equivalent cost. So a currency_gold_value numeraire has NO
    consumer (it would be dead code, the dead-gap() anti-pattern). Not built.
  - GOLD-only spreads: 2 real ones — sapphire (GE-buy 645g → resell 1500g,
    +855g), topaz (+835g). These need NO currency normalization (both sides gold);
    they are a SEPARATE potential feature: a "buy-cheap-GE / sell-high" gold-making
    means. Out of #15's scope (currency normalization). Spin as a new task if
    desired (verify the 1500g resale is an NPC-fixed price vs a transient GE buy
    order before relying on it).
* #15 RESOLVED at Phase 1 (the real fix). Normalization/arbitrage moot per live data.
