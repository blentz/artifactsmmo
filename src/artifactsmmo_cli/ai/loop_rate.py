"""The fight loop's XP rate for one monster and one utility loadout, read from
the world (`docs/PLAN_consumable_utility.md` increments 3-4). The arithmetic is
`loop_rate_core` (proved: `Formal.LoopRate`) and the fight is
`fight_outcome_core.fight_outcome` (proved: `Formal.FightOutcome`); this module
assembles their inputs. Not wired into any decision yet.

ONE LOOP is a fight from full HP, the recovery back to full, and the price of
what the fight consumed (the steady state of a grind: every fight after the
first starts where the last recovery left it, at full).

* THE LOADOUT is what the two utility slots wear for the fight — up to two
  `(code, stock)` utility potions, at most one of them a `restore` (the turn walk
  models one restore stock; two different restores would fire in the same turn).
  A `splash_restore` potion heals another character and is refused.
  Each slot is projected through `boost_selection.project_equip`, the path the
  boost choice already uses, and a slot the loadout leaves empty is emptied, so
  "no potions" really is no potions (`combat_terms` would otherwise pick a bag
  boost into the slot).
* THE FIGHT — `combat.combat_terms` over the projected state, walked by
  `fight_outcome` from the projected max HP (`combat.fight_max_hp`, the max the
  terms are built over) with the restore's stock. Its duration is ONE
  `TYPICAL_FIGHT_COOLDOWN_SECONDS` (30 s): the code has no per-round seconds,
  and the fight cooldown it already prices is per fight.
* CONSUMED — the restore potions the walk drank, and one of each boost (the
  increment-0 data: one boost per fight). USER 2026-10-09, "free until used
  up": the drinks up to the units HELD (`held_stock.held_count`: bag,
  bank, utility slots) are free, every further one costs its replacement
  (`prices`, from `consumable_price.replacement_price_of`);
  `loop_rate_core.consumed_seconds`. A drink past the held units with no
  replacement makes the loop unrunnable: the result is None.
* RECOVERY — `recovery_choice` of the missing HP (`max_hp − hp_end`, the end
  pool floored to whole HP) over the FOOD MENU (`food_menu`), eaten at the flat
  `CONSUMABLE_COOLDOWN_SECONDS`; the units it eats are the loop's `eaten`.
* XP — `game_data.xp_per_kill` at the character's level and wisdom on a win;
  0 on a loss."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

from artifactsmmo_cli.ai.actions.cost_core import CONSUMABLE_COOLDOWN_SECONDS
from artifactsmmo_cli.ai.consumable_price import FIGHT_SECONDS, replacement_price_of
from artifactsmmo_cli.ai.fight_terms_core import SCALE
from artifactsmmo_cli.ai.fight_walk import fight_walk
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.heal_catalog import FOOD, heal_candidates
from artifactsmmo_cli.ai.held_stock import held_count
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loop_rate_core import consumed_seconds, recovery_choice, xp_per_second
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

EAT_SECONDS = Fraction(CONSUMABLE_COOLDOWN_SECONDS)
"""One use of a food, whatever the quantity, exact."""



@dataclass(frozen=True)
class FoodOffer:
    """One food on the recovery menu: its HP, its replacement price in seconds
    (None: no route to more) and the units held."""

    code: str
    restore: int
    price: Fraction | None
    held: int


@dataclass(frozen=True)
class LoopRate:
    """One loop's XP rate and its parts (seconds exact, HP whole). `used` is the
    units of each loadout potion one fight drinks, `eaten` the units of each food
    its recovery eats (only the foods it eats)."""

    xp_per_second: Fraction
    xp_per_kill: int
    win: bool
    fight_seconds: Fraction
    recovery_seconds: Fraction
    consumed_seconds: Fraction
    max_hp: int
    hp_end: int
    used: tuple[tuple[str, int], ...]
    eaten: tuple[tuple[str, int], ...]


def food_menu(state: WorldState, game_data: GameData, ctx: SelectionContext,
              store: LearningStore | None = None) -> tuple[FoodOffer, ...]:
    """The foods the character can eat (item level at most its level: the API
    refuses a consumable above the character's level), in catalogue order, that
    are held (bag or bank) or have a replacement price."""
    menu: list[FoodOffer] = []
    for code in heal_candidates(game_data, FOOD):
        stats = game_data.items.stats[code]
        if stats.level > state.level:
            continue
        held = held_count(code, state)
        price = replacement_price_of(code, state, game_data, ctx, store)
        if held > 0 or price is not None:
            menu.append(FoodOffer(code, stats.hp_restore, price, held))
    return tuple(menu)


def loop_rate(state: WorldState, game_data: GameData, monster: str,
              loadout: Sequence[tuple[str, int]], food: Sequence[FoodOffer],
              prices: Mapping[str, Fraction | None]) -> LoopRate | None:
    """The loop's XP per second against `monster` wearing `loadout` and
    recovering over `food` (see the module doc); `prices` holds every loadout
    potion's replacement price. None when a drink past the held units has no
    replacement."""
    outcome, max_hp, restore_code = fight_walk(state, game_data, monster, loadout)
    used = tuple((code, outcome.used if code == restore_code else 1) for code, _ in loadout)
    consumed = consumed_seconds([(n, prices[code], held_count(code, state)) for code, n in used])
    if consumed is None:
        return None
    hp_end = outcome.hp_end // SCALE
    recovery, counts = recovery_choice(max_hp - hp_end, max_hp,
                                       [(f.restore, f.price, f.held) for f in food], EAT_SECONDS)
    eaten = tuple((f.code, k) for f, k in zip(food, counts, strict=True) if k > 0)
    xp = game_data.xp_per_kill(monster, state.level, state.wisdom) if outcome.win else 0
    return LoopRate(xp_per_second(xp, FIGHT_SECONDS, recovery, consumed), xp, outcome.win,
                    FIGHT_SECONDS, recovery, consumed, max_hp, hp_end, used, eaten)
