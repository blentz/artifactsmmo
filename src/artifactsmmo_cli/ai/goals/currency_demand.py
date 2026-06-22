"""Shared detection of an unaffordable currency-buy leaf in a recipe closure.

A "currency-buy leaf" is a recipe input that can ONLY be acquired by buying it
from an NPC against a non-gold currency (e.g. jasper_crystal @ tasks_trader for
8 tasks_coin). Such a leaf is:
  - not itself a requested item (`needed`),
  - has no crafting recipe,
  - is not a resource drop,
  - is dropped by no monster,
  - is sold by at least one NPC (npc_purchases non-empty).

A leaf is AFFORDABLE when some vendor offers it at a currency price the
character can cover from inventory + bank (>= price * closure_qty).

Two consumers share this ONE closure + predicate (DRY):
  - GatherMaterialsGoal.is_plannable fast-fails when any such leaf is
    unaffordable (currency_afford_plannable_pure is the proved live decision).
  - The arbiter (objective_step_goal) routes to ReachCurrencyGoal to FUND the
    currency when a leaf is unaffordable, instead of selecting an unplannable
    GatherMaterials.

`first_unaffordable_currency_leaf` returns (currency, price*qty) for the FIRST
such unaffordable leaf, or None when every currency-buy leaf is affordable.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.currency_afford_core import currency_afford_plannable_pure
from artifactsmmo_cli.ai.recipe_closure import closure_demand
from artifactsmmo_cli.ai.world_state import WorldState


def first_unaffordable_currency_leaf(
    needed: dict[str, int], state: WorldState, game_data: GameData
) -> tuple[str, int] | None:
    """Build the recipe closure of `needed` and return (currency, required_amount)
    for the FIRST currency-buy leaf the character cannot afford, else None.

    required_amount = cheapest affordable-targeted vendor price * closure_qty
    for the leaf; specifically the price of the cheapest vendor offering it (the
    funding target the arbiter routes ReachCurrencyGoal to). When the leaf has
    multiple vendors with the same currency, the minimum price * qty is used.
    """
    bank = state.bank_items or {}
    chain: dict[str, int] = {}
    for code, qty in needed.items():
        closure_demand(code, qty, game_data, chain, frozenset())
    for leaf, qty in chain.items():
        if leaf in needed:
            continue
        if game_data.crafting_recipe(leaf) is not None:
            continue
        if leaf in game_data.resource_drops.values():
            continue
        if game_data.monsters_dropping(leaf):
            continue
        purchases = game_data.npc_purchases(leaf)
        if not purchases:
            continue
        owned = state.inventory.get(leaf, 0) + bank.get(leaf, 0)
        affordable = any(
            (state.inventory.get(currency, 0) + bank.get(currency, 0)) >= price * qty
            for _npc, price, currency in purchases
        )
        # currency_afford_plannable_pure is the proved live decision: a leaf is
        # only blocking when not affordable AND not already owned in sufficient
        # quantity (an owned leaf needs no purchase). True ⇒ not blocking.
        if currency_afford_plannable_pure(True, affordable, owned, qty):
            continue
        # Blocking unaffordable leaf: pick the cheapest vendor as the funding
        # target (the currency amount ReachCurrencyGoal must reach).
        _npc, price, currency = min(purchases, key=lambda p: p[1])
        return currency, price * qty
    return None
