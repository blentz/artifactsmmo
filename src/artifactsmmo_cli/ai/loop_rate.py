"""The fight loop's XP rate for one monster and one utility loadout, read from
the world (`docs/PLAN_consumable_utility.md` increments 3-4). The arithmetic is
`loop_rate_core` (proved: `Formal.LoopRate`) and the fight is
`fight_outcome_core.fight_outcome` (proved: `Formal.FightOutcome`); this module
assembles their inputs.

ONE LOOP is a fight from full HP, the recovery back to full, and the price of
what the fight consumed (the steady state of a grind: every fight after the
first starts where the last recovery left it, at full). The fight is walked
over every crit ending (`fight_walk.odds_walk`, spec 2026-10-15 fight-odds §2):
the loop's recovery and consumed seconds are EXPECTATIONS over the endings, a
lost fight recovers from `LOSS_HP` and walks back from `RESPAWN_TILE` to the
nearest spawn tile (needed only when a loss is possible; the tiles are the
factory's FightAction tiles on every layer, `fight_tiles.fight_tiles`), and the rate is
renewal-reward: `p_win x xp / (fight + expected recovery + consumed + walk)`.

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
  terms are built over) with the restore's stock. Its duration is the learned
  fight seconds at the walk's expected server turns and the loadout's haste
  (`fight_walk.walk_seconds`, spec 2026-10-18 §2.9): a faster kill is a
  shorter fight, so kill speed pays.
* CONSUMED — the restore potions the walk drank, and one of each boost (the
  increment-0 data: one boost per fight). USER 2026-10-09, "free until used
  up": the drinks up to the units HELD (`held_stock.held_count`: bag,
  bank, utility slots) are free, every further one costs its replacement
  (`prices`, from `consumable_price.replacement_price_of`);
  `loop_rate_core.consumed_seconds`, per crit ending. A potion with NO
  replacement is paid on its expectation instead (final review I1 ruling): the
  loop is unrunnable (None) when its expected drinks, rounded up, exceed the
  units held — a rare deep ending that drinks past them does not veto it.
* RECOVERY — `recovery_choice` of the missing HP (`max_hp − hp_end`, the end
  pool floored to whole HP) over the FOOD MENU (`food_menu`), eaten at the flat
  `CONSUMABLE_COOLDOWN_SECONDS`; the units it eats are the loop's `eaten`.
* XP — `game_data.xp_per_kill` at the character's level and wisdom on a win
  (`LoopRate.p_win` weights it); 0 on a loss. `used`/`eaten` are the expected
  units rounded up, `hp_end` the expected end HP rounded down.
* BANK TRIPS (spec 2026-10-18 §2.10) — the drops fill the bag and a full bag
  is a trip to the bank, so each fight carries `loop_rate_core.trip_share`
  seconds of trips. A fight's drops are its win odds times every drop of the
  monster at its learned units per attempt (`LearnedDrops.units_per_attempt`,
  the one drop model) at the prospecting the fight is fought in
  (`combat.fight_stats`). The room for them is the bag cap of that loadout
  (a worn bag raises it) less what the bag carries through a deposit: the
  keep's other units (`carried`, `inventory_keep.carried_keep`), the carry of
  the food the recovery eats (`chosen_loadout.food_carry`) and the potion
  carry the utility slots do not hold (`chosen_loadout.potion_carry` less the
  stock worn). A trip walks from the monster's tile nearest the bank to the
  bank (`GameData.bank_location`) and back, and pays one deposit
  (`cost_core.DEPOSIT_SECONDS_PER_CODE`) per distinct drop code. A loop with
  drops and no room for them does not run (`LoopRate.runnable` False, no XP a
  second); one with no drops makes no trip and needs no bank."""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

from artifactsmmo_cli.ai.actions.cost_core import (
    CONSUMABLE_COOLDOWN_SECONDS,
    DEPOSIT_SECONDS_PER_CODE,
    travel_seconds,
)
from artifactsmmo_cli.ai.chosen_loadout import food_carry, potion_carry
from artifactsmmo_cli.ai.combat import fight_stats
from artifactsmmo_cli.ai.consumable_price import replacement_price_of
from artifactsmmo_cli.ai.fight_odds_core import win_probability as odds_win
from artifactsmmo_cli.ai.fight_seconds_core import FightSecondsModel
from artifactsmmo_cli.ai.fight_terms_core import SCALE
from artifactsmmo_cli.ai.fight_tiles import fight_tiles
from artifactsmmo_cli.ai.fight_walk import fight_walk, odds_walk, walk_seconds, wear
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.heal_catalog import FOOD, heal_candidates
from artifactsmmo_cli.ai.held_stock import held_count
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loop_rate_core import (
    consumed_seconds,
    drops_per_fight,
    expected_xp_per_second,
    recovery_choice,
    trip_seconds,
    trip_share,
)
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

EAT_SECONDS = Fraction(CONSUMABLE_COOLDOWN_SECONDS)
"""One use of a food, whatever the quantity, exact."""

RESPAWN_TILE = (0, 0)
"""Where the server puts a character that lost a fight (learning.db 2026-10-15:
every R2D2 owlbear `error:fight_lost` row ends at (0, 0) with hp = 1). Observed
server behaviour, not API data (spec 2026-10-15 fight-odds §2 ruling)."""

LOSS_HP = 1
"""The HP a lost fight leaves (`learning/fight_loop_cost.loss_cost`, live 2026-10-08)."""


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
    """One loop's expected XP rate and its parts (seconds exact, HP whole).
    `p_win` is the fight's win probability; `win` the plain one-walk yes/no.
    `recovery_seconds` and `consumed_seconds` are EXPECTATIONS over the fight's
    endings (a loss recovers from `LOSS_HP`); the walk back from the respawn
    tile appears only in `xp_per_second`. `used` is the units of each loadout
    potion one fight drinks and `eaten` the units of each food its recovery eats
    (only the foods it eats), both the expectation rounded UP; `hp_end` is the
    expected end HP rounded down. `xp_per_kill` is the kill's XP when the
    fight can be won (`p_win > 0`) and 0 when it cannot: the XP a win pays,
    not an expectation (`xp_per_second` carries the `p_win` weight).
    `runnable` is False when the fight drops something and the bag has no room
    for it (spec 2026-10-18 §2.10): the loop cannot run, so it earns nothing
    (`xp_per_second` 0) while its fight, recovery and consumables are still
    the ones it would take. The ONE verdict a fight against that monster is
    refused on (`fight_room_license`)."""

    xp_per_second: Fraction
    xp_per_kill: int
    win: bool
    p_win: Fraction
    fight_seconds: Fraction
    recovery_seconds: Fraction
    consumed_seconds: Fraction
    max_hp: int
    hp_end: int
    used: tuple[tuple[str, int], ...]
    eaten: tuple[tuple[str, int], ...]
    runnable: bool


@dataclass(frozen=True)
class LoopInputs:
    """What every loop of one character's cycle reads alike, whatever the
    monster or the gear: the learned fight seconds, the cycle's drop evidence
    and the units the keep holds in the bag (`inventory_keep.carried_keep`)."""

    timing: FightSecondsModel
    drops: LearnedDrops
    carried: int


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


def monster_tile(state: WorldState, game_data: GameData, monster: str) -> tuple[int, int]:
    """The monster's fight tile nearest the respawn tile: where a loss walks back
    to. The tiles are every layer's (`fight_tiles`); the walk is priced on the
    tile's (x, y) alone, so a walk back into an interior or the underground is
    under-priced by its layer transitions (a residual of spec 2026-10-15 §2)."""
    tiles = fight_tiles(state, game_data, monster)
    if not tiles:
        raise ValueError(f"{monster} has no spawn tile: a loss's walk back cannot be priced")
    return min(tiles, key=lambda tile: (travel_seconds(RESPAWN_TILE, tile), tile))


def bank_walk(state: WorldState, game_data: GameData, monster: str) -> int:
    """The walk from the monster's fight tile nearest the bank to the bank
    (`GameData.bank_location`, which raises when the map has none): half a bank
    trip. The tiles are every layer's (`fight_tiles`), priced on their (x, y)
    alone, as the walk back from a loss is (`monster_tile`)."""
    tiles = fight_tiles(state, game_data, monster)
    if not tiles:
        raise ValueError(f"{monster} has no spawn tile: a bank trip cannot be priced")
    bank = game_data.bank_location()
    return min(travel_seconds(tile, bank) for tile in tiles)


def loop_rate(state: WorldState, game_data: GameData, monster: str,
              loadout: Sequence[tuple[str, int]], food: Sequence[FoodOffer],
              prices: Mapping[str, Fraction | None],
              timing: FightSecondsModel, drops: LearnedDrops, carried: int) -> LoopRate | None:
    """The loop's expected XP per second against `monster` wearing `loadout` and
    recovering over `food` (see the module doc): every crit ending of the fight
    is priced (`odds_walk`), a loss walks back from `RESPAWN_TILE`, the
    fight lasts `walk_seconds` under `timing`, and the bank trips its drops
    force are shared over the fights between them, the drops priced on
    `drops` and the bag's room less `carried`, the units the keep holds in it
    other than food and potions (`inventory_keep.carried_keep`). `prices` holds
    every loadout potion's replacement price. None when a potion with no
    replacement is expected (rounded up) to be drunk past the held units. A
    fight that drops something into a bag with no room for it is a loop that
    does not run: `runnable` False and no XP a second."""
    outcome, max_hp, restore_code = fight_walk(state, game_data, monster, loadout)
    endings, _, _ = odds_walk(state, game_data, monster, loadout)
    p_win = odds_win(endings)
    menu = [(f.restore, f.price, f.held) for f in food]
    extra = Fraction(0)
    if p_win < 1:
        extra = (1 - p_win) * travel_seconds(RESPAWN_TILE, monster_tile(state, game_data, monster))
    held = {code: held_count(code, state) for code, _ in loadout}
    used_mean = {code: Fraction(0) for code, _ in loadout}
    eaten_mean = [Fraction(0)] * len(food)
    recovery_mean = consumed_mean = hp_end_mean = Fraction(0)
    for e in endings:
        used = tuple((code, e.used if code == restore_code else 1) for code, _ in loadout)
        # A potion with no replacement is paid on its expectation (below), so no
        # single ending prices it: only the priced ones enter, and a priced
        # drink always has a price.
        consumed = consumed_seconds([(n, prices[code], held[code]) for code, n in used
                                     if prices[code] is not None])
        assert consumed is not None
        hp_end = e.hp_end // SCALE if e.win else LOSS_HP
        recovery, counts = recovery_choice(max_hp - hp_end, max_hp, menu, EAT_SECONDS)
        recovery_mean += e.prob * recovery
        consumed_mean += e.prob * consumed
        hp_end_mean += e.prob * hp_end
        for code, n in used:
            used_mean[code] += e.prob * n
        for i, k in enumerate(counts):
            eaten_mean[i] += e.prob * k
    extra += recovery_mean + consumed_mean
    xp = game_data.xp_per_kill(monster, state.level, state.wisdom)
    fight = walk_seconds(state, game_data, monster, loadout, timing)
    used_units = tuple((code, math.ceil(used_mean[code])) for code, _ in loadout)
    if any(prices[code] is None and n > held[code] for code, n in used_units):
        return None
    eaten = tuple((f.code, math.ceil(k)) for f, k in zip(food, eaten_mean, strict=True) if k > 0)
    stats = fight_stats(wear(state, game_data, loadout)[0], game_data, monster)
    carry = (carried + sum(food_carry(n) for _, n in eaten)
             + sum(max(0, potion_carry(n) - stock)
                   for (_, stock), (_, n) in zip(loadout, used_units, strict=True)))
    table = game_data.monster_drops(monster)
    per_fight = drops_per_fight(p_win, [
        drops.units_per_attempt(monster, item, drop_rate, low, high, stats.prospecting)
        for item, drop_rate, low, high in table])
    walk = bank_walk(state, game_data, monster) if per_fight > 0 else 0
    trips = trip_share(trip_seconds(walk, Fraction(DEPOSIT_SECONDS_PER_CODE), len(table)),
                       per_fight, stats.inventory_max - carry)
    rate = Fraction(0) if trips is None else expected_xp_per_second(xp, p_win, fight, extra + trips)
    return LoopRate(rate, xp if p_win > 0 else 0, outcome.win, p_win, fight, recovery_mean,
                    consumed_mean, max_hp, math.floor(hp_end_mean), used_units, eaten,
                    trips is not None)
