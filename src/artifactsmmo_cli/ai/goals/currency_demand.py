"""Shared analysis of currency-buy leaves in a recipe closure.

A "currency-buy leaf" is a closure member (a recipe input OR the requested
item itself) that can ONLY be acquired by buying it from an NPC against a
currency (e.g. jasper_crystal @ tasks_trader for 8 tasks_coin). Such a leaf:
  - has no crafting recipe,
  - is not a resource drop,
  - is dropped by no monster,
  - is sold by at least one NPC (npc_purchases non-empty).

A leaf is AFFORDABLE when some PERMANENT, located vendor offers it at a currency
price the character can cover from inventory + bank (>= price * closure_qty).
Event/unlocated vendors are excluded — `relevant_actions` emits no NpcBuy for
them, so they must not count as a usable purchase path (closure + vendor set kept
symmetric with GatherMaterialsGoal.relevant_actions).

ONE closure walk serves two consumers (DRY), each reading a DIFFERENT signal:
  - `blocked`  — GatherMaterialsGoal.is_plannable fast-fails when any currency-buy
    leaf is unaffordable (currency_afford_plannable_pure is the proved live
    decision). A leaf with no usable vendor at all is also blocking.
  - `funding_target` — the arbiter routes ReachCurrencyGoal to FUND the currency.
    This fires ONLY for a leaf whose currency is `tasks_coin` (the currency
    ReachCurrencyGoal can actually produce by completing tasks — C2
    CompleteTaskAction mints tasks_coin, nothing else). A leaf priced in gold or
    a non-task currency is `blocked` when unaffordable, but is NOT a funding
    target — ReachCurrencyGoal cannot earn that currency, so routing to it would
    chase an unfundable goal; the bot earns gold/other currencies by its normal
    means instead. Among the leaf's eligible vendors, the one with the FEWEST
    funding cycles (proved `funding_cycles_pure`) is chosen — a semantic key, not
    raw price, so a cheap vendor in a currency the character barely holds does not
    out-rank a slightly pricier vendor in a currency already mostly funded.
"""
from typing import NamedTuple

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.currency_afford_core import currency_afford_plannable_pure
from artifactsmmo_cli.ai.goals.funding_core import funding_cycles_pure
from artifactsmmo_cli.ai.recipe_closure import closure_demand
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState


class CurrencyLeafAnalysis(NamedTuple):
    """Result of walking a recipe closure for currency-buy leaves.

    `blocked`: at least one currency-buy leaf is unaffordable (and unowned) via
    every usable vendor — GatherMaterialsGoal.is_plannable must prune.
    `funding_target`: (tasks_coin, required_amount) for the FIRST unaffordable
    leaf the arbiter can fund via ReachCurrencyGoal, or None when no unaffordable
    leaf is tasks_coin-funded.
    """

    blocked: bool
    funding_target: tuple[str, int] | None


def analyze_currency_leaves(
    needed: dict[str, int], state: WorldState, game_data: GameData
) -> CurrencyLeafAnalysis:
    """Walk the recipe closure of `needed` once, returning the `blocked` signal
    (for is_plannable) and the `funding_target` (for the arbiter)."""
    bank = state.bank_items or {}
    chain: dict[str, int] = {}
    for code, qty in needed.items():
        closure_demand(code, qty, game_data, chain, frozenset())

    blocked = False
    funding_target: tuple[str, int] | None = None

    for leaf, qty in chain.items():
        # The requested item ITSELF is analyzed too: stepwise decomposition
        # hands the mapper the currency item directly once every other input
        # is in hand (satchel -> ... -> ObtainItem(jasper_crystal)), and the
        # old `leaf in needed` exclusion silenced funding exactly at that
        # final step (live satchel stall 2026-07-06). Craftable / gatherable /
        # monster-dropped requests still skip via the guards below.
        if game_data.crafting_recipe(leaf) is not None:
            continue
        if leaf in game_data.resource_drops.values():
            continue
        if game_data.monsters_dropping(leaf):
            continue
        purchases = game_data.npc_purchases(leaf)
        if not purchases:
            continue
        # PERMANENT, located vendors only — matching relevant_actions' guard, so
        # the affordability view and the emitted action set use the same vendors.
        permanent = [
            (npc, price, currency)
            for npc, price, currency in purchases
            if not game_data.is_event_npc(npc) and game_data.npc_location(npc) is not None
        ]
        owned = state.inventory.get(leaf, 0) + bank.get(leaf, 0)
        affordable = any(
            (state.inventory.get(currency, 0) + bank.get(currency, 0)) >= price * qty
            for _npc, price, currency in permanent
        )
        # currency_afford_plannable_pure is the proved live decision: a leaf is
        # only blocking when not affordable AND not already owned in sufficient
        # quantity. True ⇒ not blocking (affordable or owned, or no closure need).
        if currency_afford_plannable_pure(True, affordable, owned, qty):
            continue

        blocked = True  # is_plannable must prune; the leaf cannot be acquired now.

        # Fundable ONLY via tasks_coin — the currency ReachCurrencyGoal produces.
        fundable = [
            (npc, price, currency)
            for npc, price, currency in permanent
            if currency == TASKS_COIN_CODE
        ]
        if not fundable:
            continue  # gold/event/non-task currency leaf: blocked but unfundable;
            #           keep scanning for a later tasks_coin-funded blocking leaf.

        floor = game_data.min_task_coin_reward()  # ≥1, enforced at load (C2)
        # Pick the vendor needing the FEWEST funding cycles (semantic, proved
        # core), tiebreak by cheaper target then by most currency already held.
        # `min(key=s[0])` compares ONLY the semantic key; genuine ties fall to
        # iteration (vendor-data) order — never a repr/alphabetical sort.
        scored = []
        for _npc, price, currency in fundable:
            target = price * qty
            on_hand = state.inventory.get(currency, 0) + bank.get(currency, 0)
            key = (funding_cycles_pure(on_hand, target, floor), target, -on_hand)
            scored.append((key, currency, target))
        _key, best_currency, best_target = min(scored, key=lambda s: s[0])
        funding_target = (best_currency, best_target)
        break  # blocked is already True and we have the FIRST fundable target.

    return CurrencyLeafAnalysis(blocked=blocked, funding_target=funding_target)
