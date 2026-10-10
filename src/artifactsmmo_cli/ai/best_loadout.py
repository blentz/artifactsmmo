"""The best consumable loadout against one monster, read from the world
(`docs/PLAN_consumable_utility.md` increment 4). Each loadout's rate is
`loop_rate.loop_rate` (proved arithmetic: `Formal.LoopRate`); the pick is
`best_loadout_core.pick_best` (proved: `Formal.BestLoadout`). Not wired into
any decision yet (increment 5 equips it).

* CANDIDATE POTIONS — the utility potions the character can use (item level at
  most its level), in the catalogue order of the API item list, whose every
  effect is `restore` or a `boost_*` (the increment-0 table). A
  `splash_restore` potion restores ANOTHER character and an `antipoison` only
  cleanses poison, so neither changes a solo fight's walk: both are left out.
  A candidate must be HELD (bag, bank, utility slots) or have a replacement
  price — exactly the potions `consumable_price.consumable_price_of` prices.
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
  always a pick."""

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from artifactsmmo_cli.ai.best_loadout_core import pick_best
from artifactsmmo_cli.ai.consumable_floor import POTION
from artifactsmmo_cli.ai.consumable_price import held_count, replacement_price_of
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loop_rate import LoopRate, food_menu, loop_rate
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.thresholds import UTILITY_SLOT_MAX_STACK
from artifactsmmo_cli.ai.world_state import WorldState

RESTORE = "restore"
"""The API effect of a self-heal utility potion (increment-0 table)."""

BOOST_PREFIX = "boost_"
"""The API effects of a stat-buff utility potion (`boost_dmg_*`, `boost_res_*`,
`boost_hp`)."""


@dataclass(frozen=True)
class BestLoadout:
    """The chosen utility potions, their loop, and what one fight uses: the
    potions it drinks and the foods its recovery eats, units per code."""

    loadout: tuple[str, ...]
    rate: LoopRate
    bare: LoopRate
    per_fight: tuple[tuple[str, int], ...]


def potion_effects_usable(codes: Sequence[str]) -> bool:
    """Every effect changes the wearer's own fight: a `restore` or a boost."""
    return bool(codes) and all(c == RESTORE or c.startswith(BOOST_PREFIX) for c in codes)


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
        if held_count(code, state) > 0 or price is not None:
            out[code] = price
    return out


def loadouts(candidates: Sequence[str], game_data: GameData) -> list[tuple[str, ...]]:
    """No potions, each candidate, then each pair with at most one restore."""
    out: list[tuple[str, ...]] = [()]
    out += [(code,) for code in candidates]
    for i, first in enumerate(candidates):
        for second in candidates[i + 1:]:
            restores = sum(RESTORE in game_data.effect_codes(c) for c in (first, second))
            if restores <= 1:
                out.append((first, second))
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
    per_fight = tuple((code, n) for code, n in rate.used if n > 0) + rate.eaten
    return BestLoadout(codes, rate, scored[0][1], per_fight)


def units_used(rate: LoopRate) -> int:
    """Consumable units one fight uses: potions drunk plus food eaten."""
    return sum(n for _, n in rate.used) + sum(n for _, n in rate.eaten)
