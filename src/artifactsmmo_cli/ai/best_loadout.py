"""The best consumable loadout against one monster, read from the world
(`docs/PLAN_consumable_utility.md` increment 4). Each loadout's rate is
`loop_rate.loop_rate` (proved arithmetic: `Formal.LoopRate`); the pick is
`best_loadout_core.pick_best` (proved: `Formal.BestLoadout`). The pick reaches
the decisions as a `chosen_loadout.ChosenLoadout` (increment 5).

* CANDIDATE POTIONS — the utility potions the character can use (item level at
  most its level), in the catalogue order of the API item list, whose every
  effect is `restore` or a `boost_*` (the increment-0 table). A
  `splash_restore` potion restores ANOTHER character and an `antipoison` only
  cleanses poison, so neither changes a solo fight's walk: both are left out.
  A candidate must be HELD (bag, bank, utility slots), or have a replacement
  price AND be stockable (`potion_supply.potion_stockable`: the CRAFT_POTIONS
  ladder brews it or the fight step's prep makes it). A potion priced only by a
  route nothing stocks (a GE fill) was chosen and then fought without.
* LOADOUTS — no potions, each candidate alone, and each pair of candidates (in
  candidate order) with at most one `restore` (the turn walk models one restore
  stock). Every potion is walked with a full slot, `UTILITY_SLOT_MAX_STACK`
  units, so the fight is never cut short by the stock; what one fight drinks is
  the walk's `used`.
* FOODS — `loop_rate.food_menu`: held foods and priced foods at the character's
  level, read once for every loadout.
* THE PICK — the highest XP per second; on the same rate the fewer units one
  fight uses (potions drunk plus food eaten); on a full tie the earlier loadout.
  The no-potion loadout consumes nothing, so it is always runnable and there is
  always a pick.

The player reads the pick once per cycle against the fight ahead
(`fight_ahead_loadout`) and threads it on the selection context; every
consumable decision reads it there (`chosen_loadout`, increment 5)."""

from dataclasses import dataclass
from fractions import Fraction

from artifactsmmo_cli.ai.best_loadout_core import pick_best
from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout
from artifactsmmo_cli.ai.consumable_price import replacement_price_of
from artifactsmmo_cli.ai.fight_walk import loadouts, potion_effects_usable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.heal_catalog import POTION
from artifactsmmo_cli.ai.held_stock import held_count
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loop_rate import LoopRate, food_menu, loop_rate
from artifactsmmo_cli.ai.potion_supply import potion_stockable
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.thresholds import UTILITY_SLOT_MAX_STACK
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class BestLoadout:
    """The chosen utility potions, their loop (`rate.used`: the potions one
    fight drinks; `rate.eaten`: the foods its recovery eats) and the no-potion
    loop."""

    loadout: tuple[str, ...]
    rate: LoopRate
    bare: LoopRate


def candidate_potions(state: WorldState, game_data: GameData, ctx: SelectionContext,
                      store: LearningStore | None = None) -> dict[str, Fraction | None]:
    """The candidate potions (see the module doc) with their replacement price,
    in catalogue order."""
    out: dict[str, Fraction | None] = {}
    for code, stats in game_data.items.stats.items():
        if stats.type_ != POTION or stats.level > state.level:
            continue
        if not potion_effects_usable(game_data.effect_codes(code)):
            continue
        price = replacement_price_of(code, state, game_data, ctx, store)
        if held_count(code, state) > 0 or (price is not None
                                           and potion_stockable(code, state, game_data, ctx)):
            out[code] = price
    return out


def best_loadout(state: WorldState, game_data: GameData, ctx: SelectionContext, monster: str,
                 store: LearningStore | None = None) -> BestLoadout:
    """The loadout with the most XP per second against `monster` (see the module doc)."""
    prices = candidate_potions(state, game_data, ctx, store)
    food = food_menu(state, game_data, ctx, store)
    scored: list[tuple[tuple[str, ...], LoopRate]] = []
    for codes in loadouts(list(prices), game_data):
        rate = loop_rate(state, game_data, monster,
                         [(code, UTILITY_SLOT_MAX_STACK) for code in codes], food, prices)
        if rate is not None:
            scored.append((codes, rate))
    index = pick_best([(rate.xp_per_second, units_used(rate)) for _, rate in scored])
    # The no-potion loadout is first and consumes nothing: always runnable.
    assert index is not None and scored[0][0] == ()
    codes, rate = scored[index]
    return BestLoadout(codes, rate, scored[0][1])


def units_used(rate: LoopRate) -> int:
    """Consumable units one fight uses: potions drunk plus food eaten."""
    return sum(n for _, n in rate.used) + sum(n for _, n in rate.eaten)


def chosen(best: BestLoadout, monster: str) -> ChosenLoadout:
    """The pick as plain data: the potions one fight drinks and the food its
    recovery eats."""
    return ChosenLoadout(monster, tuple((code, n) for code, n in best.rate.used if n > 0),
                         best.rate.eaten)


def fight_ahead_loadout(state: WorldState, game_data: GameData, ctx: SelectionContext,
                        store: LearningStore | None) -> ChosenLoadout | None:
    """The pick against the fight ahead — the committed intention's next fight
    (`ctx.fight_monster`), else the grind target (`ctx.combat_monster`) — or
    None with neither."""
    monster = ctx.fight_monster or ctx.combat_monster
    if monster is None:
        return None
    return chosen(best_loadout(state, game_data, ctx, monster, store), monster)


def loadout_for(state: WorldState, game_data: GameData, ctx: SelectionContext,
                monster: str) -> ChosenLoadout:
    """The pick against `monster`: the cycle's own (`ctx.loadout`) when it was
    chosen against that monster, else chosen now. A fight other than the one
    ahead (a grind's drop fight) is priced without the learning store, which
    the context does not carry."""
    if ctx.loadout is not None and ctx.loadout.monster == monster:
        return ctx.loadout
    return chosen(best_loadout(state, game_data, ctx, monster), monster)
