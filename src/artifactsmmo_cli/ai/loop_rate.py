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
  terms are built over) with the restore's stock. Its duration is ONE
  `TYPICAL_FIGHT_COOLDOWN_SECONDS` (30 s): the code has no per-round seconds,
  and the fight cooldown it already prices is per fight.
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
  units rounded up, `hp_end` the expected end HP rounded down."""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

from artifactsmmo_cli.ai.actions.cost_core import CONSUMABLE_COOLDOWN_SECONDS, travel_seconds
from artifactsmmo_cli.ai.consumable_price import FIGHT_SECONDS, replacement_price_of
from artifactsmmo_cli.ai.fight_odds_core import win_probability as odds_win
from artifactsmmo_cli.ai.fight_terms_core import SCALE
from artifactsmmo_cli.ai.fight_tiles import fight_tiles
from artifactsmmo_cli.ai.fight_walk import fight_walk, odds_walk
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.heal_catalog import FOOD, heal_candidates
from artifactsmmo_cli.ai.held_stock import held_count
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loop_rate_core import consumed_seconds, expected_xp_per_second, recovery_choice
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
    not an expectation (`xp_per_second` carries the `p_win` weight)."""

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


def loop_rate(state: WorldState, game_data: GameData, monster: str,
              loadout: Sequence[tuple[str, int]], food: Sequence[FoodOffer],
              prices: Mapping[str, Fraction | None]) -> LoopRate | None:
    """The loop's expected XP per second against `monster` wearing `loadout` and
    recovering over `food` (see the module doc): every crit ending of the fight
    is priced (`odds_walk`), a loss walks back from `RESPAWN_TILE`. `prices`
    holds every loadout potion's replacement price. None when a potion with no
    replacement is expected (rounded up) to be drunk past the held units."""
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
    rate = expected_xp_per_second(xp, p_win, FIGHT_SECONDS, extra)
    used_units = tuple((code, math.ceil(used_mean[code])) for code, _ in loadout)
    if any(prices[code] is None and n > held[code] for code, n in used_units):
        return None
    eaten = tuple((f.code, math.ceil(k)) for f, k in zip(food, eaten_mean, strict=True) if k > 0)
    return LoopRate(rate, xp if p_win > 0 else 0, outcome.win, p_win, FIGHT_SECONDS, recovery_mean,
                    consumed_mean, max_hp, math.floor(hp_end_mean), used_units, eaten)
