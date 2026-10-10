"""The price of one consumable, in seconds, read from the world
(`docs/PLAN_consumable_utility.md` increment 2). The arithmetic is
`consumable_price_core.consumable_price` (proved: `Formal.ConsumablePrice`);
this module only reads its four inputs. Not wired into any decision yet.

* HELD — bag + bank + the utility slots that wear it (the USER's ruling: "held
  stock (bag, bank, utility slots) is free").
* MAKE — the acquisition walk (`acquisition_cost.acquisition_actions`, one unit,
  not equipped) in fight-equivalent actions, times
  `TYPICAL_FIGHT_COOLDOWN_SECONDS` (the walk's unit is one Fight, as
  `fight_loop_cost` declares). A walk at or past `UNOBTAINABLE_PER_UNIT` has no
  route: no make side. The walk prices EVERY route `obtain_sources` names,
  including a gold vendor paid from the pocket, so "make" is the cheapest way to
  obtain it in actions, not only crafting.
* BUY — the cheapest current gold price for one unit over the `BUY` (gold
  currency) and `GE_FILL` sources `obtain_sources` names, re-read through
  `acquisition_cost.npc_price_of` / `ge_price_of` exactly as the walk prices
  them. A vendor charging another currency is not a gold price.
* GOLD RATE — the grind target's fight gold per loop cycle
  (`task_worth.fight_gold_rate` over `ctx.combat_monster`, the rate task worth
  reads) over `TYPICAL_FIGHT_COOLDOWN_SECONDS`; 0 with no grind target, which
  makes buying unpriceable."""

from fractions import Fraction

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions, ge_price_of, npc_price_of
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.consumable_price_core import consumable_price
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.held_stock import held_count
from artifactsmmo_cli.ai.learning.fight_loop_cost import TYPICAL_FIGHT_COOLDOWN_SECONDS
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.obtain_sources import SourceKind, obtain_sources
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.task_worth import fight_gold_rate
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState

FIGHT_SECONDS = Fraction(TYPICAL_FIGHT_COOLDOWN_SECONDS)
"""Seconds in one fight-equivalent action, exact."""


def make_seconds(code: str, state: WorldState, game_data: GameData, ctx: SelectionContext,
                 store: LearningStore | None) -> Fraction | None:
    """The acquisition walk for one unit in seconds; None when it has no route."""
    actions = acquisition_actions(code, 1, state, game_data, ctx, equip=False, store=store)
    if actions >= UNOBTAINABLE_PER_UNIT:
        return None
    return actions * FIGHT_SECONDS


def buy_gold(code: str, state: WorldState, game_data: GameData,
             ctx: SelectionContext) -> int | None:
    """The cheapest current gold price of one unit; None when nobody sells it for gold."""
    prices: list[int] = []
    for source in obtain_sources(code, state, game_data, ctx):
        if source.kind is SourceKind.BUY:
            price, currency = npc_price_of(code, source.code, game_data)
            if currency == GOLD_CODE:
                prices.append(price)
        elif source.kind is SourceKind.GE_FILL:
            prices.append(ge_price_of(code, source.code, game_data))
    return min(prices) if prices else None


def gold_per_second(state: WorldState, game_data: GameData, ctx: SelectionContext) -> Fraction:
    """The grind target's fight gold per second; 0 with no grind target."""
    if ctx.combat_monster is None:
        return Fraction(0)
    return fight_gold_rate(state, game_data, ctx.combat_monster) / FIGHT_SECONDS


def replacement_price_of(code: str, state: WorldState, game_data: GameData,
                         ctx: SelectionContext,
                         store: LearningStore | None = None) -> Fraction | None:
    """The price in seconds of a unit PAST the held stock: the cheaper of making
    and buying it, as if none were held (USER 2026-10-09, "free until used up";
    further units cost replacement). None when neither side is available."""
    return consumable_price(0, make_seconds(code, state, game_data, ctx, store),
                            buy_gold(code, state, game_data, ctx),
                            gold_per_second(state, game_data, ctx))


def consumable_price_of(code: str, state: WorldState, game_data: GameData,
                        ctx: SelectionContext,
                        store: LearningStore | None = None) -> Fraction | None:
    """The price in seconds of one more unit of `code` (see the module doc).
    Held stock reads nothing else: it is free whatever the other sides say."""
    if held_count(code, state) > 0:
        return Fraction(0)
    return replacement_price_of(code, state, game_data, ctx, store)
