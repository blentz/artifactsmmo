#!/usr/bin/env python
"""READ-ONLY probe: does the live economy have currency arbitrage worth modelling?

#15 Phase 2/3 (value-normalization + arbitrage) only earns its keep if there are
real cross-currency or gold spreads to exploit. This loads live game data and
reports:

  1. every non-gold currency in use, and whether it is GE-tradeable (has a gold
     price — the precondition for a gold-equivalent numeraire);
  2. GOLD spreads: items whose best gold ACQUISITION (NPC buy / GE sell order)
     is strictly cheaper than their best gold RESALE (NPC sell-to / GE buy order);
  3. CROSS-CURRENCY spreads: items bought from an NPC for a non-gold currency,
     resold for gold above the gold-equivalent cost of that currency.

No character mutation — pure data inspection. Usage:
    uv run python scripts/probe_currency_arbitrage.py
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config


def _gold_resale(gd: GameData, item: str) -> int:
    """Best immediate gold from selling one unit: max(NPC buy price, GE buy order)."""
    best = 0
    buyers = gd.npcs_buying_item(item)
    if buyers:
        best = max(best, buyers[0][1])
    order = gd.ge_best_buy_order(item)
    if order is not None:
        best = max(best, order[1])
    return best


def _ge_acquire_cost(gd: GameData, item: str) -> int | None:
    """Gold to BUY one unit from the cheapest standing GE sell order, or None."""
    order = gd.ge_best_sell_order(item)
    return order[1] if order is not None else None


def main() -> None:
    cm = ClientManager()
    cm.initialize(Config.from_token_file())
    gd = GameData.load(cm.client)

    # (1) currencies in use + GE-tradeability.
    currencies: set[str] = set()
    for stock in gd._npc_buy_currency.values():
        for currency in stock.values():
            if currency and currency != "gold":
                currencies.add(currency)
    print("=== non-gold currencies in use ===")
    if not currencies:
        print("  NONE — every NPC sells for gold. No cross-currency arbitrage possible.")
    tradeable: dict[str, int] = {}
    for c in sorted(currencies):
        sell = gd.ge_best_sell_order(c)   # gold to buy 1 unit of the currency item
        buy = gd.ge_best_buy_order(c)     # gold from selling 1 unit
        ge = f"GE sell@{sell[1]} buy@{buy[1]}" if (sell and buy) else (
            f"GE sell@{sell[1]}" if sell else (f"GE buy@{buy[1]}" if buy else "NOT GE-tradeable"))
        if sell:
            tradeable[c] = sell[1]
        print(f"  {c}: {ge}")

    # (2) gold spreads.
    print("\n=== GOLD spreads (acquire < resale) ===")
    gold_hits = 0
    for npc, stock in gd._npc_buy_currency.items():
        for item, currency in stock.items():
            if currency != "gold":
                continue
            acquire = gd._npc_stock.get(npc, {}).get(item)
            if acquire is None:
                continue
            resale = _gold_resale(gd, item)
            if resale > acquire:
                gold_hits += 1
                print(f"  {item}: buy {acquire}g ({npc}) → resell {resale}g  (+{resale - acquire}g)")
    # also GE-sell-order acquire vs NPC/GE resale
    for item in gd.all_item_stats:
        acquire = _ge_acquire_cost(gd, item)
        if acquire is None:
            continue
        resale = _gold_resale(gd, item)
        if resale > acquire:
            gold_hits += 1
            print(f"  {item}: GE-buy {acquire}g → resell {resale}g  (+{resale - acquire}g)")
    if gold_hits == 0:
        print("  NONE.")

    # (3) cross-currency spreads.
    print("\n=== CROSS-CURRENCY spreads (non-gold buy → gold resale > gold-equiv cost) ===")
    cross_hits = 0
    for npc, stock in gd._npc_buy_currency.items():
        for item, currency in stock.items():
            if currency == "gold" or currency not in tradeable:
                continue
            buy_units = gd._npc_stock.get(npc, {}).get(item)
            if buy_units is None:
                continue
            gold_cost = buy_units * tradeable[currency]
            resale = _gold_resale(gd, item)
            if resale > gold_cost:
                cross_hits += 1
                print(f"  {item}: {buy_units} {currency} (~{gold_cost}g) → resell {resale}g  (+{resale - gold_cost}g)")
    if cross_hits == 0:
        print("  NONE (no tradeable-currency item resells above its gold-equivalent cost).")

    print(f"\nSUMMARY: {len(currencies)} non-gold currencies "
          f"({len(tradeable)} GE-tradeable); {gold_hits} gold spreads; {cross_hits} cross-currency spreads.")
    if gold_hits == 0 and cross_hits == 0:
        print("→ No arbitrage in the live economy. #15 can stop at the Phase-1 bug fix.")


if __name__ == "__main__":
    main()
